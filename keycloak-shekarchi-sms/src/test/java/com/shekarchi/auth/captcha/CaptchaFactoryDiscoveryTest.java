package com.shekarchi.auth.captcha;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.*;

class CaptchaFactoryDiscoveryTest {
    private static final String SERVICE_FILE = "META-INF/services/org.keycloak.authentication.AuthenticatorFactory";

    @Test
    void factoryIdAndServiceDescriptorAreRegistered() throws IOException {
        assertEquals("shekarchi-captcha-password-form", new CaptchaPasswordFormFactory().getId());
        try (var stream = getClass().getClassLoader().getResourceAsStream(SERVICE_FILE)) {
            assertNotNull(stream);
            String descriptor = new String(stream.readAllBytes(), StandardCharsets.UTF_8);
            assertTrue(descriptor.contains("com.shekarchi.auth.captcha.CaptchaPasswordFormFactory"));
        }
    }
}
