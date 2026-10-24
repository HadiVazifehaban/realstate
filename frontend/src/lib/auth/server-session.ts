import 'server-only';

import { auth } from '@/lib/auth/config';
import { hasValidKeycloakSession } from '@/lib/auth/session-validity';

/** Resolve/refresh Auth.js server-side and fail closed on expired credentials. */
export async function getValidAuthSession() {
  const session = await auth();
  return hasValidKeycloakSession(session) ? session : null;
}
