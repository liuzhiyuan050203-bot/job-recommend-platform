#!/usr/bin/env bash
# 推荐批次运行时，直接调 Ollama /api/generate 测解码速度（tok/s），比较 Spark 资源配置与 Ollama 线程数。
# 用法: bash experiments/stability/ollama_under_spark.sh <label> <SPARK_LOCAL_CORES> <nice> [threads...]
# 例:   bash experiments/stability/ollama_under_spark.sh old 0 0 8 6 4     # local[*]、不降优先级（改造前）
#       bash experiments/stability/ollama_under_spark.sh new 4 10 8 6 4    # local[4]、nice 10（改造后默认）
# 批次子进程会真实写入一批推荐结果（与后台触发相同）。输出 JSON 行到 experiments/results/stability_ollama_<label>.jsonl
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
LABEL=$1; CORES=$2; NICE=$3; shift 3
THREADS=("$@"); [ ${#THREADS[@]} -gt 0 ] || THREADS=(8 6 4)
OUT="$ROOT/experiments/results/stability_ollama_${LABEL}.jsonl"
: > "$OUT"
BATCH=$(date +%Y%m%d%H%M%S)$(head -c2 /dev/urandom | od -An -tx1 | tr -d ' \n')
probe() {
  curl -s 127.0.0.1:11434/api/generate -d "{\"model\":\"qwen2.5:3b\",\"prompt\":\"请用三句话介绍三方协议的签订流程。\",\"stream\":false,\"options\":{\"num_thread\":$1,\"num_predict\":64,\"temperature\":0,\"seed\":1}}" \
    | jq -c --arg nt "$1" --arg phase "$2" --arg t "$(date +%T)" '{t:$t, phase:$phase, threads:($nt|tonumber), tokens:.eval_count, tok_s:((.eval_count/(.eval_duration/1e9))*100|round/100), prompt_ms:((.prompt_eval_duration/1e6)|round)}'
}
cd "$ROOT/ai-service"
SPARK_LOCAL_CORES=$CORES nice -n "$NICE" "$ROOT/.venv/bin/python" -m app.spark.batch_worker --batch-no "$BATCH" --tasks recommend \
  > "$ROOT/experiments/results/stability_ollama_${LABEL}_batch.log" 2>&1 &
PID=$!
START=$(date +%s)
sleep 15   # 跳过 JVM 启动
while kill -0 "$PID" 2>/dev/null; do
  for nt in "${THREADS[@]}"; do
    kill -0 "$PID" 2>/dev/null || break
    probe "$nt" batch | tee -a "$OUT"
  done
done
wait "$PID"; RC=$?
echo "{\"batch\":\"$BATCH\",\"rc\":$RC,\"batch_wall_s\":$(( $(date +%s) - START )),\"cores\":$CORES,\"nice\":$NICE}" | tee -a "$OUT"
