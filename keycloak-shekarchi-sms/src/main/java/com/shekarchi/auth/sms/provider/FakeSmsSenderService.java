package com.shekarchi.auth.sms.provider;

import com.shekarchi.auth.sms.SmsException;
import com.shekarchi.auth.sms.SmsSenderService;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class FakeSmsSenderService implements SmsSenderService {
    private static final java.util.regex.Pattern OTP_PATTERN = java.util.regex.Pattern.compile("(?<!\\d)(\\d{6})(?!\\d)");
    private static final Map<String, String> LAST_CODE_BY_PHONE = new ConcurrentHashMap<>();
    private final boolean enabled;

    public FakeSmsSenderService(FakeSmsSenderServiceFactory factory) {
        this(factory != null && factory.isFakeMode());
    }

    FakeSmsSenderService(boolean enabled) { this.enabled = enabled; }

    @Override
    public void sendSms(String phoneNumber, String message, String templateCode) throws SmsException {
        if (!enabled) {
            throw new SmsException("Fake SMS provider is disabled in Production (SHEKARCHI_SMS_FAKE not set)");
        }
        if (phoneNumber == null || phoneNumber.isBlank()) {
            throw new SmsException("شماره موبایل الزامی است");
        }
        java.util.regex.Matcher matcher = OTP_PATTERN.matcher(message == null ? "" : message);
        if (matcher.find()) LAST_CODE_BY_PHONE.put(phoneNumber, matcher.group(1));
    }

    @Override
    public void sendOtp(String phoneNumber, String code) throws SmsException {
        if (!enabled) {
            throw new SmsException("Fake SMS provider is disabled");
        }
        if (phoneNumber == null || phoneNumber.isBlank() || code == null || !code.matches("\\d{6}")) {
            throw new SmsException("Invalid OTP test delivery");
        }
        LAST_CODE_BY_PHONE.put(phoneNumber, code);
        captureForAuthorizedCloneTest(code);
    }

    /**
     * برای القناة تستی فقط: آخرین کد تولیدشده برای یک شماره را برمی‌گرداند.
     * صرفاً در محیط توسعه/تست و با مجوز ادمین قابل‌دسترس است.
     */
    public String getLastCode(String phoneNumber) {
        if (!enabled) {
            return null;
        }
        return LAST_CODE_BY_PHONE.get(phoneNumber);
    }

    private void captureForAuthorizedCloneTest(String code) throws SmsException {
        if (!enabled || !"test".equalsIgnoreCase(System.getenv("SHEKARCHI_ENV"))
                || !"true".equalsIgnoreCase(System.getenv("SHEKARCHI_TEST_CAPTURE_OTP"))) return;
        String configuredPath = System.getenv("SHEKARCHI_TEST_OTP_CAPTURE_PATH");
        Path path = Path.of(configuredPath == null || configuredPath.isBlank()
                ? "/tmp/shekarchi-test-otp-capture" : configuredPath);
        try {
            Files.writeString(path, code, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING,
                    StandardOpenOption.WRITE);
            Files.setPosixFilePermissions(path, PosixFilePermissions.fromString("rw-------"));
        } catch (Exception failure) {
            throw new SmsException("Unable to write test-only fake OTP capture", failure);
        }
    }

    /** Package-level test hook; not exposed through an HTTP or Keycloak endpoint. */
    static void clearTestCodes() { LAST_CODE_BY_PHONE.clear(); }

    @Override
    public void close() {
        // Shared test codes are cleared explicitly between isolated tests.
    }
}
