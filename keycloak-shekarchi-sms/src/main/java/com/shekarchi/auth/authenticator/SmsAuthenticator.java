package com.shekarchi.auth.authenticator;
import com.shekarchi.auth.config.SmsAuthConfig;
import com.shekarchi.auth.captcha.CaptchaChallenge;
import com.shekarchi.auth.captcha.CaptchaChallengeStore;
import com.shekarchi.auth.captcha.CaptchaHmac;
import com.shekarchi.auth.otp.OtpRedisStore;
import com.shekarchi.auth.sms.SmsSenderService;
import com.shekarchi.auth.sms.provider.FakeSmsAllowed;
import com.shekarchi.auth.sms.provider.MelliPayamakSmsSenderService;
import com.shekarchi.auth.util.OtpGenerator;
import com.shekarchi.auth.util.OtpHmacUtil;
import com.shekarchi.auth.util.PhoneNormalizer;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.authentication.AuthenticationFlowError;
import org.keycloak.authentication.Authenticator;
import org.keycloak.authentication.authenticators.browser.UsernamePasswordForm;
import org.keycloak.authentication.authenticators.util.AuthenticatorUtils;
import org.keycloak.models.*;

import jakarta.ws.rs.core.MultivaluedMap;
import jakarta.ws.rs.core.MultivaluedHashMap;
import jakarta.ws.rs.core.Response;
import java.time.Instant;
import java.security.SecureRandom;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Stream;

public class SmsAuthenticator extends UsernamePasswordForm {
    private static final String NOTE_PHONE = "SHEKARCHI_PHONE_NORMALIZED";
    private static final String NOTE_CHALLENGE_ID = "SHEKARCHI_OTP_CHALLENGE_ID";
    private static final String NOTE_OTP_ELIGIBLE = "SHEKARCHI_OTP_ELIGIBLE";
    private static final String NOTE_FLOW = "SHEKARCHI_FLOW_TYPE";
    private static final String NOTE_USER_ID = "SHEKARCHI_OTP_USER_ID";
    private static final String NOTE_ISSUED_AT = "SHEKARCHI_OTP_ISSUED_AT";
    private static final String NOTE_DELIVERY_STATUS = "SHEKARCHI_OTP_DELIVERY_STATUS";
    private static final String NOTE_FAILED_ATTEMPTS = "SHEKARCHI_LOGIN_FAILED_ATTEMPTS";
    private static final String NOTE_CAPTCHA_REQUIRED = "SHEKARCHI_LOGIN_CAPTCHA_REQUIRED";
    private static final String NOTE_RESEND_CAPTCHA_REQUIRED = "SHEKARCHI_RESEND_CAPTCHA_REQUIRED";
    private static final int CAPTCHA_AFTER_FAILURES = 3;
    private static final String GENERIC_OTP_MESSAGE = "اگر شماره واجد شرایط باشد، کد تأیید ارسال می‌شود.";
    private static final int CAPTCHA_RATE_WINDOW_SECONDS = 900;
    private static final int CAPTCHA_MAX_ISSUES_PER_SESSION = 12;
    private static final int CAPTCHA_MAX_ISSUES_PER_IP = 60;
    private static final int CAPTCHA_MAX_SUBMISSIONS_PER_SESSION = 6;
    private static final int CAPTCHA_MAX_SUBMISSIONS_PER_IP = 30;
    private static final SecureRandom CAPTCHA_RANDOM = new SecureRandom();

    private final OtpRedisStore otpStore;
    private final CaptchaChallengeStore captchaStore;

    public SmsAuthenticator(OtpRedisStore otpStore) { this(otpStore, null); }

    public SmsAuthenticator(OtpRedisStore otpStore, CaptchaChallengeStore captchaStore) {
        this.otpStore = otpStore;
        this.captchaStore = captchaStore;
    }

    @Override
    public void authenticate(AuthenticationFlowContext context) {
        SmsAuthConfig config = SmsAuthConfig.fromModel(context.getAuthenticatorConfig());
        if (config.isMfaFlow()) {
            UserModel user = context.getAuthenticationSession().getAuthenticatedUser();
            if (!eligible(context, user)) {
                context.failure(AuthenticationFlowError.INVALID_USER);
                return;
            }
            String verifiedPhone = getVerifiedPhone(user);
            if (verifiedPhone == null || verifiedPhone.isBlank()) {
                context.forceChallenge(Response.ok("شماره موبایل تأییدشده برای این حساب یافت نشد").build());
                return;
            }
            String normalized = normalizePhone(verifiedPhone, context);
            if (normalized == null) return;
            boolean sent = issueOtp(context, config, normalized, "mfa");
            showOtpForm(context, sent ? GENERIC_OTP_MESSAGE : GENERIC_OTP_MESSAGE);
            return;
        }
        showPhoneForm(context, SmsAuthConfig.fromModel(context.getAuthenticatorConfig()));
    }

