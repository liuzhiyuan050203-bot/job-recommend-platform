#!/usr/bin/env bash
# Step3 招聘流程：职位、检索、收藏、简历、投递状态机、面试通知与 IDOR
cd "$(dirname "$0")"
source ./lib.sh
TS=${TS:-$(date +%s)}
echo "### 03 招聘流程"

login admin admin123; T_ADMIN=$TOKEN; expect_ok "管理员登录"
login student student123; T_STU=$TOKEN; expect_ok "学生登录"
login company company123; T_COM=$TOKEN; expect_ok "企业登录"

# 本脚本借用演示账号 student / company 走完整招聘流程；退出时由 purge_fixtures 删除本次的职位、简历、投递、
# 面试与行为日志，并恢复演示学生原来的默认简历，避免演示首页和看板被「已录用」测试数据淹没。
fixture_keep_default student
SU="rstu$TS"
fixture_user "$SU"
req POST /public/auth/register/student "" "{\"username\":\"$SU\",\"password\":\"pass123\",\"nickname\":\"流程学生$TS\",\"realName\":\"流程同学\",\"gender\":1,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"软件工程\"}"
expect_ok "注册第二个学生"
login "$SU" pass123; T_STU2=$TOKEN; expect_ok "第二个学生登录"

CU="rcom$TS"
fixture_user "$CU"
CC=$(printf '91R%013d' "$((TS % 10000000000000))")
req POST /public/auth/register/company "" "{\"username\":\"$CU\",\"password\":\"pass123\",\"nickname\":\"流程企业$TS\",\"companyName\":\"流程科技$TS\",\"creditCode\":\"$CC\",\"contactName\":\"王招聘\",\"contactPhone\":\"13900000000\",\"industry\":\"互联网\",\"scale\":2,\"province\":\"浙江\",\"city\":\"杭州\"}"
expect_ok "注册第二个企业"
COM2_ID=$(jqv '.data.company.id')
login "$CU" pass123; T_COM2=$TOKEN; expect_ok "第二个企业登录"
req GET /company/jobs "$T_COM2"; expect_http 403 "未过审企业不能管理职位"

req PUT "/admin/companies/$COM2_ID/audit" "$T_ADMIN" '{"auditStatus":1,"auditRemark":"测试通过"}'
expect_ok "管理员通过第二个企业资质"
req GET /company/jobs "$T_COM2"; expect_ok "过审企业可查看自己的职位"

TITLE="招聘流程测试$TS"
JOB_JSON=$(jq -n --arg title "$TITLE" '{
  categoryId:2, title:$title, province:"浙江", city:"杭州", district:"西湖区", address:"测试路1号",
  salaryMin:16000, salaryMax:24000, salaryMonths:13, education:2, experienceReq:1, jobType:3,
  headcount:2, description:"负责接口开发", requirement:"熟悉 Java", welfare:"五险一金", tagIds:[1,2]
}')
BAD_JSON=$(echo "$JOB_JSON" | jq '.salaryMin=30000 | .salaryMax=10000 | .title="薪资错误"')
req POST /company/jobs "$T_COM" "$BAD_JSON"; expect_fail "薪资区间非法"

req POST /company/jobs "$T_COM" "$JOB_JSON"
expect_ok "企业发布职位"
JOB=$(jqv '.data.id')
fixture_job "$JOB"
expect_jq .data.auditStatus 0 "新职位待审核"
expect_jq .data.techDirection "后端开发" "技术方向取分类名称"
[ -n "$JOB" ] && [ "$JOB" != null ] && ok "返回职位编号" || bad "返回职位编号"

ENC_TITLE=$(jq -rn --arg t "$TITLE" '$t|@uri')
req GET "/public/jobs?keyword=$ENC_TITLE"; expect_ok "未审核职位公开检索成功"
expect_jq .data.total 0 "未审核职位不可见"

