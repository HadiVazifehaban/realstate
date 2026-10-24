package com.shekarchi.auth.util;

import java.util.function.Function;

/** Resolves Redis URLs from Docker secret files without exposing them in env values. */
public final class RedisUrlValue {
    private RedisUrlValue() {}

    public static String get() {
        return get(System::getenv);
    }

    static String get(Function<String, String> environment) {
        String url = SecretValue.get("SHEKARCHI_REDIS_URL", environment);
        if (url == null || url.isBlank()) url = SecretValue.get("REDIS_URL", environment);
        return url;
    }
}
