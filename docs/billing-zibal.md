# SHEKARCHI Zibal Billing

## Current Safety State

The Zibal adapter is disabled by default. No Merchant ID is bundled in this repository, no real payment has been made, and no migration has been applied to a database. Keep these settings until an approved Zibal sandbox flow has been exercised:

```env
ZIBAL_ENABLED=false
ZIBAL_TEST_MODE=true
ZIBAL_MERCHANT=
ZIBAL_CREDENTIAL_ENCRYPTION_KEY=
```

The adapter uses the standard Zibal endpoints configured in `app/core/config.py`. The official documentation site was not reachable from the implementation environment, so the request, verification, inquiry result codes, and callback fields must be revalidated against the current official Zibal documentation before enabling the provider. The adapter fails closed on unknown status/result codes, amount mismatches, missing track IDs, timeouts, or malformed responses.

The admin entry is **مدیریت و زیرساخت → تنظیمات درگاه زیبال** (`/dashboard/settings/zibal`). It is restricted to `ROLE_ADMIN`. Its API (`GET/PUT /api/v1/admin/integrations/zibal/config`) returns only credential presence and a masked suffix, never the Merchant Code. The code is encrypted at rest with the separate `ZIBAL_CREDENTIAL_ENCRYPTION_KEY`; that key must be provisioned only in the Backend secret environment. The current API adapter uses Zibal's Merchant Code field; it does not invent a separate unsupported API-token field.

## Configuration

Set these only in the Backend secret environment, not in Next.js `NEXT_PUBLIC_*` variables:

```env
ZIBAL_ENABLED=false
ZIBAL_TEST_MODE=true
ZIBAL_MERCHANT=
ZIBAL_CREDENTIAL_ENCRYPTION_KEY=
ZIBAL_REQUEST_URL=https://gateway.zibal.ir/v1/request
ZIBAL_VERIFY_URL=https://gateway.zibal.ir/v1/verify
ZIBAL_INQUIRY_URL=https://gateway.zibal.ir/v1/inquiry
ZIBAL_START_URL=https://gateway.zibal.ir/start
ZIBAL_CALLBACK_URL=https://api.example.invalid/api/v1/billing/zibal/callback
ZIBAL_RESULT_URL=https://app.example.invalid/dashboard/billing
ZIBAL_TIMEOUT_SECONDS=8
```

Replace both example hosts with the actual API and Frontend origins before enabling. The callback URL must be publicly reachable and end in `/api/v1/billing/zibal/callback`; it must go to FastAPI directly, not the authenticated Next.js BFF. Cloud mode requires HTTPS. The result URL is a fixed server setting; caller-supplied return URLs are never accepted.

Live activation requires both `ZIBAL_ENABLED=true` and `ZIBAL_TEST_MODE=false`, plus the Merchant ID and Callback/Result URLs. Never set `ZIBAL_TEST_MODE=false` before a controlled sandbox test and finance sign-off. The existing `PaymentOrder` amount is in Toman; provider attempts record both the Toman amount and the integer Rial amount sent to the gateway (`1 toman = 10 rial`).

## Flow

1. Backend computes the order amount from its plan/referral policy and persists an idempotent `PaymentOrder`.
2. `PaymentAttempt` records each provider request. A pending attempt is reused on repeated checkout calls; a result-unknown request is not automatically retried.
3. Zibal's browser return is only a notification. FastAPI uses the saved track ID and calls Verify server-to-server.
4. Only a verified Rial amount equal to the saved order amount can settle the order. A mismatch enters `RECONCILIATION_REQUIRED` and never activates a subscription.
5. Order settlement, subscription activation, quota snapshot and referral completion happen in the existing transaction. Repeated callbacks are idempotent.
6. Test-mode gateway payments end in `TEST_APPROVED_NO_ACTIVATION` and never activate a paid subscription.

The endpoint and Provider never log Merchant credentials or persist raw Zibal response bodies/card data. Only minimal result codes, track IDs, reference IDs, amounts and state transitions are retained for reconciliation/audit.

## Reconciliation

`app.services.zibal_billing.reconcile_stale_zibal_attempts()` is the bounded reconciliation job callable from an external scheduler. The financial admin API also exposes a bounded manual run and per-attempt inquiry. Run the CLI only after deploying the migration and enabling a valid sandbox/production configuration:

```bash
python -m scripts.reconcile_zibal --older-than-minutes 5 --limit 50
```

The command is not scheduled or run automatically by the application. `UNKNOWN` requests without a track ID remain in the finance queue for manual investigation; the system does not risk a duplicate charge by retrying them.

For a `PENDING`/`UNKNOWN` attempt that finance independently checked in the Zibal merchant portal and confirmed was not paid, the finance-only `confirm-not-paid` action requires a 20–1000 character reason, cancels the order (it is not reused), releases reserved referral credit, and records an audit entry. A late successful callback after that action goes to reconciliation and does not activate the cancelled order.

## Migration and Rollout

`alembic/versions/d9b41e7a2c63_zibal_payment_attempts.py` adds `payment_attempt`, idempotency and plan snapshot fields, nullable card-only snapshots for online orders, `pending_payment` enum values, the editable plan catalog seeded from the existing SHEKARCHI prices, encrypted gateway configuration, and workspace ownership for first-party listings. Its downgrade refuses to drop online attempts/orders, customized plans, any gateway configuration record, or workspace-scoped listings. The migration has not been run.

First-party listing quota is checked server-side under a workspace lock; a duplicate/deduplicated listing is not charged and scraped/global inventory is not included. `GET /api/v1/billing/quota/me` reports listing usage. SMS, advisor, and region quota fields remain defined on plans, but the current repository does not provide all corresponding metered feature/member-creation paths, so those quotas are not claimed as enforced by this change.

Before an approved deployment:

1. Verify the current database revision and take a recoverable database backup.
2. Confirm the current official Zibal API contract with a sandbox Merchant.
3. Apply the migration only to an approved development/staging database.
4. Test request, callback with tampered parameters, Verify, already-verified Inquiry, amount mismatch, timeout, duplicate callback, repeated checkout and reconciliation.
5. Configure HTTPS Callback/Result URLs, Merchant secrets, firewall, and finance-role permissions.
6. Enable live mode only after a separately approved end-to-end test and reconciliation check.

No live Merchant, production host configuration, or database operation is included in this code change.
