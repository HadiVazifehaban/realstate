import * as z from 'zod';
import { ROLE_VALUES, USER_STATUSES, type UserRole } from '../constants/roles';

/** Convert Persian/Arabic digits to Latin for phone validation. */
export function toLatinDigits(value: string): string {
  return value
    .replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)));
}

/** Canonical phone shape the backend expects: 11 Latin digits starting 09. */
export function normalizePhone(value: string): string {
  return toLatinDigits(value.trim().replace(/[\s-]/g, ''));
}

export function normalizeEmail(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed === '' ? undefined : trimmed;
}

// Zod v4: `z.enum` takes the tuple directly and custom messages via `error`.
//
// NOTE: validate-only, no `.transform()` / `.pipe()` here. TanStack Form runs
// this schema against the live field values; a transform would make the
// schema's output type differ from its input type and the form engine would
// keep the *transformed* value internally, silently desyncing the visible
// inputs. Normalisation happens explicitly in the submit handler instead.
export const userSchema = z.object({
  first_name: z.string().min(2, 'نام باید حداقل ۲ نویسه باشد'),
  last_name: z.string().min(2, 'نام خانوادگی باید حداقل ۲ نویسه باشد'),
  // Email is optional: the login identity may be the phone alone.
  email: z
    .string()
    .trim()
    .refine((v) => v === '' || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v), 'ایمیل واردشده معتبر نیست'),
  phone: z
    .string()
    .refine((v) => /^09\d{9}$/.test(normalizePhone(v)), 'شماره تماس باید ۱۱ رقم و با 09 شروع شود'),
  role: z.enum(ROLE_VALUES as [UserRole, ...UserRole[]], {
    error: 'یک نقش معتبر انتخاب کنید'
  }),
  keycloak_role: z.enum(['ROLE_JUNIOR_BROKER', 'ROLE_SENIOR_BROKER']).optional(),
  status: z.enum(USER_STATUSES, { error: 'یک وضعیت معتبر انتخاب کنید' })
});

export type UserFormValues = z.infer<typeof userSchema>;
