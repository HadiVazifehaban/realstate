'use client';

import * as React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  bookVisitSlot,
  fetchBargains,
  fetchGisAreas,
  fetchInventoryCities,
  fetchNearbyPoi,
  fetchNeighbourhoodMarket,
  fetchPriceHistory,
  fetchProperties,
  fetchProperty,
  fetchPropertyMedia,
  fetchVisitAvailability,
  reportProperty,
  revalueProperty,
  submitProperty,
  updatePrice,
  uploadPropertyMedia
} from '../api/client';
import type { NeighbourhoodMarketFilters, PropertyListFilters } from '../api/client';
import type { PropertyReportRequest, PropertySubmitRequest, VisitBookingRequest } from '../types';
import { type MarketMedians, marketKey } from '../utils/market';

export interface BargainFilters {
  neighborhood?: string;
  city?: string;
  cities?: string[];
  city_ids?: string[];
  province_ids?: string[];
  limit?: number;
}

/**
 * Market-map filters.
 *
 * Re-exported from the client so the page and the hook cannot drift on what a
 * "rent" view actually asks the node for (`RENT` plus `FULL_MORTGAGE`).
 */
export type { NeighbourhoodMarketFilters };

/** Radar feed. `refetchInterval` keeps the desk live without a WebSocket yet. */
export function useBargains(filters: BargainFilters = {}) {
  return useQuery({
    queryKey: ['bargains', filters],
    queryFn: () => fetchBargains(filters),
    refetchInterval: 60_000,
    staleTime: 30_000
  });
}

/**
 * Province/city options for the listing filter, from the node's GIS gateway.
 *
 * Cached for a day on the way out of the backend, so this is a cheap request
 * repeated on every page view; the staleTime matches so React Query does not
 * re-fetch it on each navigation. A missing list is not an error worth a
 * toast -- the page falls back to free-text city entry.
 */
export function useGisAreas() {
  return useQuery({
    queryKey: ['gis', 'areas'],
    queryFn: fetchGisAreas,
    staleTime: 86_400_000,
    gcTime: 604_800_000,
    retry: 1
  });
}

/**
 * The cities the node itself holds, from its own listings table.
 *
 * The fallback for `useGisAreas`: when the GIS gateway is unreachable -- the
 * Nominatim/Overpass call failed -- the city filter would otherwise be
 * an empty dropdown on a LAN install. Cities read off the inventory are always
 * filterable, because the radar's `city` parameter is an exact match on the
 * same column these names come from.
 *
 * Shorter staleTime than the gateway list on purpose: inventory grows as the
 * crawler runs, and a new city must not need a day to become selectable.
 */
export function useInventoryCities() {
  return useQuery({
    queryKey: ['properties', 'cities'],
    queryFn: fetchInventoryCities,
    staleTime: 300_000,
    gcTime: 604_800_000,
    retry: 1
  });
}

/**
 * Live inventory feed behind `/dashboard/properties`.
 *
 * Unlike the radar this is not valuation-gated, so freshly crawled listings
 * appear immediately even before the AVM has enough comparables to judge them.
 *
 * `placeholderData: keepPreviousData` is what keeps "نمایش بیشتر" from moving
 * the page: growing `limit` is a new cache key, so without it the hook reports
 * pending with no data, the grid unmounts, and the reader's scroll position
 * collapses back to the first card. Holding the previous window on screen
 * until the bigger one lands means only new cards are appended, exactly where
 * the reader stopped -- `isFetching` is still true, so the button can show its
 * spinner while that happens.
 */
export function useProperties(filters: PropertyListFilters = {}, enabled = true) {
  return useQuery({
    enabled,
    queryKey: ['properties', filters],
    queryFn: () => fetchProperties(filters),
    placeholderData: (previous, previousQuery) => {
      const withoutWindow = (value: PropertyListFilters) => {
        const { limit: _limit, offset: _offset, ...scope } = value;
        return scope;
      };
      const prior = previousQuery?.queryKey[1] as PropertyListFilters | undefined;
      return prior && JSON.stringify(withoutWindow(prior)) === JSON.stringify(withoutWindow(filters))
        ? previous : undefined;
    },
    refetchInterval: 60_000,
    staleTime: 30_000
  });
}

