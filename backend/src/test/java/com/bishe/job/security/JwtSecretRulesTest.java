package com.bishe.job.security;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

class JwtSecretRulesTest {

    @Test
    void devProfileSkipsTheCheck() {
        assertDoesNotThrow(() -> JwtSecretRules.verify(false, "short"));
        assertDoesNotThrow(() -> JwtSecretRules.verify(false, null));
        assertDoesNotThrow(() -> JwtSecretRules.verify(false, JwtSecretRules.DEV_DEFAULT));
    }

    @Test
    void prodRejectsMissingSecret() {
        assertThrows(IllegalStateException.class, () -> JwtSecretRules.verify(true, null));
        assertThrows(IllegalStateException.class, () -> JwtSecretRules.verify(true, "  "));
    }

    @Test
    void prodRejectsDevDefault() {
        assertThrows(IllegalStateException.class,
                () -> JwtSecretRules.verify(true, JwtSecretRules.DEV_DEFAULT));
    }

    @Test
    void prodRejectsShortSecret() {
        assertThrows(IllegalStateException.class, () -> JwtSecretRules.verify(true, "too-short"));
    }

    @Test
    void prodAcceptsLongSecret() {
        assertDoesNotThrow(() -> JwtSecretRules.verify(true, "a-production-secret-that-is-long-enough!!"));
    }
}
