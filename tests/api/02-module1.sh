#!/usr/bin/env bash
# Step2 模块一：公共内容、学生档案与社区、企业资料审核、管理员字典与账号，以及越权与分页
cd "$(dirname "$0")"
source ./lib.sh
TS=$(date +%s%N)
TAIL=${TS: -12}
echo "### 02 模块一"

no_password() {
  local hit
  hit=$(echo "$BODY" | jq -r 'paths | map(tostring) | join(".")' 2>/dev/null | grep -i password || true)
  [ -z "$hit" ] && ok "$1" || bad "$1: 出现 $hit"
}
expect_denied() {
  { [ "$HTTP" = 403 ] || [ "$HTTP" = 404 ]; } && ok "$1" || bad "$1: 期望 403 或 404"
}
enc() { jq -rn --arg t "$1" '$t|@uri'; }
absent() {
  echo "$BODY" | jq -e --arg t "$1" '[.data.records[]? | select(.title==$t)] | length == 0' >/dev/null \
    && ok "$2" || bad "$2"
}
present() {
  echo "$BODY" | jq -e --arg t "$1" '[.data.records[]? | select(.title==$t)] | length > 0' >/dev/null \
    && ok "$2" || bad "$2"
}

login admin admin123; T_ADMIN=$TOKEN; expect_ok "管理员登录"
no_password "登录响应不含 password"
req GET /user/me "$T_ADMIN"; expect_ok "管理员 /user/me"
ADMIN_ID=$(jqv .data.id)
no_password "当前用户不含 password"

login student student123; T_DEMO_STU=$TOKEN; expect_ok "演示学生登录"
login company company123; T_DEMO_COM=$TOKEN; expect_ok "演示企业登录"
req GET /company/applications/1 "$T_DEMO_COM"; expect_ok "企业候选人详情"
no_password "候选人详情不含 password"

# ---------- 公共内容 ----------
req GET /public/banners; expect_ok "轮播图列表"
echo "$BODY" | jq -e '.data | length >= 1' >/dev/null && ok "轮播图至少一条" || bad "轮播图至少一条"
req GET /public/articles; expect_ok "文章列表"
echo "$BODY" | jq -e '.data | has("records") and has("total") and has("current") and has("size")' >/dev/null \
  && ok "文章分页字段齐全" || bad "文章分页字段齐全"
req GET /public/articles/1; expect_ok "已发布文章详情"
V1=$(jqv .data.viewCount)
req GET /public/articles/1; expect_ok "再次查看文章"
V2=$(jqv .data.viewCount)
[ "$V2" -gt "$V1" ] && ok "文章浏览数 +1 ($V1 -> $V2)" || bad "文章浏览数 +1: $V1 -> $V2"
req GET /public/articles/99999999; expect_http 404 "不存在的文章 404"

req GET /public/categories; expect_ok "职位分类树"
echo "$BODY" | jq -e '[.data[] | select(.name=="技术研发") | .children | length] | .[0] > 0' >/dev/null \
  && ok "分类树包含子节点" || bad "分类树包含子节点"
req GET "/public/skill-tags?direction=%E5%90%8E%E7%AB%AF%E5%BC%80%E5%8F%91"; expect_ok "技能标签"
echo "$BODY" | jq -e '[.data[] | select(.name=="Java")] | length == 1' >/dev/null \
  && ok "后端方向含 Java" || bad "后端方向含 Java"
SEED_POST=$(enc "星澜科技 Java 后端一面准备记录")
req GET "/public/posts?keyword=$SEED_POST"; expect_ok "已审核帖子列表"
present "星澜科技 Java 后端一面准备记录" "公开列表能看到种子帖"
req GET /public/posts/1; expect_ok "帖子详情"

req GET "/public/articles?size=10000"; expect_ok "文章超大分页"
SZ=$(jqv .data.size)
[ "$SZ" -le 100 ] && [ "$SZ" -ge 1 ] && ok "文章分页 size=$SZ <= 100" || bad "文章分页 size=$SZ 未被限制"
req GET "/public/posts?size=500"; expect_ok "帖子超大分页"
SZ=$(jqv .data.size)
[ "$SZ" -le 100 ] && ok "帖子分页 size=$SZ <= 100" || bad "帖子分页 size=$SZ 未被限制"

