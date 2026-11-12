#!/usr/bin/env bash
# 按依赖顺序启动 MySQL 8.4、本地 Ollama（若 LLM 指向本机）、ai-service、后端和前端。
# 已经健康的服务不会重复启动。PID 写在 .run/，日志写在 logs/。
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_DIR="$ROOT/.run"
LOG_DIR="$ROOT/logs"
NO_FRONTEND=0
SPARK_CLUSTER=0

usage() {
  cat <<'EOF'
用法: bash scripts/start-all.sh [--no-frontend] [--spark-cluster]

启动 MySQL 8.4、Ollama（仅当 LLM_BASE_URL 指向本机且 ollama 存在）、ai-service（8000）、
Spring Boot（8080）和 Vite（5173）。已在监听的服务会跳过。
环境变量若已设置则原样传给子进程；否则依次从仓库根目录 .env、ai-service/.env 补齐。
--spark-cluster：先用 scripts/start-spark-cluster.sh 拉起 Standalone 伪分布式集群
（Master 7077 / UI 8081，2 个 Worker × 2 核 × 1536m），ai-service 以 SPARK_MASTER=spark://127.0.0.1:7077 启动。
不加时 SPARK_MASTER 默认 local[*]。
EOF
}

for arg in "$@"; do
  case "$arg" in
    --no-frontend) NO_FRONTEND=1 ;;
    --spark-cluster) SPARK_CLUSTER=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $arg" >&2; usage >&2; exit 1 ;;
  esac
done

mkdir -p "$RUN_DIR" "$LOG_DIR"
export PATH="${HOME}/.local/bin:${PATH}"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"
export PATH="${JAVA_HOME}/bin:${PATH}"

