package com.shekarchi.auth.sms.provider;

import com.shekarchi.auth.sms.SmsException;
import org.junit.jupiter.api.Test;

import java.net.http.HttpClient;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;

class MelliPayamakSmsSenderServiceTest {
    @Test void performsFormEncodedHttpPostAgainstLocalMockWithoutRetry() throws Exception {
        AtomicInteger calls = new AtomicInteger();
        AtomicReference<String> method = new AtomicReference<>();
        AtomicReference<String> contentType = new AtomicReference<>();
        AtomicReference<String> body = new AtomicReference<>();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/api/SendSMS/BaseServiceNumber", exchange -> {
            calls.incrementAndGet();
            method.set(exchange.getRequestMethod());
            contentType.set(exchange.getRequestHeaders().getFirst("Content-Type"));
            body.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            byte[] reply = "{\"Value\":\"12345678901234567\",\"RetStatus\":1}".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, reply.length);
            exchange.getResponseBody().write(reply);
            exchange.close();
        });
        server.start();
        try {
            String endpoint = "http://127.0.0.1:" + server.getAddress().getPort() + "/api/SendSMS/BaseServiceNumber";
            var provider = new MelliPayamakSmsSenderService("mock-user", "mock-password", endpoint,
                    2000, HttpClient.newHttpClient(), Map.of(), null);
            provider.sendSms("09121234567", "123456", "12345");
            assertEquals(1, calls.get());
            assertEquals("POST", method.get());
            assertTrue(contentType.get().startsWith("application/x-www-form-urlencoded"));
            assertTrue(body.get().contains("username=mock-user"));
            assertTrue(body.get().contains("password=mock-password"));
            assertTrue(body.get().contains("to=09121234567"));
            assertTrue(body.get().contains("bodyId=12345"));
        } finally {
            server.stop(0);
        }
    }

    @Test void sendsFormWithOrderedPatternVariablesAndAcceptsGatewaySuccess() throws Exception {
        AtomicInteger count = new AtomicInteger();
        final String[] request = new String[1];
        final String[] contentType = new String[1];
        MelliPayamakSmsSenderService.Transport transport = (endpoint, type, body, timeout) -> {
            count.incrementAndGet(); request[0] = body; contentType[0] = type;
            assertTrue(endpoint.endsWith("BaseServiceNumber"));
            assertEquals(3000, timeout);
            return new MelliPayamakSmsSenderService.HttpResult(200,
                    "{\"Value\":\"12345678901234567\",\"RetStatus\":1}");
        };
        MelliPayamakSmsSenderService provider = new MelliPayamakSmsSenderService("user", "secret",
                MelliPayamakSmsSenderService.DEFAULT_ENDPOINT, 3000, HttpClient.newHttpClient(),
                Map.of("SHEKARCHI_SMS_MELLI_VISIT_BODY_ID", "12345"), transport);
        provider.sendPattern("+989121234567", "shekarchi_visit_booking",
                Map.of("time", "14:30", "date", "1405/07/27", "property_id", "P-7"));
        assertEquals("application/x-www-form-urlencoded; charset=UTF-8", contentType[0]);
        Map<String, String> fields = java.util.Arrays.stream(request[0].split("&"))
                .map(part -> part.split("=", 2))
                .collect(java.util.stream.Collectors.toMap(pair -> java.net.URLDecoder.decode(pair[0], java.nio.charset.StandardCharsets.UTF_8),
                        pair -> java.net.URLDecoder.decode(pair[1], java.nio.charset.StandardCharsets.UTF_8)));
        assertEquals("user", fields.get("username"));
        assertEquals("secret", fields.get("password"));
        assertEquals("P-7;1405/07/27;14:30", fields.get("text"));
        assertEquals("09121234567", fields.get("to"));
        assertEquals("12345", fields.get("bodyId"));
        assertEquals(1, count.get());
    }

    @Test void rejectsUnconfiguredPatternAndBadPhoneBeforeNetwork() {
        MelliPayamakSmsSenderService provider = new MelliPayamakSmsSenderService("user", "secret",
                "https://localhost/unused", 3000, HttpClient.newHttpClient(), Map.of(), (u,c,b,t) -> { throw new AssertionError("network must not run"); });
        assertThrows(SmsException.class, () -> provider.sendPattern("+989121234567", "shekarchi_otp_login", Map.of("code", "123456")));
        assertThrows(SmsException.class, () -> provider.sendSms("02123456789", "123456", "12345"));
    }

    @Test void classifiesBusinessCodesWithoutLeakingResponse() {
        assertEquals("body_id_invalid_or_unapproved", MelliPayamakSmsSenderService.businessReason("-4"));
        assertEquals("credentials_invalid", MelliPayamakSmsSenderService.businessReason("0"));
        assertEquals("provider_rejected", MelliPayamakSmsSenderService.businessReason("unknown"));
    }

    @Test void disabledProviderNeverCallsTransportEvenWithCredentialsAndBodyId() {
        MelliPayamakSmsSenderService provider = new MelliPayamakSmsSenderService("user", "secret",
                MelliPayamakSmsSenderService.DEFAULT_ENDPOINT, 3000, HttpClient.newHttpClient(),
                Map.of("SHEKARCHI_SMS_MELLI_OTP_BODY_ID", "562609"),
                (u,c,b,t) -> { throw new AssertionError("disabled provider must not make a request"); }, false);
        SmsException error = assertThrows(SmsException.class,
                () -> provider.sendOtp("+989121234567", "123456"));
        assertTrue(error.getMessage().contains("not approved/enabled"));
    }

    @Test void classifiesHttpFailuresWithoutProviderResponseData() {
        assertEquals("MelliPayamak rate limit rejected request", MelliPayamakSmsSenderService.httpReason(429));
        assertEquals("MelliPayamak service unavailable", MelliPayamakSmsSenderService.httpReason(503));
        assertEquals("MelliPayamak rejected request", MelliPayamakSmsSenderService.httpReason(400));
    }

    @Test void failedDeliveryIsClosedAndAmbiguousPostIsNotRetriedOrLeaked() {
        AtomicInteger calls = new AtomicInteger();
        MelliPayamakSmsSenderService provider = new MelliPayamakSmsSenderService("mock-user", "mock-password",
                MelliPayamakSmsSenderService.DEFAULT_ENDPOINT, 3000, HttpClient.newHttpClient(),
                Map.of("MELLIPAYAMAK_OTP_BODY_ID", "12345"),
                (url, type, form, timeout) -> {
                    calls.incrementAndGet();
                    return new MelliPayamakSmsSenderService.HttpResult(503,
                            "sensitive-provider-body mock-password +989121234567");
                });
        SmsException error = assertThrows(SmsException.class, () -> provider.sendOtp("+989121234567", "123456"));
        assertEquals(1, calls.get());
        assertTrue(error.getMessage().contains("unavailable"));
        assertFalse(error.getMessage().contains("mock-password"));
        assertFalse(error.getMessage().contains("+989121234567"));
        assertFalse(error.getMessage().contains("sensitive-provider-body"));
    }
}
