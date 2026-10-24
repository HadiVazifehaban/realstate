package com.shekarchi.auth.otp;

import io.lettuce.core.RedisClient;
import io.lettuce.core.RedisURI;
import io.lettuce.core.ScriptOutputType;
import io.lettuce.core.api.StatefulRedisConnection;
import io.lettuce.core.api.sync.RedisCommands;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Map;

/** Shared Redis-backed OTP state. One thread-safe Lettuce connection is reused by all authenticator executions. */
public final class OtpRedisStore implements AutoCloseable {
    private static final String ISSUE_SCRIPT = """
        local cooldown = redis.call('ttl', KEYS[1])
        if cooldown > 0 then return 'COOLDOWN:' .. cooldown end
        local daily = tonumber(redis.call('get', KEYS[2]) or '0')
        if daily >= tonumber(ARGV[1]) then return 'DAILY_LIMIT' end
        local phoneCount = redis.call('incr', KEYS[3])
        if phoneCount == 1 then redis.call('expire', KEYS[3], ARGV[2]) end
        local ipCount = redis.call('incr', KEYS[4])
        if ipCount == 1 then redis.call('expire', KEYS[4], ARGV[2]) end
        if phoneCount > tonumber(ARGV[3]) or ipCount > tonumber(ARGV[4]) then return 'SOFT_LIMIT' end
        local dailyCount = redis.call('incr', KEYS[2])
        if dailyCount == 1 then redis.call('expire', KEYS[2], ARGV[5]) end
        redis.call('set', KEYS[1], '1', 'EX', ARGV[6])
        redis.call('hset', KEYS[5], 'hash', ARGV[7], 'attempts', '0', 'expires', ARGV[8])
        redis.call('expire', KEYS[5], ARGV[9])
        return 'OK'
        """;

    private static final String VERIFY_SCRIPT = """
        if redis.call('exists', KEYS[1]) == 0 then return -1 end
        if redis.call('hget', KEYS[1], 'hash') ~= ARGV[1] then return -1 end
        if redis.call('hget', KEYS[1], 'attempts') ~= ARGV[2] then return -1 end
        if ARGV[3] == '1' then
          return redis.call('del', KEYS[1])
        end
        local attempts = redis.call('hincrby', KEYS[1], 'attempts', 1)
        if attempts >= tonumber(ARGV[4]) then redis.call('del', KEYS[1]) end
        return 0
        """;

    private final String redisUrl;
    private final String namespace;
    private final Object connectionLock = new Object();
    private volatile RedisClient client;
    private volatile StatefulRedisConnection<String, String> connection;
    private volatile boolean closed;
    private volatile long retryConnectionAfterMillis;

    public OtpRedisStore(String redisUrl, String namespace) {
        this.redisUrl = redisUrl == null ? "" : redisUrl.trim();
        this.namespace = namespace == null || namespace.isBlank() ? "shekarchi:otp" : namespace.replaceAll(":+$", "");
    }

    public IssueResult issue(String challengeId, String mobile, String ip, String otpHmac,
                             long expiresAt, Policy policy) {
        RedisCommands<String, String> commands = commands();
        long now = Instant.now().getEpochSecond();
        long window = now / policy.rateWindowSeconds();
        long day = now / 86400;
        int windowTtl = (int) Math.max(1, policy.rateWindowSeconds() - (now % policy.rateWindowSeconds()));
        int dayTtl = (int) Math.max(1, 86400 - (now % 86400));
        String result = commands.eval(ISSUE_SCRIPT, ScriptOutputType.VALUE,
                new String[]{key("cooldown", digest(mobile)), key("daily", digest(mobile), Long.toString(day)),
                        key("hour-mobile", digest(mobile), Long.toString(window)),
                        key("hour-ip", digest(ip), Long.toString(window)), key("challenge", challengeId)},
                Integer.toString(policy.dailyLimit()), Integer.toString(windowTtl),
                Integer.toString(policy.mobileHourlySoftLimit()), Integer.toString(policy.ipHourlySoftLimit()),
                Integer.toString(dayTtl), Integer.toString(policy.cooldownSeconds()), otpHmac,
                Long.toString(expiresAt), Integer.toString(policy.ttlSeconds()));
        if ("OK".equals(result)) return new IssueResult(IssueStatus.OK, 0);
        if (result != null && result.startsWith("COOLDOWN:")) {
            return new IssueResult(IssueStatus.COOLDOWN, parseInt(result.substring("COOLDOWN:".length()), policy.cooldownSeconds()));
        }
        if ("DAILY_LIMIT".equals(result)) return new IssueResult(IssueStatus.DAILY_LIMIT, dayTtl);
        if ("SOFT_LIMIT".equals(result)) return new IssueResult(IssueStatus.SOFT_LIMIT, windowTtl);
        throw new IllegalStateException("Redis returned an unexpected OTP issue result");
    }

