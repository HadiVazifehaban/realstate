import { handlers } from '@/lib/auth/config';

// Keep Auth.js's built-in CSRF-protected POST endpoint for local sign-out.
export const POST = handlers.POST;
