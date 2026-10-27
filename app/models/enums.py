"""Enumerations shared across models, schemas and services."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String enum that serialises to its value."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class NodeMode(str, Enum):
    LOCAL = "LOCAL"
    CLOUD_HUB = "CLOUD_HUB"


class UserRole(StrEnum):
    """Seven-tier RBAC ladder (Phase 5).

    Ordered from least to most privileged; the CRM and PII guards compare
    against these members rather than hard-coding strings.
    """

    GUEST = "GUEST"                    # بازدیدکننده ویترین عمومی
    USER = "USER"                      # کاربر احراز هویت‌شده
    OWNER = "OWNER"                    # مالک ملک (ثبت مستقیم)
    AGENT = "AGENT"                    # مشاور املاک
    OFFICE_MANAGER = "OFFICE_MANAGER"  # مدیر دفتر
    SUPERVISOR = "SUPERVISOR"          # ناظر کیفی و حقوقی
    ADMIN = "ADMIN"                    # مدیر ارشد سامانه


class PaymentOrderStatus(StrEnum):
    CREATED = "created"
    PENDING_PAYMENT = "pending_payment"
    AWAITING_TRANSFER = "awaiting_transfer"
    RECEIPT_SUBMITTED = "receipt_submitted"
    UNDER_REVIEW = "under_review"
    TEST_APPROVED_NO_ACTIVATION = "test_approved_no_activation"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PaymentEnvironmentMode(StrEnum):
    TEST = "test"
    LIVE = "live"


class PaymentReviewDecision(StrEnum):
    STARTED = "started"
    APPROVED = "approved"
    REJECTED = "rejected"
    TEST_APPROVED = "test_approved"


class AgencyReferralStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    VOIDED = "VOIDED"


class ReferralCreditStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    PENDING = "PENDING"
    RESERVED = "RESERVED"
    CONSUMED = "CONSUMED"
    RELEASED = "RELEASED"
    VOIDED = "VOIDED"


# Roles allowed to decrypt owner PII. Managers and agents consume plan quota;
# supervisors and admins are exempt (they need it for dispute resolution).
PII_READER_ROLES: frozenset[UserRole] = frozenset(
    {UserRole.AGENT, UserRole.OFFICE_MANAGER, UserRole.SUPERVISOR, UserRole.ADMIN}
)

# Roles allowed to move a lead to CLOSED_DEAL.
LEAD_CLOSER_ROLES: frozenset[UserRole] = frozenset({UserRole.OFFICE_MANAGER, UserRole.ADMIN})

# Roles allowed to override automated valuation parameters or merge duplicates.
DATA_GOVERNOR_ROLES: frozenset[UserRole] = frozenset({UserRole.SUPERVISOR, UserRole.ADMIN})


class PropertySource(StrEnum):
    """Listing origin, ordered by data provenance precedence.

    ``INTERNAL_USER`` wins over ``INTERNAL_AGENCY``, which wins over portal
    scrapes. ``DEDUPLICATOR.precedence_for`` turns this ordering into the
    numeric score used when two listings claim the same physical unit, so a
    direct owner registration always overwrites a scraped record.
    """

    INTERNAL_USER = "INTERNAL_USER"        # ثبت مستقیم مالک — بالاترین تقدم
    INTERNAL_AGENCY = "INTERNAL_AGENCY"    # ثبت مستقیم دفتر/مشاور
    SHEYPOOR = "SHEYPOOR"                  # اسکرپ شیپور
    DIVAR = "DIVAR"                        # اسکرپ دیوار
    DELTA = "DELTA"                        # اسکرپ دلتا
    MLS_IMPORT = "MLS_IMPORT"              # واردشده از شبکه همکاران

    # Legacy members kept so existing rows stay valid; they map onto the
    # sources above via LEGACY_SOURCE_ALIASES.
    DIVAR_KENAR = "DIVAR_KENAR"
    DIVAR_SCRAPER = "DIVAR_SCRAPER"
    MANUAL_OFFICE = "MANUAL_OFFICE"


#: Legacy -> canonical source mapping, applied on read so old rows dedupe and
#: rank exactly like their modern equivalents.
LEGACY_SOURCE_ALIASES: dict[PropertySource, PropertySource] = {
    PropertySource.DIVAR_KENAR: PropertySource.DIVAR,
    PropertySource.DIVAR_SCRAPER: PropertySource.DIVAR,
    PropertySource.MANUAL_OFFICE: PropertySource.INTERNAL_AGENCY,
}

#: Higher wins. Kept as an explicit table (not dict ordering) so the precedence
#: is reviewable and testable as a single source of truth.
SOURCE_PRECEDENCE: dict[PropertySource, int] = {
    PropertySource.INTERNAL_USER: 100,
    PropertySource.INTERNAL_AGENCY: 80,
    PropertySource.SHEYPOOR: 40,
    PropertySource.DIVAR: 40,
    # Delta publishes an agency as `offeredBy`/`realEstateAgency` in its own
    # JSON-LD, so a row can often be attributed to a named broker. Ranked with
    # the other portals rather than with INTERNAL_AGENCY: the node still only
    # has the scraped copy.
    PropertySource.DELTA: 40,
    PropertySource.MLS_IMPORT: 60,
    PropertySource.DIVAR_KENAR: 40,
    PropertySource.DIVAR_SCRAPER: 40,
    PropertySource.MANUAL_OFFICE: 80,
}


class SubmitterType(StrEnum):
    """Who filed the listing: a natural person or an agency.

    Deliberately **not** the same question as :class:`PropertySource`.

    ``source`` answers *which channel* the row arrived through (a portal scrape,
    an MLS import, a first-party registration). ``submitter_type`` answers *what
    kind of party* pressed submit. A broker filing on behalf of a natural-person
    owner is ``AGENCY`` here while the owner contacts in the vault stay the
    owner's -- the two facts are independent and collapsing them is how a
    listing ends up advertising an office as its own seller.

    Derived from the signed token, never from the request body: see
    :data:`SUBMITTER_TYPE_BY_ROLE`.
    """

    PERSON = "PERSON"        # شخص حقیقی — ثبت‌کننده خودِ مالک
    AGENCY = "AGENCY"        # بنگاه/دفتر — ثبت توسط مشاور یا مدیر


#: Internal role -> the kind of submitter that role is. The single translation
#: point, so the submitter class is read off the realm role the same way the
#: rest of the ladder is. A role absent here cannot file a first-party listing
#: at all, so there is no default to fall back to.
SUBMITTER_TYPE_BY_ROLE: dict[UserRole, SubmitterType] = {
    UserRole.OWNER: SubmitterType.PERSON,
    UserRole.AGENT: SubmitterType.AGENCY,
    UserRole.OFFICE_MANAGER: SubmitterType.AGENCY,
    UserRole.SUPERVISOR: SubmitterType.AGENCY,
    UserRole.ADMIN: SubmitterType.AGENCY,
}

#: Roles allowed to file a first-party listing. ``USER``/``GUEST`` are excluded
#: on purpose: an authenticated visitor is not a submitter, and the public
#: showcase plus the report endpoint cover what they may do.
SUBMITTER_ROLES: frozenset[UserRole] = frozenset(SUBMITTER_TYPE_BY_ROLE)


class PropertyType(StrEnum):
    APARTMENT = "APARTMENT"        # آپارتمان
    SUITE = "SUITE"                # سوئیت و اتاق (اجاره کوتاه‌مدت)
    VILLA = "VILLA"                # ویلا / خانه
    PENTHOUSE = "PENTHOUSE"        # پنت‌هاوس
    LAND = "LAND"                  # زمین / کلنگی
    OFFICE = "OFFICE"              # دفتر کار
    STORE = "STORE"                # مغازه
    WAREHOUSE = "WAREHOUSE"        # انبار / سوله
    INDUSTRIAL = "INDUSTRIAL"      # صنعتی، کشاورزی و تجاری
    GARDEN = "GARDEN"              # باغ / باغچه


class DealType(StrEnum):
    SALE = "SALE"                  # فروش
    RENT = "RENT"                  # رهن و اجاره
    FULL_MORTGAGE = "FULL_MORTGAGE"  # رهن کامل


class LeadStage(StrEnum):
    """The five-column CRM pipeline (Phase 5).

    ``VISITING`` is a *stage*, never a date. The actual appointment timestamp
    lives on :class:`LeadInteraction` as ``scheduled_at`` — there is deliberately
    no ``visit_date`` column anywhere in the schema.
    """

    NEW_FILE = "NEW_FILE"                # فایل جدید
    CONTACTING = "CONTACTING"            # تماس اولیه
    APPRAISAL = "APPRAISAL"              # کارشناسی/بازدید هماهنگ‌شده
    CONTRACT_READY = "CONTRACT_READY"    # توافق و آماده‌سازی قرارداد
    CLOSED_DEAL = "CLOSED_DEAL"          # معامله موفق
    LOST_ARCHIVED = "LOST_ARCHIVED"      # معامله از دست رفته


#: Allowed forward transitions. Anything not listed here is rejected with a
#: 409 by the CRM endpoint, so a column can never be skipped.
LEAD_TRANSITIONS: dict[LeadStage, frozenset[LeadStage]] = {
    LeadStage.NEW_FILE: frozenset(
        {LeadStage.CONTACTING, LeadStage.LOST_ARCHIVED}
    ),
    LeadStage.CONTACTING: frozenset(
        {LeadStage.APPRAISAL, LeadStage.LOST_ARCHIVED}
    ),
    LeadStage.APPRAISAL: frozenset(
        {LeadStage.CONTRACT_READY, LeadStage.LOST_ARCHIVED}
    ),
    LeadStage.CONTRACT_READY: frozenset(
        {LeadStage.CLOSED_DEAL, LeadStage.LOST_ARCHIVED}
    ),
    # Terminal states; only a governor (ADMIN) may reopen a closed deal.
    LeadStage.CLOSED_DEAL: frozenset({LeadStage.APPRAISAL}),
    LeadStage.LOST_ARCHIVED: frozenset({LeadStage.NEW_FILE}),
}

#: The five columns rendered on the desk, in order. ``LOST_ARCHIVED`` is a
#: terminal sink rather than a visible column.
KANBAN_COLUMNS: tuple[LeadStage, ...] = (
    LeadStage.NEW_FILE,
    LeadStage.CONTACTING,
    LeadStage.APPRAISAL,
    LeadStage.CONTRACT_READY,
    LeadStage.CLOSED_DEAL,
)


class InteractionType(StrEnum):
    """CRM timeline events.

    ``VISIT_EVENT`` carries the appointment time in ``LeadInteraction.scheduled_at``
    — this is the only sanctioned home for a visit timestamp.
    """

    PHONE_CALL = "PHONE_CALL"
    VISIT_EVENT = "VISIT_EVENT"
    NOTE_ADDED = "NOTE_ADDED"
    PRICE_OFFER = "PRICE_OFFER"
    STAGE_CHANGED = "STAGE_CHANGED"


class SaasTier(StrEnum):
    """Subscription level; drives daily PII decryption quota."""

    FREE = "FREE"
    BASIC = "BASIC"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


#: Daily owner-phone reveal allowance per tier (-1 = unlimited).
TIER_PII_DAILY_QUOTA: dict[SaasTier, int] = {
    SaasTier.FREE: 5,
    SaasTier.BASIC: 30,
    SaasTier.PRO: 100,
    SaasTier.ENTERPRISE: -1,
}


class LeadPriority(StrEnum):
    URGENT_BARGAIN = "URGENT_BARGAIN"  # لید شکار بازار
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class PropertyStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    RESERVED = "RESERVED"          # رزرو شده
    SOLD = "SOLD"
    RENTED = "RENTED"
    # Pulled by the owner or a moderator. Kept distinct from ARCHIVED (which is
    # a closed deal) so withdrawn inventory can be suppressed without hiding
    # historic deals.
    WITHDRAWN = "WITHDRAWN"
    ARCHIVED = "ARCHIVED"


class VisitSlotStatus(StrEnum):
    """One slot's life-cycle in the visit scheduler."""

    DRAFT = "DRAFT"                    # آماده‌ی تغییر، برای دفتر
    REQUESTED = "REQUESTED"            # درخواست داده، منتظر تایید
    CONFIRMED = "CONFIRMED"            # تایید شده، به زمان بستن می‌رسد
    CANCELLED = "CANCELLED"            # لغو شده
    NO_SHOW = "NO_SHOW"                # شرکت نکردن
    COMPLETED = "COMPLETED"            # به زنگ آمد، آموزش به اتمام رسید