    public Challenge readChallenge(String challengeId) {
        Map<String, String> data = commands().hgetall(key("challenge", challengeId));
        if (data == null || data.isEmpty()) return null;
        try {
            return new Challenge(data.get("hash"), Integer.parseInt(data.get("attempts")), Long.parseLong(data.get("expires")));
        } catch (RuntimeException malformed) {
            commands().del(key("challenge", challengeId));
            return null;
        }
    }

    /** Atomically consumes a matching challenge or increments a wrong-code attempt. */
    public VerifyResult verify(String challengeId, Challenge snapshot, boolean codeMatches, int maxAttempts) {
        Long result = commands().eval(VERIFY_SCRIPT, ScriptOutputType.INTEGER,
                new String[]{key("challenge", challengeId)}, snapshot.hash(), Integer.toString(snapshot.attempts()),
                codeMatches ? "1" : "0", Integer.toString(maxAttempts));
        if (result == null || result < 0) return VerifyResult.STALE;
        return codeMatches && result == 1 ? VerifyResult.CONSUMED : VerifyResult.REJECTED;
    }

    public void invalidate(String challengeId) {
        commands().del(key("challenge", challengeId));
    }

    private RedisCommands<String, String> commands() {
        StatefulRedisConnection<String, String> current = connection;
        if (current != null && current.isOpen() && !closed) return current.sync();
        synchronized (connectionLock) {
            if (closed) throw new IllegalStateException("OTP Redis store is closed");
            if (connection != null && connection.isOpen()) return connection.sync();
            if (System.currentTimeMillis() < retryConnectionAfterMillis) {
                throw new IllegalStateException("OTP Redis connection is temporarily unavailable");
            }
            if (redisUrl.isBlank()) throw new IllegalStateException("OTP Redis is not configured");
            if (client == null) {
                RedisURI uri = RedisURI.create(redisUrl);
                uri.setTimeout(Duration.ofSeconds(2));
                client = RedisClient.create(uri);
            }
            try {
                connection = client.connect();
                connection.setTimeout(Duration.ofSeconds(2));
                retryConnectionAfterMillis = 0;
                return connection.sync();
            } catch (RuntimeException unavailable) {
                retryConnectionAfterMillis = System.currentTimeMillis() + 5000;
                throw unavailable;
            }
        }
    }

    private String key(String... parts) {
        return namespace + ":" + String.join(":", parts);
    }

    private static String digest(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest((value == null ? "" : value).getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException("Unable to derive Redis key", e);
        }
    }

    private static int parseInt(String value, int fallback) {
        try { return Integer.parseInt(value); } catch (RuntimeException e) { return fallback; }
    }

    @Override
    public void close() {
        synchronized (connectionLock) {
            closed = true;
            if (connection != null) connection.close();
            if (client != null) client.shutdown(Duration.ofMillis(100), Duration.ofSeconds(2));
            connection = null;
            client = null;
        }
    }

    public enum IssueStatus { OK, COOLDOWN, DAILY_LIMIT, SOFT_LIMIT }
    public enum VerifyResult { CONSUMED, REJECTED, STALE }
    public record IssueResult(IssueStatus status, int retryAfterSeconds) {}
    public record Challenge(String hash, int attempts, long expiresAt) {}
    public record Policy(int ttlSeconds, int maxAttempts, int cooldownSeconds,
                         int rateWindowSeconds, int ipHourlySoftLimit, int mobileHourlySoftLimit, int dailyLimit) {}
}
