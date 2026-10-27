/** Public copy links to existing protected pages; their auth/RBAC gates still apply. */
export const landingRoutes = {
  dashboard: "/dashboard",
  avm: "/dashboard/avm",
  radar: "/dashboard/properties",
  map: "/dashboard/avm#market-map",
  billing: "/dashboard/billing",
  submit: "/dashboard/properties/submit",
  signIn: "/auth/sign-in",
  signUp: "/auth/sign-up"
} as const;

export const publicNavigation = [
  { label: "جستجوی ملک", href: "#search" },
  { label: "ابزارهای هوشمند", href: "#professional-tools" },
  { label: "تعرفه و اشتراک", href: "#subscription-plans" },
  { label: "ویژهٔ مشاوران", href: "#agency-services" },
  { label: "ورود به سامانه", href: landingRoutes.dashboard }
] as const;
