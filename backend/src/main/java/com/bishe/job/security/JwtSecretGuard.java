package com.bishe.job.security;

import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

import java.util.Arrays;

/**
 * 生产 profile 下密钥不合格就拒绝启动，避免带着开发默认密钥上线。
 */
@Component
@RequiredArgsConstructor
public class JwtSecretGuard {

    private final Environment environment;
    private final JwtProperties jwtProperties;

    @PostConstruct
    public void verify() {
        boolean prod = Arrays.asList(environment.getActiveProfiles()).contains("prod");
        JwtSecretRules.verify(prod, jwtProperties.getSecret());
    }
}
