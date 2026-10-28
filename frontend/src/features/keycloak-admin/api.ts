import { apiBaseUrl, networkFailureMessage } from '@/lib/api-base-url';

export type KeycloakItem = Record<string, string | number | boolean | null | string[]>;
export type KeycloakList = { items: KeycloakItem[]; count?: number; limit?: number; truncated?: boolean };

class KeycloakApiError extends Error {
  constructor(message: string, readonly status: number, readonly code?: string) {
    super(message);
    this.name = 'KeycloakApiError';
  }
}

async function request<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/admin/keycloak${path}`, {
      cache: 'no-store', credentials: 'same-origin', headers: { Accept: 'application/json' }
    });
  } catch (error) {
    throw new Error(networkFailureMessage(error));
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: { error?: string; message?: string } } | null;
    const detail = body?.detail;
    throw new KeycloakApiError(detail?.message ?? detail?.error ?? `درخواست ناموفق بود (${response.status})`, response.status, detail?.error);
  }
  return response.json() as Promise<T>;
}

export function fetchKeycloakDashboard() {
  return request<{ realm: string; metrics: Record<string, number | null>; adminPermissions: { systemRole: string; realmManagementRoles: string[] } }>('/dashboard');
}

export function fetchKeycloakConfig() {
  return request<{ realm: string }>('/config');
}

export function fetchKeycloakResource(realm: string, resource: string, first = 0, max = 25, search = '') {
  const query = new URLSearchParams({ first: String(first), max: String(max) });
  if (search.trim()) query.set('search', search.trim());
  return request<KeycloakList>(`/realms/${encodeURIComponent(realm)}/${resource}?${query}`);
}