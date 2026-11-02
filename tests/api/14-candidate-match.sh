#!/usr/bin/env bash
# P1-4：职位至少 1 个技能标签；企业候选人列表显示技能熟练度、命中高亮与可排序的匹配分
source "$(dirname "$0")/lib.sh"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TS=${TS:-$(date +%s)}
echo "== 14 职位技能标签与候选人匹配 =="

if (cd "$ROOT/backend" && mvn -q test -Dtest=SkillMatchTest -Dsurefire.failIfNoSpecifiedTests=false >/tmp/skill-match-test.log 2>&1); then
  ok "JUnit SkillMatchTest 通过"
else
  bad "JUnit SkillMatchTest" "$(grep -E 'Tests run|FAIL|expected' /tmp/skill-match-test.log | head -5)"
fi

tag_id() { db_sql "SELECT id FROM skill_tag WHERE name='$1' AND deleted=0 LIMIT 1"; }
JAVA=$(tag_id Java); MYSQL=$(tag_id MySQL); REDIS=$(tag_id Redis); PY=$(tag_id Python)

login admin admin123; T_ADMIN=$TOKEN
login company company123; T_CO=$TOKEN; expect_ok "企业登录"

# ---- 发布职位必须带技能标签 ----
BASE_JSON=$(jq -n --arg title "匹配分测试岗$TS" '{title:$title, categoryId:2, province:"浙江", city:"杭州", district:"西湖区", address:"测试路1号",
  salaryMin:12000, salaryMax:20000, salaryMonths:13, education:2, experienceReq:0, jobType:3, headcount:2,
  description:"负责后端接口开发", requirement:"熟悉 Java、MySQL、Redis", welfare:"五险一金"}')
req POST /company/jobs "$T_CO" "$(jq 'del(.tagIds)' <<<"$BASE_JSON")"; expect_http 400 "不带技能标签发布被拒（400）"
jqv .msg | grep -q "至少选择 1 个技能标签" && ok "提示：$(jqv .msg)" || bad "缺技能标签的提示文字" "$(jqv .msg)"
req POST /company/jobs "$T_CO" "$(jq '.tagIds=[]' <<<"$BASE_JSON")"; expect_http 400 "空技能标签数组被拒"
req POST /company/jobs "$T_CO" "$(jq '.tagIds=[null]' <<<"$BASE_JSON")"; expect_fail "只含 null 的技能标签被拒"
req POST /company/jobs "$T_CO" "$(jq --argjson a "$JAVA" --argjson b "$MYSQL" --argjson c "$REDIS" '.tagIds=[$a,$b,$c]' <<<"$BASE_JSON")"
expect_ok "带 3 个技能标签发布职位"
JOB=$(jqv .data.id); fixture_job "$JOB"
req PUT "/company/jobs/$JOB" "$T_CO" "$(jq '.tagIds=[]' <<<"$BASE_JSON")"; expect_http 400 "编辑时清空技能标签被拒"
req PUT "/admin/jobs/$JOB/audit" "$T_ADMIN" '{"auditStatus":1,"auditRemark":"通过"}'; expect_ok "审核职位"
req PUT "/company/jobs/$JOB/shelf" "$T_CO" '{"shelfStatus":1}'; expect_ok "上架职位"

# ---- 两个候选人：一个技能对口，一个没有技能 ----
new_student() { # new_student USERNAME -> T_NEW, APP_NEW
  fixture_user "$1"
  req POST /public/auth/register/student "" "{\"username\":\"$1\",\"password\":\"pass123\",\"nickname\":\"匹配$1\",\"realName\":\"匹配同学$2\",\"gender\":1,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"软件工程\"}"
  login "$1" pass123; T_NEW=$TOKEN
}
apply_with_resume() {
  req POST /student/resumes "$T_NEW" "$(jq -n --arg t "匹配测试简历$TS" '{title:$t,isDefault:1,educationExp:"本科",projectExp:"无",internshipExp:"无",skillDesc:"",selfEvaluation:"",attachmentUrl:""}')"
  local rid; rid=$(jqv .data.id); fixture_resume "$rid"
  req POST /student/applications "$T_NEW" "{\"jobId\":$JOB,\"resumeId\":$rid}"; APP_NEW=$(jqv .data)
}
new_student "match1$TS" 甲; T_S1=$T_NEW
req POST /student/skills "$T_S1" "{\"skillTagId\":$JAVA,\"proficiency\":5}"; expect_ok "候选人甲：Java 精通"
req POST /student/skills "$T_S1" "{\"skillTagId\":$MYSQL,\"proficiency\":1}"; expect_ok "候选人甲：MySQL 入门"
req POST /student/skills "$T_S1" "{\"skillTagId\":$PY,\"proficiency\":4}"; expect_ok "候选人甲：Python 熟练"
apply_with_resume; APP1=$APP_NEW; expect_ok "候选人甲投递"
new_student "match2$TS" 乙
apply_with_resume; APP2=$APP_NEW; expect_ok "候选人乙（无技能）投递"

