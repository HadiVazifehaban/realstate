package com.shekarchi.auth.captcha;

import jakarta.ws.rs.core.MultivaluedHashMap;
import jakarta.ws.rs.core.MultivaluedMap;
import jakarta.ws.rs.core.Response;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.authentication.AuthenticationFlowError;
import org.keycloak.authentication.authenticators.browser.UsernamePasswordForm;
import org.keycloak.models.AuthenticatorConfigModel;

import java.security.SecureRandom;
import java.time.Instant;
import java.util.HexFormat;

/** Keycloak's standard username/password authenticator with an additional server-verified challenge. */
public final class CaptchaPasswordForm extends UsernamePasswordForm {
    public static final String PROVIDER_ID = "shekarchi-captcha-password-form";
    private static final String NOTE_CHALLENGE = "SHEKARCHI_CAPTCHA_RECORD";
    private static final int DEFAULT_TTL_SECONDS = 120;
    private static final int RATE_WINDOW_SECONDS = 900;
    private static final int MAX_ISSUES_PER_SESSION = 12;
    private static final int MAX_ISSUES_PER_IP = 60;
    private static final int MAX_SUBMISSIONS_PER_SESSION = 6;
    private static final int MAX_SUBMISSIONS_PER_IP = 30;
    private static final SecureRandom RANDOM = new SecureRandom();

    private final CaptchaChallengeStore store;

    public CaptchaPasswordForm(CaptchaChallengeStore store) {
        this.store = store;
    }

    @Override
    public void action(AuthenticationFlowContext context) {
        MultivaluedMap<String, String> formData = context.getHttpRequest().getDecodedFormParameters();
        if (formData.containsKey("cancel")) {
            super.action(context);
            return;
        }

        if (formData.containsKey("captchaRefresh")) {
            context.challenge(renderChallenge(context, safeFormData(formData), null));
            return;
        }

        String binding = sessionBinding(context);
        String ip = remoteAddress(context);
        CaptchaChallengeStore.ConsumeResult consumed;
        boolean valid;
        try {
            consumed = store.consume(binding, ip, RATE_WINDOW_SECONDS,
                    MAX_SUBMISSIONS_PER_SESSION, MAX_SUBMISSIONS_PER_IP);
            String answer = formData.getFirst("captchaAnswer");
            valid = !consumed.rateLimited() && consumed.record() != null
                    && CaptchaHmac.verify(hmacSecret(), binding, consumed.record(), answer);
        } catch (RuntimeException unavailable) {
            context.getEvent().detail("captcha_result", "unavailable").error("authentication_failed");
            context.failure(AuthenticationFlowError.INTERNAL_ERROR);
            return;
        }

        context.getAuthenticationSession().removeAuthNote(NOTE_CHALLENGE);
        if (!valid) {
            context.getEvent().detail("captcha_result", consumed.rateLimited() ? "rate_limited" : "invalid")
                    .error("invalid_user_credentials");
            context.failureChallenge(AuthenticationFlowError.INVALID_CREDENTIALS,
                    renderChallenge(context, safeFormData(formData), "captchaInvalid"));
            return;
        }

        // Keep Keycloak's normal user lookup, password verification and brute-force handling.
        super.action(context);
    }

    @Override
    protected Response challenge(AuthenticationFlowContext context, MultivaluedMap<String, String> formData) {
        return renderChallenge(context, safeFormData(formData), null);
    }

    private Response renderChallenge(AuthenticationFlowContext context,
                                      MultivaluedMap<String, String> formData, String errorKey) {
        var form = context.form();
        if (!formData.isEmpty()) form.setFormData(formData);
        if (errorKey != null) form.setError(errorKey);

        String binding = sessionBinding(context);
        String ip = remoteAddress(context);
        try {
            CaptchaChallenge challenge = CaptchaChallenge.create();
            long expiresAt = Instant.now().getEpochSecond() + ttlSeconds(context);
            String nonce = randomNonce();
            String signature = CaptchaHmac.sign(hmacSecret(), binding, nonce, expiresAt, challenge.answer());
            String record = nonce + ":" + expiresAt + ":" + signature;
            if (!store.issue(binding, ip, record, ttlSeconds(context), RATE_WINDOW_SECONDS,
                    MAX_ISSUES_PER_SESSION, MAX_ISSUES_PER_IP)) {
                context.getAuthenticationSession().removeAuthNote(NOTE_CHALLENGE);
                return form.setError("captchaRateLimited")
                        .setAttribute("captchaAvailable", false)
                        .createLoginUsernamePassword();
            }
            context.getAuthenticationSession().setAuthNote(NOTE_CHALLENGE, "issued");
            return form.setAttribute("captchaAvailable", true)
                    .setAttribute("captchaQuestion", challenge.question())
                    .setAttribute("captchaImage", challenge.imageDataUri())
                    .createLoginUsernamePassword();
        } catch (RuntimeException unavailable) {
            context.getAuthenticationSession().removeAuthNote(NOTE_CHALLENGE);
            return form.setError("captchaServiceUnavailable")
                    .setAttribute("captchaAvailable", false)
                    .createLoginUsernamePassword();
        }
    }

    private static MultivaluedMap<String, String> safeFormData(MultivaluedMap<String, String> formData) {
        MultivaluedMap<String, String> safe = new MultivaluedHashMap<>();
        copy(formData, safe, "username");
        copy(formData, safe, "rememberMe");
        copy(formData, safe, "credentialId");
        return safe;
    }

    private static void copy(MultivaluedMap<String, String> from, MultivaluedMap<String, String> to, String key) {
        String value = from.getFirst(key);
        if (value != null) to.putSingle(key, value);
    }

    private static String sessionBinding(AuthenticationFlowContext context) {
        var session = context.getAuthenticationSession();
        return session.getParentSession().getId() + ":" + session.getTabId();
    }

    private static String remoteAddress(AuthenticationFlowContext context) {
        String address = context.getConnection().getRemoteAddr();
        return address == null || address.isBlank() ? "unknown" : address;
    }

    private static String randomNonce() {
        byte[] bytes = new byte[16];
        RANDOM.nextBytes(bytes);
        return HexFormat.of().formatHex(bytes);
    }

    private static String hmacSecret() {
        String secret = com.shekarchi.auth.util.SecretValue.get("SHEKARCHI_CAPTCHA_HMAC_SECRET");
        if (secret == null || secret.length() < 32) {
            throw new IllegalStateException("CAPTCHA HMAC secret is unavailable");
        }
        return secret;
    }

    private static int ttlSeconds(AuthenticationFlowContext context) {
        AuthenticatorConfigModel model = context.getAuthenticatorConfig();
        if (model == null || model.getConfig() == null) return DEFAULT_TTL_SECONDS;
        try {
            int ttl = Integer.parseInt(model.getConfig().getOrDefault("captcha.ttl-seconds", "" + DEFAULT_TTL_SECONDS));
            return Math.max(1, Math.min(ttl, 600));
        } catch (NumberFormatException invalid) {
            return DEFAULT_TTL_SECONDS;
        }
    }
}