    @Override
    public void action(AuthenticationFlowContext context) {
        MultivaluedMap<String, String> formData = context.getHttpRequest().getDecodedFormParameters();
        if (formData.containsKey("cancel")) {
            context.cancelLogin();
            return;
        }

        SmsAuthConfig config = SmsAuthConfig.fromModel(context.getAuthenticatorConfig());
        String action = formData.getFirst("action");
        if (action == null) action = "";

        // Second-factor execution must never accept a new account or first-factor action.
        if (config.isMfaFlow() && !List.of("verify", "resend").contains(action)) {
            context.failure(AuthenticationFlowError.INVALID_CREDENTIALS);
            return;
        }

        if ("returnToLogin".equals(action) && config.isUnifiedLogin()) {
            clearOtp(context);
            context.clearUser();
            context.challenge(renderUnifiedLogin(context, config, safeLoginFormData(formData), null));
            return;
        }

        if ("captchaRefresh".equals(action) || formData.containsKey("captchaRefresh")) {
            if (config.isUnifiedLogin()) {
                if (getSessionNote(context, NOTE_CHALLENGE_ID) != null
                        && "login".equals(getSessionNote(context, NOTE_FLOW))) {
                    showOtpForm(context, GENERIC_OTP_MESSAGE);
                } else {
                    context.challenge(renderUnifiedLogin(context, config, safeLoginFormData(formData), null));
                }
            } else {
                context.attempted();
            }
            return;
        }

        if (config.isUnifiedLogin() && (action.isEmpty() || "passwordLogin".equals(action))) {
            boolean required = captchaRequired(context, formData);
            if (required && !consumeCaptcha(context, formData)) {
                context.getEvent().detail("captcha_result", "invalid").error("invalid_user_credentials");
                context.failureChallenge(AuthenticationFlowError.INVALID_CREDENTIALS,
                        renderUnifiedLogin(context, config, safeLoginFormData(formData), "captchaInvalid"));
                return;
            }
            if (required) context.getEvent().detail("captcha_result", "valid");
            super.action(context);
            return;
        }

        if ("submitPhone".equals(action)) {
            if (config.isUnifiedLogin() && captchaRequired(context, formData) && !consumeCaptcha(context, formData)) {
                context.getEvent().detail("captcha_result", "invalid").error("invalid_user_credentials");
                context.failureChallenge(AuthenticationFlowError.INVALID_CREDENTIALS,
                        renderUnifiedLogin(context, config, safeLoginFormData(formData), "captchaInvalid"));
                return;
            }
            String phone = formData.getFirst("phone");
            String normalized = normalizePhone(phone, context);
            if (normalized == null) return;
            setSessionNote(context, NOTE_OTP_ELIGIBLE, "false");
            UserModel user = findUniqueVerifiedUser(context, context.getRealm(), normalized);
            if (!eligible(context, user)) {
                // Keep the response generic and do not create a fake OTP
                // challenge for an unknown, disabled, or unverified account.
                context.getEvent().detail("otp_issue", "not_eligible");
                context.challenge(renderUnifiedLogin(context, config,
                        safeLoginFormData(formData), "smsOtpRequestGeneric"));
                return;
            }
            if (issueOtp(context, config, normalized, "login")) {
                showOtpForm(context, GENERIC_OTP_MESSAGE);
            } else {
                context.challenge(renderUnifiedLogin(context, config,
                        safeLoginFormData(formData), "smsOtpChallengeUnavailable"));
            }
            return;
        }

        if ("resend".equals(action)) {
            if (config.isUnifiedLogin() && !config.isMfaFlow()) {
                if (!captchaRequired(context, formData)
                        && !"true".equals(getSessionNote(context, NOTE_RESEND_CAPTCHA_REQUIRED))) {
                    setSessionNote(context, NOTE_RESEND_CAPTCHA_REQUIRED, "true");
                    showOtpForm(context, GENERIC_OTP_MESSAGE);
                    return;
                }
                if (!consumeCaptcha(context, formData)) {
                    context.getEvent().detail("captcha_result", "invalid").error("invalid_user_credentials");
                    showOtpForm(context, "پاسخ کپچا معتبر نیست یا منقضی شده است");
                    return;
                }
                context.getAuthenticationSession().removeAuthNote(NOTE_RESEND_CAPTCHA_REQUIRED);
            }
            String phone = getSessionNote(context, NOTE_PHONE);
            if (phone == null) {
                showPhoneForm(context, config);
                return;
            }
            if (config.isMfaFlow()) {
                UserModel currentUser = context.getAuthenticationSession().getAuthenticatedUser();
                String verifiedPhone = currentUser == null ? null : getVerifiedPhone(currentUser);
                if (currentUser == null || !currentUser.isEnabled() || verifiedPhone == null
                        || !phone.equals(normalizePhone(verifiedPhone, context))) {
                    setSessionNote(context, NOTE_OTP_ELIGIBLE, "false");
                    showOtpForm(context, GENERIC_OTP_MESSAGE);
                    return;
                }
            } else {
                UserModel eligibleUser = findUniqueVerifiedUser(context, context.getRealm(), phone);
                if (!eligible(context, eligibleUser)) {
                    setSessionNote(context, NOTE_OTP_ELIGIBLE, "false");
                    showOtpForm(context, GENERIC_OTP_MESSAGE);
                    return;
                }
            }
            issueOtp(context, config, phone, config.isMfaFlow() ? "mfa" : "login");
            showOtpForm(context, GENERIC_OTP_MESSAGE);
            return;
        }

        if ("verify".equals(action)) {
            String code = formData.getFirst("otp");
            if (config.isUnifiedLogin() && !config.isMfaFlow()
                    && captchaRequired(context, formData) && !consumeCaptcha(context, formData)) {
                context.getEvent().detail("captcha_result", "invalid").error("invalid_user_credentials");
                showOtpForm(context, "پاسخ کپچا معتبر نیست یا منقضی شده است");
                return;
            }
            if ("true".equals(getSessionNote(context, NOTE_OTP_ELIGIBLE)) && verifyOtp(context, config, code == null ? "" : code)) {
                context.getAuthenticationSession().removeAuthNote(NOTE_FAILED_ATTEMPTS);
                completeAuthentication(context, config);
            } else {
                incrementFailedAttempts(context);
                context.getEvent().detail("otp_result", "invalid").error("invalid_user_credentials");
                showOtpForm(context, "کد وارد شده نامعتبر یا منقضی است");
            }
            return;
        }

        context.failure(AuthenticationFlowError.INVALID_CREDENTIALS);
    }

