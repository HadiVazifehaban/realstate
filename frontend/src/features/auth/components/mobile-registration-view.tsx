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
    agency_official_name: '', agency_brand_name: '', trade_code: '', national_id: '', office_address: '',
    latitude: '', longitude: '', consultant_count: '', agency_docs_ref: '',
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
    <div className="mx-auto max-w-lg p-6 space-y-6">
      <div className="flex flex-col items-center gap-2">
        <Icons.phone className="h-12 w-12 text-blue-600" />
        <h2 className="text-xl font-bold text-slate-900">ثبت‌نام سریع با موبایل</h2>
        <p className="text-sm text-slate-500">یک کد یک‌بار مصرف به شماره شما ارسال می‌شود.</p>
      </div>

      {step === 'mobile' && (
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700">شماره موبایل</label>
          <Input
            value={mobile}
            onChange={(e) => setMobile(e.target.value)}
            placeholder="۰۹۱۲۳۴۵۶۷۸۹"
            className="text-right dir-rtl"
          />
          <p className="text-xs text-slate-500">فرم معتبر: ۰۹۱۲…، +۹۸۹…، یا ۰۰۹۸۹…</p>
          <Button type="button" onClick={requestOtp} disabled={!MOBILE_RE.test(normalizeMobile(mobile))} className="w-full">
            ارسال کد تأیید
          </Button>
        </div>
      )}

      {step === 'otp' && (
        <div className="space-y-4">
          <label className="text-sm font-medium text-slate-700">کد تأیید از {currentMobile}</label>
          <Input
  value={otpCode}
  onChange={(e) => setOtpCode(e.target.value)}
  maxLength={6}
  placeholder="123456"
  className="text-center letter-spacing-wide dir-rtl"
/>
          {otpError && <div className="text-sm text-destructive">{otpError}</div>}
          <div className="flex justify-between items-center gap-2">
            <Button type="button" variant="outline" onClick={() => { setStep('mobile'); setOtpError(null); }}>
              تغییر شماره
            </Button>
            <Button type="button" onClick={verifyOtp} disabled={!/^\d{6}$/.test(otpCode.trim())} className="w-1/3">
              تایید کد
            </Button>
          </div>
        </div>
      )}

      {step === 'done' && !outcome?.hasAccount && (
        <div className="space-y-4">
          <label className="text-sm font-medium text-slate-700">ثبت‌نام کاربری</label>
          <p className="text-sm text-slate-600">ثبت‌نام کردن یا ثبت‌نام حرفه‌ای</p>
          <div className="space-y-3">
            <Button onClick={submitQuickRegistration} disabled={registering} className="w-full">
              ثبت‌نام سریع (کاربر عادی)
            </Button>
            <Button type="button" variant="secondary" onClick={() => setTrack('ROLE_JUNIOR_BROKER')} className="w-full">
              ثبت‌نام حرفه‌ای (مشاور)
            </Button>
          </div>
        </div>
      )}

      {step === 'done' && outcome?.hasAccount && (
        <div className="space-y-4">
          <label className="text-sm font-medium text-slate-700">حساب پیدا شد</label>
          <p className="text-sm text-slate-600">شماره شما ثبت‌شده است؛ در حال ورود به سیستم…</p>
          <div className="space-y-2">
            <p className="text-xs text-amber-600">اگر کد شما منقضی شده است، دوباره درخواست دهید.</p>
          </div>
        </div>
      )}

      {lastMessage && (
        <div className="p-3 rounded-md border bg-amber-50 border-amber-200 text-amber-800 text-sm">
          {lastMessage}
        </div>
      )}
    </div>
  );
}
