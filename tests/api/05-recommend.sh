#!/usr/bin/env bash
# Phase4 混合推荐：学生推荐（只能看自己的）、过滤已投递/下架职位、冷启动、相似职位、管理员评估。
# 离线推荐结果来自 spark_recommend（is_latest=1）；冷启动学生走 ai-service 实时推荐，ai-service 未启动时走数据库兜底。
cd "$(dirname "$0")"; source ./lib.sh
TS=${TS:-$(date +%s)}
echo "### 05 混合推荐"

skip() { echo "  [SKIP] $1"; }
ai_up() { curl -sf -m 2 -o /dev/null "http://127.0.0.1:8000/health"; }
DB() { db_sql "$1"; }

login admin admin123; T_ADMIN=$TOKEN; expect_ok "管理员登录"
login student student123; T_STU=$TOKEN; expect_ok "学生登录"
login company company123; T_COM=$TOKEN; expect_ok "企业登录"

# ---- 权限 ----
req GET /student/recommend;              expect_http 401 "未登录访问推荐 401"
req GET /student/recommend "bad.token";  expect_http 401 "无效 token 访问推荐 401"
req GET /student/recommend "$T_COM";     expect_http 403 "企业访问学生推荐 403"
req GET /student/recommend "$T_ADMIN";   expect_http 403 "管理员访问学生推荐 403"
req GET /admin/recommend/eval "$T_STU";  expect_http 403 "学生访问推荐评估 403"
req GET /admin/recommend/stats "$T_COM"; expect_http 403 "企业访问推荐统计 403"
req POST /admin/recommend/run "$T_STU" '{}'; expect_http 403 "学生不能触发推荐任务 403"
# 推荐接口只按 token 取当前学生，传 userId 参数不会越权
req GET "/student/recommend?userId=1&user_id=1&size=50" "$T_STU"; expect_ok "附带 userId 参数仍返回自己的推荐"
IDOR_IDS=$(jq -c '[.data.records[].positionId]' <<<"$BODY")
req GET "/student/recommend?size=50" "$T_STU"
[ "$IDOR_IDS" = "$(jq -c '[.data.records[].positionId]' <<<"$BODY")" ] && ok "userId 参数被忽略" || bad "userId 参数被忽略"

# ---- 演示学生推荐 ----
req GET "/student/recommend?size=10" "$T_STU"; expect_ok "学生推荐列表"
TOTAL=$(jqv .data.total)
[ "${TOTAL:-0}" -gt 0 ] && ok "推荐非空 (total=$TOTAL)" || bad "推荐非空"
[ "$(jq '.data.records | length' <<<"$BODY")" -le 10 ] && ok "分页大小生效" || bad "分页大小生效"
[ "$(jq '[.data.records[] | select((.reason // "") == "")] | length' <<<"$BODY")" = 0 ] && ok "每条推荐都有理由" || bad "每条推荐都有理由"
[ "$(jq '[.data.records[] | select(.matchScore < 0 or .matchScore > 100)] | length' <<<"$BODY")" = 0 ] && ok "匹配分在 0~100" || bad "匹配分在 0~100"
[ "$(jq '[.data.records[].rankNo] | . == sort' <<<"$BODY")" = true ] && ok "按名次排序" || bad "按名次排序"
[ "$(jq '[.data.records[].positionId] | length == (unique | length)' <<<"$BODY")" = true ] && ok "推荐职位不重复" || bad "推荐职位不重复"
REC_IDS=$(jq -r '.data.records[].positionId' <<<"$BODY")
FIRST=$(jq -r '.data.records[0].positionId' <<<"$BODY")
vis_ok=1
for id in $REC_IDS; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/public/jobs/$id")
  [ "$code" = 200 ] || vis_ok=0
done
[ "$vis_ok" = 1 ] && ok "推荐职位均为已审核且在架" || bad "推荐职位均为已审核且在架"

req GET "/student/applications?size=100" "$T_STU"
APPLIED=$(jq -c '[.data.records[].jobId]' <<<"$BODY")
req GET "/student/recommend?size=50" "$T_STU"
[ "$(jq --argjson a "$APPLIED" '[.data.records[].positionId] - ([.data.records[].positionId] - $a) | length' <<<"$BODY")" = 0 ] \
  && ok "不推荐已投递职位" || bad "不推荐已投递职位"

req GET "/student/recommend?current=2&size=5" "$T_STU"; expect_ok "推荐第二页"
[ "$(jqv .data.current)" = 2 ] && ok "页码回显" || bad "页码回显"

