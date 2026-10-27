'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { toast } from 'sonner';
import { useTransition } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Icons } from '@/components/icons';
import { api } from '@/features/auth/api/registration';
import { KEYCLOAK_ENABLED } from '@/lib/utils';
import { signIn } from 'next-auth/react';
import Link from 'next/link';
import { AuthPanel, ShowcasePanel } from './sign-in-view';
import { cn } from '@/lib/utils';

function toAsciiDigits(raw: string): string {
  return raw
    .replace(/[۰-۹]/g, (ch) => String(ch.charCodeAt(0) - 0x06F0))
    .replace(/[٠-٩]/g, (ch) => String(ch.charCodeAt(0) - 0x0660))
    .replace(/[\s\-().]/g, '');
}

function normalizeMobile(raw: string): string {
  const text = toAsciiDigits(raw);
  if (text.startsWith('0098')) return '+98' + text.slice(4);
  if (text.startsWith('98') && text.length === 12) return '+' + text;
  if (text.startsWith('0')) return '+98' + text.slice(1);
  if (text.startsWith('9') && text.length === 10) return '+98' + text;
  return text;
}

const MOBILE_RE = /^(\+989\d{9})$/;

const STEPS = ['mobile', 'otp', 'done'] as const;
type Step = (typeof STEPS)[number];

interface OtpStepOutcome {
  token: string;
  hasAccount: boolean;
  mobile: string;
}

const trackLabels: Record<string, string> = {
  ROLE_JUNIOR_BROKER: 'مشاور تازه‌وارد',
  ROLE_SENIOR_BROKER: 'مشاور ارشد',
  ROLE_AGENCY_MANAGER: 'مدیر آژانس',
  ROLE_DATA_ANALYST: 'تحلیل‌گر داده',
};

const trackRequired = (track: string): string[] => {
  switch (track) {
    case 'ROLE_JUNIOR_BROKER':
      return ['agency_name', 'experience_years'];
    case 'ROLE_SENIOR_BROKER':
      return ['experience_years', 'specialty', 'certificate_ref'];
    case 'ROLE_AGENCY_MANAGER':
      return ['agency_official_name', 'agency_brand_name', 'trade_code', 'national_id', 'office_address'];
    case 'ROLE_DATA_ANALYST':
      return ['organization', 'position', 'invite_code', 'data_purpose'];
    default:
      return [];
  }
};

