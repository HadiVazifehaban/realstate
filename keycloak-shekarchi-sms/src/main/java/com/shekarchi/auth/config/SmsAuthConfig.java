package com.shekarchi.auth.config;

import org.keycloak.models.AuthenticatorConfigModel;

import java.util.Map;

public class SmsAuthConfig {
    private final Map<String, String> config;

    public SmsAuthConfig(Map<String, String> config) {
        this.config = config != null ? config : Map.of();
    }

    public static SmsAuthConfig fromModel(AuthenticatorConfigModel model) {
        return new SmsAuthConfig(model != null && model.getConfig() != null ? model.getConfig() : Map.of());
    }

    private String get(String key, String defaultValue) {
        String value = config.get(key);
        return value != null && !value.isBlank() ? value : defaultValue;
    }

    private int getInt(String key, int defaultValue) {
        String value = config.get(key);
        if (value == null || value.isBlank()) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    public int getOtpTtlSeconds() {
        return getTtlSeconds();
    }

    public int getMaxAttempts() {
        return bounded("otp.max-attempts", 3, 1, 10);
    }

    public int getResendCooldownSeconds() {
        return bounded("otp.resend-cooldown-seconds", 120, 1, 3600);
    }

    public int getResendMaxPerWindow() {
        return getDailyLimit();
    }

    public int getWindowSeconds() {
        return bounded("otp.rate-window-seconds", 3600, 60, 86400);
    }

    public int getIpHourlySoftLimit() { return bounded("otp.ip-hourly-soft-limit", 5, 1, 10000); }
    public int getMobileHourlySoftLimit() { return bounded("otp.mobile-hourly-soft-limit", 5, 1, 10000); }
    public int getDailyLimit() { return bounded("otp.daily-max-per-mobile", 15, 1, 1000); }
    public int getTtlSeconds() { return bounded("otp.ttl-seconds", 120, 30, 600); }

    private int bounded(String key, int fallback, int min, int max) {
        int value = getInt(key, fallback);
        return Math.max(min, Math.min(max, value));
    }

    public String getSmsProviderId() {
        return get("sms.provider-id", "melli-payamak");
    }

    public String getFlowType() {
        return get("flow.type", "PASSWORDLESS"); // PASSWORDLESS or MFA
    }

    public boolean isMfaFlow() {
        return "MFA".equalsIgnoreCase(getFlowType());
    }

    public boolean isUnifiedLogin() {
        return Boolean.parseBoolean(get("ui.unified-login", "true"));
    }

    public int getCaptchaTtlSeconds() {
        return bounded("captcha.ttl-seconds", 120, 1, 600);
    }
}