req PUT "/admin/jobs/$JOB/audit" "$T_ADMIN" '{"auditStatus":1,"auditRemark":"信息完整"}'
expect_ok "管理员审核职位"
req GET "/public/jobs?keyword=$ENC_TITLE"; expect_jq .data.total 0 "未上架职位不可见"

req PUT "/company/jobs/$JOB/shelf" "$T_COM" '{"shelfStatus":1}'
expect_ok "企业上架"
req GET "/public/jobs?keyword=$ENC_TITLE"; expect_ok "上架后可检索"
echo "$BODY" | jq -e --argjson id "$JOB" '.data.records | map(.id) | index($id) != null' >/dev/null \
  && ok "检索结果包含新职位" || bad "检索结果包含新职位"
expect_jq '.data.records[0].companyName' "星澜科技" "卡片带企业名"
echo "$BODY" | jq -e '.data.records[0].tagNames | index("Java") != null' >/dev/null \
  && ok "卡片带标签名" || bad "卡片带标签名"

req GET "/public/jobs?keyword=$ENC_TITLE&city=%E6%9D%AD%E5%B7%9E&techDirection=%E5%90%8E%E7%AB%AF%E5%BC%80%E5%8F%91&categoryId=2&education=2&jobType=3&salaryMin=20000&salaryMax=22000&tagIds=1,2&sort=newest" "$T_STU"
expect_ok "多条件检索"
echo "$BODY" | jq -e --argjson id "$JOB" '.data.records | map(.id) | index($id) != null' >/dev/null \
  && ok "学历与薪资重叠命中" || bad "学历与薪资重叠命中"
expect_jq '.data.records[0].favorited' false "尚未收藏"

req GET "/public/jobs?keyword=$ENC_TITLE&education=1"; expect_ok "低学历筛选"
echo "$BODY" | jq -e --argjson id "$JOB" '.data.records | map(.id) | index($id) == null' >/dev/null \
  && ok "学历要求高于本人时不返回" || bad "学历要求高于本人时不返回"
req GET "/public/jobs?keyword=$ENC_TITLE&salaryMin=30000&salaryMax=40000"; expect_ok "薪资不重叠"
echo "$BODY" | jq -e --argjson id "$JOB" '.data.records | map(.id) | index($id) == null' >/dev/null \
  && ok "薪资区间不重叠时排除" || bad "薪资区间不重叠时排除"
req GET "/public/jobs?sort=salary%3Bdrop+table+job_position"; expect_ok "排序注入按白名单回落"

req GET "/public/jobs/$JOB" "bad.token.x"; expect_ok "公开详情忽略无效令牌"
V1=$(jqv '.data.viewCount')
req GET "/public/jobs/$JOB" "$T_STU"; expect_ok "学生查看详情"
V2=$(jqv '.data.viewCount')
[ "$V2" -gt "$V1" ] && ok "浏览次数增加" || bad "浏览次数增加: $V1 -> $V2"

req POST /student/favorites "$T_STU" "{\"jobId\":$JOB}"; expect_ok "收藏职位"
req GET "/public/jobs/$JOB" "$T_STU"; expect_jq .data.favorited true "详情标记已收藏"
FAV=$(jqv '.data.favoriteCount')
req POST /student/favorites "$T_STU" "{\"jobId\":$JOB}"; expect_ok "重复收藏幂等"
req GET "/public/jobs/$JOB" "$T_STU"; expect_jq .data.favoriteCount "$FAV" "重复收藏不重复计数"
req GET "/student/favorites?size=50" "$T_STU"; expect_ok "收藏列表"
echo "$BODY" | jq -e --argjson id "$JOB" '.data.records | map(.id) | index($id) != null' >/dev/null \
  && ok "收藏列表包含该职位" || bad "收藏列表包含该职位"

