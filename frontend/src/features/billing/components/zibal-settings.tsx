"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuthContext } from "@/hooks/use-auth";
import {
  fetchZibalGatewaySettings,
  updateZibalGatewaySettings,
  type ZibalGatewaySettings
} from "../api/client";

type FormState = {
  version: number;
  enabled: boolean;
  testMode: boolean;
  merchantConfigured: boolean;
  merchantMasked: string | null;
  source: "database" | "environment";
  encryptionKeyReady: boolean;
  callbackUrl: string;
  resultUrl: string;
  requestUrl: string;
  verifyUrl: string;
  inquiryUrl: string;
  startUrl: string;
};

const initial: FormState = {
  version: 0,
  enabled: false,
  testMode: true,
  merchantConfigured: false,
  merchantMasked: null,
  source: "environment",
  encryptionKeyReady: false,
  callbackUrl: "",
  resultUrl: "http://localhost:3000/dashboard/billing",
  requestUrl: "",
  verifyUrl: "",
  inquiryUrl: "",
  startUrl: ""
};

function fromServer(value: ZibalGatewaySettings): FormState {
  return {
    version: value.version,
    enabled: value.enabled,
    testMode: value.test_mode,
    merchantConfigured: value.merchant_configured,
    merchantMasked: value.merchant_masked,
    source: value.source,
    encryptionKeyReady: value.encryption_key_ready,
    callbackUrl: value.callback_url,
    resultUrl: value.result_url,
    requestUrl: value.request_url,
    verifyUrl: value.verify_url,
    inquiryUrl: value.inquiry_url,
    startUrl: value.start_url
  };
}

const fieldClass = "w-full rounded-xl border border-[#ffd8be]/20 bg-[#060b13]/80 text-white focus-visible:ring-[#ffd8be]";

