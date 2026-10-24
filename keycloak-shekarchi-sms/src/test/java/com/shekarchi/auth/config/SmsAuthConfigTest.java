package com.shekarchi.auth.config;

import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class SmsAuthConfigTest {
    @Test void defaultsMatchApprovedOtpPolicy() {
        SmsAuthConfig config = new SmsAuthConfig(Map.of());
        assertEquals(120, config.getTtlSeconds());
        assertEquals(3, config.getMaxAttempts());
        assertEquals(120, config.getResendCooldownSeconds());
        assertEquals(3600, config.getWindowSeconds());
        assertEquals(5, config.getIpHourlySoftLimit());
        assertEquals(5, config.getMobileHourlySoftLimit());
        assertEquals(15, config.getDailyLimit());
        assertTrue(config.isUnifiedLogin()); // Changed default to true for unified login
        assertEquals("melli-payamak", config.getSmsProviderId());
        assertEquals(120, config.getCaptchaTtlSeconds());
    }

    @Test void unifiedLoginIsExplicitlyOptIn() {
        assertTrue(new SmsAuthConfig(Map.of("ui.unified-login", "true")).isUnifiedLogin());
        assertFalse(new SmsAuthConfig(Map.of("ui.unified-login", "false")).isUnifiedLogin());
        assertEquals(3, new SmsAuthConfig(Map.of("captcha.ttl-seconds", "3")).getCaptchaTtlSeconds());
        assertEquals(600, new SmsAuthConfig(Map.of("captcha.ttl-seconds", "9999")).getCaptchaTtlSeconds());
    }

    @Test void policyIsConfigurableAndValuesAreBounded() {
        SmsAuthConfig config = new SmsAuthConfig(Map.of(
                "otp.ttl-seconds", "90", "otp.max-attempts", "4",
                "otp.resend-cooldown-seconds", "180", "otp.rate-window-seconds", "7200",
                "otp.ip-hourly-soft-limit", "8", "otp.mobile-hourly-soft-limit", "7",
                "otp.daily-max-per-mobile", "20"));
        assertEquals(90, config.getTtlSeconds());
        assertEquals(4, config.getMaxAttempts());
        assertEquals(180, config.getResendCooldownSeconds());
        assertEquals(7200, config.getWindowSeconds());
        assertEquals(8, config.getIpHourlySoftLimit());
        assertEquals(7, config.getMobileHourlySoftLimit());
        assertEquals(20, config.getDailyLimit());

        SmsAuthConfig bounded = new SmsAuthConfig(Map.of("otp.max-attempts", "-1", "otp.ttl-seconds", "9999"));
        assertEquals(1, bounded.getMaxAttempts());
        assertEquals(600, bounded.getTtlSeconds());
    }
}
