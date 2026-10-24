'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  addInteraction,
  createLead,
  fetchBoardStats,
  deleteLead,
  fetchLead,
  fetchLeads,
  fetchQuota,
  moveLead,
  revealContact
} from '../api/client';
import type { Actor, InteractionRequest, LeadStage, StageChangeRequest } from '../types';
import { LEAD_STAGE_LABELS } from '../types';

export interface LeadFilters {
  stages?: LeadStage[];
  bargainsOnly?: boolean;
  limit?: number;
}

const CRM_PREFIX = 'crm';

/** Board feed. `refetchInterval` keeps the desk live ahead of a WebSocket hub. */
export function useLeads(filters: LeadFilters = {}, actor?: Actor) {
  return useQuery({
    queryKey: [CRM_PREFIX, 'leads', filters, actor?.role, actor?.tier],
    queryFn: () => fetchLeads(filters, actor),
    refetchInterval: 30_000,
    staleTime: 15_000
  });
}

/**
 * Board header totals. Kept on the same cadence as the card feed so the strip
 * and the columns refresh together — a header that lags the board reads as a
 * bug even when both are technically correct.
 */
export function useBoardStats(actor?: Actor) {
  return useQuery({
    queryKey: [CRM_PREFIX, 'board-stats', actor?.role, actor?.tier],
    queryFn: () => fetchBoardStats(actor),
    refetchInterval: 30_000,
    staleTime: 15_000
  });
}

export function useLead(leadId: string, actor?: Actor) {
  return useQuery({
    queryKey: [CRM_PREFIX, 'lead', leadId],
    queryFn: () => fetchLead(leadId, actor),
    enabled: !!leadId
  });
}

export function useQuota(actor?: Actor) {
  return useQuery({
    queryKey: [CRM_PREFIX, 'pii-quota', actor?.role, actor?.tier],
    queryFn: () => fetchQuota(actor),
    staleTime: 60_000
  });
}

/**
 * Move a card between columns.
 *
 * The board refuses illegal drops before calling this, so a 409 here means the
 * client's transition table drifted from the server — worth surfacing as a
 * distinct error rather than a generic toast.
 */
export function useMoveLead(actor?: Actor) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ leadId, payload }: { leadId: string; payload: StageChangeRequest }) =>
      moveLead(leadId, payload, actor),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: [CRM_PREFIX, 'leads'] });
      void queryClient.invalidateQueries({ queryKey: [CRM_PREFIX, 'lead'] });
      // The card lands optimistically, so without this the board looks frozen
      // even on success and the broker cannot tell a saved move from a no-op.
      toast.success(
        `لید به مرحلهٔ «${LEAD_STAGE_LABELS[result.lead.stage]}» منتقل شد.`
      );
    },
    onError: (error: Error) => {
      toast.error(error.message || 'انتقال مرحله ناموفق بود.');
    }
  });
}

/**
 * Put a listing on the desk.
 *
 * `created=false` means the card was already there — the toast says so instead
 * of claiming a new lead, because a board that counts phantom additions stops
 * being trustworthy.
 */
export function useCreateLead(actor?: Actor) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (propertyId: string) => createLead(propertyId, actor),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: [CRM_PREFIX, 'leads'] });
      toast.success(
        result.created ? 'لید به تخته اضافه شد.' : 'این ملک از قبل روی تخته بود.'
      );
    },
    onError: (error: Error) => {
      toast.error(error.message || 'افزودن لید ناموفق بود.');
    }
  });
}

/**
 * Erase a lead permanently.
 *
 * No undo: the timeline is gone once this lands, so the UI gates it behind an
 * explicit confirmation and points the broker at LOST_ARCHIVED first.
 */
export function useDeleteLead(actor?: Actor) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (leadId: string) => deleteLead(leadId, actor),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: [CRM_PREFIX, 'leads'] });
      void queryClient.invalidateQueries({ queryKey: [CRM_PREFIX, 'lead'] });
      toast.success(
        result.deleted_interactions > 0
          ? `لید و ${result.deleted_interactions} رویداد آن حذف شد.`
          : 'لید حذف شد.'
      );
    },
    onError: (error: Error) => {
      toast.error(error.message || 'حذف لید ناموفق بود.');
    }
  });
}

export function useAddInteraction(actor?: Actor) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ leadId, payload }: { leadId: string; payload: InteractionRequest }) =>
      addInteraction(leadId, payload, actor),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [CRM_PREFIX, 'leads'] });
      void queryClient.invalidateQueries({ queryKey: [CRM_PREFIX, 'lead'] });
      toast.success('رویداد در تایم‌لاین ثبت شد.');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'ثبت رویداد ناموفق بود.');
    }
  });
}

/**
 * Spend one unit of daily quota to reveal an owner phone.
 *
 * On success the revealed number is returned to the caller only — it is never
 * put into the query cache, so it cannot be replayed from a persisted store.
 */
export function useRevealContact(actor?: Actor) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ propertyId, reason }: { propertyId: string; reason: string }) =>
      revealContact(propertyId, reason, actor),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [CRM_PREFIX, 'pii-quota'] });
    },
    onError: (error: Error) => {
      toast.error(error.message || 'رمزگشایی اطلاعات تماس انجام نشد.');
    }
  });
}