/**
 * The listings behind one neighbourhood bubble on the market map.
 *
 * Scoped to the selected neighbourhood so the grid on the AVM page can show
 * the files a median was computed from, rather than the whole book. Shares the
 * `useProperties` cache, so opening a bubble does not double the request count:
 * the feed page and the AVM grid read the same rows.
 *
 * The backend accepts one `deal_type` per request, while the market map's RENT
 * view spans `RENT` *and* `FULL_MORTGAGE`. For that group the hook fires both
 * and merges -- two small requests beat one request that silently drops half
 * the rent book.
 */
export function useNeighbourhoodProperties(
  neighborhood: string | null,
  filters: Omit<PropertyListFilters, 'neighborhood'> & {
    deal_types?: string[];
  } = {}
) {
  const { deal_types, ...rest } = filters;
  return useProperties({
    ...rest,
    ...(neighborhood ? { neighborhood } : {}),
    ...(deal_types?.length ? { deal_type: deal_types } : {}),
    limit: rest.limit ?? 60
  }, Boolean(neighborhood));
}

/**
 * Per-neighbourhood medians behind the market map.
 *
 * Longer-lived than the listing feed on purpose: a city's median price per
 * square metre does not move between two page views, and the aggregation walks
 * the whole inventory. The map refreshes with the listing feed's cadence only
 * because a broker expects the numbers on a market page to be current.
 */
export function useNeighbourhoodMarket(filters: NeighbourhoodMarketFilters = {}) {
  return useQuery({
    queryKey: [
      'market',
      'neighbourhoods',
      filters
    ],
    queryFn: () => fetchNeighbourhoodMarket(filters),
    refetchInterval: 120_000,
    staleTime: 60_000
  });
}

/**
 * The same medians, shaped for a card to look its own neighbourhood up in.
 *
 * Everything on `/dashboard/properties` that shows a listing — the showcase
 * rails above and the grid below — marks the figure the listing is quoted in,
 * and all three read this map. Each family is fetched separately and React
 * Query de-dupes on the query key, so the page pays one call per deal family
 * no matter how many cards consume it.
 *
 * Both families are fetched because most of the book is *leases*, and a lease
 * has no price per square metre to mark — judging it against a sale median
 * would mark every lease in the city. Each family is therefore keyed by city
 * as well as neighbourhood and never read across.
 */
export function useMarketMedians() {
  const saleQuery = useNeighbourhoodMarket({
    dealTypes: ['SALE'],
    minFiles: 3,
    limit: 300
  });
  const rentQuery = useNeighbourhoodMarket({
    dealTypes: ['RENT', 'FULL_MORTGAGE'],
    minFiles: 3,
    limit: 300
  });

  const medians = React.useMemo<MarketMedians>(() => {
    const sale = new Map<string, number>();
    const rent = new Map<string, number>();
    for (const stat of saleQuery.data?.items ?? []) {
      if (stat.median_price_per_meter !== null) {
        sale.set(marketKey(stat.city, stat.neighborhood), stat.median_price_per_meter);
      }
    }
    for (const stat of rentQuery.data?.items ?? []) {
      if (stat.median_deposit !== null) {
        rent.set(marketKey(stat.city, stat.neighborhood), stat.median_deposit);
      }
    }
    return { sale, rent };
  }, [saleQuery.data, rentQuery.data]);

  return { saleQuery, rentQuery, medians };
}

export function useProperty(propertyId: string) {
  return useQuery({
    queryKey: ['property', propertyId],
    queryFn: () => fetchProperty(propertyId),
    enabled: !!propertyId
  });
}

/**
 * Full gallery for one listing.
 *
 * Separate from the summary on purpose: a feed of 60 cards must not fetch 60
 * galleries, and the summary already carries the cover plus a count, which is
 * all a card needs.
 */
export function usePropertyMedia(propertyId: string) {
  return useQuery({
    queryKey: ['property', propertyId, 'media'],
    queryFn: () => fetchPropertyMedia(propertyId),
    enabled: !!propertyId,
    staleTime: 5 * 60_000
  });
}

/**
 * Nearby amenities for one listing.
 *
 * Long `staleTime` on purpose: the answer is Overpass cached per city block for
 * seven days server-side, so refetching on every navigation would spend the
 * node's egress for an identical answer.
 */
