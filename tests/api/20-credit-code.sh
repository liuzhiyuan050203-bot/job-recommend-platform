#!/usr/bin/env bash
# 企业注册与资质提交：统一社会信用代码须为 18 位且校验位正确；已绑定的同一代码可再提交。
# 不向演示企业写入，避免改动其审核状态。
source "$(dirname "$0")/lib.sh"
TS=${TS:-$(date +%s)}
TAIL=${TS: -10}
echo "== 20 统一社会信用代码校验 =="

req POST /public/auth/register/company "" "{\"username\":\"ccshort$TAIL\",\"password\":\"pass123\",\"nickname\":\"短代码$TAIL\",\"companyName\":\"短代码科技$TAIL\",\"creditCode\":\"913301007161158\",\"contactName\":\"李HR\",\"contactPhone\":\"13800000001\",\"industry\":\"互联网\",\"scale\":2,\"province\":\"浙江\",\"city\":\"杭州\"}"
expect_fail "15 位代码被拒"

req POST /public/auth/register/company "" "{\"username\":\"cci$TAIL\",\"password\":\"pass123\",\"nickname\":\"非法I$TAIL\",\"companyName\":\"非法I科技$TAIL\",\"creditCode\":\"91I40300708461136T\",\"contactName\":\"李HR\",\"contactPhone\":\"13800000002\",\"industry\":\"互联网\",\"scale\":2,\"province\":\"浙江\",\"city\":\"杭州\"}"
expect_fail "含 I 的代码被拒"

req POST /public/auth/register/company "" "{\"username\":\"ccbad$TAIL\",\"password\":\"pass123\",\"nickname\":\"错校验$TAIL\",\"companyName\":\"错校验科技$TAIL\",\"creditCode\":\"91440300708461136A\",\"contactName\":\"李HR\",\"contactPhone\":\"13800000003\",\"industry\":\"互联网\",\"scale\":2,\"province\":\"浙江\",\"city\":\"杭州\"}"
expect_fail "校验位错误被拒"
echo "$BODY" | grep -q "校验位\|18 位\|统一社会信用代码" && ok "错误提示提到信用代码规则" || bad "错误提示提到信用代码规则" "msg=$(echo "$BODY" | jq -r .msg 2>/dev/null)"

CU="ccok$TAIL"; fixture_user "$CU"
CC=$(credit_code "ok$TAIL")
req POST /public/auth/register/company "" "{\"username\":\"$CU\",\"password\":\"pass123\",\"nickname\":\"合法代码$TAIL\",\"companyName\":\"合法代码科技$TAIL\",\"creditCode\":\"$CC\",\"contactName\":\"李HR\",\"contactPhone\":\"13800000004\",\"industry\":\"互联网\",\"scale\":2,\"province\":\"浙江\",\"city\":\"杭州\"}"
expect_ok "校验位正确的 18 位代码可注册"

login "$CU" pass123; T_NEW=$TOKEN; expect_ok "新企业登录"
req POST /company/profile/qualification "$T_NEW" "{\"creditCode\":\"$CC\",\"licenseUrl\":\"https://example.com/license/$TAIL.png\"}"
expect_ok "用已绑定的同一代码再次提交资质"

req POST /company/profile/qualification "$T_NEW" "{\"creditCode\":\"91440300708461136A\",\"licenseUrl\":\"https://example.com/license/$TAIL.png\"}"
expect_fail "已绑定企业改成非法代码被拒"

# 演示企业只读校验，不提交资质
login company company123; T_CO=$TOKEN; expect_ok "演示企业登录"
req GET /company/profile "$T_CO"; expect_ok "读取演示企业资料"
expect_jq .data.auditStatus 1 "演示企业审核状态仍为已通过"

summary
