"""Central, typed application configuration.

Configuration is driven by environment variables / a local ``.env`` file so the
exact same codebase runs in both deployment topologies:

* ``NODE_MODE=LOCAL``      -> on-premise node inside the real-estate office.
* ``NODE_MODE=CLOUD_HUB``  -> the central AVG SaaS hub.

The module intentionally exposes a cached :func:`get_settings` accessor so the
rest of the code never has to re-parse the environment.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
import stat

from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two levels above this file (``app/core/config.py`` -> repo root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_runtime_secret_file(filename: str) -> str:
    """Read a Docker secret without ever echoing its path or value."""
    path = Path(filename)
    try:
        info = path.stat()
        if not path.is_file() or info.st_size > 16_384 or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("secret file is unavailable or has unsafe permissions")
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise ValueError("secret file is empty")
        return value
    except Exception as exc:
        raise ValueError("configured secret file is unavailable") from exc


class NodeMode(str, Enum):
    """Deployment topology of the current process."""

    LOCAL = "LOCAL"
    CLOUD_HUB = "CLOUD_HUB"


class AuthMode(str, Enum):
    """Who the node trusts to say who a caller is.

    KEYCLOAK is the production posture: a bearer token issued by the realm, with
    roles and KYC status read from its claims. LICENSE is the pre-Keycloak LAN
    model kept only so an isolated single-office node still works with no IdP.
    """

    KEYCLOAK = "KEYCLOAK"
    LICENSE = "LICENSE"


class Settings(BaseSettings):
    """Strongly typed settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    # -- Node topology / branding -----------------------------------------------
    node_mode: NodeMode = NodeMode.LOCAL
    app_name: str = "AVG CRM & MLS Core"
    app_version: str = "2.0.0-SCRAPER-HYBRID"
    brand_owner: str = "AVG - گروه چشم‌انداز اوج فردا"
    brand_domains: tuple[str, str] = ("avgcrm.ir", "avgcrm.com")
    debug: bool = False

    # -- Feature flags ----------------------------------------------------------
    # The commercial build ships AI-Ready interfaces but processing is fully
    # deterministic + spatial.  Keep this False for the commercial release.
    feature_flag_ai_engine: bool = False

    # -- Database ---------------------------------------------------------------
    # psycopg3 supports both sync (Alembic) and async (runtime) usage.
    database_url: str = Field(
        default="postgresql+psycopg://avg:avg_secret@localhost:5432/avgcrm",
        validation_alias=AliasChoices("DATABASE_URL", "PHASE15_TEST_DATABASE_URL"),
    )

    # -- Filesystem paths -------------------------------------------------------
    data_dir: Path = Path("data")
    media_dir: Path = Path("data/media")
    keys_dir: Path = Path("data/keys")
    license_file: Path = Path("data/license/node.lic")
    license_public_key_file: Path = Path("data/keys/license_public.pem")
    license_private_key_file: Path = Path("data/keys/license_private.pem")
    # Per-agency symmetric key for the Fernet PII vault (Phase 1, never leaves the node).
    pii_key_file: Path = Path("data/keys/agency_pii.key")

    # -- Manual card-to-card subscription payments ------------------------------
    payment_method: str = "CARD_TO_CARD"
    payment_card_number: str = "0000000000000000"
    payment_card_holder: str = "چشم‌انداز اوج فردا"
    payment_card_configured: bool = False
    payment_card_owner_verified: bool = False
    payment_receipt_max_bytes: int = 8 * 1024 * 1024
    payment_encryption_key: str = ""

    # -- Zibal gateway (double opt-in; live payments remain disabled by default) --
    zibal_enabled: bool = False
    zibal_test_mode: bool = True
    zibal_merchant: str = ""
    zibal_credential_encryption_key: str = ""
    zibal_request_url: str = "https://gateway.zibal.ir/v1/request"
    zibal_verify_url: str = "https://gateway.zibal.ir/v1/verify"
    zibal_inquiry_url: str = "https://gateway.zibal.ir/v1/inquiry"
    zibal_start_url: str = "https://gateway.zibal.ir/start"
    zibal_callback_url: str = ""
    zibal_result_url: str = "http://localhost:3000/dashboard/billing"
    zibal_timeout_seconds: float = Field(default=8.0, gt=0, le=30)

    # -- Commercial licensing ---------------------------------------------------
    offline_grace_days: int = 14
    heartbeat_interval_hours: int = 12
    # Dev/testing override; MUST be empty in production.
    machine_fingerprint_override: str = ""

    # -- Security ---------------------------------------------------------------
    jwt_secret: str = "change-me-in-production-please-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720

    # -- Identity & access (Keycloak / OIDC) ------------------------------------
    # ``auth_mode`` selects the trust model:
    #   KEYCLOAK — every API call must carry a Keycloak access token; the node
    #              trusts nothing it did not issue itself. This is the only mode
    #              permitted on a deployed hub.
    #   LICENSE  — the legacy LAN-office model: the commercial licence is the
    #              whole gate and callers identify via trusted headers. It exists
    #              so an unconnected single-office node keeps working offline;
    #              it must never be used for a multi-tenant deployment.
    auth_mode: AuthMode = AuthMode.LICENSE

    # Blank issuer/auth_mode=LICENSE is what makes Keycloak optional locally.
    keycloak_issuer: str = ""
    # Optional server-to-server JWKS endpoint. Token ``iss`` validation always
    # uses keycloak_issuer; this endpoint only avoids routing key retrieval
    # through the public browser-facing Keycloak hostname in Docker.
    keycloak_jwks_url: str = ""
    keycloak_audience: str = "maskanchi-backend-api"
    # Only the frontend OIDC client is allowed to present user access tokens to
    # this API. `azp` distinguishes its access token from tokens minted for an
    # unrelated client that happens to share an audience mapper.
    keycloak_authorized_party: str = "shekarchi-frontend"
    # Role that satisfies the approval gate; a VERIFIED KYC status is required
    # regardless of role, so no role can bypass the identity check.
    keycloak_required_kyc_status: str = "VERIFIED"
    # JWKS cache lifetime. Key rotation publishes a new kid, and a stale cache
    # would reject freshly issued tokens until it expires.
    jwks_cache_seconds: int = 300
    jwks_request_timeout_seconds: int = 5

    # -- Keycloak Admin API (user directory) -------------------------------------
    # The /users directory is sourced from the realm, not from the local
    # `agency_user` table, so Keycloak is the single source of truth for who
    # exists and what tier they hold. These settings drive the node's own
    # service-account client, used only for directory reads/writes.
    #
    # Blank admin client id/secret means "directory not wired to Keycloak" and
    # the /users router falls back to `agency_user`, so a fresh clone keeps
    # working before Keycloak is ever started.
    keycloak_admin_client_id: str = ""
    keycloak_admin_client_secret: str = ""
    # Only used when keycloak_issuer is blank (a fresh clone in LICENSE mode).
    # In a configured install the issuer wins, so the admin API cannot end up
    # pointed at a different server than the one whose tokens we verify.
    keycloak_admin_url: str = ""
    # Realm name only -- not a URL. The base is derived from `keycloak_issuer`
    # so the admin API can never end up pointed at a different host than the
    # one whose tokens this node verifies.
    keycloak_realm: str = "maskanchi"
    # Access-token lifetime for the service account. Deliberately short: the
    # token grants user administration.
    keycloak_admin_token_ttl_seconds: int = 60
    # Ceiling on one directory page, so a caller cannot ask Keycloak to
    # materialise the whole realm in one response.
    keycloak_directory_max_limit: int = 100

    # PII reveal ceiling. A caller's own `daily_pii_quota` claim wins; this is
    # the hard stop for a token that carries none (or an absurd value).
    pii_quota_hard_cap: int = 200

    # -- OTP quick-registration (SHEKARCHI fast + professional onboarding) ------
    # Registration phone proof is public. In KEYCLOAK mode it cannot mint a
    # login session: users continue through Auth.js OIDC and the Keycloak SPI.
    # The password-grant bridge remains only for the isolated LICENSE topology.
    #
    # The provider adapters send nothing when TEST-mode is off; production
    # needs real credentials. ``sms_provider=fake`` is the local/test-only
    # adapter: it stores the last code in-process so tests can assert the
    # flow end-to-end without touching a real SMS gateway.
    sms_provider: str = "fake"
    # Kavenegar (https://kavenegar.com) REST API key; used when
    # ``sms_provider=kavenegar``. Also used as the sender line selector's
    # fallback when ``sms_sender`` is empty.
    sms_api_key: str = ""
    # Sender line / service pattern; provider-specific (e.g. Kavenegar lookup
    # template name when ``sms_provider=kavenegar``).
    sms_sender: str = ""
    # Base URL override for the SMS HTTP API (tests pin this to loopback).
    sms_base_url: str = ""
    # MelliPayamak REST pattern service. Empty body IDs intentionally disable
    # real delivery until each approved panel pattern is configured.
    sms_melli_username: str = Field(default="", validation_alias=AliasChoices("MELLIPAYAMAK_USERNAME", "SMS_MELLI_USERNAME"))
    sms_melli_password: str = Field(default="", validation_alias=AliasChoices("MELLIPAYAMAK_PASSWORD", "SMS_MELLI_PASSWORD"))
    # Explicit double opt-in: provider selection alone is insufficient to send.
    # Keep false until the panel patterns and Body IDs are approved.
    mellipayamak_enabled: bool = False
    sms_melli_endpoint: str = Field(
        default="https://rest.payamak-panel.com/api/SendSMS/BaseServiceNumber",
        validation_alias=AliasChoices("MELLIPAYAMAK_ENDPOINT", "SMS_MELLI_ENDPOINT"),
    )
    sms_melli_timeout_seconds: float = Field(
        default=8.0, validation_alias=AliasChoices("MELLIPAYAMAK_TIMEOUT_SECONDS", "SMS_MELLI_TIMEOUT_SECONDS")
    )
    sms_melli_otp_body_id: str = Field(
        default="", validation_alias=AliasChoices("MELLIPAYAMAK_OTP_BODY_ID", "SMS_MELLI_OTP_BODY_ID")
    )
    sms_melli_visit_body_id: str = Field(
        default="", validation_alias=AliasChoices("MELLIPAYAMAK_VISIT_BODY_ID", "SMS_MELLI_VISIT_BODY_ID")
    )
    sms_melli_price_alert_body_id: str = Field(
        default="", validation_alias=AliasChoices("MELLIPAYAMAK_LEAD_BODY_ID", "MELLIPAYAMAK_PRICE_BODY_ID", "SMS_MELLI_PRICE_ALERT_BODY_ID")
    )
    sms_melli_agency_sub_body_id: str = Field(
        default="", validation_alias=AliasChoices("MELLIPAYAMAK_SUBSCRIPTION_BODY_ID", "SMS_MELLI_AGENCY_SUB_BODY_ID")
    )
    # Authentication policy shared with the Keycloak SMS SPI.
    otp_ttl_seconds: int = 120
    # Max wrong-code attempts before the challenge is voided. Each attempt --
    # right or wrong -- is compared in constant time and audited.
    otp_max_attempts: int = 3
    # Min seconds between two requests for the same mobile.
    otp_request_cooldown_seconds: int = 120
    # Max requests per mobile per rolling hour.
    otp_max_requests_per_hour: int = 5
    # Absolute daily cap per mobile.
    otp_max_requests_per_day: int = 15
    # Max requests per client IP per rolling hour (abuse backstop).
    otp_max_requests_per_ip_hour: int = 30
    # Namespace prefix for every OTP/registration key in Redis.
    otp_redis_prefix: str = "shekarchi:otp"
    # Shared secret used to HMAC OTP values before persistence. Configure from
    # a secret manager; blank disables the legacy FastAPI OTP bridge.
    otp_hmac_secret: str = ""
    otp_hmac_secret_file: str = Field(default="", validation_alias="OTP_HMAC_SECRET_FILE", repr=False)
    # Skip the real Keycloak token exchange (Direct Grant) and SMS send --
    # NEVER true in production; the test-suite and local dev use it.
    otp_test_mode: bool = False
    # Number of the last OTPs a phone's audit keeps ( trim guard).
    otp_audit_keep: int = 50
    # Client id used for the OTP->token Direct Grant exchange against the
    # realm. Must be a public client with direct grants enabled; defaults to
    # the dashboard's own public client so no realm change is needed.
    otp_keycloak_client_id: str = "shekarchi-frontend"
    # Minutes a verified-mobile ``registration_token`` stays valid. It is a
    # short-lived, single-purpose, single-use credential for
    # ``/auth/quick-register`` and ``/auth/professional-registration`` --
    # never a session and never a substitute for a realm token.
    registration_token_ttl_minutes: int = 15
    # How long a ``mobile_verified=true`` marker survives in Redis after the
    # registration token is consumed -- lets the professional funnel keep the
    # verified number without forcing a second OTP round.
    mobile_verified_grace_seconds: int = 1800
    # Invite code that unlocks the analyst track. Empty means the track is
    # closed; the backend rejects every analyst request regardless of payload.
    analyst_invite_code: str = ""
    # Default daily PII reveal quota seeded onto freshly created realm users.
    # The tier ceiling in the token still applies.
    new_user_pii_quota: int = 0
    # Comma-separated realm roles the professional funnel may request.
    # Anything else -- notably ROLE_ADMIN / ROLE_SUPERVISOR -- is rejected
    # with 422 before it ever reaches Keycloak.
    professional_allowed_roles: str = (
        "ROLE_JUNIOR_BROKER,ROLE_SENIOR_BROKER,ROLE_AGENCY_MANAGER,ROLE_DATA_ANALYST"
    )

    # -- Cloud hub / sync (Phase 2) --------------------------------------------
    cloud_hub_base_url: str = "https://avgcrm.ir"
    sync_enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"
    redis_url_file: str = Field(default="", validation_alias="REDIS_URL_FILE", repr=False)
    divar_webhook_secret: str = "change-me-divar-hmac-secret"

    # -- Divar scraper (Phase 2) ------------------------------------------------
    scraper_enabled: bool = True
    divar_api_base_url: str = "https://api.divar.ir"
    divar_web_base_url: str = "https://divar.ir"
    # Sheypoor exposes its listing API under the web host; kept separate so a
    # future mobile-API host can be swapped in without touching the client.
    sheypoor_web_base_url: str = "https://www.sheypoor.com"

    def model_post_init(self, __context) -> None:
        if self.otp_hmac_secret_file:
            self.otp_hmac_secret = _read_runtime_secret_file(self.otp_hmac_secret_file)
        if self.redis_url_file:
            self.redis_url = _read_runtime_secret_file(self.redis_url_file)
    # Verified 2026-10-05 against the live API (see sheypoor_client.py). The
    # previous /api/web/v1/... defaults answered 404, which is why the one
    # Sheypoor job this node ever ran failed and the portal's feed stayed empty.
    sheypoor_search_path: str = "/api/v10.0.0/search"
    sheypoor_listing_path: str = ""
    # -- Nearby points of interest (Overpass) ---------------------------------
    # Overpass is a free public service with no SLA, so the result is cached per
    # ~111 m block for 7 days (see poi_service). An alternate mirror can be
    # swapped in here without touching the service.
    overpass_endpoint: str = "https://overpass-api.de/api/interpreter"
    poi_radius_m: int = 500
    poi_cache_ttl_days: int = 7

    # -- Delta scraper ---------------------------------------------------------
    # Delta is Next.js: there is no public JSON API. Listing data is embedded in
    # the RSC flight payload of the rendered HTML, so the client fetches pages and
    # extracts the schema.org/Product JSON-LD out of them.
    delta_web_base_url: str = "https://delta.ir"
    delta_detail_path: str = "/detail/{listing_id}"
    delta_search_path: str = "/{city}/{deal}/{property_type}"
    #: RSC flight row holding the detail JSON-LD. Delta has shipped this under a
    #: different row id across deploys, so the extractor scans for the row whose
    #: payload parses as a Product instead of trusting this alone.
    delta_flight_row: str = "28:"
    # curl_cffi impersonation target (browser TLS fingerprint)
    scraper_impersonate: str = "chrome124"
    scraper_timeout_seconds: int = 25
    scraper_max_retries: int = 4
    scraper_base_backoff_seconds: float = 1.5
    scraper_backoff_max_seconds: float = 30.0
    scraper_jitter_factor: float = 0.5
    scraper_pace_min_seconds: float = 1.2
    scraper_pace_max_seconds: float = 3.5
    scraper_page_size: int = 24
    # Comma-separated lists (parsed into tuples via properties below)
    proxy_pool: str = ""
    scraper_cities: str = "tehran"
    scraper_categories: str = (
        "apartment-sell,apartment-rent,house-villa-sell,house-villa-rent"
    )
    scraper_user_agents: str = ""
    #: Registry keys the scheduler crawls. Empty means every registered source.
    #:
    #: The scheduler used to take no source at all and let each job fall back to
    #: the node default (Divar), so Delta and Sheypoor were reachable by API but
    #: nothing ever queued them -- their feeds were permanently empty. Sources
    #: are named here so one portal being unreachable cannot silently drop the
    #: others: each is scheduled independently and a failure is recorded per job.
    scraper_sources: str = ""
    # Phone extraction (on-demand, session/OTP gated) cache
    phone_cache_ttl_seconds: int = 86400
    phone_extraction_enabled: bool = False
    # Backwards/e2e alias consumed by the services layer.
    phone_ttl_seconds: int = 86400

    # -- Scheduled ingestion (Phase 2b) -----------------------------------------
    # Autonomous periodic sweeps over SCRAPER_CITIES x SCRAPER_CATEGORIES.
    # Disabled by default: a node only crawls when explicitly told to.
    scraper_scheduler_enabled: bool = False
    scraper_schedule_interval_minutes: int = 60
    # Extra jitter (seconds) added to each interval so N workers/clients that
    # boot together do not fire on the same second.
    scraper_schedule_jitter_seconds: int = 90
    # First tick delay after boot, so the node does not scrape during startup.
    scraper_schedule_initial_delay_seconds: int = 30
    scraper_schedule_max_pages: int = 3
    # Skip a city whose previous scheduled job has not finished yet.
    scraper_schedule_skip_overlapping: bool = True

    # -- Matching engine (Phase 3) ----------------------------------------------
    # Minimum 0..100 score for a property/demand suggestion to be persisted.
    # Below this the row is not a suggestion, it is noise in the agent's queue.
    matching_min_score: float = 55.0
    matching_enabled: bool = True
    # Cap on demands scored per ingested listing (guards against a large book).
    matching_max_demands_per_property: int = 500

    # -- GIS helpers -------------------------------------------------------------
    # Nominatim API (used for reverse geocoding and autocomplete). The free public
    # service has no SLA, so a configured override can point the node at a mirror
    # for higher availability or a paid instance with SLAs. The cache in
    # ``app.services.geocode_cache`` limits downstream calls to once per ~50 m grid
    # cell.
    #
    # A node with ``osm_enabled=false`` degrades to an empty district instead
    # of failing the submission.
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_timeout_seconds: float = 10.0

    # -- Overpass API (for nearby POIs and polygons) --------------------------------
    # OpenStreetMap's query API. Also free public service with no SLA; use a
    # configured override for a mirror or paid instance.
    overpass_endpoint: str = "https://overpass-api.de/api/interpreter"
    overpass_timeout_seconds: float = 30.0

    # -- OSM/Overpass GIS service -------------------------------------------------
    # The node's configured GIS stack: Nominatim for geocoding, Overpass for
    # nearby POIs. A node with ``osm_enabled=false`` degrades to empty geocodes
    # and POIs, falling back to the legacy Iran Locations API for city lists.
    osm_enabled: bool = True
    osm_timeout_seconds: float = 10.0

    # -- Iran Locations API (self-hosted) --------------------------------------
    # The vendored `services/iran-locations-api` container, which serves the
    # province -> county tree from a local dataset with no platform key. It is
    # the primary source for the listing filter's city cascade; OSM stays the
    # fallback for everything else GIS (reverse geocode, nearby POIs).
    iran_locations_url: str = "http://iran_locations:3000"

    # -- Automated valuation (Phase 3b) -----------------------------------------
    valuation_enabled: bool = True
    # Re-value a listing after it changes; disabled means manual "refresh radar".
    valuation_auto_on_ingest: bool = False
    # Radius (metres) searched for comparables around the subject property.
    valuation_radius_m: int = 5000

    # ------------------------------------------------------------------ helpers
    @computed_field  # type: ignore[misc]
    @property
    def is_local_node(self) -> bool:
        return self.node_mode is NodeMode.LOCAL

    @computed_field  # type: ignore[misc]
    @property
    def is_cloud_hub(self) -> bool:
        return self.node_mode is NodeMode.CLOUD_HUB

    def resolve_path(self, path: Path | str) -> Path:
        """Resolve ``path`` against the project root when it is relative."""
        p = Path(path)
        return p if p.is_absolute() else (PROJECT_ROOT / p)

    # -------------------------------------------------- parsed list properties
    @staticmethod
    def _split_csv(value: str) -> tuple[str, ...]:
        return tuple(item.strip() for item in value.split(",") if item.strip())

    @property
    def proxy_list(self) -> tuple[str, ...]:
        """Configured outbound proxy pool (round-robin)."""
        return self._split_csv(self.proxy_pool)

    @property
    def professional_allowed_role_list(self) -> tuple[str, ...]:
        """Realm roles the professional funnel may request (upper-cased)."""
        return tuple(r.strip().upper() for r in self._split_csv(self.professional_allowed_roles))

    @property
    def city_list(self) -> tuple[str, ...]:
        return self._split_csv(self.scraper_cities)

    @property
    def category_list(self) -> tuple[str, ...]:
        return self._split_csv(self.scraper_categories)

    @property
    def source_list(self) -> tuple[str, ...]:
        """Registry keys the scheduler should crawl.

        Defaults to every registered source when unset. Unknown keys are dropped
        rather than raising, so a typo in the environment cannot take the whole
        scheduler down; the resolved list is logged by the scheduler on each tick.
        """
        from app.services.scraper.registry import SOURCES, UnknownSourceError, get_source

        configured = self._split_csv(self.scraper_sources)
        keys = configured or tuple(sorted(SOURCES))
        out: list[str] = []
        for key in keys:
            try:
                out.append(get_source(key).key)
            except UnknownSourceError:
                continue
        return tuple(out)

    @property
    def user_agent_list(self) -> tuple[str, ...]:
        return self._split_csv(self.scraper_user_agents)

    def ensure_directories(self) -> None:
        """Create the runtime directory tree if it does not exist yet."""
        for directory in (
            self.data_dir,
            self.media_dir,
            self.keys_dir,
            self.license_file.parent,
        ):
            self.resolve_path(directory).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide singleton :class:`Settings` instance."""
    return Settings()


def settings() -> Settings:
    """Convenience alias used across the codebase."""
    return get_settings()
