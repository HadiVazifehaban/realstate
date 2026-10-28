import { NavGroup } from "@/types";

/**
 * Navigation configuration with RBAC support.
 *
 * This drives three surfaces from one source of truth: the sidebar, the Cmd+K
 * bar and the breadcrumb trail — so a rename or re-group here lands everywhere
 * at once. Items are grouped into labelled sections, each rendered with a
 * SidebarGroupLabel.
 *
 * IA (four blocks, most- to least-frequent):
 *
 *   1. نمای کلی         — the 360° numbers.
 *   2. رادار و املاک    — the core loop: find a price, file a property, work the
 *                         desk's files, value the market.
 *   3. معاملات و شبکه   — deals desk, inter-office MLS, comms.
 *   4. مدیریت و زیرساخت — team & access, CRM calendar, admin-gated ops.
 *
 * Conventions:
 *  - Names use the office's own vocabulary, never backend jargon. The old
 *    «صف جاوب» (a mis-translation of Job Queue) and the standalone
 *    «پایپ‌لاین پنج فاز» are gone; the pipeline now lives inside «میز کار معاملات».
 *  - `badge` renders a small status chip («زنده», «جدید», «به‌زودی»). A
 *    `disabled` row renders as a non-navigating button with a «به‌زودی» chip, so
 *    a click never lands on an unfinished page.
 *  - `access.roles` is an any-of realm-role gate for the infra block; ordinary
 *    brokers never see «صف پردازش» or «لاگ ممیزی».
 *
 * RBAC Access Control (see `use-nav.ts`):
 *  - access: { requireOrg: true }
 *  - access: { permission: 'org:teams:manage' }
 *  - access: { role: 'admin' }                     (exact single match)
 *  - access: { roles: ['ROLE_ADMIN', ...] }        (any-of; the admin block)
 */
