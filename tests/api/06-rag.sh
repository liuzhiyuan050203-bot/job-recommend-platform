#!/usr/bin/env bash
# Phase5 RAG 与三类助手：内部令牌、角色隔离、SSE、会话和知识库。
# 本地小模型较慢，流式请求 --max-time 180。ai-service 未启动时记 SKIP 且失败数为 0。
# 大模型不可达时助手走离线模式，这些断言仍然应当通过。
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source ./lib.sh
TS=${TS:-$(date +%s)}
AI=${AI:-http://127.0.0.1:8000}
echo "### 06 RAG 与智能体"

if ! curl -sf -m 2 -o /dev/null "$AI/health"; then
  echo "  [SKIP] ai-service 未运行（${AI}/health），跳过本脚本"
  echo "== $(basename "$0"): PASS=0 FAIL=0 (SKIP)"
  echo "$(basename "$0") 0 0" >> /tmp/job-api-test-summary.txt
  exit 0
fi

DOC_KEY=""
TMP_MD=""
STREAM_FILE=""
HDR_FILE=""
STU_SID=""
COM_SID=""
ADM_SID=""
T_ADMIN=""
T_STU=""
T_COM=""

enc() { jq -rn --arg v "$1" '$v|@uri'; }

cleanup() {
  if [ -n "$DOC_KEY" ] && [ -n "$T_ADMIN" ]; then
    curl -s -m 30 -o /dev/null -X DELETE \
      "$BASE/admin/ai/knowledge/documents?docKey=$(enc "$DOC_KEY")" \
      -H "Authorization: Bearer $T_ADMIN" || true
  fi
  if [ -n "$STU_SID" ] && [ -n "$T_STU" ]; then
    curl -s -m 15 -o /dev/null -X DELETE "$BASE/student/ai/sessions/$STU_SID" \
      -H "Authorization: Bearer $T_STU" || true
  fi
  if [ -n "$COM_SID" ] && [ -n "$T_COM" ]; then
    curl -s -m 15 -o /dev/null -X DELETE "$BASE/company/ai/sessions/$COM_SID" \
      -H "Authorization: Bearer $T_COM" || true
  fi
  if [ -n "$ADM_SID" ] && [ -n "$T_ADMIN" ]; then
    curl -s -m 15 -o /dev/null -X DELETE "$BASE/admin/ai/sessions/$ADM_SID" \
      -H "Authorization: Bearer $T_ADMIN" || true
  fi
  [ -n "$TMP_MD" ] && rm -f "$TMP_MD"
  [ -n "$STREAM_FILE" ] && rm -f "$STREAM_FILE"
  [ -n "$HDR_FILE" ] && rm -f "$HDR_FILE"
}
trap cleanup EXIT

ai_call() {
  # ai_call METHOD URL [TOKEN] [JSON]
  local method=$1 url=$2 token=${3:-} data=${4:-}
  local args=(-s -m 15 -o /tmp/_ai_body -w '%{http_code}' -X "$method" "$url")
  if [ -n "$token" ]; then
    args+=(-H "X-Internal-Token: $token")
  fi
  if [ -n "$data" ]; then
    args+=(-H 'Content-Type: application/json' --data-raw "$data")
  fi
  HTTP=$(curl "${args[@]}")
  BODY=$(cat /tmp/_ai_body)
}

ai_call POST "$AI/agent/chat/stream" "" '{"question":"ping"}'
expect_http 401 "无令牌 /agent/chat/stream 401"
ai_call POST "$AI/agent/chat/stream" "definitely-wrong" '{"question":"ping"}'
expect_http 403 "错误令牌 /agent/chat/stream 403"
ai_call GET "$AI/rag/search?q=ping"
expect_http 401 "无令牌 /rag/search 401"
ai_call GET "$AI/rag/search?q=ping" "definitely-wrong"
expect_http 403 "错误令牌 /rag/search 403"
ai_call GET "$AI/rag/admin/stats"
expect_http 401 "无令牌 /rag/admin/stats 401"
ai_call GET "$AI/rag/admin/stats" "definitely-wrong"
expect_http 403 "错误令牌 /rag/admin/stats 403"
ai_call GET "$AI/health"
[ "$HTTP" = 200 ] && [ "$(jq -r .code <<<"$BODY")" = 200 ] && ok "/health 无需令牌" || bad "/health 无需令牌"

login admin admin123; T_ADMIN=$TOKEN; expect_ok "管理员登录"
login student student123; T_STU=$TOKEN; expect_ok "学生登录"
login company company123; T_COM=$TOKEN; expect_ok "企业登录"

req POST /student/ai/chat/stream "" '{"question":"三方协议怎么签？"}'
expect_http 401 "未登录访问学生助手 401"
req POST /company/ai/chat/stream "$T_STU" '{"question":"列出我发布的职位"}'
expect_http 403 "学生访问企业助手 403"
req GET /admin/ai/knowledge/stats "$T_STU"
expect_http 403 "学生访问知识库统计 403"
req POST /student/ai/chat/stream "$T_COM" '{"question":"三方协议怎么签？"}'
expect_http 403 "企业访问学生助手 403"
req POST /student/ai/chat/stream "$T_STU" '{"question":""}'
expect_http 400 "空问题 400"
req POST /admin/ai/chat/stream "$T_ADMIN" '{"question":"   "}'
expect_http 400 "空白问题 400"

stream_chat() {
  local path=$1 token=$2 question=$3
  STREAM_FILE=$(mktemp /tmp/sse-body.XXXXXX)
  HDR_FILE=$(mktemp /tmp/sse-hdr.XXXXXX)
  HTTP=$(curl -sS -N --connect-timeout 5 --max-time 180 \
    -D "$HDR_FILE" -o "$STREAM_FILE" -w '%{http_code}' \
    -X POST "$BASE$path" \
    -H "Authorization: Bearer $token" \
    -H 'Content-Type: application/json' \
    -H 'Accept: text/event-stream' \
    --data-binary "$(jq -n --arg q "$question" '{question:$q}')" || true)
  CT=$(grep -i '^content-type:' "$HDR_FILE" | head -1 | tr -d '\r' || true)
  BODY=$(head -c 400 "$STREAM_FILE" 2>/dev/null || true)
}

read_sse() {
  local expect=${1:-}
  eval "$(python3 - "$STREAM_FILE" "$expect" <<'PY'
import json, re, sys

def emit(name, cond):
    print("%s=%s" % (name, "1" if cond else "0"))

def fail():
    for name in ("SSE_SESSION", "SSE_META", "SSE_DONE", "SSE_END", "SSE_SANFANG", "SSE_ANSWER", "SSE_CONSISTENT", "SSE_TOOL_HIT"):
        emit(name, False)
    emit("SSE_ERROR", True)
    emit("SSE_ZILIAO", True)
    print("SSE_SID=0")
    print("SSE_MODE=bad")

try:
    path = sys.argv[1]
    expect = sys.argv[2] if len(sys.argv) > 2 else ""
    raw = open(path, encoding="utf-8", errors="replace").read()
    events = []
    done_line = False
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            done_line = True
            continue
        if payload.startswith("{"):
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                pass
    sid = ""
    mode = ""
    tools = set()
    answer = ""
    deltas = []
    sanfang = False
    for event in events:
        if event.get("type") == "session" and str(event.get("session_id") or "").isdigit():
            sid = str(event.get("session_id"))
        if event.get("type") == "meta" and event.get("mode") in ("online", "offline"):
            mode = event.get("mode")
        if event.get("type") == "tool" and event.get("name"):
            tools.add(str(event.get("name")))
        if event.get("type") == "delta":
            deltas.append(event.get("text") or "")
        items = []
        if event.get("type") == "sources":
            items = event.get("items") or []
        if event.get("type") == "done":
            answer = event.get("answer") or ""
            items = items or event.get("sources") or []
            for tool in event.get("tools") or []:
                if isinstance(tool, dict) and tool.get("name"):
                    tools.add(str(tool.get("name")))
        for item in items:
            if "三方" in str((item or {}).get("title") or ""):
                sanfang = True
    text = "".join(deltas)
    ziliao = bool(re.search(r"\[资料\s*\d|【资料\s*\d", text) or re.search(r"\[资料\s*\d|【资料\s*\d", answer))
    emit("SSE_SESSION", any(e.get("type") == "session" for e in events))
    emit("SSE_META", any(e.get("type") == "meta" for e in events))
    emit("SSE_DONE", any(e.get("type") == "done" for e in events))
    emit("SSE_END", done_line)
    emit("SSE_ERROR", any(e.get("type") == "error" for e in events))
    emit("SSE_SANFANG", sanfang)
    emit("SSE_ANSWER", bool(str(answer).strip()))
    emit("SSE_CONSISTENT", answer == text and bool(str(answer).strip()))
    emit("SSE_ZILIAO", ziliao)
    emit("SSE_TOOL_HIT", bool(expect) and expect in tools)
    print("SSE_SID=%s" % (sid if sid.isdigit() else "0"))
    print("SSE_MODE=%s" % (mode if mode in ("online", "offline") else "bad"))
except Exception:
    fail()
PY
)"
}

