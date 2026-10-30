#!/usr/bin/env bash
# 准备 MariaDB 与后端，依次执行 tests/api 下的接口脚本并打印汇总。
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

STARTED_BACKEND=0
BACKEND_PID=""

cleanup() {
  if [ "$STARTED_BACKEND" = 1 ] && [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$BACKEND_PID" 2>/dev/null || break
      sleep 0.5
    done
    if kill -0 "$BACKEND_PID" 2>/dev/null; then
      kill -9 "$BACKEND_PID" 2>/dev/null || true
    fi
    wait "$BACKEND_PID" 2>/dev/null || true
    echo "已关闭本次启动的后端 (pid=$BACKEND_PID)"
  fi
}
trap cleanup EXIT

mysql_ok() {
  mariadb-admin --protocol=tcp -h127.0.0.1 -P3306 -ujob -pjob123 ping --silent 2>/dev/null
}

if mysql_ok; then
  echo "MariaDB 已在运行"
else
  echo "MariaDB 未响应，尝试启动..."
  bash "$ROOT/scripts/start-mysql.sh" || exit 1
  mysql_ok || { echo "MariaDB 启动失败"; exit 1; }
fi

export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"
export PATH="$HOME/.local/bin:$JAVA_HOME/bin:$PATH"

if curl -sf -m 3 -o /dev/null "http://127.0.0.1:8080/api/health"; then
  echo "8080 已响应，沿用现有后端"
else
  echo "8080 未响应，打包并启动后端..."
  (cd "$ROOT/backend" && mvn -q -DskipTests package) || { echo "Maven 打包失败"; exit 1; }
  JAR="$ROOT/backend/target/job-backend-1.0.0.jar"
  [ -f "$JAR" ] || { echo "找不到 $JAR"; exit 1; }
  java -jar "$JAR" > /tmp/job-backend-test.log 2>&1 &
  BACKEND_PID=$!
  STARTED_BACKEND=1
  ready=0
  for _ in $(seq 1 90); do
    if curl -sf -m 2 -o /dev/null "http://127.0.0.1:8080/api/health"; then
      ready=1
      break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
      echo "后端进程已退出，最近日志："
      tail -n 80 /tmp/job-backend-test.log || true
      exit 1
    fi
    sleep 1
  done
  if [ "$ready" != 1 ]; then
    echo "等待 /api/health 超时，最近日志："
    tail -n 80 /tmp/job-backend-test.log || true
    exit 1
  fi
  echo "后端已就绪"
fi

rm -f /tmp/job-api-test-state.env /tmp/job-api-test-summary.txt
: > /tmp/job-api-test-summary.txt

any_fail=0
for script in "$ROOT"/tests/api/[0-9]*.sh; do
  echo
  bash "$script" || any_fail=1
done

echo
echo "================ 汇总 ================"
printf '%-22s %8s %8s\n' "脚本" "PASS" "FAIL"
total_p=0
total_f=0
while read -r name p f; do
  [ -n "${name:-}" ] || continue
  printf '%-22s %8s %8s\n' "$name" "$p" "$f"
  total_p=$((total_p + p))
  total_f=$((total_f + f))
done < /tmp/job-api-test-summary.txt
printf '%-22s %8s %8s\n' "合计" "$total_p" "$total_f"

if [ "$any_fail" != 0 ] || [ "$total_f" != 0 ]; then
  exit 1
fi
exit 0
