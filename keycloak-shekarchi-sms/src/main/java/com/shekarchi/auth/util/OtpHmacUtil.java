package com.shekarchi.auth.util;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;

public class OtpHmacUtil {
    private static final String HMAC_ALGO = "HmacSHA256";

    public static String hmac(String secret, String data) {
        try {
            Mac mac = Mac.getInstance(HMAC_ALGO);
            SecretKeySpec keySpec = new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), HMAC_ALGO);
            mac.init(keySpec);
            byte[] hmac = mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
            return Base64.getUrlEncoder().withoutPadding().encodeToString(hmac);
        } catch (Exception e) {
            throw new RuntimeException("HMAC generation failed", e);
        }
    }

    public static boolean verify(String secret, String data, String expectedHash) {
        if (secret == null || data == null || expectedHash == null) {
            return false;
        }
        try {
            String actual = hmac(secret, data);
            return MessageDigest.isEqual(actual.getBytes(StandardCharsets.UTF_8),
                    expectedHash.getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            return false;
        }
    }
}