    @Override
    protected Response challenge(AuthenticationFlowContext context, String error, String field) {
        SmsAuthConfig config = SmsAuthConfig.fromModel(context.getAuthenticatorConfig());
        if (!config.isUnifiedLogin()) return super.challenge(context, error, field);
        String password = context.getHttpRequest().getDecodedFormParameters().getFirst("password");
        if (error != null && !error.isBlank() && password != null && !password.isEmpty()) {
            incrementFailedAttempts(context);
        }
        return renderUnifiedLogin(context, config,
                safeLoginFormData(context.getHttpRequest().getDecodedFormParameters()), error);
    }

    private boolean eligible(AuthenticationFlowContext context, UserModel user) {
        return user != null && user.isEnabled()
                && AuthenticatorUtils.getDisabledByBruteForceEventError(context, user) == null;
    }

    private void clearOtp(AuthenticationFlowContext context) {
        String challenge = getSessionNote(context, NOTE_CHALLENGE_ID);
        if (challenge != null) {
            try { otpStore.invalidate(challenge); } catch (RuntimeException unavailable) {
                context.getEvent().detail("otp_result", "unavailable").error("authentication_failed");
            }
        }
        for (String note : List.of(NOTE_PHONE, NOTE_CHALLENGE_ID, NOTE_OTP_ELIGIBLE,
                NOTE_FLOW, NOTE_USER_ID, NOTE_ISSUED_AT, NOTE_DELIVERY_STATUS)) {
            context.getAuthenticationSession().removeAuthNote(note);
        }
    }

    private void showPhoneForm(AuthenticationFlowContext context, SmsAuthConfig config) {
        if (config.isUnifiedLogin()) {
            context.forceChallenge(renderUnifiedLogin(context, config, new MultivaluedHashMap<>(), null));
            return;
        }
        Response response = context.form()
                .setAttribute("loginMethod", "sms")
                .createForm("login-sms.ftl");
        context.forceChallenge(response);
    }

    @Override
    protected Response challenge(AuthenticationFlowContext context, MultivaluedMap<String, String> formData) {
        SmsAuthConfig config = SmsAuthConfig.fromModel(context.getAuthenticatorConfig());
        if (config.isUnifiedLogin() && !config.isMfaFlow()) {
            return renderUnifiedLogin(context, config, safeLoginFormData(formData), null);
        }
        return super.challenge(context, formData);
    }

