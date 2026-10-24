package com.shekarchi.auth.sms.provider;

import com.shekarchi.auth.sms.SmsException;
import com.shekarchi.auth.sms.SmsSenderService;

public class FarazSmsSenderService implements SmsSenderService {
    private final FarazSmsSenderServiceFactory factory;

    public FarazSmsSenderService(FarazSmsSenderServiceFactory factory) {
        this.factory = factory;
    }

    @Override
    public void sendSms(String phoneNumber, String message, String templateCode) throws SmsException {
        String apiKey = getConfig("api-key");
        if (apiKey == null || apiKey.isBlank()) {
            throw new SmsException("SMS provider configuration missing");
        }
        // Stub - fail closed by default; implement per provider API
        throw new SmsException("FarazSMS provider not fully configured");
    }

    private String getConfig(String key) {
        String env = System.getenv("SHEKARCHI_SMS_" + key.toUpperCase().replace('-', '_'));
        return env;
    }

    @Override
    public void close() {
    }
}
