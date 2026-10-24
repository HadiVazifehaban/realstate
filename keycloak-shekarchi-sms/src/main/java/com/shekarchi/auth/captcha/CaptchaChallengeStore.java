package com.shekarchi.auth.captcha;

import io.lettuce.core.RedisClient;
import io.lettuce.core.RedisURI;
import io.lettuce.core.ScriptOutputType;
import io.lettuce.core.api.StatefulRedisConnection;
import io.lettuce.core.api.sync.RedisCommands;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;

/** Redis-backed one-time CAPTCHA challenges and per-session/IP limits. */
public final class CaptchaChallengeStore implements AutoCloseable {
    private static final String ISSUE_SCRIPT = """
        local sessionCount = redis.call('incr', KEYS[2])
        if sessionCount == 1 then redis.call('expire', KEYS[2], ARGV[1]) end
        local ipCount = redis.call('incr', KEYS[3])
        if ipCount == 1 then redis.call('expire', KEYS[3], ARGV[1]) end
        if sessionCount > tonumber(ARGV[2]) or ipCount > tonumber(ARGV[3]) then
          redis.call('del', KEYS[1])
          return 0
        end
        redis.call('set', KEYS[1], ARGV[4], 'EX', ARGV[5])
        return 1
        """;

    private static final String CONSUME_SCRIPT = """
        local stored = redis.call('getdel', KEYS[1])
        local sessionCount = redis.call('incr', KEYS[2])
        if sessionCount == 1 then redis.call('expire', KEYS[2], ARGV[1]) end
        local ipCount = redis.call('incr', KEYS[3])
        if ipCount == 1 then redis.call('expire', KEYS[3], ARGV[1]) end
        local limited = 0
        if sessionCount > tonumber(ARGV[2]) or ipCount > tonumber(ARGV[3]) then limited = 1 end
        return tostring(limited) .. ':' .. (stored or '')
        """;

    private final String redisUrl;
    private final String namespace;
    private final Object connectionLock = new Object();
    private volatile RedisClient client;
    private volatile StatefulRedisConnection<String, String> connection;
    private volatile boolean closed;

    public CaptchaChallengeStore(String redisUrl, String namespace) {
        this.redisUrl = redisUrl == null ? "" : redisUrl.trim();
        this.namespace = namespace == null || namespace.isBlank()
                ? "shekarchi:captcha" : namespace.replaceAll(":+$", "");
    }

    public boolean issue(String sessionBinding, String ip, String record, int ttlSeconds,
                         int windowSeconds, int maxIssuesPerSession, int maxIssuesPerIp) {
        Long result = commands().eval(ISSUE_SCRIPT, ScriptOutputType.INTEGER,
                new String[]{challengeKey(sessionBinding), rateKey("issued-session", sessionBinding), rateKey("issued-ip", ip)},
                Integer.toString(windowSeconds), Integer.toString(maxIssuesPerSession),
                Integer.toString(maxIssuesPerIp), record, Integer.toString(ttlSeconds));
        return result != null && result == 1;
    }

    /** Atomically consumes the challenge and records the submission against session/IP limits. */
    public ConsumeResult consume(String sessionBinding, String ip, int windowSeconds,
                                 int maxSubmissionsPerSession, int maxSubmissionsPerIp) {
        String result = commands().eval(CONSUME_SCRIPT, ScriptOutputType.VALUE,
                new String[]{challengeKey(sessionBinding), rateKey("submit-session", sessionBinding), rateKey("submit-ip", ip)},
                Integer.toString(windowSeconds), Integer.toString(maxSubmissionsPerSession),
                Integer.toString(maxSubmissionsPerIp));
        if (result == null) return new ConsumeResult(true, null);
        int separator = result.indexOf(':');
        if (separator != 1) return new ConsumeResult(true, null);
        boolean limited = result.charAt(0) == '1';
        String record = result.substring(separator + 1);
        return new ConsumeResult(limited, record.isEmpty() ? null : record);
    }

    public void invalidate(String sessionBinding) {
        commands().del(challengeKey(sessionBinding));
    }

    private RedisCommands<String, String> commands() {
        StatefulRedisConnection<String, String> current = connection;
        if (current != null && current.isOpen() && !closed) return current.sync();
        synchronized (connectionLock) {
            if (closed) throw new IllegalStateException("CAPTCHA Redis store is closed");
            if (connection != null && connection.isOpen()) return connection.sync();
            if (redisUrl.isBlank()) throw new IllegalStateException("CAPTCHA Redis is not configured");
            if (client == null) {
                RedisURI uri = RedisURI.create(redisUrl);
                uri.setTimeout(Duration.ofSeconds(2));
                client = RedisClient.create(uri);
            }
            try {
                connection = client.connect();
                connection.setTimeout(Duration.ofSeconds(2));
                return connection.sync();
            } catch (RuntimeException unavailable) {
                if (connection != null) connection.close();
                connection = null;
                throw new IllegalStateException("CAPTCHA Redis is unavailable", unavailable);
            }
        }
    }

    private String challengeKey(String sessionBinding) {
        return namespace + ":challenge:" + digest(sessionBinding);
    }

    private String rateKey(String kind, String identity) {
        return namespace + ":" + kind + ":" + digest(identity);
    }

    private static String digest(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest((value == null ? "unknown" : value).getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException("Unable to derive CAPTCHA Redis key", e);
        }
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

    public record ConsumeResult(boolean rateLimited, String record) {}
}
