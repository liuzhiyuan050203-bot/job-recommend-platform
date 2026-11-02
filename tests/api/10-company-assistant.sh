#!/usr/bin/env bash
# UX 审计 P0：企业招聘助手问「本周投递概况」要走本公司投递统计工具，兜底不能混入学生侧资料和话术。
# 先跑 ai-service 的 unittest（路由 + 工具 + 兜底文案），再经后端 SSE 端点做端到端核对。
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source ./lib.sh
AI=${AI:-http://127.0.0.1:8000}
ROOT=$(cd ../.. && pwd)
PY=${PY:-$ROOT/.venv/bin/python}
echo "### 10 企业招聘助手：投递统计与角色隔离"

if ! curl -sf -m 2 -o /dev/null "$AI/health"; then
  echo "  [SKIP] ai-service 未运行（${AI}/health），跳过本脚本"
  echo "== $(basename "$0"): PASS=0 FAIL=0 (SKIP)"
  echo "$(basename "$0") 0 0" >> /tmp/job-api-test-summary.txt
  exit 0
fi

# 1) 单元测试：每个用例计一次 PASS/FAIL
UT_LOG=$(mktemp /tmp/ut-company.XXXXXX)
(cd "$ROOT/ai-service" && "$PY" -m unittest -v tests.test_company_assistant) >"$UT_LOG" 2>&1
while IFS= read -r line; do
  name=$(sed -E 's/^([a-zA-Z0-9_]+) .*/\1/' <<<"$line")
  case "$line" in
    *"... ok") ok "unittest $name" ;;
    *"... FAIL"|*"... ERROR") HTTP=-; BODY=$(tail -c 300 "$UT_LOG"); bad "unittest $name" ;;
  esac
done < <(grep -E '\.\.\. (ok|FAIL|ERROR)$' "$UT_LOG")
grep -qE '^OK' "$UT_LOG" && ok "unittest 全部通过" || { HTTP=-; BODY=$(tail -c 300 "$UT_LOG"); bad "unittest 全部通过"; }
rm -f "$UT_LOG"

if ! wait_spark_idle 900; then
  echo "  [WARN] 900s 后仍有 Spark 批次在运行，继续执行"
fi

login company company123; T_COM=$TOKEN; expect_ok "企业登录"
login student student123; T_STU=$TOKEN; expect_ok "学生登录"
SIDS=()
STREAM_FILE=$(mktemp /tmp/sse-company.XXXXXX)
cleanup() {
  for sid in "${SIDS[@]}"; do
    [ "$sid" != 0 ] && curl -s -m 15 -o /dev/null -X DELETE "$BASE/company/ai/sessions/$sid" -H "Authorization: Bearer $T_COM" || true
  done
  rm -f "$STREAM_FILE"
}
trap cleanup EXIT

stream_chat() { # stream_chat PATH TOKEN QUESTION
  HTTP=$(curl -sS -N --connect-timeout 5 --max-time 180 -o "$STREAM_FILE" -w '%{http_code}' \
    -X POST "$BASE$1" -H "Authorization: Bearer $2" -H 'Content-Type: application/json' \
    -H 'Accept: text/event-stream' --data-binary "$(jq -n --arg q "$3" '{question:$q}')" || true)
  # 汇总成一个 JSON：会话、工具名与摘要、来源文档类型、最终回答
  BODY=$(python3 - "$STREAM_FILE" <<'PY'
import json, sys
out = {"sid": 0, "tools": [], "summaries": [], "docTypes": [], "titles": [], "answer": "", "done": False}
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    if not line.startswith("data:"):
        continue
    payload = line[5:].strip()
    if not payload.startswith("{"):
        continue
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        continue
    kind = event.get("type")
    if kind == "session" and str(event.get("session_id") or "").isdigit():
        out["sid"] = int(event["session_id"])
    if kind == "tool" and event.get("name"):
        out["tools"].append(event["name"])
        out["summaries"].append(str(event.get("summary") or ""))
    items = event.get("items") if kind == "sources" else (event.get("sources") if kind == "done" else None)
    for item in items or []:
        out["docTypes"].append((item or {}).get("doc_type"))
        out["titles"].append(str((item or {}).get("title") or ""))
    if kind == "done":
        out["done"] = True
        out["answer"] = event.get("answer") or ""
print(json.dumps(out, ensure_ascii=False))
PY
)
  SIDS+=("$(jq -r .sid <<<"$BODY")")
}