    private Response renderUnifiedLogin(AuthenticationFlowContext context, SmsAuthConfig config,
                                        MultivaluedMap<String, String> formData, String errorKey) {
        var form = context.form();
        // The SMS tab is a real Keycloak execution even while the gateway is
        // awaiting credentials. Delivery readiness is informational only.
        form.setAttribute("smsAvailable", true);
        form.setAttribute("smsDeliveryConfigured", smsDeliveryAvailable(context, config));
        if (formData != null && !formData.isEmpty()) form.setFormData(formData);
        if (errorKey != null) form.setError(errorKey);
        boolean captchaRequired = captchaRequired(context, formData);
        form.setAttribute("captchaRequired", captchaRequired);
        if (!captchaRequired) {
            return form.setAttribute("captchaAvailable", false).setAttribute("unifiedLogin", true)
                    .setAttribute("loginMode", loginMode(formData)).createForm("login.ftl");
        }
        setSessionNote(context, NOTE_CAPTCHA_REQUIRED, "true");
        if (captchaStore == null) {
            return form.setError("captchaServiceUnavailable").setAttribute("captchaAvailable", false)
                    .setAttribute("unifiedLogin", true).setAttribute("loginMode", loginMode(formData))
                    .createForm("login.ftl");
        }
        String binding = captchaBinding(context);
        String ip = trustedClientIp(context);
        try {
            context.getEvent().detail("captcha_phase", "render");
            CaptchaChallenge challenge = CaptchaChallenge.create();
            int captchaTtl = config.getCaptchaTtlSeconds();
            long expiresAt = Instant.now().getEpochSecond() + captchaTtl;
            byte[] nonceBytes = new byte[16];
            CAPTCHA_RANDOM.nextBytes(nonceBytes);
            String nonce = HexFormat.of().formatHex(nonceBytes);
            context.getEvent().detail("captcha_phase", "sign");
            String signature = CaptchaHmac.sign(captchaSecret(), binding, nonce, expiresAt, challenge.answer());
            String record = nonce + ":" + expiresAt + ":" + signature;
            context.getEvent().detail("captcha_phase", "redis");
            if (!captchaStore.issue(binding, ip, record, captchaTtl, CAPTCHA_RATE_WINDOW_SECONDS,
                    CAPTCHA_MAX_ISSUES_PER_SESSION, CAPTCHA_MAX_ISSUES_PER_IP)) {
                return form.setError("captchaRateLimited").setAttribute("captchaAvailable", false)
                        .setAttribute("unifiedLogin", true).setAttribute("loginMode", loginMode(formData))
                        .createForm("login.ftl");
            }
            context.getEvent().detail("captcha_phase", "ready");
            return form.setAttribute("captchaAvailable", true).setAttribute("captchaQuestion", challenge.question())
                    .setAttribute("captchaImage", challenge.imageDataUri())
                    .setAttribute("unifiedLogin", true).setAttribute("loginMode", loginMode(formData))
                    .createForm("login.ftl");
        } catch (RuntimeException unavailable) {
            context.getAuthenticationSession().removeAuthNote(NOTE_CHALLENGE_ID);
            Throwable root = unavailable;
            while (root.getCause() != null && root.getCause() != root) root = root.getCause();
            context.getEvent().detail("captcha_result", "unavailable")
                    .detail("captcha_failure", root.getClass().getSimpleName())
                    .error("authentication_failed");
            return form.setError("captchaServiceUnavailable").setAttribute("captchaAvailable", false)
                    .setAttribute("unifiedLogin", true).setAttribute("loginMode", loginMode(formData))
                    .createForm("login.ftl");
        }
    }

    private boolean smsDeliveryAvailable(AuthenticationFlowContext context, SmsAuthConfig config) {
        String providerId = config.getSmsProviderId();
        if ("fake-sms-shekarchi".equals(providerId)) return FakeSmsAllowed.allowed();
        try {
            SmsSenderService sender = context.getSession().getProvider(SmsSenderService.class, providerId);
            if (sender instanceof MelliPayamakSmsSenderService melliPayamak) return melliPayamak.isOtpConfigured();
        } catch (RuntimeException | LinkageError unavailable) {
            return false;
        }
        // Do not advertise provider stubs or unknown senders as live OTP login.
        // Kavenegar's current adapter is not yet a production-verified pattern
        // implementation and exposes no safe readiness check.
        return false;
    }

