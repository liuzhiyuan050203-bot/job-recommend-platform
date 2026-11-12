#!/usr/bin/env bash
# 可用性整改：未过审的企业 / 职位不能上架；学生删除投递所用简历后，投递详情仍可查看（标记「简历已删除」）
source "$(dirname "$0")/lib.sh"
TS=${TS:-$(date +%s)}
TAIL=${TS: -8}
echo "== 17 上架审核门槛与已删除简历的投递 =="

login admin admin123; T_ADMIN=$TOKEN
login company company123; T_CO=$TOKEN; expect_ok "已认证企业登录"

JOB_JSON=$(jq -n --arg title "上架门槛测试岗$TS" '{title:$title, categoryId:2, province:"浙江", city:"杭州", district:"西湖区", address:"测试路1号",
  salaryMin:12000, salaryMax:20000, salaryMonths:13, education:2, experienceReq:0, jobType:3, headcount:1,
  description:"负责后端接口开发", requirement:"熟悉 Java", welfare:"五险一金", tagIds:[1]}')

# ---- 1. 职位未过审不能上架；草稿（下架）可以保存 ----
req POST /company/jobs "$T_CO" "$JOB_JSON"; expect_ok "发布职位（待审核草稿）"
JOB=$(jqv .data.id); fixture_job "$JOB"
expect_jq .data.shelfStatus 0 "新职位默认未上架"
expect_jq .data.auditStatus 0 "新职位待审核"
req PUT "/company/jobs/$JOB/shelf" "$T_CO" '{"shelfStatus":1}'; expect_http 400 "待审核职位上架被拒（400）"
jqv .msg | grep -q "审核通过后才能上架" && ok "提示：$(jqv .msg)" || bad "待审核上架提示文字" "$(jqv .msg)"
[ "$(db_sql "SELECT shelf_status FROM job_position WHERE id=$JOB")" = 0 ] && ok "库中仍为未上架" || bad "库中仍为未上架"
req PUT "/company/jobs/$JOB/shelf" "$T_CO" '{"shelfStatus":0}'; expect_ok "待审核职位保持下架（草稿）可保存"

req PUT "/admin/jobs/$JOB/audit" "$T_ADMIN" '{"auditStatus":2,"auditRemark":"描述过于简单"}'; expect_ok "管理员驳回职位"
req PUT "/company/jobs/$JOB/shelf" "$T_CO" '{"shelfStatus":1}'; expect_http 400 "已驳回职位上架被拒"
jqv .msg | grep -q "审核未通过" && ok "提示：$(jqv .msg)" || bad "驳回上架提示文字" "$(jqv .msg)"

req PUT "/company/jobs/$JOB" "$T_CO" "$JOB_JSON"; expect_ok "按意见修改后重新提交"
req PUT "/admin/jobs/$JOB/audit" "$T_ADMIN" '{"auditStatus":1,"auditRemark":"通过"}'; expect_ok "管理员审核通过"
req PUT "/company/jobs/$JOB/shelf" "$T_CO" '{"shelfStatus":1}'; expect_ok "审核通过后上架成功"
req GET "/public/jobs/$JOB"; expect_ok "上架后学生可见"
expect_jq .data.applyInPlatform true "企业发布职位可站内投递"

# ---- 2. 企业资质未过审：所有职位接口被拦截 ----
CU="pg$TAIL"; fixture_user "$CU"
CC=$(credit_code "pg$TAIL")
req POST /public/auth/register/company "" "{\"username\":\"$CU\",\"password\":\"pass123\",\"nickname\":\"待审企业$TAIL\",\"companyName\":\"待审科技$TAIL\",\"creditCode\":\"$CC\",\"contactName\":\"王HR\",\"contactPhone\":\"137${TAIL: -8}\",\"industry\":\"互联网\",\"scale\":2,\"province\":\"浙江\",\"city\":\"杭州\"}"
expect_ok "注册待审企业"
login "$CU" pass123; T_PEND=$TOKEN; expect_ok "待审企业可登录"
req POST /company/jobs "$T_PEND" "$JOB_JSON"; expect_http 403 "待审企业不能发布职位"
req PUT "/company/jobs/$JOB/shelf" "$T_PEND" '{"shelfStatus":1}'; expect_http 403 "待审企业不能上架职位"
req GET /company/profile "$T_PEND"; expect_ok "待审企业仍可查看 / 完善资料"

# ---- 3. 学生删除投递所用简历后，投递记录正常显示 ----
SU="rd$TAIL"; fixture_user "$SU"
req POST /public/auth/register/student "" "{\"username\":\"$SU\",\"password\":\"pass123\",\"nickname\":\"删简历$TAIL\",\"realName\":\"删简历同学\",\"gender\":1,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"软件工程\"}"
expect_ok "注册学生"
login "$SU" pass123; T_SU=$TOKEN
req POST /student/resumes "$T_SU" "$(jq -n --arg t "待删除简历$TS" '{title:$t, isDefault:1, educationExp:"测试大学 本科", projectExp:"在线商城后端", internshipExp:"无", skillDesc:"Java、MySQL", selfEvaluation:"认真负责", attachmentUrl:""}')"
expect_ok "创建简历"
RID=$(jqv .data.id); fixture_resume "$RID"
req POST /student/applications "$T_SU" "{\"jobId\":$JOB,\"resumeId\":$RID}"; expect_ok "用该简历投递"
APP=$(jqv .data)
req DELETE "/student/resumes/$RID" "$T_SU"; expect_ok "学生删除简历"
req GET /student/resumes "$T_SU"; expect_ok "简历列表"
[ "$(jq --argjson id "$RID" '[.data[]? | select(.id == $id)] | length' <<<"$BODY")" = 0 ] && ok "已删除简历不再出现在学生简历列表" || bad "已删除简历不再出现在学生简历列表"

req GET /student/applications "$T_SU"; expect_ok "学生投递列表正常"
[ "$(jq --argjson id "$APP" '[(.data.records // .data)[] | select(.id == $id)] | length' <<<"$BODY")" = 1 ] && ok "投递记录仍在" || bad "投递记录仍在"
req GET "/student/applications/$APP" "$T_SU"; expect_ok "学生投递详情正常"

req GET "/company/applications/$APP" "$T_CO"; expect_ok "企业候选人详情不报错"
expect_jq .data.resumeDeleted true "标记简历已删除"
expect_jq .data.resume.title "待删除简历$TS" "仍展示删除前的简历内容"
expect_jq .data.resume.projectExp "在线商城后端" "项目经历保留"
req GET "/company/applications?current=1&size=50&jobId=$JOB" "$T_CO"; expect_ok "企业候选人列表正常"
HTTP=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $T_CO" "$BASE/company/applications/$APP/resume-file")
[ "$HTTP" = 404 ] && ok "无附件时下载原件返回 404（不是 500）" || bad "无附件时下载原件返回 404" "http=$HTTP"
req POST /student/applications "$T_SU" "{\"jobId\":$JOB,\"resumeId\":$RID}"; expect_fail "已删除的简历不能再用于投递"

summary