# 只填尚未设置的变量，避免把已导出的密钥打进日志。
load_dotenv() {
  local file=$1 line key val
  [ -f "$file" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%$'\r'}
    case "$line" in
      ''|\#*) continue ;;
      [A-Za-z_]*=*) ;;
      *) continue ;;
    esac
    key=${line%%=*}
    val=${line#*=}
    if [ "${val#\"}" != "$val" ] && [ "${val%\"}" != "$val" ]; then
      val=${val#\"}
      val=${val%\"}
    elif [ "${val#\'}" != "$val" ] && [ "${val%\'}" != "$val" ]; then
      val=${val#\'}
      val=${val%\'}
    fi
    if [ -z "${!key+x}" ]; then
      export "$key=$val"
    fi
  done < "$file"
}

if [ -f "$ROOT/.env" ]; then
  load_dotenv "$ROOT/.env"
  echo "==> 已读取 .env（不覆盖当前环境变量）"
fi

if [ -f "$ROOT/ai-service/.env" ]; then
  load_dotenv "$ROOT/ai-service/.env"
  echo "==> 已读取 ai-service/.env（不覆盖当前环境变量）"
fi

# 根目录用 DB_*，ai-service 读 MYSQL_*。只在后者还没设置时对齐，避免两套口令不一致。
sync_alias() {
  local src=$1 dst=$2
  if [ -z "${!dst+x}" ] && [ -n "${!src+x}" ]; then
    export "$dst=${!src}"
  fi
}
sync_alias DB_PASSWORD MYSQL_PASSWORD
sync_alias DB_USERNAME MYSQL_USER
sync_alias DB_HOST MYSQL_HOST
sync_alias DB_PORT MYSQL_PORT
sync_alias DB_NAME MYSQL_DB

pid_alive() {
  local file="$RUN_DIR/$1.pid" pid
  [ -f "$file" ] || return 1
  pid=$(tr -d '[:space:]' < "$file" || true)
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

wait_http() {
  local url=$1 seconds=$2 name=$3
  local i
  for i in $(seq 1 "$seconds"); do
    if curl -sf -m 2 -o /dev/null "$url"; then
      echo "==> ${name} 就绪: ${url}"
      return 0
    fi
    sleep 1
  done
  echo "错误: 等待 ${name} 超时 (${url})" >&2
  return 1
}

source "$ROOT/scripts/db-env.sh"

if db_ping; then
  echo "==> MySQL $(db_version) 已在运行"
else
  echo "==> 启动 MySQL"
  bash "$ROOT/scripts/start-mysql.sh"
  db_ping
fi

llm_base=${LLM_BASE_URL:-http://127.0.0.1:11434/v1}
llm_provider=$(printf '%s' "${LLM_PROVIDER:-ollama}" | tr '[:upper:]' '[:lower:]' | tr '-' '_')
llm_local=0
case "$llm_provider" in
  ollama|"")
    llm_local=1
    ;;
  openai_compatible)
    case "$llm_base" in
      *127.0.0.1*|*localhost*|*0.0.0.0*) llm_local=1 ;;
    esac
    ;;
esac

if [ "$llm_local" != 1 ]; then
  echo "==> LLM_PROVIDER=${llm_provider:-ollama} 不使用本机模型，跳过 Ollama"
elif curl -sf -m 2 -o /dev/null "http://127.0.0.1:11434/api/tags"; then
  echo "==> Ollama 已在运行"
  bash "$ROOT/scripts/start-ollama.sh" || echo "警告: 检查模型/推理线程失败，继续启动"
elif ! command -v ollama >/dev/null 2>&1; then
  echo "==> 未找到 ollama，跳过本地模型（大模型不可达时助手走离线模式）"
elif pid_alive ollama; then
  echo "==> Ollama 正在启动，继续等待"
  wait_http "http://127.0.0.1:11434/api/tags" 40 "Ollama"
else
  echo "==> 启动 Ollama"
  nohup ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
  echo $! > "$RUN_DIR/ollama.pid"
  wait_http "http://127.0.0.1:11434/api/tags" 40 "Ollama"
  bash "$ROOT/scripts/start-ollama.sh"
fi

kb_count=$(db_sql "SELECT COUNT(*) FROM rag_document WHERE deleted=0" || true)
if [ "${kb_count:-}" = "0" ]; then
  echo "==> rag_document 为空，重建知识库"
  (cd "$ROOT/ai-service" && "$ROOT/.venv/bin/python" -m app.rag.ingest --all)
fi

if [ "$SPARK_CLUSTER" = 1 ]; then
  bash "$ROOT/scripts/start-spark-cluster.sh"
  export SPARK_MASTER="spark://127.0.0.1:${SPARK_MASTER_PORT:-7077}"
  if curl -sf -m 2 -o /dev/null "http://127.0.0.1:8000/health"; then
    echo "==> 注意: ai-service 已在运行，沿用它启动时的 SPARK_MASTER；要切到集群请先 stop-all 再加 --spark-cluster 启动"
  fi
fi
echo "==> SPARK_MASTER=${SPARK_MASTER:-local[*]}（local[*] 实际按 SPARK_LOCAL_CORES=${SPARK_LOCAL_CORES:-4} 限核；推荐/分析批次在独立子进程中以 nice ${SPARK_BATCH_NICE:-10} 运行）"

if curl -sf -m 2 -o /dev/null "http://127.0.0.1:8000/health"; then
  echo "==> ai-service 已在运行"
elif pid_alive ai-service; then
  echo "==> ai-service 正在启动，继续等待"
  wait_http "http://127.0.0.1:8000/health" 90 "ai-service" \
    || { echo "最近日志:" >&2; tail -n 40 "$LOG_DIR/ai-service.log" >&2 || true; exit 1; }
else
  echo "==> 启动 ai-service"
  (
    cd "$ROOT/ai-service"
    nohup "$ROOT/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 \
      > "$LOG_DIR/ai-service.log" 2>&1 &
    echo $! > "$RUN_DIR/ai-service.pid"
  )
  wait_http "http://127.0.0.1:8000/health" 90 "ai-service" \
    || { echo "最近日志:" >&2; tail -n 40 "$LOG_DIR/ai-service.log" >&2 || true; exit 1; }
fi

JAR="$ROOT/backend/target/job-backend-1.0.0.jar"
if curl -sf -m 2 -o /dev/null "http://127.0.0.1:8080/api/health"; then
  echo "==> 后端已在运行"
elif pid_alive backend; then
  echo "==> 后端正在启动，继续等待"
  wait_http "http://127.0.0.1:8080/api/health" 90 "后端" \
    || { echo "最近日志:" >&2; tail -n 40 "$LOG_DIR/backend.log" >&2 || true; exit 1; }
else
  if [ ! -f "$JAR" ]; then
    echo "==> 打包后端"
    (cd "$ROOT/backend" && mvn -q -DskipTests package)
  fi
  [ -f "$JAR" ] || { echo "错误: 找不到 $JAR" >&2; exit 1; }
  echo "==> 启动后端"
  nohup java -jar "$JAR" > "$LOG_DIR/backend.log" 2>&1 &
  echo $! > "$RUN_DIR/backend.pid"
  wait_http "http://127.0.0.1:8080/api/health" 90 "后端" \
    || { echo "最近日志:" >&2; tail -n 40 "$LOG_DIR/backend.log" >&2 || true; exit 1; }
fi

if [ "$NO_FRONTEND" = 1 ]; then
  echo "==> 已跳过前端 (--no-frontend)"
elif curl -sf -m 2 -o /dev/null "http://127.0.0.1:5173/"; then
  echo "==> 前端已在运行"
elif pid_alive frontend; then
  echo "==> 前端正在启动，继续等待"
  wait_http "http://127.0.0.1:5173/" 40 "前端" \
    || { echo "最近日志:" >&2; tail -n 40 "$LOG_DIR/frontend.log" >&2 || true; exit 1; }
else
  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    echo "==> 安装前端依赖"
    (cd "$ROOT/frontend" && pnpm install)
  fi
  echo "==> 启动前端"
  (
    cd "$ROOT/frontend"
    nohup pnpm dev --host 127.0.0.1 --port 5173 > "$LOG_DIR/frontend.log" 2>&1 &
    echo $! > "$RUN_DIR/frontend.pid"
  )
  wait_http "http://127.0.0.1:5173/" 40 "前端" \
    || { echo "最近日志:" >&2; tail -n 40 "$LOG_DIR/frontend.log" >&2 || true; exit 1; }
fi

echo
echo "服务地址"
echo "  前端     http://127.0.0.1:5173"
echo "  后端     http://127.0.0.1:8080/api/health"
echo "  AI 服务  http://127.0.0.1:8000/health"
echo "  Ollama   http://127.0.0.1:11434"
echo "  MySQL    127.0.0.1:3306  库 job_platform（$(db_version)）"
echo
echo "演示账号"
echo "  admin / admin123"
echo "  student / student123"
echo "  company / company123"
echo
echo "日志在 logs/ ，PID 在 .run/ 。停止请执行 bash scripts/stop-all.sh"
