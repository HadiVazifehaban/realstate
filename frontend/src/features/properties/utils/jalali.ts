/**
 * Jalali (Solar Hijri) calendar math for the visit scheduler widget.
 *
 * No calendar dependency on purpose: the widget needs day-level arithmetic
 * (month length, month start weekday, ±1 month) in Jalali terms, not a full
 * date library. The conversion below is the standard jalaali-js algorithm
 * (Birashk/Dershowitz), checked against the anchor 2026-10-10 == 1405-07-18.
 *
 * Gregorian dates stay the wire format -- the node stores `slot_date` as a
 * plain DATE -- and conversions happen at the very edge: feed items in,
 * Jalali labels out, and the selected Jalali day back to ISO for the POST.
 */

export interface JalaliDate {
  year: number;
  month: number; // 1..12
  day: number; // 1..31
}

/** Persian month names, index `month - 1` reads naturally. */
export const JALALI_MONTH_NAMES = [
  'فروردین',
  'اردیبهشت',
  'خرداد',
  'تیر',
  'مرداد',
  'شهریور',
  'مهر',
  'آبان',
  'آذر',
  'دی',
  'بهمن',
  'اسفند'
] as const;

/** Weekday headers, Saturday-first like every Iranian wall calendar. */
export const JALALI_WEEKDAY_NAMES = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'] as const;

const JALALI_BREAKS = [
  -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097,
  2192, 2262, 2324, 2394, 2456, 3178
];

function div(value: number, by: number): number {
  return ~~(value / by);
}

function mod(value: number, by: number): number {
  return value - ~~(value / by) * by;
}

interface JalaliBreakInfo {
  leap: number;
  gy: number;
  march: number;
}

/** Leap-year cycles for one Jalali year from the break table. */
function jalCalendar(jy: number): JalaliBreakInfo {
  const breaks = JALALI_BREAKS;
  const bl = breaks.length;
  const gy = jy + 621;
  let leapJ = -14;
  let jp = breaks[0];
  let jm = 0;
  let jump = 0;
  let leap = 0;
  let leapG = 0;
  let march = 0;
  let n = 0;

  if (jy < jp || jy >= breaks[bl - 1]) {
    throw new Error(`Invalid Jalali year ${jy}`);
  }

  for (let i = 1; i < bl; i += 1) {
    jm = breaks[i];
    jump = jm - jp;
    if (jy < jm) {
      break;
    }
    leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4);
    jp = jm;
  }
  n = jy - jp;

  leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
  if (mod(jump, 33) === 4 && jump - n === 4) {
    leapJ += 1;
  }

  leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
  march = 20 + leapJ - leapG;

  if (jump - n < 6) {
    n = n - jump + div(jump + 4, 33) * 33;
  }
  leap = mod(mod(n + 1, 33) - 1, 4);
  if (leap === -1) {
    leap = 4;
  }

  return { leap, gy, march };
}

function gregorianToDayNumber(gy: number, gm: number, gd: number): number {
  let day =
    div((gy + div(gm - 8, 6) + 100100) * 1461, 4) +
    div(153 * mod(gm + 9, 12) + 2, 5) +
    gd -
    34840408;
  day = day - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
  return day;
}

function dayNumberToGregorian(dayNumber: number): { gy: number; gm: number; gd: number } {
  let j = 4 * dayNumber + 139361631;
  j = j + div(div(4 * dayNumber + 183187720, 146097) * 3, 4) * 4 - 3908;
  const i = div(mod(j, 1461), 4) * 5 + 308;
  const gd = div(mod(i, 153), 5) + 1;
  const gm = mod(div(i, 153), 12) + 1;
  const gy = div(j, 1461) - 100100 + div(8 - gm, 6);
  return { gy, gm, gd };
}

function jalaliToDayNumber(jy: number, jm: number, jd: number): number {
  const info = jalCalendar(jy);
  return (
    gregorianToDayNumber(info.gy, 3, info.march) +
    (jm - 1) * 31 -
    div(jm, 7) * (jm - 7) +
    jd -
    1
  );
}

