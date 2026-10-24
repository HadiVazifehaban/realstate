package com.shekarchi.auth.sms.provider;

import com.shekarchi.auth.sms.SmsSenderService;
import com.shekarchi.auth.sms.SmsSenderServiceFactory;
import org.keycloak.Config;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
public class MelliPayamakSmsSenderServiceFactory implements SmsSenderServiceFactory {
    public static final String ID = "melli-payamak";

    @Override
    public SmsSenderService create(KeycloakSession session) {
        return new MelliPayamakSmsSenderService(this);
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
}
