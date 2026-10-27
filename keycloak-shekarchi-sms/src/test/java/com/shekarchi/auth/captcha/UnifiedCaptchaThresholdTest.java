package com.shekarchi.auth.captcha;

import jakarta.ws.rs.core.MultivaluedHashMap;
import org.junit.jupiter.api.Test;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.forms.login.LoginFormsProvider;
import org.keycloak.http.HttpRequest;
import org.keycloak.models.AuthenticationExecutionModel;
import org.keycloak.sessions.AuthenticationSessionModel;
import org.keycloak.sessions.RootAuthenticationSessionModel;

import java.lang.reflect.Proxy;
import java.util.HashMap;
import java.util.Map;
import java.util.function.BiFunction;

import static org.junit.jupiter.api.Assertions.*;

class UnifiedCaptchaThresholdTest {
    protected final Map<String, String> notes = new HashMap<>();
    protected final Map<String, Object> attributes = new HashMap<>();
    protected final MultivaluedHashMap<String, String> input = new MultivaluedHashMap<>();
    private final UnifiedForm authenticator = new UnifiedForm();

    private static class UnifiedForm extends com.shekarchi.auth.authenticator.SmsAuthenticator {
        UnifiedForm() { super(null, null); }
        void render(AuthenticationFlowContext context, jakarta.ws.rs.core.MultivaluedMap<String, String> data) {
            super.challenge(context, data);
        }
        void fail(AuthenticationFlowContext context) {
            super.challenge(context, "invalidUserMessage", "password");
        }
    }

    @Test
    void thirdFailureRequiresCaptchaWithoutNativeFailureTracking() {
        var context = context();
        input.putSingle("username", "unknown-user");
        input.putSingle("password", "incorrect");
        authenticator.render(context, input);
        assertEquals(false, attributes.get("captchaRequired"));
        for (int attempt = 1; attempt <= 3; attempt++) {
            authenticator.fail(context);
            assertEquals(attempt >= 3, attributes.get("captchaRequired"));
        }
        assertEquals(false, attributes.get("captchaAvailable"));
        assertEquals("true", notes.get("SHEKARCHI_LOGIN_CAPTCHA_REQUIRED"));
    }

    @Test
    void requiredCaptchaSurvivesRefreshAndAccountSwitch() {
        notes.put("SHEKARCHI_LOGIN_CAPTCHA_REQUIRED", "true");
        input.putSingle("username", "another-user");
        input.putSingle("captchaRefresh", "1");
        authenticator.action(context());
        assertEquals(true, attributes.get("captchaRequired"));
        input.remove("captchaRefresh");
        authenticator.render(context(), input);
        assertEquals(true, attributes.get("captchaRequired"));
        assertEquals(false, attributes.get("captchaAvailable"));
    }

    @Test
    void emptyPasswordDoesNotIncrementFailedPasswordAttempts() {
        authenticator.fail(context());
        assertFalse(notes.containsKey("SHEKARCHI_LOGIN_FAILED_ATTEMPTS"));
        assertEquals(false, attributes.get("captchaRequired"));
    }

    protected AuthenticationFlowContext context() {
        var root = proxy(RootAuthenticationSessionModel.class, (name, args) -> "getId".equals(name) ? "root" : null);
        var session = proxy(AuthenticationSessionModel.class, (name, args) -> {
            switch (name) {
                case "getAuthNote": return notes.get(args[0]);
                case "setAuthNote": notes.put((String) args[0], (String) args[1]); return null;
                case "removeAuthNote": notes.remove(args[0]); return null;
                case "getParentSession": return root;
                case "getTabId": return "tab";
                default: return null;
            }
        });
        var request = proxy(HttpRequest.class, (name, args) -> input);
        var form = proxy(LoginFormsProvider.class, (name, args) -> {
            if ("setAttribute".equals(name)) attributes.put((String) args[0], args[1]);
            return null;
        });
        return proxy(AuthenticationFlowContext.class, (name, args) -> {
            switch (name) {
                case "getSession": return proxy(org.keycloak.models.KeycloakSession.class, (method, values) ->
                        "users".equals(method) ? proxy(org.keycloak.models.UserProvider.class, (lookup, params) -> null) : null);
                case "getAuthenticationSession": return session;
                case "getHttpRequest": return request;
                case "form": return form;
                case "getExecution": return new AuthenticationExecutionModel();
                case "getConnection": return proxy(org.keycloak.common.ClientConnection.class,
                        (method, values) -> "198.51.100.1");
                default: return null;
            }
        });
    }

    private static <T> T proxy(Class<T> type, BiFunction<String, Object[], Object> handler) {
        return type.cast(Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[]{type}, (self, method, args) -> {
            Object result = handler.apply(method.getName(), args);
            return result == null && method.getReturnType().isInstance(self) ? self : result;
        }));
    }
}