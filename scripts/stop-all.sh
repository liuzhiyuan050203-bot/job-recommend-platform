#!/usr/bin/env bash
# 停止 scripts/start-all.sh 记录过 PID 的进程。默认保留 MariaDB。
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_DIR="$ROOT/.run"
WITH_MYSQL=0

usage() {
  cat <<'EOF'
用法: bash scripts/stop-all.sh [--with-mysql]

按 .run/*.pid 停止前端、后端、ai-service 和由 start-all 拉起的 Ollama。
没有 PID 文件时直接返回。加上 --with-mysql 时再停止 MariaDB。
EOF
}

for arg in "$@"; do
  case "$arg" in
    --with-mysql) WITH_MYSQL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $arg" >&2; usage >&2; exit 1 ;;
  esac
done

mkdir -p "$RUN_DIR"

kill_tree() {
  local pid=$1 sig=${2:-TERM} child children
  case "$pid" in
    ''|*[!0-9]*) return 0 ;;
  esac
  if [ "$pid" -le 1 ]; then
    return 0
  fi
  children=$(ps -o pid= --ppid "$pid" 2>/dev/null || true)
  for child in $children; do
    kill_tree "$child" "$sig"
  done
  kill -s "$sig" "$pid" 2>/dev/null || true
}

stop_one() {
  local name=$1 file="$RUN_DIR/$1.pid" pid i
  if [ ! -f "$file" ]; then
    echo "==> ${name} 无 PID 文件，跳过"
    return 0
  fi
  pid=$(tr -d '[:space:]' < "$file" || true)
  rm -f "$file"
  case "$pid" in
    ''|*[!0-9]*) echo "==> ${name} PID 无效，已清理"; return 0 ;;
  esac
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "==> ${name} 已不在运行 (pid=${pid})"
    return 0
  fi
  echo "==> 停止 ${name} (pid=${pid})"
  kill_tree "$pid" TERM
  for i in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.3
  done
  echo "==> ${name} 未退出，发送 KILL"
  kill_tree "$pid" KILL
  sleep 0.5
}

stop_one frontend
stop_one backend
stop_one ai-service
stop_one ollama

if [ "$WITH_MYSQL" = 1 ]; then
  echo "==> 停止 MariaDB"
  if sudo service mariadb stop; then
    echo "==> MariaDB 已停止"
  else
    echo "错误: MariaDB 停止失败" >&2
    exit 1
  fi
else
  echo "==> 保留 MariaDB（需要停止时加 --with-mysql）"
fi

echo "==> stop-all 完成"
