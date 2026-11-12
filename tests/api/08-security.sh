#!/usr/bin/env bash
# 跨租户：投递、简历、面试、AI 会话。企业只能看自己职位上的投递和对应简历原件。
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source ./lib.sh
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PY=${PY:-$ROOT/.venv/bin/python}
TS=${TS:-$(date +%s)}
AI_PID=""
AI_STARTED=0
echo "### 08 越权隔离"

cleanup() {
  purge_fixtures
  if [ "$AI_STARTED" = 1 ] && [ -n "$AI_PID" ]; then
    kill "$AI_PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$AI_PID" 2>/dev/null || break
      sleep 0.3
    done
    kill -9 "$AI_PID" 2>/dev/null || true
    wait "$AI_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

ensure_ai() {
  if curl -sf -m 2 -o /dev/null "http://127.0.0.1:8000/health"; then
    return 0
  fi
  echo "  启动 ai-service 以便校验简历原件下载"
  (
    cd "$ROOT/ai-service" || exit 1
    exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  ) > /tmp/ai-service-08.log 2>&1 &
  AI_PID=$!
  AI_STARTED=1
  for _ in $(seq 1 90); do
    if curl -sf -m 2 -o /dev/null "http://127.0.0.1:8000/health"; then
      return 0
    fi
    if ! kill -0 "$AI_PID" 2>/dev/null; then
      echo "  ai-service 已退出"
      tail -n 40 /tmp/ai-service-08.log || true
      return 1
    fi
    sleep 1
  done
  echo "  等待 ai-service 超时"
  tail -n 40 /tmp/ai-service-08.log || true
  return 1
}

upload_pdf() {
  local token=$1 file=$2
  HTTP=$(curl -s -m 60 -o /tmp/_body -w '%{http_code}' -X POST "$BASE/student/resume/upload" \
    -H "Authorization: Bearer $token" \
    -F "file=@${file};filename=resume.pdf")
  BODY=$(cat /tmp/_body)
}

download_to() {
  local path=$1 token=$2 out=$3
  local args=(-s -m 30 -o "$out" -w '%{http_code}' "$BASE$path")
  [ -n "$token" ] && args+=(-H "Authorization: Bearer $token")
  HTTP=$(curl "${args[@]}")
  BODY=$(head -c 400 "$out" 2>/dev/null || true)
}

login admin admin123; T_ADMIN=$TOKEN; expect_ok "管理员登录"
login company company123; T_COM=$TOKEN; expect_ok "企业甲登录"

SUA="secua$TS"
fixture_user "$SUA"
SUB="secub$TS"
fixture_user "$SUB"
req POST /public/auth/register/student "" "{\"username\":\"$SUA\",\"password\":\"pass123\",\"nickname\":\"安全学生甲$TS\",\"realName\":\"安全甲\",\"gender\":1,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"软件工程\"}"
expect_ok "注册学生甲"
login "$SUA" pass123; T_A=$TOKEN; expect_ok "学生甲登录"
req POST /public/auth/register/student "" "{\"username\":\"$SUB\",\"password\":\"pass123\",\"nickname\":\"安全学生乙$TS\",\"realName\":\"安全乙\",\"gender\":2,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"软件工程\"}"
expect_ok "注册学生乙"
login "$SUB" pass123; T_B=$TOKEN; expect_ok "学生乙登录"

CU="seccom$TS"
fixture_user "$CU"
CC=$(credit_code "s$TS")
req POST /public/auth/register/company "" "{\"username\":\"$CU\",\"password\":\"pass123\",\"nickname\":\"安全企业乙$TS\",\"companyName\":\"安全科技$TS\",\"creditCode\":\"$CC\",\"contactName\":\"赵招聘\",\"contactPhone\":\"13900001111\",\"industry\":\"互联网\",\"scale\":2,\"province\":\"浙江\",\"city\":\"杭州\"}"
expect_ok "注册企业乙"
COM2_ID=$(jqv '.data.company.id')
login "$CU" pass123; T_COM2=$TOKEN; expect_ok "企业乙登录"
req PUT "/admin/companies/$COM2_ID/audit" "$T_ADMIN" '{"auditStatus":1,"auditRemark":"安全测试通过"}'
expect_ok "审核企业乙"

TITLE="越权隔离职位$TS"
JOB_JSON=$(jq -n --arg title "$TITLE" '{
  categoryId:2, title:$title, province:"浙江", city:"杭州", district:"西湖区", address:"安全路1号",
  salaryMin:12000, salaryMax:18000, salaryMonths:13, education:2, experienceReq:1, jobType:3,
  headcount:1, description:"越权测试职位", requirement:"熟悉 Java", welfare:"五险一金", tagIds:[1]
}')
req POST /company/jobs "$T_COM" "$JOB_JSON"; expect_ok "企业甲发布职位"
JOB=$(jqv '.data.id')
fixture_job "$JOB"
req PUT "/admin/jobs/$JOB/audit" "$T_ADMIN" '{"auditStatus":1,"auditRemark":"通过"}'; expect_ok "审核职位"
req PUT "/company/jobs/$JOB/shelf" "$T_COM" '{"shelfStatus":1}'; expect_ok "上架职位"

RESUME_JSON=$(jq -n --arg title "安全简历$TS" '{
  title:$title, isDefault:1, educationExp:"本科", projectExp:"安全测试项目",
  internshipExp:"无", skillDesc:"Java", selfEvaluation:"仅供越权测试", attachmentUrl:""
}')
req POST /student/resumes "$T_A" "$RESUME_JSON"; expect_ok "学生甲创建简历"
RESUME=$(jqv '.data.id')
req POST /student/applications "$T_A" "{\"jobId\":$JOB,\"resumeId\":$RESUME}"; expect_ok "学生甲投递"
APP=$(jqv '.data')

req GET "/student/applications/$APP" "$T_B"; expect_http 403 "学生乙不能看甲的投递"
req GET "/student/applications/$APP" "$T_A"; expect_ok "学生甲可看自己的投递"
req GET "/student/resumes/$RESUME" "$T_B"; expect_http 403 "学生乙不能看甲的简历"
req PUT "/student/resumes/$RESUME" "$T_B" "$RESUME_JSON"; expect_http 403 "学生乙不能改甲的简历"
req DELETE "/student/resumes/$RESUME" "$T_B"; expect_http 403 "学生乙不能删甲的简历"
req GET "/student/resumes/$RESUME" "$T_A"; expect_ok "拒绝后甲仍能看自己的简历"
expect_jq .data.projectExp "安全测试项目" "简历正文未被越权改写"
req POST /student/applications "$T_B" "{\"jobId\":$JOB,\"resumeId\":$RESUME}"; expect_http 403 "学生乙不能用甲的简历投递"
req GET "/student/resumes/$RESUME" "$T_COM"; expect_http 403 "企业不能走学生简历接口"
req GET "/student/applications/$APP"; expect_http 401 "未登录不能看投递"

req GET "/company/applications/$APP" "$T_COM2"; expect_http 403 "企业乙不能看甲的投递详情"
req PUT "/company/applications/$APP/status" "$T_COM2" '{"toStatus":1,"remark":"越权"}'
expect_http 403 "企业乙不能改投递状态"
req GET "/company/applications?jobId=$JOB" "$T_COM2"; expect_http 403 "企业乙不能按甲的职位筛投递"
req GET "/company/applications/$APP" "$T_COM"; expect_ok "企业甲可看候选人详情"
expect_jq .data.resume.projectExp "安全测试项目" "详情里是投递的那份简历"
req PUT "/company/applications/$APP/status" "$T_COM" '{"toStatus":1,"remark":"进入笔试"}'
expect_ok "企业甲可更新自己的投递"
req GET "/company/applications?jobId=$JOB" "$T_COM"; expect_ok "企业甲按自己的职位筛投递"
echo "$BODY" | jq -e --argjson id "$APP" '.data.records | map(.id) | index($id) != null' >/dev/null \
  && ok "候选人列表包含该投递" || bad "候选人列表包含该投递"
req GET "/company/applications?size=50" "$T_COM2"; expect_ok "企业乙的投递列表"
echo "$BODY" | jq -e --argjson id "$APP" '.data.records | map(.id) | index($id) == null' >/dev/null \
  && ok "企业乙列表里没有甲的投递" || bad "企业乙列表里没有甲的投递"

MEET_AT=$(date -d '+2 day' '+%Y-%m-%d %H:%M:%S')
MEET_JSON=$(jq -n --arg t "$MEET_AT" '{noticeType:2, interviewTime:$t, interviewType:1, meetingUrl:"https://meet.example.com/sec", contactName:"周宁", contactPhone:"13800000003", remark:"面试"}')
req POST "/company/applications/$APP/interviews" "$T_COM2" "$MEET_JSON"; expect_http 403 "企业乙不能给甲的投递发面试"
req POST "/company/applications/$APP/interviews" "$T_COM" "$MEET_JSON"; expect_ok "企业甲可以发面试"
IV=$(jqv '.data')
req GET /student/interviews/upcoming "$T_A"; expect_ok "学生甲的面试列表"
echo "$BODY" | jq -e --argjson id "$IV" '(.data // []) | map(.id) | index($id) != null' >/dev/null \
  && ok "学生甲能看到自己的面试" || bad "学生甲能看到自己的面试"
req GET /student/interviews/upcoming "$T_B"; expect_ok "学生乙的面试列表"
echo "$BODY" | jq -e --argjson id "$IV" '(.data // []) | map(.id) | index($id) == null' >/dev/null \
  && ok "学生乙看不到甲的面试" || bad "学生乙看不到甲的面试"
req GET "/company/interviews?size=50" "$T_COM"; expect_ok "企业甲的面试列表"
echo "$BODY" | jq -e --argjson id "$IV" '.data.records | map(.id) | index($id) != null' >/dev/null \
  && ok "企业甲列表包含该面试" || bad "企业甲列表包含该面试"
req GET "/company/interviews?size=50" "$T_COM2"; expect_ok "企业乙的面试列表"
echo "$BODY" | jq -e --argjson id "$IV" '.data.records | map(.id) | index($id) == null' >/dev/null \
  && ok "企业乙列表没有该面试" || bad "企业乙列表没有该面试"
req PUT "/company/interviews/$IV/result" "$T_COM2" '{"interviewStatus":2,"remark":"越权"}'
expect_http 403 "企业乙不能改甲的面试结果"
req PUT "/company/interviews/$IV/result" "$T_COM" '{"interviewStatus":1,"remark":"已完成"}'
expect_ok "企业甲可记录面试结果"
req GET "/student/interviews/upcoming" "$T_COM"; expect_http 403 "企业不能看学生面试接口"

# 会话在连上模型之前就会落库。限制等待时间，避免模型慢把脚本拖住。
open_session() {
  local token=$1 out=$2
  curl -s -m 8 -N -o "$out" -X POST "$BASE/student/ai/chat/stream" \
    -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
    -d '{"question":"只用于越权测试不要回答"}' >/dev/null || true
}

open_session "$T_A" /tmp/sse_sec_a.txt
open_session "$T_B" /tmp/sse_sec_b.txt
SID_A=$(sed -n 's/.*"session_id":\([0-9][0-9]*\).*/\1/p' /tmp/sse_sec_a.txt | head -1)
SID_B=$(sed -n 's/.*"session_id":\([0-9][0-9]*\).*/\1/p' /tmp/sse_sec_b.txt | head -1)
if [ -z "$SID_A" ]; then
  req GET "/student/ai/sessions?size=5" "$T_A"
  SID_A=$(jqv '.data.records[0].id')
fi
if [ -z "$SID_B" ]; then
  req GET "/student/ai/sessions?size=5" "$T_B"
  SID_B=$(jqv '.data.records[0].id')
fi
[ -n "$SID_A" ] && [ "$SID_A" != null ] && ok "学生甲会话已创建" || bad "学生甲会话已创建"
[ -n "$SID_B" ] && [ "$SID_B" != null ] && ok "学生乙会话已创建" || bad "学生乙会话已创建"

if [ -n "$SID_A" ] && [ "$SID_A" != null ]; then
  req GET "/student/ai/sessions/$SID_A/messages" "$T_B"; expect_http 404 "学生乙不能读甲的会话"
  req PUT "/student/ai/sessions/$SID_A" "$T_B" '{"title":"越权改名"}'; expect_http 404 "学生乙不能改甲的会话标题"
  req DELETE "/student/ai/sessions/$SID_A" "$T_B"; expect_http 404 "学生乙不能删甲的会话"
  req GET "/student/ai/sessions/$SID_A/messages" "$T_A"; expect_ok "学生甲仍能读自己的消息"
  req GET "/company/ai/sessions/$SID_A/messages" "$T_COM"; expect_http 404 "企业在自己的会话接口里读不到学生会话"
  req GET "/student/ai/sessions/$SID_A/messages" "$T_COM"; expect_http 403 "企业不能读学生会话"
  req GET "/student/ai/sessions?size=20" "$T_B"; expect_ok "学生乙的会话列表"
  echo "$BODY" | jq -e --argjson id "$SID_A" '.data.records | map(.id) | index($id) == null' >/dev/null \
    && ok "乙的列表没有甲的会话" || bad "乙的列表没有甲的会话"
  req PUT "/student/ai/sessions/$SID_A" "$T_A" '{"title":"甲的会话"}'; expect_ok "学生甲可重命名"
  expect_jq .data.title "甲的会话" "标题已更新"
  HTTP=$(curl -s -m 15 -o /tmp/_body -w '%{http_code}' -X POST "$BASE/student/ai/chat/stream" \
    -H "Authorization: Bearer $T_B" -H 'Content-Type: application/json' \
    -d "{\"question\":\"继续越权\",\"sessionId\":$SID_A}")
  BODY=$(cat /tmp/_body)
  expect_http 404 "学生乙不能往甲的会话里发消息"
  req DELETE "/student/ai/sessions/$SID_A" "$T_A"; expect_ok "学生甲可删除自己的会话"
  req GET "/student/ai/sessions/$SID_A/messages" "$T_A"; expect_http 404 "删除后会话不可读"
fi
if [ -n "$SID_B" ] && [ "$SID_B" != null ]; then
  req DELETE "/student/ai/sessions/$SID_B" "$T_B"; expect_ok "清理学生乙的会话"
fi

PDF=/tmp/sec-resume-$TS.pdf
"$PY" "$ROOT/tests/api/resume_fixture.py" pdf "$PDF" "熟悉 Java、Spring Boot、MySQL、Vue 与 Docker" \
  && ok "生成测试 PDF" || bad "生成测试 PDF"

if ensure_ai; then
  ok "ai-service 可用"
  upload_pdf "$T_A" "$PDF"
  expect_ok "学生甲上传简历"
  expect_jq .data.resumeId "$RESUME" "原件挂在甲自己的简历上"
  download_to "/student/resumes/$RESUME/file" "$T_A" /tmp/sec_own.pdf
  expect_http 200 "学生甲可下载自己的简历原件"
  head -c 4 /tmp/sec_own.pdf | grep -q '%PDF' && ok "下载内容是 PDF" || bad "下载内容是 PDF"
  download_to "/student/resumes/$RESUME/file" "$T_B" /tmp/sec_other.bin
  expect_http 403 "学生乙不能下载甲的简历原件"
  download_to "/student/resumes/$RESUME/file" "$T_COM" /tmp/sec_com_stu.bin
  expect_http 403 "企业不能下载学生简历接口上的原件"
  download_to "/student/resumes/$RESUME/file" "" /tmp/sec_anon.bin
  expect_http 401 "未登录不能下载简历原件"
  download_to "/company/applications/$APP/resume-file" "$T_COM" /tmp/sec_com.pdf
  expect_http 200 "企业甲可下载投递过来的简历原件"
  head -c 4 /tmp/sec_com.pdf | grep -q '%PDF' && ok "企业下载内容是 PDF" || bad "企业下载内容是 PDF"
  download_to "/company/applications/$APP/resume-file" "$T_COM2" /tmp/sec_com2.bin
  expect_http 403 "企业乙不能下载甲的简历原件"
  download_to "/company/applications/$APP/resume-file" "$T_A" /tmp/sec_stu_com.bin
  expect_http 403 "学生不能走企业简历下载接口"
  download_to "/company/applications/$APP/resume-file" "" /tmp/sec_com_anon.bin
  expect_http 401 "未登录不能下载企业侧简历"
else
  bad "ai-service 可用"
fi

rm -f "$PDF" /tmp/sec_own.pdf /tmp/sec_other.bin /tmp/sec_com_stu.bin /tmp/sec_anon.bin \
  /tmp/sec_com.pdf /tmp/sec_com2.bin /tmp/sec_stu_com.bin /tmp/sec_com_anon.bin \
  /tmp/sse_sec_a.txt /tmp/sse_sec_b.txt

summary
