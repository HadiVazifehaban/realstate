/**
 * CRM contracts — mirrors `app/schemas/crm.py` and the Phase 5 enums.
 *
 * Five board columns plus a terminal `LOST_ARCHIVED` sink. A card carries no
 * owner contact: the phone lives in the PII vault and only ever arrives from
 * the audited `reveal-contact` endpoint.
 */

export const LEAD_STAGES = [
  'NEW_FILE',
  'CONTACTING',
  'APPRAISAL',
  'CONTRACT_READY',
  'CLOSED_DEAL',
  'LOST_ARCHIVED'
] as const;
export type LeadStage = (typeof LEAD_STAGES)[number];

/** The five visible columns, in board order. */
export const KANBAN_COLUMNS = [
  'NEW_FILE',
  'CONTACTING',
  'APPRAISAL',
  'CONTRACT_READY',
  'CLOSED_DEAL'
] as const satisfies readonly LeadStage[];

export const LEAD_STAGE_LABELS: Record<LeadStage, string> = {
  NEW_FILE: 'فایل جدید',
  CONTACTING: 'تماس اولیه',
  APPRAISAL: 'کارشناسی و بازدید',
  CONTRACT_READY: 'آمادهٔ قرارداد',
  CLOSED_DEAL: 'معاملهٔ موفق',
  LOST_ARCHIVED: 'از دست رفته'
};

/**
 * Mirrors `LEAD_TRANSITIONS` on the server. The board uses it to refuse illegal
 * drops up front instead of round-tripping for a 409 — the server still
 * re-validates, since this copy can drift.
 */
export const LEAD_TRANSITIONS: Record<LeadStage, readonly LeadStage[]> = {
  NEW_FILE: ['CONTACTING', 'LOST_ARCHIVED'],
  CONTACTING: ['APPRAISAL', 'LOST_ARCHIVED'],
  APPRAISAL: ['CONTRACT_READY', 'LOST_ARCHIVED'],
  CONTRACT_READY: ['CLOSED_DEAL', 'LOST_ARCHIVED'],
  CLOSED_DEAL: ['APPRAISAL'],
  LOST_ARCHIVED: ['NEW_FILE']
};

export function canMoveLead(from: LeadStage, to: LeadStage): boolean {
  return LEAD_TRANSITIONS[from].includes(to);
}

export const LEAD_PRIORITIES = ['URGENT_BARGAIN', 'HIGH', 'NORMAL', 'LOW'] as const;
export type LeadPriority = (typeof LEAD_PRIORITIES)[number];

/**
 * Listing provenance, mirrored from `PropertySource` on the linked listing.
 *
 * `DELTA` is here because the backend enum now carries it (with a precedence
 * score in `SOURCE_PRECEDENCE`) -- the portal the desk legend always showed,
 * promoted from fiction to a real member.
 */
export const PROPERTY_SOURCES = [
  'INTERNAL_USER',
  'INTERNAL_AGENCY',
  'SHEYPOOR',
  'DIVAR',
  'DELTA',
  'MLS_IMPORT'
] as const;
export type PropertySource = (typeof PROPERTY_SOURCES)[number];

/** Glyph per source, matching the legend the desk is briefed with. */
export const LEAD_SOURCE_LABELS: Record<PropertySource, string> = {
  INTERNAL_USER: '◆ مالک مستقیم (Canonical)',
  INTERNAL_AGENCY: '💼 مشاور',
  SHEYPOOR: '◈ شیپور',
  DIVAR: '◆ دیوار',
  DELTA: '◐ دلتا',
  MLS_IMPORT: '◐ واردشده از MLS'
};

/** Short form for the card badge; the legend carries the long form. */
export const LEAD_SOURCE_SHORT_LABELS: Record<PropertySource, string> = {
  INTERNAL_USER: 'مالک',
  INTERNAL_AGENCY: 'مشاور',
  SHEYPOOR: 'شیپور',
  DIVAR: 'دیوار',
  DELTA: 'دلتا',
  MLS_IMPORT: 'MLS'
};

/**
 * Short badge text for a card.
 *
 * Returns null for an unrecognised value rather than `undefined`: the board
 * keys its badge off this, and rendering `undefined` produces an empty pill
 * that reads as "source unknown" when the real problem is a stale enum member
 * the backend has not folded yet. Failing visibly here is better than
 * shipping a blank badge to the broker.
 */
export function leadSourceBadge(
  source: PropertySource | string | null | undefined
): string | null {
  if (!source) return null;
  return LEAD_SOURCE_SHORT_LABELS[source as PropertySource] ?? null;
}

/**
 * Re-export under the properties-facing name so the "add lead" picker can label
 * a listing without importing two modules for one lookup.
 */
export const PROPERTY_SOURCE_SHORT_LABELS = LEAD_SOURCE_SHORT_LABELS;

export const INTERACTION_TYPES = [
  'PHONE_CALL',
  'VISIT_EVENT',
  'NOTE_ADDED',
  'PRICE_OFFER',
  'STAGE_CHANGED'
] as const;
export type InteractionType = (typeof INTERACTION_TYPES)[number];

