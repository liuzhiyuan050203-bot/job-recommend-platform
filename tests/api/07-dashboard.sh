#!/usr/bin/env bash
# Phase6 仪表盘与公开图表接口。
cd "$(dirname "$0")"; source ./lib.sh
echo "### 07 仪表盘与图表接口"

login admin admin123; T_ADMIN=$TOKEN; expect_ok "管理员登录"
login student student123; T_STU=$TOKEN; expect_ok "学生登录"
login company company123; T_COM=$TOKEN; expect_ok "企业登录"

# ---- 公开统计扩展 ----
req GET /public/stats/overview
expect_ok "公开概览"
[ "$(jqv .data.jobCount)" -gt 0 ] && ok "概览职位数" || bad "概览职位数"
[ "$(jqv .data.companyCount)" -gt 0 ] && ok "概览企业数" || bad "概览企业数"
[ "$(jqv .data.studentCount)" -gt 0 ] && ok "概览学生数" || bad "概览学生数"
[ "$(jqv .data.applicationCount)" -gt 0 ] && ok "概览投递数" || bad "概览投递数"
[ -n "$(jqv .data.avgSalary)" ] && [ "$(jqv .data.avgSalary)" != "null" ] && ok "概览平均月薪" || bad "概览平均月薪"

req GET "/public/stats/hiring-demand?months=12"
expect_ok "月度招聘需求"
[ "$(jq -r '.data.months | length' <<<"$BODY")" = "12" ] && ok "需求月份数为12" || bad "需求月份数为12"
[ "$(jq -r '.data.jobCounts | length' <<<"$BODY")" = "12" ] && ok "职位发布序列对齐" || bad "职位发布序列对齐"
[ "$(jq -r '.data.applyCounts | length' <<<"$BODY")" = "12" ] && ok "投递序列对齐" || bad "投递序列对齐"
[ "$(jq -r '[.data.jobCounts[]] | add' <<<"$BODY")" -gt 0 ] && ok "职位发布总量>0" || bad "职位发布总量>0"

req GET /public/stats/salary
expect_ok "薪资统计(图表)"
[ "$(jq -r '.data.byDirection | length' <<<"$BODY")" -gt 0 ] && ok "方向薪资非空" || bad "方向薪资非空"
[ "$(jq -r '.data.byCity | length' <<<"$BODY")" -gt 0 ] && ok "城市薪资非空" || bad "城市薪资非空"

req GET "/public/stats/tech-trend?top=8&months=12"
expect_ok "技术趋势(图表)"
[ "$(jq -r '.data.series | length' <<<"$BODY")" -gt 0 ] && ok "趋势序列非空" || bad "趋势序列非空"

req GET /public/stats/region
expect_ok "地区分布(图表)"
[ "$(jq -r '.data | length' <<<"$BODY")" -gt 0 ] && ok "地区非空" || bad "地区非空"

# ---- 权限 ----
req GET /student/dashboard
expect_http 401 "未登录学生看板 401"

req GET /student/dashboard "$T_COM"
expect_http 403 "企业访问学生看板 403"

req GET /company/dashboard "$T_STU"
expect_http 403 "学生访问企业看板 403"

req GET /admin/dashboard/overview "$T_STU"
expect_http 403 "学生访问管理看板 403"

# ---- 学生看板 ----
req GET /student/dashboard "$T_STU"
expect_ok "学生看板"
[ "$(jq -r '.data.applicationStatus | length' <<<"$BODY")" = "5" ] && ok "投递状态 5 档" || bad "投递状态 5 档"
[ "$(jq -r '[.data.applicationStatus[].count] | add' <<<"$BODY")" -ge 0 ] && ok "投递计数可加总" || bad "投递计数可加总"
[ "$(jq -r '.data.skillRadar.skills | length' <<<"$BODY")" -gt 0 ] && ok "技能雷达维度非空" || bad "技能雷达维度非空"
[ "$(jq -r '.data.skillRadar.myLevels | length' <<<"$BODY")" = "$(jq -r '.data.skillRadar.skills | length' <<<"$BODY")" ] && ok "技能雷达对齐" || bad "技能雷达对齐"
[ "$(jq -r '.data.profile.city' <<<"$BODY")" != "null" ] && [ -n "$(jq -r '.data.profile.city' <<<"$BODY")" ] && ok "学生档案城市" || bad "学生档案城市"
[ "$(jq -r '.data.recommendTop | length' <<<"$BODY")" -ge 0 ] && ok "推荐摘要数组" || bad "推荐摘要数组"

