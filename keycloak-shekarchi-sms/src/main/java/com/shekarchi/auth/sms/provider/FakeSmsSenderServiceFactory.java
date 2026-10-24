package com.shekarchi.auth.sms.provider;

import com.shekarchi.auth.sms.SmsSenderService;
import com.shekarchi.auth.sms.SmsSenderServiceFactory;
import org.keycloak.Config;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.provider.ProviderConfigProperty;
import org.keycloak.provider.ProviderConfigurationBuilder;

import java.util.List;

public class FakeSmsSenderServiceFactory implements SmsSenderServiceFactory {
    public static final String ID = "fake-sms-shekarchi";
    private List<ProviderConfigProperty> configProperties;

    @Override
    public SmsSenderService create(KeycloakSession session) {
        return new FakeSmsSenderService(this);
    }

    @Override
    public void init(Config.Scope config) {
    }

    @Override
    public void postInit(KeycloakSessionFactory factory) {
    }

    @Override
    public void close() {
    }

    @Override
    public String getId() {
        return ID;
    }

    public List<ProviderConfigProperty> getConfigProperties() {
        if (configProperties == null) {
            configProperties = ProviderConfigurationBuilder.create()
                    .property()
                    .name("dev-test-channel")
                    .label("Show Code Channel (dev only)")
                    .type(ProviderConfigProperty.STRING_TYPE)
                    .helpText("کد تولیدشده فقط در محیط تست از طریق این کانال قابل‌دسترس است. در Production غیرفعال است.")
                    .add()
                    .build();
        }
        return configProperties;
    }

    public boolean isFakeMode() {
        return FakeSmsAllowed.allowed();
    }
}
