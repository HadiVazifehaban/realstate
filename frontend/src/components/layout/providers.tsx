'use client';
import { ClerkProvider } from '@clerk/nextjs';
import { SessionProvider } from 'next-auth/react';
import React from 'react';
import { AUTH_BYPASS_ENABLED, KEYCLOAK_ENABLED } from '@/lib/utils';
import { ActiveThemeProvider } from '../themes/active-theme';
import QueryProvider from './query-provider';
import { DirectionProvider } from '@/components/ui/direction';

export default function Providers({
  activeThemeValue,
  children
}: {
  activeThemeValue: string;
  children: React.ReactNode;
}) {
  // Three mutually exclusive stacks, chosen once:
  //   * Keycloak -> Auth.js SessionProvider (ClerkProvider is skipped: it throws
  //     without keys and there is no Clerk session in this mode).
  //   * bypass    -> local-dev only; no auth provider at all.
  //   * Clerk     -> the starter's original provider, still the fallback.
  const content = <QueryProvider>{children}</QueryProvider>;
  const noClerk = KEYCLOAK_ENABLED || AUTH_BYPASS_ENABLED;

  return (
    <ActiveThemeProvider initialTheme={activeThemeValue}>
      {/*
        The root layout declares `<html dir='rtl'>`, but Base UI reads
        direction from this context, not from the DOM: with no provider every
        Base UI component silently falls back to LTR math. On the showcase
        sliders that mirrored the drag -- pulling a thumb left jumped it to the
        opposite extreme (`20 -> 0.5`), which read as the drag being broken.
      */}
      <DirectionProvider direction='rtl'>
        {noClerk ? (
          KEYCLOAK_ENABLED ? <SessionProvider>{content}</SessionProvider> : content
        ) : (
          <ClerkProvider
            appearance={{
              variables: {
                colorPrimary: 'var(--primary)',
                colorPrimaryForeground: 'var(--primary-foreground)',
                colorDanger: 'var(--destructive)',
                colorBackground: 'var(--card)',
                colorForeground: 'var(--foreground)',
                colorMuted: 'var(--muted)',
                colorMutedForeground: 'var(--muted-foreground)',
                colorInput: 'var(--input)',
                colorInputForeground: 'var(--foreground)',
                colorBorder: 'var(--border)',
                colorRing: 'var(--ring)',
                fontFamily: 'var(--font-vazir), sans-serif'
              }
            }}
          >
            {content}
          </ClerkProvider>
        )}
      </DirectionProvider>
    </ActiveThemeProvider>
  );
}
