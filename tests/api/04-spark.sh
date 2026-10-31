#!/usr/bin/env bash
# Spark 离线分析结果与公开图表接口。
# 公开统计只读数据库中 is_latest=1 的 spark_* 表，不依赖 ai-service。
# 触发分析和实时预测依赖 8000 上的 FastAPI；服务未启动时这些断言记为 SKIP。
cd "$(dirname "$0")"; source ./lib.sh
echo "### 04 Spark 分析与公开统计"

login admin admin123; T_ADMIN=$TOKEN; expect_ok "管理员登录"
login student student123; T_STU=$TOKEN; expect_ok "学生登录"

skip() { echo "  [SKIP] $1"; }
ai_up() { curl -sf -m 2 -o /dev/null "http://127.0.0.1:8000/health"; }

req GET /public/stats/overview
expect_ok "公开概览"
[ "$(jqv .data.jobCount)" -gt 0 ] && ok "职位总数非空" || bad "职位总数非空"
[ "$(jqv .data.companyCount)" -gt 0 ] && ok "企业数非空" || bad "企业数非空"
[ "$(jqv .data.studentCount)" -gt 0 ] && ok "学生数非空" || bad "学生数非空"
[ "$(jqv .data.cityCount)" -gt 0 ] && ok "城市数非空" || bad "城市数非空"
[ -n "$(jqv .data.avgSalary)" ] && [ "$(jqv .data.avgSalary)" != "null" ] && ok "平均月薪非空" || bad "平均月薪非空"
[ -n "$(jqv .data.lastBatchNo)" ] && [ "$(jqv .data.lastBatchNo)" != "null" ] && ok "最近分析批次非空" || bad "最近分析批次非空"
BATCH=$(jqv .data.lastBatchNo)

req GET /public/stats/salary
expect_ok "薪资统计"
[ "$(jq -r '.data.records | length' <<<"$BODY")" -gt 0 ] && ok "薪资明细非空" || bad "薪资明细非空"
[ "$(jq -r '.data.byDirection | length' <<<"$BODY")" -gt 0 ] && ok "按方向汇总非空" || bad "按方向汇总非空"
[ "$(jq -r '.data.byCity | length' <<<"$BODY")" -gt 0 ] && ok "按城市汇总非空" || bad "按城市汇总非空"
[ "$(jq -r '.data.records[0].techDirection' <<<"$BODY")" != "null" ] && ok "薪资明细含技术方向" || bad "薪资明细含技术方向"
[ "$(jq -r '.data.records[0].p25Salary' <<<"$BODY")" != "null" ] && ok "薪资明细含分位数" || bad "薪资明细含分位数"

req GET "/public/stats/salary?city=%E5%8C%97%E4%BA%AC"
expect_ok "按城市过滤薪资"
[ "$(jq -r '.data.records | length' <<<"$BODY")" -gt 0 ] && ok "北京薪资非空" || bad "北京薪资非空"
[ "$(jq -r '[.data.records[].city] | map(select(. != "北京")) | length' <<<"$BODY")" = "0" ] && ok "过滤后只有北京" || bad "过滤后只有北京"

req GET "/public/stats/salary?tech_direction=%E5%90%8E%E7%AB%AF%E5%BC%80%E5%8F%91"
expect_ok "按方向过滤薪资"
[ "$(jq -r '[.data.records[].techDirection] | map(select(. != "后端开发")) | length' <<<"$BODY")" = "0" ] && ok "过滤后只有后端开发" || bad "过滤后只有后端开发"

req GET "/public/stats/salary?city=%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%9F%8E%E5%B8%82"
expect_ok "未知城市返回空列表"
expect_jq '.data.records | length' 0 "未知城市明细为空"
expect_jq '.data.byCity | length' 0 "未知城市汇总为空"

req GET "/public/stats/tech-trend?top=5&months=6"
expect_ok "技术趋势"
[ "$(jq -r '.data.months | length' <<<"$BODY")" -gt 0 ] && ok "趋势月份非空" || bad "趋势月份非空"
[ "$(jq -r '.data.series | length' <<<"$BODY")" -gt 0 ] && ok "趋势序列非空" || bad "趋势序列非空"
[ "$(jq -r '.data.series | length' <<<"$BODY")" -le 5 ] && ok "趋势序列不超过 top" || bad "趋势序列不超过 top"
[ "$(jq -r '.data.ranking | length' <<<"$BODY")" -gt 0 ] && ok "技能排行非空" || bad "技能排行非空"
[ "$(jq -r '.data.series[0].data | length' <<<"$BODY")" = "$(jq -r '.data.months | length' <<<"$BODY")" ] && ok "序列与月份对齐" || bad "序列与月份对齐"

