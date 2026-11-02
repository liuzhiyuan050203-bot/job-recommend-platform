#!/usr/bin/env bash
# P1-1：推荐按求职方向加权、冲突方向降权，推荐理由如实且相邻不重复
source "$(dirname "$0")/lib.sh"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$ROOT/.venv/bin/python"
TS=${TS:-$(date +%s)}
echo "== 12 推荐方向与理由 =="

if (cd "$ROOT/ai-service" && "$PY" -m unittest tests.test_recommend_direction >/tmp/test_recommend_direction.log 2>&1); then
  ok "unittest test_recommend_direction 通过"
else
  bad "unittest test_recommend_direction" "$(tail -20 /tmp/test_recommend_direction.log)"
fi

# 后端方向之外、也不算相近的方向（与 recommend_eval.DIRECTION_NEAR 一致）
FAR_FOR_BACKEND='["前端开发","移动开发","算法工程","人工智能","嵌入式开发","产品经理","UI设计"]'

# ---- 真实职位的错误默认标签已修正 ----
N=$(db_sql "SELECT COUNT(DISTINCT p.id) FROM job_position p JOIN ent_company c ON c.id=p.company_id JOIN sys_user u ON u.id=c.user_id
  JOIN job_position_tag pt ON pt.position_id=p.id AND pt.deleted=0 JOIN skill_tag t ON t.id=pt.tag_id
  WHERE p.deleted=0 AND u.username LIKE 'real\\_%' AND p.tech_direction IN ('产品经理','UI设计') AND t.name IN ('Java','Spring Boot','MySQL')")
[ "$N" = 0 ] && ok "运营/设计类真实职位不再挂 Java/Spring Boot/MySQL" || bad "运营/设计类真实职位不再挂 Java/Spring Boot/MySQL" "count=$N"

# ---- 演示学生（期望后端开发）离线批次 ----
login student student123; T_STU=$TOKEN; expect_ok "演示学生登录"
req GET "/student/recommend?size=20" "$T_STU"; expect_ok "演示学生推荐"
FAR=$(jq --argjson far "$FAR_FOR_BACKEND" '[.data.records[] | select(.techDirection as $d | $far | index($d))] | length' <<<"$BODY")
[ "$FAR" = 0 ] && ok "演示学生 Top20 没有冲突方向职位" || bad "演示学生 Top20 没有冲突方向职位" "far=$FAR"
DUP=$(jq '[.data.records | . as $r | range(1; length) | select($r[.].reason == $r[.-1].reason)] | length' <<<"$BODY")
[ "$DUP" = 0 ] && ok "相邻推荐理由不重复" || bad "相邻推荐理由不重复" "dup=$DUP"
OLD=$(jq '[.data.records[] | select(.reason | test("技能匹配度"))] | length' <<<"$BODY")
[ "$OLD" = 0 ] && ok "理由不再用余弦百分比「技能匹配度 n%」" || bad "理由不再用余弦百分比" "old=$OLD"
DIST=$(jq '[.data.records[].reason] | unique | length' <<<"$BODY")
[ "$DIST" -ge 15 ] && ok "20 条推荐理由至少 15 种 ($DIST)" || bad "20 条推荐理由至少 15 种" "distinct=$DIST"

# 理由里提到的命中技能都必须是职位标签，也必须是学生技能
req GET /student/skills "$T_STU"; MY_SKILLS=$(jq -c '[.data[] | (.tagName // .name)]' <<<"$BODY")
req GET "/student/recommend?size=20" "$T_STU"
LIE=$(jq --argjson mine "$MY_SKILLS" '[.data.records[] | . as $r
  | (($r.reason | capture("(已掌握 [0-9]+ 项：|你的 |技能对口：)(?<s>[^（，；：]+)")?) // {s:""}).s | sub(" 正是.*$"; "")
  | split("、") | map(select(length > 0)) | map(. as $s | select((($r.tagNames // []) | index([$s])) == null or ($mine | index([$s])) == null))
  | select(length > 0)] | length' <<<"$BODY")
CHECKED=$(jq '[.data.records[] | select(.reason | test("已掌握 [0-9]+ 项：|你的 |技能对口："))] | length' <<<"$BODY")
[ "$CHECKED" -ge 5 ] && ok "多数理由写出了具体命中技能 ($CHECKED/20)" || bad "多数理由写出了具体命中技能" "$CHECKED"
[ "$LIE" = 0 ] && ok "理由中的命中技能同时属于职位标签和学生技能" || bad "理由中的命中技能同时属于职位标签和学生技能" "bad=$LIE"

# ---- 自由填写的方向「Java后端开发」也能对上（实时推荐路径） ----
SU="dirjava$TS"
fixture_user "$SU"
req POST /public/auth/register/student "" "{\"username\":\"$SU\",\"password\":\"pass123\",\"nickname\":\"方向测试$TS\",\"realName\":\"方同学\",\"gender\":1,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"软件工程\",\"expectCity\":\"杭州\",\"expectDirection\":\"Java后端开发\"}"
expect_ok "注册期望方向为「Java后端开发」的学生"
login "$SU" pass123; T_NEW=$TOKEN; expect_ok "新学生登录"
for TAG in 1 2 3; do req POST /student/skills "$T_NEW" "{\"skillTagId\":$TAG,\"proficiency\":4}" >/dev/null; done
req GET "/student/recommend?size=20" "$T_NEW"; expect_ok "新学生推荐"
SRC=$(jqv '.data.records[0].source')
[ "$SRC" != batch ] && ok "新学生走实时推荐 (source=$SRC)" || bad "新学生走实时推荐" "source=$SRC"
TOP5=$(jq '[.data.records[:5][] | select(.techDirection == "后端开发")] | length' <<<"$BODY")
[ "$TOP5" = 5 ] && ok "「Java后端开发」前 5 条都是后端开发" || bad "「Java后端开发」前 5 条都是后端开发" "$(jq -c '[.data.records[:5][].techDirection]' <<<"$BODY")"
FAR=$(jq --argjson far "$FAR_FOR_BACKEND" '[.data.records[] | select(.techDirection as $d | $far | index($d))] | length' <<<"$BODY")
[ "$FAR" = 0 ] && ok "「Java后端开发」Top20 没有冲突方向职位" || bad "「Java后端开发」Top20 没有冲突方向职位" "far=$FAR"
DIRTXT=$(jq '[.data.records[:5][] | select(.reason | test("求职方向一致|期望的后端开发方向|方向对口"))] | length' <<<"$BODY")
[ "$DIRTXT" -ge 3 ] && ok "理由说明了方向一致 ($DIRTXT/5)" || bad "理由说明了方向一致" "$DIRTXT"
FAKE=$(jq '[.data.records[] | select(((.tagNames // []) | map(select(. == "Java" or . == "Spring Boot" or . == "MySQL")) | length) == 0)
  | select(.reason | test("已掌握|正是该岗位要求|技能对口"))] | length' <<<"$BODY")
[ "$FAKE" = 0 ] && ok "没有技能交集的职位不写技能命中" || bad "没有技能交集的职位不写技能命中" "fake=$FAKE"
DUP=$(jq '[.data.records | . as $r | range(1; length) | select($r[.].reason == $r[.-1].reason)] | length' <<<"$BODY")
[ "$DUP" = 0 ] && ok "实时推荐相邻理由不重复" || bad "实时推荐相邻理由不重复" "dup=$DUP"

# ---- 离线批次整体：融合 Top10 中与期望方向冲突的职位占比 ----
RATE=$(cd "$ROOT/ai-service" && DB_HOST="$DB_HOST" DB_PORT="$DB_PORT" DB_USER="$DB_USER" DB_PASS="$DB_PASS" DB_NAME="$DB_NAME" "$PY" - <<'PYEOF'
import os
import sys
sys.path.insert(0, ".")
import pymysql
from app.spark.recommend_eval import direction_relation
conn = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]), user=os.environ["DB_USER"],
                       password=os.environ["DB_PASS"], database=os.environ["DB_NAME"], charset="utf8mb4")
with conn.cursor() as cur:
    cur.execute("""SELECT s.expect_direction, p.tech_direction FROM spark_recommend sp
        JOIN job_position p ON p.id = sp.position_id JOIN stu_profile s ON s.user_id = sp.user_id AND s.deleted = 0
        WHERE sp.is_latest = 1 AND sp.deleted = 0 AND sp.algo = 3 AND sp.rank_no <= 10""")
    rows = cur.fetchall()
far = sum(1 for u, j in rows if direction_relation(u, j) == "far")
print(f"{far / max(1, len(rows)):.4f}")
PYEOF
)
awk -v r="$RATE" 'BEGIN{exit !(r <= 0.01)}' && ok "离线融合 Top10 冲突方向占比 ≤1% ($RATE)" || bad "离线融合 Top10 冲突方向占比 ≤1%" "$RATE"

summary