    private boolean consumeCaptcha(AuthenticationFlowContext context, MultivaluedMap<String, String> formData) {
        if (captchaStore == null) return false;
        String binding = captchaBinding(context);
        try {
            var consumed = captchaStore.consume(binding, trustedClientIp(context), CAPTCHA_RATE_WINDOW_SECONDS,
                    CAPTCHA_MAX_SUBMISSIONS_PER_SESSION, CAPTCHA_MAX_SUBMISSIONS_PER_IP);
            String answer = formData.getFirst("captchaAnswer");
            return !consumed.rateLimited() && consumed.record() != null
                    && CaptchaHmac.verify(captchaSecret(), binding, consumed.record(), answer);
        } catch (RuntimeException unavailable) {
            context.getEvent().detail("captcha_result", "unavailable")
                    .detail("captcha_failure", unavailable.getClass().getSimpleName())
                    .error("authentication_failed");
            return false;
        }
    }

    private boolean captchaRequired(AuthenticationFlowContext context, MultivaluedMap<String, String> formData) {
        if ("true".equals(getSessionNote(context, NOTE_CAPTCHA_REQUIRED))) return true;
        int failures = failedAttempts(context);
        String username = formData == null ? null : formData.getFirst("username");
        String phone = formData == null ? null : formData.getFirst("phone");
        if ((phone == null || phone.isBlank()) && getSessionNote(context, NOTE_PHONE) != null) {
            phone = getSessionNote(context, NOTE_PHONE);
        }
        UserModel user = null;
        if (username != null && !username.isBlank()) {
            user = context.getSession().users().getUserByUsername(context.getRealm(), username.trim());
            if (user == null && username.contains("@")) {
                user = context.getSession().users().getUserByEmail(context.getRealm(), username.trim());
            }
        } else if (phone != null && !phone.isBlank()) {
            try { user = findUniqueVerifiedUser(context, context.getRealm(), PhoneNormalizer.normalize(phone)); }
            catch (IllegalArgumentException ignored) { return failures >= CAPTCHA_AFTER_FAILURES; }
        }
        if (user != null) {
            var failure = context.getSession().loginFailures().getUserLoginFailure(context.getRealm(), user.getId());
            if (failure != null) failures = Math.max(failures, failure.getNumFailures());
        }
        return failures >= CAPTCHA_AFTER_FAILURES;
    }

    private int failedAttempts(AuthenticationFlowContext context) {
        try {
            return Math.max(0, Integer.parseInt(getSessionNote(context, NOTE_FAILED_ATTEMPTS)));
        } catch (RuntimeException missingOrInvalid) {
            return 0;
        }
    }

    private void incrementFailedAttempts(AuthenticationFlowContext context) {
        int current = failedAttempts(context);
        setSessionNote(context, NOTE_FAILED_ATTEMPTS, Integer.toString(Math.min(current + 1, 100)));
    }

    private static MultivaluedMap<String, String> safeLoginFormData(MultivaluedMap<String, String> formData) {
        MultivaluedMap<String, String> safe = new MultivaluedHashMap<>();
        copySafe(formData, safe, "username");
        copySafe(formData, safe, "phone");
        copySafe(formData, safe, "loginMode");
        return safe;
    }

    private static void copySafe(MultivaluedMap<String, String> from, MultivaluedMap<String, String> to, String key) {
        String value = from.getFirst(key);
        if (value != null) to.putSingle(key, value);
    }

    private static String loginMode(MultivaluedMap<String, String> formData) {
        String mode = formData == null ? null : formData.getFirst("loginMode");
        return "sms".equals(mode) || "recovery".equals(mode) ? mode : "password";
    }

    private static String captchaBinding(AuthenticationFlowContext context) {
        var session = context.getAuthenticationSession();
        return session.getParentSession().getId() + ":" + session.getTabId();
    }

    private String captchaSecret() {
        String secret = com.shekarchi.auth.util.SecretValue.get("SHEKARCHI_CAPTCHA_HMAC_SECRET");
        if (secret == null || secret.length() < 32) throw new IllegalStateException("CAPTCHA HMAC secret is unavailable");
        return secret;
    }

