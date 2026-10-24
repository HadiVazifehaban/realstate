package com.shekarchi.auth.captcha;

import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

/** Run against a disposable Redis only; production Redis is never used by this test. */
class CaptchaChallengeStoreTest {
    private String redisUrl() {
        String url = System.getenv("SHEKARCHI_TEST_REDIS_URL");
        Assumptions.assumeTrue(url != null && !url.isBlank(), "Set SHEKARCHI_TEST_REDIS_URL to a disposable test Redis");
        return url;
    }

    private String namespace() { return "shekarchi:captcha:test:" + UUID.randomUUID(); }

    @Test
    void consumesAChallengeExactlyOnce() {
        String session = "auth-session-" + UUID.randomUUID();
        try (var store = new CaptchaChallengeStore(redisUrl(), namespace())) {
            assertTrue(store.issue(session, "198.51.100.10", "nonce:9999999999:hmac", 60, 900, 12, 60));
            var first = store.consume(session, "198.51.100.10", 900, 6, 30);
            var replay = store.consume(session, "198.51.100.10", 900, 6, 30);
            assertFalse(first.rateLimited());
            assertEquals("nonce:9999999999:hmac", first.record());
            assertNull(replay.record());
        }
    }

    @Test
    void expiresChallengesAndLimitsRepeatedSubmissions() throws InterruptedException {
        String session = "auth-session-" + UUID.randomUUID();
        try (var store = new CaptchaChallengeStore(redisUrl(), namespace())) {
            assertTrue(store.issue(session, "198.51.100.11", "expired", 1, 900, 12, 60));
            Thread.sleep(1200);
            assertNull(store.consume(session, "198.51.100.11", 900, 6, 30).record());

            String secondSession = "auth-session-" + UUID.randomUUID();
            assertTrue(store.issue(secondSession, "198.51.100.12", "fresh", 60, 900, 12, 60));
            assertFalse(store.consume(secondSession, "198.51.100.12", 900, 1, 30).rateLimited());
            assertTrue(store.consume(secondSession, "198.51.100.12", 900, 1, 30).rateLimited());
        }
    }

    @Test
    void failsClosedWhenRedisIsNotConfigured() {
        try (var store = new CaptchaChallengeStore("", namespace())) {
            assertThrows(IllegalStateException.class,
                    () -> store.issue("session", "ip", "record", 60, 900, 12, 60));
        }
    }
}
