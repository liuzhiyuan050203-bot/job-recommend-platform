package com.bishe.job.service;

import com.bishe.job.common.BusinessException;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class CreditCodesTest {

    /** 公开披露的腾讯统一社会信用代码，用于核对 GB 32100 校验位。 */
    static final String TENCENT = "91440300708461136T";

    @Test
    void knownPublicCodeIsValid() {
        assertTrue(CreditCodes.isValid(TENCENT));
        assertEquals('T', CreditCodes.checksum(TENCENT.substring(0, 17)));
        assertTrue(CreditCodes.isValid(TENCENT.toLowerCase()));
    }

    @Test
    void rejectsWrongChecksumLengthAndIllegalLetters() {
        assertFalse(CreditCodes.isValid("91440300708461136A"));
        assertFalse(CreditCodes.isValid("91440300708461136"));
        assertFalse(CreditCodes.isValid("91440300708461136TT"));
        assertFalse(CreditCodes.isValid("91I40300708461136T"));
        assertFalse(CreditCodes.isValid("DEMO000000000001"));
        assertFalse(CreditCodes.isValid(""));
        assertFalse(CreditCodes.isValid(null));
    }

    @Test
    void generateProducesValidUniqueCodes() {
        String a = CreditCodes.generate("20261112111");
        String b = CreditCodes.generate("20261112112");
        assertTrue(CreditCodes.isValid(a));
        assertTrue(CreditCodes.isValid(b));
        assertEquals(18, a.length());
        assertFalse(a.equals(b));
        assertEquals("91330100", a.substring(0, 8));
        assertEquals(a, CreditCodes.requireValid(a));
    }

    @Test
    void requireValidThrowsOnBadCode() {
        BusinessException ex = assertThrows(BusinessException.class, () -> CreditCodes.requireValid("123456"));
        assertEquals(400, ex.getCode());
        assertTrue(ex.getMessage().contains("18"));
    }

    @Test
    void existingDemoCodeSkippedOnUpdateButCheckedWhenChanged() {
        assertFalse(CreditCodes.requiresFormatCheck("DEMO000000000001", "DEMO000000000001"));
        assertFalse(CreditCodes.requiresFormatCheck("demo000000000001", "DEMO000000000001"));
        assertTrue(CreditCodes.requiresFormatCheck("91440300708461136T", "DEMO000000000001"));
        assertEquals("DEMO000000000001", CreditCodes.requireForUpdate("demo000000000001", "DEMO000000000001"));
        assertEquals(TENCENT, CreditCodes.requireForUpdate(TENCENT, "DEMO000000000001"));
        assertThrows(BusinessException.class, () -> CreditCodes.requireForUpdate("91440300708461136A", "DEMO000000000001"));
    }
}
