"use client";

import * as Sentry from '@sentry/nextjs';
import { useEffect } from 'react';

// global-error replaces the root layout when it errors, so globals.css is not
// loaded here — styles must be inline and self-contained.
export default function GlobalError({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang='fa' dir='rtl'>
      <head>
        <style>{`@font-face{font-family:Vazirmatn;src:url('/fonts/Vazirmatn%5Bwght%5D.woff2') format('woff2');font-style:normal;font-weight:100 900;font-display:swap}`}</style>
      </head>
      <body
        style={{
          margin: 0,
          display: "flex",
          minHeight: "100vh",
          alignItems: "center",
          justifyContent: "center",
          /* global-error replaces the root layout, so use the self-hosted
             Vazirmatn asset directly instead of relying on its font class. */
          fontFamily: "'Vazirmatn', 'Segoe UI', Tahoma, system-ui, sans-serif"
        }}
      >
        <div style={{ textAlign: "center", padding: "1rem" }}>
          <h1 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>خطایی رخ داد</h1>
          <p style={{ color: "#6b7280", marginBottom: "1.25rem" }}>
            خطای غیرمنتظره‌ای رخ داد. لطفاً دوباره تلاش کنید.
          </p>
          <button
            onClick={() => reset()}
            style={{
              padding: "0.5rem 1.25rem",
              borderRadius: "0.5rem",
              border: "1px solid #d1d5db",
              background: "transparent",
              font: "inherit",
              cursor: "pointer"
            }}
          >
            تلاش دوباره
          </button>
        </div>
      </body>
    </html>
  );
}
