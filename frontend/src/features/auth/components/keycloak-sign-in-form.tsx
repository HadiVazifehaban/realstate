"use client";

import { Icons } from '@/components/icons';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import * as React from 'react';
import { beginKeycloakSignIn, resolveCallbackUrl } from './keycloak-sign-in';

/**
 * The realm accepts either an email or a phone number as its username, so both
 * are accepted here. This only decides whether we pre-fill the realm's username
 * field -- it is not an authentication check, and the realm performs no less
 * validation if a stranger types something else.
 */
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const IRAN_MOBILE_RE = /^(?:\+98|0)?9\d{9}$/;

function isPlausibleIdentifier(value: string): boolean {
  const compact = value.replace(/[\s-]/g, '');
  return EMAIL_RE.test(compact) || IRAN_MOBILE_RE.test(compact);
}

/**
 * Sign-in form for the Keycloak hand-off.
 *
 * The single field is the identifier, and it is used as `login_hint` so the
 * realm's login page arrives with the username already filled in.
 *
 * There is deliberately no password field. The realm owns credentials, so a
 * password typed here would have nowhere to go: the app would either drop it
 * (so a typo would be indistinguishable from a wrong password) or hold it in
 * memory, which is exactly what routing authentication to a single
 * identity provider is meant to avoid. The note under the button says so,
 * rather than leaving the user to guess where their password went.
 */
export function KeycloakSignInForm() {
  const [identifier, setIdentifier] = React.useState('');
  const [error, setError] = React.useState<string | null>(null);
  const [pending, startTransition] = React.useTransition();

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const value = identifier.trim();

    if (!value) {
      setError('ایمیل یا شمارهٔ موبایل خود را وارد کنید.');
      return;
    }
    if (!isPlausibleIdentifier(value)) {
      setError('ایمیل یا شمارهٔ موبایل معتبر وارد کنید.');
      return;
    }

    setError(null);
    startTransition(async () => {
      try {
        await beginKeycloakSignIn({
          callbackUrl: resolveCallbackUrl(window.location.search),
          loginHint: value
        });
      } catch {
        setError('انتقال به صفحهٔ ورود ممکن نشد. لطفاً دوباره تلاش کنید.');
      }
    });
  };

  return (
    <form onSubmit={submit} noValidate className='space-y-4'>
      <div className='space-y-2'>
        <label
          htmlFor='sign-in-identifier'
          className='text-showcase-text block text-sm font-medium'
        >
          ایمیل یا شمارهٔ موبایل
        </label>
        <div className='relative'>
          <Icons.account
            aria-hidden
            className='text-showcase-dim pointer-events-none absolute inset-y-0 end-3 my-auto h-4 w-4'
          />
          <Input
            id='sign-in-identifier'
            name='identifier'
            type='text'
            inputMode='email'
            autoComplete='username'
            autoCapitalize='none'
            spellCheck={false}
            dir='ltr'
            placeholder='you@example.com'
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? 'sign-in-identifier-error' : undefined}
            className={cn(
              'border-showcase-border h-12 rounded-xl bg-white/5 ps-10 pe-4',
              'text-showcase-text placeholder:text-showcase-dim',
              'focus-visible:border-gold-accent focus-visible:ring-gold-accent/25',
              'aria-invalid:border-showcase-danger'
            )}
          />
        </div>
        {error ? (
          <p
            id='sign-in-identifier-error'
            role='alert'
            className='text-showcase-danger text-sm'
          >
            {error}
          </p>
        ) : null}
      </div>

      <button
        type='submit'
        disabled={pending}
        className={cn(
          'group relative flex h-12 w-full items-center justify-center gap-2 overflow-hidden rounded-xl',
          'bg-linear-to-l from-gold-primary via-gold-accent to-gold-dark',
          'text-showcase-base text-sm font-semibold',
          'transition-transform hover:scale-[1.01] active:scale-[0.99]',
          'focus-visible:ring-gold-accent/40 focus-visible:ring-2 focus-visible:outline-none',
          'disabled:pointer-events-none disabled:opacity-70'
        )}
      >
        {pending ? 'در حال انتقال…' : 'ادامهٔ ورود'}
        {!pending ? (
          <Icons.arrowRight
            aria-hidden
            className='h-4 w-4 rotate-180 transition-transform group-hover:-translate-x-0.5'
          />
        ) : null}
      </button>

      <p className='text-showcase-dim flex items-start gap-2 text-xs leading-5'>
        <Icons.lock aria-hidden className='mt-0.5 h-3.5 w-3.5 shrink-0' />
        <span>
          رمز عبور شما در صفحهٔ امن مرکز هویت وارد می‌شود و هرگز در این
          صفحه ذخیره نمی‌گردد.
        </span>
      </p>
    </form>
  );
}