# ---------- 注册测试账号 ----------
SU1="m1a$TAIL"; SU2="m1b$TAIL"
fixture_user "$SU1"; fixture_user "$SU2"
req POST /public/auth/register/student "" "{\"username\":\"$SU1\",\"password\":\"pass123\",\"nickname\":\"模块一学生$TAIL\",\"realName\":\"模块一同学\",\"gender\":1,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"软件工程\"}"
expect_ok "注册学生甲"
login "$SU1" pass123; T_STU1=$TOKEN; expect_ok "学生甲登录"
req POST /public/auth/register/student "" "{\"username\":\"$SU2\",\"password\":\"pass123\",\"nickname\":\"模块一学生乙$TAIL\",\"realName\":\"越权同学\",\"gender\":2,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"软件工程\"}"
expect_ok "注册学生乙"
STU2_ID=$(jqv .data.id)
login "$SU2" pass123; T_STU2=$TOKEN; expect_ok "学生乙登录"

CU1="m1c$TAIL"; CU2="m1d$TAIL"
fixture_user "$CU1"; fixture_user "$CU2"
CC1=$(credit_code "m1c$TAIL"); CC2=$(credit_code "m1d$TAIL")
req POST /public/auth/register/company "" "{\"username\":\"$CU1\",\"password\":\"pass123\",\"nickname\":\"模块一企业$TAIL\",\"companyName\":\"模块一科技$TAIL\",\"creditCode\":\"$CC1\",\"contactName\":\"李HR\",\"contactPhone\":\"138${TAIL: -8}\",\"industry\":\"互联网\",\"scale\":2,\"province\":\"浙江\",\"city\":\"杭州\"}"
expect_ok "注册待审企业甲"
COM1_ID=$(jqv .data.company.id)
login "$CU1" pass123; T_COM1=$TOKEN; expect_ok "企业甲登录"
req POST /public/auth/register/company "" "{\"username\":\"$CU2\",\"password\":\"pass123\",\"nickname\":\"驳回企业$TAIL\",\"companyName\":\"驳回科技$TAIL\",\"creditCode\":\"$CC2\",\"contactName\":\"赵HR\",\"contactPhone\":\"139${TAIL: -8}\",\"industry\":\"互联网\",\"scale\":2,\"province\":\"浙江\",\"city\":\"宁波\"}"
expect_ok "注册待审企业乙"
COM2_ID=$(jqv .data.company.id)
login "$CU2" pass123; T_COM2=$TOKEN; expect_ok "企业乙登录"

# ---------- 学生档案与技能 ----------
req GET /student/profile "$T_STU1"; expect_ok "读取学生档案"
req PUT /student/profile "$T_STU1" '{"realName":"","gender":1,"education":2,"graduationYear":2026}'
expect_http 400 "档案姓名为空 400"
LONG_NAME=$(python3 -c 'print("名"*65)')
req PUT /student/profile "$T_STU1" "{\"realName\":\"$LONG_NAME\",\"gender\":1,\"education\":2,\"graduationYear\":2026}"
expect_http 400 "档案姓名超长 400"
req PUT /student/profile "$T_STU1" '{"realName":"模块一同学","gender":1,"education":2,"graduationYear":2026,"expectSalaryMin":20000,"expectSalaryMax":8000}'
expect_http 400 "期望薪资上下限颠倒 400"
req PUT /student/profile "$T_STU1" '{"realName":"模块一同学","gender":1,"education":2,"graduationYear":2026,"school":"测试大学","major":"软件工程","expectCity":"杭州","expectSalaryMin":8000,"expectSalaryMax":15000,"expectDirection":"后端开发","selfIntro":"模块一档案"}'
expect_ok "保存学生档案"
req GET /student/profile "$T_STU1"; expect_ok "再次读取档案"
expect_jq .data.realName "模块一同学" "档案姓名已更新"
expect_jq .data.expectCity "杭州" "期望城市已更新"

