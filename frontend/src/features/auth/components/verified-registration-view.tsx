"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Logo } from "@/components/brand/logo";
import { beginKeycloakSignIn } from "./keycloak-sign-in";
import styles from "./verified-registration-view.module.css";

export function generateSecurePassword(): string {
  const groups = ["ABCDEFGHJKLMNPQRSTUVWXYZ", "abcdefghijkmnopqrstuvwxyz", "23456789", "!@#$%*-_+"];
  const randomIndex = (limit: number) => {
    const value = new Uint32Array(1);
    const cutoff = Math.floor(0x100000000 / limit) * limit;
    do { crypto.getRandomValues(value); } while (value[0] >= cutoff);
    return value[0] % limit;
  };
  const all = groups.join("");
  const chars = groups.map(group => group[randomIndex(group.length)]);
  while (chars.length < 12) chars.push(all[randomIndex(all.length)]);
  for (let i = chars.length - 1; i > 0; i--) {
    const j = randomIndex(i + 1);
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }
  return chars.join("");
}

function EyeIcon({ visible }: { visible: boolean }) {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" />
    {visible && <path d="m3 3 18 18" />}
  </svg>;
}

class RegistrationApiError extends Error {
  constructor(message: string, readonly code?: string) {
    super(message);
  }
}

async function post(path: string, body: object) {
  const response = await fetch(`/backend/api/v1/auth/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store"
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new RegistrationApiError(typeof data.detail?.message === "string"
      ? data.detail.message : "درخواست انجام نشد؛ اطلاعات را بررسی و دوباره تلاش کنید.", data.detail?.error);
  }
  return data;
}

export function VerifiedRegistrationView() {
  const [identity, setIdentity] = useState({ first_name: "", last_name: "", username: "", mobile: "" });
  const [step, setStep] = useState<"identity" | "otp" | "done">("identity");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [usernameError, setUsernameError] = useState("");
  const [proof, setProof] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setUsernameError("");
    try {
      if (step === "identity") {
        if (password.length < 12 || password.length > 128) {
          throw new Error("رمز عبور باید بین ۱۲ تا ۱۲۸ کاراکتر باشد.");
        }
        if (password !== confirmation) throw new Error("رمز عبور و تکرار آن یکسان نیستند.");
        await post("otp/request", { mobile: identity.mobile });
        setCode("");
        setProof("");
        setStep("otp");
      } else {
        const token = proof || (await post("otp/verify", {
          mobile: identity.mobile,
          otp_code: code.replace(/[۰-۹]/g, c => String(c.charCodeAt(0) - 1776))
            .replace(/[٠-٩]/g, c => String(c.charCodeAt(0) - 1632))
        })).registration_token;
        setProof(token);
        try {
          await post("register", {
            registration_token: token, username: identity.username,
            first_name: identity.first_name, last_name: identity.last_name, password
          });
          setStep("done");
          setPassword("");
          setConfirmation("");
        } catch (failure) {
          // The proof is one-use, including failed registration attempts.
          setProof("");
          setStep("identity");
          throw failure;
        }
      }
    } catch (failure) {
      if (failure instanceof RegistrationApiError && failure.code === "username_taken") {
        setUsernameError(failure.message);
      }
      setError(failure instanceof Error ? failure.message : "ثبت‌نام انجام نشد؛ دوباره تلاش کنید.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main dir="rtl" className={styles.page}>
      <div className={styles.backdrop} aria-hidden="true" />
      <div className={styles.layout}>
        <Link href="/" className={styles.brand} aria-label="شکارچی — صفحهٔ اصلی">
          <Logo size={96} priority />
        </Link>
      <section className={styles.card} aria-labelledby="registration-title">
        <div className={styles.cardHeader}>
          <span className={styles.cardKicker}>به شکارچی خوش آمدید</span>
          <h1 id="registration-title" className="text-2xl font-bold">ثبت‌نام در شکارچی</h1>
          <ol className={styles.steps} aria-label="مراحل ثبت‌نام">
            {['اطلاعات شما', 'تأیید موبایل', 'حساب آماده'].map((label, index) => (
              <li key={label} aria-current={index === (step === 'identity' ? 0 : step === 'otp' ? 1 : 2) ? 'step' : undefined}>
                <span aria-hidden="true">{index + 1}</span>{label}
              </li>
            ))}
          </ol>
        </div>
        {step === "done" ? (
          <>
            <p role="status">حساب شما با نام کاربری {identity.username} ساخته شد. اکنون با رمز عبور یا کد پیامکی وارد شوید.</p>
            <Button className="mt-6 w-full" disabled={busy} onClick={async () => {
              setBusy(true);
              try { await beginKeycloakSignIn({ loginHint: identity.username }); }
              catch { setError("انتقال به ورود ممکن نشد؛ دوباره تلاش کنید."); setBusy(false); }
            }}>ورود به حساب</Button>
          </>
        ) : (
          <form onSubmit={submit} className={styles.form}>
            {step === "identity" ? (
              <>
                <p className="text-sm text-muted-foreground">حساب فقط پس از تأیید شماره موبایل ساخته می‌شود.</p>
                <div className={styles.fields}>
                {([
                  ["first_name", "نام", "given-name"],
                  ["last_name", "نام خانوادگی", "family-name"],
                  ["username", "نام کاربری دلخواه", "username"],
                  ["mobile", "شماره موبایل", "tel"]
                ] as const).map(([key, label, autocomplete]) => (
                  <div key={key}>
                    <label htmlFor={`register-${key}`} className="mb-2 block text-sm">{label}</label>
                    <Input id={`register-${key}`} name={key} autoComplete={autocomplete}
                      type={key === "mobile" ? "tel" : "text"} required disabled={busy}
                      dir={key === "mobile" || key === "username" ? "ltr" : "rtl"}
                      minLength={key === "username" ? 3 : key === "mobile" ? 10 : 2}
                      maxLength={key === "username" ? 64 : key === "mobile" ? 20 : 128}
                      pattern={key === "username" ? "[a-zA-Z0-9][a-zA-Z0-9._\\-]{2,63}" : undefined}
                      aria-invalid={key === "username" && usernameError ? true : undefined}
                      aria-describedby={key === "username" ? `register-username-help${usernameError ? " register-username-error" : ""}` : undefined}
                      value={identity[key]} onChange={e => {
                        setIdentity({ ...identity, [key]: e.target.value });
                        if (key === "username" && usernameError) { setUsernameError(""); setError(""); }
                      }} />
                    {key === "username" && (
                      <p id="register-username-help" className={styles.help}>۳ تا ۶۴ کاراکتر انگلیسی، عدد، نقطه، خط تیره یا زیرخط؛ بدون فاصله و با شروع حرف یا عدد. مثل <bdi dir="ltr">ali.reza_123</bdi></p>
                    )}
                    {key === "username" && usernameError && (
                      <p id="register-username-error" className="mt-2 text-sm text-destructive">{usernameError}</p>
                    )}
                  </div>
                ))}
                </div>
                <div>
                  <div className={styles.passwordHeading}>
                    <label htmlFor="register-password">رمز عبور</label>
                    <button type="button" className={styles.suggest} disabled={busy} onClick={() => {
                      try {
                        const value = generateSecurePassword(); setPassword(value); setConfirmation(value); setError("");
                      } catch { setError("تولید رمز امن در این مرورگر ممکن نیست؛ رمز را وارد کنید."); }
                    }}>پیشنهاد رمز عبور امن</button>
                  </div>
                  <div className={styles.passwordInput}>
                    <Input id="register-password" name="password" type={showPassword ? "text" : "password"}
                      dir="ltr" autoComplete="new-password" required minLength={12} maxLength={128}
                      value={password} onChange={e => setPassword(e.target.value)} disabled={busy} aria-describedby="register-password-help" />
                    <button type="button" className={styles.eye} aria-label={showPassword ? "مخفی کردن رمز عبور" : "نمایش رمز عبور"}
                      aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}><EyeIcon visible={showPassword} /></button>
                  </div>
                  <p id="register-password-help" className={styles.help}>حداقل ۱۲ کاراکتر؛ برای امنیت بیشتر از حروف، عدد و نماد استفاده کنید.</p>
                </div>
                <div>
                  <label htmlFor="register-confirmation">تکرار رمز عبور</label>
                  <Input id="register-confirmation" name="password_confirmation" type={showPassword ? "text" : "password"}
                    dir="ltr" autoComplete="new-password" required minLength={12} maxLength={128}
                    value={confirmation} onChange={e => setConfirmation(e.target.value)} disabled={busy} />
                </div>
              </>
            ) : (
              <>
                <p>کد تأیید ارسال‌شده به {identity.mobile} را وارد کنید.</p>
                <label htmlFor="register-otp">کد تأیید پیامکی</label>
                <Input id="register-otp" inputMode="numeric" autoComplete="one-time-code" dir="ltr"
                  required minLength={6} maxLength={6} value={code} disabled={busy}
                  onChange={e => setCode(e.target.value)} />
                <Button type="button" variant="ghost" disabled={busy} onClick={() => {
                  setStep("identity"); setProof(""); setError("");
                }}>ویرایش اطلاعات / دریافت کد تازه</Button>
              </>
            )}
            <Button type="submit" disabled={busy} className={styles.submit}>
              {busy ? "در حال بررسی…" : step === "identity" ? "دریافت کد تأیید" : "تأیید کد و ساخت حساب"}
            </Button>
          </form>
        )}
        {error && <p role="alert" className="mt-4 text-sm text-destructive">{error}</p>}
        <Link href="/auth/sign-in" className={styles.signIn}>حساب دارید؟ ورود به سامانه</Link>
      </section>
      </div>
    </main>
  );
}