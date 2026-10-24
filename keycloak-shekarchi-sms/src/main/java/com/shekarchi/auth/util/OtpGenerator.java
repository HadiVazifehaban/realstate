package com.shekarchi.auth.util;

import java.security.SecureRandom;

public class OtpGenerator {
    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    public static String generate6Digit() {
        return String.format(java.util.Locale.ROOT, "%06d", SECURE_RANDOM.nextInt(1_000_000));
    }
}