# ---- 下架后不再推荐 ----
OWNER=$(DB "SELECT u.username FROM job_position p JOIN ent_company c ON c.id=p.company_id JOIN sys_user u ON u.id=c.user_id WHERE p.id=${FIRST:-0} AND u.username LIKE 'demo_%'")
if [ -n "$OWNER" ]; then
  login "$OWNER" 'Demo@123'; T_OWN=$TOKEN
  req PUT "/company/jobs/$FIRST/shelf" "$T_OWN" '{"shelfStatus":0}'; expect_ok "企业下架推荐中的职位"
  req GET "/student/recommend?size=50" "$T_STU"
  [ "$(jq --argjson id "$FIRST" '[.data.records[].positionId] | index($id)' <<<"$BODY")" = null ] && ok "下架职位不再推荐" || bad "下架职位不再推荐"
  NEXT=$(jq -r '.data.records[0].positionId' <<<"$BODY")
  req GET "/public/jobs/$FIRST/similar"; expect_http 404 "下架职位相似职位 404"
  req GET "/public/jobs/$NEXT/similar?size=20"
  [ "$(jq --argjson id "$FIRST" '[.data[].id] | index($id)' <<<"$BODY")" = null ] && ok "相似职位不含下架职位" || bad "相似职位不含下架职位"
  req PUT "/company/jobs/$FIRST/shelf" "$T_OWN" '{"shelfStatus":1}'; expect_ok "恢复上架"
else
  skip "找不到推荐首位职位的演示企业账号，跳过下架过滤"
fi

# ---- 冷启动：新注册学生，无任何行为 ----
SU="cold$TS"
fixture_user "$SU"
req POST /public/auth/register/student "" "{\"username\":\"$SU\",\"password\":\"pass123\",\"nickname\":\"冷启动$TS\",\"realName\":\"冷同学\",\"gender\":1,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"计算机科学与技术\",\"expectCity\":\"北京\",\"expectDirection\":\"后端开发\"}"
expect_ok "注册冷启动学生"
login "$SU" pass123; T_COLD=$TOKEN; expect_ok "冷启动学生登录"
req GET "/student/recommend?size=10" "$T_COLD"; expect_ok "冷启动学生推荐"
[ "$(jqv .data.total)" -gt 0 ] && ok "冷启动学生有推荐 (source=$(jqv '.data.records[0].source'))" || bad "冷启动学生有推荐"
[ "$(jq '[.data.records[] | select((.reason // "") == "")] | length' <<<"$BODY")" = 0 ] && ok "冷启动推荐有理由" || bad "冷启动推荐有理由"
[ "$(jq '[.data.records[] | select(.source == "batch")] | length' <<<"$BODY")" = 0 ] && ok "冷启动不读离线批次" || bad "冷启动不读离线批次"
[ "$(jq '[.data.records[] | select(.cfScore > 0)] | length' <<<"$BODY")" = 0 ] && ok "冷启动无协同过滤分" || bad "冷启动无协同过滤分"
[ "$(jq '[.data.records[:5][] | select(.techDirection == "后端开发" or .city == "北京")] | length' <<<"$BODY")" -ge 3 ] \
  && ok "冷启动前 5 条大多符合期望方向或城市" || bad "冷启动前 5 条大多符合期望方向或城市"
# 外部来源职位（ext_ats）只能去官网投递，取首个可站内投递的推荐
COLD_FIRST=$(jq -r '[.data.records[] | select((.sourceCode // "platform") == "platform")][0].positionId' <<<"$BODY")

RESUME_JSON=$(jq -n --arg title "推荐测试简历$TS" '{title:$title, isDefault:1, educationExp:"本科", projectExp:"推荐测试", internshipExp:"无", skillDesc:"Java", selfEvaluation:"测试", attachmentUrl:""}')
req POST /student/resumes "$T_COLD" "$RESUME_JSON"; expect_ok "冷启动学生创建简历"
RESUME=$(jqv .data.id)
req POST /student/applications "$T_COLD" "{\"jobId\":$COLD_FIRST,\"resumeId\":$RESUME}"; expect_ok "投递推荐首位职位"
req GET "/student/recommend?size=50" "$T_COLD"; expect_ok "投递后重新推荐"
[ "$(jq --argjson id "$COLD_FIRST" '[.data.records[].positionId] | index($id)' <<<"$BODY")" = null ] && ok "已投递职位从推荐中移除" || bad "已投递职位从推荐中移除"

# ---- 相似职位（公开） ----
req GET "/public/jobs/$FIRST/similar?size=5"; expect_ok "相似职位"
[ "$(jq '.data | length' <<<"$BODY")" -gt 0 ] && [ "$(jq '.data | length' <<<"$BODY")" -le 5 ] && ok "相似职位条数 1~5" || bad "相似职位条数 1~5"
[ "$(jq --argjson id "$FIRST" '[.data[].id] | index($id)' <<<"$BODY")" = null ] && ok "相似职位不含自身" || bad "相似职位不含自身"
[ "$(jq '[.data[] | select(.similarity < 0 or .similarity > 100)] | length' <<<"$BODY")" = 0 ] && ok "相似度在 0~100" || bad "相似度在 0~100"
req GET "/public/jobs/99999999/similar"; expect_http 404 "不存在职位的相似职位 404"
req GET "/public/jobs/abc/similar"; expect_fail "非法职位编号"