#: What kind of slot this is, used to show the right label and glyph.
class VisitSlotKind(StrEnum):
    """Kind of calendar slot rendered by the scheduler widget."""

    OFFICE_HOUSE = "OFFICE_HOUSE"      # دیدگاه تمام‌زمان در دفتر
    PHONE = "PHONE"                    # تماس تلفنی
    VIRTUAL = "VIRTUAL"                # دیدگاه آنلاین


#: Statuses the matching engine will surface as fresh suggestions. RESERVED stays
#: matchable — a flat under offer is still a lead worth chasing. Defined here so
#: the service and the repository share one source of truth.
MATCHABLE_STATUSES: frozenset[PropertyStatus] = frozenset(
    {PropertyStatus.ACTIVE, PropertyStatus.RESERVED}
)


class MediaType(StrEnum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    FLOOR_PLAN = "FLOOR_PLAN"


class MediaSyncStatus(StrEnum):
    LOCAL_ONLY = "LOCAL_ONLY"
    PENDING_UPLOAD = "PENDING_UPLOAD"
    SYNCED_TO_CLOUD = "SYNCED_TO_CLOUD"
    FAILED = "FAILED"


class SyncStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    RETRY_FAILED = "RETRY_FAILED"


class AggregateType(StrEnum):
    PROPERTY_MLS_SHARE = "PROPERTY_MLS_SHARE"
    COLLABORATION_REQUEST = "COLLABORATION_REQUEST"
    PRICE_UPDATE = "PRICE_UPDATE"


class DemandStatus(StrEnum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    VISITING = "VISITING"
    MATCHED = "MATCHED"
    CLOSED = "CLOSED"
    LOST = "LOST"


class MatchStatus(StrEnum):
    NEW = "NEW"            # تازه پیشنهاد شده — منتظر اقدام مشاور
    SEEN = "SEEN"          # مشاور دیده، هنوز تصمیمی نگرفته
    SHORTLISTED = "SHORTLISTED"  # در فهرست کوتاه
    DISMISSED = "DISMISSED"      # رد شد (نامرتبط)
    CONTACTED = "CONTACTED"      # تماس گرفته شد


class PriceChangeSource(StrEnum):
    SCRAPER = "SCRAPER"        # کشف خودکار در اسکرپ
    MANUAL = "MANUAL"          # ویرایش مشاور/مدیر
    OWNER = "OWNER"            # ثبت مستقیم توسط مالک
    AVM = "AVM"                # بازمحاسبه موتور ارزش‌گذاری


class ValuationStatus(StrEnum):
    BARGAIN = "BARGAIN"        # زیر قیمت بازار
    FAIR = "FAIR"              # منصفانه
    OVERPRICED = "OVERPRICED"  # بالاتر از بازار
    UNKNOWN = "UNKNOWN"        # داده کافی برای قضاوت وجود ندارد


class ScrapeJobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ScrapeJobTrigger(StrEnum):
    MANUAL = "MANUAL"          # دکمه دستی مشاور/مدیر
    SCHEDULED = "SCHEDULED"    # کرون/جاب زمان‌بندی‌شده
    API = "API"                # فراخوانی مستقیم API


class ScrapeJobKind(StrEnum):
    SEARCH = "SEARCH"          # اسکرپ فهرست نتایج
    DETAIL = "DETAIL"          # اسکرپ جزئیات یک آگهی
    PHONE = "PHONE"            # استخراج شماره تماس


# Re-export the licensing status so models/schemas have a single import point.
from app.core.licensing import LicenseStatus  # noqa: E402,F401


# --------------------------------------------------------------------------- #
# Inter-agency collaboration network (شبکه همکاری دفاتر)
# --------------------------------------------------------------------------- #
class CooperationStatus(str, Enum):
    """Where a request to work with another office stands.

    Distinct from a share's own state: a *request* asks for the relationship,
    a *share* grants access to one file inside it. Collapsing the two is what
    makes an MLS network impossible to audit -- you can no longer tell whether
    a partner office may see a listing because the offices agreed, or because
    one broker shared it once.
    """

    PENDING = "PENDING"                  # sent, awaiting the other office
    APPROVED = "APPROVED"                # offices may work together
    REJECTED = "REJECTED"                # declined; reason is recorded
    COUNTER = "COUNTER"                  # replied asking for changes
    REVOKED = "REVOKED"                  # was approved, later withdrawn


class CooperationScope(str, Enum):
    """What kind of work the two offices agreed to do together.

    Deliberately not a boolean matrix here: the scope is the shape of the
    relationship, while the per-listing permission matrix lives on the share.
    """

    SHARE_LISTINGS = "SHARE_LISTINGS"        #互相可见 listings
    REFER_LEADS = "REFER_LEADS"              # pass clients to each other
    CO_BROKE = "CO_BROKE"                    # joint deals, shared commission
    FULL_MERGE = "FULL_MERGE"                # one book, one brand


class AgencyStatus(str, Enum):
    """Trust state of an office on the network.

    ``SUSPENDED`` keeps the history: a network admin pulls an office out of
    rotation without deleting the agreements or commissions it already closed.
    """

    PENDING = "PENDING"        # registered, not yet vouched for
    VERIFIED = "VERIFIED"      # papers checked
    SUSPENDED = "SUSPENDED"    # barred from new work


# --------------------------------------------------------------------------- #
# Listing shares, referrals, transfers, commissions, disputes, audit
# --------------------------------------------------------------------------- #
class ListingShareMode(str, Enum):
    """How one office lets another office work a single file.

    The three modes are genuinely different operations and must never collapse
    into one flag -- a *share* lends read access, a *referral* hands a lead over
    while the file stays put, and a *transfer* moves responsibility. Treating a
    transfer as a share is how an MLS loses track of who actually owns a file.
    """

    SHARE = "SHARE"            # lend access to this one file
    REFERRAL = "REFERRAL"      # pass a lead/client to the partner office
    TRANSFER = "TRANSFER"      # move responsibility for the file


class ShareStatus(str, Enum):
    """Lifecycle of a single listing share."""

    ACTIVE = "ACTIVE"          # partner office may act within the granted scope
    EXPIRED = "EXPIRED"        # passed its expiry; access is blocked
    REVOKED = "REVOKED"        # withdrawn early by the owner
    PENDING = "PENDING"        # created, awaiting the partner to acknowledge


class ReferralStatus(str, Enum):
    """Where a referred lead stands. Kept separate from a share because a
    referral is a client hand-off, not file access."""

    SENT = "SENT"
    VIEWED = "VIEWED"
    ACCEPTED = "ACCEPTED"
    IN_FOLLOW_UP = "IN_FOLLOW_UP"
    CONVERTED = "CONVERTED"
    LOST = "LOST"
    CANCELLED = "CANCELLED"


class TransferStatus(str, Enum):
    """State of a listing-ownership transfer between offices."""

    PENDING = "PENDING"        # requested, awaiting confirmation
    COMPLETED = "COMPLETED"    # responsibility moved; history preserved
    REJECTED = "REJECTED"      # refused; file stays with the owner
    CANCELLED = "CANCELLED"    # withdrawn by the requester


class CommissionModel(str, Enum):
    """How a co-broke commission is expressed on an agreement."""

    PERCENTAGE = "PERCENTAGE"  # split of the deal commission, in percent
    FIXED = "FIXED"            # fixed amount per side


class CommissionStatus(str, Enum):
    """Lifecycle of a commission agreement.

    ``LOCKED`` is the point of no return: once both offices accept the split it
    can only change through an authorised amendment, never a silent edit.
    """

    DRAFT = "DRAFT"
    LOCKED = "LOCKED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    SETTLED = "SETTLED"
    DISPUTED = "DISPUTED"


class DisputeCategory(str, Enum):
    """Why two offices fell out. A typed category keeps the dispute inbox
    sortable and stops 'other' from swallowing every real case."""

    COMMISSION_MISMATCH = "COMMISSION_MISMATCH"
    OWNERSHIP = "OWNERSHIP"
    UNAUTHORIZED_CONTACT = "UNAUTHORIZED_CONTACT"
    UNAUTHORIZED_RESHARE = "UNAUTHORIZED_RESHARE"
    CLIENT_OWNERSHIP = "CLIENT_OWNERSHIP"
    SETTLEMENT_DELAY = "SETTLEMENT_DELAY"
    POLICY_VIOLATION = "POLICY_VIOLATION"


class DisputeStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    WAITING_RESPONSE = "WAITING_RESPONSE"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class AuditAction(str, Enum):
    """Security-sensitive network actions that must leave a trail.

    The reveal/export/access-change events are the ones a dispute or a
    compliance audit will ask about first, so they are first-class values
    rather than a free-text log line.
    """

    OWNER_PHONE_REVEALED = "OWNER_PHONE_REVEALED"
    ADDRESS_REVEALED = "ADDRESS_REVEALED"
    LISTING_EXPORTED = "LISTING_EXPORTED"
    PERMISSION_CHANGED = "PERMISSION_CHANGED"
    SHARE_CREATED = "SHARE_CREATED"
    SHARE_REVOKED = "SHARE_REVOKED"
    SHARE_EXTENDED = "SHARE_EXTENDED"
    TRANSFER_EXECUTED = "TRANSFER_EXECUTED"
    COMMISSION_MODIFIED = "COMMISSION_MODIFIED"
    COMMISSION_LOCKED = "COMMISSION_LOCKED"
    PAYMENT_RECORDED = "PAYMENT_RECORDED"
    DISPUTE_OPENED = "DISPUTE_OPENED"
    DISPUTE_RESOLVED = "DISPUTE_RESOLVED"
