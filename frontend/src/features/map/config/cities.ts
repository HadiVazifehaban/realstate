/**
 * Reference gazetteer for the city picker.
 *
 * This is *not* an authoritative admin-boundary dataset -- it is the curated
 * seed list the office maintains, matching the `cities` fixture the backend
 * scraper keys off (`app/services/scraper/cities.py`). Boundaries proper live
 * in PostGIS; the `radius` here is only a viewport hint for the initial flyTo.
 *
 * Coordinates are city centres, not the city's geometric centroid, because a
 * centroid on Tehran lands in a mountain range west of the built-up area.
 *
 * `tier` drives the UI grouping: mega cities are the nine the office actually
 * searches, satellite towns are the high-demand commuter belt that the mega
 * city listings overflow into.
 */

export type CityTier = 'mega' | 'satellite';

export interface City {
  /** Persian display name. */
  name: string;
  /** Province, shown as the subtitle in the grid. */
  province: string;
  lat: number;
  lng: number;
  tier: CityTier;
  /** Viewport zoom on selection. */
  zoom: number;
  /** High-demand neighbourhoods, used to prime the district chips. */
  districts: string[];
  /**
   * Latin transliteration, so an advisor can type 'tehran' into the Persian
   * search box. Kept alongside rather than as a separate index because the
   * pairing must stay in sync.
   */
  latin: string;
}

export const CITIES: City[] = [
  {
    name: 'تهران',
    province: 'استان تهران',
    lat: 35.7448,
    lng: 51.5,
    tier: 'mega',
    zoom: 12,
    latin: 'tehran',
    districts: [
      'منطقه ۱',
      'زعفرانیه',
      'نیاوران',
      'ولنجک',
      'الهیه',
      'سعادت‌آباد',
      'پونک',
      'جردن',
      'فرشته',
      'اکباتان'
    ]
  },
  {
    name: 'مشهد',
    province: 'خراسان رضوی',
    lat: 36.2972,
    lng: 59.6067,
    tier: 'mega',
    zoom: 12,
    latin: 'mashhad',
    districts: ['احمدآباد', 'سجاد', 'وکیل‌آباد', 'الهیه', 'قاسم‌آباد']
  },
  {
    name: 'اصفهان',
    province: 'اصفهان',
    lat: 32.6546,
    lng: 51.668,
    tier: 'mega',
    zoom: 12,
    latin: 'isfahan',
    districts: ['جلفا', 'مرداویج', 'چهارباغ', 'سپاهان‌شهر', 'ملک‌شهر']
  },
  {
    name: 'شیراز',
    province: 'فارس',
    lat: 29.5918,
    lng: 52.5837,
    tier: 'mega',
    zoom: 12,
    latin: 'shiraz',
    districts: ['معالی‌آباد', 'قصرالدشت', 'عفیف‌آباد', 'قدوسی', 'فرهنگ‌شهر']
  },
  {
    name: 'تبریز',
    province: 'آذربایجان شرقی',
    lat: 38.0962,
    lng: 46.2738,
    tier: 'mega',
    zoom: 12,
    latin: 'tabriz',
    districts: ['ولیعصر', 'ائل‌گلی', 'رشدیه', 'آبرسان', 'منظریه']
  },
  {
    name: 'کرج',
    province: 'البرز',
    lat: 35.84,
    lng: 50.9391,
    tier: 'mega',
    zoom: 12,
    latin: 'karaj',
    districts: ['عظیمیه', 'جهانشهر', 'گوهردشت', 'مهرشهر', 'فردیس']
  },
  {
    name: 'اهواز',
    province: 'خوزستان',
    lat: 31.3183,
    lng: 48.6706,
    tier: 'mega',
    zoom: 12,
    latin: 'ahvaz',
    districts: ['کیانپارس', 'زیتون', 'گلستان', 'آزادگان']
  },
  {
    name: 'قم',
    province: 'قم',
    lat: 34.6416,
    lng: 50.8746,
    tier: 'mega',
    zoom: 12,
    latin: 'qom',
    districts: ['سالاریه', 'پردیسان', 'زنبیل‌آباد', 'صفائیه']
  },
  {
    name: 'رشت',
    province: 'گیلان',
    lat: 37.2808,
    lng: 49.5832,
    tier: 'mega',
    zoom: 12,
    latin: 'rasht',
    districts: ['گلسار', 'منظریه', 'رشتیان', 'معلم']
  },

  // Commuter belt around Tehran -- the supply that a Tehran-centre search
  // systematically misses, and where the cheap-per-m2 bargains actually sit.
  {
    name: 'پردیس',
    province: 'تهران',
    lat: 35.742,
    lng: 51.817,
    tier: 'satellite',
    zoom: 13,
    latin: 'pardis',
    districts: ['فاز ۱', 'فاز ۲', 'فاز ۳']
  },
  {
    name: 'پرند',
    province: 'تهران',
    lat: 35.489,
    lng: 51.033,
    tier: 'satellite',
    zoom: 13,
    latin: 'parand',
    districts: ['فاز ۳', 'فاز ۵', 'فاز ۶']
  },
  {
    name: 'اندیشه',
    province: 'تهران',
    lat: 35.68,
    lng: 51.02,
    tier: 'satellite',
    zoom: 13,
    latin: 'andisheh',
    districts: ['فاز ۱', 'فاز ۳', 'فاز ۴']
  },
  {
    name: 'لواسان',
    province: 'تهران',
    lat: 35.823,
    lng: 51.633,
    tier: 'satellite',
    zoom: 13,
    latin: 'lavasan',
    districts: ['لواسان بزرگ', 'کلاک', 'سبو بزرگ']
  },
  {
    name: 'دماوند',
    province: 'تهران',
    lat: 35.717,
    lng: 52.067,
    tier: 'satellite',
    zoom: 13,
    latin: 'damavand',
    districts: ['گیلاوند', 'محله قاضی']
  }
];

export const MEGA_CITIES = CITIES.filter((city) => city.tier === 'mega');
export const SATELLITE_CITIES = CITIES.filter((city) => city.tier === 'satellite');

export const DEFAULT_CITY = CITIES[0];

/**
 * Rough accuracy circle drawn around the pin, in metres.
 *
 * Deliberately large. Portal listings (Divar/Sheypoor) give an approximate
 * location, never the exact address, and disclosing a tighter circle would
 * de-anonymise the seller before the viewing is even agreed.
 */
export const APPROXIMATE_RADIUS_M = 900;

/**
 * Persian-ify a number for display. The picker is RTL, so Latin digits render
 * in the wrong visual order around the degree sign in a few of the browser
 * font stacks the office actually uses.
 */
export function toPersianDigits(input: string | number): string {
  return String(input).replace(/[0-9]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
}

/**
 * Fold Persian text into a comparable form for search.
 *
 * Arabic ي/ى and Persian ی are distinct code points but the same letter to any
 * reader, and the office pastes names from listings that mix all three. Zero
 * width non-joiner is stripped for the same reason: پردیس‌آباد must match a
 * search for پردیس آباد.
 */
export function normalizePersian(input: string): string {
  return input
    .toLowerCase()
    .replace(/[يى]/g, 'ی')
    .replace(/ك/g, 'ک')
    .replace(/[ً-ْـ]/g, '')
    .replace(/[\s‌ـ]/g, '')
    .trim();
}