function dayNumberToJalali(dayNumber: number): JalaliDate {
  const gy = dayNumberToGregorian(dayNumber).gy;
  let jy = gy - 621;
  const info = jalCalendar(jy);
  const marchDay = gregorianToDayNumber(gy, 3, info.march);
  let dayOfYear = dayNumber - marchDay;
  if (dayOfYear >= 0) {
    if (dayOfYear <= 185) {
      return { year: jy, month: Math.ceil((dayOfYear + 1) / 31), day: mod(dayOfYear, 31) + 1 };
    }
    dayOfYear -= 186;
  } else {
    const daysInPrevYear = isJalaliLeap(jy - 1) ? 366 : 365;
    dayOfYear += daysInPrevYear;
    jy -= 1;
    if (dayOfYear <= 185) {
      return { year: jy, month: Math.ceil((dayOfYear + 1) / 31), day: mod(dayOfYear, 31) + 1 };
    }
    dayOfYear -= 186;
  }
  return {
    year: jy,
    month: Math.ceil((dayOfYear + 1) / 30) + 6,
    day: mod(dayOfYear, 30) + 1
  };
}

/** Gregorian fields -> Jalali fields. */
export function toJalali(gy: number, gm: number, gd: number): JalaliDate {
  return dayNumberToJalali(gregorianToDayNumber(gy, gm, gd));
}

/** Jalali fields -> Gregorian fields. */
export function toGregorian(jy: number, jm: number, jd: number): {
  year: number;
  month: number;
  day: number;
} {
  const { gy, gm, gd } = dayNumberToGregorian(jalaliToDayNumber(jy, jm, jd));
  return { year: gy, month: gm, day: gd };
}

/** Jalali leap check through the same break table (no second algorithm). */
export function isJalaliLeap(jy: number): boolean {
  return jalCalendar(jy).leap === 0;
}

/** Days in a Jalali month (Esfand honors leap years). */
export function jalaliMonthLength(jy: number, jm: number): number {
  if (jm <= 6) return 31;
  if (jm <= 11) return 30;
  return isJalaliLeap(jy) ? 30 : 29;
}



/** ISO `YYYY-MM-DD` (Gregorian) -> Jalali fields for the header. */
export function isoToJalali(iso: string): JalaliDate {
  const [gy, gm, gd] = iso.split('-').map(Number);
  return toJalali(gy, gm, gd);
}

/** Calendar header label, e.g. `مهر ۱۴۰۵` (month + Jalali year). */
export function formatJalaliMonth(year: number, month: number): string {
  return `${JALALI_MONTH_NAMES[month - 1]} ${toPersianDigits(String(year))}`;
}

/** Full Persian label for a date, e.g. `۱۵ مهر ۱۴۰۵`. */
export function formatJalaliLong(jalali: JalaliDate): string {
  return `${toPersianDigits(String(jalali.day))} ${JALALI_MONTH_NAMES[jalali.month - 1]} ${toPersianDigits(
    String(jalali.year)
  )}`;
}

/** `YYYY-MM-DD` (Gregorian) -> Persian `YYYY-M-D` digits for plain text. */
export function toPersianDigits(value: string): string {
  return value.replace(/\d/g, (digit) => '۰۱۲۳۴۵۶۷۸۹'[Number(digit)]);
}

/** `14:00` style timestamp -> Persian digits with the ASCII colon kept. */
export function toPersianTime(value: string): string {
  return value.replace(/\d/g, (digit) => '۰۱۲۳۴۵۶۷۸۹'[Number(digit)]);
}

/** Weekday key for a Gregorian date, Saturday-first (0 = Saturday … 6 = Friday). */
export function gregorianWeekdaySaturdayFirst(gy: number, gm: number, gd: number): number {
  return (new Date(gy, gm - 1, gd).getDay() + 1) % 7;
}

/** The 1st of a Jalali month is this many cells to the right of Saturday. */
export function jalaliMonthStartOffset(jy: number, jm: number): number {
  const { year, month, day } = toGregorian(jy, jm, 1);
  return gregorianWeekdaySaturdayFirst(year, month, day);
}

/** `YYYY-MM-DD` of today in the *local* timezone (no UTC shift). */
export function todayIsoLocal(now: Date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** Jalali of today, computed from the local Gregorian clock. */
export function todayJalali(now: Date = new Date()): JalaliDate {
  return toJalali(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

/** `14:00` -> `14:00`; keeps the colon ASCII so the chip stays aligned. */
export function shortTime(value: string): string {
  const match = /T?(\d{2}:\d{2})/.exec(value);
  return match ? match[1] : value;
}
