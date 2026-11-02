#!/usr/bin/env bash
# UX 审计 P1：演示数据卫生。放在最后执行，检查前面各脚本退出时已收掉自己的夹具，
# 演示账号看到的首页、投递、看板不再被测试职位 / 测试简历 / 「已录用」测试投递淹没。
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source ./lib.sh
echo "### 11 演示数据卫生"

if ! db_ping; then
  echo "  [SKIP] 数据库不可用"
  echo "$(basename "$0") 0 0" >> /tmp/job-api-test-summary.txt
  exit 0
fi

PATTERNS="title LIKE '招聘流程测试%' OR title LIKE '越权隔离职位%' OR title LIKE 'UX-IDOR%' OR title LIKE '用户体验审计岗位%'"
N=$(db_sql "SELECT COUNT(*) FROM job_position WHERE deleted = 0 AND ($PATTERNS)")
[ "$N" = 0 ] && ok "库中没有残留的测试职位" || { HTTP=-; BODY="残留 $N 条"; bad "库中没有残留的测试职位"; }

N=$(db_sql "SELECT COUNT(*) FROM sys_user WHERE deleted = 0 AND role IN (1,2) AND NOT (username IN ('student','company') OR username LIKE 'demo\\_%' OR username LIKE 'real\\_%')")
[ "$N" = 0 ] && ok "测试注册的临时账号已收尾" || { HTTP=-; BODY="残留 $N 个"; bad "测试注册的临时账号已收尾"; }

for kw in 越权隔离职位 招聘流程测试 UX-IDOR; do
  req GET "/public/jobs?keyword=$(jq -rn --arg v "$kw" '$v|@uri')"
  expect_jq .data.total 0 "公开检索「$kw」无结果"
done
req GET "/public/jobs?sort=newest&size=20"; expect_ok "最新职位"
echo "$BODY" | jq -e '[.data.records[].title | select(test("测试|越权|IDOR"))] | length == 0' >/dev/null \
  && ok "最新职位不含测试标题" || bad "最新职位不含测试标题"
req GET /public/skill-tags
echo "$BODY" | jq -e '[.data[].name | select(. == "Rust测试")] | length == 0' >/dev/null \
  && ok "技能词表不含「Rust测试」" || bad "技能词表不含「Rust测试」"

login student student123; T_STU=$TOKEN; expect_ok "演示学生登录"
req GET /student/resumes "$T_STU"; expect_ok "演示学生简历"
expect_jq '[.data[] | select(.isDefault == 1) | .title] | join(",")' "陈晓-校招简历" "默认简历是正式简历"
echo "$BODY" | jq -e '[.data[].title | select(test("测试|E2E"))] | length == 0' >/dev/null \
  && ok "简历列表没有测试简历" || bad "简历列表没有测试简历"
req GET "/student/applications?size=100" "$T_STU"; expect_ok "演示学生投递"
TOTAL=$(jqv .data.total); OFFER=$(jq '[.data.records[] | select(.status == 3)] | length' <<<"$BODY")
[ "$TOTAL" -ge 3 ] && [ $((OFFER * 2)) -le "$TOTAL" ] && ok "投递以进行中为主（共 $TOTAL，已录用 $OFFER）" || bad "投递以进行中为主（共 $TOTAL，已录用 $OFFER）"
echo "$BODY" | jq -e '[.data.records[].jobTitle | select(test("测试|越权|IDOR"))] | length == 0' >/dev/null \
  && ok "投递列表不含测试职位" || bad "投递列表不含测试职位"
req GET /student/interviews/upcoming "$T_STU"; expect_ok "即将到来的安排"
echo "$BODY" | jq -e '[(.data // [])[].jobTitle | select(test("测试|越权|IDOR"))] | length == 0' >/dev/null \
  && ok "面试提醒不含测试职位" || bad "面试提醒不含测试职位"

# 演示企业漏斗：待初筛不少于已录用，且各阶段都有投递日志
CID=$(db_sql "SELECT c.id FROM ent_company c JOIN sys_user u ON u.id = c.user_id WHERE u.username = 'company' AND c.deleted = 0")
P0=$(db_sql "SELECT COUNT(*) FROM job_application WHERE company_id = $CID AND deleted = 0 AND status = 0")
P3=$(db_sql "SELECT COUNT(*) FROM job_application WHERE company_id = $CID AND deleted = 0 AND status = 3")
[ "$P0" -ge "$P3" ] && [ "$P0" -ge 1 ] && ok "演示企业漏斗正常（待初筛 $P0 ≥ 已录用 $P3）" || bad "演示企业漏斗正常（待初筛 $P0，已录用 $P3）"
N=$(db_sql "SELECT COUNT(*) FROM job_application a WHERE a.deleted = 0 AND a.status <> 0 AND NOT EXISTS (
  SELECT 1 FROM job_application_log l WHERE l.application_id = a.id AND l.deleted = 0 AND l.to_status = a.status)")
[ "$N" = 0 ] && ok "非待初筛投递都有对应状态日志" || { HTTP=-; BODY="缺日志 $N 条"; bad "非待初筛投递都有对应状态日志"; }
N=$(db_sql "SELECT COUNT(*) FROM job_application a JOIN job_position p ON p.id = a.position_id WHERE a.deleted = 0 AND p.deleted = 1")
[ "$N" = 0 ] && ok "没有挂在已删职位上的投递" || { HTTP=-; BODY="$N 条"; bad "没有挂在已删职位上的投递"; }
ALL0=$(db_sql "SELECT COUNT(*) FROM job_application WHERE deleted = 0 AND status = 0")
ALL3=$(db_sql "SELECT COUNT(*) FROM job_application WHERE deleted = 0 AND status = 3")
[ "$ALL0" -gt "$ALL3" ] && ok "全平台漏斗不倒挂（待初筛 $ALL0 > 已录用 $ALL3）" || bad "全平台漏斗不倒挂（待初筛 $ALL0，已录用 $ALL3）"

summary
