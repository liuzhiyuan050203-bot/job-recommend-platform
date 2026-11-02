#!/usr/bin/env bash
# P1-2：职位详情不显示爬虫 JSON / 抓取元数据；给出数据来源与估算薪资说明
source "$(dirname "$0")/lib.sh"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TS=${TS:-$(date +%s)}
echo "== 13 职位详情正文整理 =="

if (cd "$ROOT/backend" && mvn -q test -Dtest=JobTextCleanerTest -Dsurefire.failIfNoSpecifiedTests=false >/tmp/job-text-cleaner-test.log 2>&1); then
  ok "JUnit JobTextCleanerTest 通过"
else
  bad "JUnit JobTextCleanerTest" "$(grep -E 'Tests run|FAIL|expected' /tmp/job-text-cleaner-test.log | head -5)"
fi

# ---- 真实职位（校招官网同步） ----
REAL=$(db_sql "SELECT p.id FROM job_position p JOIN ent_company c ON c.id=p.company_id JOIN sys_user u ON u.id=c.user_id
  WHERE p.deleted=0 AND p.shelf_status=1 AND p.audit_status=1 AND u.username LIKE 'real\\_%' AND p.requirement LIKE '{\"provenance\"%' ORDER BY p.id LIMIT 1")
if [ -z "$REAL" ]; then
  skip "库里没有真实职位，跳过"
else
  req GET "/public/jobs/$REAL"; expect_ok "真实职位详情"
  RAW=$(jq -r '[.data.description, .data.requirement, .data.welfare, (.data.descriptionItems // [] | join("\n")), (.data.requirementItems // [] | join("\n"))] | join("\n")' <<<"$BODY")
  grep -qE '\{"|"provenance"|\["|【来源】|【抓取时间】|post_id|岗位名称：|本条记录由' <<<"$RAW" \
    && bad "详情正文不含 JSON 与抓取元数据" "$(head -c 300 <<<"$RAW")" || ok "详情正文不含 JSON 与抓取元数据"
  [ "$(jqv .data.dataSource.type)" = CRAWLER ] && ok "数据来源标为校招官网同步" || bad "数据来源标为校招官网同步" "$(jq -c .data.dataSource <<<"$BODY")"
  jqv .data.dataSource.label | grep -q "校招官网" && ok "来源徽标文字：$(jqv .data.dataSource.label)" || bad "来源徽标文字" "$(jqv .data.dataSource.label)"
  jqv .data.dataSource.applyUrl | grep -qE '^https?://' && ok "给出官网投递链接" || bad "给出官网投递链接"
  [ "$(jqv .data.dataSource.site)" != null ] && [ "$(jqv .data.dataSource.crawledAt)" != null ] && ok "来源含站点与抓取时间" || bad "来源含站点与抓取时间"
  [ "$(jqv .data.salaryEstimated)" = true ] && ok "真实职位标为估算薪资" || bad "真实职位标为估算薪资"
  jqv .data.salaryNote | grep -q "估算" && ok "估算薪资有说明文字" || bad "估算薪资有说明文字"
  [ "$(jq '.data.requirementItems | type' <<<"$BODY")" = '"array"' ] && ok "requirementItems 为数组" || bad "requirementItems 为数组"
  # 库里原文保留，供溯源
  db_sql "SELECT requirement FROM job_position WHERE id=$REAL" | grep -q '"provenance"' && ok "库内 provenance 原文未改动" || bad "库内 provenance 原文未改动"
fi

# ---- 企业发布的职位：带序号正文拆成条目，不标估算 ----
login company company123; T_CO=$TOKEN; expect_ok "企业登录"
JOB_JSON=$(jq -n --arg title "详情整理测试岗$TS" '{title:$title, techDirection:"后端开发", province:"北京", city:"北京", district:"海淀", address:"测试地址",
  salaryMin:10000, salaryMax:20000, salaryMonths:13, education:2, experienceReq:0, jobType:1, headcount:1, categoryId:1, tagIds:[1,2],
  description:"1. 负责接口开发；\n2. 参与代码评审", requirement:"[\"1、熟悉 Java\", \"2、了解 MySQL\"]", welfare:"五险一金"}')
req POST /company/jobs "$T_CO" "$JOB_JSON"; expect_ok "企业发布测试职位"
JOB=$(jqv .data.id)
fixture_job "$JOB"
login admin admin123; T_ADMIN=$TOKEN
req PUT "/admin/jobs/$JOB/audit" "$T_ADMIN" '{"auditStatus":1,"auditRemark":"通过"}'; expect_ok "审核职位"
req PUT "/company/jobs/$JOB/shelf" "$T_CO" '{"shelfStatus":1}'; expect_ok "上架职位"
req GET "/public/jobs/$JOB"; expect_ok "企业职位详情"
[ "$(jq -c .data.descriptionItems <<<"$BODY")" = '["负责接口开发","参与代码评审"]' ] && ok "职责按序号拆成条目" || bad "职责按序号拆成条目" "$(jq -c .data.descriptionItems <<<"$BODY")"
[ "$(jq -c .data.requirementItems <<<"$BODY")" = '["熟悉 Java","了解 MySQL"]' ] && ok "JSON 数组形式的要求被解析为条目" || bad "JSON 数组形式的要求被解析为条目" "$(jq -c .data.requirementItems <<<"$BODY")"
[ "$(jqv .data.dataSource.type)" = PLATFORM ] && [ "$(jqv .data.dataSource.label)" = "企业发布" ] && ok "数据来源：企业发布" || bad "数据来源：企业发布"
[ "$(jqv .data.salaryEstimated)" = false ] && ok "企业填写的薪资不标估算" || bad "企业填写的薪资不标估算"
[ "$(jqv .data.welfare)" = "五险一金" ] && ok "福利原样保留" || bad "福利原样保留"

summary