req POST /student/skills "$T_STU1" '{"skillTagId":10,"proficiency":0}'; expect_http 400 "熟练度 0 非法"
req POST /student/skills "$T_STU1" '{"skillTagId":10,"proficiency":6}'; expect_http 400 "熟练度 6 非法"
req POST /student/skills "$T_STU1" '{"skillTagId":10,"proficiency":3}'; expect_ok "添加技能"
req GET /student/skills "$T_STU1"; expect_ok "技能列表"
SKILL_ID=$(echo "$BODY" | jq -r '.data[] | select(.tagId==10) | .id' | head -1)
[ -n "$SKILL_ID" ] && [ "$SKILL_ID" != null ] && ok "拿到技能编号" || bad "拿到技能编号"
req PUT "/student/skills/$SKILL_ID" "$T_STU1" '{"proficiency":4}'; expect_ok "修改熟练度"
req GET /student/skills "$T_STU1"; expect_jq '.data[] | select(.tagId==10) | .proficiency' 4 "熟练度为 4"
req PUT "/student/skills/$SKILL_ID" "$T_STU1" '{"proficiency":9}'; expect_http 400 "熟练度越界 400"
req PUT "/student/skills/$SKILL_ID" "$T_STU2" '{"proficiency":2}'; expect_denied "其他学生不能改技能"
req DELETE "/student/skills/$SKILL_ID" "$T_STU2"; expect_denied "其他学生不能删技能"
req GET /student/skills "$T_STU1"; expect_jq '.data[] | select(.tagId==10) | .proficiency' 4 "越权未改掉熟练度"
req DELETE "/student/skills/$SKILL_ID" "$T_STU1"; expect_ok "删除自己的技能"
req GET /student/skills "$T_STU1"
echo "$BODY" | jq -e '.data | map(select(.tagId==10)) | length == 0' >/dev/null && ok "技能已删除" || bad "技能已删除"

# ---------- 帖子与评论 ----------
TITLE="模块一面经$TAIL"
CMT="模块一评论$TAIL"
POST_JSON=$(jq -n --arg t "$TITLE" '{postType:1,title:$t,content:"模块一面经正文，用于接口测试。"}')
req POST /student/posts "$T_STU1" "$POST_JSON"; expect_ok "发布帖子"
req GET "/student/posts?size=50" "$T_STU1"; expect_ok "我的帖子"
echo "$BODY" | jq -e --arg t "$TITLE" '.data.records[] | select(.title==$t) | .auditStatus == 0' >/dev/null \
  && ok "新帖待审核" || bad "新帖待审核"
POST_ID=$(echo "$BODY" | jq -r --arg t "$TITLE" '.data.records[] | select(.title==$t) | .id' | head -1)
[ -n "$POST_ID" ] && [ "$POST_ID" != null ] && ok "拿到帖子编号" || bad "拿到帖子编号"
ENC_TITLE=$(enc "$TITLE")
req GET "/public/posts?keyword=$ENC_TITLE"; expect_ok "公开检索待审帖"
absent "$TITLE" "待审核帖子公开不可见"

req PUT "/admin/posts/$POST_ID/audit" "$T_ADMIN" '{"auditStatus":1,"auditRemark":"内容可用"}'
expect_ok "管理员审核通过帖子"
req GET "/public/posts?keyword=$ENC_TITLE"; expect_ok "审核后公开检索"
present "$TITLE" "审核通过后公开可见"
req GET "/public/posts/$POST_ID"; expect_ok "公开帖子详情"

req POST "/student/posts/$POST_ID/comments" "$T_STU1" "$(jq -n --arg c "$CMT" '{content:$c}')"
expect_ok "发表评论"
req GET "/public/posts/$POST_ID"
echo "$BODY" | jq -e --arg c "$CMT" '[(.data.comments // [])[] | select(.content==$c)] | length == 0' >/dev/null \
  && ok "待审核评论公开不可见" || bad "待审核评论公开不可见"
