package com.shekarchi.auth.captcha;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.text.Normalizer;
import java.util.HexFormat;
import java.util.Locale;

public final class CaptchaHmac {
    private CaptchaHmac() {}

    public static String sign(String secret, String sessionBinding, String nonce, long expiresAt, String answer) {
        if (secret == null || secret.length() < 32) {
            throw new IllegalStateException("SHEKARCHI_CAPTCHA_HMAC_SECRET must contain at least 32 characters");
        }
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            String message = sessionBinding + "\u0000" + nonce + "\u0000" + expiresAt + "\u0000" + normalize(answer);
            return HexFormat.of().formatHex(mac.doFinal(message.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException("Unable to sign CAPTCHA challenge", e);
        }
    }

    public static boolean verify(String secret, String sessionBinding, String record, String submittedAnswer) {
        if (record == null || submittedAnswer == null) return false;
        String[] fields = record.split(":", -1);
        if (fields.length != 3) return false;
        try {
            long expiresAt = Long.parseLong(fields[1]);
            if (System.currentTimeMillis() / 1000L > expiresAt) return false;
            byte[] expected = sign(secret, sessionBinding, fields[0], expiresAt, submittedAnswer)
                    .getBytes(StandardCharsets.US_ASCII);
            byte[] stored = fields[2].getBytes(StandardCharsets.US_ASCII);
            return MessageDigest.isEqual(stored, expected);
        } catch (RuntimeException malformed) {
            return false;
        }
    }

    public static String normalize(String value) {
        String normalized = Normalizer.normalize(value == null ? "" : value, Normalizer.Form.NFKC).trim();
        StringBuilder ascii = new StringBuilder(normalized.length());
        for (int i = 0; i < normalized.length(); i++) {
            char c = normalized.charAt(i);
            if (c >= '۰' && c <= '۹') c = (char) ('0' + c - '۰');
            else if (c >= '٠' && c <= '٩') c = (char) ('0' + c - '٠');
            ascii.append(c);
        }
        return ascii.toString().toUpperCase(Locale.ROOT);
    }
}
