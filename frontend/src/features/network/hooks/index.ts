'use client';

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult
} from '@tanstack/react-query';
import { toast } from 'sonner';

import {
  addDisputeMessage,
  approveCooperation,
  createCooperation,
  createDispute,
  createCommission,
  createReferral,
  createShare,
  createTransfer,
  extendShare,
  fetchAgencies,
  fetchAgency,
  fetchAudit,
  fetchCooperations,
  fetchCommission,
  fetchCommissions,
  fetchDispute,
  fetchDisputes,
  fetchNetworkOverview,
  fetchNetworkReports,
  fetchReferrals,
  fetchShare,
  fetchShares,
  fetchTransfers,
  lockCommission,
  recordPayment,
  rejectCooperation,
  revokeShare,
  updateDisputeStatus,
  updateReferralStage
} from '../api/client';
import type {
  Agency,
  AuditEvent,
  CommissionAgreement,
  CommissionAgreementDetail,
  CommissionCreate,
  Cooperation,
  CooperationCreate,
  CooperationDecision,
  Dispute,
  DisputeCreate,
  DisputeDetail,
  DisputeStatusUpdate,
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
} from '../types';

/** React-query keys, so a mutation can invalidate exactly what it changed. */
export const networkKeys = {
  all: () => ['network'] as const,
  agencies: () => [...networkKeys.all(), 'agencies'] as const,
  cooperations: (agencyId: string, params?: unknown) =>
    [...networkKeys.all(), 'cooperations', agencyId, params ?? {}] as const,
  shares: (params?: unknown) => [...networkKeys.all(), 'shares', params ?? {}] as const,
  share: (id: string) => [...networkKeys.all(), 'share', id] as const,
  referrals: (params?: unknown) => [...networkKeys.all(), 'referrals', params ?? {}] as const,
  transfers: (params?: unknown) => [...networkKeys.all(), 'transfers', params ?? {}] as const,
  commissions: (params?: unknown) => [...networkKeys.all(), 'commissions', params ?? {}] as const,
  commission: (id: string) => [...networkKeys.all(), 'commission', id] as const,
  disputes: (params?: unknown) => [...networkKeys.all(), 'disputes', params ?? {}] as const,
  dispute: (id: string) => [...networkKeys.all(), 'dispute', id] as const,
  audit: (params?: unknown) => [...networkKeys.all(), 'audit', params ?? {}] as const
};

// --------------------------------------------------------------------------- //
// Queries
// --------------------------------------------------------------------------- //

export function useAgencies(params: { q?: string; city?: string; status?: string } = {}) {
  return useQuery({
    queryKey: [...networkKeys.agencies(), params],
    queryFn: () => fetchAgencies(params)
  }) as UseQueryResult<Agency[], Error>;
}

export function useAgency(agencyId: string | null) {
  return useQuery({
    queryKey: [...networkKeys.agencies(), 'detail', agencyId ?? ''],
    queryFn: () => fetchAgency(agencyId as string),
    enabled: !!agencyId
  }) as UseQueryResult<Agency, Error>;
}

export function useCooperations(
  agencyId: string | null,
  params: { direction?: 'incoming' | 'outgoing' | 'any'; status?: string } = {}
) {
  return useQuery({
    queryKey: networkKeys.cooperations(agencyId ?? '', params),
    queryFn: () => fetchCooperations({ agency_id: agencyId as string, ...params }),
    enabled: !!agencyId
  }) as UseQueryResult<Cooperation[], Error>;
}

export function useShares(
  params: { agencyId?: string | null; direction?: 'incoming' | 'outgoing'; status?: string } = {}
) {
  return useQuery({
    queryKey: networkKeys.shares(params),
    queryFn: () => fetchShares(params)
  }) as UseQueryResult<Share[], Error>;
}

export function useShare(shareId: string | null) {
  return useQuery({
    queryKey: networkKeys.share(shareId ?? ''),
    queryFn: () => fetchShare(shareId as string),
    enabled: !!shareId
  }) as UseQueryResult<ShareDetail, Error>;
}

export function useReferrals(
  params: { agencyId?: string | null; direction?: 'incoming' | 'outgoing'; stage?: string } = {}
) {
  return useQuery({
    queryKey: networkKeys.referrals(params),
    queryFn: () => fetchReferrals(params)
  }) as UseQueryResult<Referral[], Error>;
}

