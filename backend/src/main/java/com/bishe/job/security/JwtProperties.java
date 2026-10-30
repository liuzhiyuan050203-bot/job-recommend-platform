package com.bishe.job.security;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * JWT 配置，对应 application.yml 的 jwt.secret 与 jwt.expire-hours。
 */
@Data
@ConfigurationProperties(prefix = "jwt")
public class JwtProperties {

    /**
     * HS256 密钥，至少 32 字节
     */
    private String secret;

    /**
     * 令牌有效期（小时）
     */
    private int expireHours = 24;
}