ENC_CMT=$(enc "$CMT")
req GET "/admin/comments?auditStatus=0&keyword=$ENC_CMT&size=20" "$T_ADMIN"; expect_ok "管理员查看待审评论"
CMT_ID=$(echo "$BODY" | jq -r --arg c "$CMT" '.data.records[] | select(.content==$c) | .id' | head -1)
[ -n "$CMT_ID" ] && [ "$CMT_ID" != null ] && ok "拿到评论编号" || bad "拿到评论编号"
expect_jq '.data.records[0].auditStatus' 0 "新评论待审核"
req PUT "/admin/comments/$CMT_ID/audit" "$T_ADMIN" '{"auditStatus":1,"auditRemark":"评论通过"}'
expect_ok "管理员审核评论"
req GET "/public/posts/$POST_ID"; expect_ok "审核后帖子详情"
echo "$BODY" | jq -e --arg c "$CMT" '[(.data.comments // [])[] | select(.content==$c)] | length == 1' >/dev/null \
  && ok "审核通过的评论公开可见" || bad "审核通过的评论公开可见"

UPD_JSON=$(jq -n --arg t "$TITLE" '{postType:1,title:$t,content:"修改后的面经正文。"}')
req PUT "/student/posts/$POST_ID" "$T_STU2" "$UPD_JSON"; expect_denied "其他学生不能改帖子"
req DELETE "/student/posts/$POST_ID" "$T_STU2"; expect_denied "其他学生不能删帖子"
req DELETE "/student/comments/$CMT_ID" "$T_STU2"; expect_denied "其他学生不能删评论"
req PUT "/student/posts/$POST_ID" "$T_STU1" "$UPD_JSON"; expect_ok "作者修改帖子"
req GET "/student/posts?size=50" "$T_STU1"
echo "$BODY" | jq -e --argjson id "$POST_ID" '.data.records[] | select(.id==$id) | .auditStatus == 0' >/dev/null \
  && ok "修改后重新待审核" || bad "修改后重新待审核"
req GET "/public/posts?keyword=$ENC_TITLE"
absent "$TITLE" "重新待审后公开不可见"
req DELETE "/student/comments/$CMT_ID" "$T_STU1"; expect_ok "删除自己的评论"
req DELETE "/student/posts/$POST_ID" "$T_STU1"; expect_ok "删除自己的帖子"
req GET "/public/posts/$POST_ID"; expect_http 404 "已删帖子详情 404"

# ---------- 企业资料与资质 ----------
req GET /company/profile "$T_COM1"; expect_ok "企业资料"
expect_jq .data.auditStatus 0 "新企业资质待审核"
LONG_SHORT=$(python3 -c 'print("简"*65)')
req PUT /company/profile "$T_COM1" "{\"shortName\":\"$LONG_SHORT\",\"scale\":2}"
expect_http 400 "企业简称超长 400"
req PUT /company/profile "$T_COM1" "{\"companyName\":\"模块一科技$TAIL\",\"shortName\":\"简称$TAIL\",\"industry\":\"互联网\",\"scale\":2,\"province\":\"浙江\",\"city\":\"杭州\",\"contactName\":\"李HR\",\"contactPhone\":\"138${TAIL: -8}\"}"
expect_ok "更新企业资料"
req GET /company/profile "$T_COM1"; expect_jq .data.shortName "简称$TAIL" "简称已保存"
req POST /company/profile/qualification "$T_COM1" "{\"creditCode\":\"$CC1\",\"licenseUrl\":\"/upload/license/m1-$TAIL.png\"}"
expect_ok "提交资质"
req GET /company/profile "$T_COM1"; expect_jq .data.auditStatus 0 "提交后仍待审核"
req GET /company/jobs "$T_COM1"; expect_http 403 "未过审不能访问职位"