assert_stream() {
  local label=$1 expect_tool=$2
  [ "$HTTP" = 200 ] && ok "$label HTTP 200" || bad "$label HTTP 200"
  case "$CT" in
    *text/event-stream*) ok "$label Content-Type" ;;
    *) bad "$label Content-Type" ;;
  esac
  read_sse "$expect_tool"
  [ "$SSE_SESSION" = 1 ] && ok "$label 含 session" || bad "$label 含 session"
  [ "$SSE_META" = 1 ] && ok "$label 含 meta" || bad "$label 含 meta"
  [ "$SSE_DONE" = 1 ] && ok "$label 含 done" || bad "$label 含 done"
  [ "$SSE_END" = 1 ] && ok "$label 含 [DONE]" || bad "$label 含 [DONE]"
  [ "$SSE_ERROR" = 0 ] && ok "$label 无 error 事件" || bad "$label 无 error 事件"
  [ "$SSE_ANSWER" = 1 ] && ok "$label 回答非空" || bad "$label 回答非空"
  [ "$SSE_CONSISTENT" = 1 ] && ok "$label done 与 delta 一致" || bad "$label done 与 delta 一致"
  if [ "$SSE_MODE" = online ] || [ "$SSE_MODE" = offline ]; then
    ok "$label meta.mode=$SSE_MODE"
  else
    bad "$label meta.mode"
  fi
  [ "$SSE_ZILIAO" = 0 ] && ok "$label 引用已规范为 [n]" || bad "$label 引用已规范为 [n]"
  [ "$SSE_SID" != 0 ] && ok "$label 返回 session_id" || bad "$label 返回 session_id"
  if [ -n "$expect_tool" ]; then
    [ "$SSE_TOOL_HIT" = 1 ] && ok "$label 调用 $expect_tool" || bad "$label 调用 $expect_tool"
  fi
}

