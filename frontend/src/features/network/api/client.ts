/**
 * Client for the inter-agency collaboration endpoints (Phases 2-5).
 *
 * Same contract as the CRM client: every call carries the realm access token
 * from the Auth.js session; the FastAPI node re-verifies it and re-derives the
 * caller's agency/roles from the signed claims. Nothing here caches a revealed
 * phone or address -- a reveal is a one-shot, audited read, never a toggle.
 *
 * The masking rule from the spec lives server-side (owner phone and exact
 * address default to OFF on a share), so this client only ever *requests* the
 * reveal; it cannot grant itself one.
 */

import { apiBaseUrl, networkFailureMessage } from "@/lib/api-base-url";
import { authHeaders } from "@/lib/auth/session";
import type {
  Agency,
  Cooperation,
  CooperationCreate,
  CooperationDecision,
  CommissionAgreement,
  CommissionAgreementDetail,
  CommissionCreate,
  Dispute,
  DisputeCreate,
  DisputeDetail,
  DisputeMessage,
  DisputeMessageCreate,
  DisputeStatusUpdate,
  AuditEvent,
  NetworkOverview,
  NetworkReports,
  Payment,
  PaymentCreate,
  Referral,
  ReferralCreate,
  ReferralStageUpdate,
  Share,
  ShareCreate,
  ShareDetail,
  Transfer,
  TransferCreate
} from "../types";

export class NetworkApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "NetworkApiError";
    this.status = status;
    this.code = code;
  }
}

export type Workspace = {
  id: string;
  slug: string;
  name: string;
  name_fa: string;
  status: string;
  role: string;
};

const WORKSPACE_STORAGE_KEY = "shekarchi.active-workspace";
let workspaceHeaderOverride: string | null | undefined;

export function getActiveWorkspaceId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(WORKSPACE_STORAGE_KEY);
}

export function setActiveWorkspaceId(id: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(WORKSPACE_STORAGE_KEY, id);
  window.dispatchEvent(new Event("shekarchi:workspace-changed"));
}

export function clearActiveWorkspaceId(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(WORKSPACE_STORAGE_KEY);
  window.dispatchEvent(new Event("shekarchi:workspace-changed"));
}

export function setWorkspaceHeaderOverride(id: string | null): void {
  workspaceHeaderOverride = id;
}

export function getWorkspaceHeaderOverride(): string | null | undefined {
  return workspaceHeaderOverride;
}

function selectedWorkspaceId(): string | null {
  return workspaceHeaderOverride === undefined ? getActiveWorkspaceId() : workspaceHeaderOverride;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      cache: "no-store",
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(await authHeaders()),
        ...(selectedWorkspaceId() ? { "X-Workspace-ID": selectedWorkspaceId() as string } : {}),
        ...options.headers
      }
    });
  } catch (error) {
    throw new NetworkApiError(0, "network_unreachable", networkFailureMessage(error));
  }

  if (!response.ok) {
    let code = "request_failed";
    let message = response.statusText || "درخواست ناموفق بود.";
    try {
      const body = (await response.json()) as {
        detail?: { error?: string; message?: string } | string;
      };
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (body.detail) {
        code = body.detail.error ?? code;
        message = body.detail.message ?? message;
      }
    } catch {
      // Non-JSON error body -- keep the fallback message.
    }
    throw new NetworkApiError(response.status, code, message);
  }

  return (await response.json()) as T;
}

const qs = (params: Record<string, string | number | null | undefined>): string => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
};

// --------------------------------------------------------------------------- //
// Partner offices & cooperation requests (Phase 1)
// --------------------------------------------------------------------------- //
export function fetchAgencies(params: { q?: string; city?: string; status?: string } = {}) {
  return request<Agency[]>(`/network/agencies${qs(params)}`);
}

export function fetchWorkspaces() {
  return request<Workspace[]>("/network/workspaces");
}

