package com.shekarchi.auth.otp;

import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertThrows;

class OtpRedisStoreFailClosedTest {
    @Test
    void missingRedisConfigurationRejectsOtpIssuance() {
        OtpRedisStore.Policy policy = new OtpRedisStore.Policy(120, 3, 120, 3600, 5, 5, 15);
        try (OtpRedisStore store = new OtpRedisStore("", "shekarchi:unit")) {
            assertThrows(IllegalStateException.class, () -> store.issue(
                    "test-challenge", "989000000001", "198.51.100.1", "test-hmac",
                    Instant.now().getEpochSecond() + 120, policy));
        }
    }
}
