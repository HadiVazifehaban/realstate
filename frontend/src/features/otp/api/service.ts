import { apiClient } from '@/lib/api-client';
import type { OtpAuditEntry, OtpRequest, OtpRequestResult, OtpStatus, OtpVerifyRequest, OtpVerifyResult } from './types';

export async function requestOtp(data: OtpRequest): Promise<OtpRequestResult> {
  const response = await apiClient<OtpRequestResult>('/v1/otp/request', {
    method: 'POST',
    body: JSON.stringify(data)
  });
  return response;
}

export async function verifyOtp(data: OtpVerifyRequest): Promise<OtpVerifyResult> {
  const response = await apiClient<OtpVerifyResult>('/v1/otp/verify', {
    method: 'POST',
    body: JSON.stringify(data)
  });
  return response;
}

export async function getOtpAuditTrail(mobile: string): Promise<OtpAuditEntry[]> {
  return apiClient<OtpAuditEntry[]>(`/v1/otp/audit/${mobile}`);
}

export async function getOtpStatus(mobile: string): Promise<OtpStatus> {
  return apiClient<OtpStatus>(`/v1/otp/status/${mobile}`);
}
