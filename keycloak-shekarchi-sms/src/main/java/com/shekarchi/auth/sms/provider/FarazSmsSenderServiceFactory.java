package com.shekarchi.auth.sms.provider;

import com.shekarchi.auth.sms.SmsSenderService;
import com.shekarchi.auth.sms.SmsSenderServiceFactory;
import org.keycloak.Config;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.provider.ProviderConfigProperty;
import org.keycloak.provider.ProviderConfigurationBuilder;

import java.util.List;

public class FarazSmsSenderServiceFactory implements SmsSenderServiceFactory {
    public static final String ID = "faraz-sms";

    @Override
    public SmsSenderService create(KeycloakSession session) {
        return new FarazSmsSenderService(this);
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
                .property().name("endpoint").label("Endpoint").type(ProviderConfigProperty.STRING_TYPE).defaultValue("https://api.ippanel.com").add()
                .property().name("from").label("From").type(ProviderConfigProperty.STRING_TYPE).add()
                .property().name("timeout-ms").label("Timeout (ms)").type(ProviderConfigProperty.STRING_TYPE).defaultValue("5000").add()
                .build();
    }
}
