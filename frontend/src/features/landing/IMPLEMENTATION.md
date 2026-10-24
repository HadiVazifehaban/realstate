# Dashboard landing — local implementation report

## Integration

- Next.js 16.2.12 App Router, React 19, existing Vazir font, Tabler icons and Base UI Dialog.
- Every `/dashboard` route now uses the shared full-width `DashboardShell` with a sticky obsidian/rose-gold header. The vertical sidebar, sidebar inset and bottom navigation are no longer mounted. `DashboardTopNav` renders all RBAC-filtered groups and nested links with the existing Tabler icons, exact active-route highlights, outside-click dismissal and Escape focus restoration. `/dashboard/overview` remains the analytics dashboard.
- The dashboard home no longer renders a second landing header. The public landing header is unchanged. Dashboard header utilities retain property creation, theme mode/palette selection, notifications, account menu, search, location, office switching and breadcrumbs. A second compact context row retains these secondary workflows; navigation wraps on tablet/mobile without dropping routes. SidebarProvider remains solely for existing office-control compatibility and does not reserve horizontal space.
- The existing public `/` reuses the same content, without the private navigation directory. No parallel demo route was introduced.
- Default Keycloak sign-in destination is `/dashboard`; explicit return destinations and authentication/approval/route guards are unchanged.
- The city-selection modal is not forced on the dashboard home; existing city selection remains available in the header and operational tools.

## Navigation inventory (before and after)

Source: `src/config/nav-config.ts`. Four groups, thirteen top-level items, sixteen child items (29 nodes), including the explicit dashboard home link added after runtime-image diagnosis. All permitted nodes are rendered recursively and in source order. Disabled nodes remain visible but non-navigable.

1. نمای کلی
   - خانهٔ شکارچی — `/dashboard`
   - داشبورد مدیریتی — `/dashboard/overview`
2. رادار و املاک
   - رادار شکار قیمت — `/dashboard/properties`
   - ثبت و فایلینگ ملک — `/dashboard/properties/submit`
   - کارتابل فایل‌های دفتر — `/dashboard/workspaces`
   - تحلیل بازار و ارزش‌گذاری (AVM) — `/dashboard/avm`
3. معاملات و شبکه
   - میز کار معاملات — `/dashboard/crm`
   - شبکه همکاری دفاتر — `/dashboard/network/agencies`
     - دفاتر همکار — `/dashboard/network/agencies`
     - درخواست‌های همکاری — `/dashboard/network/requests`
     - فایل‌های اشتراکی — `/dashboard/network/shared-listings`
     - ارجاع‌ها — `/dashboard/network/referrals`
     - انتقال فایل‌ها — `/dashboard/network/transfers`
     - کمیسیون و تسویه — `/dashboard/network/commissions`
     - اختلافات — `/dashboard/network/disputes`
     - گزارش همکاری‌ها — `/dashboard/network/reports`
     - رهگیری و لاگ — `/dashboard/network/audit`
   - مرکز ارتباطات — `/dashboard/chat`
     - گفتگوهای همکاران — `/dashboard/chat`
     - دستیار هوشمند شکارچی — `/dashboard/ai-chat` (disabled, coming soon)
4. مدیریت و زیرساخت
   - تیم و سطوح دسترسی — `/dashboard/users`
     - اعضای دفتر — `/dashboard/workspaces/team` (requires organization/tenant)
   - رویدادها و تقویم CRM — `/dashboard/events`
   - نقش‌های کاربر — `/dashboard/roles`
   - مرکز امنیت و عملیات — `/dashboard/otp`
     - مدیریت OTP — `/dashboard/otp`
     - خزانه هویت و مالکیت — `/dashboard/pii`
     - صف پردازش و خزش — `/dashboard/streams`
     - لاگ ممیزی — `/dashboard/audit`

The last three operations children require any of ROLE_ADMIN, ROLE_SUPERVISOR or ROLE_DATA_ANALYST according to the existing sidebar configuration. All other listed main-menu nodes have no sidebar visibility restriction. In particular, the OTP parent/child is not role-gated in that configuration. Existing page guards can be stricter than sidebar visibility; this implementation does not loosen them or silently change the sidebar policy.

Sidebar footer: three route items (profile, organization-dependent billing, notifications) now share `accountNavItems`; logout remains the existing explicit sign-out action in both surfaces. No automatic logout or submission occurs.

Locally tested navigation profiles:

| Context | Main-directory links | Disabled nodes | Hidden nodes |
| --- | ---: | ---: | --- |
| No role, no tenant | 24 | 1 | Team member child and three role-gated operations children |
| Junior broker with tenant | 25 | 1 | Three role-gated operations children |
| Administrator with tenant | 28 | 1 | None |
| Data analyst with tenant | 28 | 1 | None in sidebar visibility; route guards still apply |

The parity test compares the complete ordered title/URL sequence from the shared filtering hook with the landing directory. Parent and child entries sharing a route are deliberately not deduplicated. Recursive filtering now applies the same existing permission rules at arbitrary depth rather than only one child level.

## Real actions and sources

