package com.shekarchi.auth.sms;

import org.keycloak.provider.Provider;
import org.keycloak.provider.ProviderFactory;
import org.keycloak.provider.Spi;

public class SmsSpi implements Spi {
    public static final String ID = "shekarchi-sms";

    @Override
    public boolean isInternal() {
        return false;
    }

    @Override
    public String getName() {
        return ID;
    }

    @Override
    public Class<? extends Provider> getProviderClass() {
        return SmsSenderService.class;
    }

    @Override
    public Class<? extends ProviderFactory<SmsSenderService>> getProviderFactoryClass() {
        return SmsSenderServiceFactory.class;
    }
}
