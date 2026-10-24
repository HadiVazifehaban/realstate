package com.shekarchi.auth.otp;

import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import io.lettuce.core.RedisClient;
import io.lettuce.core.api.StatefulRedisConnection;

import java.time.Instant;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;

/** Integration checks run only when SHEKARCHI_TEST_REDIS_URL points at a disposable test Redis. */
class OtpRedisStoreIntegrationTest {
    private OtpRedisStore store() {
        return new OtpRedisStore(redisUrl(), namespace());
    }

    private OtpRedisStore.Policy policy() { return new OtpRedisStore.Policy(120, 3, 120, 3600, 5, 5, 15); }

    private String redisUrl() {
        String url = System.getenv("SHEKARCHI_TEST_REDIS_URL");
        Assumptions.assumeTrue(url != null && !url.isBlank(), "Set SHEKARCHI_TEST_REDIS_URL for Redis integration tests");
        return url;
    }

    private String namespace() { return "shekarchi:test:" + UUID.randomUUID(); }

    private static String digest(String value) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
    }

    @Test void storesOnlyHmacAndAppliesExactOtpAndCooldownTtls() throws Exception {
        String namespace = namespace();
        String challengeId = UUID.randomUUID().toString();
        String mobile = "989000000030";
        String rawOtp = "004219";
        String storedHmac = "test-hmac-value";
        try (OtpRedisStore store = new OtpRedisStore(redisUrl(), namespace);
             RedisClient client = RedisClient.create(redisUrl());
             StatefulRedisConnection<String, String> connection = client.connect()) {
            assertEquals(OtpRedisStore.IssueStatus.OK, store.issue(challengeId, mobile, "198.51.100.30",
                    storedHmac, Instant.now().getEpochSecond() + 120, policy()).status());

            long challengeTtl = connection.sync().ttl(namespace + ":challenge:" + challengeId);
            long cooldownTtl = connection.sync().ttl(namespace + ":cooldown:" + digest(mobile));
            assertTrue(challengeTtl >= 119 && challengeTtl <= 120, "OTP challenge TTL must be 120 seconds");
            assertTrue(cooldownTtl >= 119 && cooldownTtl <= 120, "phone cooldown TTL must be 120 seconds");
            assertEquals(storedHmac, connection.sync().hget(namespace + ":challenge:" + challengeId, "hash"));
            assertNotEquals(rawOtp, connection.sync().hget(namespace + ":challenge:" + challengeId, "hash"));
        }
    }

    @Test void enforcesApprovedFivePerHourPhoneAndIpThresholds() {
        try (OtpRedisStore store = new OtpRedisStore(redisUrl(), namespace())) {
            String sharedIp = "198.51.100.31";
            for (int i = 0; i < 5; i++) {
                assertEquals(OtpRedisStore.IssueStatus.OK, store.issue(UUID.randomUUID().toString(),
                        "98900000004" + i, sharedIp, "h" + i, Instant.now().getEpochSecond() + 120, policy()).status());
            }
            assertEquals(OtpRedisStore.IssueStatus.SOFT_LIMIT, store.issue(UUID.randomUUID().toString(),
                    "989000000049", sharedIp, "h6", Instant.now().getEpochSecond() + 120, policy()).status());
        }
    }

    @Test void enforcesApprovedFivePerHourPerPhoneThreshold() throws Exception {
        String namespace = namespace();
        String mobile = "989000000045";
        String url = redisUrl();
        try (OtpRedisStore store = new OtpRedisStore(url, namespace);
             RedisClient client = RedisClient.create(url);
             StatefulRedisConnection<String, String> connection = client.connect()) {
            String cooldownKey = namespace + ":cooldown:" + digest(mobile);
            for (int i = 0; i < 5; i++) {
                if (i > 0) connection.sync().del(cooldownKey); // isolate hourly quota from resend cooldown
                assertEquals(OtpRedisStore.IssueStatus.OK, store.issue(UUID.randomUUID().toString(), mobile,
                        "198.51.100." + (70 + i), "h" + i, Instant.now().getEpochSecond() + 120, policy()).status());
            }
            connection.sync().del(cooldownKey);
            assertEquals(OtpRedisStore.IssueStatus.SOFT_LIMIT, store.issue(UUID.randomUUID().toString(), mobile,
                    "198.51.100.79", "h6", Instant.now().getEpochSecond() + 120, policy()).status());
        }
    }

    @Test void enforcesApprovedFifteenPerDayMobileLimit() throws Exception {
        String namespace = namespace();
        String mobile = "989000000050";
        String url = redisUrl();
        OtpRedisStore.Policy policy = new OtpRedisStore.Policy(120, 3, 120, 3600, 100, 100, 15);
        try (OtpRedisStore store = new OtpRedisStore(url, namespace);
             RedisClient client = RedisClient.create(url);
             StatefulRedisConnection<String, String> connection = client.connect()) {
            String cooldownKey = namespace + ":cooldown:" + digest(mobile);
            for (int i = 0; i < 15; i++) {
                if (i > 0) connection.sync().del(cooldownKey); // test-only: bypass waiting, preserve daily counter
                assertEquals(OtpRedisStore.IssueStatus.OK, store.issue(UUID.randomUUID().toString(), mobile,
                        "198.51.100.50", "h" + i, Instant.now().getEpochSecond() + 120, policy).status());
            }
            connection.sync().del(cooldownKey);
            assertEquals(OtpRedisStore.IssueStatus.DAILY_LIMIT, store.issue(UUID.randomUUID().toString(), mobile,
                    "198.51.100.50", "h16", Instant.now().getEpochSecond() + 120, policy).status());
        }
    }

    @Test void concurrentIssueRequestsAllowOnlyOneChallengeForPhone() throws Exception {
        try (OtpRedisStore store = new OtpRedisStore(redisUrl(), namespace())) {
            int count = 16;
            CountDownLatch ready = new CountDownLatch(count);
            CountDownLatch start = new CountDownLatch(1);
            AtomicInteger issued = new AtomicInteger();
            AtomicReference<Throwable> failure = new AtomicReference<>();
            Thread[] workers = new Thread[count];
            OtpRedisStore.Policy generous = new OtpRedisStore.Policy(120, 3, 120, 3600, 100, 100, 100);
            for (int i = 0; i < count; i++) {
                final int index = i;
                workers[i] = new Thread(() -> {
                    ready.countDown();
                    try {
                        start.await();
                        if (store.issue(UUID.randomUUID().toString(), "989000000060", "198.51.100.60",
                                "h" + index, Instant.now().getEpochSecond() + 120, generous).status()
                                == OtpRedisStore.IssueStatus.OK) issued.incrementAndGet();
                    } catch (Throwable e) { failure.compareAndSet(null, e); Thread.currentThread().interrupt(); }
                });
                workers[i].start();
            }
            ready.await();
            start.countDown();
            for (Thread worker : workers) worker.join();
            assertNull(failure.get(), "Concurrent issue worker failed");
            assertEquals(1, issued.get(), "Redis Lua must serialize concurrent issuance and enforce cooldown");
        }
    }

    @Test void enforcesCooldownAndSoftThresholdsAtomically() {
        try (OtpRedisStore store = store()) {
            String id = UUID.randomUUID().toString();
            assertEquals(OtpRedisStore.IssueStatus.OK,
                    store.issue(id, "989000000001", "198.51.100.10", "h1", Instant.now().getEpochSecond() + 120, policy()).status());
            assertEquals(OtpRedisStore.IssueStatus.COOLDOWN,
                    store.issue(UUID.randomUUID().toString(), "989000000001", "198.51.100.10", "h2", Instant.now().getEpochSecond() + 120, policy()).status());
        }
    }

    @Test void consumesChallengeOnceUnderConcurrentVerification() throws Exception {
        try (OtpRedisStore store = store()) {
            String id = UUID.randomUUID().toString();
            assertEquals(OtpRedisStore.IssueStatus.OK,
                    store.issue(id, "989000000002", "198.51.100.11", "hmac", Instant.now().getEpochSecond() + 120, policy()).status());
            OtpRedisStore.Challenge snapshot = store.readChallenge(id);
            assertNotNull(snapshot);
            CountDownLatch start = new CountDownLatch(1);
            AtomicInteger consumed = new AtomicInteger();
            Runnable verify = () -> {
                try {
                    start.await();
                    if (store.verify(id, snapshot, true, 3) == OtpRedisStore.VerifyResult.CONSUMED) consumed.incrementAndGet();
                } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            };
            Thread one = new Thread(verify);
            Thread two = new Thread(verify);
            one.start(); two.start(); start.countDown(); one.join(); two.join();
            assertEquals(1, consumed.get());
        }
    }

    @Test void blocksRequestsAboveTheIpSoftThreshold() {
        try (OtpRedisStore store = store()) {
            OtpRedisStore.Policy onePerIp = new OtpRedisStore.Policy(120, 3, 120, 3600, 1, 5, 15);
            assertEquals(OtpRedisStore.IssueStatus.OK,
                    store.issue(UUID.randomUUID().toString(), "989000000010", "198.51.100.20", "h1", Instant.now().getEpochSecond() + 120, onePerIp).status());
            assertEquals(OtpRedisStore.IssueStatus.SOFT_LIMIT,
                    store.issue(UUID.randomUUID().toString(), "989000000011", "198.51.100.20", "h2", Instant.now().getEpochSecond() + 120, onePerIp).status());
        }
    }

    @Test void enforcesTheHardDailyMobileLimitAfterCooldown() throws InterruptedException {
        try (OtpRedisStore store = store()) {
            OtpRedisStore.Policy onePerDay = new OtpRedisStore.Policy(120, 3, 1, 3600, 5, 5, 1);
            String mobile = "989000000021";
            assertEquals(OtpRedisStore.IssueStatus.OK,
                    store.issue(UUID.randomUUID().toString(), mobile, "198.51.100.21", "h1", Instant.now().getEpochSecond() + 120, onePerDay).status());
            Thread.sleep(1100);
            assertEquals(OtpRedisStore.IssueStatus.DAILY_LIMIT,
                    store.issue(UUID.randomUUID().toString(), mobile, "198.51.100.22", "h2", Instant.now().getEpochSecond() + 120, onePerDay).status());
        }
    }

    @Test void invalidatesAfterThreeWrongAttempts() {
        try (OtpRedisStore store = store()) {
            String id = UUID.randomUUID().toString();
            assertEquals(OtpRedisStore.IssueStatus.OK,
                    store.issue(id, "989000000003", "198.51.100.12", "hmac", Instant.now().getEpochSecond() + 120, policy()).status());
            for (int i = 0; i < 3; i++) {
                OtpRedisStore.Challenge state = store.readChallenge(id);
                assertNotNull(state);
                assertEquals(OtpRedisStore.VerifyResult.REJECTED, store.verify(id, state, false, 3));
            }
            assertNull(store.readChallenge(id));
        }
    }

    @Test void oneWrongAttemptDoesNotConsumeAStillValidChallenge() {
        try (OtpRedisStore store = store()) {
            String id = UUID.randomUUID().toString();
            assertEquals(OtpRedisStore.IssueStatus.OK,
                    store.issue(id, "989000000004", "198.51.100.14", "expected-hmac",
                            Instant.now().getEpochSecond() + 120, policy()).status());
            OtpRedisStore.Challenge first = store.readChallenge(id);
            assertNotNull(first);
            assertEquals(OtpRedisStore.VerifyResult.REJECTED, store.verify(id, first, false, 3));

            OtpRedisStore.Challenge afterWrongAttempt = store.readChallenge(id);
            assertNotNull(afterWrongAttempt, "one wrong OTP must retain the challenge below the attempt limit");
            assertEquals(1, afterWrongAttempt.attempts());
            assertEquals(OtpRedisStore.VerifyResult.CONSUMED,
                    store.verify(id, afterWrongAttempt, true, 3));
            assertNull(store.readChallenge(id), "a correct OTP consumes its challenge exactly once");
        }
    }
}
