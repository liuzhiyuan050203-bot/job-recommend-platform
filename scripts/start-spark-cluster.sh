#!/usr/bin/env bash
# 在本机拉起 Spark Standalone 伪分布式集群：1 个 Master + N 个 Worker（默认 2 × 2 核 × 1536m）。
# 使用 .venv 里 pip 安装的 PySpark（SPARK_HOME = pyspark 包目录），不需要另装 Spark 发行版。
# 已经在运行时不会重复启动。PID 在 .run/spark/，日志在 logs/spark/。
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"
export PATH="${JAVA_HOME}/bin:${PATH}"
PY="$ROOT/.venv/bin/python"
SPARK_HOME=$("$PY" -c 'import os, pyspark; print(os.path.dirname(pyspark.__file__))')
export SPARK_HOME
export SPARK_LOG_DIR="$ROOT/logs/spark"
export SPARK_PID_DIR="$ROOT/.run/spark"
export SPARK_WORKER_DIR="${SPARK_WORKER_DIR:-/tmp/bishe-spark-work}"
export SPARK_LOCAL_IP=127.0.0.1
export SPARK_MASTER_HOST=127.0.0.1
export SPARK_IDENT_STRING=bishe
export PYSPARK_PYTHON="$PY"

MASTER_PORT=${SPARK_MASTER_PORT:-7077}
MASTER_UI_PORT=${SPARK_MASTER_WEBUI_PORT:-8081}
WORKERS=${SPARK_WORKER_INSTANCES:-2}
WORKER_CORES=${SPARK_WORKER_CORES:-2}
WORKER_MEMORY=${SPARK_WORKER_MEMORY:-1536m}
WORKER_UI_BASE=${SPARK_WORKER_WEBUI_BASE:-8082}
MASTER_URL="spark://127.0.0.1:${MASTER_PORT}"

usage() {
  cat <<USAGE
用法: bash scripts/start-spark-cluster.sh

可用环境变量（括号内为默认）：
  SPARK_MASTER_PORT (7077)  SPARK_MASTER_WEBUI_PORT (8081)
  SPARK_WORKER_INSTANCES (2)  SPARK_WORKER_CORES (2)  SPARK_WORKER_MEMORY (1536m)
  SPARK_WORKER_WEBUI_BASE (8082，第 i 个 Worker 用 base+i-1)
启动后让 ai-service 用集群：export SPARK_MASTER=${MASTER_URL}
USAGE
}
case "${1:-}" in -h|--help) usage; exit 0 ;; esac

mkdir -p "$SPARK_LOG_DIR" "$SPARK_PID_DIR" "$SPARK_WORKER_DIR"
DAEMON="$SPARK_HOME/sbin/spark-daemon.sh"
[ -x "$DAEMON" ] || chmod +x "$DAEMON" "$SPARK_HOME/sbin/spark-config.sh" "$SPARK_HOME/bin/spark-class" 2>/dev/null || true

port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

if port_open "$MASTER_PORT"; then
  echo "==> Spark Master 已在 ${MASTER_URL}"
else
  echo "==> 启动 Spark Master ${MASTER_URL}（UI http://127.0.0.1:${MASTER_UI_PORT}）"
  "$DAEMON" start org.apache.spark.deploy.master.Master 1 \
    --host 127.0.0.1 --port "$MASTER_PORT" --webui-port "$MASTER_UI_PORT"
  for _ in $(seq 1 60); do port_open "$MASTER_PORT" && break; sleep 0.5; done
  port_open "$MASTER_PORT" || { echo "Master 未能启动，见 $SPARK_LOG_DIR" >&2; exit 1; }
fi

for i in $(seq 1 "$WORKERS"); do
  ui=$((WORKER_UI_BASE + i - 1))
  if port_open "$ui"; then
    echo "==> Worker $i 已在运行（UI $ui）"
    continue
  fi
  echo "==> 启动 Worker $i：${WORKER_CORES} 核 / ${WORKER_MEMORY}（UI $ui）"
  "$DAEMON" start org.apache.spark.deploy.worker.Worker "$i" \
    --host 127.0.0.1 --cores "$WORKER_CORES" --memory "$WORKER_MEMORY" \
    --webui-port "$ui" --work-dir "$SPARK_WORKER_DIR/worker-$i" "$MASTER_URL"
done

# 等所有 Worker 在 Master 上注册（Master /json 的 aliveworkers）
for _ in $(seq 1 60); do
  alive=$(curl -s "http://127.0.0.1:${MASTER_UI_PORT}/json/" | "$PY" -c 'import json,sys; print(json.load(sys.stdin).get("aliveworkers", 0))' 2>/dev/null || echo 0)
  [ "$alive" -ge "$WORKERS" ] && break
  sleep 0.5
done
echo "==> 已注册 Worker: ${alive:-0}/${WORKERS}"
[ "${alive:-0}" -ge "$WORKERS" ] || { echo "Worker 注册不全，见 $SPARK_LOG_DIR" >&2; exit 1; }
echo "==> 集群就绪。ai-service 使用集群：export SPARK_MASTER=${MASTER_URL}"
