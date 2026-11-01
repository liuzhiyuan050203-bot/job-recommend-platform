package com.bishe.job.security;

import java.nio.charset.StandardCharsets;

/**
 * 生产环境 JWT 密钥约束。开发默认值必须与 application.yml 中的 jwt.secret 默认值一致。
 */
public final class JwtSecretRules {

    public static final String DEV_DEFAULT = "JobPlatformJwtSecretKey-2026-OK!!";

    public static final int MIN_BYTES = 32;

    private JwtSecretRules() {
    }

    /**
     * 非生产环境不检查。生产环境拒绝空值、开发默认值以及不足 32 字节的密钥。
     */
    public static void verify(boolean prod, String secret) {
        if (!prod) {
            return;
        }
        if (secret == null || secret.isBlank()) {
            throw new IllegalStateException("生产环境必须配置 JWT_SECRET");
        }
        if (DEV_DEFAULT.equals(secret)) {
            throw new IllegalStateException("生产环境不能使用开发默认 JWT_SECRET");
        }
        if (secret.getBytes(StandardCharsets.UTF_8).length < MIN_BYTES) {
            throw new IllegalStateException("生产环境 JWT_SECRET 长度至少 32 字节");
        }
    }
}
