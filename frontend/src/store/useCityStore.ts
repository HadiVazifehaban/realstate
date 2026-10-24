'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { findCityByName, type ShekarchiCity } from '@/constants/cities';
import { apiBaseUrl } from '@/lib/api-base-url';
import { authHeaders } from '@/lib/auth/session';

/**
 * استیت سراسری شهر فعالیت شکارچی — به‌ازای هر کاربر.
 *
 * سه لایهٔ ذخیره‌سازی، به ترتیب اولویت:
 *
 *  1. **سرور** (`GET/PUT /users/me/preferences`) — به `sub` توکن گره خورده،
 *     پس با هر لاگینِ دوباره (هر دستگاه، هر مرورگر) همان شهر بالا می‌آید و
 *     هر تغییر شهر هم همان لحظه PUT می‌شود تا دفعهٔ بعد همان بیاید.
 *  2. **localStorage به‌ازای کاربر** (`shekarchi_city:<subject>`) — کش آفلاین
 *     برای همان کاربر؛ کاربر عوض شود، شهر قبلی لو نمی‌رود.
 *  3. **کلید قدیمی سراسری** (`selected_city` / `shekarchi_active_city`) — فقط
 *     یک‌بار موقع مهاجرت خوانده می‌شود تا کاربران فعلی شهرشان را از دست ندهند.
 */

const GLOBAL_STORAGE_KEY = 'shekarchi_active_city';
const LEGACY_STORAGE_KEY = 'selected_city';
const PREFERENCE_KEY = 'active_city';

function userStorageKey(subject: string | null): string {
  return subject ? `shekarchi_city:${subject}` : GLOBAL_STORAGE_KEY;
}

function readStoredCity(key: string): ShekarchiCity | null {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    // دو شکل ذخیره داریم: persist زاستند ({state:{activeCity}}) و نام ساده.
    try {
      const parsed = JSON.parse(raw) as {
        state?: { activeCity?: ShekarchiCity | null };
        name?: string;
      };
      if (parsed?.state?.activeCity) return parsed.state.activeCity;
      if (typeof parsed?.name === 'string') return findCityByName(parsed.name);
    } catch {
      // JSON نیست — نام خالص شهر است.
    }
    return findCityByName(raw);
  } catch {
    return null;
  }
}

function writeStoredCity(key: string, city: ShekarchiCity | null): void {
  try {
    if (city) {
      window.localStorage.setItem(
        key,
        JSON.stringify({ state: { activeCity: city } })
      );
      // سازگاری با کدهای قدیمی که مستقیم `selected_city` را می‌خوانند.
      window.localStorage.setItem(LEGACY_STORAGE_KEY, city.name);
    } else {
      window.localStorage.removeItem(key);
      window.localStorage.removeItem(LEGACY_STORAGE_KEY);
    }
  } catch {
    // localStorage در دسترس نیست — استیت حافظه‌ای همچنان کار می‌کند.
  }
}

async function fetchServerCity(): Promise<ShekarchiCity | null> {
  try {
    const response = await fetch(`${apiBaseUrl()}/users/me/preferences`, {
      cache: 'no-store',
      headers: await authHeaders()
    });
    if (!response.ok) return null;
    const body = (await response.json()) as { preferences?: Record<string, string> };
    return findCityByName(body.preferences?.[PREFERENCE_KEY]);
  } catch {
    return null;
  }
}

async function pushServerCity(city: ShekarchiCity): Promise<void> {
  try {
    await fetch(`${apiBaseUrl()}/users/me/preferences`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
      body: JSON.stringify({ preferences: { [PREFERENCE_KEY]: city.name } })
    });
  } catch {
    // آفلاین یا بی‌توکن — کش لوکال همچنان معتبر است، دفعهٔ بعد سینک می‌شود.
  }
}

interface CityStoreState {
  /** شناسهٔ کاربر فعلی (sub توکن)؛ null یعنی ناشناس/بای‌پس. */
  subject: string | null;
  /** شهر فعال؛ null یعنی کاربر هنوز انتخاب نکرده (گیت باز می‌شود). */
  activeCity: ShekarchiCity | null;
  /** باز بودن مدال انتخاب شهر (گیت اول یا سوییچر هدر). */
  isCityModalOpen: boolean;
  /** true یعنی گیت اجباری اول ورود است (backdrop close ندارد). */
  initialGate: boolean;
  /** hydration از localStorage تمام شده — برای جلوگیری از hydration mismatch. */
  hasHydrated: boolean;
  /** سینک اولیه با سرور انجام شده (تا نژاد لوکال/سرور مشخص شود). */
  hasSyncedServer: boolean;
  setActiveCity: (city: ShekarchiCity) => void;
  clearActiveCity: () => void;
  openCityModal: (initialGate?: boolean) => void;
  closeCityModal: () => void;
  setHasHydrated: (value: boolean) => void;
  /**
   * ورود کاربر (یا تغییر کاربر): کش همان کاربر + سرور خوانده می‌شود.
   * سرور برنده است؛ اگر سرور شهری داشت، همان اعمال و در کش همان کاربر ذخیره
   * می‌شود. اگر نداشت ولی کش لوکال داشت، کش به سرور پوش می‌شود.
   */
  bindSubject: (subject: string | null) => Promise<void>;
  /** سینک دستی با سرور (بعد از لاگین دیرهنگام Auth.js). */
  syncWithServer: () => Promise<void>;
}

