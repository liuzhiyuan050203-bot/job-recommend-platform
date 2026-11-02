#!/usr/bin/env bash
# P1-5：PDF 合并技能同步到默认在线简历；投递弹窗过滤测试简历并预览命中技能
source "$(dirname "$0")/lib.sh"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY=${PY:-"$ROOT/.venv/bin/python"}
TS=${TS:-$(date +%s)}
echo "== 15 PDF 技能同步默认简历与投递预览 =="

if (cd "$ROOT/backend" && mvn -q test -Dtest=ResumeSkillSyncTest -Dsurefire.failIfNoSpecifiedTests=false >/tmp/resume-skill-sync-test.log 2>&1); then
  ok "JUnit ResumeSkillSyncTest 通过"
else
  bad "JUnit ResumeSkillSyncTest" "$(grep -E 'Tests run|FAIL|expected' /tmp/resume-skill-sync-test.log | head -5)"
fi

# ---- 前端选取与技能预览工具 ----
if command -v node >/dev/null; then
  OUT=$(cd "$ROOT/frontend" && node --input-type=module -e "
import { isTestResumeTitle, pickApplyResumes, preferredApplyResume, mergePreviewSkills } from './src/utils/resumePick.js'
const list=[
  {id:1,title:'UX-IDOR-勿用',isDefault:1,updateTime:'2026-03-01'},
  {id:2,title:'推荐测试简历1',isDefault:0},
  {id:3,title:'陈晓-校招简历',isDefault:0,updateTime:'2026-01-01',skillDesc:'Spark 入门'},
  {id:4,title:'备用简历',isDefault:1,updateTime:'2026-02-01'}
]
if (!isTestResumeTitle('UX-IDOR-勿用') || isTestResumeTitle('陈晓-校招简历')) { console.log('TITLE_FAIL'); process.exit(0) }
const ids = pickApplyResumes(list).map(r=>r.id).join(',')
const pref = preferredApplyResume(list)?.id
const preview = mergePreviewSkills([{tagName:'Java',proficiency:5}], 'Spark 入门、Vue', ['Java','MySQL'])
const hit = preview.filter(s=>s.matched).map(s=>s.name).join(',')
const names = preview.map(s=>s.name).join(',')
console.log(['OK', ids, pref, hit, names].join('|'))
" 2>&1)
  IFS='|' read -r ST IDS PREF HIT NAMES <<<"$OUT"
  [ "$ST" = OK ] && [ "$IDS" = "4,3" ] && [ "$PREF" = 3 ] && ok "投递简历选取：过滤测试并优先校招" || bad "投递简历选取" "$OUT"
  [ "$HIT" = Java ] && [[ "$NAMES" == *Java* && "$NAMES" == *Spark* && "$NAMES" == *Vue* ]] && ok "技能预览合并档案与简历并标命中" || bad "技能预览" "$OUT"
fi

# ---- 后端：无简历学生合并 PDF 技能后自动建校招简历并写入 skillDesc ----
SU="pdfsync$TS"
fixture_user "$SU"
req POST /public/auth/register/student "" "{\"username\":\"$SU\",\"password\":\"pass123\",\"nickname\":\"同步同学\",\"realName\":\"同步同学\",\"gender\":1,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"软件工程\"}"
expect_ok "注册学生"
login "$SU" pass123; T_STU=$TOKEN; expect_ok "学生登录"

# 先塞一份测试简历，确认不会被当作默认同步目标
req POST /student/resumes "$T_STU" "$(jq -n '{title:"UX-IDOR-污染简历",isDefault:1,educationExp:"",projectExp:"",internshipExp:"",skillDesc:"旧测试",selfEvaluation:"",attachmentUrl:""}')"
expect_ok "创建测试污染简历"
TEST_RID=$(jqv .data.id); fixture_resume "$TEST_RID"

PDF=/tmp/resume-sync-$TS.pdf
"$PY" "$ROOT/tests/api/resume_fixture.py" pdf "$PDF" \
  "姓名：同步同学 掌握 Java、Spring Boot、MySQL、Vue、Docker 后端开发经验"
upload() {
  local token=$1 file=$2 name=$3
  HTTP=$(curl -s -m 60 -o /tmp/_body -w '%{http_code}' -X POST "$BASE/student/resume/upload" \
    -H "Authorization: Bearer $token" -F "file=@${file};filename=${name}")
  BODY=$(cat /tmp/_body)
}
upload "$T_STU" "$PDF" "resume.pdf"; expect_ok "上传 PDF 解析"
IDS=$(jq -c '[.data.skills[].tagId]' <<<"$BODY")
[ "$(jq '.data.skills|length' <<<"$BODY")" -ge 3 ] && ok "解析出多项技能" || bad "解析出多项技能" "$(jq -c .data.skills <<<"$BODY")"

HTTP=$(curl -s -m 90 -o /tmp/_body -w '%{http_code}' -X POST "$BASE/student/resume/skills" \
  -H "Authorization: Bearer $T_STU" -H 'Content-Type: application/json' --data-raw "{\"tagIds\":$IDS}")
BODY=$(cat /tmp/_body); expect_ok "合并解析技能到档案"

req GET /student/resumes "$T_STU"; expect_ok "简历列表"
# 应新建或提升「同步同学-校招简历」，测试简历不再是唯一默认
CAMPUS=$(jq -c '.data[] | select(.title|test("校招简历"))' <<<"$BODY")
[ -n "$CAMPUS" ] && [ "$CAMPUS" != null ] && ok "存在校招简历：$(jq -r .title <<<"$CAMPUS")" || bad "存在校招简历" "$(jq -c '[.data[].title]' <<<"$BODY")"
[ "$(jq -r .isDefault <<<"$CAMPUS")" = 1 ] && ok "校招简历为默认" || bad "校招简历为默认" "$CAMPUS"
DESC=$(jq -r .skillDesc <<<"$CAMPUS")
for name in Java "Spring Boot" MySQL Vue Docker; do
  echo "$DESC" | grep -q "$name" && ok "校招简历 skillDesc 含 $name" || bad "校招简历 skillDesc 含 $name" "$DESC"
done
# 测试简历的 skillDesc 不应被改成合并结果（仍是「旧测试」或保持原样）
TEST_DESC=$(jq -r --argjson id "$TEST_RID" '.data[] | select(.id==$id) | .skillDesc' <<<"$BODY")
[ "$TEST_DESC" = "旧测试" ] && ok "测试污染简历 skillDesc 未被同步改写" || bad "测试污染简历未被改写" "$TEST_DESC"

# 演示账号：已有「陈晓-校招简历」时合并只追加 skillDesc
login student student123; T_DEMO=$TOKEN
BEFORE=$(db_sql "SELECT skill_desc FROM stu_resume r JOIN sys_user u ON u.id=r.user_id WHERE u.username='student' AND r.deleted=0 AND r.is_default=1 LIMIT 1")
req GET /student/skills "$T_DEMO"; expect_ok "演示学生技能"
# 取一个档案里可能还没有的冷门标签：若都有则用 Redis
TAG=$(db_sql "SELECT t.id FROM skill_tag t WHERE t.deleted=0 AND t.status=1 AND t.name='Redis' LIMIT 1")
req POST /student/resume/skills "$T_DEMO" "{\"tagIds\":[$TAG]}"; expect_ok "演示学生合并 Redis"
req GET /student/resumes "$T_DEMO"
DEMO_DESC=$(jq -r '.data[] | select(.isDefault==1) | .skillDesc' <<<"$BODY")
echo "$DEMO_DESC" | grep -q Redis && ok "演示默认简历 skillDesc 追加 Redis" || bad "演示默认简历追加 Redis" "$DEMO_DESC"
# 标题仍是校招简历
jq -e '.data[] | select(.isDefault==1) | .title | test("校招")' <<<"$BODY" >/dev/null && ok "演示默认仍是校招简历" || bad "演示默认仍是校招简历"

# 前端页面已接好
grep -q "preferredApplyResume" "$ROOT/frontend/src/views/student/JobDetail.vue" \
  && grep -q "previewSkills" "$ROOT/frontend/src/views/student/JobDetail.vue" \
  && grep -q "syncSkillsToDefaultResume\|ResumeSkillSync" "$ROOT/backend/src/main/java/com/bishe/job/service/impl/ResumeFileServiceImpl.java" \
  && ok "前后端已接入同步与投递预览" || bad "前后端接入检查"

summary
