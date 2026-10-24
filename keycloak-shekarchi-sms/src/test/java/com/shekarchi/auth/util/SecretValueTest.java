package com.shekarchi.auth.util;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import static org.junit.jupiter.api.Assertions.*;

class SecretValueTest {
    @TempDir Path directory;

    @Test void loadsDockerSecretFileBeforeLegacyEnvironmentValue() throws Exception {
        Path secret = directory.resolve("otp.secret");
        Files.writeString(secret, "file-only-test-secret\n");
        Files.setPosixFilePermissions(secret, java.util.EnumSet.of(PosixFilePermission.OWNER_READ, PosixFilePermission.OWNER_WRITE));
        String value = SecretValue.get("SHEKARCHI_OTP_HMAC_SECRET", name -> switch (name) {
            case "SHEKARCHI_OTP_HMAC_SECRET_FILE" -> secret.toString();
            case "SHEKARCHI_OTP_HMAC_SECRET" -> "legacy-environment-value";
            default -> null;
        });
        assertEquals("file-only-test-secret", value);
    }

    @Test void rejectsGroupOrWorldReadableSecretFile() throws Exception {
        Path secret = directory.resolve("otp.secret");
        Files.writeString(secret, "test-only-secret");
        Files.setPosixFilePermissions(secret, java.util.EnumSet.of(PosixFilePermission.OWNER_READ,
                PosixFilePermission.OWNER_WRITE, PosixFilePermission.GROUP_READ));
        assertThrows(IllegalStateException.class,
                () -> SecretValue.get("SHEKARCHI_OTP_HMAC_SECRET", name -> name.endsWith("_FILE") ? secret.toString() : null));
    }

    @Test void resolvesRedisUrlFromFileAndKeepsLegacyFallback() throws Exception {
        Path secret = directory.resolve("redis.url");
        Files.writeString(secret, "redis://:test-only-password@redis:6379/0\n");
        Files.setPosixFilePermissions(secret, java.util.EnumSet.of(PosixFilePermission.OWNER_READ, PosixFilePermission.OWNER_WRITE));
        assertEquals("redis://:test-only-password@redis:6379/0", RedisUrlValue.get(name -> switch (name) {
            case "SHEKARCHI_REDIS_URL_FILE" -> secret.toString();
            default -> null;
        }));
        assertEquals("redis://redis:6379/0", RedisUrlValue.get(name ->
                "SHEKARCHI_REDIS_URL".equals(name) ? "redis://redis:6379/0" : null));
    }
}