    private void showOtpForm(AuthenticationFlowContext context, String message) {
        String deliveryStatus = getSessionNote(context, NOTE_DELIVERY_STATUS);
        var form = context.form().setAttribute("loginMethod", "otp")
                .setAttribute("otpMessage", message)
                .setAttribute("phoneMasked", maskPhone(getSessionNote(context, NOTE_PHONE)));
        String deliveryMessage = switch (deliveryStatus == null ? "" : deliveryStatus) {
            case "accepted" -> "درخواست ارسال کد تأیید با موفقیت ثبت شد. لطفاً پیامک دریافتی را بررسی کنید.";
            case "not-configured" -> "درخواست تأیید ثبت شد، اما سرویس پیامکی هنوز آماده ارسال کد نیست. لطفاً بعداً دوباره تلاش کنید.";
            case "failed" -> "درخواست ارسال کد انجام شد، اما سرویس پیامکی ارسال موفق را تأیید نکرد. اگر پیامک را دریافت کردید، کد را وارد کنید یا بعداً دوباره تلاش کنید.";
            default -> null;
        };
        if (deliveryMessage != null) form.setAttribute("otpDeliveryMessage", deliveryMessage);
        SmsAuthConfig config = SmsAuthConfig.fromModel(context.getAuthenticatorConfig());
        long issuedAt;
        try { issuedAt = Long.parseLong(getSessionNote(context, NOTE_ISSUED_AT)); }
        catch (RuntimeException missing) { issuedAt = Instant.now().getEpochSecond(); }
        long elapsed = Math.max(0, Instant.now().getEpochSecond() - issuedAt);
        form.setAttribute("otpSecondsRemaining", Math.max(0, config.getTtlSeconds() - elapsed))
                .setAttribute("otpCooldownRemaining", Math.max(0, config.getResendCooldownSeconds() - elapsed))
                .setAttribute("unifiedLogin", config.isUnifiedLogin() && !config.isMfaFlow())
                .setAttribute("captchaAvailable", false)
                .setAttribute("captchaRequired", captchaRequired(context, null));
        if (config.isUnifiedLogin() && !config.isMfaFlow()
                && (captchaRequired(context, null)
                    || "true".equals(getSessionNote(context, NOTE_RESEND_CAPTCHA_REQUIRED)))
                && "login".equals(getSessionNote(context, NOTE_FLOW))) {
            try {
                CaptchaChallenge challenge = CaptchaChallenge.create();
                String binding = captchaBinding(context);
                int captchaTtl = config.getCaptchaTtlSeconds();
                long expiresAt = Instant.now().getEpochSecond() + captchaTtl;
                byte[] nonceBytes = new byte[16];
                CAPTCHA_RANDOM.nextBytes(nonceBytes);
                String nonce = HexFormat.of().formatHex(nonceBytes);
                String signature = CaptchaHmac.sign(captchaSecret(), binding, nonce, expiresAt, challenge.answer());
                String record = nonce + ":" + expiresAt + ":" + signature;
                boolean issued = captchaStore != null && captchaStore.issue(binding, trustedClientIp(context), record,
                        captchaTtl, CAPTCHA_RATE_WINDOW_SECONDS,
                        CAPTCHA_MAX_ISSUES_PER_SESSION, CAPTCHA_MAX_ISSUES_PER_IP);
                form.setAttribute("captchaAvailable", issued);
                if (issued) {
                    form.setAttribute("captchaQuestion", challenge.question());
                    form.setAttribute("captchaImage", challenge.imageDataUri());
                }
            } catch (RuntimeException unavailable) {
                context.getEvent().detail("captcha_result", "unavailable").error("authentication_failed");
                form.setAttribute("captchaAvailable", false);
                form.setAttribute("otpMessage", "سرویس تأیید موقتاً در دسترس نیست؛ تا زمان رفع مشکل امکان ادامه ورود وجود ندارد.");
            }
        }
        Response response = form.createForm("login-otp-sms.ftl");
        context.forceChallenge(response);
    }

    private String normalizePhone(String phone, AuthenticationFlowContext context) {
        try {
            return PhoneNormalizer.normalize(phone);
        } catch (IllegalArgumentException e) {
            SmsAuthConfig config = SmsAuthConfig.fromModel(context.getAuthenticatorConfig());
            if (config.isUnifiedLogin() && !config.isMfaFlow()) {
                context.challenge(renderUnifiedLogin(context, config,
                        safeLoginFormData(context.getHttpRequest().getDecodedFormParameters()), "شماره موبایل معتبر وارد کنید"));
                return null;
            }
            context.forceChallenge(Response.ok("شماره موبایل معتبر وارد کنید").build());
            return null;
        }
    }

