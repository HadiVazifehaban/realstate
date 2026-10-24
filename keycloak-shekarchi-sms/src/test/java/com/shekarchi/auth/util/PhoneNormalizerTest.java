package com.shekarchi.auth.util;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class PhoneNormalizerTest {
    @Test
    void testNormalize09() {
        assertEquals("989123456789", PhoneNormalizer.normalize("09123456789"));
    }

    @Test
    void testNormalizeWithPlus() {
        assertEquals("989123456789", PhoneNormalizer.normalize("+989123456789"));
    }

    @Test
    void testNormalizeWith98() {
        assertEquals("989123456789", PhoneNormalizer.normalize("989123456789"));
    }

    @Test
    void testNormalizeWithSpaces() {
        assertEquals("989123456789", PhoneNormalizer.normalize("0912 345 6789"));
    }

    @Test
    void testNormalizePersianAndArabicDigits() {
        assertEquals("989123456789", PhoneNormalizer.normalize("۰۹۱۲۳۴۵۶۷۸۹"));
        assertEquals("989123456789", PhoneNormalizer.normalize("٠٩١٢٣٤٥٦٧٨٩"));
    }

    @Test
    void testInvalid() {
        assertThrows(IllegalArgumentException.class, () -> PhoneNormalizer.normalize("12345"));
    }
}
