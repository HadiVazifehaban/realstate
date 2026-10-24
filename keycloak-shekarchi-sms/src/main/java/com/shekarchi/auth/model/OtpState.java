package com.shekarchi.auth.model;

import java.io.Serializable;

public class OtpState implements Serializable {
    private static final long serialVersionUID = 1L;

    private final String otpHash;
    private final String phoneNormalized;
    private final long expiryEpoch;
    private final int attempts;
    private final long lastSentEpoch;
    private final int resendCount;
    private final long windowStartEpoch;
    private final boolean consumed;

    public OtpState(String otpHash, String phoneNormalized, long expiryEpoch, int attempts,
                    long lastSentEpoch, int resendCount, long windowStartEpoch, boolean consumed) {
        this.otpHash = otpHash;
        this.phoneNormalized = phoneNormalized;
        this.expiryEpoch = expiryEpoch;
        this.attempts = attempts;
        this.lastSentEpoch = lastSentEpoch;
        this.resendCount = resendCount;
        this.windowStartEpoch = windowStartEpoch;
        this.consumed = consumed;
    }

    public String getOtpHash() {
        return otpHash;
    }

    public String getPhoneNormalized() {
        return phoneNormalized;
    }

    public long getExpiryEpoch() {
        return expiryEpoch;
    }

    public int getAttempts() {
        return attempts;
    }

    public long getLastSentEpoch() {
        return lastSentEpoch;
    }

    public int getResendCount() {
        return resendCount;
    }

    public long getWindowStartEpoch() {
        return windowStartEpoch;
    }

    public boolean isConsumed() {
        return consumed;
    }

    public OtpState withIncrementedAttempts() {
        return new OtpState(otpHash, phoneNormalized, expiryEpoch, attempts + 1,
                lastSentEpoch, resendCount, windowStartEpoch, consumed);
    }

    public OtpState withConsumed() {
        return new OtpState(otpHash, phoneNormalized, expiryEpoch, attempts,
                lastSentEpoch, resendCount, windowStartEpoch, true);
    }

    public OtpState withResent(long newLastSent, int newResendCount, long newWindowStart) {
        return new OtpState(otpHash, phoneNormalized, expiryEpoch, attempts,
                newLastSent, newResendCount, newWindowStart, consumed);
    }
}