export function useTransfers(params: { agencyId?: string | null; propertyId?: string } = {}) {
  return useQuery({
    queryKey: networkKeys.transfers(params),
    queryFn: () => fetchTransfers(params)
  }) as UseQueryResult<Transfer[], Error>;
}

export function useCommissions(params: { agencyId?: string | null; status?: string } = {}) {
  return useQuery({
    queryKey: networkKeys.commissions(params),
    queryFn: () => fetchCommissions(params)
  }) as UseQueryResult<CommissionAgreement[], Error>;
}

export function useCommission(agreementId: string | null) {
  return useQuery({
    queryKey: networkKeys.commission(agreementId ?? ''),
    queryFn: () => fetchCommission(agreementId as string),
    enabled: !!agreementId
  }) as UseQueryResult<CommissionAgreementDetail, Error>;
}

export function useDisputes(params: { agencyId?: string | null; status?: string } = {}) {
  return useQuery({
    queryKey: networkKeys.disputes(params),
    queryFn: () => fetchDisputes(params)
  }) as UseQueryResult<Dispute[], Error>;
}

export function useDispute(disputeId: string | null) {
  return useQuery({
    queryKey: networkKeys.dispute(disputeId ?? ''),
    queryFn: () => fetchDispute(disputeId as string),
    enabled: !!disputeId
  }) as UseQueryResult<DisputeDetail, Error>;
}

export function useAudit(
  params: { action?: string; agencyId?: string | null; propertyId?: string; limit?: number } = {}
) {
  return useQuery({
    queryKey: networkKeys.audit(params),
    queryFn: () => fetchAudit(params)
  }) as UseQueryResult<AuditEvent[], Error>;
}

export function useNetworkOverview(params: { agencyId?: string | null } = {}) {
  return useQuery({
    queryKey: [...networkKeys.all(), 'overview', params ?? {}],
    queryFn: () => fetchNetworkOverview(params)
  }) as UseQueryResult<NetworkOverview, Error>;
}

export function useNetworkReports(params: { agencyId?: string | null } = {}) {
  return useQuery({
    queryKey: [...networkKeys.all(), 'reports', params ?? {}],
    queryFn: () => fetchNetworkReports(params)
  }) as UseQueryResult<NetworkReports, Error>;
}

// --------------------------------------------------------------------------- //
// Mutations
// --------------------------------------------------------------------------- //

export function useCreateCooperation(): UseMutationResult<Cooperation, Error, CooperationCreate> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createCooperation,
    onSuccess: (_data, vars) => {
      toast.success('درخواست همکاری ارسال شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.cooperations(vars.requester_agency_id) });
    },
    onError: (error) => toast.error(error.message || 'ارسال درخواست همکاری ناموفق بود.')
  });
}

export function useDecideCooperation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      cooperationId,
      decision,
      payload
    }: {
      cooperationId: string;
      decision: 'approve' | 'reject';
      payload?: CooperationDecision;
      agencyId?: string;
    }) =>
      decision === 'approve'
        ? approveCooperation(cooperationId, payload)
        : rejectCooperation(cooperationId, payload),
    onSuccess: (_data, vars) => {
      toast.success(vars.decision === 'approve' ? 'درخواست همکاری پذیرفته شد.' : 'درخواست همکاری رد شد.');
      void queryClient.invalidateQueries({ queryKey: [...networkKeys.all(), 'cooperations'] });
    },
    onError: (error) => toast.error(error.message || 'ثبت تصمیم ناموفق بود.')
  });
}

export function useCreateShare(): UseMutationResult<ShareDetail, Error, ShareCreate> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createShare,
    onSuccess: () => {
      toast.success('اشتراک فایل ایجاد شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.all() });
    },
    onError: (error) => toast.error(error.message || 'ایجاد اشتراک ناموفق بود.')
  });
}

export function useRevokeShare(): UseMutationResult<Share, Error, { shareId: string }> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ shareId }: { shareId: string }) => revokeShare(shareId),
    onSuccess: () => {
      toast.success('اشتراک لغو شد و دسترسی بی‌درنگ بسته شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.all() });
    },
    onError: (error) => toast.error(error.message || 'لغو اشتراک ناموفق بود.')
  });
}