req PUT "/admin/companies/$COM1_ID/audit" "$T_ADMIN" '{"auditStatus":1,"auditRemark":"资质齐全"}'
expect_ok "审核通过企业甲"
req GET /company/profile "$T_COM1"; expect_jq .data.auditStatus 1 "企业甲已通过"
req GET /company/jobs "$T_COM1"; expect_ok "过审企业可访问职位"

req POST /company/profile/qualification "$T_COM2" "{\"creditCode\":\"$CC2\",\"licenseUrl\":\"/upload/license/m2-$TAIL.png\"}"
expect_ok "企业乙提交资质"
req GET /company/profile "$T_COM2"; expect_jq .data.auditStatus 0 "企业乙待审核"
REJECT="材料不清晰$TAIL"
req PUT "/admin/companies/$COM2_ID/audit" "$T_ADMIN" "$(jq -n --arg r "$REJECT" '{auditStatus:2,auditRemark:$r}')"
expect_ok "驳回企业乙"
req GET /company/profile "$T_COM2"; expect_ok "读取驳回结果"
expect_jq .data.auditStatus 2 "企业乙已驳回"
expect_jq .data.auditRemark "$REJECT" "驳回意见已记录"
req GET /company/jobs "$T_COM2"; expect_http 403 "驳回企业不能访问职位"

ENC_COM=$(enc "模块一科技$TAIL")
req GET "/admin/companies?auditStatus=1&keyword=$ENC_COM&size=20" "$T_ADMIN"; expect_ok "按审核状态筛选企业"
echo "$BODY" | jq -e --argjson id "$COM1_ID" '.data.records | map(.id) | index($id) != null' >/dev/null \
  && ok "企业列表含已通过企业" || bad "企业列表含已通过企业"

# ---------- 管理员用户 ----------
req GET "/admin/users?role=1&status=1&keyword=$SU1&size=10" "$T_ADMIN"; expect_ok "按角色状态筛选用户"
echo "$BODY" | jq -e --arg u "$SU1" '.data.records | map(.username) | index($u) != null' >/dev/null \
  && ok "用户列表含学生甲" || bad "用户列表含学生甲"
no_password "用户列表不含 password"
req GET "/admin/users?size=10000" "$T_ADMIN"; expect_ok "用户超大分页"
SZ=$(jqv .data.size)
[ "$SZ" -le 100 ] && ok "用户分页 size=$SZ <= 100" || bad "用户分页 size=$SZ 未被限制"

req PUT "/admin/users/$ADMIN_ID/status" "$T_ADMIN" '{"status":2}'; expect_http 400 "不能禁用自己"
req GET /user/me "$T_ADMIN"; expect_ok "管理员账号仍然有效"
req PUT "/admin/users/$STU2_ID/status" "$T_ADMIN" '{"status":2}'; expect_ok "禁用学生乙"
req GET /user/me "$T_STU2"; expect_http 401 "禁用后旧 token 失效"
login "$SU2" pass123; expect_fail "禁用账号不能登录"
req PUT "/admin/users/$STU2_ID/status" "$T_ADMIN" '{"status":1}'; expect_ok "重新启用学生乙"
login "$SU2" pass123; T_STU2=$TOKEN; expect_ok "启用后原密码可登录"
req PUT "/admin/users/$STU2_ID/reset-password" "$T_ADMIN"; expect_ok "重置密码"
login "$SU2" pass123; expect_fail "重置后旧密码不能登录"
login "$SU2" 123456; expect_ok "重置后可用 123456 登录"

# ---------- 轮播、文章、分类、技能标签 ----------
BAN="模块一轮播$TAIL"
BAN_JSON=$(jq -n --arg t "$BAN" '{title:$t,imageUrl:"/upload/banner/m1.png",linkUrl:"/articles/m1",sortNo:80,status:1}')
req POST /admin/banners "$T_ADMIN" "$BAN_JSON"; expect_ok "新增轮播图"
req GET "/admin/banners?size=100" "$T_ADMIN"; expect_ok "轮播图管理列表"
BAN_ID=$(echo "$BODY" | jq -r --arg t "$BAN" '.data.records[] | select(.title==$t) | .id' | head -1)
[ -n "$BAN_ID" ] && [ "$BAN_ID" != null ] && ok "拿到轮播图编号" || bad "拿到轮播图编号"
req GET /public/banners
echo "$BODY" | jq -e --arg t "$BAN" '[.data[] | select(.title==$t)] | length == 1' >/dev/null \
  && ok "启用的轮播图对外可见" || bad "启用的轮播图对外可见"
