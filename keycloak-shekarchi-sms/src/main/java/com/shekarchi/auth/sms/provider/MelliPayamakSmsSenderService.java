package com.shekarchi.auth.sms.provider;

import com.shekarchi.auth.sms.SmsException;
import com.shekarchi.auth.sms.SmsSenderService;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.util.Properties;
import java.io.Reader;
import java.time.Duration;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** MelliPayamak REST BaseServiceNumber adapter. Ambiguous POSTs are never retried. */
public class MelliPayamakSmsSenderService implements SmsSenderService {
    static final String DEFAULT_ENDPOINT = "https://rest.payamak-panel.com/api/SendSMS/BaseServiceNumber";
    private static final int MAX_RESPONSE_BYTES = 16_384;
    private static final Pattern PHONE = Pattern.compile("^\\+989[0-9]{9}$");
    private static final Pattern SAFE_VALUE = Pattern.compile("^[^;{}\\r\\n]{1,128}$");
    private static final Pattern SUCCESS_VALUE = Pattern.compile("\\\"Value\\\"\\s*:\\s*\\\"?([0-9]{16,})\\\"?");
    private static final Pattern RET_STATUS = Pattern.compile("\\\"RetStatus\\\"\\s*:\\s*(-?[0-9]+)");

    private final String username;
    private final String password;
    private final String endpoint;
    private final int timeoutMs;
    private final HttpClient client;
    private final Map<String, String> bodyIds;
    private final boolean enabled;
    interface Transport { HttpResult post(String endpoint, String contentType, String form, int timeoutMs) throws IOException, InterruptedException; }
    record HttpResult(int statusCode, String body) {}
    private final Transport transport;
    private static final Properties CONFIG = loadConfig();

    private static Properties loadConfig() {
        Properties values = new Properties();
        String path = System.getenv("MELLIPAYAMAK_CONFIG_FILE");
        if (path == null || path.isBlank()) path = System.getenv("SHEKARCHI_SMS_MELLI_CONFIG_FILE");
        if (path == null || path.isBlank()) return values;
        try {
            if (Files.size(Path.of(path)) > 16_384) throw new IllegalStateException("Configuration file is too large");
            var permissions = Files.getPosixFilePermissions(Path.of(path));
            if (permissions.contains(PosixFilePermission.GROUP_READ)
                    || permissions.contains(PosixFilePermission.GROUP_WRITE)
                    || permissions.contains(PosixFilePermission.GROUP_EXECUTE)
                    || permissions.contains(PosixFilePermission.OTHERS_READ)
                    || permissions.contains(PosixFilePermission.OTHERS_WRITE)
                    || permissions.contains(PosixFilePermission.OTHERS_EXECUTE)) {
                throw new IllegalStateException("Configuration file permissions are too broad");
            }
            try (Reader reader = Files.newBufferedReader(Path.of(path), StandardCharsets.UTF_8)) {
                values.load(reader);
            }
            return values;
        } catch (Exception ex) {
            throw new IllegalStateException("MelliPayamak configuration file is unavailable", ex);
        }
    }

    public MelliPayamakSmsSenderService(MelliPayamakSmsSenderServiceFactory factory) {
        this(envAny("MELLIPAYAMAK_USERNAME", "SHEKARCHI_SMS_MELLI_USERNAME"),
                envAny("MELLIPAYAMAK_PASSWORD", "SHEKARCHI_SMS_MELLI_PASSWORD"),
                envAny("MELLIPAYAMAK_ENDPOINT", "SHEKARCHI_SMS_MELLI_ENDPOINT", DEFAULT_ENDPOINT),
                parseTimeout(envAny("MELLIPAYAMAK_TIMEOUT_MS", "SHEKARCHI_SMS_MELLI_TIMEOUT_MS", "8000")),
                newHttpClient(parseTimeout(env("MELLIPAYAMAK_CONNECT_TIMEOUT_MS", "5000"))), configValues(), null,
                Boolean.parseBoolean(env("MELLIPAYAMAK_ENABLED", "false")));
    }

    MelliPayamakSmsSenderService(String username, String password, String endpoint, int timeoutMs, HttpClient client, Map<String, String> bodyIds) {
        this(username, password, endpoint, timeoutMs, client, bodyIds, null);
    }
    MelliPayamakSmsSenderService(String username, String password, String endpoint, int timeoutMs, HttpClient client,
                                Map<String, String> bodyIds, Transport injectedTransport) {
        this(username, password, endpoint, timeoutMs, client, bodyIds, injectedTransport, true);
    }
    MelliPayamakSmsSenderService(String username, String password, String endpoint, int timeoutMs, HttpClient client,
                                Map<String, String> bodyIds, Transport injectedTransport, boolean enabled) {
        this.username = username;
        this.password = password;
        this.endpoint = endpoint;
        this.timeoutMs = timeoutMs;
        this.client = client;
        this.bodyIds = bodyIds;
        this.transport = injectedTransport == null ? this::postHttp : injectedTransport;
        this.enabled = enabled;
    }

