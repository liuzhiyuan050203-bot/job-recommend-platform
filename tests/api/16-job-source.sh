#!/usr/bin/env bash
# UX 整改：职位来源标注（platform / self_crawl / ext_ats）、来源筛选、外部来源职位不可站内投递
source "$(dirname "$0")/lib.sh"
echo "== 16 职位来源标注与筛选 =="

req GET "/public/jobs?current=1&size=20"; expect_ok "职位列表"
[ "$(jq '[.data.records[] | has("sourceCode")] | all' <<<"$BODY")" = true ] && ok "列表卡片带 sourceCode" || bad "列表卡片带 sourceCode"

for src in platform self_crawl ext_ats; do
  req GET "/public/jobs?current=1&size=20&source=$src"; expect_ok "来源筛选 $src"
  total=$(jqv .data.total)
  if [ "${total:-0}" -gt 0 ]; then
    [ "$(jq --arg s "$src" '[.data.records[].sourceCode == $s] | all' <<<"$BODY")" = true ] && ok "$src 筛选结果来源一致（$total 条）" || bad "$src 筛选结果来源一致"
    if [ "$src" = platform ]; then
      [ "$(jq '[.data.records[].salaryEstimated == false] | all' <<<"$BODY")" = true ] && ok "平台发布职位不标估算薪资" || bad "平台发布职位不标估算薪资"
    else
      [ "$(jq '[.data.records[].salaryEstimated == true] | all' <<<"$BODY")" = true ] && ok "$src 列表标为估算薪资" || bad "$src 列表标为估算薪资"
    fi
  else
    ok "$src 暂无职位（跳过一致性检查）"
  fi
done

req GET "/public/jobs?current=1&size=50&source=internal"; expect_ok "来源筛选 internal"
[ "$(jq '[.data.records[].sourceCode != "ext_ats"] | all' <<<"$BODY")" = true ] && ok "internal 排除外部扩充库" || bad "internal 排除外部扩充库"
req GET "/public/jobs?current=1&size=5&source=bogus"; expect_ok "非法来源取值按全部处理"

EXT=$(db_sql "SELECT p.id FROM job_position p JOIN ent_company c ON c.id=p.company_id WHERE p.deleted=0 AND p.shelf_status=1 AND p.audit_status=1 AND c.audit_status=1 AND c.deleted=0 AND p.data_source='ext_ats' ORDER BY p.id LIMIT 1")
if [ -z "$EXT" ]; then
  ok "库里没有外部来源职位，跳过详情与投递检查"
else
  req GET "/public/jobs/$EXT"; expect_ok "外部来源职位详情"
  expect_jq .data.sourceCode ext_ats "详情 sourceCode=ext_ats"
  jqv .data.dataSource.label | grep -q "^外部来源" && ok "来源徽标标明外部来源：$(jqv .data.dataSource.label)" || bad "来源徽标标明外部来源" "$(jqv .data.dataSource.label)"
  expect_jq .data.salaryEstimated true "外部来源职位标为估算薪资"
  login student student123; T_STU=$TOKEN
  RID=$(db_sql "SELECT r.id FROM stu_resume r JOIN sys_user u ON u.id=r.user_id WHERE u.username='student' AND r.deleted=0 ORDER BY r.is_default DESC, r.id LIMIT 1")
  req POST /student/applications "$T_STU" "{\"jobId\":$EXT,\"resumeId\":${RID:-0}}"
  expect_fail "外部来源职位不能站内投递"
  jqv .msg | grep -q "官网" && ok "提示前往官网投递" || bad "提示前往官网投递"
  N=$(db_sql "SELECT COUNT(*) FROM job_application a JOIN sys_user u ON u.id=a.user_id WHERE u.username='student' AND a.position_id=$EXT AND a.deleted=0")
  [ "$N" = 0 ] && ok "未产生投递记录" || bad "未产生投递记录" "$N"
fi

login student student123; T_STU=$TOKEN
req GET "/student/recommend?current=1&size=5" "$T_STU"; expect_ok "推荐列表"
CNT=$(jq '.data.records | length' <<<"$BODY")
if [ "${CNT:-0}" -gt 0 ]; then
  [ "$(jq '[.data.records[] | (.sourceCode // "") != ""] | all' <<<"$BODY")" = true ] && ok "推荐卡片带 sourceCode" || bad "推荐卡片带 sourceCode"
else
  ok "推荐为空（跳过）"
fi
ANY=$(db_sql "SELECT p.id FROM job_position p WHERE p.deleted=0 AND p.shelf_status=1 AND p.audit_status=1 ORDER BY p.id LIMIT 1")
req GET "/public/jobs/$ANY/similar?size=3"; expect_ok "相似职位"
[ "$(jq '[.data[] | (.sourceCode // "") != ""] | all' <<<"$BODY")" = true ] && ok "相似职位带 sourceCode" || bad "相似职位带 sourceCode"
req GET "/student/favorites?current=1&size=5" "$T_STU"; expect_ok "收藏列表"
[ "$(jq '[.data.records[] | select(.title != "职位已删除") | (.sourceCode // "") != ""] | all' <<<"$BODY")" = true ] && ok "收藏卡片带 sourceCode" || bad "收藏卡片带 sourceCode"

summary
