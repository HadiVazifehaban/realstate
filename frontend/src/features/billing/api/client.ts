import { apiBaseUrl } from '@/lib/api-base-url';
import { getActiveWorkspaceId } from '@/features/network/api/client';

export type BillingPlan = {
  id: string;
  title: string;
  price_toman: number;
  duration_days: number;
  listing_quota: number | null;
  sms_quota: number;
  regions_quota: number;
  advisor_quota: number | null;
  is_unlimited: boolean;
  features: string[];
};

export type ManagedBillingPlan = BillingPlan & {
  description: string;
  is_active: boolean;
  sort_order: number;
};

export type PlanFields = Omit<ManagedBillingPlan, 'id' | 'is_active' | 'sort_order'> & {
  is_active: boolean;
  sort_order: number;
};
export type PlanCreateInput = PlanFields & { id: string };

export type ZibalGatewaySettings = {
  enabled: boolean;
  test_mode: boolean;
  merchant_configured: boolean;
  merchant_masked: string | null;
  source: 'database' | 'environment';
  encryption_key_ready: boolean;
  callback_url: string;
  result_url: string;
  request_url: string;
  verify_url: string;
  inquiry_url: string;
  start_url: string;
  version: number;
};

export type ZibalGatewaySettingsUpdate = {
  version: number;
  enabled: boolean;
  test_mode: boolean;
  merchant_code?: string;
  clear_merchant: boolean;
  callback_url: string;
  result_url: string;
};

export type BillingPaymentMethod = 'CARD_TO_CARD' | 'ZIBAL';

export type BillingPaymentMethods = {
  CARD_TO_CARD: boolean;
  ZIBAL: boolean;
  ZIBAL_TEST_MODE: boolean;
};

export type PaymentAttempt = {
  id: string;
  order_id: string;
  order_number: string | null;
  provider: string;
  status: string;
  attempt_number: number;
  amount_toman: number;
  currency: string;
  track_id: string | null;
  payment_url: string | null;
  reference_id: string | null;
  failure_code: string | null;
  created_at: string;
  updated_at: string;
};

export type PaymentOrder = {
  id: string;
  order_number: string;
  plan: string;
  amount_toman: number;
  base_amount_toman: number;
  discount_percent: number;
  discount_amount_toman: number;
  referral_credit_count: number;
  environment_mode: 'test' | 'live';
  is_test: boolean;
  status: string;
  payment_method: BillingPaymentMethod;
  card_number: string | null;
  card_last4: string | null;
  card_holder: string | null;
  card_configured: boolean;
  test_warning: string | null;
  created_at: string;
  expires_at: string;
  submitted_at: string | null;
  approved_at?: string | null;
  payment_attempt?: PaymentAttempt | null;
  receipt?: {
    original_filename: string;
    content_type: string;
    file_size: number;
    transfer_tracking_number: string;
    transfer_datetime: string;
  } | null;
};

export function createBillingIdempotencyKey(): string {
  if (typeof crypto === 'undefined' || typeof crypto.getRandomValues !== 'function') {
    throw new Error('مرورگر تولید تصادفی امن را پشتیبانی نمی‌کند.');
  }
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('');
}

export type Subscription = {
  plan: string;
  title: string;
  status: string;
  starts_at: string | null;
  expires_at: string | null;
  listing_quota: number | null;
  sms_quota: number;
  regions_quota: number;
  advisor_quota: number | null;
  is_unlimited: boolean;
  usage: Record<string, number>;
  quota?: {
    listings: { used: number; limit: number | null; unlimited: boolean; remaining: number | null };
  };
};