req GET /public/stats/region
expect_ok "地区分布"
[ "$(jq -r '.data | length' <<<"$BODY")" -gt 0 ] && ok "地区数据非空" || bad "地区数据非空"
[ "$(jq -r '.data[0].adcode | length' <<<"$BODY")" = "6" ] && ok "行政区划代码为 6 位" || bad "行政区划代码为 6 位"
[ -n "$(jqv '.data[0].name')" ] && [ "$(jqv '.data[0].name')" != "null" ] && ok "省份名称非空" || bad "省份名称非空"
[ "$(jqv '.data[0].value')" -gt 0 ] && ok "省份职位数非空" || bad "省份职位数非空"

req GET "/public/stats/salary/predict?education=9&experienceYears=0&city=%E5%8C%97%E4%BA%AC&techDirection=%E5%90%8E%E7%AB%AF%E5%BC%80%E5%8F%91"
expect_http 400 "学历越界返回 400"
req GET "/public/stats/salary/predict?education=2&experienceYears=-1&city=%E5%8C%97%E4%BA%AC&techDirection=%E5%90%8E%E7%AB%AF%E5%BC%80%E5%8F%91"
expect_http 400 "工作年限越界返回 400"
req GET "/public/stats/salary/predict?education=2&experienceYears=0&techDirection=%E5%90%8E%E7%AB%AF%E5%BC%80%E5%8F%91"
expect_http 400 "缺少城市返回 400"

req GET "/admin/spark/tasks?current=1&size=5" "$T_ADMIN"
expect_ok "管理员任务分页"
[ "$(jqv .data.total)" -ge 1 ] && ok "任务日志非空" || bad "任务日志非空"
[ "$(jq -r '.data.records | length' <<<"$BODY")" -ge 1 ] && ok "任务当前页非空" || bad "任务当前页非空"
[ "$(jq -r '.data.records | length' <<<"$BODY")" -le 5 ] && ok "任务页大小生效" || bad "任务页大小生效"

req GET "/admin/spark/tasks?status=1&current=1&size=20" "$T_ADMIN"
expect_ok "按状态过滤任务"
[ "$(jq -r '[.data.records[].status] | map(select(. != 1)) | length' <<<"$BODY")" = "0" ] && ok "过滤后状态均为成功" || bad "过滤后状态均为成功"

req GET "/admin/spark/tasks?batchNo=${BATCH}&current=1&size=20" "$T_ADMIN"
expect_ok "按批次过滤任务"
[ "$(jqv .data.total)" -ge 1 ] && ok "批次任务非空" || bad "批次任务非空"
[ "$(jq -r --arg b "$BATCH" '[.data.records[].batchNo] | map(select(. != $b)) | length' <<<"$BODY")" = "0" ] && ok "过滤后批次一致" || bad "过滤后批次一致"

req GET /admin/spark/tasks
expect_http 401 "未登录查看任务 401"
req POST /admin/spark/run "$T_STU" '{}'
expect_http 403 "学生触发分析 403"
req GET /admin/spark/tasks "$T_STU"
expect_http 403 "学生查看任务 403"

if ai_up; then
  req GET "/public/stats/salary/predict?city=%E5%8C%97%E4%BA%AC&techDirection=%E5%90%8E%E7%AB%AF%E5%BC%80%E5%8F%91&education=2&experienceYears=0"
  expect_ok "实时薪资预测"
  [ "$(jqv .data.predictedSalary)" != "null" ] && ok "预测月薪非空" || bad "预测月薪非空"
  [ -n "$(jqv .data.modelVersion)" ] && [ "$(jqv .data.modelVersion)" != "null" ] && ok "模型版本非空" || bad "模型版本非空"
  req POST /admin/spark/run "$T_ADMIN" '{"tasks":["clean"]}'
  if [ "$(jqv .code)" = "409" ]; then
    ok "重复触发返回任务运行中"
  else
    expect_ok "触发 Spark 分析"
    [ -n "$(jqv .data.batchNo)" ] && [ "$(jqv .data.batchNo)" != "null" ] && ok "返回批次号" || bad "返回批次号"
  fi
  AI_CODE=$(curl -s -m 5 "http://127.0.0.1:8000/spark/tasks?current=1&size=2" | jq -r .code)
  [ "$AI_CODE" = "200" ] && ok "FastAPI 任务列表" || bad "FastAPI 任务列表"
else
  skip "ai-service 未运行，跳过分析触发、实时预测和 FastAPI 任务列表"
fi

summary
