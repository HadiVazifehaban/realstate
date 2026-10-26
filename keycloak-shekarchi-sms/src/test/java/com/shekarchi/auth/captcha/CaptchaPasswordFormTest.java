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

class CaptchaPasswordFormTest {
    private final Map<String, String> notes = new HashMap<>();
    private final Map<String, Object> attributes = new HashMap<>();
    private final MultivaluedHashMap<String, String> input = new MultivaluedHashMap<>();
    private final CaptchaPasswordForm authenticator = new CaptchaPasswordForm(null);

    @Test
    void thirdFailureRequiresCaptchaWithoutNativeFailureTracking() {
        var context = context();
        input.putSingle("username", "unknown-user");
        input.putSingle("password", "incorrect");
        authenticator.challenge(context, input);
        assertEquals(false, attributes.get("captchaRequired"));
        for (int attempt = 1; attempt <= 3; attempt++) {
            authenticator.challenge(context, "invalidUserMessage", "password");
            assertEquals(attempt >= 3, attributes.get("captchaRequired"));
        }
        assertEquals(false, attributes.get("captchaAvailable"));
        assertEquals("true", notes.get("SHEKARCHI_PASSWORD_CAPTCHA_REQUIRED"));
    }

    @Test
    void requiredCaptchaSurvivesRefreshAndAccountSwitch() {
        notes.put("SHEKARCHI_PASSWORD_CAPTCHA_REQUIRED", "true");
        input.putSingle("username", "another-user");
        input.putSingle("captchaRefresh", "1");
        authenticator.action(context());
        assertEquals(true, attributes.get("captchaRequired"));
        input.remove("captchaRefresh");
        authenticator.challenge(context(), input);
        assertEquals(true, attributes.get("captchaRequired"));
        assertEquals(false, attributes.get("captchaAvailable"));
    }

    @Test
    void emptyPasswordDoesNotIncrementFailedPasswordAttempts() {
        authenticator.challenge(context(), "invalidUserMessage", "password");
        assertFalse(notes.containsKey("SHEKARCHI_PASSWORD_FAILURES"));
        assertEquals(false, attributes.get("captchaRequired"));
    }

    private AuthenticationFlowContext context() {
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