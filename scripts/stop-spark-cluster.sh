#!/usr/bin/env bash
# 停止 start-spark-cluster.sh 拉起的 Worker 与 Master。
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"
PY="$ROOT/.venv/bin/python"
SPARK_HOME=$("$PY" -c 'import os, pyspark; print(os.path.dirname(pyspark.__file__))')
export SPARK_HOME
export SPARK_LOG_DIR="$ROOT/logs/spark"
export SPARK_PID_DIR="$ROOT/.run/spark"
export SPARK_IDENT_STRING=bishe
DAEMON="$SPARK_HOME/sbin/spark-daemon.sh"

if [ ! -d "$SPARK_PID_DIR" ]; then
  echo "==> 没有 Spark 集群 PID 目录，跳过"
  exit 0
fi
for pidfile in "$SPARK_PID_DIR"/*Worker*.pid; do
  [ -e "$pidfile" ] || continue
  inst=${pidfile%.pid}; inst=${inst##*-}
  echo "==> 停止 Worker $inst"
  "$DAEMON" stop org.apache.spark.deploy.worker.Worker "$inst" || true
done
for pidfile in "$SPARK_PID_DIR"/*Master*.pid; do
  [ -e "$pidfile" ] || continue
  echo "==> 停止 Master"
  "$DAEMON" stop org.apache.spark.deploy.master.Master 1 || true
done
echo "==> Spark 集群已停止"
