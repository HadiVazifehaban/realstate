'use client';

import * as React from 'react';
import { AUTH_BYPASS_ENABLED, KEYCLOAK_ENABLED } from '@/lib/utils';
import { requestAuthJsSession } from '@/lib/auth/session';
import { useCityStore } from '@/store/useCityStore';

/** شناسهٔ پایدار از metadata نشست Auth.js؛ هیچ توکنی به مرورگر داده نمی‌شود. */
function subjectFromSession(session: Awaited<ReturnType<typeof requestAuthJsSession>>): string | null {
  return session?.user?.id || null;
}

/**
 * هویت کاربر را به استور شهر گره می‌زند.
 *
 * - Keycloak: `sub` توکن خوانده و `bindSubject` صدا زده می‌شود — شهر همان
 *   کاربر (کش + سرور) بالا می‌آید، نه شهر کاربر قبلی روی همین مرورگر.
 * - Bypass/Clerk: شناسهٔ ثابت محلی تا رفتار تک‌کاربره حفظ شود.
 *
 * زیر QueryProvider سوار می‌شود (کنار CityQuerySync).
 */
export default function CityIdentityBinder() {
  const bindSubject = useCityStore((s) => s.bindSubject);
  const subject = useCityStore((s) => s.subject);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      let next: string | null = null;
      if (KEYCLOAK_ENABLED) {
        next = subjectFromSession(await requestAuthJsSession());
        // توکن هنوز نیامده (لاگین دیرهنگام Auth.js) — با subject موقت ناشناس
        // bind نکن؛ syncWithServer بعداً با توکن واقعی سینک می‌کند.
        if (!next) {
          await useCityStore.getState().syncWithServer();
          const retry = subjectFromSession(await requestAuthJsSession());
          if (retry && !cancelled) await bindSubject(retry);
          return;
        }
      } else if (AUTH_BYPASS_ENABLED) {
        next = 'local-bypass';
      } else {
        next = 'clerk-user';
      }
      if (!cancelled) await bindSubject(next);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // خروج کاربر: استور به حالت ناشناس برمی‌گردد تا شهر کاربر بعدی لو نرود.
  React.useEffect(() => {
    if (subject) {
      const onStorage = () => {};
      window.addEventListener('storage', onStorage);
      return () => window.removeEventListener('storage', onStorage);
    }
  }, [subject]);

  return null;
}