finish_session() {
  local role=$1 token=$2 other_role=$3 other_token=$4 label=$5
  local sid=$SSE_SID
  req GET "/${role}/ai/sessions?size=50" "$token"
  if [ "$HTTP" = 200 ] && [ "$(jq -r .code <<<"$BODY")" = 200 ] \
    && [ "$(jq --argjson id "$sid" '[.data.records[].id] | index($id) != null' <<<"$BODY")" = true ]; then
    ok "$label 会话出现在列表"
  else
    bad "$label 会话出现在列表"
  fi
  req GET "/${role}/ai/sessions/${sid}/messages" "$token"
  expect_ok "$label 消息历史"
  [ "$(jq '[.data[].msgRole] | index("user")' <<<"$BODY")" != null ] && ok "$label 含用户消息" || bad "$label 含用户消息"
  [ "$(jq '[.data[].msgRole] | index("assistant")' <<<"$BODY")" != null ] && ok "$label 含助手消息" || bad "$label 含助手消息"
  req GET "/${other_role}/ai/sessions/${sid}/messages" "$other_token"
  expect_http 404 "$label 其他角色读取 404"
  req DELETE "/${role}/ai/sessions/${sid}" "$token"
  expect_ok "$label 删除自己的会话"
  req GET "/${role}/ai/sessions/${sid}/messages" "$token"
  expect_http 404 "$label 删除后 404"
}

