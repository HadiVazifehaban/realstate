package com.shekarchi.auth.sms.provider;

import java.util.List;
import java.util.Map;

/** Stable pattern identifiers and positional variable contracts. */
public final class MelliPayamakPatternRegistry {
    public record Pattern(String bodyIdEnv, List<String> variables) {}
    private static final Map<String, Pattern> PATTERNS = Map.of(
            "shekarchi_otp_login", new Pattern("MELLIPAYAMAK_OTP_BODY_ID", List.of("code")),
            "shekarchi_otp", new Pattern("MELLIPAYAMAK_OTP_BODY_ID", List.of("code")),
            "shekarchi_visit_booking", new Pattern("MELLIPAYAMAK_VISIT_BODY_ID", List.of("property_id", "date", "time")),
            "shekarchi_price_alert", new Pattern("MELLIPAYAMAK_LEAD_BODY_ID", List.of("region", "price")),
            "shekarchi_lead_alert", new Pattern("MELLIPAYAMAK_LEAD_BODY_ID", List.of("region", "price")),
            "shekarchi_agency_sub", new Pattern("MELLIPAYAMAK_SUBSCRIPTION_BODY_ID", List.of("plan_name", "expire_date"))
    );
    private MelliPayamakPatternRegistry() {}
    public static Pattern get(String id) { return PATTERNS.get(id); }
}
