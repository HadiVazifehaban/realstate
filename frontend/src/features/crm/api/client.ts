/**
 * Client for the Phase 5 CRM + PII-vault endpoints.
 *
 * Every call carries the realm access token from the Auth.js session. The FastAPI
 * node re-verifies it against the realm's JWKS and re-derives role, tier and KYC
 * from the signed claims — that is what authorises the call and what the
 * `API_GUARD` and PII vault enforce. The `X-User-Role` / `X-SaaS-Tier` headers
 * are a UI hint only; a caller cannot escalate by setting them.
 *
 * Nothing here caches a plaintext phone: `revealContact` returns it once, to the
 * caller that asked for it, and it is never written to storage.
 */

import { apiBaseUrl, networkFailureMessage } from '@/lib/api-base-url';
import { authHeaders } from '@/lib/auth/session';
import type {
  Actor,
  BoardStats,
  Interaction,
  InteractionRequest,
  LeadCreateResponse,
  LeadDetail,
  LeadListResponse,
  LeadStage,
  PiiAccessLogEntry,
  PiiReveal,
  QuotaStatus,
  StageChangeRequest
} from '../types';

export class CrmApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'CrmApiError';
    this.status = status;
    this.code = code;
  }
}

function actorHeaders(actor: Actor = {}): Record<string, string> {
  const headers: Record<string, string> = {};
  if (actor.role) headers['X-User-Role'] = actor.role;
  if (actor.tier) headers['X-SaaS-Tier'] = actor.tier;
  return headers;
}

async function request<T>(path: string, options: RequestInit & { actor?: Actor } = {}): Promise<T> {
  const { actor, ...init } = options;
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      cache: 'no-store',
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(await authHeaders()),
        ...actorHeaders(actor),
        ...init.headers
      }
    });
  } catch (error) {
    // No response was ever received -- unreachable host, refused connection or
    // a blocked preflight. Report it as the transport failure it is instead of
    // letting the bare `TypeError: Failed to fetch` reach the board as an
    // unexplained query error.
    throw new CrmApiError(0, 'network_unreachable', networkFailureMessage(error));
  }

  if (!response.ok) {
    let code = 'request_failed';
    let message = response.statusText || 'درخواست ناموفق بود.';
    try {
      const body = (await response.json()) as {
        detail?: { error?: string; message?: string } | string;
      };
      if (typeof body.detail === 'string') {
        message = body.detail;
      } else if (body.detail) {
        code = body.detail.error ?? code;
        message = body.detail.message ?? message;
      }
    } catch {
      // Non-JSON error body (e.g. a gateway page) — keep the fallback.
    }
    throw new CrmApiError(response.status, code, message);
  }

  return (await response.json()) as T;
}

export function fetchLeads(
  filters: { stages?: LeadStage[]; bargainsOnly?: boolean; limit?: number } = {},
  actor?: Actor
): Promise<LeadListResponse> {
  const search = new URLSearchParams();
  filters.stages?.forEach((stage) => search.append('stage', stage));
  if (filters.bargainsOnly) search.set('bargains_only', 'true');
  if (filters.limit) search.set('limit', String(filters.limit));
  const query = search.toString();
  return request<LeadListResponse>(`/crm/leads${query ? `?${query}` : ''}`, { actor });
}

/**
 * Desk totals for the header strip.
 *
 * Aggregated server-side over every lead, so the numbers describe the whole
 * pipeline rather than the cards currently on screen.
 */
export function fetchBoardStats(actor?: Actor): Promise<BoardStats> {
  return request<BoardStats>('/crm/board/stats', { actor });
}

export function fetchLead(leadId: string, actor?: Actor): Promise<LeadDetail> {
  return request<LeadDetail>(`/crm/leads/${leadId}`, { actor });
}

/** Result of permanently removing a lead and its timeline. */
export interface LeadDeleteResponse {
  lead_id: string;
  deleted_interactions: number;
}

/**
 * Erase a lead and its timeline for good.
 *
 * `POST .../delete` rather than `DELETE`: the endpoint requires a `confirm`
 * flag, and a body-bearing DELETE is dropped by some proxies. Prefer moving the
 * card to LOST_ARCHIVED, which is reversible.
 */
export function deleteLead(
  leadId: string,
  actor?: Actor
): Promise<LeadDeleteResponse> {
  return request<LeadDeleteResponse>(`/crm/leads/${leadId}/delete`, {
    method: 'POST',
    body: JSON.stringify({ confirm: true }),
    actor
  });
}

/**
 * Put a listing on the desk.
 *
 * Idempotent per property: the server returns the existing card with
 * `created=false` rather than stacking a duplicate, so the UI can treat a
 * double-click as a no-op instead of showing an error.
 */
export function createLead(
  propertyId: string,
  actor?: Actor
): Promise<LeadCreateResponse> {
  return request<LeadCreateResponse>('/crm/leads', {
    method: 'POST',
    body: JSON.stringify({ property_id: propertyId }),
    actor
  });
}

export function moveLead(
  leadId: string,
  payload: StageChangeRequest,
  actor?: Actor
): Promise<LeadDetail> {
  return request<LeadDetail>(`/crm/leads/${leadId}/stage`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
    actor
  });
}

export function addInteraction(
  leadId: string,
  payload: InteractionRequest,
  actor?: Actor
): Promise<Interaction> {
  return request<Interaction>(`/crm/leads/${leadId}/events`, {
    method: 'POST',
    body: JSON.stringify(payload),
    actor
  });
}

export function fetchQuota(actor?: Actor): Promise<QuotaStatus> {
  return request<QuotaStatus>('/crm/pii/quota', { actor });
}

/**
 * Read the owner-PII access trail. The server gates this to SUPERVISOR/ADMIN and
 * answers 403 otherwise, so callers must render the refusal rather than assume
 * an empty log means 'no access happened'.
 */
export function fetchPiiAudit(limit = 100, actor?: Actor): Promise<PiiAccessLogEntry[]> {
  return request<PiiAccessLogEntry[]>(`/crm/pii/audit?limit=${limit}`, { actor });
}

/**
 * Reveal the owner phone. This spends quota and writes an audit row — the UI
 * treats the button as a deliberate, accounted-for action, not a toggle.
 */
export function revealContact(
  propertyId: string,
  reason: string,
  actor?: Actor
): Promise<PiiReveal> {
  return request<PiiReveal>(`/crm/properties/${propertyId}/reveal-contact`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
    actor
  });
}
