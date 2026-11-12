#!/usr/bin/env bash
# 投递时保存简历快照：企业看到投递当时的内容；学生事后修改会提示「投递后简历已更新」
source "$(dirname "$0")/lib.sh"
TS=${TS:-$(date +%s)}
TAIL=${TS: -8}
echo "== 19 投递简历快照 =="

login admin admin123; T_ADMIN=$TOKEN
login company company123; T_CO=$TOKEN; expect_ok "已认证企业登录"

JOB_JSON=$(jq -n --arg title "快照测试岗$TS" '{title:$title, categoryId:2, province:"浙江", city:"杭州", district:"西湖区", address:"测试路1号",
  salaryMin:12000, salaryMax:20000, salaryMonths:13, education:2, experienceReq:0, jobType:3, headcount:1,
  description:"负责后端接口开发", requirement:"熟悉 Java", welfare:"五险一金", tagIds:[1]}')
req POST /company/jobs "$T_CO" "$JOB_JSON"; expect_ok "发布职位（待审核草稿）"
JOB=$(jqv .data.id); fixture_job "$JOB"
req PUT "/admin/jobs/$JOB/audit" "$T_ADMIN" '{"auditStatus":1,"auditRemark":"通过"}'; expect_ok "管理员审核通过"
req PUT "/company/jobs/$JOB/shelf" "$T_CO" '{"shelfStatus":1}'; expect_ok "上架"

SU="rs$TAIL"; fixture_user "$SU"
req POST /public/auth/register/student "" "{\"username\":\"$SU\",\"password\":\"pass123\",\"nickname\":\"快照学生$TAIL\",\"realName\":\"快照同学\",\"gender\":1,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"软件工程\"}"
expect_ok "注册学生"
login "$SU" pass123; T_SU=$TOKEN
TITLE="投递时简历$TS"
req POST /student/resumes "$T_SU" "$(jq -n --arg t "$TITLE" '{title:$t, isDefault:1, educationExp:"测试大学 本科", projectExp:"在线商城后端", internshipExp:"无", skillDesc:"Java、MySQL", selfEvaluation:"认真负责", attachmentUrl:""}')"
expect_ok "创建简历"
RID=$(jqv .data.id); fixture_resume "$RID"
req POST /student/applications "$T_SU" "{\"jobId\":$JOB,\"resumeId\":$RID}"; expect_ok "用该简历投递"
APP=$(jqv .data)

# 库中已有快照，内容与投递时一致
SNAP_TITLE=$(db_sql "SELECT title FROM job_application_resume WHERE application_id=$APP")
[ "$SNAP_TITLE" = "$TITLE" ] && ok "投递后写入快照标题" || bad "投递后写入快照标题" "got=$SNAP_TITLE"
SNAP_PROJ=$(db_sql "SELECT project_exp FROM job_application_resume WHERE application_id=$APP")
[ "$SNAP_PROJ" = "在线商城后端" ] && ok "快照项目经历为投递时内容" || bad "快照项目经历为投递时内容" "got=$SNAP_PROJ"

req GET "/company/applications/$APP" "$T_CO"; expect_ok "企业查看候选人详情"
expect_jq .data.resume.title "$TITLE" "企业看到投递时标题"
expect_jq .data.resume.projectExp "在线商城后端" "企业看到投递时项目经历"
expect_jq .data.resumeDeleted false "未删除"
expect_jq .data.resumeUpdatedAfterApply false "投递后尚未修改"

# 学生修改在线简历
req PUT "/student/resumes/$RID" "$T_SU" "$(jq -n --arg t "修改后简历$TS" '{title:$t, isDefault:1, educationExp:"测试大学 本科已更新", projectExp:"分布式交易系统", internshipExp:"某厂实习", skillDesc:"Java、Redis", selfEvaluation:"已更新评价", attachmentUrl:""}')"
expect_ok "学生修改在线简历"

req GET "/student/resumes/$RID" "$T_SU"; expect_ok "学生看到修改后的简历"
expect_jq .data.title "修改后简历$TS" "学生简历标题已更新"
expect_jq .data.projectExp "分布式交易系统" "学生项目经历已更新"

req GET "/company/applications/$APP" "$T_CO"; expect_ok "企业再次查看候选人详情"
expect_jq .data.resume.title "$TITLE" "企业仍看到投递时标题"
expect_jq .data.resume.projectExp "在线商城后端" "企业仍看到投递时项目经历"
expect_jq .data.resume.educationExp "测试大学 本科" "教育经历保持快照"
expect_jq .data.resume.selfEvaluation "认真负责" "自我评价保持快照"
expect_jq .data.resumeUpdatedAfterApply true "标记投递后简历已更新"
expect_jq .data.resumeDeleted false "未删除"

# 库中快照未被覆盖
SNAP_PROJ2=$(db_sql "SELECT project_exp FROM job_application_resume WHERE application_id=$APP")
[ "$SNAP_PROJ2" = "在线商城后端" ] && ok "修改后快照未被覆盖" || bad "修改后快照未被覆盖" "got=$SNAP_PROJ2"

req GET "/student/applications/$APP" "$T_SU"; expect_ok "学生投递详情可看快照"
expect_jq .data.resume.projectExp "在线商城后端" "学生投递详情也是快照"
expect_jq .data.resumeUpdatedAfterApply true "学生端也标记已更新"

# 删除在线简历后仍展示快照
req DELETE "/student/resumes/$RID" "$T_SU"; expect_ok "学生删除简历"
req GET "/company/applications/$APP" "$T_CO"; expect_ok "删除后企业详情不报错"
expect_jq .data.resumeDeleted true "标记简历已删除"
expect_jq .data.resume.title "$TITLE" "删除后仍展示投递时内容"
expect_jq .data.resume.projectExp "在线商城后端" "删除后项目经历仍是快照"

summary
