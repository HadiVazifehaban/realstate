import { toPersianDigits } from '@/lib/utils';
import type {
  DealType,
  PriceChangeSource,
  PropertySource,
  PropertyStatus,
  PropertyType,
  SubmitterType,
  ValuationStatus
} from '../types';

/** Persian labels + badge variants for the four valuation verdicts. */
export const VALUATION_LABELS: Record<ValuationStatus, string> = {
  BARGAIN: 'شکار بازار',
  FAIR: 'قیمت منصفانه',
  OVERPRICED: 'بالای قیمت',
  UNKNOWN: 'بدون مرجع'
};

export const VALUATION_BADGE_VARIANT: Record<
  ValuationStatus,
  'default' | 'secondary' | 'destructive' | 'outline'
> = {
  BARGAIN: 'default',
  FAIR: 'secondary',
  OVERPRICED: 'destructive',
  UNKNOWN: 'outline'
};

export const PROPERTY_TYPE_LABELS: Record<PropertyType, string> = {
  APARTMENT: 'آپارتمان',
  SUITE: 'سوئیت',
  VILLA: 'ویلا',
  PENTHOUSE: 'پنت‌هاوس',
  LAND: 'زمین',
  OFFICE: 'اداری',
  STORE: 'مغازه',
  WAREHOUSE: 'انبار',
  INDUSTRIAL: 'صنعتی',
  GARDEN: 'باغ'
};

export const DEAL_TYPE_LABELS: Record<DealType, string> = {
  SALE: 'فروش',
  RENT: 'رهن و اجاره',
  FULL_MORTGAGE: 'رهن کامل'
};

export const PROPERTY_STATUS_LABELS: Record<PropertyStatus, string> = {
  DRAFT: 'پیش‌نویس',
  ACTIVE: 'فعال',
  RESERVED: 'رزرو شده',
  SOLD: 'فروخته شده',
  RENTED: 'اجاره شده',
  ARCHIVED: 'بایگانی'
};

export const PRICE_SOURCE_LABELS: Record<PriceChangeSource, string> = {
  MANUAL: 'ویرایش مشاور',
  SCRAPER: 'به‌روزرسانی اسکرپر',
  OWNER: 'ثبت توسط مالک',
  AVM: 'محاسبه سیستم'
};

/**
 * Provenance badge text. A first-party registration is what the office can act
 * on, so it is worded as such rather than as a generic 'internal' tag.
 */
export const SOURCE_LABELS: Record<PropertySource, string> = {
  INTERNAL_USER: 'ثبت مستقیم مالک',
  INTERNAL_AGENCY: 'ثبت مستقیم دفتر',
  MLS_IMPORT: 'شبکه همکاران',
  SHEYPOOR: 'شیپور',
  DIVAR: 'دیوار',
  DELTA: 'دلتا'
};

/**
 * Compact provenance badge text for the photo overlay.
 *
 * The overlay's corner is a shared budget: the source badge and the property
 * type badge sit opposite each other over a 4:3 thumbnail, and the full
 * «ثبت مستقیم مالک» was wide enough to squeeze the type badge into a
 * different width on first-party cards than on portal ones. Same trust
 * signal, fewer glyphs — «ثبت مالک», «ثبت دفتر».
 *
 * The full label still rides on everything with room for it (the detail
 * sidebar, the lead card, the filter bar), so this shortens the badge only
 * where space is the constraint, and never changes what it says.
 */
export const SOURCE_SHORT_LABELS: Record<PropertySource, string> = {
  INTERNAL_USER: 'ثبت مالک',
  INTERNAL_AGENCY: 'ثبت دفتر',
  MLS_IMPORT: 'همکاران',
  SHEYPOOR: 'شیپور',
  DIVAR: 'دیوار',
  DELTA: 'دلتا'
};

/**
 * Who filed the listing: the class of party, not the channel.
 *
 * Kept apart from `SOURCE_LABELS` on purpose. `source` answers where the row
 * came from (a portal scrape, an MLS import, a first-party registration); this
 * answers *who pressed submit*. A broker filing for a private owner reads
 * «ثبت دفتر» here while the owner contacts in the card stay the owner's — the
 * two facts must not collapse into one badge.
 */
