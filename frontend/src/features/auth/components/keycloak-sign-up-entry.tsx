"use client";

import { Icons } from "@/components/icons";
import { useEffect, useState } from "react";
import { signIn } from "next-auth/react";
import { resolveCallbackUrl } from "./keycloak-sign-in";

export function KeycloakSignUpEntry() {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const callbackUrl = resolveCallbackUrl(window.location.search);
    void signIn("keycloak", { callbackUrl }, { prompt: "create" }).catch(() => setFailed(true));
  }, []);

  return (
    <main
      dir="rtl"
      className="showcase-shell flex min-h-screen items-center justify-center px-6"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="flex items-center gap-3 text-showcase-muted">
        <Icons.spinner className="h-5 w-5 animate-spin" aria-hidden />
        <span role={failed ? "alert" : undefined}>
          {failed ? "انتقال به ثبت‌نام ممکن نشد. دوباره صفحه را بارگذاری کنید." : "در حال انتقال به ثبت‌نام امن…"}
        </span>
      </div>
    </main>
  );
}
