#!/usr/bin/env bash
# 公共测试函数：curl + jq 断言。BASE 可通过环境变量覆盖。
BASE=${BASE:-http://localhost:8080/api}
PASS=${PASS:-0}; FAIL=${FAIL:-0}
STATE_FILE=${STATE_FILE:-/tmp/job-api-test-state.env}
# 数据库辅助函数 db_sql / db_ping（MySQL 8.4 客户端）
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../scripts" && pwd)/db-env.sh"
[ -f "$STATE_FILE" ] && source "$STATE_FILE"

save_state() { # save_state KEY VALUE —— 在脚本之间共享变量
  touch "$STATE_FILE"; sed -i "/^$1=/d" "$STATE_FILE"; echo "$1='$2'" >> "$STATE_FILE"; export "$1=$2"; }

# req METHOD PATH [TOKEN] [JSON]  -> 设置 $HTTP（状态码）与 $BODY
req() {
  local m=$1 p=$2 t=$3 d=$4
  local args=(-s --path-as-is -o /tmp/_body -w '%{http_code}' -X "$m" "$BASE$p")
  [ -n "$t" ] && args+=(-H "Authorization: Bearer $t")
  [ -n "$d" ] && args+=(-H 'Content-Type: application/json' --data-raw "$d")
  HTTP=$(curl "${args[@]}"); BODY=$(cat /tmp/_body)
}
ok()   { PASS=$((PASS+1)); echo "  [PASS] $1"; }
bad()  { FAIL=$((FAIL+1)); echo "  [FAIL] $1 (http=$HTTP body=${BODY:0:300})"; }
# expect_http CODE DESC
expect_http() { [ "$HTTP" = "$1" ] && ok "$2" || bad "$2: 期望 HTTP $1"; }
# expect_ok DESC —— HTTP 200 且 Result.code==200
expect_ok() { [ "$HTTP" = 200 ] && [ "$(echo "$BODY" | jq -r .code)" = 200 ] && ok "$1" || bad "$1: 期望成功"; }
# expect_fail DESC —— Result.code != 200（业务失败）
expect_fail() { [ -n "$HTTP" ] && [ "$HTTP" != 000 ] && [ "$(echo "$BODY" | jq -r .code 2>/dev/null)" != 200 ] && ok "$1" || bad "$1: 期望失败"; }
# expect_jq FILTER EXPECTED DESC
expect_jq() { local v; v=$(echo "$BODY" | jq -r "$1" 2>/dev/null); [ "$v" = "$2" ] && ok "$3" || bad "$3: $1 期望 '$2' 实际 '$v'"; }
jqv() { echo "$BODY" | jq -r "$1"; }
login() { # login USER PASS -> 设置 $TOKEN（失败为空）
  req POST /public/auth/login "" "{\"username\":\"$1\",\"password\":\"$2\"}"; TOKEN=$(jqv '.data.token // empty'); }
summary() { echo "== $(basename "$0"): PASS=$PASS FAIL=$FAIL"; echo "$(basename "$0") $PASS $FAIL" >> /tmp/job-api-test-summary.txt; [ "$FAIL" = 0 ]; }
# Spark 批次轮询（直连 ai-service，不计入断言）。批次与助手问答同机争 CPU，后续脚本开始前要等批次结束。
AI_BASE=${AI_BASE:-http://127.0.0.1:8000}
# spark_batch_state BATCH -> 输出 QUEUED/RUNNING/FINISHED，取不到时输出空
spark_batch_state() { curl -s -m 5 "$AI_BASE/spark/tasks/$1" | jq -r '.data.state // empty' 2>/dev/null; }
# wait_spark_batch BATCH [SECONDS] -> 等到 FINISHED 返回 0，超时返回 1；结束后 $BATCH_BODY 为批次详情
wait_spark_batch() {
  local batch=$1 limit=${2:-900} waited=0 state
  while [ "$waited" -lt "$limit" ]; do
    state=$(spark_batch_state "$batch")
    if [ "$state" = FINISHED ]; then BATCH_BODY=$(curl -s -m 5 "$AI_BASE/spark/tasks/$batch"); return 0; fi
    sleep 3; waited=$((waited + 3))
  done
  BATCH_BODY=$(curl -s -m 5 "$AI_BASE/spark/tasks/$batch"); return 1
}
# wait_spark_idle [SECONDS] -> 没有运行或排队中的批次时返回 0（ai-service 未启动也视为空闲）
wait_spark_idle() {
  local limit=${1:-900} waited=0 running
  while [ "$waited" -lt "$limit" ]; do
    running=$(curl -s -m 5 "$AI_BASE/spark/status" | jq -r '.data.running // false' 2>/dev/null)
    [ "$running" != true ] && return 0
    sleep 3; waited=$((waited + 3))
  done
  return 1
}