export function useExtendShare(): UseMutationResult<Share, Error, { shareId: string; days: number }> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ shareId, days }: { shareId: string; days: number }) => extendShare(shareId, days),
    onSuccess: () => {
      toast.success('مهلت اشتراک تمدید شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.all() });
    },
    onError: (error) => toast.error(error.message || 'تمدید اشتراک ناموفق بود.')
  });
}

export function useCreateReferral(): UseMutationResult<Referral, Error, ReferralCreate> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createReferral,
    onSuccess: () => {
      toast.success('ارجاع مشتری ثبت شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.all() });
    },
    onError: (error) => toast.error(error.message || 'ثبت ارجاع ناموفق بود.')
  });
}

export function useUpdateReferralStage(): UseMutationResult<
  Referral,
  Error,
  { referralId: string; payload: ReferralStageUpdate }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ referralId, payload }: { referralId: string; payload: ReferralStageUpdate }) =>
      updateReferralStage(referralId, payload),
    onSuccess: () => {
      toast.success('مرحلهٔ ارجاع به‌روزرسانی شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.all() });
    },
    onError: (error) => toast.error(error.message || 'تغییر مرحلهٔ ارجاع ناموفق بود.')
  });
}

export function useCreateTransfer(): UseMutationResult<Transfer, Error, TransferCreate> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createTransfer,
    onSuccess: () => {
      toast.success('انتقال فایل ثبت شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.all() });
    },
    onError: (error) => toast.error(error.message || 'ثبت انتقال ناموفق بود.')
  });
}


export function useCreateCommission(): UseMutationResult<
  CommissionAgreementDetail,
  Error,
  CommissionCreate
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createCommission,
    onSuccess: () => {
      toast.success('توافق پورسانت ایجاد شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.all() });
    },
    onError: (error) => toast.error(error.message || 'ایجاد توافق پورسانت ناموفق بود.')
  });
}

export function useLockCommission(): UseMutationResult<
  CommissionAgreement,
  Error,
  { agreementId: string }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ agreementId }: { agreementId: string }) => lockCommission(agreementId),
    onSuccess: () => {
      toast.success('توافق پورسانت قفل شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.all() });
    },
    onError: (error) => toast.error(error.message || 'قفل کردن پورسانت ناموفق بود.')
  });
}

export function useRecordPayment(): UseMutationResult<Payment, Error, PaymentCreate> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: recordPayment,
    onSuccess: () => {
      toast.success('پرداخت ثبت شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.all() });
    },
    onError: (error) => toast.error(error.message || 'ثبت پرداخت ناموفق بود.')
  });
}

export function useCreateDispute(): UseMutationResult<Dispute, Error, DisputeCreate> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createDispute,
    onSuccess: () => {
      toast.success('اختلاف ثبت شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.all() });
    },
    onError: (error) => toast.error(error.message || 'ثبت اختلاف ناموفق بود.')
  });
}

export function useAddDisputeMessage(): UseMutationResult<
  unknown,
  Error,
  { disputeId: string; body: string; isInternal?: boolean }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      disputeId,
      body,
      isInternal
    }: {
      disputeId: string;
      body: string;
      isInternal?: boolean;
    }) => addDisputeMessage(disputeId, { body, is_internal: isInternal }),
    onSuccess: (_data, vars) => {
      toast.success('پیام ثبت شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.dispute(vars.disputeId) });
    },
    onError: (error) => toast.error(error.message || 'ثبت پیام ناموفق بود.')
  });
}

export function useUpdateDisputeStatus(): UseMutationResult<
  Dispute,
  Error,
  { disputeId: string; payload: DisputeStatusUpdate }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ disputeId, payload }: { disputeId: string; payload: DisputeStatusUpdate }) =>
      updateDisputeStatus(disputeId, payload),
    onSuccess: () => {
      toast.success('وضعیت اختلاف به‌روزرسانی شد.');
      void queryClient.invalidateQueries({ queryKey: networkKeys.all() });
    },
    onError: (error) => toast.error(error.message || 'تغییر وضعیت اختلاف ناموفق بود.')
  });
}

