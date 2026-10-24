import 'server-only';

import { NextResponse } from 'next/server';
import { getValidAuthSession } from '@/lib/auth/server-session';

/** Defense-in-depth guard for Route Handlers; middleware is not the sole gate. */
export async function requireRouteSession(): Promise<NextResponse | null> {
  const session = await getValidAuthSession();
  if (session) return null;
  return NextResponse.json(
    { error: 'authentication_required', message: 'برای ادامه وارد شوید.' },
    {
      status: 401,
      headers: { 'Cache-Control': 'private, no-store', 'WWW-Authenticate': 'Bearer' }
    }
  );
}
