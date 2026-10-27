package com.shekarchi.auth.captcha;

import jakarta.ws.rs.core.MultivaluedHashMap;
import jakarta.ws.rs.core.MultivaluedMap;
import jakarta.ws.rs.core.Response;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.authentication.AuthenticationFlowError;
import org.keycloak.authentication.authenticators.browser.UsernamePasswordForm;
import org.keycloak.forms.login.LoginFormsProvider;
import org.keycloak.models.AuthenticatorConfigModel;
import org.keycloak.models.utils.FormMessage;
import org.keycloak.models.utils.KeycloakModelUtils;

import java.security.SecureRandom;
import java.time.Instant;
import java.util.HexFormat;

/** Keycloak's standard username/password authenticator with an additional server-verified challenge. */
public final class CaptchaPasswordForm extends UsernamePasswordForm {
    public static final String PROVIDER_ID = "shekarchi-captcha-password-form";
    private static final String NOTE_CHALLENGE = "SHEKARCHI_CAPTCHA_RECORD";
    private static final String NOTE_FAILURES = "SHEKARCHI_PASSWORD_FAILURES";
    private static final String NOTE_REQUIRED = "SHEKARCHI_PASSWORD_CAPTCHA_REQUIRED";
    private static final int CAPTCHA_AFTER_FAILURES = 3;
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
            MultivaluedMap<String, String> safe = safeFormData(formData);
            if (captchaRequired(context, safe)) {
                context.challenge(renderChallenge(context, safe, null));
            } else {
                context.challenge(renderPasswordForm(context, safe, null));
            }
            return;
        }

        if (!captchaRequired(context, formData)) {
            context.getAuthenticationSession().removeAuthNote(NOTE_CHALLENGE);
            super.action(context);
            return;
        }

        if (store == null) {
            context.getEvent().detail("captcha_result", "unavailable").error("authentication_failed");
            context.failure(AuthenticationFlowError.INTERNAL_ERROR);
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
        context.getEvent().detail("captcha_result", "valid");
        super.action(context);
    }

    @Override
    protected boolean validateForm(AuthenticationFlowContext context, MultivaluedMap<String, String> formData) {
        boolean valid = super.validateForm(context, formData);
        if (valid) {
            context.getAuthenticationSession().removeAuthNote(NOTE_FAILURES);
            context.getAuthenticationSession().removeAuthNote(NOTE_REQUIRED);
            context.getAuthenticationSession().removeAuthNote(NOTE_CHALLENGE);
        }
        return valid;
    }

    @Override
    protected Response challenge(AuthenticationFlowContext context, String error, String field) {
        var submitted = context.getHttpRequest().getDecodedFormParameters();
        String password = submitted.getFirst("password");
        if (error != null && password != null && !password.isEmpty()) {
            // Keycloak renders this response before recording the native failure.
            // A session count also covers unknown users and realms without brute-force protection.
            int failures = Math.max(failedAttempts(context), accountFailures(context, submitted));
            context.getAuthenticationSession().setAuthNote(NOTE_FAILURES,
                    Integer.toString(Math.min(failures + 1, 100)));
        }
        var form = context.form().setExecution(context.getExecution().getId());
        if (error != null) {
            if (field != null) form.addError(new FormMessage(field, error));
            else form.setError(error);
        }
        var safe = safeFormData(submitted);
        return captchaRequired(context, safe)
                ? renderChallenge(context, safe, null, form)
                : renderPasswordForm(context, safe, null, form);
    }

    @Override
    protected Response challenge(AuthenticationFlowContext context, MultivaluedMap<String, String> formData) {
        MultivaluedMap<String, String> safe = safeFormData(formData);
        if (captchaRequired(context, safe)) {
            return renderChallenge(context, safe, null);
        }
        return renderPasswordForm(context, safe, null);
    }

    private boolean captchaRequired(AuthenticationFlowContext context, MultivaluedMap<String, String> formData) {
        return "true".equals(context.getAuthenticationSession().getAuthNote(NOTE_REQUIRED))
                || isCaptchaRequired(Math.max(failedAttempts(context), accountFailures(context, formData)));
    }

    private int failedAttempts(AuthenticationFlowContext context) {
        try {
            return Math.max(0, Integer.parseInt(context.getAuthenticationSession().getAuthNote(NOTE_FAILURES)));
        } catch (NumberFormatException missingOrInvalid) {
            return 0;
        }
    }

    private int accountFailures(AuthenticationFlowContext context, MultivaluedMap<String, String> formData) {
        String username = formData == null ? null : formData.getFirst("username");
        try {
            var user = isUserAlreadySetBeforeUsernamePasswordAuth(context) ? context.getUser() : null;
            if (user == null && username != null && !username.isBlank())
                user = KeycloakModelUtils.findUserByNameOrEmail(context.getSession(), context.getRealm(), username.trim());
            if (user != null) {
                var failure = context.getSession().loginFailures().getUserLoginFailure(context.getRealm(), user.getId());
                return failure == null ? 0 : failure.getNumFailures();
            }
        } catch (RuntimeException unavailable) {
            // Do not expose account lookup failures through a CAPTCHA decision.
        }
        return 0;
    }

    private Response renderPasswordForm(AuthenticationFlowContext context,
                                        MultivaluedMap<String, String> formData, String errorKey) {
        return renderPasswordForm(context, formData, errorKey, context.form());
    }

    private Response renderPasswordForm(AuthenticationFlowContext context,
                                        MultivaluedMap<String, String> formData, String errorKey,
                                        LoginFormsProvider form) {
        if (formData != null && !formData.isEmpty()) form.setFormData(formData);
        if (errorKey != null) form.setError(errorKey);
        return form.setAttribute("captchaRequired", false)
                .setAttribute("captchaAvailable", false)
                .createLoginUsernamePassword();
    }

    private Response renderChallenge(AuthenticationFlowContext context,
                                      MultivaluedMap<String, String> formData, String errorKey) {
        return renderChallenge(context, formData, errorKey, context.form());
    }

    private Response renderChallenge(AuthenticationFlowContext context,
                                      MultivaluedMap<String, String> formData, String errorKey,
                                      LoginFormsProvider form) {
        if (!formData.isEmpty()) form.setFormData(formData);
        if (errorKey != null) form.setError(errorKey);
        form.setAttribute("captchaRequired", true);
        context.getAuthenticationSession().setAuthNote(NOTE_REQUIRED, "true");

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
                        .setAttribute("captchaRequired", true)
                        .setAttribute("captchaAvailable", false)
                        .createLoginUsernamePassword();
            }
            context.getAuthenticationSession().setAuthNote(NOTE_CHALLENGE, "issued");
            return form.setAttribute("captchaRequired", true)
                    .setAttribute("captchaAvailable", true)
                    .setAttribute("captchaQuestion", challenge.question())
                    .setAttribute("captchaImage", challenge.imageDataUri())
                    .createLoginUsernamePassword();
        } catch (RuntimeException unavailable) {
            context.getAuthenticationSession().removeAuthNote(NOTE_CHALLENGE);
            return form.setError("captchaServiceUnavailable")
                    .setAttribute("captchaRequired", true)
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

    static boolean isCaptchaRequired(long accountFailures) {
        return accountFailures >= CAPTCHA_AFTER_FAILURES;
    }
}
