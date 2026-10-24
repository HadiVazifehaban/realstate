// ============================================================
// Route Handler — Single User (update + delete)
// ============================================================
// See src/app/api/users/route.ts for pattern documentation.
// ============================================================

import { fakeUsers } from '@/constants/mock-api-users';
import { NextRequest, NextResponse } from 'next/server';
import { requireRouteSession } from '@/lib/auth/route-guard';

type Params = { params: Promise<{ id: string }> };

export async function PUT(request: NextRequest, { params }: Params) {
  const denied = await requireRouteSession();
  if (denied) return denied;
  const { id } = await params;
  const body = await request.json();
  const data = await fakeUsers.updateUser(Number(id), body);

  if (!data.success) {
    return NextResponse.json(data, { status: 404 });
  }

  return NextResponse.json(data);
}

export async function DELETE(request: NextRequest, { params }: Params) {
  const denied = await requireRouteSession();
  if (denied) return denied;
  const { id } = await params;
  const data = await fakeUsers.deleteUser(Number(id));

  if (!data.success) {
    return NextResponse.json(data, { status: 404 });
  }

  return NextResponse.json(data);
}
