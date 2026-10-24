/**
 * Types and Persian labels for the inter-agency collaboration network.
 *
 * The string enums mirror the backend exactly (they travel over the wire as the
 * raw enum values), and each carries a Persian label so the UI never has to
 * re-derive a display name from a status code.
 */

export type AgencyStatus = 'PENDING' | 'VERIFIED' | 'SUSPENDED';
export type CooperationStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'COUNTER' | 'REVOKED';
export type CooperationScope = 'SHARE_LISTINGS' | 'REFER_LEADS' | 'CO_BROKE' | 'FULL_MERGE';
export type ShareMode = 'SHARE' | 'REFERRAL' | 'TRANSFER';
export type ShareStatus = 'ACTIVE' | 'EXPIRED' | 'REVOKED' | 'PENDING';
export type ReferralStatus =
  | 'SENT'
  | 'VIEWED'
  | 'ACCEPTED'
  | 'IN_FOLLOW_UP'
  | 'CONVERTED'
  | 'LOST'
  | 'CANCELLED';
export type TransferStatus = 'PENDING' | 'COMPLETED' | 'REJECTED' | 'CANCELLED';
export type CommissionModel = 'PERCENTAGE' | 'FIXED';
export type CommissionStatus =
  | 'DRAFT'
  | 'LOCKED'
  | 'PARTIALLY_PAID'
  | 'SETTLED'
  | 'DISPUTED';
export type DisputeCategory =
  | 'COMMISSION_MISMATCH'
  | 'OWNERSHIP'
  | 'UNAUTHORIZED_CONTACT'
  | 'UNAUTHORIZED_RESHARE'
  | 'CLIENT_OWNERSHIP'
  | 'SETTLEMENT_DELAY'
  | 'POLICY_VIOLATION';
export type DisputeStatus =
  | 'OPEN'
  | 'UNDER_REVIEW'
  | 'WAITING_RESPONSE'
  | 'RESOLVED'
  | 'REJECTED'
  | 'ESCALATED';
export type AuditAction =
  | 'OWNER_PHONE_REVEALED'
  | 'ADDRESS_REVEALED'
  | 'LISTING_EXPORTED'
  | 'PERMISSION_CHANGED'
  | 'SHARE_CREATED'
  | 'SHARE_REVOKED'
  | 'SHARE_EXTENDED'
  | 'TRANSFER_EXECUTED'
  | 'COMMISSION_MODIFIED'
  | 'COMMISSION_LOCKED'
  | 'PAYMENT_RECORDED'
  | 'DISPUTE_OPENED'
  | 'DISPUTE_RESOLVED';

export const SHARE_STATUS_LABELS: Record<ShareStatus, string> = {
  ACTIVE: 'فعال',
  EXPIRED: 'منقضی‌شده',
  REVOKED: 'لغوشده',
  PENDING: 'در انتظار'
};

export const SHARE_MODE_LABELS: Record<ShareMode, string> = {
  SHARE: 'اشتراک فایل',
  REFERRAL: 'ارجاع مشتری',
  TRANSFER: 'انتقال فایل'
};

export const REFERRAL_STATUS_LABELS: Record<ReferralStatus, string> = {
  SENT: 'ارسال‌شده',
  VIEWED: 'دیده‌شده',
  ACCEPTED: 'پذیرفته‌شده',
  IN_FOLLOW_UP: 'در پیگیری',
  CONVERTED: 'تبدیل‌شده',
  LOST: 'ازدست‌رفته',
  CANCELLED: 'لغوشده'
};

export const TRANSFER_STATUS_LABELS: Record<TransferStatus, string> = {
  PENDING: 'در انتظار',
  COMPLETED: 'انجام‌شده',
  REJECTED: 'ردشده',
  CANCELLED: 'لغوشده'
};

export const COMMISSION_STATUS_LABELS: Record<CommissionStatus, string> = {
  DRAFT: 'پیش‌نویس',
  LOCKED: 'قفل‌شده',
  PARTIALLY_PAID: 'پرداخت جزئی',
  SETTLED: 'تسویه‌شده',
  DISPUTED: 'مورد اختلاف'
};

export const DISPUTE_CATEGORY_LABELS: Record<DisputeCategory, string> = {
  COMMISSION_MISMATCH: 'اختلاف پورسانت',
  OWNERSHIP: 'اختلاف مالکیت فایل',
  UNAUTHORIZED_CONTACT: 'تماس غیرمجاز',
  UNAUTHORIZED_RESHARE: 'اشتراک‌گذاری مجدد غیرمجاز',
  CLIENT_OWNERSHIP: 'ادعای مالکیت مشتری',
  SETTLEMENT_DELAY: 'تأخیر تسویه',
  POLICY_VIOLATION: 'نقض مقررات'
};

