import { apiClient } from '@/lib/api-client';

/**
 * The SHEKARCHI public front door. `POST /auth/*` and `GET /registration/*` are
 * mounted WITHOUT the bearer gate, so a brand-new sign-up validates + redeems a
 * mobile OTP and never touches an identity token. Server-side enforcement lives
 * in `registration_service` and the OTP store.
 */

/** `POST /auth/otp/request` */
export interface OtpRequestIn {
  mobile: string;
}

export interface OtpRequestOut {
  ok: boolean;
  message: string;
  retry_after: number;
}

export interface OtpVerifyIn {
  mobile: string;
  otp_code: string;
}

export interface OtpVerifyOut {
  ok: boolean;
  message: string;
  registration_token: string;
  has_account: boolean;
}

/** `POST /auth/quick-register` */
export interface QuickRegisterIn {
  registration_token: string;
}

export interface QuickRegisterOut {
  ok: boolean;
  message: string;
  user_id: string;
  mobile: string;
  first_name: string;
  last_name: string;
  roles: string[];
}

/** `POST /auth/professional-registration/{track}` */
export interface ProfessionalRegistrationOut {
  ok: boolean;
  message: string;
  application_id: string;
  status: string;
}

/** `GET /auth/registration-status` */
export interface RegistrationStatusOut {
  mobile_verified: boolean;
  has_account: boolean;
  application_status: string;
  requested_role: string;
}

/** `POST /auth/session` */
export interface SessionExchangeIn {
  registration_token: string;
}

export interface SessionOut {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
  test_mode: boolean;
}

/** `GET /registration/cities` */
export interface RegistrationCitiesOut {
  ok: boolean;
  provinces: string[];
  cities: string[];
}

/** `GET /registration/roles` */
export interface RegistrationRolesOut {
  ok: boolean;
  roles: { name: string; label: string }[];
}

export const api = {
  /** POST /auth/otp/request */
  async requestOtp({ mobile }: OtpRequestIn): Promise<OtpRequestOut> {
    return apiClient<OtpRequestOut>('/auth/otp/request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mobile }),
    });
  },

  /** POST /auth/otp/verify */
  async verifyOtp({
    mobile,
    otp_code,
  }: OtpVerifyIn): Promise<OtpVerifyOut> {
    return apiClient<OtpVerifyOut>('/auth/otp/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mobile, otp_code }),
    });
  },

  /** POST /auth/quick-register */
  async quickRegister({
    registration_token,
  }: QuickRegisterIn): Promise<QuickRegisterOut> {
    return apiClient<QuickRegisterOut>('/auth/quick-register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ registration_token }),
    });
  },

  /** POST /auth/session */
  async exchangeSession({
    registration_token,
  }: SessionExchangeIn): Promise<SessionOut> {
    return apiClient<SessionOut>('/auth/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ registration_token }),
    });
  },

  /** POST /auth/professional-registration/{track} */
  async submitProfessionalRegistration(
    track: string,
    body: Record<string, unknown>,
  ): Promise<ProfessionalRegistrationOut> {
    return apiClient<ProfessionalRegistrationOut>(
      `/auth/professional-registration/${encodeURIComponent(track)}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      },
    );
  },

  /** GET /auth/registration-status?mobile= */
  async getRegistrationStatus(mobile: string): Promise<RegistrationStatusOut> {
    const url = new URL('/auth/registration-status', window.location.origin);
    url.searchParams.set('mobile', mobile);
    const res = await fetch(url.toString(), { cache: 'no-store' });
    if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
    return (await res.json()) as Promise<RegistrationStatusOut>;
  },

  /** GET /registration/cities */
  async getCities(): Promise<RegistrationCitiesOut> {
    return apiClient<RegistrationCitiesOut>('/registration/cities');
  },

  /** GET /registration/roles */
  async getRoles(): Promise<RegistrationRolesOut> {
    return apiClient<RegistrationRolesOut>('/registration/roles');
  },
};
