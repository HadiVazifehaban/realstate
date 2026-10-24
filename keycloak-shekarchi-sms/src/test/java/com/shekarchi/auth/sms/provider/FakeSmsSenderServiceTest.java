package com.shekarchi.auth.sms.provider;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class FakeSmsSenderServiceTest {
    @BeforeEach void clearBeforeTest() { FakeSmsSenderService.clearTestCodes(); }
    @AfterEach void clearCodes() { FakeSmsSenderService.clearTestCodes(); }

    @Test void recordsTheExactAuthenticatorCodeWithoutGeneratingAnother() throws Exception {
        FakeSmsSenderService fake = new FakeSmsSenderService(true);
        fake.sendOtp("989121234567", "004219");
        assertEquals("004219", fake.getLastCode("989121234567"));
    }

    @Test void refusesToExposeCodesWhenFakeModeIsDisabled() throws Exception {
        FakeSmsSenderService fake = new FakeSmsSenderService(false);
        assertThrows(Exception.class, () -> fake.sendOtp("989121234567", "004219"));
        assertNull(fake.getLastCode("989121234567"));
    }
}