export default function MobileRegistrationView() {
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [step, setStep] = useState<Step>('mobile');
  const [mobile, setMobile] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [otpError, setOtpError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<OtpStepOutcome | null>(null);
  const [registering, setRegistering] = useState(false);
  const [track, setTrack] = useState('');
  const [professionalForm, setProfessionalForm] = useState<Record<string, string>>({});
  const [lastMessage, setLastMessage] = useState<string | null>(null);

  const currentMobile = outcome ? outcome.mobile : (normalizeMobile(mobile) || mobile);

  const flash = (message: string) => {
    setLastMessage(message);
    toast(message);
  };

  const requestOtp = async () => {
    const normalized = normalizeMobile(mobile);
    if (!MOBILE_RE.test(normalized)) {
      flash('شماره موبایل معتبر وارد کنید (۰۹۱۲... / +۹۸۹ / ۰۰۹۸).');
      return;
    }
    try {
      setLastMessage(null);
      const data = await api.requestOtp({ mobile: normalized });
      if (!data.ok) {
        flash(data.message);
        return;
      }
      setOutcome({ token: '', hasAccount: false, mobile: normalized });
      setStep('otp');
      setOtpError(null);
      flash(data.message);
    } catch (error) {
      flash(typeof error === 'string' ? error : 'درخواست کد ناموفق بود.');
    }
  };

  const exchangeAndContinue = async (token: string) => {
    try {
      if (KEYCLOAK_ENABLED) {
        await signIn('keycloak', { callbackUrl: '/dashboard' });
        return;
      }
      await api.exchangeSession({ registration_token: token });
      startTransition(() => {
        router.push(KEYCLOAK_ENABLED ? '/dashboard' : '/dashboard');
      });
      toast.success('به داشبورد هدایت شدید.');
    } catch (error) {
      setLastMessage(typeof error === 'string' ? error : 'ایجاد نشست ناموفق بود؛ دوباره کد بگیرید.');
    }
  };

  const submitQuickRegistration = async () => {
    if (!outcome) return;
    setRegistering(true);
    try {
      const data = await api.quickRegister({ registration_token: outcome.token });
      if (!data.ok) {
        setLastMessage(data.message);
        setRegistering(false);
        return;
      }
      if (KEYCLOAK_ENABLED) {
        await signIn('keycloak', { callbackUrl: '/dashboard' });
      } else {
        await api.exchangeSession({ registration_token: outcome.token });
        startTransition(() => {
          router.push('/dashboard');
        });
        flash(data.message || 'ثبت‌نام کامل شد و به داشبورد هدایت می‌شود.');
      }
    } catch (error) {
      setLastMessage(typeof error === 'string' ? error : 'ثبت‌نام ناموفق بود.');
      setRegistering(false);
    }
  };

  const submitProfessional = async () => {
    if (!outcome || !track) return;
    const payload: Record<string, unknown> = {
      registration_token: outcome.token,
      first_name: professionalForm.first_name,
      last_name: professionalForm.last_name,
      email: professionalForm.email,
      cities: professionalForm.cities ? professionalForm.cities.split(',').map((c) => c.trim()).filter(Boolean) : [],
      accepted_terms: true,
    };
    if (track === 'ROLE_AGENCY_MANAGER') {
      payload.referral_code = (professionalForm.referral_code ?? '').trim();
    }
    for (const field of trackRequired(track)) {
      payload[field] = professionalForm[field] ?? '';
    }
    try {
      const data = await api.submitProfessionalRegistration(track, payload);
      if (!data.ok) {
        setLastMessage(data.message);
        return;
      }
      setLastMessage(`درخواست برای «${trackLabels[track]}» ثبت شد؛ در صف بررسی قرار گرفت.`);
      toast.success(data.message);
      setTrack('');
      setProfessionalForm(initialProfessionalFields());
    } catch (error) {
      setLastMessage(typeof error === 'string' ? error : 'ثبت‌نام حرفه‌ای ناموفق بود.');
    }
  };

  const initialProfessionalFields = (): Record<string, string> => ({
    first_name: '', last_name: '', email: '', cities: '',
    agency_name: '', experience_years: '', specialty: '', certificate_ref: '',
    agency_official_name: '', agency_brand_name: '', trade_code: '', registration_no: '', national_id: '', landline: '', office_address: '', consultant_count: '1', agency_docs_ref: 'provided',
    referral_code: '',
    latitude: '', longitude: '',
    organization: '', position: '', invite_code: '', data_purpose: '', analysis_type: '',
  });

  const canSubmitProfessional = (t: string) => {
    if (!outcome) return false;
    return trackRequired(t).every((field) => Boolean(professionalForm[field]));
  };

  const verifyOtp = async () => {
    const trimmed = otpCode.trim();
    if (!/^\d{6}$/.test(trimmed)) {
      setOtpError('کد تأیید را با ۶ رقم وارد کنید.');
      return;
    }
    try {
      setOtpError(null);
      const data = await api.verifyOtp({ mobile: currentMobile, otp_code: trimmed });
      if (!data.ok) {
        setOtpError(data.message);
        return;
      }
      setOutcome({ token: data.registration_token, hasAccount: data.has_account, mobile: currentMobile });
      if (data.has_account) {
        setLastMessage('شماره موبایل شما در سامانه ثبت شده است؛ در حال دریافت نشست…');
        await exchangeAndContinue(data.registration_token);
      } else {
        setLastMessage('کد تأیید شد؛ حالا می‌توانید وارد شوید یا ثبت‌نام حرفه‌ای کنید.');
        setStep('done');
        flash(data.message);
      }
    } catch (error) {
      setOtpError(typeof error === 'string' ? error : 'پیمایش ناموفق بود.');
    }
  };

  return (
    <div className="showcase-shell grid min-h-screen lg:grid-cols-2">
      <AuthPanel
        title="ثبت‌نام در شکارچی"
        description="با شمارهٔ موبایل خود حساب بسازید و به امکانات سامانه دسترسی پیدا کنید."
        icon={<Icons.phone aria-hidden className="h-6 w-6" />}
      >
        <div className="space-y-6">
          <div className="flex flex-col items-center gap-2">
            <h3 className="text-showcase-text text-lg font-semibold">ثبت‌نام سریع با موبایل</h3>
            <p className="text-showcase-muted text-center text-sm leading-6">یک کد یک‌بارمصرف به شمارهٔ شما ارسال می‌شود.</p>
          </div>

          {step === 'mobile' && (
            <div className="space-y-2">
              <label htmlFor="registration-mobile" className="text-showcase-text block text-sm font-medium">شمارهٔ موبایل</label>
              <Input
                id="registration-mobile"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                value={mobile}
                onChange={(e) => setMobile(e.target.value)}
                placeholder="۰۹۱۲۳۴۵۶۷۸۹"
                className="border-showcase-border text-showcase-text placeholder:text-showcase-dim h-12 rounded-xl bg-white/5 text-right dir-rtl"
              />
              <p className="text-showcase-dim text-xs leading-5">فرمت معتبر: ۰۹۱۲…، ‎+۹۸۹…، یا ‎۰۰۹۸۹…</p>
              <Button
                type="button"
                onClick={requestOtp}
                disabled={!MOBILE_RE.test(normalizeMobile(mobile))}
                className={cn('h-12 w-full rounded-xl border-0 bg-linear-to-l from-gold-primary to-gold-dark text-showcase hover:opacity-90')}
              >
                ارسال کد تأیید
              </Button>
            </div>
          )}

          {step === 'otp' && (
            <div className="space-y-4">
              <label htmlFor="registration-otp" className="text-showcase-text block text-sm font-medium">کد تأیید ارسال‌شده به {currentMobile}</label>
              <Input
                id="registration-otp"
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value)}
                maxLength={6}
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="۱۲۳۴۵۶"
                className="border-showcase-border text-showcase-text h-12 rounded-xl bg-white/5 text-center tracking-[0.35em]"
              />
              {otpError && <div role="alert" className="text-showcase-danger text-sm">{otpError}</div>}
              <div className="flex items-center justify-between gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => { setStep('mobile'); setOtpError(null); }}
                  className="border-showcase-border text-showcase-text h-11 rounded-xl bg-white/5 hover:bg-white/10"
                >
                  تغییر شماره
                </Button>
                <Button
                  type="button"
                  onClick={verifyOtp}
                  disabled={!/^\d{6}$/.test(otpCode.trim())}
                  className="h-11 rounded-xl bg-linear-to-l from-gold-primary to-gold-dark text-showcase hover:opacity-90"
                >
                  تایید کد
                </Button>
              </div>
            </div>
          )}

          {step === 'done' && !outcome?.hasAccount && (
            <div className="space-y-4">
              <label className="text-showcase-text block text-sm font-medium">نوع حساب</label>
              <p className="text-showcase-muted text-sm">روش ثبت‌نام موردنظر را انتخاب کنید.</p>
              <div className="space-y-3">
                <Button onClick={submitQuickRegistration} disabled={registering} className="h-12 w-full rounded-xl bg-linear-to-l from-gold-primary to-gold-dark text-showcase hover:opacity-90">
                  ثبت‌نام سریع (کاربر عادی)
                </Button>
                <Button type="button" variant="outline" onClick={() => setTrack('ROLE_JUNIOR_BROKER')} className="border-showcase-border text-showcase-text h-12 w-full rounded-xl bg-white/5 hover:bg-white/10">
                  ثبت‌نام حرفه‌ای (مشاور)
                </Button>
                <Button type="button" variant="outline" onClick={() => { setTrack('ROLE_AGENCY_MANAGER'); setProfessionalForm(initialProfessionalFields()); }} className="border-showcase-border text-showcase-text h-12 w-full rounded-xl bg-white/5 hover:bg-white/10">
                  ثبت دفتر املاک
                </Button>
              </div>
            </div>
          )}

          {track === 'ROLE_AGENCY_MANAGER' && step === 'done' && !outcome?.hasAccount && (
            <div className="space-y-2">
              <label className="text-showcase-text block text-sm font-medium">اطلاعات دفتر</label>
              <Input aria-label="نام رسمی دفتر" placeholder="نام رسمی دفتر" value={professionalForm.agency_official_name ?? ''} onChange={(event) => setProfessionalForm((current) => ({ ...current, agency_official_name: event.target.value }))} />
              <Input aria-label="نام تجاری دفتر" placeholder="نام تجاری دفتر (اختیاری)" value={professionalForm.agency_brand_name ?? ''} onChange={(event) => setProfessionalForm((current) => ({ ...current, agency_brand_name: event.target.value }))} />
              <Input aria-label="شناسه صنفی" placeholder="شناسه صنفی" value={professionalForm.trade_code ?? ''} onChange={(event) => setProfessionalForm((current) => ({ ...current, trade_code: event.target.value }))} />
              <Input aria-label="شناسه ملی" placeholder="شناسه ملی" value={professionalForm.national_id ?? ''} onChange={(event) => setProfessionalForm((current) => ({ ...current, national_id: event.target.value }))} />
              <Input aria-label="نشانی دفتر" placeholder="نشانی دفتر" value={professionalForm.office_address ?? ''} onChange={(event) => setProfessionalForm((current) => ({ ...current, office_address: event.target.value }))} />
              <label htmlFor="agency-referral-code" className="text-showcase-text block text-sm font-medium">کد معرف (اختیاری)</label>
              <Input
                id="agency-referral-code"
                autoComplete="off"
                maxLength={16}
                value={professionalForm.referral_code ?? ''}
                onChange={(event) => setProfessionalForm((current) => ({ ...current, referral_code: event.target.value.toUpperCase() }))}
                placeholder="کد دفتر همکار"
                className="border-showcase-border text-showcase-text h-11 rounded-xl bg-white/5"
              />
              <p className="text-showcase-dim text-xs leading-5">این فرم فقط درخواست حرفه‌ای را ثبت می‌کند. ثبت دفتر و کد معرف هنگام ایجاد دفتر در بخش «دفاتر همکار» انجام می‌شود.</p>
              <Button type="button" disabled={!canSubmitProfessional(track)} onClick={submitProfessional} className="h-11 w-full">ثبت درخواست دفتر</Button>
            </div>
          )}

          {step === 'done' && outcome?.hasAccount && (
            <div className="space-y-4">
              <label className="text-showcase-text block text-sm font-medium">حساب پیدا شد</label>
              <p className="text-showcase-muted text-sm leading-6">شمارهٔ شما قبلاً ثبت شده است؛ در حال انتقال به صفحهٔ ورود…</p>
              <p className="text-showcase-dim text-xs">اگر کد منقضی شده است، دوباره درخواست دهید.</p>
            </div>
          )}

          {lastMessage && (
            <div role="status" className="border-showcase-border bg-white/5 text-showcase-muted rounded-xl border p-3 text-sm leading-6">
              {lastMessage}
            </div>
          )}

          <p className="text-showcase-dim border-showcase-border border-t pt-5 text-center text-xs">
            حساب دارید؟{' '}
            <Link href="/auth/sign-in" className="text-gold-accent hover:underline">وارد شوید</Link>
          </p>
        </div>
      </AuthPanel>
      <ShowcasePanel />
    </div>
  );
}
