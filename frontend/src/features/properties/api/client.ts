/**
 * Browser-side client for the Maskanchi FastAPI node.
 *
 * Every call carries the realm access token from the Auth.js session: the node
 * rejects anonymous requests, and it is the sole enforcement point — it
 * re-verifies the token against the realm's JWKS and re-derives role/KYC from
 * the signed claims. The header here is only a forwarded credential.
 *
 * Note that owner phone numbers are deliberately absent: PII is decrypt-scoped
 * and audit-logged on the backend, so it never appears in any type in this
 * feature.
 */

import { apiBaseUrl, networkFailureMessage } from '@/lib/api-base-url';
import { authHeaders } from '@/lib/auth/session';
import type {
  BargainListResponse,
  GisAreasResponse,
  InventoryCitiesResponse,
  NeighbourhoodMarketResponse,
  NearbyPoiResponse,
  PriceHistoryEntry,
  PropertyListResponse,
  PropertyMediaListResponse,
  PropertyReportRequest,
  PropertyReportResponse,
  PropertySubmitRequest,
  PropertySubmitResponse,
  PropertySummary,
  ReverseGeocodeResponse,
  ValuationResponse,
  VisitAvailabilityResponse,
  VisitBookingRequest,
  VisitBookingResponse
} from '../types';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit, requireAuth: boolean = true): Promise<T> {
  let response: Response;
  // A FormData body must set its own multipart Content-Type (the boundary is
  // part of it), so the JSON default is skipped for uploads rather than
  // overwriting it with a value the server cannot parse.
  const isFormData = init?.body instanceof FormData;
  try {
    const headers: HeadersInit = {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init?.headers as HeadersInit | undefined)
    };

    // Only add auth headers if required and available
    if (requireAuth) {
      const auth = await authHeaders();
      if (auth) {
        Object.assign(headers, auth);
      }
    }

    response = await fetch(`${apiBaseUrl()}${path}`, {
      // The node is LAN-local, so every call is uncached by default.
      cache: 'no-store',
      ...init,
      headers
    });
  } catch (error) {
    // A rejected fetch never saw a status, so `status: 0` marks it as a
    // transport failure rather than an API answer the caller could act on.
    throw new ApiError(0, 'network_unreachable', networkFailureMessage(error));
  }

  if (!response.ok) {
    // The backend answers with `detail: { error, message }`; fall back to the
    // status text so a proxy error still surfaces something readable.
    let code = 'request_failed';
    let message = response.statusText || 'درخواست ناموفق بود.';
    try {
      const body = (await response.json()) as {
        detail?: { error?: string; message?: string } | string;
      };
      if (typeof body.detail === 'string') {
        message = body.detail;
      } else if (body.detail) {
        code = body.detail.error ?? code;
        message = body.detail.message ?? message;
      }
    } catch {
      // Non-JSON error body (e.g. gateway HTML page) -- keep the fallback.
    }
    throw new ApiError(response.status, code, message);
  }

  return (await response.json()) as T;
}

function toQuery(
  params: Record<string, string | number | boolean | readonly string[] | undefined | null>
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    // `false` is skipped like an unset filter: the node treats a missing bool
    // as "no constraint", and sending `false` would mean the same thing while
    // making the URL lie about the applied filters.
    if (value === undefined || value === null || value === '' || value === false) continue;
    // Repeated param: `property_type=APARTMENT&property_type=SUITE`.
    if (Array.isArray(value)) {
      value.forEach((entry) => {
        if (entry !== '') search.append(key, String(entry));
      });
      continue;
    }
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : '';
}

/** Radar feed: units the engine priced below the local median. */
export function fetchBargains(filters?: {
  neighborhood?: string;
  city?: string;
  limit?: number;
}): Promise<BargainListResponse> {
  return request<BargainListResponse>(`/properties/bargains${toQuery({ ...filters })}`);
}

export interface NeighbourhoodMarketFilters {
  city?: string;
  /** Repeated query param — a rent view asks for RENT *and* FULL_MORTGAGE. */
  dealTypes?: string[];
  /** Hide neighbourhoods thinner than this many priced files. */
  minFiles?: number;
  limit?: number;
}

/**
 * Per-neighbourhood medians for the market map.
 *
 * The medians are computed in PostGIS, not here: a mean over portal asking
 * prices lands in whatever tail the scraper saw last, and a neighbourhood
 * median that nobody can transact at is worse than no number at all.
 */