export type ReferralSummary = {
  referral_code: string;
  pending_referrals: number;
  completed_referrals: number;
  credits: Record<string, number>;
  next_renewal_percent: number;
  policy: { credit_percent: number; invoice_cap_percent: number; allow_stacking_with_other_discounts: boolean };
  referrals: Array<{ status: string; created_at: string; completed_at: string | null }>;
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const workspaceId = path.startsWith('/billing') ? getActiveWorkspaceId() : null;
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    cache: 'no-store',
    ...init,
    headers: {
      ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(workspaceId ? { 'X-Workspace-ID': workspaceId } : {}),
      ...init.headers
    }
  });
  if (!response.ok) {
    let message = 'درخواست ناموفق بود.';
    try {
      const body = await response.json();
      const detail = body.detail;
      message = typeof detail === 'string' ? detail : detail?.message ?? message;
    } catch { /* keep fallback */ }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export const fetchPlans = () => request<{ plans: BillingPlan[]; payment_methods: BillingPaymentMethods }>('/billing/plans');
export const fetchOrders = () => request<{ items: PaymentOrder[]; page: number; page_size: number }>('/billing/orders');
export const fetchSubscription = () => request<Subscription>('/billing/subscriptions/current');
export const fetchReferralSummary = () => {
  const workspaceId = getActiveWorkspaceId();
  return request<ReferralSummary>('/billing/referrals', workspaceId ? {
    headers: { 'X-Workspace-ID': workspaceId }
  } : {});
};
export const createOrder = (
  planId: string,
  paymentMethod: BillingPaymentMethod = 'CARD_TO_CARD',
  idempotencyKey = createBillingIdempotencyKey()
) => request<PaymentOrder & { plan_detail: BillingPlan; payment_attempt: PaymentAttempt | null }>('/billing/orders', {
  method: 'POST',
  headers: { 'Idempotency-Key': idempotencyKey },
  body: JSON.stringify({ plan_id: planId, payment_method: paymentMethod })
});
export const startZibalCheckout = (orderId: string) => request<{
  order: PaymentOrder;
  payment_attempt: PaymentAttempt;
}>(`/billing/orders/${encodeURIComponent(orderId)}/checkout`, { method: 'POST' });
export const previewOrder = (planId: string) => request<{
  plan: BillingPlan;
  base_amount_toman: number;
  referral_discount_percent: number;
  referral_discount_toman: number;
  referral_credit_count: number;
  amount_toman: number;
}>('/billing/checkout/preview', { method: 'POST', body: JSON.stringify({ plan_id: planId }) });
export const fetchOrder = (id: string) => request<PaymentOrder>(`/billing/orders/${encodeURIComponent(id)}`);
export function submitReceipt(id: string, values: { file: File; trackingNumber: string; transferDateTime: string }) {
  const form = new FormData();
  form.set('file', values.file);
  form.set('transfer_tracking_number', values.trackingNumber);
  form.set('transfer_datetime', values.transferDateTime);
  return request<{ order_id: string; status: string; message: string }>(`/billing/orders/${encodeURIComponent(id)}/receipt`, {
    method: 'POST', body: form
  });
}

export function fetchFinancialQueue(options: { page?: number; status?: string; isTest?: boolean; q?: string } = {}) {
  const params = new URLSearchParams();
  if (options.page) params.set('page', String(options.page));
  if (options.status) params.set('status', options.status);
  if (options.isTest !== undefined) params.set('is_test', String(options.isTest));
  if (options.q?.trim()) params.set('q', options.q.trim());
  const query = params.toString();
  const suffix = query ? `?${query}` : '';
  return request<{ items: PaymentOrder[]; page: number; page_size: number }>(`/admin/financial/payment-orders${suffix}`);
}
export function fetchFinancialAttempts(options: { page?: number; status?: string; reconciliationOnly?: boolean } = {}) {
  const params = new URLSearchParams();
  if (options.page) params.set('page', String(options.page));
  if (options.status) params.set('status', options.status);
  const route = options.reconciliationOnly ? '/admin/financial/reconciliation' : '/admin/financial/payment-attempts';
  const query = params.toString();
  const suffix = query ? `?${query}` : '';
  return request<{ items: PaymentAttempt[]; page: number; page_size: number }>(`${route}${suffix}`);
}
export const reconcilePaymentAttempt = (id: string) => request<{
  result: string; order: PaymentOrder; payment_attempt: PaymentAttempt;
}>(`/admin/financial/payment-attempts/${encodeURIComponent(id)}/reconcile`, { method: 'POST' });
export const confirmZibalAttemptNotPaid = (id: string, reason: string) => request<{
  order: PaymentOrder; payment_attempt: PaymentAttempt;
}>(`/admin/financial/payment-attempts/${encodeURIComponent(id)}/confirm-not-paid`, {
  method: 'POST', body: JSON.stringify({ confirmed_not_paid: true, reason })
});
export const runFinancialReconciliation = () => request<{
  success: boolean; checked: number; paid: number; pending: number; errors: number;
}>('/admin/financial/reconciliation/run', { method: 'POST' });
export function fetchFinancialAuditLogs(options: { page?: number; action?: string; entityId?: string } = {}) {
  const params = new URLSearchParams();
  if (options.page) params.set('page', String(options.page));
  if (options.action) params.set('action', options.action);
  if (options.entityId) params.set('entity_id', options.entityId);
  const query = params.toString();
  const suffix = query ? `?${query}` : '';
  return request<{ items: Array<{ id: string; actor_user_id: string; actor_role: string; action: string; entity_type: string; entity_id: string; before: Record<string, unknown>; after: Record<string, unknown>; request_id: string; created_at: string }>; page: number; page_size: number }>(`/admin/financial/audit-logs${suffix}`);
}
export const fetchManagedPlans = () => request<{ items: ManagedBillingPlan[] }>('/admin/financial/plans');
export const createManagedPlan = (plan: PlanCreateInput) => request<ManagedBillingPlan>('/admin/financial/plans', {
  method: 'POST', body: JSON.stringify(plan)
});
export const updateManagedPlan = (id: string, plan: PlanFields) => request<ManagedBillingPlan>(
  `/admin/financial/plans/${encodeURIComponent(id)}`,
  { method: 'PUT', body: JSON.stringify(plan) }
);
export const fetchZibalGatewaySettings = () => request<ZibalGatewaySettings>('/admin/integrations/zibal/config');
export const updateZibalGatewaySettings = (settings: ZibalGatewaySettingsUpdate) => request<ZibalGatewaySettings>(
  '/admin/integrations/zibal/config',
  { method: 'PUT', body: JSON.stringify(settings) }
);
export const approveTestOrder = (id: string) => request<PaymentOrder>(`/admin/financial/payment-orders/${encodeURIComponent(id)}/approve`, { method: 'POST' });
export const rejectOrder = (id: string, reason: string) => request<PaymentOrder>(`/admin/financial/payment-orders/${encodeURIComponent(id)}/reject`, {
  method: 'POST', body: JSON.stringify({ reason })
});
export const receiptUrl = (id: string) => `${apiBaseUrl()}/admin/financial/payment-orders/${encodeURIComponent(id)}/receipt`;

export const toman = (amount: number) => new Intl.NumberFormat('fa-IR').format(amount);
export const groupedCard = (digits: string) => digits.replace(/\D/g, '').replace(/(.{4})/g, '$1 ').trim();
