package com.shekarchi.auth.sms.provider;

/** Fake delivery is available only when both the environment and explicit flag agree. */
public final class FakeSmsAllowed {
    private FakeSmsAllowed() {}

    public static boolean allowed() {
        String environment = System.getenv("SHEKARCHI_ENV");
        String enabled = System.getenv("SHEKARCHI_SMS_FAKE");
        boolean nonOperational = "development".equalsIgnoreCase(environment) || "test".equalsIgnoreCase(environment);
        boolean explicitlyEnabled = "true".equalsIgnoreCase(enabled) || "1".equals(enabled);
        return nonOperational && explicitlyEnabled;
    }
}
