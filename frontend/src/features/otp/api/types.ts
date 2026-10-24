export interface OtpRequest {
  mobile: string;
  purpose?: 'login' | 'register';
}

export interface OtpRequestResult {
  ok: boolean;
  retry_after: number;
  message_id: string;
  dev_code?: string;
}

export interface OtpVerifyRequest {
  mobile: string;
  code: string;
}

export interface OtpVerifyResult {
  ok: boolean;
  registration_token?: string;
  reason: string;
}

export interface OtpAuditEntry {
  ts: number;
  mobile: string;
  event: string;
}

export interface OtpStatus {
  mobile: string;
  is_verified: boolean;
  verified_at?: number;
}
