package com.shekarchi.auth.authenticator;

import org.keycloak.Config;
import org.keycloak.authentication.Authenticator;
import org.keycloak.authentication.AuthenticatorFactory;
import org.keycloak.models.AuthenticationExecutionModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.provider.ProviderConfigProperty;
import org.keycloak.provider.ProviderConfigurationBuilder;
import com.shekarchi.auth.otp.OtpRedisStore;
import com.shekarchi.auth.captcha.CaptchaChallengeStore;
import com.shekarchi.auth.util.RedisUrlValue;

import java.util.List;

public class SmsAuthenticatorFactory implements AuthenticatorFactory {
    public static final String ID = "shekarchi-sms-authenticator";
    public static final String DISPLAY_TYPE = "Shekarchi SMS OTP Authenticator";
    public static final String HELP_TEXT = "SMS OTP authentication for Shekarchi (Passwordless & MFA)";
    private List<ProviderConfigProperty> configProperties;
    private volatile OtpRedisStore otpRedisStore;
    private volatile CaptchaChallengeStore captchaChallengeStore;

    @Override
    public String getDisplayType() {
        return DISPLAY_TYPE;
    }

    @Override
    public String getReferenceCategory() {
        return "otp";
    }

    @Override
    public boolean isConfigurable() {
        return true;
    }

    @Override
    public AuthenticationExecutionModel.Requirement[] getRequirementChoices() {
        return new AuthenticationExecutionModel.Requirement[]{
                AuthenticationExecutionModel.Requirement.REQUIRED,
                AuthenticationExecutionModel.Requirement.ALTERNATIVE,
                AuthenticationExecutionModel.Requirement.CONDITIONAL,
                AuthenticationExecutionModel.Requirement.DISABLED
        };
    }

    @Override
    public boolean isUserSetupAllowed() {
        return false;
    }

    @Override
    public String getHelpText() {
        return HELP_TEXT;
    }

    @Override
    public List<ProviderConfigProperty> getConfigProperties() {
        if (configProperties == null) {
            configProperties = ProviderConfigurationBuilder.create()
                    .property()
                    .name("flow.type")
                    .label("Flow Type")
                    .type(ProviderConfigProperty.LIST_TYPE)
                    .options("PASSWORDLESS", "MFA")
                    .defaultValue("PASSWORDLESS")
                    .helpText("PASSWORDLESS for mobile OTP login, MFA for second factor after password")
                    .add()
                    .property()
                    .name("ui.unified-login")
                    .label("Unified Password + SMS Login UI")
                    .type(ProviderConfigProperty.BOOLEAN_TYPE)
                    .defaultValue("true")
                    .helpText("Testable combined SHEKARCHI login tabs with server-validated CAPTCHA.")
                    .add()
                    .property()
                    .name("captcha.ttl-seconds")
                    .label("CAPTCHA TTL (seconds)")
                    .type(ProviderConfigProperty.STRING_TYPE)
                    .defaultValue("120")
                    .helpText("Lifetime for the phone/password challenge; valid range is 1-600 seconds.")
                    .add()
                    .property()
                    .name("otp.ttl-seconds")
                    .label("OTP TTL (seconds)")
                    .type(ProviderConfigProperty.STRING_TYPE)
                    .defaultValue("120")
                    .add()
                    .property()
                    .name("otp.max-attempts")
                    .label("Max failed attempts")
                    .type(ProviderConfigProperty.STRING_TYPE)
                    .defaultValue("3")
                    .add()
                    .property()
                    .name("otp.resend-cooldown-seconds")
                    .label("Resend cooldown (seconds)")
                    .type(ProviderConfigProperty.STRING_TYPE)
                    .defaultValue("120")
                    .add()
                    .property()
                    .name("otp.daily-max-per-mobile")
                    .label("Daily SMS limit per mobile")
                    .type(ProviderConfigProperty.STRING_TYPE)
                    .defaultValue("15")
                    .add()
                    .property()
                    .name("otp.rate-window-seconds")
                    .label("Rate limit window (seconds)")
                    .type(ProviderConfigProperty.STRING_TYPE)
                    .defaultValue("3600")
                    .add()
                    .property()
                    .name("otp.ip-hourly-soft-limit")
                    .label("IP hourly soft threshold")
                    .type(ProviderConfigProperty.STRING_TYPE)
                    .defaultValue("5")
                    .add()
                    .property()
                    .name("otp.mobile-hourly-soft-limit")
                    .label("Mobile hourly soft threshold")
                    .type(ProviderConfigProperty.STRING_TYPE)
                    .defaultValue("5")
                    .add()
                    .property()
                    .name("sms.provider-id")
                    .label("SMS Provider ID")
                    .type(ProviderConfigProperty.STRING_TYPE)
                    .defaultValue("melli-payamak")
                    .add()
                    .build();
        }
        return configProperties;
    }

    @Override
    public Authenticator create(KeycloakSession session) {
        OtpRedisStore store = otpRedisStore;
        if (store == null) {
            synchronized (this) {
                if (otpRedisStore == null) otpRedisStore = newStoreFromEnvironment();
                store = otpRedisStore;
            }
        }
        return new SmsAuthenticator(store, getCaptchaStore());
    }

    @Override
    public void init(Config.Scope config) {
    }

    @Override
    public void postInit(KeycloakSessionFactory factory) {
        if (otpRedisStore == null) otpRedisStore = newStoreFromEnvironment();
    }

    @Override
    public void close() {
        OtpRedisStore store = otpRedisStore;
        otpRedisStore = null;
        if (store != null) store.close();
        CaptchaChallengeStore captcha = captchaChallengeStore;
        captchaChallengeStore = null;
        if (captcha != null) captcha.close();
    }

    @Override
    public String getId() {
        return ID;
    }

    private OtpRedisStore newStoreFromEnvironment() {
        return new OtpRedisStore(RedisUrlValue.get(), System.getenv("SHEKARCHI_OTP_REDIS_PREFIX"));
    }

    private CaptchaChallengeStore getCaptchaStore() {
        CaptchaChallengeStore store = captchaChallengeStore;
        if (store == null) {
            synchronized (this) {
                if (captchaChallengeStore == null) {
                    captchaChallengeStore = new CaptchaChallengeStore(RedisUrlValue.get(),
                            System.getenv("SHEKARCHI_CAPTCHA_REDIS_PREFIX"));
                }
                store = captchaChallengeStore;
            }
        }
        return store;
    }
}
