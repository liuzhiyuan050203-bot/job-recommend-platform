#!/usr/bin/env bash
# 简历上传：PDF/DOCX 解析技能、合并 stu_skill、拒绝非法文件与错误角色。
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source ./lib.sh
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PY=${PY:-$ROOT/.venv/bin/python}
TS=${TS:-$(date +%s)}
AI=${AI:-http://127.0.0.1:8000}
AI_PID=""
AI_STARTED=0
echo "### 09 简历解析"

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
  rm -f /tmp/resume-$TS.pdf /tmp/resume-$TS.docx /tmp/resume-fake-$TS.pdf \
    /tmp/resume-exe-$TS.pdf /tmp/resume-big-$TS.pdf
}
trap cleanup EXIT

ensure_ai() {
  if curl -sf -m 2 -o /dev/null "$AI/health"; then
    return 0
  fi
  echo "  启动 ai-service"
  (
    cd "$ROOT/ai-service" || exit 1
    exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  ) > /tmp/ai-service-09.log 2>&1 &
  AI_PID=$!
  AI_STARTED=1
  for _ in $(seq 1 90); do
    if curl -sf -m 2 -o /dev/null "$AI/health"; then
      return 0
    fi
    if ! kill -0 "$AI_PID" 2>/dev/null; then
      echo "  ai-service 已退出"
      tail -n 40 /tmp/ai-service-09.log || true
      return 1
    fi
    sleep 1
  done
  echo "  等待 ai-service 超时"
  tail -n 40 /tmp/ai-service-09.log || true
  return 1
}

upload() {
  local token=$1 file=$2 name=$3
  local args=(-s -m 60 -o /tmp/_body -w '%{http_code}' -X POST "$BASE/student/resume/upload" \
    -F "file=@${file};filename=${name}")
  [ -n "$token" ] && args+=(-H "Authorization: Bearer $token")
  HTTP=$(curl "${args[@]}")
  BODY=$(cat /tmp/_body)
}

has_skill() {
  local name=$1
  echo "$BODY" | jq -e --arg n "$name" '.data.skills | map(.name) | index($n) != null' >/dev/null
}

lacks_skill() {
  local name=$1
  echo "$BODY" | jq -e --arg n "$name" '[.data.skills[].name | select(. == $n)] | length == 0' >/dev/null
}

login company company123; T_COM=$TOKEN; expect_ok "企业登录"
SU="rsm$TS"
fixture_user "$SU"
req POST /public/auth/register/student "" "{\"username\":\"$SU\",\"password\":\"pass123\",\"nickname\":\"解析学生$TS\",\"realName\":\"解析同学\",\"gender\":1,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"软件工程\"}"
expect_ok "注册解析学生"
login "$SU" pass123; T_STU=$TOKEN; expect_ok "解析学生登录"

PDF=/tmp/resume-$TS.pdf
DOCX=/tmp/resume-$TS.docx
FAKE=/tmp/resume-fake-$TS.pdf
EXE=/tmp/resume-exe-$TS.pdf
BIG=/tmp/resume-big-$TS.pdf
"$PY" "$ROOT/tests/api/resume_fixture.py" pdf "$PDF" \
  "熟悉 Java、Spring Boot、MySQL、Vue 与 Docker。项目使用 MongoDB，正在 going abroad，了解 CSS。" \
  && ok "生成 PDF" || bad "生成 PDF"
"$PY" "$ROOT/tests/api/resume_fixture.py" docx "$DOCX" \
  "熟悉 Java、SpringBoot、MySQL、Vue.js 与 Docker。" \
  && ok "生成 DOCX" || bad "生成 DOCX"
printf 'this is plain text not a pdf' > "$FAKE"
printf 'MZ\x90\x00not-a-pdf' > "$EXE"
"$PY" -c "p='$BIG'; open(p,'wb').write(b'%PDF-1.4\n'+b'A'*(5*1024*1024+2048))" \
  && ok "生成超限 PDF" || bad "生成超限 PDF"

upload "" "$PDF" "resume.pdf"; expect_http 401 "未登录不能上传简历"
upload "$T_COM" "$PDF" "resume.pdf"; expect_http 403 "企业不能上传学生简历"
upload "$T_STU" "$FAKE" "notes.pdf"; expect_http 400 "txt 改名为 pdf 被拒绝"
upload "$T_STU" "$EXE" "tool.pdf"; expect_http 400 "exe 改名为 pdf 被拒绝"
upload "$T_STU" "$BIG" "huge.pdf"; expect_http 400 "超过 5MB 被拒绝"

if ! ensure_ai; then
  bad "ai-service 可用"
  summary
  exit 1
fi
ok "ai-service 可用"

HTTP=$(curl -s -m 20 -o /tmp/_body -w '%{http_code}' -X POST "$AI/api/resume/parse" \
  -F "file=@${PDF};filename=resume.pdf")
BODY=$(cat /tmp/_body)
expect_http 401 "解析接口缺少内部令牌"
HTTP=$(curl -s -m 20 -o /tmp/_body -w '%{http_code}' -X POST "$AI/api/resume/parse" \
  -H "X-Internal-Token: definitely-wrong" \
  -F "file=@${PDF};filename=resume.pdf")