export const useCityStore = create<CityStoreState>()(
  persist(
    (set, get) => ({
      subject: null,
      activeCity: null,
      isCityModalOpen: false,
      initialGate: true,
      hasHydrated: false,
      hasSyncedServer: false,
      setActiveCity: (city) => {
        const { subject, initialGate } = get();
        set({ activeCity: city, isCityModalOpen: false, initialGate: false });
        writeStoredCity(userStorageKey(subject), city);
        // هر تغییر شهر همان لحظه به سرور پوش می‌شود تا لاگین بعدی همان بیاید.
        void pushServerCity(city);
        // اگر گیت اول ورود بود، به داشبورد redirect شود.
        if (initialGate && typeof window !== 'undefined') {
          setTimeout(() => {
            window.location.href = '/dashboard/overview';
          }, 100);
        }
      },
      clearActiveCity: () => {
        const { subject } = get();
        writeStoredCity(userStorageKey(subject), null);
        set({ activeCity: null, isCityModalOpen: true, initialGate: true });
      },
      openCityModal: (initialGate = false) =>
        set({ isCityModalOpen: true, initialGate }),
      closeCityModal: () =>
        set((state) => (state.activeCity ? { isCityModalOpen: false } : state)),
      setHasHydrated: (value) => set({ hasHydrated: value }),
      bindSubject: async (subject) => {
        const prev = get().subject;
        // همان کاربر و قبلاً سینک شده — کاری نکن.
        if (prev === subject && get().hasSyncedServer) return;
        set({ subject, hasSyncedServer: false });
        // کش همان کاربر (با مهاجرت یک‌باره از کلیدهای قدیمی سراسری).
        let local: ShekarchiCity | null = null;
        if (typeof window !== 'undefined') {
          local =
            readStoredCity(userStorageKey(subject)) ??
            readStoredCity(GLOBAL_STORAGE_KEY) ??
            readStoredCity(LEGACY_STORAGE_KEY);
        }
        // سرور برنده است: شهر سرور روی کش همان کاربر می‌نشیند.
        const server = await fetchServerCity();
        const winner = server ?? local;
        if (winner) {
          set({ activeCity: winner, isCityModalOpen: false, initialGate: false });
          if (typeof window !== 'undefined') {
            writeStoredCity(userStorageKey(subject), winner);
          }
          // کش لوکال که سرور نداشت — به سرور پوش شود تا دستگاه بعدی هم بگیرد.
          if (!server && subject) await pushServerCity(winner);
        } else {
          set({ activeCity: null, isCityModalOpen: true, initialGate: true });
        }
        set({ hasSyncedServer: true, hasHydrated: true });
      },
      syncWithServer: async () => {
        const server = await fetchServerCity();
        if (server) {
          const { subject } = get();
          set({ activeCity: server, isCityModalOpen: false, initialGate: false });
          if (typeof window !== 'undefined') {
            writeStoredCity(userStorageKey(subject), server);
          }
        }
        set({ hasSyncedServer: true });
      }
    }),
    {
      // persist فقط برای سازگاری با رفرشِ قبل از bindSubject است؛
      // منبع حقیقت کلید به‌ازای کاربر است که bindSubject می‌خواند/می‌نویسد.
      name: GLOBAL_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ activeCity: state.activeCity }) as CityStoreState,
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.setHasHydrated(true);
          // تا bindSubject (با subject واقعی) صدا زده نشده، گیت باز می‌ماند
          // مگر اینکه کش سراسری قدیمی شهری داشته باشد.
          if (!state.activeCity && typeof window !== 'undefined') {
            const legacy =
              readStoredCity(GLOBAL_STORAGE_KEY) ??
              readStoredCity(LEGACY_STORAGE_KEY);
            if (legacy) state.activeCity = legacy;
          }
          state.isCityModalOpen = !state.activeCity;
          state.initialGate = !state.activeCity;
        }
      }
    }
  )
);

/** نام شهر فعال برای فیلترهای API (همان `Property.city` بک‌اند). */
export function useActiveCityName(): string | null {
  return useCityStore((state) => state.activeCity?.name ?? null);
}
