package com.bishe.job.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

/**
 * 签发与解析 JWT。授权以数据库中的当前用户为准，令牌里的角色只作辅助信息。
 */
public class JwtUtil {

    private static final String ISSUER = "job-platform";

    private final SecretKey key;
    private final long expireMillis;

    public JwtUtil(JwtProperties properties) {
        if (properties.getSecret() == null || properties.getSecret().isBlank()) {
            throw new IllegalStateException("jwt.secret 不能为空");
        }
        byte[] secretBytes = properties.getSecret().getBytes(StandardCharsets.UTF_8);
        if (secretBytes.length < 32) {
            throw new IllegalStateException("jwt.secret 长度至少 32 字节");
        }
        if (properties.getExpireHours() <= 0) {
            throw new IllegalStateException("jwt.expire-hours 必须大于 0");
        }
        this.key = Keys.hmacShaKeyFor(secretBytes);
        this.expireMillis = Math.multiplyExact((long) properties.getExpireHours(), 3_600_000L);
    }

    public String createToken(Long userId, String username, Integer role) {
        Date now = new Date();
        Date expiration = new Date(now.getTime() + expireMillis);
        return Jwts.builder()
                .issuer(ISSUER)
                .subject(String.valueOf(userId))
                .claim("username", username)
                .claim("role", role)
                .issuedAt(now)
                .expiration(expiration)
                .signWith(key)
                .compact();
    }

    public Long parseUserId(String token) {
        Claims claims = Jwts.parser()
                .verifyWith(key)
                .requireIssuer(ISSUER)
                .build()
                .parseSignedClaims(token)
                .getPayload();
        return Long.valueOf(claims.getSubject());
    }
}