export function fetchNeighbourhoodMarket(
  filters: NeighbourhoodMarketFilters = {}
): Promise<NeighbourhoodMarketResponse> {
  const search = new URLSearchParams();
  if (filters.city) search.set('city', filters.city);
  filters.dealTypes?.forEach((dealType) => search.append('deal_type', dealType));
  if (filters.minFiles) search.set('min_files', String(filters.minFiles));
  if (filters.limit) search.set('limit', String(filters.limit));
  const query = search.toString();
  return request<NeighbourhoodMarketResponse>(
    `/properties/market/neighbourhoods${query ? `?${query}` : ''}`
  );
}

export interface PropertyListFilters {
  q?: string;
  /**
   * One city, or several. Repeated as a query param because the feed's city
   * filter is multi-select: a Tehran desk's market is the capital *and* its
   * satellites, and paging once per city would show whichever city happened to
   * answer first.
   */
  city?: string | string[];
  neighborhood?: string;
  /**
   * One or several deal families. Repeated as a query param, because «رهن و
   * اجاره» is one choice for the advisor but two stored deal types — RENT and
   * FULL_MORTGAGE — and sending only one of them would drop every
   * deposit-only lease out of a lease search.
   */
  deal_type?: string | string[];
  /**
   * One property type, or several. Repeated as a query param so a category
   * that spans types (مسکونی -> APARTMENT + SUITE + PENTHOUSE) is one request.
   */
  property_type?: string | string[];
  status?: string;
  valuation_status?: string;
  source?: string;
  /** Inclusive bounds in tomans; the deal-appropriate price column per row. */
  min_price?: number;
  max_price?: number;
  /** Inclusive bounds in square metres. */
  min_area?: number;
  max_area?: number;
  // -- Building & unit attributes ----------------------------------------
  // Inclusive bounds on the bedroom count. "4 خواب و بیشتر" leaves
  // `max_rooms` unset rather than guessing a ceiling, so an open-ended chip
  // stays open-ended all the way to the query.
  min_rooms?: number;
  max_rooms?: number;
  /** Inclusive bounds on the plot/yard area, for houses and villas. */
  min_land_area?: number;
  max_land_area?: number;
  /** Inclusive bounds on the construction year; null years stay unmatchable. */
  min_year_built?: number;
  max_year_built?: number;
  /** Inclusive bounds on the unit's own storey. */
  min_floor?: number;
  max_floor?: number;
  /**
   * Amenity switches: `true` means "must have it". Sent as `'true'` because the
   * node models them as a plain bool, with no dedicated/shared split for
   * parking -- the UI therefore offers one parking chip, not two.
   */
  has_parking?: boolean | string;
  has_elevator?: boolean | string;
  has_storage?: boolean | string;
  has_balcony?: boolean | string;
  /**
   * Inclusive bounds on price per square metre. Distinct from `*_price`: a
   * per-metre ceiling of 50m excludes a 200 m² unit priced at 12b, while the
   * total-price ceiling at the same number would include it.
   */
  min_price_per_meter?: number;
  max_price_per_meter?: number;
  /**
   * Bargain radar: how far below the neighbourhood AVM a listing must sit, in
   * percent. Rows without a verdict never match -- unpriced is not cheap.
   */
  below_market_pct?: number;
  /** Who filed the listing: PERSON is the owner-direct route, AGENCY the desk. */
  submitter_type?: string;
  /** Recency in hours since `created_at`. */
  published_within_hours?: number;
  limit?: number;
  offset?: number;
}

/** Live inventory feed: crawled + first-party listings, newest first. */
export function fetchProperties(filters: PropertyListFilters = {}): Promise<PropertyListResponse> {
  return request<PropertyListResponse>(`/properties${toQuery({ ...filters })}`);
}

/** A scrape job the node queued in response to a crawl request. */
export interface ScrapeJobResponse {
  id: string;
  city: string;
  source: string;
  status: string;
}

/**
 * Ask the node to crawl one market now.
 *
 * The city list is sent as a repeated field because the backend queues one job
 * per city: a six-city market is six sweepable jobs the caller can watch,
 * rather than one request that silently covers only the first city.
 */