    @Override
    public void sendSms(String phoneNumber, String message, String templateCode) throws SmsException {
        if (!enabled) throw new SmsException("MelliPayamak delivery is not approved/enabled");
        if (username == null || username.isBlank() || password == null || password.isBlank())
            throw new SmsException("MelliPayamak credentials are not configured");
        boolean secureEndpoint = false;
        try {
            URI parsedEndpoint = URI.create(endpoint);
            secureEndpoint = "https".equalsIgnoreCase(parsedEndpoint.getScheme())
                    || ("http".equalsIgnoreCase(parsedEndpoint.getScheme())
                    && ("127.0.0.1".equals(parsedEndpoint.getHost()) || "localhost".equals(parsedEndpoint.getHost())));
        } catch (RuntimeException ignored) { /* mapped to safe config error below */ }
        if (!secureEndpoint) throw new SmsException("MelliPayamak endpoint must use HTTPS");
        String normalizedPhone = normalizePhone(phoneNumber);
        if (normalizedPhone == null)
            throw new SmsException("Invalid mobile number");
        if (templateCode == null || !templateCode.matches("[1-9][0-9]{0,9}"))
            throw new SmsException("MelliPayamak pattern is disabled: approved Body ID is missing");
        String[] values = message == null ? new String[0] : message.split(";", -1);
        if (values.length == 0) throw new SmsException("Pattern variables are missing");
        for (String value : values) if (!SAFE_VALUE.matcher(value).matches())
            throw new SmsException("Invalid pattern variable");
        String form = "username=" + formEncode(username)
                + "&password=" + formEncode(password)
                + "&text=" + formEncode(String.join(";", values))
                + "&to=" + formEncode("0" + normalizedPhone.substring(3))
                + "&bodyId=" + formEncode(templateCode);
        try {
            HttpResult response = transport.post(endpoint, "application/x-www-form-urlencoded; charset=UTF-8", form, timeoutMs);
            if (response.statusCode() < 200 || response.statusCode() >= 300)
                throw new SmsException(httpReason(response.statusCode()));
            Matcher status = RET_STATUS.matcher(response.body());
            Matcher value = SUCCESS_VALUE.matcher(response.body());
            if (!status.find() || Integer.parseInt(status.group(1)) != 1 || !value.find()) {
                String code = extractValueCode(response.body());
                throw new SmsException("MelliPayamak business rejection: " + businessReason(code));
            }
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new SmsException("MelliPayamak request interrupted");
        } catch (IOException ex) {
            throw new SmsException("MelliPayamak transport failure");
        }
    }

