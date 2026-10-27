import { apiBaseUrl, networkFailureMessage } from '@/lib/api-base-url';

export type PendingAgency = {
  id: string;
  slug: string;
  name: string;
  name_fa: string;
  city: string;
  district: string;
  phone: string;
  description: string;
  status: string;
  created_at: string;
};

export type ProfessionalApplication = {
  id: string;
  mobile: string;
  requested_role: string;
  assigned_role: string;
  first_name: string;
  last_name: string;
  email: string;
  payload: Record<string, unknown>;
  status: string;
  reviewer_note: string;
  created_at: string | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      cache: 'no-store',
      credentials: 'same-origin',
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers }
    });
  } catch (error) {
    throw new Error(networkFailureMessage(error));
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(
      typeof detail === 'string' ? detail : detail?.message ?? `درخواست ناموفق بود (${response.status})`
    );
  }
  return response.json() as Promise<T>;
}

export function fetchPendingAgencies() {
  return request<PendingAgency[]>('/network/agencies?status=PENDING&limit=200');
}

export function reviewAgency(id: string, decision: 'APPROVE' | 'REJECT', reason = '') {
  return request<PendingAgency>(`/network/agencies/${encodeURIComponent(id)}/review`, {
    method: 'POST',
    body: JSON.stringify({ decision, reason })
  });
}

export function fetchApplications() {
  return request<{ ok: boolean; total: number; items: ProfessionalApplication[] }>(
    '/auth/applications?status=ROLE_REVIEW_PENDING&limit=200'
  );
}

export function approveApplication(id: string) {
  return request<{ ok: boolean; status: string }>(
    `/auth/applications/${encodeURIComponent(id)}/approve`, { method: 'POST' }
  );
}

export function rejectApplication(id: string, note: string) {
  return request<{ ok: boolean; status: string }>(
    `/auth/applications/${encodeURIComponent(id)}/reject`, {
      method: 'POST',
      body: JSON.stringify({ note })
    }
  );
}

export type DirectoryUser = {
  id: string;
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  enabled: boolean;
  realmRoles: string[];
};

export function fetchDirectoryUsers() {
  return request<{ users: DirectoryUser[] }>('/admin/users');
}

export function approveDirectoryUser(userId: string) {
  return request<{ message: string }>('/admin/users/approve', {
    method: 'POST', body: JSON.stringify({ userId })
  });
}