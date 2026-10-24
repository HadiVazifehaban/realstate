/**
 * Shared types for the Maskanchi property/lead surfaces.
 *
 * These mirror the FastAPI contract in `app/schemas/properties.py`. Amounts are
 * always integer toman -- never strings -- and the valuation verdict is one of
 * the four `ValuationStatus` values (BARGAIN / FAIR / OVERPRICED / UNKNOWN).
 *
 * Hard rule: there is no `visit_date` on a property payload. A property has
 * no schedule of its own; its viewing windows live on the
 * `property_visit_booking` schedule and arrive through the
 * `VisitAvailabilityResponse` feed below.
 */

export const VALUATION_STATUSES = ['BARGAIN', 'FAIR', 'OVERPRICED', 'UNKNOWN'] as const;
export type ValuationStatus = (typeof VALUATION_STATUSES)[number];

/** Mirrors `PropertyType` in `app/models/enums.py`. */
export const PROPERTY_TYPES = [
  'APARTMENT',
  'SUITE',
  'VILLA',
  'PENTHOUSE',
  'LAND',
  'OFFICE',
  'STORE',
  'WAREHOUSE',
  'INDUSTRIAL',
  'GARDEN'
] as const;
export type PropertyType = (typeof PROPERTY_TYPES)[number];

/** Mirrors `DealType` — there is no PRE_SALE, the third member is FULL_MORTGAGE. */

export const DEAL_TYPES = ['SALE', 'RENT', 'FULL_MORTGAGE'] as const;
export type DealType = (typeof DEAL_TYPES)[number];

/** Mirrors `PropertyStatus` — a listing is DRAFT/RESERVED, never PENDING. */
export const PROPERTY_STATUSES = [
  'DRAFT',
  'ACTIVE',
  'RESERVED',
  'SOLD',
  'RENTED',
  'ARCHIVED'
] as const;
export type PropertyStatus = (typeof PROPERTY_STATUSES)[number];

/**
 * Mirrors `PropertySource` — where the listing came from, in provenance order.
 * The backend aliases the legacy DIVAR_KENAR / DIVAR_SCRAPER / MANUAL_OFFICE
 * values onto their canonical members before serialising, so these five are the
 * only ones that ever reach the browser.
 */
export const PROPERTY_SOURCES = [
  'INTERNAL_USER',
  'INTERNAL_AGENCY',
  'MLS_IMPORT',
  'SHEYPOOR',
  'DIVAR',
  'DELTA'
] as const;
export type PropertySource = (typeof PROPERTY_SOURCES)[number];

/**
 * Mirrors `SubmitterType` in `app/models/enums.py` — the *class of party* that
 * filed a listing, as opposed to `PropertySource`, which is the channel it came
 * through. A broker filing for a private owner is `AGENCY` here while the owner
 * contacts stay the owner's, so the two are kept separate in the UI too.
 *
 * The backend derives this from the submitter's signed token and never accepts
 * it in a request body, so it is deliberately absent from
 * `PropertySubmitRequest` below.
 */
export const SUBMITTER_TYPES = ['PERSON', 'AGENCY'] as const;
export type SubmitterType = (typeof SUBMITTER_TYPES)[number];

/** Radar feed row -- identical projection to `PropertySummary` on the API. */
/**
 * One neighbourhood's slice of the office's own inventory.
 *
 * Aggregated server-side (`app/services/market.py`): the map draws medians, and
 * shipping the files behind them to the browser would leak the book for a
 * summary no broker asked to see line by line.
 */
export interface NeighbourhoodStat {
  neighborhood: string;
  city: string;
  /** Listings that carry the price this row describes. */
  files: number;
  /** Every file in the neighbourhood, priced or not — the coverage figure. */
  all_files: number;
  median_price_per_meter: number | null;
  median_total_price: number | null;
  median_deposit: number | null;
  median_monthly_rent: number | null;
  median_area: number | null;
  /** Share of *all* files the AVM judged below market, 0..1. */
  bargain_share: number;
  median_deviation_pct: number | null;
  latitude: number | null;
  longitude: number | null;
}

export interface NeighbourhoodMarketResponse {
  city: string | null;
  deal_types: DealType[];
  count: number;
  total_files: number;
  priced_files: number;
  median_price_per_meter: number | null;
  items: NeighbourhoodStat[];
}