# 2) 「本周投递概况」：命中 application_stats，数字与本公司数据库一致，无学生话术
CID=$(db_sql "SELECT c.id FROM ent_company c JOIN sys_user u ON u.id=c.user_id WHERE u.username='company' AND c.deleted=0")
RECENT=$(db_sql "SELECT COUNT(*) FROM job_application a JOIN job_position p ON p.id=a.position_id AND p.deleted=0 WHERE a.company_id=$CID AND a.deleted=0 AND a.apply_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)")
PENDING=$(db_sql "SELECT COUNT(*) FROM job_application a JOIN job_position p ON p.id=a.position_id AND p.deleted=0 WHERE a.company_id=$CID AND a.deleted=0 AND a.status=0")
stream_chat /company/ai/chat/stream "$T_COM" "本周投递概况"
[ "$HTTP" = 200 ] && [ "$(jq -r .done <<<"$BODY")" = true ] && ok "企业问本周投递概况 SSE 完成" || bad "企业问本周投递概况 SSE 完成"
jq -e '.tools | index("application_stats")' <<<"$BODY" >/dev/null && ok "命中 application_stats 工具" || bad "命中 application_stats 工具"
jq -e --arg r "新增 $RECENT 份" --arg p "待初筛 $PENDING 份" '.summaries | any(contains($r) and contains($p))' <<<"$BODY" >/dev/null \
  && ok "工具摘要与数据库一致（近7天新增 $RECENT，待初筛 $PENDING）" || bad "工具摘要与数据库一致（期望 新增 $RECENT / 待初筛 $PENDING）"
jq -e '.answer | contains("学校就业指导中心") | not' <<<"$BODY" >/dev/null && ok "回答不含学校就业指导中心" || bad "回答不含学校就业指导中心"
jq -e '[.docTypes[] | select(. == 1 or . == 2 or . == 3 or . == 5)] | length == 0' <<<"$BODY" >/dev/null \
  && ok "统计问答未引用学生侧资料" || bad "统计问答未引用学生侧资料"

# 3) 企业泛化问题走兜底检索：只允许企业招聘须知(4)/手续 FAQ(6)
stream_chat /company/ai/chat/stream "$T_COM" "我们公司怎么提高校招效率？"
[ "$(jq -r .done <<<"$BODY")" = true ] && ok "企业泛化问题 SSE 完成" || bad "企业泛化问题 SSE 完成"
jq -e '[.docTypes[] | select(. != null and . != 4 and . != 6)] | length == 0' <<<"$BODY" >/dev/null \
  && ok "企业兜底来源只含企业招聘须知/手续FAQ" || bad "企业兜底来源只含企业招聘须知/手续FAQ"
jq -e '[.titles[] | select(test("双选会|平台使用指南|面经|求职"))] | length == 0' <<<"$BODY" >/dev/null \
  && ok "企业兜底未引用学生侧文档标题" || bad "企业兜底未引用学生侧文档标题"
jq -e '.answer | contains("学校就业指导中心") | not' <<<"$BODY" >/dev/null && ok "企业兜底回答无学生话术" || bad "企业兜底回答无学生话术"

# 4) 学生不能访问企业助手（统计工具只在企业白名单）
req POST /company/ai/chat/stream "$T_STU" '{"question":"本周投递概况"}'
expect_http 403 "学生访问企业助手 403"

summary