BAN2="模块一轮播改$TAIL"
req PUT "/admin/banners/$BAN_ID" "$T_ADMIN" "$(jq -n --arg t "$BAN2" '{title:$t,imageUrl:"/upload/banner/m1b.png",linkUrl:"/articles/m1b",sortNo:81,status:1}')"
expect_ok "修改轮播图"
req DELETE "/admin/banners/$BAN_ID" "$T_ADMIN"; expect_ok "删除轮播图"
req GET /public/banners
echo "$BODY" | jq -e --arg t "$BAN2" '[.data[] | select(.title==$t)] | length == 0' >/dev/null \
  && ok "已删轮播图不再展示" || bad "已删轮播图不再展示"

ART="模块一公告$TAIL"
ART_JSON=$(jq -n --arg t "$ART" '{articleType:1,title:$t,summary:"模块一摘要",content:"模块一公告正文",status:0,topFlag:0}')
req POST /admin/articles "$T_ADMIN" "$ART_JSON"; expect_ok "保存草稿文章"
ENC_ART=$(enc "$ART")
req GET "/admin/articles?keyword=$ENC_ART&status=0&size=20" "$T_ADMIN"; expect_ok "草稿出现在管理列表"
ART_ID=$(echo "$BODY" | jq -r --arg t "$ART" '.data.records[] | select(.title==$t) | .id' | head -1)
[ -n "$ART_ID" ] && [ "$ART_ID" != null ] && ok "拿到文章编号" || bad "拿到文章编号"
req GET "/public/articles/$ART_ID"; expect_http 404 "未发布文章 404"
req GET "/public/articles?keyword=$ENC_ART"; absent "$ART" "草稿不在公开列表"
req PUT "/admin/articles/$ART_ID/status" "$T_ADMIN" '{"status":1}'; expect_ok "发布文章"
req GET "/public/articles?keyword=$ENC_ART"; present "$ART" "发布后公开可见"
req GET "/public/articles/$ART_ID"; expect_ok "发布后可看详情"
AV1=$(jqv .data.viewCount)
req GET "/public/articles/$ART_ID"
AV2=$(jqv .data.viewCount)
[ "$AV2" -gt "$AV1" ] && ok "新文章浏览数 +1" || bad "新文章浏览数 +1: $AV1 -> $AV2"
req PUT "/admin/articles/$ART_ID/status" "$T_ADMIN" '{"status":2}'; expect_ok "撤回文章"
req GET "/public/articles/$ART_ID"; expect_http 404 "撤回后详情 404"
req GET "/public/articles?keyword=$ENC_ART"; absent "$ART" "撤回后列表不可见"
req DELETE "/admin/articles/$ART_ID" "$T_ADMIN"; expect_ok "删除文章"

