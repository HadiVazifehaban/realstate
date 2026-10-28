"""SQLModel table registry.

Importing this package registers every table on ``SQLModel.metadata`` which is
what Alembic and ``create_all`` rely on.
"""
from app.models.property_booking import PropertyVisitBooking
from app.models.chat import ChatConversation, ChatMembership, ChatMessage
from app.models.footer_social_link import FooterSocialLink

from app.models.registration import AuthAuditLog, ProfessionalApplication
from app.models.billing import (
    AgencySubscription,
    AgencyWallet,
    AgencyReferral,
    FinancialAuditLog,
    PaymentAttempt,
    PaymentOrder,
    SubscriptionPlan,
    ZibalGatewayConfiguration,
    PaymentReceipt,
    PaymentReview,
    ReferralCredit,
    WalletTransaction,
)

from app.models.agency_user import AgencyUser
from app.models.client_demand import ClientDemand
from app.models.crm import CrmLead, LeadInteraction
from app.models.enums import (
    AgencyStatus,
    AggregateType,
    CooperationScope,
    CooperationStatus,
    AuditAction,
    CommissionModel,
    CommissionStatus,
    DisputeCategory,
    DisputeStatus,
    ListingShareMode,
    ReferralStatus,
    ShareStatus,
    TransferStatus,
    DealType,
    DemandStatus,
    InteractionType,
    LeadPriority,
    LeadStage,
    MatchStatus,
    MediaSyncStatus,
    MediaType,
    NodeMode,
    PropertySource,
    PropertyStatus,
    PropertyType,
    PriceChangeSource,
    SaasTier,
    ValuationStatus,
    ScrapeJobKind,
    ScrapeJobStatus,
    ScrapeJobTrigger,
    SyncStatus,
    SubmitterType,
    UserRole,
    AgencyStatus,
    CooperationScope,
    CooperationStatus,
)
from app.models.geo_cache import GeoCache
from app.models.node_license import NodeLicense
from app.models.owner_access_log import OwnerAccessLog
from app.models.pii_quota import PiiQuota
from app.models.property import Property
from app.models.property_match import PropertyMatch
from app.models.poi_cache import PoiCache
from app.models.property_media import PropertyMedia
from app.models.property_owner_pii import PropertyOwnerPII
from app.models.property_price_history import PropertyPriceHistory
from app.models.property_report import PropertyReport
from app.models.publication import (
    PropertyMediaPublication,
    PropertyPublication,
    PropertyPublicationAudit,
)
from app.models.scrape_job import ScrapeJob
from app.models.sync_outbox import SyncOutbox
from app.models.user_preference import UserPreference
from app.models.agency_network import Agency, AgencyCooperation, AgencyMembership
from app.models.network_collab import (
    AuditEvent,
    CommissionAgreement,
    CommissionAllocation,
    CommissionPayment,
    DisputeCase,
    DisputeMessage,
    LeadReferral,
    ListingShare,
    ListingSharePermission,
    ListingTransferHistory,
)

__all__ = [
    "ChatConversation",
    "ChatMembership",
    "ChatMessage",
    "FooterSocialLink",
    "AgencyUser",
    "AuthAuditLog",
    "ProfessionalApplication",
    "AgencySubscription",
    "AgencyReferral",
    "ReferralCredit",
    "AgencyWallet",
    "PaymentAttempt",
    "WalletTransaction",
    "PaymentOrder",
    "SubscriptionPlan",
    "ZibalGatewayConfiguration",
    "PaymentReceipt",
    "PaymentReview",
    "FinancialAuditLog",
    "CrmLead",
    "GeoCache",
    "ClientDemand",
    "LeadInteraction",
    "NodeLicense",
    "OwnerAccessLog",
    "PiiQuota",
    "Property",
    "PropertyMatch",
    "PoiCache",
    "PropertyMedia",
    "PropertyOwnerPII",
    "PropertyPriceHistory",
    "PropertyReport",
    "ScrapeJob",
    "SyncOutbox",
    "UserPreference",
    "Agency",
    "AgencyCooperation",
    "AgencyMembership",
    "ListingShare",
    "ListingSharePermission",
    "LeadReferral",
    "ListingTransferHistory",
    "CommissionAgreement",
    "CommissionAllocation",
    "CommissionPayment",
    "DisputeCase",
    "DisputeMessage",
    "AuditEvent",
    "AggregateType",
    "DealType",
    "DemandStatus",
    "InteractionType",
    "LeadPriority",
    "LeadStage",
    "MatchStatus",
    "MediaSyncStatus",
    "MediaType",
    "NodeMode",
    "PropertySource",
    "PropertyStatus",
    "PropertyType",
    "PriceChangeSource",
    "SaasTier",
    "ValuationStatus",
    "ScrapeJobKind",
    "ScrapeJobStatus",
    "ScrapeJobTrigger",
    "SyncStatus",
    "AgencyStatus",
    "CooperationScope",
    "CooperationStatus",
    "UserRole",
]
