#!/usr/bin/env bash
# MySQL 8 切换后的端到端冒烟：学生 / 企业 / 管理员三种角色的主流程，
# 管理员经接口触发完整 Spark 离线批次（清洗、聚合、薪资回归、推荐），确认结果写入 MySQL。
# 需要后端 8080、ai-service 8000 已启动。用法：bash tests/e2e/smoke-mysql8.sh
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
source "$ROOT/scripts/db-env.sh"
B=http://127.0.0.1:8080/api
P=0; F=0
ok()  { P=$((P+1)); echo "  [PASS] $1"; }
bad() { F=$((F+1)); echo "  [FAIL] $1"; }
chk() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }
login() { curl -s -X POST "$B/public/auth/login" -H 'Content-Type: application/json' -d "{\"username\":\"$1\",\"password\":\"$2\"}" | jq -r '.data.token // empty'; }
get() { curl -s -m 30 -H "Authorization: Bearer $1" "$B$2"; }
post() { curl -s -m 60 -X POST -H "Authorization: Bearer $1" -H 'Content-Type: application/json' -d "$3" "$B$2"; }

echo "数据库: MySQL $(db_version)"
TA=$(login admin admin123); TS=$(login student student123); TC=$(login company company123)
chk "三种角色登录" '[ -n "$TA" ] && [ -n "$TS" ] && [ -n "$TC" ]'

echo "## 学生"
chk "学生工作台" '[ "$(get "$TS" /student/dashboard | jq -r .code)" = 200 ]'
R=$(get "$TS" "/student/recommend?size=10")
chk "个性化推荐有结果" '[ "$(jq -r ".code" <<<"$R")" = 200 ] && [ "$(jq "[.data.records // .data | .[]?] | length" <<<"$R")" -ge 1 ]'
chk "职位搜索（关键词 Java）" '[ "$(get "$TS" "/public/jobs?keyword=Java&current=1&size=5" | jq ".data.total")" -ge 1 ]'
chk "薪资预测" '[ "$(get "$TS" "/public/stats/salary/predict?education=2&experienceYears=0&city=%E5%8C%97%E4%BA%AC&techDirection=%E5%90%8E%E7%AB%AF%E5%BC%80%E5%8F%91" | jq -r .code)" = 200 ]'
SSE=$(curl -s -m 180 -N -X POST -H "Authorization: Bearer $TS" -H 'Content-Type: application/json' -d '{"question":"三方协议怎么签？"}' "$B/student/ai/chat/stream")
chk "AI 助手流式回答（含 token 与 done 事件）" 'grep -q "token" <<<"$SSE" && grep -q "done" <<<"$SSE"'
chk "AI 会话写入 MySQL" '[ "$(db_sql "select count(*) from ai_message where create_time > now() - interval 5 minute")" -ge 1 ]'

echo "## 企业"
chk "企业工作台" '[ "$(get "$TC" /company/dashboard | jq -r .code)" = 200 ]'
chk "企业职位列表" '[ "$(get "$TC" "/company/jobs?current=1&size=5" | jq ".data.total")" -ge 1 ]'
chk "企业收到的投递" '[ "$(get "$TC" "/company/applications?current=1&size=5" | jq -r .code)" = 200 ]'

echo "## 管理员"
chk "管理员总览" '[ "$(get "$TA" /admin/dashboard/overview | jq -r .code)" = 200 ]'
# wait_batch BATCH：等到该批次没有运行中的任务（最多 10 分钟）
wait_batch() {
  local i n
  for i in $(seq 1 120); do
    n=$(db_sql "select count(*) from spark_task_log where batch_no='$1' and status=0")
    [ "$(db_sql "select count(*) from spark_task_log where batch_no='$1'")" -ge 1 ] && [ "$n" = 0 ] && return 0
    sleep 5
  done
  return 1
}
# 平台同一时间只允许一个离线批次，先等 ETL 结束再提交推荐
B1=$(post "$TA" /admin/spark/run '{"tasks":["clean","aggregate","salary_regression"]}' | jq -r '.data.batchNo // empty')
[ -n "$B1" ] && wait_batch "$B1"
B2=$(post "$TA" /admin/recommend/run '{}' | jq -r '.data.batchNo // empty')
[ -n "$B2" ] && wait_batch "$B2"
echo "  批次: ETL=$B1 推荐=$B2"
chk "触发 Spark ETL 与推荐" '[ -n "$B1" ] && [ -n "$B2" ]'
db_sql "select batch_no, task_code, status, timestampdiff(second,start_time,end_time), output_count from spark_task_log where batch_no in ('$B1','$B2') order by id" | sed 's/^/    /'
chk "四个 Spark 任务全部成功" '[ "$(db_sql "select count(*) from spark_task_log where batch_no in ('"'"'$B1'"'"','"'"'$B2'"'"') and status=1")" = 4 ]'
chk "params_json 为 JSON 类型且记录 sparkMaster" '[ -n "$(db_sql "select json_unquote(json_extract(params_json,'"'"'$.sparkMaster'"'"')) from spark_task_log where batch_no='"'"'$B1'"'"' limit 1")" ]'
chk "新推荐批次已发布" '[ "$(db_sql "select count(*) from spark_recommend where batch_no='"'"'$B2'"'"' and is_latest=1")" -ge 1 ]'
chk "推荐评估接口" '[ "$(get "$TA" /admin/recommend/eval | jq -r .code)" = 200 ]'

echo "合计 PASS=$P FAIL=$F"
[ "$F" = 0 ]