export interface PropertySummary {
  id: string;
  title: string;
  property_type: PropertyType;
  deal_type: DealType;
  status: PropertyStatus;
  neighborhood: string;
  city: string;
  area: number | null;
  rooms: number | null;
  total_price: number | null;
  price_per_meter: number | null;
  valuation_status: ValuationStatus;
  valuation_deviation_pct: number | null;
  /** AVM benchmark (weighted median Toman/m²) the verdict was computed against. */
  valuation_median_price_per_meter: number | null;
  /** Comparable count behind the AVM verdict; null when the engine has none. */
  valuation_sample_count: number | null;
  /** Blurred for public viewers; exact only for an authorised in-office user. */
  latitude: number | null;
  longitude: number | null;
  exact_pin: boolean;
  /** Radius in metres of the approximate area drawn around the pin. */
  privacy_radius_m: number;
  /** Listed-by identity for the advisor card (business, never the owner). */
  agent_name: string | null;
  agency_name: string | null;
  /** Portal-side listing id, rendered as "کد ملک". */
  source_ref: string | null;

  source: PropertySource;
  /**
   * Class of party that filed this listing. `null` for a scraped row, which has
   * no submitter to classify — not `AGENCY`, which would be a guess.
   */
  submitter_type: SubmitterType | null;
  floor: number | null;
  total_floors: number | null;
  year_built: number | null;
  has_elevator: boolean;
  has_parking: boolean;
  has_storage: boolean;
  has_balcony: boolean;
  /** RENT and FULL_MORTGAGE only. */
  deposit_amount: number | null;
  /** RENT only. */
  monthly_rent: number | null;
  updated_at: string | null;
  /**
   * Free-text listing body as published. Empty when the source shipped none.
   * Never owner contact -- the portals keep the seller's phone out of it.
   */
  description: string;
  /** Null unless the node can serve the image; the card falls back to a plate. */
  cover_url: string | null;
  images_count: number;
}

export interface BargainListResponse {
  count: number;
  items: PropertySummary[];
}

/** One servable gallery image. `local_path` never reaches the browser. */
export interface PropertyMediaItem {
  id: string;
  url: string;
  is_cover: boolean;
  media_type: 'IMAGE' | 'VIDEO' | 'FLOOR_PLAN';
  sort_order: number;
}

/** Mirrors `PropertyMediaListResponse` -- cover first. */
export interface PropertyMediaListResponse {
  property_id: string;
  items: PropertyMediaItem[];
  count: number;
}

/** One named amenity near a listing. */
export interface NearbyPoiItem {
  name: string;
  lat: number;
  lng: number;
  distance_m: number;
}

/** Mirrors `VisitSlotStatus` in `app/models/enums.py`. */
export const VISIT_SLOT_STATUSES = [
  'DRAFT',
  'REQUESTED',
  'CONFIRMED',
  'CANCELLED',
  'NO_SHOW',
  'COMPLETED'
] as const;
export type VisitSlotStatus = (typeof VISIT_SLOT_STATUSES)[number];

/** Mirrors `VisitSlotKind` in `app/models/enums.py`. */
export const VISIT_SLOT_KINDS = ['OFFICE_HOUSE', 'PHONE', 'VIRTUAL'] as const;
export type VisitSlotKind = (typeof VISIT_SLOT_KINDS)[number];

export const VISIT_SLOT_KIND_LABELS: Record<VisitSlotKind, string> = {
  OFFICE_HOUSE: 'بازدید حضوری',
  PHONE: 'تماس تلفنی',
  VIRTUAL: 'بازدید آنلاین'
};

export const VISIT_SLOT_STATUS_LABELS: Record<VisitSlotStatus, string> = {
  DRAFT: 'پیش‌نویس دفتر',
  REQUESTED: 'در انتظار تأیید',
  CONFIRMED: 'تأیید شده',
  CANCELLED: 'لغو شده',
  NO_SHOW: 'عدم حضور',
  COMPLETED: 'انجام شده'
};

/** One viewing-window request, as returned by POST `/visit-slots`. */
export interface VisitBookingResponse {
  id: string;
  property_id: string;
  /** Gregorian ISO date (`YYYY-MM-DD`); the widget renders it as Jalali. */
  slot_date: string;
  start_time: string;
  end_time: string | null;
  status: VisitSlotStatus;
  kind: VisitSlotKind;
  guests: number | null;
  notes: string | null;
  created_at: string;
}

/** Payload for POST `/visit-slots`. The row always lands as REQUESTED. */
export interface VisitBookingRequest {
  slot_date: string;
  start_time: string;
  end_time?: string | null;
  kind?: VisitSlotKind;
  guests?: number | null;
  notes?: string | null;
}

