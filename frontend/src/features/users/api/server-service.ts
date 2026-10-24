import 'server-only';

import { fetchPrivateApi } from '@/lib/server-api';
import type { UserFilters, UsersResponse } from './types';

/** Server Component prefetch; the access token never enters the dehydrated data. */
export async function getUsersForServer(filters: UserFilters): Promise<UsersResponse> {
  const params = new URLSearchParams();
  if (filters.page) params.set('page', String(filters.page));
  if (filters.limit) params.set('limit', String(filters.limit));
  if (filters.roles) params.set('roles', filters.roles);
  if (filters.search) params.set('search', filters.search);
  if (filters.sort) params.set('sort', filters.sort);

  const response = await fetchPrivateApi(`/users?${params.toString()}`);
  if (!response.ok) throw new Error(`Users request failed (${response.status})`);
  const data = (await response.json()) as UsersResponse;
  return data;
}