RESUME_JSON=$(jq -n --arg title "招聘流程测试简历$TS" '{
  title:$title, isDefault:0, educationExp:"本科", projectExp:"招聘流程测试项目",
  internshipExp:"无", skillDesc:"Java", selfEvaluation:"测试简历", attachmentUrl:""
}')
req POST /student/resumes "$T_STU" "$RESUME_JSON"; expect_ok "创建简历"
RESUME=$(jqv '.data.id')
fixture_resume "$RESUME"
req PUT "/student/resumes/$RESUME/default" "$T_STU"; expect_ok "设为默认简历"
req GET /student/resumes "$T_STU"; expect_ok "简历列表"
expect_jq ".data[] | select(.id==$RESUME) | .isDefault" 1 "默认标记"

req POST /student/applications "$T_STU" "{\"jobId\":$JOB,\"resumeId\":$RESUME}"
expect_ok "投递简历"
APP=$(jqv '.data')
req POST /student/applications "$T_STU" "{\"jobId\":$JOB,\"resumeId\":$RESUME}"
expect_fail "重复投递失败"
echo "$BODY" | jq -r '.msg' | grep -q '已投递' && ok "重复投递提示已投递" || bad "重复投递提示已投递"
req GET "/public/jobs/$JOB" "$T_STU"; expect_jq .data.applied true "详情标记已投递"

req GET "/student/applications?size=50" "$T_STU"; expect_ok "我的投递"
echo "$BODY" | jq -e --argjson id "$APP" '.data.records | map(select(.id==$id)) | .[0].statusName == "待初筛"' >/dev/null \
  && ok "投递列表含状态名" || bad "投递列表含状态名"
req GET "/student/applications/$APP" "$T_STU"; expect_ok "投递详情"
expect_jq '.data.logs | length' 1 "新建日志"
expect_jq .data.logs[0].toStatus 0 "日志到待初筛"
req GET "/student/applications/$APP" "$T_STU2"; expect_http 403 "其他学生不能看该投递"

req PUT "/company/jobs/$JOB" "$T_COM2" "$JOB_JSON"; expect_http 403 "其他企业不能改职位"
req PUT "/company/jobs/$JOB/shelf" "$T_COM2" '{"shelfStatus":0}'; expect_http 403 "其他企业不能下架"
req GET "/company/applications/$APP" "$T_COM2"; expect_http 403 "其他企业不能看投递"
req GET "/company/applications?jobId=$JOB" "$T_COM"; expect_ok "本企业候选人列表"
echo "$BODY" | jq -e --argjson id "$APP" '.data.records | map(.id) | index($id) != null' >/dev/null \
  && ok "候选人列表包含该投递" || bad "候选人列表包含该投递"
req GET "/company/applications/$APP" "$T_COM"; expect_ok "候选人详情"
expect_jq .data.resume.projectExp "招聘流程测试项目" "详情含投递简历"
expect_jq .data.studentName "陈晓" "详情含学生档案"

EXAM_AT=$(date -d '+1 day' '+%Y-%m-%d %H:%M:%S')
MEET_AT=$(date -d '+2 day' '+%Y-%m-%d %H:%M:%S')
EXAM_JSON=$(jq -n --arg t "$EXAM_AT" '{noticeType:1, interviewTime:$t, interviewType:1, meetingUrl:"https://exam.example.com/room", contactName:"周宁", contactPhone:"13800000003", remark:"笔试通知"}')
req POST "/company/applications/$APP/interviews" "$T_COM" "$EXAM_JSON"
expect_ok "发送笔试通知"
EXAM_ID=$(jqv '.data')
req GET "/company/applications/$APP" "$T_COM"; expect_jq .data.status 1 "笔试通知把待初筛改为笔试"

req GET /student/interviews/upcoming "$T_STU"; expect_ok "即将到来的安排"
echo "$BODY" | jq -e --arg t "$TITLE" '[.data[] | select(.jobTitle==$t)] | length > 0' >/dev/null \
  && ok "学生能看到新的笔试安排" || bad "学生能看到新的笔试安排"