PNAME="父类$TAIL"
CNAME="子类$TAIL"
req POST /admin/categories "$T_ADMIN" "$(jq -n --arg n "$PNAME" '{name:$n,sortNo:90,status:1}')"
expect_ok "新增父分类"
req GET /admin/categories "$T_ADMIN"; expect_ok "分类管理树"
PARENT_ID=$(echo "$BODY" | jq -r --arg n "$PNAME" '.. | objects | select(.name?==$n) | .id' | head -1)
[ -n "$PARENT_ID" ] && [ "$PARENT_ID" != null ] && ok "拿到父分类编号" || bad "拿到父分类编号"
req POST /admin/categories "$T_ADMIN" "$(jq -n --arg n "$CNAME" --argjson p "$PARENT_ID" '{name:$n,parentId:$p,sortNo:1,status:1}')"
expect_ok "新增子分类"
req DELETE "/admin/categories/$PARENT_ID" "$T_ADMIN"; expect_fail "有子分类不能删除"
req DELETE /admin/categories/1 "$T_ADMIN"; expect_fail "种子父分类不能删除"
req GET /admin/categories "$T_ADMIN"
CHILD_ID=$(echo "$BODY" | jq -r --arg n "$CNAME" '.. | objects | select(.name?==$n) | .id' | head -1)
req DELETE "/admin/categories/$CHILD_ID" "$T_ADMIN"; expect_ok "删除子分类"
req DELETE "/admin/categories/$PARENT_ID" "$T_ADMIN"; expect_ok "子分类清空后可删父分类"
req GET /public/categories
echo "$BODY" | jq -e '[.data[] | select(.name=="技术研发")] | length == 1' >/dev/null \
  && ok "种子分类仍在" || bad "种子分类仍在"

TAG="测技$TAIL"
TAG2="测技改$TAIL"
req POST /admin/skill-tags "$T_ADMIN" "$(jq -n --arg n "$TAG" '{name:$n,direction:"后端开发",sortNo:60,status:1}')"
expect_ok "新增技能标签"
ENC_TAG=$(enc "$TAG")
req GET "/admin/skill-tags?keyword=$ENC_TAG&size=20" "$T_ADMIN"; expect_ok "技能标签管理列表"
TAG_ID=$(echo "$BODY" | jq -r --arg n "$TAG" '.data.records[] | select(.name==$n) | .id' | head -1)
[ -n "$TAG_ID" ] && [ "$TAG_ID" != null ] && ok "拿到技能标签编号" || bad "拿到技能标签编号"
req PUT "/admin/skill-tags/$TAG_ID" "$T_ADMIN" "$(jq -n --arg n "$TAG2" '{name:$n,direction:"前端开发",sortNo:61,status:1}')"
expect_ok "修改技能标签"
req GET "/public/skill-tags?direction=%E5%89%8D%E7%AB%AF%E5%BC%80%E5%8F%91"
echo "$BODY" | jq -e --arg n "$TAG2" '[.data[] | select(.name==$n)] | length == 1' >/dev/null \
  && ok "修改后的标签对外可见" || bad "修改后的标签对外可见"
req DELETE "/admin/skill-tags/$TAG_ID" "$T_ADMIN"; expect_ok "删除技能标签"
req GET "/public/skill-tags?direction=%E5%89%8D%E7%AB%AF%E5%BC%80%E5%8F%91"
echo "$BODY" | jq -e --arg n "$TAG2" '[.data[] | select(.name==$n)] | length == 0' >/dev/null \
  && ok "已删标签不再展示" || bad "已删标签不再展示"

# ---------- 越权与路径绕过 ----------
req GET /admin/users "$T_DEMO_STU"; expect_http 403 "学生访问 admin 403"
req GET /admin/companies "$T_DEMO_COM"; expect_http 403 "企业访问 admin 403"
req GET /company/jobs "$T_DEMO_STU"; expect_http 403 "学生访问 company 403"
req GET /company/profile "$T_DEMO_STU"; expect_http 403 "学生访问企业资料 403"
req GET /admin/users; expect_http 401 "未登录访问 admin 401"
req GET /student/profile; expect_http 401 "未登录访问 student 401"
req GET /company/jobs; expect_http 401 "未登录访问 company 401"
req GET "/%61dmin/users" "$T_DEMO_STU"; expect_http 403 "编码路径 /api/%61dmin/users 仍是 403"
req GET "/admin;x=1/users" "$T_DEMO_STU"; expect_http 403 "分号路径 /api/admin;x=1/users 仍是 403"
req GET "/%2e%2e/admin/users" "$T_DEMO_STU"; expect_http 400 "含 %2e%2e 的路径 400"
req GET "/public/%2e%2e/posts" "$T_DEMO_STU"; expect_http 400 "公开路径中的 %2e%2e 也是 400"

summary
