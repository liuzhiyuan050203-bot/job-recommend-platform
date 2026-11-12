#!/usr/bin/env bash
# 知识库职位增量同步，以及企业合规 / 薪资意图路由。
# ai-service 未启动时记 SKIP 且失败数为 0。
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source ./lib.sh
TS=${TS:-$(date +%s)}
AI=${AI:-http://127.0.0.1:8000}
echo "### 18 知识库同步与意图路由"

if ! curl -sf -m 2 -o /dev/null "$AI/health"; then
  echo "  [SKIP] ai-service 未运行（${AI}/health），跳过本脚本"
  echo "== $(basename "$0"): PASS=0 FAIL=0 (SKIP)"
  echo "$(basename "$0") 0 0" >> /tmp/job-api-test-summary.txt
  exit 0
fi

enc() { jq -rn --arg v "$1" '$v|@uri'; }

ai_call() {
  local method=$1 url=$2 token=${3:-} data=${4:-}
  local args=(-s -m 30 -o /tmp/_ai_body -w '%{http_code}' -X "$method" "$url")
  if [ -n "$token" ]; then
    args+=(-H "X-Internal-Token: $token")
  fi
  if [ -n "$data" ]; then
    args+=(-H 'Content-Type: application/json' --data-raw "$data")
  fi
  HTTP=$(curl "${args[@]}")
  BODY=$(cat /tmp/_ai_body)
}

JOB=""
T_ADMIN=""
cleanup() {
  if [ -n "$JOB" ] && [ -n "$T_ADMIN" ]; then
    curl -s -m 20 -o /dev/null -X POST "$BASE/admin/ai/knowledge/jobs/sync" \
      -H "Authorization: Bearer $T_ADMIN" \
      -H 'Content-Type: application/json' \
      --data-raw "{\"jobIds\":[$JOB]}" || true
  fi
  purge_fixtures || true
}
trap cleanup EXIT

ai_call POST "$AI/rag/jobs/sync" "" '{"job_ids":[1]}'
expect_http 401 "无令牌 /rag/jobs/sync 401"
ai_call POST "$AI/rag/jobs/sync" "definitely-wrong" '{"job_ids":[1]}'
expect_http 403 "错误令牌 /rag/jobs/sync 403"
ai_call POST "$AI/agent/route" "" '{"question":"ping","role":"student"}'
expect_http 401 "无令牌 /agent/route 401"
ai_call POST "$AI/agent/route" "definitely-wrong" '{"question":"ping","role":"student"}'
expect_http 403 "错误令牌 /agent/route 403"

login admin admin123; T_ADMIN=$TOKEN; expect_ok "管理员登录"
login student student123; T_STU=$TOKEN; expect_ok "学生登录"
login company company123; T_CO=$TOKEN; expect_ok "企业登录"

req POST /admin/ai/knowledge/route "$T_STU" '{"question":"招候选人只限男性合不合规","role":"company"}'
expect_http 403 "学生不能预览路由"

req POST /admin/ai/knowledge/route "$T_ADMIN" '{"question":"招候选人只限男性合不合规","role":"company"}'
expect_ok "企业合规问题路由"
[ "$(jq '[.data.tools[].name] | index("screen_applicants")' <<<"$BODY")" = null ] \
  && ok "合规问题不调用筛选候选人" || bad "合规问题不调用筛选候选人"
TYPES=$(jq -r '[.data.doc_types[]? | tostring] | join(",")' <<<"$BODY")
echo "$TYPES" | grep -Eq '(^|,)(4|6)(,|$)' && ok "合规问题检索企业知识库($TYPES)" || bad "合规问题检索企业知识库($TYPES)"

req POST /admin/ai/knowledge/route "$T_ADMIN" '{"question":"向候选人收培训费合不合法","role":"company"}'
expect_ok "培训费合规路由"
[ "$(jq '[.data.tools[].name] | index("screen_applicants")' <<<"$BODY")" = null ] \
  && ok "培训费问题不调用筛选" || bad "培训费问题不调用筛选"

req POST /admin/ai/knowledge/route "$T_ADMIN" '{"question":"帮我筛选职位 1 的候选人","role":"company"}'
expect_ok "筛选候选人路由保持不变"
[ "$(jq -r '.data.tools[0].name' <<<"$BODY")" = "screen_applicants" ] \
  && ok "筛选意图仍走 screen_applicants" || bad "筛选意图仍走 screen_applicants"

req POST /admin/ai/knowledge/route "$T_ADMIN" '{"question":"杭州 Java 后端月薪多少","role":"student"}'
expect_ok "薪资问题路由"
NAMES=$(jq -r '[.data.tools[].name] | join(",")' <<<"$BODY")
echo "$NAMES" | grep -q "predict_salary" && ok "薪资问题调用 predict_salary" || bad "薪资问题调用 predict_salary ($NAMES)"
echo "$NAMES" | grep -q "search_jobs" && ok "薪资问题同时检索在招岗位" || bad "薪资问题同时检索在招岗位 ($NAMES)"
[ "$(jq -r '.data.doc_types | join(",")' <<<"$BODY")" = "7" ] \
  && ok "薪资问题检索职位资料" || bad "薪资问题检索职位资料"

req POST /admin/ai/knowledge/route "$T_ADMIN" '{"question":"懂车帝在招哪些产品经理","role":"student"}'
expect_ok "懂车帝职位检索路由"
[ "$(jq -r '.data.tools[0].name' <<<"$BODY")" = "search_jobs" ] \
  && ok "懂车帝问题走 search_jobs" || bad "懂车帝问题走 search_jobs"
[ "$(jq -r '.data.slots.keyword // empty' <<<"$BODY")" = "懂车帝" ] \
  && ok "识别企业名懂车帝" || bad "识别企业名懂车帝"

# ---- 职位同步：上架后出现在知识库，下架后移除 ----
MARKER="相位同步标记${TS}"
JOB_JSON=$(jq -n --arg title "知识库同步岗$TS" --arg desc "负责${MARKER}相关接口开发与维护" --arg req "熟悉 Java 与 ${MARKER}" \
  '{title:$title, categoryId:2, province:"浙江", city:"杭州", district:"西湖区", address:"测试路1号",
    salaryMin:12000, salaryMax:20000, salaryMonths:13, education:2, experienceReq:0, jobType:3, headcount:1,
    description:$desc, requirement:$req, welfare:"五险一金", tagIds:[1]}')
req POST /company/jobs "$T_CO" "$JOB_JSON"; expect_ok "发布待同步职位"
JOB=$(jqv .data.id); fixture_job "$JOB"
req PUT "/admin/jobs/$JOB/audit" "$T_ADMIN" '{"auditStatus":1,"auditRemark":"通过"}'; expect_ok "审核通过"
req PUT "/company/jobs/$JOB/shelf" "$T_CO" '{"shelfStatus":1}'; expect_ok "上架职位"

req POST /admin/ai/knowledge/jobs/sync "$T_ADMIN" "{\"jobIds\":[$JOB]}"
expect_ok "同步已上架职位到知识库"

HIT_OK=0
for _try in 1 2 3 4 5 6; do
  req GET "/admin/ai/knowledge/search?q=$(enc "$MARKER")&topK=8&docType=7" "$T_ADMIN"
  if [ "$HTTP" = 200 ] && [ "$(jq -r .code <<<"$BODY")" = 200 ]; then
    if [ "$(jq --arg t "知识库同步岗$TS" --arg m "$MARKER" '[.data.results[] | select((.title==$t) or ((.content // "") | contains($m)))] | length' <<<"$BODY")" -ge 1 ]; then
      HIT_OK=1
      break
    fi
  fi
  sleep 1
done
[ "$HTTP" = 200 ] && [ "$(jq -r .code <<<"$BODY")" = 200 ] && ok "检索同步职位接口成功" || bad "检索同步职位接口成功"
[ "$HIT_OK" = 1 ] && ok "上架后知识库能检索到该职位" || bad "上架后知识库能检索到该职位"

req PUT "/company/jobs/$JOB/shelf" "$T_CO" '{"shelfStatus":0}'; expect_ok "下架职位"
req POST /admin/ai/knowledge/jobs/sync "$T_ADMIN" "{\"jobIds\":[$JOB]}"
expect_ok "同步已下架职位（应从知识库移除）"

GONE=0
for _try in 1 2 3 4 5 6; do
  req GET "/admin/ai/knowledge/search?q=$(enc "$MARKER")&topK=8&docType=7" "$T_ADMIN"
  if [ "$HTTP" = 200 ] && [ "$(jq -r .code <<<"$BODY")" = 200 ]; then
    if [ "$(jq --arg t "知识库同步岗$TS" --arg m "$MARKER" '[.data.results[] | select((.title==$t) or ((.content // "") | contains($m)))] | length' <<<"$BODY")" = 0 ]; then
      GONE=1
      break
    fi
  fi
  sleep 1
done
[ "$GONE" = 1 ] && ok "下架后知识库已无该职位" || bad "下架后知识库已无该职位"

summary
