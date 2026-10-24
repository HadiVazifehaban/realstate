package com.shekarchi.auth.sms.provider;

import com.shekarchi.auth.sms.SmsException;
import com.shekarchi.auth.sms.SmsSenderService;
import org.keycloak.provider.ProviderConfigProperty;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;

public class KavenegarSmsSenderService implements SmsSenderService {
    private final KavenegarSmsSenderServiceFactory factory;
    private HttpClient httpClient;

    public KavenegarSmsSenderService(KavenegarSmsSenderServiceFactory factory) {
        this.factory = factory;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();
    }

    @Override
    public void sendSms(String phoneNumber, String message, String templateCode) throws SmsException {
        List<ProviderConfigProperty> props = factory.getConfigProperties();
        // Note: actual config values come from provider config in runtime; this is minimal
        String apiKey = getConfigValue("api-key");
        String endpoint = getConfigValue("endpoint", "https://api.kavenegar.com/v1");
        String from = getConfigValue("from", "");
        String timeoutStr = getConfigValue("timeout-ms", "5000");

        if (apiKey == null || apiKey.isBlank()) {
            throw new SmsException("SMS provider configuration missing");
        }

        int timeoutMs;
        try {
            timeoutMs = Integer.parseInt(timeoutStr);
        } catch (Exception e) {
            timeoutMs = 5000;
        }

        // Minimal implementation - in production use proper Kavenegar API
        // This is a safe, fail-closed stub structure; actual API calls should be implemented per docs
        try {
            URI uri = URI.create(endpoint + "/" + apiKey + "/sms/send.json");
            String body = buildRequestBody(phoneNumber, message, from, templateCode);
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(uri)
                    .timeout(Duration.ofMillis(timeoutMs))
                    .header("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
                    .POST(HttpRequest.BodyPublishers.ofString(body))
                    .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            // Validate response - fail closed on non-2xx
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new SmsException("SMS send failed with status: " + response.statusCode());
            }
            // Do not log response body or sensitive data
        } catch (IOException | InterruptedException e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            throw new SmsException("SMS send failed: " + e.getMessage(), e);
        }
    }

    private String buildRequestBody(String phone, String message, String from, String templateCode) {
        StringBuilder sb = new StringBuilder();
        sb.append("receptor=").append(urlEncode(phone));
        if (templateCode != null && !templateCode.isBlank()) {
            sb.append("&template=").append(urlEncode(templateCode));
        }
        if (message != null && !message.isBlank() && (templateCode == null || templateCode.isBlank())) {
            sb.append("&message=").append(urlEncode(message));
        }
        if (from != null && !from.isBlank()) {
            sb.append("&sender=").append(urlEncode(from));
        }
        return sb.toString();
    }

    private String urlEncode(String s) {
        if (s == null) return "";
        try {
            return java.net.URLEncoder.encode(s, "UTF-8");
        } catch (Exception e) {
            return s;
        }
    }

    private String getConfigValue(String key) {
        return getConfigValue(key, null);
    }

    private String getConfigValue(String key, String defaultVal) {
        // Runtime config from provider - placeholder; actual impl reads from config
        String env = System.getenv("SHEKARCHI_SMS_" + key.toUpperCase().replace('-', '_'));
        if (env != null && !env.isBlank()) return env;
        return defaultVal;
    }

    @Override
    public void close() {
    }
}