export const navGroups: NavGroup[] = [
  {
    label: "نمای کلی",
    items: [
      {
        title: "خانهٔ شکارچی",
        url: "/dashboard",
        icon: "home",
        isActive: false,
        items: []
      },
      {
        title: "داشبورد مدیریتی",
        url: "/dashboard/overview",
        icon: "dashboard",
        isActive: false,
        shortcut: ["d", "d"],
        items: []
      }
    ]
  },
  {
    label: "رادار و املاک",
    items: [
      {
        title: "رادار شکار قیمت",
        url: "/dashboard/properties",
        icon: "crosshair",
        badge: "زنده",
        isActive: false,
        shortcut: ["p", "r"],
        items: []
      },
      {
        title: "ثبت و فایلینگ ملک",
        url: "/dashboard/properties/submit",
        icon: "plusCircle",
        isActive: false,
        items: []
      },
      {
        title: "کارتابل فایل‌های دفتر",
        url: "/dashboard/workspaces",
        icon: "workspace",
        isActive: false,
        items: []
      },
      {
        title: "تحلیل بازار و ارزش‌گذاری (AVM)",
        url: "/dashboard/avm",
        icon: "trendingUp",
        isActive: false,
        shortcut: ["a", "v"],
        items: []
      }
    ]
  },
  {
    label: "معاملات و شبکه",
    items: [
      {
        title: "میز کار معاملات",
        url: "/dashboard/crm",
        icon: "kanban",
        description: "پایپ‌لاین معاملات، پرونده‌ها و کمیسیون",
        isActive: false,
        shortcut: ["c", "r"],
        items: []
      },
      {
        title: "شبکه همکاری دفاتر",
        url: "/dashboard/network/agencies",
        icon: "network",
        badge: "جدید",
        isActive: false,
        items: [
          { title: "کد معرف دفتر", url: "/dashboard/agency/referral", icon: "referral", access: { roles: ["ROLE_ADMIN", "ROLE_AGENCY_MANAGER"] } },
          { title: "دفاتر همکار", url: "/dashboard/network/agencies", icon: "office" },
          { title: "درخواست‌های همکاری", url: "/dashboard/network/requests", icon: "handshake" },
          { title: "فایل‌های اشتراکی", url: "/dashboard/network/shared-listings", icon: "share" },
          { title: "ارجاع‌ها", url: "/dashboard/network/referrals", icon: "referral" },
          { title: "انتقال فایل‌ها", url: "/dashboard/network/transfers", icon: "transfer" },
          { title: "کمیسیون و تسویه", url: "/dashboard/network/commissions", icon: "split" },
          { title: "اختلافات", url: "/dashboard/network/disputes", icon: "gavel" },
          { title: "گزارش همکاری‌ها", url: "/dashboard/network/reports", icon: "chart" },
          { title: "رهگیری و لاگ", url: "/dashboard/network/audit", icon: "audit" }
        ]
      },
      {
        title: "مرکز ارتباطات",
        url: "/dashboard/chat",
        icon: "chat",
        isActive: false,
        items: [
          { title: "گفتگوهای همکاران", url: "/dashboard/chat", icon: "chat", shortcut: ["c", "c"] },
          {
            title: "دستیار هوشمند شکارچی",
            url: "/dashboard/ai-chat",
            icon: "sparkles",
            badge: "به‌زودی",
            disabled: true,
            shortcut: ["a", "i"]
          }
        ]
      }
    ]
  },
  {
    label: "مدیریت و زیرساخت",
    items: [
      {
        title: "پیوندهای شبکه‌های اجتماعی",
        url: "/dashboard/settings/social-links",
        icon: "settings",
        access: { roles: ["ROLE_ADMIN", "ROLE_SUPER_ADMIN", "admin", "super_admin"] },
        items: []
      },
      {
        title: "تنظیمات درگاه زیبال",
        url: "/dashboard/settings/zibal",
        icon: "creditCard",
        description: "مدیریت امن کد مرچنت، محیط آزمایشی و Callback",
        access: { roles: ["ROLE_ADMIN"] },
        isActive: false,
        items: []
      },
      {
        title: "مدیریت Keycloak",
        url: "/dashboard/settings/keycloak",
        icon: "lock",
        description: "مدیریت Realm هویت با مجوزهای تأییدشده",
        access: { roles: ["ROLE_ADMIN"] },
        isActive: false,
        items: [
          { title: "داشبورد Keycloak", url: "/dashboard/settings/keycloak", icon: "dashboard", access: { roles: ["ROLE_ADMIN"] } },
          { title: "کاربران", url: "/dashboard/settings/keycloak/users", icon: "teams", access: { roles: ["ROLE_ADMIN"] } },
          { title: "گروه‌ها", url: "/dashboard/settings/keycloak/groups", icon: "workspace", access: { roles: ["ROLE_ADMIN"] } },
          { title: "نقش‌ها", url: "/dashboard/settings/keycloak/roles", icon: "badgeCheck", access: { roles: ["ROLE_ADMIN"] } },
          { title: "Clientها", url: "/dashboard/settings/keycloak/clients", icon: "settings", access: { roles: ["ROLE_ADMIN"] } },
          { title: "Client Scopeها", url: "/dashboard/settings/keycloak/client-scopes", icon: "settings", access: { roles: ["ROLE_ADMIN"] } },
          { title: "تنظیمات Realm", url: "/dashboard/settings/keycloak/realm-settings", icon: "settings", access: { roles: ["ROLE_ADMIN"] } },
          { title: "Authentication Flowها", url: "/dashboard/settings/keycloak/authentication", icon: "lock", access: { roles: ["ROLE_ADMIN"] } },
          { title: "Identity Providerها", url: "/dashboard/settings/keycloak/identity-providers", icon: "network", access: { roles: ["ROLE_ADMIN"] } },
          { title: "User Federation", url: "/dashboard/settings/keycloak/user-federation", icon: "network", access: { roles: ["ROLE_ADMIN"] } },
          { title: "رویدادها", url: "/dashboard/settings/keycloak/events", icon: "calendar", access: { roles: ["ROLE_ADMIN"] } },
          { title: "مجوزهای مدیر", url: "/dashboard/settings/keycloak/admin-permissions", icon: "fileTypeDoc", access: { roles: ["ROLE_ADMIN"] } }
        ]
      },
      {
        title: "تیم و سطوح دسترسی",
        url: "/dashboard/users",
        icon: "teams",
        description: "مدیریت مشاوران، سرپرستان و نقش‌ها",
        access: { roles: ["ROLE_ADMIN", "ROLE_AGENCY_MANAGER"] },
        isActive: false,
        shortcut: ["u", "u"],
        items: [
          {
            title: "اعضای دفتر",
            url: "/dashboard/workspaces/team",
            icon: "employee",
            access: { requireOrg: true }
          }
        ]
      },
      {
        title: "رویدادها و تقویم CRM",
        url: "/dashboard/events",
        icon: "calendar",
        isActive: false,
        shortcut: ["e", "v"],
        items: []
      },
      {
        title: "نقش‌های کاربر",
        url: "/dashboard/roles",
        icon: "badgeCheck",
        description: "مشاهده نقش‌های Keycloak و وضعیت احراز هویت",
        access: { roles: ["ROLE_ADMIN"] },
        isActive: false,
        items: []
      },
      {
        // Admin-only ops block: any-of role gate keeps it hidden from ordinary
        // brokers. A normal user should never see a job queue or an audit log.
        title: "مرکز امنیت و عملیات",
        url: "/dashboard/otp",
        icon: "lock",
        access: { roles: ["ROLE_ADMIN", "ROLE_SUPERVISOR", "ROLE_DATA_ANALYST"] },
        isActive: false,
        items: [
          { title: "مدیریت OTP", url: "/dashboard/otp", icon: "lock", shortcut: ["o", "t"], access: { roles: ["ROLE_ADMIN"] } },
          {
            title: "خزانه هویت و مالکیت",
            url: "/dashboard/pii",
            icon: "badgeCheck",
            shortcut: ["p", "i"],
            access: { roles: ["ROLE_ADMIN", "ROLE_SUPERVISOR", "ROLE_DATA_ANALYST"] }
          },
          {
            title: "صف پردازش و خزش",
            url: "/dashboard/streams",
            icon: "inbox",
            shortcut: ["s", "t"],
            access: { roles: ["ROLE_ADMIN", "ROLE_SUPERVISOR", "ROLE_DATA_ANALYST"] }
          },
          {
            title: "لاگ ممیزی",
            url: "/dashboard/audit",
            icon: "fileTypeDoc",
            shortcut: ["a", "u"],
            access: { roles: ["ROLE_ADMIN", "ROLE_SUPERVISOR", "ROLE_DATA_ANALYST"] }
          }
        ]
      }
    ]
  }
];

/** Shared by the sidebar footer and the dashboard landing; logout remains an action. */
export const accountNavItems: import("@/types").NavItem[] = [
  { title: "پروفایل", url: "/dashboard/profile", icon: "account" },
  {
    title: "امور مالی",
    url: "/dashboard/billing",
    icon: "creditCard",
    access: { requireOrg: true }
  },
  { title: "اعلان‌ها", url: "/dashboard/notifications", icon: "notification" }
];