- The `#search` section reuses the existing inventory API and `ListingCard` with six results per request. Search text, city, neighborhood, type, price ceiling and minimum area apply server-side on submit; deal and showcase chips apply immediately. Rent includes both RENT and FULL_MORTGAGE. Reset restores the unfiltered latest view (React Query may serve its fresh cached response).
- Showcase choices are latest active inventory, BARGAIN-valued inventory and agency-submitted inventory. No sample listings or image substitutions are used. Loading, empty, access-denied and retry states are explicit. A broader feed is available through the all-listings link; no unsupported global sorting is implied.

- AVM: `/dashboard/avm`; map: `/dashboard/avm#market-map`.
- Radar: `/dashboard/properties`; listing submission: `/dashboard/properties/submit`.
- Billing: `/dashboard/billing`; plan CTAs navigate here without posting orders.
- Pricing uses the existing `fetchPlans` client and `GET /billing/plans` through the authenticated same-origin BFF. Source catalog: `app/services/billing.py`, IDs free, monthly, quarterly, yearly. No duplicated fallback price table or reference-site discounts.
- Displayed quotas are the returned listing, SMS and advisor quotas. Region quotas are not represented as geographic coverage. API feature strings are not promoted as verified delivered capabilities by this landing.
- Existing billing flow creates an order on user action, accepts a card-transfer receipt and requires financial review. Test approval does not activate a subscription. The landing creates no orders and collects no payment or personal data.
- Existing sign-in `/auth/sign-in` and mobile registration `/auth/sign-up` are retained; no membership-request endpoint, form, contact promise or demo booking was fabricated.

## Geography and presentation

- Hero opportunity float: reference-style 288px obsidian glass card at right 3% / top 50%, visible from 1536px, with original bell paths, pulse and slow float (disabled by reduced-motion). Shares the real bargain query/cache with radar; property type, area, location, negative AVM deviation and price-to-AVM bar come from a valid returned BARGAIN. No result/error/missing valuation means no card. The label does not claim a newly published alert.

- Tool previews now query the existing authenticated market-neighbourhood and bargain endpoints, scoped by the active city, refreshed every minute. AVM shows the server's sale-price median and a cross-sectional comparison of returned neighbourhood medians (not a fabricated time series). Map/radar points use only valid returned coordinates with relative geographic projection, explicitly not street geometry. Radar counts describe the returned sample, not an assumed inventory total. No synthetic prices, growth percentages, historical periods, streets or fixed targets remain. Loading, empty, access-denied and retry states replace unavailable data. Existing authorization and tool links are unchanged.

- Reference reinspection: the skyline treatment is not low-resolution pixelation. It combines the unchanged photograph (object position 50% 78%, opacity .9), a 56px copper grid with radial mask, matching gradient/vignette layers, soft copper glow, floating particles and a non-interactive SVG noise overlay at opacity .035. These layers are now recreated locally. Hero is centered; footer follows the reference's four-column proportions (1.5/1/1/1.3), 48px gaps and divided payment/copyright row. Existing project branding, factual copy and functional destinations are intentionally retained rather than copying unsupported contact/developer claims.

- Hero uses the supplied Tehran skyline image; product copy refers to Iran, not only Tehran.
- AVM/radar/maps are described subject to available city/neighborhood data. No city count, countrywide map coverage, live market metric or investment return is claimed.
- Map tile code retains a Tehran default center; this is not evidence of nationwide tile coverage. Existing scraper configuration also defaults to Tehran. No runtime coverage count was inferred from those defaults.
- Reference-site Tehran region counts, demo charts, discount claims, contact details and activation form were not copied. The unsupported company attribution in the earlier landing footer was removed.
- The landing uses a fixed glass header with responsive dropdowns and the existing account menu (organization-gated billing, notifications and provider logout). Other dashboard routes retain the sidebar-native account menu. SidebarProvider stays mounted so saved collapse preferences survive navigation.
- Reference-inspired glass, copper gradients, pricing cards and decorative SVG chart/map/radar previews are scoped to landing CSS. CSS view-timeline reveals progressively enhance supported browsers; content stays visible otherwise. Reduced-motion preferences disable animations. The previews explicitly identify themselves as schematic, not live data.
- Both `#pricing` and the existing `#subscription-plans` anchors reach the API-backed pricing section.

## Validation and limitations

- Local unit/component suite: 108 passed, including navigation parity across four access contexts, deeper recursive filtering and pricing loading/error/success states.
- Local TypeScript and production-mode compilation passed; this was a local build, not production execution/deployment.
- Full lint: 30 existing warnings, zero errors; targeted implementation lint: zero warnings/errors. Build retains the existing Sentry/OpenTelemetry dynamic-require warning.
- Local browser layout checked at 360, 390, 768, 1024, 1366 and 1920; no horizontal content overflow observed. Screenshots and measurements are under `/tmp/shekarchi-dashboard-*`.
- Preview used the pre-existing development-only auth bypass in a disposable local process; no environment files or auth guards were changed. Billing correctly returned an authorization error without a real session. Authenticated pricing, payments and live market data were not tested.
- Existing theme-dependent sidebar Logo emits a hydration warning (`logo.png` versus `logo-light.png`) in the local preview. This unrelated component was not rewritten.
- No database migration, listing schema change, visit-booking change, map-provider dependency, production configuration change, deploy, service restart, commit or push.