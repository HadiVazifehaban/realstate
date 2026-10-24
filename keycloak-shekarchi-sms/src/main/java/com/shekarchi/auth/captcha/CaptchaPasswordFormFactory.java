package com.shekarchi.auth.captcha;

import org.keycloak.Config;
import org.keycloak.authentication.Authenticator;
import org.keycloak.authentication.AuthenticatorFactory;
import org.keycloak.models.AuthenticationExecutionModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.provider.ProviderConfigProperty;
import org.keycloak.provider.ProviderConfigurationBuilder;
import com.shekarchi.auth.util.RedisUrlValue;

import java.util.List;

public final class CaptchaPasswordFormFactory implements AuthenticatorFactory {
    private volatile CaptchaChallengeStore store;
    private volatile List<ProviderConfigProperty> properties;

    @Override public String getId() { return CaptchaPasswordForm.PROVIDER_ID; }
    @Override public String getDisplayType() { return "Shekarchi Username Password + CAPTCHA"; }
    @Override public String getHelpText() { return "Standard Keycloak username/password login with a server-validated, one-time challenge."; }
    @Override public String getReferenceCategory() { return "password"; }
    @Override public boolean isConfigurable() { return true; }
    @Override public boolean isUserSetupAllowed() { return false; }

    @Override
    public AuthenticationExecutionModel.Requirement[] getRequirementChoices() {
        return new AuthenticationExecutionModel.Requirement[]{
                AuthenticationExecutionModel.Requirement.REQUIRED,
                AuthenticationExecutionModel.Requirement.ALTERNATIVE,
                AuthenticationExecutionModel.Requirement.DISABLED
        };
    }

    @Override
    public List<ProviderConfigProperty> getConfigProperties() {
        if (properties == null) {
            properties = ProviderConfigurationBuilder.create()
                    .property()
                    .name("captcha.ttl-seconds")
                    .label("CAPTCHA TTL (seconds)")
                    .type(ProviderConfigProperty.STRING_TYPE)
                    .defaultValue("120")
                    .helpText("Challenge lifetime; valid range is 1-600 seconds.")
                    .add()
                    .build();
        }
        return properties;
    }

    @Override
    public Authenticator create(KeycloakSession session) {
        return new CaptchaPasswordForm(getStore());
    }

    private CaptchaChallengeStore getStore() {
        CaptchaChallengeStore current = store;
        if (current != null) return current;
        synchronized (this) {
            if (store == null) {
                store = new CaptchaChallengeStore(RedisUrlValue.get(),
                        System.getenv("SHEKARCHI_CAPTCHA_REDIS_PREFIX"));
            }
            return store;
        }
    }

    @Override public void init(Config.Scope config) {}
    @Override public void postInit(KeycloakSessionFactory factory) {}

    @Override
    public void close() {
        CaptchaChallengeStore current = store;
        store = null;
        if (current != null) current.close();
    }
}