    private boolean issueOtp(AuthenticationFlowContext context, SmsAuthConfig config, String normalizedPhone, String purpose) {
        UserModel target = config.isMfaFlow() ? context.getAuthenticationSession().getAuthenticatedUser()
                : findUniqueVerifiedUser(context, context.getRealm(), normalizedPhone);
        if (!eligible(context, target) || !matches(normalizedPhone, getVerifiedPhone(target))) {
            context.getEvent().detail("otp_issue", "ineligible").error("authentication_failed");
            return false;
        }
        String otp = OtpGenerator.generate6Digit();
        long now = Instant.now().getEpochSecond();
        int ttl = config.getTtlSeconds();
        long expiry = now + ttl;
        String challengeId = UUID.randomUUID().toString();
        String otpHash;
        try {
            otpHash = OtpHmacUtil.hmac(getHmacSecret(), otpPayload(normalizedPhone, purpose, challengeId, otp, expiry));
            OtpRedisStore.Policy policy = new OtpRedisStore.Policy(ttl, config.getMaxAttempts(),
                    config.getResendCooldownSeconds(), config.getWindowSeconds(), config.getIpHourlySoftLimit(),
                    config.getMobileHourlySoftLimit(), config.getDailyLimit());
            OtpRedisStore.IssueResult result = otpStore.issue(challengeId, normalizedPhone,
                    trustedClientIp(context), otpHash, expiry, policy);
            if (result.status() != OtpRedisStore.IssueStatus.OK) {
                context.getEvent().detail("otp_issue", result.status().name().toLowerCase(java.util.Locale.ROOT))
                        .error("authentication_failed");
                return false;
            }
        } catch (RuntimeException unavailable) {
            context.getEvent().detail("otp_issue", "storage_unavailable").error("authentication_failed");
            return false;
        }
        setSessionNote(context, NOTE_PHONE, normalizedPhone);
        setSessionNote(context, NOTE_CHALLENGE_ID, challengeId);
        setSessionNote(context, NOTE_OTP_ELIGIBLE, "true");
        setSessionNote(context, NOTE_FLOW, purpose);
        setSessionNote(context, NOTE_USER_ID, target.getId());
        setSessionNote(context, NOTE_ISSUED_AT, Long.toString(now));
        SmsSenderService sender;
        try {
            sender = getSmsSenderService(context, config);
        } catch (RuntimeException | LinkageError unavailable) {
            sender = null;
        }
        if (sender == null || (sender instanceof MelliPayamakSmsSenderService melliPayamak
                && !melliPayamak.isOtpConfigured())) {
            setSessionNote(context, NOTE_DELIVERY_STATUS, "not-configured");
            context.getEvent().detail("otp_issue", "provider_not_configured").error("authentication_failed");
            return true;
        }
        try {
            sender.sendOtp(normalizedPhone, otp);
            setSessionNote(context, NOTE_DELIVERY_STATUS, "accepted");
            return true;
        } catch (Exception sendFailure) {
            // A timeout may happen after the gateway accepted the request. Keep
            // the HMAC challenge valid until its normal TTL, so a received code
            // remains usable; no success message is shown for the failed POST.
            setSessionNote(context, NOTE_DELIVERY_STATUS, "failed");
            context.getEvent().detail("otp_issue", "delivery_unavailable").error("authentication_failed");
            return true;
        }
    }

    private boolean verifyOtp(AuthenticationFlowContext context, SmsAuthConfig config, String code) {
        String phone = getSessionNote(context, NOTE_PHONE);
        String challengeId = getSessionNote(context, NOTE_CHALLENGE_ID);
        String purpose = getSessionNote(context, NOTE_FLOW);
        if (phone == null || challengeId == null || purpose == null || code == null) {
            return false;
        }
        try {
            OtpRedisStore.Challenge state = otpStore.readChallenge(challengeId);
            if (state == null) {
                return false;
            }
            if (Instant.now().getEpochSecond() >= state.expiresAt()) {
                return false;
            }
            code = CaptchaHmac.normalize(code);
            boolean validFormat = code.matches("\\d{6}");
            boolean matches = validFormat && OtpHmacUtil.verify(getHmacSecret(), otpPayload(phone, purpose, challengeId, code, state.expiresAt()), state.hash());
            return otpStore.verify(challengeId, state, matches, config.getMaxAttempts()) == OtpRedisStore.VerifyResult.CONSUMED;
        } catch (RuntimeException unavailable) {
            return false;
        }
    }

