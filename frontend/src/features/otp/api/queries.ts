import { queryOptions, useMutation, useQuery } from '@tanstack/react-query';
import { getOtpAuditTrail, getOtpStatus, requestOtp, verifyOtp } from './service';
import type { OtpAuditEntry, OtpRequest, OtpRequestResult, OtpStatus, OtpVerifyRequest, OtpVerifyResult } from './types';

export const otpKeys = {
  all: ['otp'] as const,
  status: (mobile: string) => [...otpKeys.all, 'status', mobile] as const,
  audit: (mobile: string) => [...otpKeys.all, 'audit', mobile] as const
};

export const otpStatusQueryOptions = (mobile: string) =>
  queryOptions({
    queryKey: otpKeys.status(mobile),
    queryFn: () => getOtpStatus(mobile),
    staleTime: 1000 * 60 * 5 // 5 minutes
  });

export const otpAuditQueryOptions = (mobile: string) =>
  queryOptions({
    queryKey: otpKeys.audit(mobile),
    queryFn: () => getOtpAuditTrail(mobile),
    staleTime: 1000 * 60 // 1 minute
  });

export const useOtpStatus = (mobile: string) => {
  return useQuery(otpStatusQueryOptions(mobile));
};

export const useOtpAuditTrail = (mobile: string) => {
  return useQuery(otpAuditQueryOptions(mobile));
};

export const useRequestOtp = () => {
  return useMutation({
    mutationFn: (data: OtpRequest) => requestOtp(data)
  });
};

export const useVerifyOtp = () => {
  return useMutation({
    mutationFn: (data: OtpVerifyRequest) => verifyOtp(data)
  });
};