export const DISPUTE_STATUS_LABELS: Record<DisputeStatus, string> = {
  OPEN: 'باز',
  UNDER_REVIEW: 'در بررسی',
  WAITING_RESPONSE: 'در انتظار پاسخ',
  RESOLVED: 'حل‌شده',
  REJECTED: 'ردشده',
  ESCALATED: 'ارجاع‌شده به بالادست'
};

export const AUDIT_ACTION_LABELS: Record<AuditAction, string> = {
  OWNER_PHONE_REVEALED: 'افشای شمارهٔ مالک',
  ADDRESS_REVEALED: 'افشای آدرس دقیق',
  LISTING_EXPORTED: 'خروجی گرفتن از فایل',
  PERMISSION_CHANGED: 'تغییر سطح دسترسی',
  SHARE_CREATED: 'ایجاد اشتراک',
  SHARE_REVOKED: 'لغو اشتراک',
  SHARE_EXTENDED: 'تمدید اشتراک',
  TRANSFER_EXECUTED: 'اجرای انتقال فایل',
  COMMISSION_MODIFIED: 'تغییر پورسانت',
  COMMISSION_LOCKED: 'قفل پورسانت',
  PAYMENT_RECORDED: 'ثبت پرداخت',
  DISPUTE_OPENED: 'ثبت اختلاف',
  DISPUTE_RESOLVED: 'حل اختلاف'
};

export const AGENCY_STATUS_LABELS: Record<AgencyStatus, string> = {
  PENDING: 'در انتظار تأیید',
  VERIFIED: 'تأییدشده',
  SUSPENDED: 'معلق'
};

export const COOPERATION_STATUS_LABELS: Record<CooperationStatus, string> = {
  PENDING: 'در انتظار پاسخ',
  APPROVED: 'پذیرفته‌شده',
  REJECTED: 'ردشده',
  COUNTER: 'پیشنهاد متقابل',
  REVOKED: 'لغوشده'
};

export const COOPERATION_SCOPE_LABELS: Record<CooperationScope, string> = {
  SHARE_LISTINGS: 'اشتراک فایل',
  REFER_LEADS: 'ارجاع سرنخ',
  CO_BROKE: 'معاملهٔ مشترک (کوبروک)',
  FULL_MERGE: 'ادغام کامل'
};

// --------------------------------------------------------------------------- //
// Wire shapes
// --------------------------------------------------------------------------- //
export interface Agency {
  id: string;
  slug: string;
  name: string;
  name_fa: string;
  city: string;
  district: string;
  phone: string;
  logo_url: string;
  description: string;
  status: AgencyStatus;
  display_name: string;
  created_at: string;
}

export interface Cooperation {
  id: string;
  requester_agency_id: string;
  target_agency_id: string;
  status: CooperationStatus;
  scope: CooperationScope;
  granted_scope_list: CooperationScope[];
  default_commission_pct: number;
  expires_at: string | null;
  decided_at: string | null;
  decision_reason: string;
  requested_by: string;
  decided_by: string;
  created_at: string;
}

export interface CooperationCreate {
  requester_agency_id: string;
  target_agency_id: string;
  scope: CooperationScope;
  default_commission_pct?: number;
  expires_in_days?: number | null;
}

export interface CooperationDecision {
  granted_scopes?: CooperationScope[];
  reason?: string;
}

export interface SharePermissions {
  view_summary: boolean;
  view_full_details: boolean;
  show_owner_phone: boolean;
  show_exact_address: boolean;
  allow_notes: boolean;
  allow_visit_request: boolean;
  allow_negotiation: boolean;
  allow_export: boolean;
  allow_re_share: boolean;
  updated_at: string;
  updated_by: string;
}

export interface Share {
  id: string;
  property_id: string;
  source_agency_id: string;
  target_agency_id: string;
  mode: ShareMode;
  status: ShareStatus;
  target_agent: string;
  note: string;
  expires_at: string | null;
  created_by: string;
  created_at: string;
  revoked_at: string | null;
}

export interface ShareDetail extends Share {
  internal_note: string;
  permissions: SharePermissions;
}

export interface SharePermissionInput {
  view_summary?: boolean;
  view_full_details?: boolean;
  show_owner_phone?: boolean;
  show_exact_address?: boolean;
  allow_notes?: boolean;
  allow_visit_request?: boolean;
  allow_negotiation?: boolean;
  allow_export?: boolean;
  allow_re_share?: boolean;
}

export interface ShareCreate {
  property_id: string;
  source_agency_id: string;
  target_agency_id: string;
  mode: ShareMode;
  target_agent?: string;
  note?: string;
  internal_note?: string;
  expires_in_days?: number | null;
  permissions: SharePermissionInput;
}

