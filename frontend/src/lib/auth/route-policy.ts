const PUBLIC_PAGE_PATHS = new Set(['/', '/auth', '/auth/sign-in', '/auth/sign-up']);
const PUBLIC_AUTH_API_PATHS = new Set([
  '/api/auth',
  '/api/auth/signin',
  '/api/auth/signin/keycloak',
  '/api/auth/callback/keycloak',
  '/api/auth/session',
  '/api/auth/csrf',
  '/api/auth/providers',
  '/api/auth/signout',
  '/api/auth/error',
  '/api/auth/verify-request',
  '/api/auth/keycloak-logout'
]);
const PUBLIC_BACKEND_EXACT = new Set([
  '/backend/api/v1/billing/plans',
  '/backend/api/v1/site/social-links',
  '/backend/api/v1/health',
  '/backend/api/v1/auth/otp/request',
  '/backend/api/v1/auth/otp/verify',
  '/backend/api/v1/auth/quick-register',
  '/backend/api/v1/auth/register',
  '/backend/api/v1/auth/registration-status',
  '/backend/api/v1/auth/roles',
  '/backend/api/v1/registration/cities',
  '/backend/api/v1/registration/roles'
]);

const PAGE_ROLE_POLICIES: Array<[string, string[]]> = [
  ['/dashboard/settings/social-links', ['ROLE_ADMIN', 'ROLE_SUPER_ADMIN', 'admin', 'super_admin']],
  ['/dashboard/properties/submit', ['ROLE_ADMIN', 'ROLE_SUPERVISOR', 'ROLE_AGENCY_MANAGER', 'ROLE_SENIOR_BROKER', 'ROLE_JUNIOR_BROKER', 'ROLE_OWNER']],
  ['/dashboard/properties', ['ROLE_ADMIN', 'ROLE_SUPERVISOR', 'ROLE_AGENCY_MANAGER', 'ROLE_SENIOR_BROKER', 'ROLE_JUNIOR_BROKER']],
  ['/dashboard/users', ['ROLE_ADMIN', 'ROLE_AGENCY_MANAGER']],
  ['/dashboard/roles', ['ROLE_ADMIN']],
  ['/dashboard/workspaces/team', ['ROLE_ADMIN', 'ROLE_AGENCY_MANAGER']],
  ['/dashboard/audit', ['ROLE_ADMIN', 'ROLE_SUPERVISOR']],
  ['/dashboard/otp', ['ROLE_ADMIN', 'ROLE_SUPERVISOR']],
  ['/dashboard/scraper', ['ROLE_ADMIN', 'ROLE_SUPERVISOR']],
  ['/dashboard/pii', ['ROLE_ADMIN', 'ROLE_SUPERVISOR', 'ROLE_AGENCY_MANAGER', 'ROLE_SENIOR_BROKER']],
  ['/dashboard/crm', ['ROLE_ADMIN', 'ROLE_SUPERVISOR', 'ROLE_AGENCY_MANAGER', 'ROLE_SENIOR_BROKER', 'ROLE_JUNIOR_BROKER']],
  ['/dashboard/network', ['ROLE_ADMIN', 'ROLE_SUPERVISOR', 'ROLE_AGENCY_MANAGER', 'ROLE_SENIOR_BROKER']],
  ['/dashboard/agency/referral', ['ROLE_ADMIN', 'ROLE_AGENCY_MANAGER']]
];

/** Explicit allowlist: any new page or API is protected until classified. */
export function isPublicRoute(pathname: string): boolean {
  if (PUBLIC_PAGE_PATHS.has(pathname)) return true;
  if (PUBLIC_AUTH_API_PATHS.has(pathname)) return true;
  if (PUBLIC_BACKEND_EXACT.has(pathname)) return true;
  return pathname.startsWith('/backend/api/v1/auth/professional-registration/');
}

export function isApiPath(pathname: string): boolean {
  return pathname === '/api' || pathname.startsWith('/api/') || pathname === '/backend' || pathname.startsWith('/backend/');
}

export function requiredRolesForPage(pathname: string): readonly string[] | null {
  for (const [prefix, roles] of PAGE_ROLE_POLICIES) {
    if (pathname === prefix || pathname.startsWith(`${prefix}/`)) return roles;
  }
  return null;
}
