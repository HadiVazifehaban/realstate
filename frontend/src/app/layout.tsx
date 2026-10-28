import Providers from '@/components/layout/providers';
import { Toaster } from '@/components/ui/sonner';
import { fontVariables } from '@/components/themes/font.config';
import { DEFAULT_THEME, THEMES } from '@/components/themes/theme.config';
import ThemeProvider from '@/components/themes/theme-provider';
import { cn } from '@/lib/utils';
import { BRAND_ASSET_VERSION } from '@/lib/brand';
import type { Metadata, Viewport } from 'next';
import { cookies, headers } from 'next/headers';
import { redirect } from 'next/navigation';
import NextTopLoader from 'nextjs-toploader';
import { NuqsAdapter } from 'nuqs/adapters/next/app';
import "swiper/css";
import "swiper/css/navigation";
import "swiper/css/scrollbar";
import "../styles/globals.css";
import "../styles/properties-mobile.css";
import RequireCitySelection from '@/components/RequireCitySelection';
import { AUTH_BYPASS_ENABLED, KEYCLOAK_ENABLED } from '@/lib/utils';
import { getValidAuthSession } from '@/lib/auth/server-session';
import { safeInternalPath } from '@/lib/auth/session-validity';
import { requiredRolesForPage } from '@/lib/auth/route-policy';

export const dynamic = 'force-dynamic';

const META_THEME_COLORS = {
  light: "#ffffff",
  dark: "#09090b"
};

export const metadata: Metadata = {
  ...(process.env.NEXT_PUBLIC_APP_URL
    ? { metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL) }
    : {}),
  title: {
    default: "سامانه مدیریت املاک و شبکه همکاران",
    template: "%s | شکارچی"
  },
  description: "سامانه مدیریت فایل‌های املاک، تطبیق مکانی و موتور ارزش‌گذاری خودکار برای دفاتر املاک.",
  openGraph: {
    title: "سامانه مدیریت املاک و شبکه همکاران",
    description:
      "سامانه مدیریت فایل‌های املاک، تطبیق مکانی و موتور ارزش‌گذاری خودکار برای دفاتر املاک.",
    siteName: "شکارچی",
    type: "website"
  },
  twitter: {
    card: "summary_large_image",
    title: "سامانه مدیریت املاک و شبکه همکاران",
    description: "سامانه مدیریت فایل‌های املاک، تطبیق مکانی و موتور ارزش‌گذاری خودکار برای دفاتر املاک."
  },
  icons: {
    icon: `/brand/icon.png?v=${BRAND_ASSET_VERSION}`,
    apple: `/brand/icon.png?v=${BRAND_ASSET_VERSION}`
  }
};

// Declared through the viewport API so Next.js emits the `<meta name='theme-color'>`
// tags itself. An inline <script> in the layout is not an option here: React does not
// execute scripts rendered inside a component tree on the client, so it would warn and
// then silently fail to apply the color after hydration or any client-side navigation.
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: META_THEME_COLORS.light },
    { media: "(prefers-color-scheme: dark)", color: META_THEME_COLORS.dark }
  ]
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const requestHeaders = await headers();
  const protectedRoute = requestHeaders.get('x-shekarchi-protected-route') !== 'false';
  if (protectedRoute && KEYCLOAK_ENABLED && !AUTH_BYPASS_ENABLED) {
    const session = await getValidAuthSession();
    if (!session) {
      const returnTo = safeInternalPath(requestHeaders.get('x-shekarchi-request-path')) ?? '/';
      redirect(`/auth/sign-in?callbackUrl=${encodeURIComponent(returnTo)}`);
    }
    const currentPath = safeInternalPath(requestHeaders.get('x-shekarchi-request-path')) ?? '/';
    const pathname = new URL(currentPath, 'https://shekarchi.invalid').pathname;
    const requiredRoles = requiredRolesForPage(pathname);
    if (requiredRoles && !requiredRoles.some((role) => session.user.roles?.includes(role))) {
      // Throwing notFound from the root layout discards the application shell
      // before its providers exist and can leave the browser with a blank 404.
      // Keep authorization fail-closed, but render an explicit denial page.
      redirect('/access-denied');
    }
  }

  const cookieStore = await cookies();
  const activeThemeValue = cookieStore.get("active_theme")?.value;
  const isValidTheme = THEMES.some((t) => t.value === activeThemeValue);
  const themeToApply = isValidTheme ? activeThemeValue! : DEFAULT_THEME;

  return (
    <html lang='fa' dir='rtl' suppressHydrationWarning className={themeToApply}>
      <body
        className={cn(
          "bg-background overflow-x-hidden overscroll-none font-sans antialiased",
          fontVariables
        )}
      >
        <NextTopLoader color='var(--primary)' showSpinner={false} />
        <NuqsAdapter>
          <ThemeProvider
            attribute='class'
            defaultTheme={themeToApply}
            enableSystem={false}
            disableTransitionOnChange
            enableColorScheme
          >
           <Providers activeThemeValue={themeToApply}>
             <Toaster />
             <RequireCitySelection>
               {children}
             </RequireCitySelection>
           </Providers>
          </ThemeProvider>
        </NuqsAdapter>
      </body>
    </html>
  );
}