# ---- 管理员评估 ----
req GET /admin/recommend/eval "$T_ADMIN"; expect_ok "推荐评估"
[ "$(jq '.data.metrics | length' <<<"$BODY")" -ge 12 ] && ok "评估含 4 种算法 × 3 个 K" || bad "评估含 4 种算法 × 3 个 K"
H10=$(jq -r '.data.metrics[] | select(.algo=="hybrid" and .k==10) | .ndcgAtK' <<<"$BODY")
P10=$(jq -r '.data.metrics[] | select(.algo=="popular" and .k==10) | .ndcgAtK' <<<"$BODY")
C10=$(jq -r '.data.metrics[] | select(.algo=="content" and .k==10) | .ndcgAtK' <<<"$BODY")
awk -v h="$H10" -v p="$P10" 'BEGIN{exit !(h>p)}' && ok "融合 NDCG@10 高于热门基线 ($H10 > $P10)" || bad "融合 NDCG@10 高于热门基线"
awk -v h="$H10" -v c="$C10" 'BEGIN{exit !(h>=c)}' && ok "融合 NDCG@10 不低于内容匹配 ($H10 >= $C10)" || bad "融合 NDCG@10 不低于内容匹配"
[ -n "$(jqv .data.cfMethod)" ] && [ "$(jqv .data.cfMethod)" != null ] && ok "返回协同过滤方法" || bad "返回协同过滤方法"
req GET /admin/recommend/stats "$T_ADMIN"; expect_ok "推荐统计"
[ "$(jqv .data.userCount)" -gt 0 ] && ok "覆盖学生数 > 0" || bad "覆盖学生数 > 0"
awk -v c="$(jqv .data.coverage)" 'BEGIN{exit !(c>0 && c<=1)}' && ok "目录覆盖率在 (0,1]" || bad "目录覆盖率在 (0,1]"

if ai_up; then
  req POST /admin/recommend/run "$T_ADMIN" '{}'
  REC_BATCH=""
  if [ "$(jqv .code)" = "409" ]; then
    ok "已有任务运行且排队已满时返回 409"
  else
    expect_ok "触发推荐任务"
    REC_BATCH=$(jqv .data.batchNo)
    [ -n "$REC_BATCH" ] && [ "$REC_BATCH" != null ] && ok "返回推荐批次号" || bad "返回推荐批次号"
  fi
  AI=$(curl -s -m 10 "http://127.0.0.1:8000/recommend/similar/$FIRST?top_k=3" | jq -r .code)
  [ "$AI" = 200 ] && ok "FastAPI 相似职位" || bad "FastAPI 相似职位"
  # 批次在后台子进程跑约 2~3 分钟，要等它结束：既检验批次真的成功，也避免和 06 的大模型问答同时抢 CPU
  if [ -n "$REC_BATCH" ] && [ "$REC_BATCH" != null ]; then
    echo "  等待推荐批次 $REC_BATCH 结束（最多 900s）..."
    WAIT_START=$(date +%s)
    if wait_spark_batch "$REC_BATCH" 900; then
      ok "推荐批次结束 ($(( $(date +%s) - WAIT_START ))s)"
      [ "$(jq '[.data.tasks[] | select(.taskCode == "recommend" and .status == 1)] | length' <<<"$BATCH_BODY")" -ge 1 ] \
        && ok "推荐批次状态为成功" || bad "推荐批次状态为成功: $(jq -c '[.data.tasks[] | {taskCode,status,errorMsg}]' <<<"$BATCH_BODY")"
      BODY=$BATCH_BODY
      [ "$(jq -r '.data.tasks[] | select(.taskCode == "recommend") | .paramsJson.sparkMaster // empty' <<<"$BATCH_BODY")" != "" ] \
        && ok "任务日志记录 Spark master ($(jq -r '.data.tasks[] | select(.taskCode == "recommend") | .paramsJson.sparkMaster' <<<"$BATCH_BODY"))" \
        || bad "任务日志记录 Spark master"
      req GET /admin/recommend/stats "$T_ADMIN"
      [ "$(jqv .data.batchNo)" = "$REC_BATCH" ] && ok "推荐统计切换到新批次" || bad "推荐统计切换到新批次"
    else
      bad "推荐批次 900s 内结束"
    fi
  else
    wait_spark_idle 900 || echo "  [WARN] 900s 内仍有批次在运行"
  fi
else
  skip "ai-service 未运行，跳过推荐任务触发与 FastAPI 接口"
fi

summary