export function triggerScrape(payload: {
  cities: string[];
  category?: string;
}): Promise<ScrapeJobResponse> {
  return request<ScrapeJobResponse>('/scraper/trigger', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

/** Full gallery for one listing, cover first. */
export function fetchPropertyMedia(propertyId: string): Promise<PropertyMediaListResponse> {
  return request<PropertyMediaListResponse>(`/properties/${propertyId}/media`);
}

/** Named amenities near a listing, bucketed and nearest-first. */
export function fetchNearbyPoi(propertyId: string): Promise<NearbyPoiResponse> {
  return request<NearbyPoiResponse>(`/properties/${propertyId}/nearby-poi`);
}

/**
 * Report a listing.
 *
 * Fire-and-forget from the UI: a report is a courtesy signal, not something the
 * broker waits on, so the caller shows a toast rather than navigating away.
 */
export function reportProperty(propertyId: string, payload: PropertyReportRequest): Promise<PropertyReportResponse> {
  return request<PropertyReportResponse>(`/properties/${propertyId}/report`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function fetchProperty(propertyId: string): Promise<PropertySummary> {
  return request<PropertySummary>(`/properties/${propertyId}`);
}

export function fetchPriceHistory(propertyId: string, limit = 50): Promise<PriceHistoryEntry[]> {
  return request<PriceHistoryEntry[]>(
    `/properties/${propertyId}/price-history${toQuery({ limit })}`
  );
}

/** Resolve an OSM pin to Persian district names before committing the form. */
export function reverseGeocode(
  latitude: number,
  longitude: number
): Promise<ReverseGeocodeResponse> {
  return request<ReverseGeocodeResponse>('/properties/reverse-geocode', {
    method: 'POST',
    body: JSON.stringify({ latitude, longitude })
  });
}

/**
 * Provinces and cities for the listing filter, from the node's GIS gateway.
 *
 * Goes through the node rather than straight to the public services so
 * server-side, and so the list arrives already normalized and deduplicated.
 */
export function fetchGisAreas(): Promise<GisAreasResponse> {
  return request<GisAreasResponse>('/gis/cities');
}

export function fetchInventoryCities(): Promise<InventoryCitiesResponse> {
  return request<InventoryCitiesResponse>('/properties/cities');
}

/**
 * Attach photos/videos to a listing (multipart).
 *
 * The property has to exist first, which is why the submit form uploads after
 * the create call resolves. The response is the whole gallery, cover first, so
 * the caller never has to re-fetch what it just sent.
 */
export function uploadPropertyMedia(
  propertyId: string,
  files: File[]
): Promise<PropertyMediaListResponse> {
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  // No headers: the shared client sees a FormData body and lets the browser set
  // the multipart Content-Type, boundary included.
  return request<PropertyMediaListResponse>(`/properties/${propertyId}/media`, {
    method: 'POST',
    body: form
  }, false);
}

export function submitProperty(payload: PropertySubmitRequest): Promise<PropertySubmitResponse> {
  return request<PropertySubmitResponse>('/properties', {
    method: 'POST',
    body: JSON.stringify(payload)
  }, false);
}

export function revalueProperty(propertyId: string): Promise<ValuationResponse> {
  return request<ValuationResponse>(`/properties/${propertyId}/value`, { method: 'POST' });
}

export function updatePrice(
  propertyId: string,
  newPrice: number,
  reason?: string
): Promise<PropertySummary> {
  return request<PropertySummary>(`/properties/${propertyId}/price`, {
    method: 'POST',
    body: JSON.stringify({ new_price: newPrice, reason: reason ?? '' })
  });
}

/**
 * Viewing windows of one listing, taken or still free.
 *
 * The ISO dates travel as Gregorian (that is what the node stores); the
 * widget converts them to Jalali for display. Only the shown range is
 * fetched -- a wider window would ship dozens of 09:00 holes the user will
 * never scroll to.
 */
export function fetchVisitAvailability(
  propertyId: string,
  range?: { dateFrom?: string; dateTo?: string }
): Promise<VisitAvailabilityResponse> {
  return request<VisitAvailabilityResponse>(
    `/properties/${propertyId}/visit-slots${toQuery({
      date_from: range?.dateFrom,
      date_to: range?.dateTo
    })}`
  );
}

/**
 * Request one viewing window. Lands as REQUESTED -- a public request never
 * confirms itself -- and answers 409 `slot_taken` when the hour is gone.
 */
export function bookVisitSlot(
  propertyId: string,
  payload: VisitBookingRequest
): Promise<VisitBookingResponse> {
  return request<VisitBookingResponse>(`/properties/${propertyId}/visit-slots`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}
