package com.shekarchi.auth.util;

import java.util.regex.Pattern;
import java.text.Normalizer;

public class PhoneNormalizer {
    private static final Pattern IRAN_MOBILE = Pattern.compile("^(\\+98|98|0)?9\\d{9}$");

    public static String normalize(String raw) throws IllegalArgumentException {
        if (raw == null) {
            throw new IllegalArgumentException("شماره موبایل الزامی است");
        }
        String trimmed = asciiDigits(Normalizer.normalize(raw, Normalizer.Form.NFKC).trim());
        if (trimmed.isEmpty()) {
            throw new IllegalArgumentException("شماره موبایل الزامی است");
        }
        // Remove spaces, dashes, parentheses
        String cleaned = trimmed.replaceAll("[\\s\\-()]", "");
        if (cleaned.startsWith("+98")) {
            cleaned = "98" + cleaned.substring(3);
        }
        if (cleaned.startsWith("0098")) {
            cleaned = "98" + cleaned.substring(4);
        }
        if (cleaned.startsWith("09")) {
            cleaned = "98" + cleaned.substring(1);
        }
        if (!IRAN_MOBILE.matcher("0" + cleaned.substring(2)).matches() && !cleaned.matches("98\\d{10}")) {
            // be lenient but validate basic form
            if (!cleaned.matches("98\\d{10}")) {
                throw new IllegalArgumentException("شماره موبایل معتبر نیست");
            }
        }
        return cleaned; // normalized to 98XXXXXXXXXX
    }

    private static String asciiDigits(String value) {
        StringBuilder result = new StringBuilder(value.length());
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (c >= '\u06f0' && c <= '\u06f9') c = (char) ('0' + c - '\u06f0');
            else if (c >= '\u0660' && c <= '\u0669') c = (char) ('0' + c - '\u0660');
            result.append(c);
        }
        return result.toString();
    }
}
