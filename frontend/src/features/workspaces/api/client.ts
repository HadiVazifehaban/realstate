/**
 * Client for the node's licence endpoint (`/api/v1/license`).
 *
 * Unlike the feature clients, this one does not *require* a session: the router
 * mounts `/license` without `API_GUARD`, because the office page has to be able
 * to say "this node has no licence" even while sign-in is failing. The realm
 * token is still attached when there is one, so a guarded deployment can add the
 * dependency later without touching this file.
 */

import { apiBaseUrl, networkFailureMessage } from '@/lib/api-base-url';
import { authHeaders } from '@/lib/auth/session';
import type { LicenseStatusResponse } from '../types';

export class WorkspacesApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'WorkspacesApiError';
    this.status = status;
  }
}

async function request<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json', ...(await authHeaders()) }
    });
  } catch (error) {
    throw new WorkspacesApiError(0, networkFailureMessage(error));
  }

  if (!response.ok) {
    let message = `دریافت وضعیت پروانه ناموفق بود (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string | { message?: string } };
      if (typeof body.detail === 'string') message = body.detail;
      else if (body.detail?.message) message = body.detail.message;
    } catch {
      // Keep the status-carrying fallback.
    }
    throw new WorkspacesApiError(response.status, message);
  }

  return (await response.json()) as T;
}

/** Current licence/office state of this node. */
export function fetchLicenseStatus(): Promise<LicenseStatusResponse> {
  return request<LicenseStatusResponse>('/license/status');
}