export function ZibalSettings() {
  const auth = useAuthContext();
  const allowed = auth.roles.includes("ROLE_ADMIN");
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(initial);
  const [merchantCode, setMerchantCode] = useState("");
  const [clearMerchant, setClearMerchant] = useState(false);
  const [dirty, setDirty] = useState(false);
  const shouldMigrateEnvironmentCredential = form.source === "environment" && form.merchantConfigured && form.encryptionKeyReady;
  const encryptionKeyRequired = Boolean(
    merchantCode.trim() || form.enabled || (form.source === "environment" && !clearMerchant)
  );

  const query = useQuery({
    queryKey: ["admin", "zibal-settings"],
    queryFn: fetchZibalGatewaySettings,
    enabled: !auth.isLoading && allowed,
    retry: false
  });

  useEffect(() => {
    if (query.data && !dirty) setForm(fromServer(query.data));
  }, [query.data, dirty]);

  const updateField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setDirty(true);
    setForm((current) => ({ ...current, [key]: value }));
  };

  const save = useMutation({
    mutationFn: () => updateZibalGatewaySettings({
      version: form.version,
      enabled: form.enabled,
      test_mode: form.testMode,
      clear_merchant: clearMerchant,
      callback_url: form.callbackUrl.trim(),
      result_url: form.resultUrl.trim(),
      ...(merchantCode.trim() ? { merchant_code: merchantCode.trim() } : {})
    }),
    onSuccess: async (saved) => {
      setMerchantCode("");
      setClearMerchant(false);
      setDirty(false);
      setForm(fromServer(saved));
      toast.success("تنظیمات زیبال به‌صورت امن ذخیره شد.");
      await queryClient.invalidateQueries({ queryKey: ["admin", "zibal-settings"] });
      await queryClient.invalidateQueries({ queryKey: ["billing", "plans"] });
    },
    onError: (error) => toast.error(error.message)
  });

  if (auth.isLoading) return <p role="status" dir="rtl">در حال بررسی دسترسی…</p>;
  if (!allowed) return <p role="alert" dir="rtl">مدیریت اعتبارنامهٔ درگاه فقط برای مدیر سامانه مجاز است.</p>;

  return (
    <section dir="rtl" className="mx-auto w-full max-w-4xl space-y-5 text-white">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold">مدیریت درگاه زیبال</h1>
        <p className="text-sm text-muted-foreground">کد پذیرنده فقط در Backend رمزگذاری می‌شود و مقدار کامل آن هیچ‌وقت دوباره به مرورگر برنمی‌گردد.</p>
      </header>

      {query.isPending && <p role="status">در حال دریافت وضعیت درگاه…</p>}
      {query.isError && <Alert variant="destructive"><AlertDescription>{query.error.message}</AlertDescription></Alert>}

      {query.data && <>
        <Alert variant={form.enabled ? form.testMode ? "destructive" : "default" : "default"}>
          <AlertDescription>
            {form.enabled
              ? form.testMode
                ? "درگاه فعال است اما در حالت آزمایشی قرار دارد؛ هیچ اشتراک پولی فعال نمی‌شود."
                : "درگاه پرداخت واقعی فعال است. قبل از استفاده، Callback و Merchant را در پنل زیبال تأیید کنید."
              : "درگاه خاموش است. درگاه تا زمان فعال‌سازی صریح مدیر و تنظیم اعتبارنامه، هیچ درخواست واقعی نمی‌فرستد."}
          </AlertDescription>
        </Alert>

        {!form.encryptionKeyReady && <Alert variant="destructive"><AlertDescription>
          کلید `ZIBAL_CREDENTIAL_ENCRYPTION_KEY` در محیط Backend تنظیم نشده است؛ کد مرچنت از UI ذخیره نمی‌شود.
        </AlertDescription></Alert>}

        <Card className="border-[#ffd8be]/15 bg-[#060b13]/70">
          <CardHeader>
            <CardTitle>اعتبارنامه و وضعیت</CardTitle>
            <CardDescription>منبع فعلی: {form.source === "database" ? "تنظیم رمزگذاری‌شدهٔ دیتابیس" : "Environment سرور"} · نسخهٔ تنظیمات {form.version}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <label className="grid gap-2 text-sm font-medium">
              کد مرچنت / کلید پذیرندهٔ زیبال
              <Input
                className={fieldClass}
                type="password"
                autoComplete="new-password"
                spellCheck={false}
                dir="ltr"
                value={merchantCode}
                onChange={(event) => { setDirty(true); setMerchantCode(event.target.value); setClearMerchant(false); }}
                placeholder={form.merchantConfigured ? `ثبت شده (${form.merchantMasked ?? "••••"})؛ برای حفظ، خالی بگذارید` : "کد مرچنت را وارد کنید"}
              />
              <span className="text-xs text-muted-foreground">مقدار ذخیره‌شده خوانده یا نمایش داده نمی‌شود. زیبال در کد فعلی با Merchant Code احراز می‌شود؛ توکن جداگانه‌ای ارسال نمی‌شود.</span>
            </label>

            {form.merchantConfigured && <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={clearMerchant}
                onChange={(event) => { setDirty(true); setClearMerchant(event.target.checked); if (event.target.checked) setMerchantCode(""); }}
              />
              پاک‌کردن اعتبارنامهٔ ذخیره‌شده (درگاه هم‌زمان باید خاموش باشد)
            </label>}

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-2 text-sm font-medium">
                Callback عمومی Backend
                <Input className={fieldClass} dir="ltr" value={form.callbackUrl} onChange={(event) => updateField("callbackUrl", event.target.value)} placeholder="https://api.example.ir/api/v1/billing/zibal/callback" />
              </label>
              <label className="grid gap-2 text-sm font-medium">
                بازگشت به Frontend
                <Input className={fieldClass} dir="ltr" value={form.resultUrl} onChange={(event) => updateField("resultUrl", event.target.value)} placeholder="https://app.example.ir/dashboard/billing" />
              </label>
            </div>

            <div className="grid gap-3 rounded-xl border border-[#ffd8be]/10 p-4 sm:grid-cols-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.enabled} onChange={(event) => updateField("enabled", event.target.checked)} />
                فعال‌سازی درگاه
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.testMode} onChange={(event) => updateField("testMode", event.target.checked)} />
                حالت آزمایشی — فعال‌سازی اشتراک ممنوع
              </label>
            </div>

            <details className="rounded-xl border border-[#ffd8be]/10 p-4">
              <summary className="cursor-pointer text-sm font-medium">نشانی‌های ثابت Provider</summary>
              <dl className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                <dt>Request</dt><dd dir="ltr">{form.requestUrl}</dd>
                <dt>Verify</dt><dd dir="ltr">{form.verifyUrl}</dd>
                <dt>Inquiry</dt><dd dir="ltr">{form.inquiryUrl}</dd>
                <dt>Start</dt><dd dir="ltr">{form.startUrl}</dd>
              </dl>
            </details>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                disabled={save.isPending || (!dirty && !shouldMigrateEnvironmentCredential) || (!form.encryptionKeyReady && encryptionKeyRequired) || (form.enabled && !form.merchantConfigured && !merchantCode.trim()) || (clearMerchant && form.enabled)}
                onClick={() => {
                  if (form.enabled && !form.testMode && !window.confirm('این کار پرداخت واقعی زیبال را فعال می‌کند. Callback و Merchant را در Sandbox تأیید کرده‌اید؟')) return;
                  save.mutate();
                }}
                >{save.isPending ? 'در حال ذخیره…' : 'ذخیرهٔ تنظیمات زیبال'}</Button>
              {save.isError && <span role="alert" className="text-sm text-destructive">{save.error.message}</span>}
            </div>
          </CardContent>
        </Card>
      </>}
    </section>
  );
}