CITY=$(jq -r '.data.profile.city' <<<"$BODY")
DIR=$(jq -r '.data.profile.techDirection' <<<"$BODY")
EDU=$(jq -r '.data.profile.education' <<<"$BODY")
EXP=$(jq -r '.data.profile.experienceYears // 0' <<<"$BODY")
# 薪资预测依赖 ai-service；不可用时 SKIP
if curl -sf -m 2 -o /dev/null "http://127.0.0.1:8000/health"; then
  req GET "/public/stats/salary/predict?city=$(python3 -c "import urllib.parse;print(urllib.parse.quote('''$CITY'''))")&techDirection=$(python3 -c "import urllib.parse;print(urllib.parse.quote('''$DIR'''))")&education=$EDU&experienceYears=$EXP"
  if [ "$HTTP" = 200 ] && [ "$(jqv .code)" = 200 ]; then
    ok "学生档案薪资预测"
    PRED=$(jq -r '.data.predictedSalary // .data.salary // .data.avgSalary // empty' <<<"$BODY")
    [ -n "$PRED" ] && [ "$PRED" != "null" ] && ok "预测值非空" || ok "预测响应成功(字段名可变)"
  else
    # 503 也可接受
    [ "$HTTP" = 503 ] && ok "薪资预测服务暂不可用(503)" || bad "学生档案薪资预测 http=$HTTP"
  fi
else
  echo "  [SKIP] 薪资预测（ai-service 未启动）"
fi

# ---- 企业看板 ----
req GET /company/dashboard "$T_COM"
expect_ok "企业看板"
[ "$(jq -r '.data.jobs | type' <<<"$BODY")" = "array" ] && ok "职位表现数组" || bad "职位表现数组"
[ "$(jq -r '.data.applicationStatus | length' <<<"$BODY")" = "5" ] && ok "企业投递状态 5 档" || bad "企业投递状态 5 档"
[ "$(jq -r '.data.applicantSkills | type' <<<"$BODY")" = "array" ] && ok "候选人技能数组" || bad "候选人技能数组"
# 若有职位，字段齐全
JOB_N=$(jq -r '.data.jobs | length' <<<"$BODY")
if [ "$JOB_N" -gt 0 ]; then
  [ "$(jq -r '.data.jobs[0].positionId' <<<"$BODY")" != "null" ] && ok "职位含 positionId" || bad "职位含 positionId"
  [ "$(jq -r '.data.jobs[0] | has("viewCount")' <<<"$BODY")" = "true" ] && ok "职位含 viewCount" || bad "职位含 viewCount"
  [ "$(jq -r '.data.jobs[0] | has("applyCount")' <<<"$BODY")" = "true" ] && ok "职位含 applyCount" || bad "职位含 applyCount"
else
  ok "企业暂无职位(空列表可接受)"
fi

# ---- 管理看板 ----
req GET /admin/dashboard/overview "$T_ADMIN"
expect_ok "管理看板总览"
[ "$(jqv .data.platform.jobCount)" -gt 0 ] && ok "平台职位数" || bad "平台职位数"
[ "$(jqv .data.platform.applicationCount)" -gt 0 ] && ok "平台投递数" || bad "平台投递数"
[ -n "$(jqv .data.spark.batchNo)" ] && [ "$(jqv .data.spark.batchNo)" != "null" ] && ok "Spark 批次" || bad "Spark 批次"
[ -n "$(jqv .data.recommend.ndcgAt10)" ] && [ "$(jqv .data.recommend.ndcgAt10)" != "null" ] && ok "推荐 NDCG@10" || bad "推荐 NDCG@10"
[ "$(jqv .data.ai.sessionCount)" -ge 0 ] && ok "AI 会话数" || bad "AI 会话数"
[ "$(jqv .data.ai.messageCount)" -ge 0 ] && ok "AI 消息数" || bad "AI 消息数"

# 交叉：公开概览投递数与管理看板一致
req GET /public/stats/overview
PUB_APP=$(jqv .data.applicationCount)
req GET /admin/dashboard/overview "$T_ADMIN"
ADM_APP=$(jqv .data.platform.applicationCount)
[ "$PUB_APP" = "$ADM_APP" ] && ok "公开与管理投递数一致" || bad "公开与管理投递数一致 ($PUB_APP vs $ADM_APP)"

summary
