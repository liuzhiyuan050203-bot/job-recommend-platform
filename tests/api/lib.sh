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

# ---- 夹具收尾 ----
# 测试在演示库里建的账号、职位、简历，在脚本退出时逻辑删除，连带投递、日志、面试、收藏、行为日志，
# 并重算受影响职位的投递 / 收藏数，避免演示账号的首页、看板和推荐被测试数据淹没。
# 用法：fixture_user 用户名 / fixture_job 职位编号 / fixture_resume 简历编号 /
#       fixture_keep_default 用户名（先记下当前默认简历，收尾时恢复）。
# 自带 trap 的脚本要在自己的 cleanup 里调用 purge_fixtures。KEEP_FIXTURES=1 时保留现场便于排查。
FIXTURE_USERS=(); FIXTURE_JOBS=(); FIXTURE_RESUMES=(); FIXTURE_DEFAULTS=()
fixture_user()   { [[ "${1:-}" =~ ^[A-Za-z0-9_]+$ ]] && FIXTURE_USERS+=("$1"); return 0; }
fixture_job()    { [[ "${1:-}" =~ ^[0-9]+$ ]] && FIXTURE_JOBS+=("$1"); return 0; }
fixture_resume() { [[ "${1:-}" =~ ^[0-9]+$ ]] && FIXTURE_RESUMES+=("$1"); return 0; }
fixture_keep_default() {
  [[ "${1:-}" =~ ^[A-Za-z0-9_]+$ ]] || return 0
  local id
  id=$(db_sql "SELECT r.id FROM stu_resume r JOIN sys_user u ON u.id = r.user_id WHERE u.username = '$1' AND r.deleted = 0 AND r.is_default = 1 LIMIT 1")
  FIXTURE_DEFAULTS+=("$1:${id:-0}")
}
_ids_sql() { # _ids_sql "SELECT ..." -> 逗号分隔编号，没有时输出 NULL
  local v
  v=$(db_sql "SET SESSION group_concat_max_len = 1000000; $1")
  [ -n "$v" ] && [ "$v" != NULL ] && echo "$v" || echo NULL
}
_join_ids() { local IFS=,; local v="$*"; [ -n "$v" ] && echo "$v" || echo NULL; }
purge_fixtures() {
  [ "${KEEP_FIXTURES:-0}" = 1 ] && return 0
  [ "${#FIXTURE_USERS[@]}${#FIXTURE_JOBS[@]}${#FIXTURE_RESUMES[@]}${#FIXTURE_DEFAULTS[@]}" = 0000 ] && return 0
  db_ping || return 0
  local names="" u uids cids jobs resumes apps touched entry name rid
  for u in "${FIXTURE_USERS[@]}"; do names+="'$u',"; done
  names=${names%,}; [ -n "$names" ] || names="NULL"
  uids=$(_ids_sql "SELECT GROUP_CONCAT(id) FROM sys_user WHERE username IN ($names) AND username NOT IN ('admin','student','company')")
  cids=$(_ids_sql "SELECT GROUP_CONCAT(id) FROM ent_company WHERE user_id IN ($uids)")
  jobs=$(_ids_sql "SELECT GROUP_CONCAT(id) FROM job_position WHERE id IN ($(_join_ids "${FIXTURE_JOBS[@]}")) OR company_id IN ($cids)")
  resumes=$(_ids_sql "SELECT GROUP_CONCAT(id) FROM stu_resume WHERE id IN ($(_join_ids "${FIXTURE_RESUMES[@]}")) OR user_id IN ($uids)")
  apps=$(_ids_sql "SELECT GROUP_CONCAT(id) FROM job_application WHERE position_id IN ($jobs) OR user_id IN ($uids) OR resume_id IN ($resumes)")
  touched=$(_ids_sql "SELECT GROUP_CONCAT(DISTINCT position_id) FROM (SELECT position_id FROM job_application WHERE id IN ($apps) UNION SELECT position_id FROM job_favorite WHERE user_id IN ($uids)) t")
  db_sql "
    UPDATE job_interview SET deleted = 1 WHERE deleted = 0 AND (application_id IN ($apps) OR position_id IN ($jobs) OR user_id IN ($uids));
    UPDATE job_application_log SET deleted = 1 WHERE deleted = 0 AND application_id IN ($apps);
    UPDATE job_application SET deleted = 1 WHERE deleted = 0 AND id IN ($apps);
    UPDATE job_favorite SET deleted = 1 WHERE deleted = 0 AND (position_id IN ($jobs) OR user_id IN ($uids));
    UPDATE user_behavior_log SET deleted = 1 WHERE deleted = 0 AND ((target_type = 1 AND target_id IN ($jobs)) OR user_id IN ($uids));
    UPDATE job_position SET deleted = 1, shelf_status = 0 WHERE deleted = 0 AND id IN ($jobs);
    UPDATE stu_resume SET deleted = 1, is_default = 0 WHERE deleted = 0 AND id IN ($resumes);
    UPDATE stu_skill SET deleted = 1 WHERE deleted = 0 AND user_id IN ($uids);
    UPDATE stu_profile SET deleted = 1 WHERE deleted = 0 AND user_id IN ($uids);
    UPDATE com_comment SET deleted = 1 WHERE deleted = 0 AND user_id IN ($uids);
    UPDATE com_post SET deleted = 1 WHERE deleted = 0 AND (user_id IN ($uids) OR position_id IN ($jobs));
    UPDATE ai_session SET deleted = 1 WHERE deleted = 0 AND user_id IN ($uids);
    UPDATE ent_company SET deleted = 1 WHERE deleted = 0 AND id IN ($cids);
    UPDATE sys_user SET deleted = 1 WHERE deleted = 0 AND id IN ($uids);
    UPDATE job_position p SET
      apply_count = (SELECT COUNT(*) FROM job_application a WHERE a.position_id = p.id AND a.deleted = 0),
      favorite_count = (SELECT COUNT(*) FROM job_favorite f WHERE f.position_id = p.id AND f.deleted = 0)
    WHERE p.id IN ($touched) AND p.deleted = 0;" || true
  for entry in "${FIXTURE_DEFAULTS[@]}"; do
    name=${entry%%:*}; rid=${entry##*:}
    [ "$rid" != 0 ] && db_sql "UPDATE stu_resume r JOIN sys_user u ON u.id = r.user_id SET r.is_default = (r.id = $rid) WHERE u.username = '$name' AND r.deleted = 0" || true
  done
  FIXTURE_USERS=(); FIXTURE_JOBS=(); FIXTURE_RESUMES=(); FIXTURE_DEFAULTS=()
}
trap purge_fixtures EXIT
