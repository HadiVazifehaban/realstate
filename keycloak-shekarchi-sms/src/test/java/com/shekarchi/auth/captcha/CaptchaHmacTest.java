package com.shekarchi.auth.captcha;

import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.junit.jupiter.api.Assertions.*;

class CaptchaHmacTest {
    private static final String SECRET = "captcha-unit-test-key-at-least-thirty-two-chars";

    @Test
    void signatureIsBoundToTheAuthenticationSessionAndExpires() {
        String binding = "root-session:tab";
        long expiresAt = Instant.now().getEpochSecond() + 30;
        String signature = CaptchaHmac.sign(SECRET, binding, "nonce-1", expiresAt, "42");
        String record = "nonce-1:" + expiresAt + ":" + signature;

        assertTrue(CaptchaHmac.verify(SECRET, binding, record, "42"));
        assertFalse(CaptchaHmac.verify(SECRET, "different-session", record, "42"));
        assertFalse(CaptchaHmac.verify(SECRET, binding, record, "43"));
        assertFalse(CaptchaHmac.verify(SECRET, binding, "nonce-1:1:" + signature, "42"));
    }

    @Test
    void normalizesPersianAndArabicDigitsWithoutChangingTheExpectedAnswer() {
        assertTrue(CaptchaHmac.verify(SECRET, "session", signed("123"), "۱۲۳"));
        assertTrue(CaptchaHmac.verify(SECRET, "session", signed("123"), "١٢٣"));
    }

    @Test
    void rejectsMissingAnswersAndShortSecrets() {
        assertFalse(CaptchaHmac.verify(SECRET, "session", signed("42"), null));
        assertThrows(IllegalStateException.class,
                () -> CaptchaHmac.sign("short", "session", "nonce", 1, "42"));
    }

    private String signed(String answer) {
        long expiresAt = Instant.now().getEpochSecond() + 30;
        return "nonce:" + expiresAt + ":" + CaptchaHmac.sign(SECRET, "session", "nonce", expiresAt, answer);
    }
}
