// ============================================================
// User Service — Data Access Layer
// ============================================================
// Talk to the FastAPI node through the browser, exactly like the
// CRM feature does. The service maps the node's envelope onto the
// `UsersResponse` shape the table already consumes; the table,
// prefetch and toolbar never change.
//
// Auth: the node expects a bearer identity, so every call carries
// the realm access token from the Auth.js session. The node
// re-verifies it against the realm's JWKS and re-derives role from
// the signed claims, which is what actually authorises the call.
// ============================================================

import { apiBaseUrl, networkFailureMessage } from '@/lib/api-base-url';
import type { UserFilters, UsersResponse, UserMutationPayload } from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (typeof window === 'undefined') {
    throw new Error('Use the server-only users API service during Server Component rendering.');
  }
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      cache: 'no-store',
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers
      }
    });
  } catch (error) {
    // Nothing was ever answered, so there is no status to report. Say that
    // plainly rather than surfacing `TypeError: Failed to fetch`, which reads
    // as a bug in the page instead of an unreachable node. Reachable during
    // SSR as well, hence the message rather than a browser-only assumption.
    throw new Error(networkFailureMessage(error));
  }

  if (!response.ok) {
    let message = `درخواست ناموفق بود (${response.status})`;
    try {
      const body = (await response.json()) as {
        detail?: string | { message?: string };
      };
      if (typeof body.detail === 'string') message = body.detail;
      else if (body.detail?.message) message = body.detail.message;
    } catch {
      // Keep the generic message.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export async function getUsers(filters: UserFilters): Promise<UsersResponse> {
  const params = new URLSearchParams();
  if (filters.page) params.set('page', String(filters.page));
  if (filters.limit) params.set('limit', String(filters.limit));
  if (filters.roles) params.set('roles', filters.roles);
  if (filters.search) params.set('search', filters.search);

  const data = await request<{
    success: boolean;
    time: string;
    message: string;
    total_users: number;
    offset: number;
    limit: number;
    users: UsersResponse['users'];
    role_breakdown: UsersResponse['role_breakdown'];
  }>(`/users?${params.toString()}`);

  return {
    success: data.success,
    time: data.time,
    message: data.message,
    total_users: data.total_users,
    offset: data.offset,
    limit: data.limit,
    users: data.users,
    role_breakdown: data.role_breakdown
  };
}

export async function createUser(data: UserMutationPayload) {
  return request('/users', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export async function updateUser(id: string, data: UserMutationPayload) {
  return request(`/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data)
  });
}

export async function deleteUser(id: string) {
  await request(`/users/${id}`, { method: 'DELETE' });
  return { success: true, message: 'کاربر غیرفعال شد' };
}
