package com.shekarchi.auth.sms;

import org.keycloak.provider.Provider;

public interface SmsSenderService extends Provider {
    /**
     * Send SMS to phoneNumber with message/templateCode.
     * Must throw SmsException on any failure.
     */
    void sendSms(String phoneNumber, String message, String templateCode) throws SmsException;

    /** Send an OTP without allowing an adapter to generate or replace its value. */
    default void sendOtp(String phoneNumber, String code) throws SmsException {
        sendSms(phoneNumber, "کد تایید: " + code, null);
    }

    @Override
    default void close() {
    }
}
