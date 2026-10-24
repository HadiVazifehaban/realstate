package com.shekarchi.auth.sms.provider;

import com.shekarchi.auth.sms.SmsSenderService;
import com.shekarchi.auth.sms.SmsSenderServiceFactory;
import org.keycloak.Config;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.provider.ProviderConfigProperty;
import org.keycloak.provider.ProviderConfigurationBuilder;

import java.util.List;

public class KavenegarSmsSenderServiceFactory implements SmsSenderServiceFactory {
    public static final String ID = "kavenegar-shekarchi";

    @Override
    public SmsSenderService create(KeycloakSession session) {
        return new KavenegarSmsSenderService(this);
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
        return ProviderConfigurationBuilder.create()
                .property().name("api-key").label("API Key").type(ProviderConfigProperty.PASSWORD).add()
                .property().name("endpoint").label("API Endpoint").type(ProviderConfigProperty.STRING_TYPE).defaultValue("https://api.kavenegar.com/v1").add()
                .property().name("from").label("Sender Number").type(ProviderConfigProperty.STRING_TYPE).add()
                .property().name("timeout-ms").label("Timeout (ms)").type(ProviderConfigProperty.STRING_TYPE).defaultValue("5000").add()
                .property().name("template-code").label("Template Code").type(ProviderConfigProperty.STRING_TYPE).add()
                .build();
    }
}
