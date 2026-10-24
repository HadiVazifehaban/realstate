import type { DefaultSession } from 'next-auth';

/**
 * TypeScript augmentation for the Auth.js session.
 *
 * Access/refresh/ID tokens stay exclusively inside the encrypted Auth.js JWT
 * cookie and are read by server-only code. The browser receives only the
 * non-secret claims needed to render navigation and approval hints.
 */
declare module 'next-auth' {
  interface Session {
    accessTokenExpiresAt?: number;
    authError?: boolean;
    user: DefaultSession['user'] & {
      id?: string;
      roles?: string[];
      kycStatus?: string;
      tenantId?: string;
      saasTier?: string;
      dailyPiiQuota?: number;
      mobileVerified?: boolean;
      phoneNumber?: string;
    };
  }

  interface JWT {
    /** Credentials are encrypted in the HttpOnly Auth.js session cookie. */
    accessToken?: string;
    idToken?: string;
    refreshToken?: string;
    /** Unix seconds at which the realm token expires (from `account.expires_at`). */
    expiresAt?: number;
    roles?: string[];
    kycStatus?: string;
    tenantId?: string;
    saasTier?: string;
    dailyPiiQuota?: number;
    mobileVerified?: boolean;
    phoneNumber?: string;
    displayName?: string;
    emailAddress?: string;
    imageUrl?: string;
    error?: string;
  }
}