    private HttpResult postHttp(String url, String contentType, String form, int timeout) throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofMillis(timeout))
                .header("Content-Type", contentType)
                .header("Accept", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(form, StandardCharsets.UTF_8)).build();
        HttpResponse<java.io.InputStream> response = client.send(request, HttpResponse.BodyHandlers.ofInputStream());
        try (java.io.InputStream body = response.body()) {
            byte[] bytes = body.readNBytes(MAX_RESPONSE_BYTES + 1);
            if (bytes.length > MAX_RESPONSE_BYTES) throw new IOException("Provider response exceeded limit");
            return new HttpResult(response.statusCode(), new String(bytes, StandardCharsets.UTF_8));
        }
    }

    private static HttpClient newHttpClient(int connectTimeoutMs) {
        return HttpClient.newBuilder().connectTimeout(Duration.ofMillis(connectTimeoutMs))
                .followRedirects(HttpClient.Redirect.NEVER).build();
    }

    static String httpReason(int status) {
        if (status == 429) return "MelliPayamak rate limit rejected request";
        if (status >= 500) return "MelliPayamak service unavailable";
        if (status >= 400) return "MelliPayamak rejected request";
        return "MelliPayamak unexpected HTTP response";
    }

    @Override
    public void sendOtp(String phoneNumber, String code) throws SmsException {
        sendPattern(phoneNumber, "shekarchi_otp_login", Map.of("code", code));
    }

    /** True only when live OTP delivery is explicitly enabled and fully configured. */
    public boolean isOtpConfigured() {
        String otpBodyId = bodyId("MELLIPAYAMAK_OTP_BODY_ID");
        return enabled && username != null && !username.isBlank()
                && password != null && !password.isBlank()
                && otpBodyId != null && otpBodyId.matches("[1-9][0-9]{0,9}");
    }

    public void sendPattern(String phoneNumber, String patternId, Map<String, String> variables) throws SmsException {
        MelliPayamakPatternRegistry.Pattern pattern = MelliPayamakPatternRegistry.get(patternId);
        if (pattern == null) throw new SmsException("Unknown MelliPayamak pattern");
        if (!variables.keySet().equals(new java.util.HashSet<>(pattern.variables())))
            throw new SmsException("Pattern variables do not match required names");
        java.util.List<String> ordered = new java.util.ArrayList<>();
        for (String key : pattern.variables()) ordered.add(variables.get(key));
        String bodyId = bodyId(pattern.bodyIdEnv());
        sendSms(phoneNumber, String.join(";", ordered), bodyId);
    }

    private String bodyId(String key) {
        String value = bodyIds.get(key);
        if (value != null && !value.isBlank()) return value;
        String legacyKey = switch (key) {
            case "MELLIPAYAMAK_OTP_BODY_ID" -> "SHEKARCHI_SMS_MELLI_OTP_BODY_ID";
            case "MELLIPAYAMAK_VISIT_BODY_ID" -> "SHEKARCHI_SMS_MELLI_VISIT_BODY_ID";
            case "MELLIPAYAMAK_LEAD_BODY_ID" -> "SHEKARCHI_SMS_MELLI_PRICE_ALERT_BODY_ID";
            case "MELLIPAYAMAK_SUBSCRIPTION_BODY_ID" -> "SHEKARCHI_SMS_MELLI_AGENCY_SUB_BODY_ID";
            default -> "";
        };
        return legacyKey.isEmpty() ? "" : bodyIds.getOrDefault(legacyKey, "");
    }

    static String businessReason(String code) {
        return switch (code) {
            case "-112", "-1" -> "pattern_service_disabled";
            case "-111", "-109", "-108" -> "ip_policy_rejected";
            case "-5" -> "pattern_variables_mismatch";
            case "-4" -> "body_id_invalid_or_unapproved";
            case "0" -> "credentials_invalid";
            case "2" -> "insufficient_credit";
            case "18" -> "phone_invalid";
            case "19" -> "daily_api_limit_reached";
            default -> "provider_rejected";
        };
    }

    private static String extractValueCode(String body) {
        Matcher m = Pattern.compile("\\\"Value\\\"\\s*:\\s*\\\"?(-?[0-9]+)\\\"?").matcher(body);
        return m.find() ? m.group(1) : "unknown";
    }
    private static String normalizePhone(String value) {
        if (value == null) return null;
        String digits = value.trim().replaceAll("[\\s()\\-]", "");
        if (digits.startsWith("0098")) digits = "+98" + digits.substring(4);
        else if (digits.startsWith("98")) digits = "+" + digits;
        else if (digits.startsWith("09")) digits = "+98" + digits.substring(1);
        else if (digits.startsWith("9")) digits = "+98" + digits;
        return PHONE.matcher(digits).matches() ? digits : null;
    }
    private static String formEncode(String value) {
        return java.net.URLEncoder.encode(value, StandardCharsets.UTF_8);
    }
    private static String env(String key, String fallback) {
        String value = System.getenv(key);
        if (value == null || value.isBlank()) value = CONFIG.getProperty(key);
        return value == null || value.isBlank() ? fallback : value;
    }
    private static String envAny(String key, String legacyKey) {
        return envAny(key, legacyKey, "");
    }
    private static String envAny(String key, String legacyKey, String fallback) {
        String value = System.getenv(key);
        if (value == null || value.isBlank()) value = CONFIG.getProperty(key);
        if (value == null || value.isBlank()) value = System.getenv(legacyKey);
        if (value == null || value.isBlank()) value = CONFIG.getProperty(legacyKey);
        return value == null || value.isBlank() ? fallback : value;
    }
    private static Map<String, String> configValues() {
        java.util.HashMap<String, String> values = new java.util.HashMap<>();
        CONFIG.forEach((key, value) -> values.put(String.valueOf(key), String.valueOf(value)));
        values.putAll(System.getenv());
        return values;
    }
    private static int parseTimeout(String value) {
        try { int parsed = Integer.parseInt(value); return Math.max(100, Math.min(parsed, 60000)); }
        catch (RuntimeException ex) { return 8000; }
    }
    @Override public void close() { /* shared JDK HttpClient has no close lifecycle */ }
}