stream_chat /student/ai/chat/stream "$T_STU" "三方协议怎么签？"
assert_stream "学生助手" ""
[ "$SSE_SANFANG" = 1 ] && ok "学生回答引用三方资料" || bad "学生回答引用三方资料"
STU_SID=$SSE_SID
finish_session student "$T_STU" company "$T_COM" "学生"
STU_SID=""

stream_chat /company/ai/chat/stream "$T_COM" "列出我发布的职位"
assert_stream "企业助手" "list_my_jobs"
COM_SID=$SSE_SID
finish_session company "$T_COM" student "$T_STU" "企业"
COM_SID=""

stream_chat /admin/ai/chat/stream "$T_ADMIN" "哪个城市岗位最多"
assert_stream "管理员助手" "city_distribution"
ADM_SID=$SSE_SID
finish_session admin "$T_ADMIN" student "$T_STU" "管理员"
ADM_SID=""

req GET /admin/ai/knowledge/stats "$T_ADMIN"
expect_ok "知识库统计"
[ "$(jq -r '.data.chunks // 0' <<<"$BODY")" -gt 0 ] && ok "知识库切片数 > 0" || bad "知识库切片数 > 0"
req GET "/admin/ai/knowledge/search?q=$(enc "三方协议怎么签")&topK=4" "$T_ADMIN"
expect_ok "检索三方协议"
[ "$(jq -r '.data.total // 0' <<<"$BODY")" -ge 1 ] && ok "三方协议检索至少 1 条" || bad "三方协议检索至少 1 条"
[ "$(jq '[.data.results[].title // empty | select(contains("三方"))] | length' <<<"$BODY")" -ge 1 ] \
  && ok "检索结果标题含三方" || bad "检索结果标题含三方"

TITLE="相位知识${TS}"
PHRASE="相位检索标记${TS}专用句子用于向量召回"
TMP_MD=$(mktemp /tmp/rag-doc.XXXXXX.md)
cat > "$TMP_MD" <<EOF
# ${TITLE}

${PHRASE}。${PHRASE}。${PHRASE}。
EOF
HTTP=$(curl -s -m 120 -o /tmp/_body -w '%{http_code}' -X POST "$BASE/admin/ai/knowledge/upload" \
  -H "Authorization: Bearer $T_ADMIN" \
  -F "file=@${TMP_MD};filename=rag-${TS}.md;type=text/markdown" \
  -F "title=${TITLE}" \
  -F "docType=2")
BODY=$(cat /tmp/_body)
expect_ok "上传临时知识文档"
DOC_KEY=$(jq -r '.data.docKey // empty' <<<"$BODY")
[ -n "$DOC_KEY" ] && [ "$DOC_KEY" != null ] && ok "上传返回 docKey" || bad "上传返回 docKey"
req GET "/admin/ai/knowledge/documents?current=1&size=20&q=$(enc "$TITLE")" "$T_ADMIN"
expect_ok "文档列表含新标题"
[ "$(jq --arg t "$TITLE" '[.data.records[].title] | index($t) != null' <<<"$BODY")" = true ] \
  && ok "列表能看到上传文档" || bad "列表能看到上传文档"
req GET "/admin/ai/knowledge/search?q=$(enc "$PHRASE")&topK=4" "$T_ADMIN"
expect_ok "检索刚上传的文档"
[ "$(jq --arg t "$TITLE" '[.data.results[].title] | index($t) != null' <<<"$BODY")" = true ] \
  && ok "检索命中上传文档" || bad "检索命中上传文档"
req DELETE "/admin/ai/knowledge/documents?docKey=$(enc "$DOC_KEY")" "$T_ADMIN"
expect_ok "删除上传文档"
DOC_KEY=""
req GET "/admin/ai/knowledge/documents?current=1&size=20&q=$(enc "$TITLE")" "$T_ADMIN"
expect_ok "删除后再次列表"
[ "$(jq -r '.data.total // 1' <<<"$BODY")" = 0 ] && ok "列表中已无该文档" || bad "列表中已无该文档"
req GET "/admin/ai/knowledge/search?q=$(enc "$PHRASE")&topK=4" "$T_ADMIN"
expect_ok "删除后再次检索"
[ "$(jq --arg t "$TITLE" '[.data.results[] | select(.title==$t)] | length' <<<"$BODY")" = 0 ] \
  && ok "检索中已无该文档" || bad "检索中已无该文档"

summary
