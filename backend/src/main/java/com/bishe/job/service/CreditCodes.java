package com.bishe.job.service;

import com.bishe.job.common.BusinessException;
import org.springframework.util.StringUtils;

/**
 * 统一社会信用代码（GB 32100-2015）：18 位，第 18 位为校验码。
 * 字符集不含 I、O、S、V、Z。已落库的演示代码（DEMO / REAL / EXTA 等）在未改码时不重新校验。
 */
public final class CreditCodes {

    static final String CHARSET = "0123456789ABCDEFGHJKLMNPQRTUWXY";
    static final int[] WEIGHTS = {1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28};
    private static final java.util.regex.Pattern PATTERN =
            java.util.regex.Pattern.compile("^[0-9A-HJ-NPQRTUWXY]{2}\\d{6}[0-9A-HJ-NPQRTUWXY]{10}$");

    public static final String INVALID_MESSAGE =
            "统一社会信用代码须为 18 位并符合校验位规则（不含 I、O、S、V、Z）";

    private CreditCodes() {
    }

    public static String normalize(String raw) {
        return raw == null ? "" : raw.trim().toUpperCase();
    }

    public static boolean isValid(String raw) {
        String code = normalize(raw);
        if (!PATTERN.matcher(code).matches()) {
            return false;
        }
        return code.charAt(17) == checksum(code.substring(0, 17));
    }

    /** 由前 17 位计算校验位。body 须已规范化且长度为 17。 */
    public static char checksum(String body17) {
        if (body17 == null || body17.length() != 17) {
            throw new IllegalArgumentException("统一社会信用代码主体须为 17 位");
        }
        int sum = 0;
        for (int i = 0; i < 17; i++) {
            int index = CHARSET.indexOf(body17.charAt(i));
            if (index < 0) {
                throw new IllegalArgumentException("统一社会信用代码含非法字符");
            }
            sum += index * WEIGHTS[i];
        }
        int check = 31 - (sum % 31);
        if (check == 31) {
            check = 0;
        }
        return CHARSET.charAt(check);
    }

    /**
     * 由种子生成合法的 18 位代码，供测试使用。前 8 位固定为 91330100（浙江杭州登记机关样式）。
     */
    public static String generate(String seed) {
        String src = normalize(seed);
        if (!StringUtils.hasText(src)) {
            src = "0";
        }
        try {
            byte[] digest = java.security.MessageDigest.getInstance("SHA-256")
                    .digest(src.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            // SHA-256 十六进制只含 0-9A-F，均在合法字符集中；取前 9 位保证不同种子几乎必不同
            String hex = java.util.HexFormat.of().withUpperCase().formatHex(digest);
            String body = "91330100" + hex.substring(0, 9);
            return body + checksum(body);
        } catch (java.security.NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 不可用", ex);
        }
    }

    /** 已绑定到本企业的代码（含演示 DEMO/REAL/EXTA）再次提交时不强制校验格式。 */
    public static boolean requiresFormatCheck(String incoming, String alreadyStored) {
        String code = normalize(incoming);
        if (!StringUtils.hasText(code)) {
            return true;
        }
        return alreadyStored == null || !code.equals(normalize(alreadyStored));
    }

    public static String requireValid(String raw) {
        String code = normalize(raw);
        if (!isValid(code)) {
            throw new BusinessException(400, INVALID_MESSAGE);
        }
        return code;
    }

    public static String requireForUpdate(String raw, String alreadyStored) {
        String code = normalize(raw);
        if (!requiresFormatCheck(code, alreadyStored)) {
            return code;
        }
        return requireValid(code);
    }
}
