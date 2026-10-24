/**
 * شهرهای کلیدی شکارچی — لیست آفلاین گیت انتخاب شهر.
 *
 * وقتی سرویس نقشه (GIS gateway) یا لیست شهرهای دفتر در دسترس نیست، گیت شهر
 * نباید پشت اسپینر قفل شود؛ این لیستِ استاتیک تضمین می‌کند کاربر همیشه
 * بتواند شهر فعالیت را انتخاب کند و وارد پنل شود.
 */

export interface ShekarchiCity {
  /** شناسهٔ یکتا (latin). */
  id: string;
  /** نام فارسی شهر. */
  name: string;
  /** نام استان. */
  province: string;
  /** مختصات مرکز شهر برای flyTo نقشه. */
  center: [number, number];
  /** زوم پیش‌فرض نقشه روی این شهر. */
  zoom: number;
  /** شهرهای پرطرفدار در تب جدا نمایش داده می‌شوند. */
  isPopular: boolean;
}

export const SHEKARCHI_CITIES: ShekarchiCity[] = [
  { id: 'tehran', name: 'تهران', province: 'استان تهران', center: [35.7448, 51.5], zoom: 12, isPopular: true },
  { id: 'mashhad', name: 'مشهد', province: 'خراسان رضوی', center: [36.2972, 59.6067], zoom: 12, isPopular: true },
  { id: 'shiraz', name: 'شیراز', province: 'فارس', center: [29.5918, 52.5837], zoom: 12, isPopular: true },
  { id: 'isfahan', name: 'اصفهان', province: 'اصفهان', center: [32.6546, 51.668], zoom: 12, isPopular: true },
  { id: 'karaj', name: 'کرج', province: 'البرز', center: [35.84, 50.9391], zoom: 12, isPopular: true },
  { id: 'kish', name: 'کیش', province: 'هرمزگان', center: [26.5333, 53.9667], zoom: 12, isPopular: true },
  { id: 'tabriz', name: 'تبریز', province: 'آذربایجان شرقی', center: [38.0962, 46.2738], zoom: 12, isPopular: false },
  { id: 'ahvaz', name: 'اهواز', province: 'خوزستان', center: [31.3183, 48.6706], zoom: 12, isPopular: false },
  { id: 'qom', name: 'قم', province: 'قم', center: [34.6416, 50.8746], zoom: 12, isPopular: false },
  { id: 'rasht', name: 'رشت', province: 'گیلان', center: [37.2808, 49.5832], zoom: 12, isPopular: false },
];

export const POPULAR_CITIES = SHEKARCHI_CITIES.filter((city) => city.isPopular);

export function findCityByName(name: string | null | undefined): ShekarchiCity | null {
  if (!name) return null;
  const trimmed = name.trim();
  return SHEKARCHI_CITIES.find((city) => city.name === trimmed) ?? null;
}