export const INTERACTION_LABELS: Record<InteractionType, string> = {
  PHONE_CALL: 'تماس',
  VISIT_EVENT: 'بازدید',
  NOTE_ADDED: 'یادداشت',
  PRICE_OFFER: 'پیشنهاد قیمت',
  STAGE_CHANGED: 'تغییر مرحله'
};

export const SAAS_TIERS = ['FREE', 'BASIC', 'PRO', 'ENTERPRISE'] as const;
export type SaasTier = (typeof SAAS_TIERS)[number];

export const USER_ROLES = [
  'GUEST',
  'USER',
  'OWNER',
  'AGENT',
  'OFFICE_MANAGER',
  'SUPERVISOR',
  'ADMIN'
] as const;
export type UserRole = (typeof USER_ROLES)[number];

/**
 * Per-stage accents.
 *
 * The colour is the fastest way for a broker to read board depth at a glance --
 * which columns are stacked up and which are empty -- so each stage carries its
 * own hue, applied to the card's edge stripe and the column's top rule.
 *
 * Values are CSS custom properties rather than hex literals so the palette
 * follows the active theme; `dark:` is deliberately absent because these are
 * chosen to hold contrast on the obsidian shell the desk already uses.
 */
export const STAGE_ACCENTS: Record<LeadStage, { stripe: string; tint: string }> = {
  NEW_FILE: { stripe: 'var(--stage-new)', tint: 'var(--stage-new-soft)' },
  CONTACTING: { stripe: 'var(--stage-contact)', tint: 'var(--stage-contact-soft)' },
  APPRAISAL: { stripe: 'var(--stage-appraisal)', tint: 'var(--stage-appraisal-soft)' },
  CONTRACT_READY: { stripe: 'var(--stage-contract)', tint: 'var(--stage-contract-soft)' },
  CLOSED_DEAL: { stripe: 'var(--stage-closed)', tint: 'var(--stage-closed-soft)' },
  // Terminal sink: not a visible column, but the menu still offers it, so it
  // needs a colour that reads as "terminal" rather than as a stage.
  LOST_ARCHIVED: { stripe: 'var(--stage-lost)', tint: 'var(--stage-lost-soft)' }
};

/**
 * One column of the board header, as the server aggregated it.
 *
 * `total_value` is the sum of the linked listings' asking prices, so it is a
 * desk-depth figure, not a valuation: an unpriced listing adds to `count` and
 * not to the money.
 */
export interface StageStat {
  stage: LeadStage;
  count: number;
  total_value: number;
}

/**
 * Desk totals for the header strip (`GET /crm/board/stats`).
 *
 * Counted over *every* lead on the node rather than the page the board happens
 * to have loaded, so the header cannot disagree with the archive drawer.
 */
export interface BoardStats {
  total: number;
  /** The five live columns, in board order. The archive is separate. */
  columns: StageStat[];
  lost: number;
  bargains: number;
  /** Value still in play — the four columns before CLOSED_DEAL. */
  open_value: number;
  closed_value: number;
  /** Won / (won + lost), as a percentage. Deals still in play are excluded. */
  conversion_pct: number;
}

export interface LeadSummary {
  id: string;
  property_id: string;
  stage: LeadStage;
  priority: LeadPriority;
  assigned_user_id: string | null;
  is_bargain: boolean;
  deviation_pct: number | null;
  neighborhood: string;
  city: string;
  title: string;
  total_price: number | null;
  area: number | null;
  rooms: number | null;
  updated_at: string;
  /** Listing provenance; null on leads created before the field existed. */
  source: PropertySource | null;
}

export interface LeadListResponse {
  count: number;
  items: LeadSummary[];
}

/** Result of opening a lead; `created=false` means it already existed. */
export interface LeadCreateResponse {
  lead_id: string;
  created: boolean;
  stage: LeadStage;
}

export interface Interaction {
  id: string;
  interaction_type: InteractionType;
  /** Only VISIT_EVENT carries an appointment time. There is no `visit_date`. */
  scheduled_at: string | null;
  note: string | null;
  created_at: string;
}

export interface LeadDetail {
  lead: LeadSummary;
  timeline: Interaction[];
}

export interface StageChangeRequest {
  target_stage: LeadStage;
  note?: string;
}

export interface InteractionRequest {
  interaction_type: InteractionType;
  scheduled_at?: string | null;
  note?: string;
}

export interface QuotaStatus {
  tier: SaasTier;
  /** null means unlimited (Enterprise). */
  remaining: number | null;
}

export interface PiiReveal {
  property_id: string;
  owner_name: string | null;
  owner_phone: string | null;
  tier: SaasTier;
  remaining_quota: number | null;
  audit_logged: boolean;
}

export interface PiiAccessLogEntry {
  id: string;
  user_id: string | null;
  property_id: string | null;
  action: string;
  allowed: boolean;
  reason: string;
  client_ip: string;
  created_at: string;
}

/**
 * Who the client is acting as.
 *
 * Node authentication is still the commercial-licence guard, so role/tier ride
 * along as headers until a real session exists. Keeping it in one type makes
 * that seam obvious at every call site.
 */
export interface Actor {
  role?: UserRole;
  tier?: SaasTier;
}