export interface Referral {
  id: string;
  subject: string;
  client_masked: string;
  source_agency_id: string;
  target_agency_id: string;
  property_id: string | null;
  assigned_to: string;
  referral_fee_pct: number;
  stage: ReferralStatus;
  note: string;
  outcome: string;
  created_at: string;
  updated_at: string;
}

export interface ReferralCreate {
  subject: string;
  client_masked?: string;
  source_agency_id: string;
  target_agency_id: string;
  property_id?: string | null;
  assigned_to?: string;
  referral_fee_pct?: number;
  note?: string;
}

export interface ReferralStageUpdate {
  stage: ReferralStatus;
  outcome?: string;
}

export interface Transfer {
  id: string;
  property_id: string;
  from_agency_id: string;
  to_agency_id: string;
  from_user: string;
  to_user: string;
  status: TransferStatus;
  reason: string;
  residual_commission_pct: number;
  executed_by: string;
  executed_at: string | null;
  created_at: string;
}

export interface TransferCreate {
  property_id: string;
  from_agency_id: string;
  to_agency_id: string;
  to_user?: string;
  reason: string;
  residual_commission_pct?: number;
  confirm: boolean;
}

export interface CommissionAllocation {
  id: string;
  agency_id: string | null;
  agent: string;
  percent: number;
  fixed_amount: number;
}

export interface Payment {
  id: string;
  allocation_id: string;
  amount: number;
  reference: string;
  note: string;
  recorded_by: string;
  recorded_at: string;
}

export interface CommissionAgreement {
  id: string;
  property_id: string | null;
  source_agency_id: string;
  target_agency_id: string;
  model: CommissionModel;
  status: CommissionStatus;
  basis_amount: number;
  currency: string;
  note: string;
  locked_by: string;
  locked_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface CommissionAgreementDetail extends CommissionAgreement {
  allocations: CommissionAllocation[];
  payments: Payment[];
  total_paid: number;
  remaining: number;
}

export interface CommissionAllocationInput {
  agency_id?: string | null;
  agent?: string;
  percent?: number;
  fixed_amount?: number;
}

export interface CommissionCreate {
  property_id?: string | null;
  source_agency_id: string;
  target_agency_id: string;
  model: CommissionModel;
  basis_amount?: number;
  currency?: string;
  note?: string;
  allocations: CommissionAllocationInput[];
}

export interface PaymentCreate {
  allocation_id: string;
  amount: number;
  reference?: string;
  note?: string;
}

export interface Dispute {
  id: string;
  category: DisputeCategory;
  status: DisputeStatus;
  claimant_agency_id: string;
  respondent_agency_id: string;
  share_id: string | null;
  agreement_id: string | null;
  referral_id: string | null;
  property_id: string | null;
  title: string;
  detail: string;
  resolution: string;
  opened_by: string;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface DisputeMessage {
  id: string;
  author: string;
  body: string;
  is_internal: boolean;
  created_at: string;
}

export interface DisputeDetail extends Dispute {
  messages: DisputeMessage[];
}

export interface DisputeCreate {
  category: DisputeCategory;
  claimant_agency_id: string;
  respondent_agency_id: string;
  share_id?: string | null;
  agreement_id?: string | null;
  referral_id?: string | null;
  property_id?: string | null;
  title: string;
  detail?: string;
}

export interface DisputeMessageCreate {
  body: string;
  is_internal?: boolean;
}

export interface DisputeStatusUpdate {
  status: DisputeStatus;
  resolution?: string;
}

export interface AuditEvent {
  id: string;
  action: AuditAction;
  actor: string;
  actor_agency_id: string | null;
  entity_type: string;
  entity_id: string | null;
  property_id: string | null;
  target_agency_id: string | null;
  detail: string;
  created_at: string;
}

export interface NetworkOverview {
  agencies_total: number;
  agencies_verified: number;
  cooperations_pending: number;
  cooperations_approved: number;
  shares_active: number;
  shares_total: number;
  referrals_open: number;
  referrals_converted: number;
  transfers_total: number;
  commissions_open: number;
  commissions_basis_total: number;
  commissions_paid_total: number;
  disputes_open: number;
  audit_total: number;
}

export interface ReportsByStatus {
  status: string;
  label_fa: string;
  count: number;
}

export interface NetworkReports {
  shares_by_status: ReportsByStatus[];
  referrals_by_stage: ReportsByStatus[];
  transfers_by_status: ReportsByStatus[];
  commissions_by_status: ReportsByStatus[];
  disputes_by_status: ReportsByStatus[];
  cooperations_by_status: ReportsByStatus[];
  audit_by_action: ReportsByStatus[];
  total_basis: number;
  total_paid: number;
  total_remaining: number;
  conversion_rate_pct: number;
}