export function createWorkspace(payload: {
  slug: string;
  name: string;
  name_fa?: string;
  city?: string;
  district?: string;
  phone?: string;
  description?: string;
  referral_code?: string;
}) {
  return request<Workspace>("/network/workspaces", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function fetchAgency(agencyId: string) {
  return request<Agency>(`/network/agencies/${agencyId}`);
}

export function fetchCooperations(
  params: {
    agency_id: string;
    direction?: "incoming" | "outgoing" | "any";
    status?: string;
    limit?: number;
    offset?: number;
  } = { agency_id: "" }
) {
  return request<Cooperation[]>(`/network/cooperations${qs(params)}`);
}

export function createCooperation(payload: CooperationCreate) {
  return request<Cooperation>("/network/cooperations", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function approveCooperation(cooperationId: string, payload: CooperationDecision = {}) {
  return request<Cooperation>(`/network/cooperations/${cooperationId}/approve`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function rejectCooperation(cooperationId: string, payload: CooperationDecision = {}) {
  return request<Cooperation>(`/network/cooperations/${cooperationId}/reject`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// --------------------------------------------------------------------------- //
// Shares
// --------------------------------------------------------------------------- //
export function fetchShares(
  params: {
    agencyId?: string | null;
    direction?: "incoming" | "outgoing";
    status?: string;
    limit?: number;
    offset?: number;
  } = {}
) {
  const { agencyId, ...query } = params;
  return request<Share[]>(`/network/shares${qs({ ...query, agency_id: agencyId })}`);
}

export function fetchShare(shareId: string) {
  return request<ShareDetail>(`/network/shares/${shareId}`);
}

export function createShare(payload: ShareCreate) {
  return request<ShareDetail>("/network/shares", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function revokeShare(shareId: string) {
  return request<Share>(`/network/shares/${shareId}/revoke`, { method: "POST" });
}

export function extendShare(shareId: string, days: number) {
  return request<Share>(`/network/shares/${shareId}/extend${qs({ days })}`, {
    method: "POST"
  });
}

// --------------------------------------------------------------------------- //
// Referrals
// --------------------------------------------------------------------------- //
export function fetchReferrals(
  params: {
    agencyId?: string | null;
    direction?: "incoming" | "outgoing";
    stage?: string;
  } = {}
) {
  return request<Referral[]>(`/network/referrals${qs(params)}`);
}

export function createReferral(payload: ReferralCreate) {
  return request<Referral>("/network/referrals", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateReferralStage(referralId: string, payload: ReferralStageUpdate) {
  return request<Referral>(`/network/referrals/${referralId}/stage`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

// --------------------------------------------------------------------------- //
// Transfers
// --------------------------------------------------------------------------- //
export function fetchTransfers(
  params: {
    propertyId?: string;
    agencyId?: string | null;
  } = {}
) {
  return request<Transfer[]>(`/network/transfers${qs(params)}`);
}

export function createTransfer(payload: TransferCreate) {
  return request<Transfer>("/network/transfers", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// --------------------------------------------------------------------------- //
// Commissions
// --------------------------------------------------------------------------- //
export function fetchCommissions(
  params: {
    agencyId?: string | null;
    status?: string;
  } = {}
) {
  return request<CommissionAgreement[]>(`/network/commissions${qs(params)}`);
}

export function fetchCommission(agreementId: string) {
  return request<CommissionAgreementDetail>(`/network/commissions/${agreementId}`);
}

export function createCommission(payload: CommissionCreate) {
  return request<CommissionAgreementDetail>("/network/commissions", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function lockCommission(agreementId: string) {
  return request<CommissionAgreement>(`/network/commissions/${agreementId}/lock`, {
    method: "POST"
  });
}

export function recordPayment(payload: PaymentCreate) {
  return request<Payment>("/network/commissions/payments", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// --------------------------------------------------------------------------- //
// Disputes
// --------------------------------------------------------------------------- //
export function fetchDisputes(
  params: {
    agencyId?: string | null;
    status?: string;
  } = {}
) {
  return request<Dispute[]>(`/network/disputes${qs(params)}`);
}

export function fetchDispute(disputeId: string) {
  return request<DisputeDetail>(`/network/disputes/${disputeId}`);
}

export function createDispute(payload: DisputeCreate) {
  return request<Dispute>("/network/disputes", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function addDisputeMessage(disputeId: string, payload: DisputeMessageCreate) {
  return request<DisputeMessage>(`/network/disputes/${disputeId}/messages`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateDisputeStatus(disputeId: string, payload: DisputeStatusUpdate) {
  return request<Dispute>(`/network/disputes/${disputeId}/status`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// --------------------------------------------------------------------------- //
// Audit
// --------------------------------------------------------------------------- //
export function fetchAudit(
  params: {
    action?: string;
    agencyId?: string | null;
    propertyId?: string;
    limit?: number;
  } = {}
) {
  return request<AuditEvent[]>(`/network/audit${qs(params)}`);
}

export function fetchNetworkOverview(params: { agencyId?: string | null } = {}) {
  return request<NetworkOverview>(`/network/overview${qs({ agency_id: params.agencyId })}`);
}

export function fetchNetworkReports(params: { agencyId?: string | null } = {}) {
  return request<NetworkReports>(`/network/reports${qs({ agency_id: params.agencyId })}`);
}
