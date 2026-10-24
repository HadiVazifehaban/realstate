package com.shekarchi.auth.util;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class OtpHmacUtilTest {
    @Test void bindsCodeToPhonePurposeAndChallenge() {
        String secret = "test-only-secret-which-is-at-least-32-bytes";
        String payload = "989121234567|login|challenge-a|004219|1792400000";
        String hash = OtpHmacUtil.hmac(secret, payload);
        assertTrue(OtpHmacUtil.verify(secret, payload, hash));
        assertFalse(OtpHmacUtil.verify(secret, payload.replace("login", "mfa"), hash));
        assertFalse(OtpHmacUtil.verify(secret, payload.replace("challenge-a", "challenge-b"), hash));
        assertFalse(OtpHmacUtil.verify(secret, payload.replace("989121234567", "989121234568"), hash));
        assertFalse(OtpHmacUtil.verify(secret, payload.replace("004219", "004218"), hash));
    }
}