MEET_JSON=$(jq -n --arg t "$MEET_AT" '{noticeType:2, interviewTime:$t, interviewType:2, location:"杭州市西湖区测试路1号", contactName:"周宁", contactPhone:"13800000003", remark:"面试通知"}')
req POST "/company/applications/$APP/interviews" "$T_COM" "$MEET_JSON"
expect_ok "发送面试通知"
req GET "/company/applications/$APP" "$T_COM"; expect_jq .data.status 2 "面试通知进入面试中"

req PUT "/company/interviews/$EXAM_ID/result" "$T_COM" '{"interviewStatus":1,"remark":"笔试通过"}'
expect_ok "记录笔试结果"
req GET "/company/interviews?size=50" "$T_COM"; expect_ok "企业面试列表"
echo "$BODY" | jq -e --argjson id "$EXAM_ID" '.data.records | map(select(.id==$id)) | .[0].interviewStatus == 1' >/dev/null \
  && ok "面试列表能看到结果" || bad "面试列表能看到结果"
req PUT "/company/interviews/$EXAM_ID/result" "$T_COM2" '{"interviewStatus":2,"remark":"越权"}'
expect_http 403 "其他企业不能改面试结果"

req PUT "/company/applications/$APP/status" "$T_COM" '{"toStatus":3,"remark":"录用"}'
expect_ok "录用"
req GET "/student/applications/$APP" "$T_STU"
expect_jq .data.status 3 "学生看到已录用"
echo "$BODY" | jq -e '.data.logs | map(.toStatus) | index(3) != null' >/dev/null \
  && ok "时间线含录用" || bad "时间线含录用"
echo "$BODY" | jq -e '.data.interviews | length >= 2' >/dev/null \
  && ok "详情含面试安排" || bad "详情含面试安排"

req PUT "/company/applications/$APP/status" "$T_COM" '{"toStatus":1,"remark":"非法回退"}'
expect_http 400 "终态不能回退"
echo "$BODY" | jq -r '.msg' | grep -q '不允许从「已录用」变为「笔试」' && ok "非法迁移文案" || bad "非法迁移文案: $(echo "$BODY" | jq -r .msg)"

req PUT "/company/jobs/$JOB" "$T_COM" "$JOB_JSON"; expect_ok "编辑关键信息"
req GET "/company/jobs/$JOB" "$T_COM"; expect_jq .data.auditStatus 0 "编辑后重新待审"
req GET "/public/jobs?keyword=$ENC_TITLE"; expect_jq .data.total 0 "重新待审后公开不可见"

req GET /admin/overview "$T_ADMIN"; expect_ok "管理员总览"
echo "$BODY" | jq -e '.data.jobTotal >= 1 and .data.applicationTotal >= 1 and (.data.applicationStatusCounts | length) == 5' >/dev/null \
  && ok "总览含职位、投递与各状态" || bad "总览含职位、投递与各状态"
req GET "/admin/applications?jobId=$JOB&status=3" "$T_ADMIN"; expect_ok "全平台投递筛选"
echo "$BODY" | jq -e --argjson id "$APP" '.data.records | map(.id) | index($id) != null' >/dev/null \
  && ok "总览表格含该投递" || bad "总览表格含该投递"

req DELETE "/student/favorites/$JOB" "$T_STU"; expect_ok "取消收藏"
req GET "/public/jobs/$JOB" "not-a-jwt"
[ "$HTTP" = 404 ] && ok "无效令牌访问不可见职位返回 404" || bad "无效令牌访问不可见职位应 404 实际 HTTP $HTTP"

if db_ping; then
  CNT=$(db_sql "select count(*) from user_behavior_log where user_id=2 and target_id=$JOB and behavior_type in (1,2,3) and deleted=0")
  [ "$CNT" -ge 3 ] && ok "浏览收藏投递写入行为日志" || bad "行为日志条数=$CNT"
fi

summary