export const SUBMITTER_LABELS: Record<SubmitterType, string> = {
  PERSON: 'شخص حقیقی',
  AGENCY: 'بنگاه'
};

/** How much to trust the row: first-party outranks a portal scrape. */
export const SOURCE_TRUSTED: Record<PropertySource, boolean> = {
  INTERNAL_USER: true,
  INTERNAL_AGENCY: true,
  MLS_IMPORT: true,
  SHEYPOOR: false,
  DIVAR: false,
  DELTA: false
};

/** Persian label for the floor chip, e.g. '۳ از ۵'; null when unknown. */
export function formatFloor(floor: number | null, totalFloors: number | null): string | null {
  if (floor === null && totalFloors === null) return null;
  const level = floor === null ? '?' : toPersianDigits(floor.toLocaleString('en-US'));
  if (totalFloors === null) return `طبقه ${level}`;
  return `طبقه ${level} از ${toPersianDigits(totalFloors.toLocaleString('en-US'))}`;
}

/**
 * '۲ ساعت پیش' from a timestamp. Falls back to null past a week, where a coarse
 * absolute date reads better than '۳۲ روز پیش'.
 */
export function formatPublishedAgo(updatedAt: string | null, now = Date.now()): string | null {
  if (!updatedAt) return null;
  const then = new Date(updatedAt).getTime();
  if (Number.isNaN(then)) return null;

  const minutes = Math.floor((now - then) / 60_000);
  if (minutes < 1) return 'همین حالا';
  if (minutes < 60) return `${toPersianDigits(minutes.toLocaleString('en-US'))} دقیقه پیش`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${toPersianDigits(hours.toLocaleString('en-US'))} ساعت پیش`;
  const days = Math.floor(hours / 24);
  if (days <= 7) return `${toPersianDigits(days.toLocaleString('en-US'))} روز پیش`;
  return null;
}

/** Signed percentage, e.g. '-۱۸.۵٪' -- the sign is what makes a bargain read. */
export function formatDeviation(deviation: number | null | undefined): string {
  if (deviation === null || deviation === undefined || Number.isNaN(deviation)) return '—';
  const magnitude = toPersianDigits(
    Math.abs(deviation).toLocaleString('en-US', { maximumFractionDigits: 1 })
  );
  // U+200E keeps the sign glued to the digits; in an RTL run the bidi
  // algorithm otherwise reorders a leading '-' to the far side of the number.
  return `${deviation > 0 ? '+' : deviation < 0 ? '−' : ''}‎${magnitude}٪`;
}

/**
 * Current year in the Persian calendar, as a number.
 *
 * A listing's `year_built` is a Gregorian year, so the age has to be measured
 * against the Persian year to be what an Iranian reader means by "۱۹ ساله".
 * Read through `Intl` rather than a fixed offset from the Gregorian year: the
 * Persian year starts at Nowruz (around 21 March), so a hard-coded 621/1400
 * offset is wrong for roughly a quarter of every year.
 */
function currentPersianYear(): number {
  const formatted = new Intl.DateTimeFormat('en-US-u-nu-latn', {
    year: 'numeric',
    timeZone: 'Asia/Tehran'
  }).format(new Date());
  const year = Number.parseInt(formatted, 10);
  return Number.isNaN(year) ? 0 : year + 621;
}

/**
 * Approximate building age, e.g. '۱۹ ساله'.
 *
 * Null when the year is unknown or in the future -- a portal that publishes a
 * nonsense year would otherwise produce a negative age. Callers render an
 * explicit dash instead of guessing.
 */
export function formatBuildingAge(yearBuilt: number | null): string | null {
  if (yearBuilt === null || yearBuilt <= 0) return null;
  const age = currentPersianYear() - yearBuilt;
  if (age <= 0 || age > 300) return null;
  return `${toPersianDigits(age.toLocaleString('en-US'))} ساله`;
}