# ---- 列表：技能熟练度、命中、匹配分 ----
req GET "/company/applications?jobId=$JOB&size=20" "$T_CO"; expect_ok "企业候选人列表"
R1=$(jq -c ".data.records[] | select(.id==$APP1)" <<<"$BODY"); R2=$(jq -c ".data.records[] | select(.id==$APP2)" <<<"$BODY")
[ "$(jq .matchScore <<<"$R1")" = 53 ] && ok "甲匹配分 53 =(1.0+0.6+0)/3" || bad "甲匹配分" "$(jq -c '{matchScore,matchedSkillCount,jobSkillCount}' <<<"$R1")"
[ "$(jq -c '[.matchedSkillCount,.jobSkillCount]' <<<"$R1")" = '[2,3]' ] && ok "甲命中 2/3" || bad "甲命中 2/3" "$(jq -c '[.matchedSkillCount,.jobSkillCount]' <<<"$R1")"
[ "$(jq -c '[.candidateSkills[] | [.tagName,.proficiencyName,.matched]]' <<<"$R1")" = '[["Java","精通",true],["MySQL","入门",true],["Python","熟练",false]]' ] \
  && ok "技能带熟练度文字，命中的排前并标记" || bad "技能熟练度与命中" "$(jq -c .candidateSkills <<<"$R1")"
[ "$(jq -c .missingSkills <<<"$R1")" = '["Redis"]' ] && ok "列出职位要求但未掌握的 Redis" || bad "缺失技能" "$(jq -c .missingSkills <<<"$R1")"
[ "$(jq -c '[.matchScore,(.candidateSkills|length)]' <<<"$R2")" = '[0,0]' ] && ok "乙无技能：匹配分 0" || bad "乙匹配分" "$R2"

# ---- 按匹配分排序（服务端） ----
req GET "/company/applications?jobId=$JOB&sort=matchDesc&size=20" "$T_CO"; expect_ok "按匹配分降序"
[ "$(jq '.data.records[0].id' <<<"$BODY")" = "$APP1" ] && ok "降序第一位是甲" || bad "降序第一位是甲" "$(jq -c '[.data.records[]|[.id,.matchScore]]' <<<"$BODY")"
[ "$(jqv .data.total)" = 2 ] && ok "排序后总数不变" || bad "排序后总数不变" "$(jqv .data.total)"
req GET "/company/applications?jobId=$JOB&sort=matchAsc&size=1&current=1" "$T_CO"
[ "$(jq '.data.records[0].id' <<<"$BODY")" = "$APP2" ] && [ "$(jqv '.data.records|length')" = 1 ] && ok "升序分页：第 1 页第一位是乙" || bad "升序分页" "$(jq -c .data <<<"$BODY" | head -c 300)"
req GET "/company/applications?jobId=$JOB&sort=matchAsc&size=1&current=2" "$T_CO"
[ "$(jq '.data.records[0].id' <<<"$BODY")" = "$APP1" ] && ok "升序分页：第 2 页是甲" || bad "升序第 2 页"
req GET "/company/applications?sort=matchDesc&size=50" "$T_CO"; expect_ok "全部职位按匹配分排序"
jq -e '[.data.records[].matchScore | select(. != null)] as $s | $s == ($s | sort | reverse)' <<<"$BODY" >/dev/null \
  && ok "全部候选人按匹配分降序（无标签职位排最后）" || bad "全部候选人降序" "$(jq -c '[.data.records[].matchScore]' <<<"$BODY")"
req GET "/company/applications?sort=bogus" "$T_CO"; expect_fail "未知排序方式被拒"

# ---- 详情：同样带匹配信息；改状态后详情即时反映 ----
req GET "/company/applications/$APP1" "$T_CO"; expect_ok "候选人详情"
[ "$(jqv .data.matchScore)" = 53 ] && [ "$(jq '.data.candidateSkills|length' <<<"$BODY")" = 3 ] && ok "详情含匹配分与技能" || bad "详情匹配信息"
NEXT=$(jqv '.data.nextStatuses[0].status')
req PUT "/company/applications/$APP1/status" "$T_CO" "{\"toStatus\":$NEXT,\"remark\":\"匹配测试\"}"; expect_ok "变更状态"
req GET "/company/applications/$APP1" "$T_CO"
[ "$(jqv .data.status)" = "$NEXT" ] && jq -e '.data.logs | any(.remark=="匹配测试")' <<<"$BODY" >/dev/null && ok "重新拉详情能看到新状态与日志" || bad "详情刷新"
req GET "/student/applications/$APP1" "$T_S1"; expect_ok "学生端详情仍可用"

# ---- 前端：表单规则与抽屉刷新 ----
grep -q "tagIds: \[{ type: 'array', required: true, min: 1" "$ROOT/frontend/src/views/company/JobManage.vue" && grep -q 'prop="tagIds"' "$ROOT/frontend/src/views/company/JobManage.vue" \
  && ok "前端职位表单：技能标签必填规则" || bad "前端职位表单技能标签规则"
grep -q "refreshAfterChange" "$ROOT/frontend/src/views/company/Candidates.vue" && grep -q 'sortable="custom"' "$ROOT/frontend/src/views/company/Candidates.vue" \
  && ok "前端候选人：可排序匹配分列、改状态后刷新抽屉" || bad "前端候选人页"
if command -v node >/dev/null; then
  OUT=$(cd "$ROOT/frontend" && node --input-type=module -e "
import { extractSkillIds } from './src/utils/jobText.js'
const tags=[{id:1,name:'Java'},{id:2,name:'Spring Boot'},{id:3,name:'Go'},{id:4,name:'C'},{id:5,name:'机器学习'},{id:6,name:'JavaScript'}]
console.log(JSON.stringify(extractSkillIds('熟悉 java、SpringBoot，了解 Google、CSS 与 C++，懂机器学习', tags)))" 2>&1)
  [ "$OUT" = '[1,2,5]' ] && ok "从描述提取技能：大小写/去空格命中，Go≠Google、C≠CSS/C++、Java≠JavaScript" || bad "从描述提取技能" "$OUT"
fi

summary