/** One calendar window in the availability feed. */
export interface VisitAvailabilityItem {
  slot_date: string;
  start_time: string;
  end_time: string | null;
  available: boolean;
  /** Null while the window is still free. */
  status: VisitSlotStatus | null;
  kind: VisitSlotKind | null;
}

/** Mirrors `VisitAvailabilityResponse` -- the scheduler's calendar feed. */
export interface VisitAvailabilityResponse {
  property_id: string;
  date_from: string;
  date_to: string;
  items: VisitAvailabilityItem[];
  count: number;
}

/** Mirrors `ReportReason` on the backend. */
export const REPORT_REASONS = [
  'wrong_price',
  'outdated',
  'duplicate',
  'misleading',
  'fraud',
  'other'
] as const;
export type ReportReason = (typeof REPORT_REASONS)[number];

export interface PropertyReportRequest {
  reason: ReportReason;
  detail?: string | null;
  reporter_email?: string | null;
}

export interface PropertyReportResponse {
  id: string;
  reason: string;
}

/**
 * Bucketed POIs. Every key is always present, so the page renders a stable set of
 * cards rather than a list that reflows as data arrives.
 */
export interface NearbyPoiResponse {
  property_id: string;
  radius_m: number;
  buckets: Record<string, NearbyPoiItem[]>;
}

/** Live inventory feed -- same item projection as the radar, paged. */
export interface PropertyListResponse {
  count: number;
  items: PropertySummary[];
  limit: number;
  offset: number;
}

export interface ReverseGeocodeResponse {
  province: string;
  city: string;
  district: string;
  neighborhood: string;
  display_name: string;
}

/**
 * Province/city options for the listing filter, from the node's GIS gateway.
 *
 * The name list is normalized and deduplicated server-side, so these are the
 * exact Persian strings the node stores in `Property.city` -- filtering on them
 * matches rows instead of silently returning nothing.
 */
export interface GisAreaProvince {
  name: string;
  cities: string[];
}

export interface GisAreasResponse {
  provinces: GisAreaProvince[];
  /** Every city, flattened. The flat filter uses this; `provinces` drives the cascade. */
  cities: string[];
}

/**
 * The cities the node itself holds, from ``GET /api/v1/properties/cities``.
 *
 * The fallback the city filter drops to when the GIS gateway is unreachable
 * (the Nominatim/Overpass call failed), so a LAN install keeps a working
 * filter without any platform key.
 */
export interface InventoryCitiesResponse {
  cities: string[];
}

export interface PropertySubmitRequest {
  latitude: number;
  longitude: number;
  property_type: PropertyType;
  deal_type: DealType;
  title: string;
  description: string;
  area: number | null;
  rooms: number | null;
  floor: number | null;
  total_floors: number | null;
  year_built: number | null;
  total_price: number | null;
  deposit_amount: number | null;
  monthly_rent: number | null;
  has_elevator: boolean;
  has_parking: boolean;
  has_storage: boolean;
  has_balcony: boolean;
  /** Written straight into the encrypted vault -- never stored on the listing. */
  owner_name: string | null;
  owner_phone: string | null;
  // No `submitter_type`: the backend reads the class of party (شخص حقیقی /
  // بنگاه) off the submitter's signed token, so sending one would be ignored.
  // An older client that still sends it keeps working -- pydantic drops the key.
  /** Additional features stored in raw_data JSONB column. */
  features?: Record<string, unknown>;
}

export interface PropertySubmitResponse {
  property_id: string;
  /** false = the deduplicator merged this into an existing listing. */
  created: boolean;
  district: string;
  valuation_status: ValuationStatus;
}

export interface ValuationResponse {
  property_id: string;
  valuation_status: ValuationStatus;
  deviation_pct: number | null;
  median_price_per_meter: number | null;
  sample_count: number;
  bargain: boolean;
  explain: Record<string, unknown>;
}

/** Mirrors `PriceChangeSource` in `app/models/enums.py`. */
export const PRICE_CHANGE_SOURCES = ['SCRAPER', 'MANUAL', 'OWNER', 'AVM'] as const;
export type PriceChangeSource = (typeof PRICE_CHANGE_SOURCES)[number];

export interface PriceHistoryEntry {
  id: string;
  previous_price: number | null;
  new_price: number;
  price_difference: number;
  change_percentage: number;
  source: PriceChangeSource;
  source_ref: string | null;
  recorded_at: string;
}