BODY=$(cat /tmp/_body)
expect_http 403 "解析接口令牌错误"

upload "$T_STU" "$PDF" "resume.pdf"
expect_ok "上传 PDF 并解析"
echo "$BODY" | jq -e '.data.textPreview | contains("Java")' >/dev/null \
  && ok "PDF 预览含 Java" || bad "PDF 预览含 Java"
for name in Java MySQL Vue Docker "Spring Boot"; do
  has_skill "$name" && ok "PDF 命中 $name" || bad "PDF 命中 $name"
done
lacks_skill Go && ok "MongoDB/going 不误伤 Go" || bad "MongoDB/going 不误伤 Go"
lacks_skill JavaScript && ok "不把 Java 认成 JavaScript" || bad "不把 Java 认成 JavaScript"
lacks_skill SQL && ok "MySQL 不误伤 SQL" || bad "MySQL 不误伤 SQL"
lacks_skill "C++" && ok "CSS 不误伤 C++" || bad "CSS 不误伤 C++"
echo "$BODY" | jq -e '.data.skills[] | select(.name=="Java") | (.evidence | length) > 0' >/dev/null \
  && ok "Java 带证据片段" || bad "Java 带证据片段"
JAVA_ID=$(echo "$BODY" | jq -r '.data.skills[] | select(.name=="Java") | .tagId')
IDS=$(echo "$BODY" | jq -c '[.data.skills[].tagId]')
[ -n "$JAVA_ID" ] && [ "$JAVA_ID" != null ] && ok "解析返回 Java 标签编号" || bad "解析返回 Java 标签编号"

req POST /student/skills "$T_STU" "{\"skillTagId\":$JAVA_ID,\"proficiency\":5}"
expect_ok "预先把 Java 标成 5 星"
HTTP=$(curl -s -m 90 -o /tmp/_body -w '%{http_code}' -X POST "$BASE/student/resume/skills" \
  -H "Authorization: Bearer $T_STU" -H 'Content-Type: application/json' \
  --data-raw "{\"tagIds\":$IDS}")
BODY=$(cat /tmp/_body)
expect_ok "合并解析出的技能"
req GET /student/skills "$T_STU"; expect_ok "读取合并后的技能"
echo "$BODY" | jq -e --argjson id "$JAVA_ID" '.data[] | select(.tagId==$id) | .proficiency == 5' >/dev/null \
  && ok "已有 Java 熟练度保持 5 星" || bad "已有 Java 熟练度保持 5 星"
echo "$BODY" | jq -e '[.data[] | select(.tagName=="Java")] | length == 1' >/dev/null \
  && ok "Java 没有重复行" || bad "Java 没有重复行"
echo "$BODY" | jq -e '.data[] | select(.tagName=="MySQL") | .proficiency == 3' >/dev/null \
  && ok "新技能 MySQL 写入且默认 3 星" || bad "新技能 MySQL 写入且默认 3 星"
for name in Vue Docker "Spring Boot"; do
  echo "$BODY" | jq -e --arg n "$name" '.data | map(.tagName) | index($n) != null' >/dev/null \
    && ok "档案含 $name" || bad "档案含 $name"
done

HTTP=$(curl -s -m 90 -o /tmp/_body -w '%{http_code}' -X POST "$BASE/student/resume/skills" \
  -H "Authorization: Bearer $T_STU" -H 'Content-Type: application/json' \
  --data-raw "{\"tagIds\":$IDS}")
BODY=$(cat /tmp/_body)
expect_ok "重复合并不报错"
req GET /student/skills "$T_STU"
echo "$BODY" | jq -e --argjson id "$JAVA_ID" '[.data[] | select(.tagId==$id)] | length == 1' >/dev/null \
  && ok "重复合并后 Java 仍只有一行" || bad "重复合并后 Java 仍只有一行"
echo "$BODY" | jq -e --argjson id "$JAVA_ID" '.data[] | select(.tagId==$id) | .proficiency == 5' >/dev/null \
  && ok "重复合并不改熟练度" || bad "重复合并不改熟练度"

upload "$T_STU" "$DOCX" "resume.docx"
expect_ok "上传 DOCX 并解析"
for name in Java MySQL Vue Docker "Spring Boot"; do
  has_skill "$name" && ok "DOCX 命中 $name" || bad "DOCX 命中 $name"
done
echo "$BODY" | jq -e '.data.textPreview | contains("Java")' >/dev/null \
  && ok "DOCX 预览含 Java" || bad "DOCX 预览含 Java"

HTTP=$(curl -s -m 20 -o /tmp/_body -w '%{http_code}' -X POST "$BASE/student/resume/skills" \
  -H 'Content-Type: application/json' --data-raw "{\"tagIds\":$IDS}")
BODY=$(cat /tmp/_body)
expect_http 401 "未登录不能合并技能"
HTTP=$(curl -s -m 20 -o /tmp/_body -w '%{http_code}' -X POST "$BASE/student/resume/skills" \
  -H "Authorization: Bearer $T_COM" -H 'Content-Type: application/json' \
  --data-raw "{\"tagIds\":$IDS}")
BODY=$(cat /tmp/_body)
expect_http 403 "企业不能合并学生技能"

summary