export function useNearbyPoi(propertyId: string) {
  return useQuery({
    queryKey: ['property', propertyId, 'poi'],
    queryFn: () => fetchNearbyPoi(propertyId),
    enabled: !!propertyId,
    staleTime: 60 * 60_000
  });
}

/** Report a listing. Callers show a toast rather than navigating away. */
export function useReportProperty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ propertyId, payload }: { propertyId: string; payload: PropertyReportRequest }) =>
      reportProperty(propertyId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['property'] });
    }
  });
}

export function usePriceHistory(propertyId: string, limit = 50) {
  return useQuery({
    queryKey: ['property', propertyId, 'price-history', limit],
    queryFn: () => fetchPriceHistory(propertyId, limit),
    enabled: !!propertyId
  });
}

/**
 * Direct submission. A dedup merge (`created=false`) is a success, not a
 * conflict -- the advisor sees which listing their pin landed on.
 */
export function useSubmitProperty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PropertySubmitRequest) => submitProperty(payload),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['bargains'] });
      toast.success(
        result.created
          ? 'ملک ثبت شد و وارد صف پردازش شد.'
          : 'این ملک با یک آگهی موجود تطبیق داده شد؛ اطلاعات ثبت‌شده جایگزین شد.'
      );
    },
    onError: (error: Error) => {
      toast.error(error.message || 'ثبت ملک ناموفق بود.');
    }
  });
}

/**
 * Upload photos/videos onto a listing that already exists.
 *
 * Runs as its own step after `useSubmitProperty`, because media attach to a row
 * that has an id: the form creates the listing first, then uploads. One request
 * per submit keeps a failed upload from losing the listing itself.
 */
export function useUploadPropertyMedia(propertyId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => {
      if (!propertyId) throw new Error('ملک هنوز ثبت نشده است.');
      return uploadPropertyMedia(propertyId, files);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['property', propertyId, 'media'] });
      void queryClient.invalidateQueries({ queryKey: ['properties'] });
    }
  });
}

export function useRevalueProperty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (propertyId: string) => revalueProperty(propertyId),
onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['property', result.property_id] });
      void queryClient.invalidateQueries({ queryKey: ['bargains'] });
      // The AVM grid on the market page reads off this feed, so a revalue has
      // to clear it too -- otherwise a card flips from "محاسبه ارزش" straight
      // to the stale UNKNOWN the row was holding before the engine ran.
      void queryClient.invalidateQueries({ queryKey: ['properties'] });
      toast.success('ارزش‌گذاری مجدداً انجام شد.');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'ارزش‌گذاری ناموفق بود.');
    }
  });
}

export function useUpdatePrice(propertyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { newPrice: number; reason?: string }) =>
      updatePrice(propertyId, input.newPrice, input.reason),
    onSuccess: (property) => {
      void queryClient.invalidateQueries({ queryKey: ['property', property.id] });
      void queryClient.invalidateQueries({ queryKey: ['bargains'] });
      toast.success('قیمت به‌روزرسانی و در تاریخچه ثبت شد.');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'به‌روزرسانی قیمت ناموفق بود.');
    }
  });
}

/**
 * Calendar windows behind the visit scheduler widget.
 *
 * `dateFrom`/`dateTo` are Gregorian ISO dates (that is what the node stores);
 * the widget converts them to Jalali for display. Only the visible month is
 * keyed -- refetching on month change keeps the payload at a few dozen rows.
 */
export function useVisitAvailability(
  propertyId: string,
  range?: { dateFrom?: string; dateTo?: string }
) {
  return useQuery({
    queryKey: ['property', propertyId, 'visit-slots', range?.dateFrom, range?.dateTo],
    queryFn: () => fetchVisitAvailability(propertyId, range),
    enabled: !!propertyId
  });
}

/**
 * Request one viewing window.
 *
 * Invalidate the availability feed on success so the just-taken chip flips
 * to REQUESTED without a reload; on a 409 the caller reads `code` off the
 * `ApiError` and offers the next free hour instead of a raw message.
 */
export function useBookVisitSlot(propertyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: VisitBookingRequest) => bookVisitSlot(propertyId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['property', propertyId, 'visit-slots']
      });
      toast.success('درخواست بازدید ثبت شد؛ دفتر برای تأیید با شما تماس می‌گیرد.');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'ثبت درخواست بازدید ناموفق بود.');
    }
  });
}