    private void completeAuthentication(AuthenticationFlowContext context, SmsAuthConfig config) {
        String phone = getSessionNote(context, NOTE_PHONE);
        if (phone == null) {
            context.failure(AuthenticationFlowError.INTERNAL_ERROR);
            return;
        }

        if (config.isMfaFlow()) {
            UserModel user = context.getAuthenticationSession().getAuthenticatedUser();
            if (!eligible(context, user) || !user.getId().equals(getSessionNote(context, NOTE_USER_ID))
                    || !matches(phone, getVerifiedPhone(user))) {
                context.failure(AuthenticationFlowError.INVALID_USER);
                return;
            }
            context.setUser(user);
            context.success();
            return;
        }

        RealmModel realm = context.getRealm();
        UserModel user = findUniqueVerifiedUser(context, realm, phone);
        if (!eligible(context, user) || !user.getId().equals(getSessionNote(context, NOTE_USER_ID))) {
            context.failure(AuthenticationFlowError.INVALID_USER);
            return;
        }
        context.setUser(user);
        context.success();
    }

    private UserModel findUniqueVerifiedUser(AuthenticationFlowContext context, RealmModel realm, String phone) {
        Map<String, UserModel> found = new LinkedHashMap<>();
        for (String attribute : List.of("phoneNumber", "mobile", "phone")) {
            for (String candidate : phoneSearchForms(phone)) {
                try (Stream<UserModel> users = context.getSession().users()
                        .searchForUserByUserAttributeStream(realm, attribute, candidate)) {
                    users.limit(2).filter(user -> matches(phone, user.getFirstAttribute(attribute)))
                            .forEach(user -> found.put(user.getId(), user));
                }
            }
        }
        if (found.size() != 1) return null;
        UserModel user = found.values().iterator().next();
        return "true".equalsIgnoreCase(user.getFirstAttribute("phoneVerified")) ? user : null;
    }

    private List<String> phoneSearchForms(String normalized) {
        String national = normalized.startsWith("98") ? normalized.substring(2) : normalized;
        return List.of(normalized, "+" + normalized, "0" + national);
    }

    private boolean matches(String normalized, String attr) {
        if (attr == null || attr.isBlank()) return false;
        try {
            return PhoneNormalizer.normalize(attr).equals(normalized);
        } catch (Exception e) {
            return attr.replaceAll("[^0-9+]", "").equals(normalized.replaceAll("[^0-9+]", ""));
        }
    }

    private String getVerifiedPhone(UserModel user) {
        String v = user.getFirstAttribute("phoneVerified");
        if (v == null || !"true".equalsIgnoreCase(v)) {
            return null;
        }
        String p = user.getFirstAttribute("phoneNumber");
        if (p == null || p.isBlank()) p = user.getFirstAttribute("mobile");
        if (p == null || p.isBlank()) p = user.getFirstAttribute("phone");
        return p;
    }

    private String trustedClientIp(AuthenticationFlowContext context) {
        // Forwarded headers are intentionally ignored until trusted proxies are established.
        String address = context.getConnection().getRemoteAddr();
        return address == null || address.isBlank() ? "unknown" : address;
    }

    private String otpPayload(String phone, String purpose, String challengeId, String code, long expiry) {
        return phone + "|" + purpose + "|" + challengeId + "|" + code + "|" + expiry;
    }

    private SmsSenderService getSmsSenderService(AuthenticationFlowContext context, SmsAuthConfig config) {
        KeycloakSession session = context.getSession();
        String providerId = config.getSmsProviderId();
        if ("fake-sms-shekarchi".equals(providerId)) {
            return FakeSmsAllowed.allowed() ? session.getProvider(SmsSenderService.class, providerId) : null;
        }
        // Real providers are selected only by explicit authenticator config;
        // each adapter validates its credentials and fails closed at send time.
        return session.getProvider(SmsSenderService.class, providerId);
    }

    private String getHmacSecret() {
        String secret = com.shekarchi.auth.util.SecretValue.get("SHEKARCHI_OTP_HMAC_SECRET");
        if (secret == null || secret.getBytes(java.nio.charset.StandardCharsets.UTF_8).length < 32) {
            throw new IllegalStateException("OTP HMAC secret is missing or too short");
        }
        return secret;
    }

    private void setSessionNote(AuthenticationFlowContext context, String key, String value) {
        context.getAuthenticationSession().setAuthNote(key, value);
    }

    private String getSessionNote(AuthenticationFlowContext context, String key) {
        return context.getAuthenticationSession().getAuthNote(key);
    }

    private String maskPhone(String phone) {
        if (phone == null || phone.length() < 4) return phone;
        return "****" + phone.substring(phone.length() - 4);
    }

    @Override
    public void close() {
    }


    @Override
    public boolean requiresUser() {
        return false;
    }

    @Override
    public boolean configuredFor(KeycloakSession session, RealmModel realm, UserModel user) {
        return true;
    }
    @Override
    public void setRequiredActions(KeycloakSession session, RealmModel realm, UserModel user) {
        // No additional required actions
    }
}
