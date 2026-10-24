package com.shekarchi.auth.authenticator;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SmsAuthenticatorFactoryDiscoveryTest {
    private static final String SERVICE_FILE =
            "META-INF/services/org.keycloak.authentication.AuthenticatorFactory";

    @Test
    void factoryIdMatchesTheRealmExecutionId() {
        assertEquals("shekarchi-sms-authenticator", new SmsAuthenticatorFactory().getId());
    }

    @Test
    void serviceLoaderDescriptorRegistersTheFactory() throws IOException {
        try (var stream = getClass().getClassLoader().getResourceAsStream(SERVICE_FILE)) {
            assertTrue(stream != null, "AuthenticatorFactory service descriptor must be packaged");
            String descriptor = new String(stream.readAllBytes(), StandardCharsets.UTF_8);
            assertTrue(descriptor.lines().map(String::trim)
                    .anyMatch(SmsAuthenticatorFactory.class.getName()::equals));
        }
    }
}
