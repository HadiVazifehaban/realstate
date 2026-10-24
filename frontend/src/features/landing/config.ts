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
  { label: "تحلیل هوشمند AVM", href: landingRoutes.avm },
  { label: "رادار قیمت", href: landingRoutes.radar },
  { label: "نقشهٔ بازار", href: landingRoutes.map },
  { label: "تعرفه و اشتراک", href: landingRoutes.billing }
] as const;
