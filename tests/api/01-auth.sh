#!/usr/bin/env bash
# Step1 认证与权限：登录、注册、401/403、当前用户、修改密码、账号状态
cd "$(dirname "$0")"; source ./lib.sh
TS=${TS:-$(date +%s)}
echo "### 01 认证与安全"

login admin admin123; T_ADMIN=$TOKEN;   expect_ok "管理员登录"; expect_jq .data.user.roleName admin "管理员 roleName=admin"
login student student123; T_STU=$TOKEN; expect_ok "学生登录";   expect_jq .data.user.roleName student "学生 roleName=student"
login company company123; T_COM=$TOKEN; expect_ok "企业登录";   expect_jq .data.user.roleName company "企业 roleName=company"
save_state T_ADMIN "$T_ADMIN"; save_state T_STU "$T_STU"; save_state T_COM "$T_COM"

login admin wrongpass; expect_fail "错误密码登录失败"
login nobody_xyz abc123; expect_fail "不存在用户登录失败"

# 注册新学生
SU="stu$TS"
fixture_user "$SU"
req POST /public/auth/register/student "" "{\"username\":\"$SU\",\"password\":\"pass123\",\"nickname\":\"测试学生$TS\",\"realName\":\"张测试\",\"gender\":1,\"education\":2,\"graduationYear\":2026,\"school\":\"测试大学\",\"major\":\"软件工程\",\"expectCity\":\"杭州\",\"expectDirection\":\"Java后端\"}"
expect_ok "学生注册"
req POST /public/auth/register/student "" "{\"username\":\"$SU\",\"password\":\"pass123\",\"nickname\":\"x\",\"realName\":\"x\",\"education\":2,\"graduationYear\":2026}"
expect_fail "重复用户名注册失败"
req POST /public/auth/register/student "" '{"username":"a","password":"1"}'
expect_http 400 "参数校验失败返回 400"
login "$SU" pass123; T_NSTU=$TOKEN; expect_ok "新学生登录"
save_state NEW_STU "$SU"; save_state T_NSTU "$T_NSTU"

# 注册新企业（待审核）
CU="com$TS"; CC=$(printf '91330%013d' "$TS")
fixture_user "$CU"
req POST /public/auth/register/company "" "{\"username\":\"$CU\",\"password\":\"pass123\",\"nickname\":\"测试企业$TS\",\"companyName\":\"测试科技有限公司$TS\",\"creditCode\":\"$CC\",\"contactName\":\"李HR\",\"contactPhone\":\"13800000000\",\"industry\":\"互联网\",\"scale\":2,\"province\":\"浙江\",\"city\":\"杭州\"}"
expect_ok "企业注册"
login "$CU" pass123; T_NCOM=$TOKEN; expect_ok "待审核企业可登录"; expect_jq .data.user.companyAuditStatus 0 "companyAuditStatus=0"
save_state NEW_COM "$CU"; save_state T_NCOM "$T_NCOM"; save_state NEW_COM_USER_ID "$(jqv .data.user.id)"
req GET /company/jobs "$T_NCOM"; expect_http 403 "待审核企业访问非资料接口 403"

# admin 注册不允许
req POST /public/auth/register/admin "" '{"username":"hacker1","password":"pass123"}'
[ "$HTTP" != 200 ] && ok "无管理员注册接口" || bad "存在管理员注册接口"

# 401 / 403
req GET /user/me;                  expect_http 401 "无 token 访问 401"
req GET /user/me "bad.token.x";    expect_http 401 "无效 token 401"
req GET /admin/users "$T_STU";     expect_http 403 "学生访问 admin 403"
req GET /company/jobs "$T_STU";    expect_http 403 "学生访问 company 403"
req GET /student/profile "$T_COM"; expect_http 403 "企业访问 student 403"
req GET /student/profile "$T_ADMIN"; expect_http 403 "管理员访问 student 403"
req GET /health;                   expect_ok "health 公开"

# 当前用户
req GET /user/me "$T_STU"; expect_ok "学生 /user/me"; expect_jq .data.username student "me.username=student"
req GET /user/me "$T_COM"; expect_ok "企业 /user/me"

# 修改密码（新学生）
req PUT /user/password "$T_NSTU" '{"oldPassword":"wrong00","newPassword":"newpass1"}'; expect_fail "旧密码错误改密失败"
req PUT /user/password "$T_NSTU" '{"oldPassword":"pass123","newPassword":"123"}'; expect_fail "新密码过短失败"
req PUT /user/password "$T_NSTU" '{"oldPassword":"pass123","newPassword":"newpass1"}'; expect_ok "修改密码"
login "$SU" pass123; expect_fail "旧密码登录失败"
login "$SU" newpass1; T_NSTU=$TOKEN; expect_ok "新密码登录"
req PUT /user/password "$T_NSTU" '{"oldPassword":"newpass1","newPassword":"pass123"}'; expect_ok "改回密码"
login "$SU" pass123; T_NSTU=$TOKEN; save_state T_NSTU "$T_NSTU"

# 禁用账号：直接改库模拟（管理员接口在 02 中测试）
if db_ping; then
  db_sql "update sys_user set status=2 where username='$SU'"
  req GET /user/me "$T_NSTU"; [ "$HTTP" = 401 ] || [ "$HTTP" = 403 ] && ok "禁用后旧 token 失效" || bad "禁用后旧 token 仍可用"
  login "$SU" pass123; expect_fail "禁用账号不能登录"
  db_sql "update sys_user set status=1 where username='$SU'"
  login "$SU" pass123; T_NSTU=$TOKEN; save_state T_NSTU "$T_NSTU"
fi
summary
