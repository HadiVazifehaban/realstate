import { apiBaseUrl } from '@/lib/api-base-url';

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

export type PaymentOrder = {
  id: string;
  order_number: string;
  plan: string;
  amount_toman: number;
  environment_mode: 'test' | 'live';
  is_test: boolean;
  status: string;
  card_number: string | null;
  card_last4: string | null;
  card_holder: string | null;
  card_configured: boolean;
  test_warning: string | null;
  created_at: string;
  expires_at: string;
  submitted_at: string | null;
  receipt?: {
    original_filename: string;
    content_type: string;
    file_size: number;
    transfer_tracking_number: string;
    transfer_datetime: string;
  } | null;
};

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
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    cache: 'no-store',
    ...init,
    headers: { ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...init.headers }
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

export const fetchPlans = () => request<{ plans: BillingPlan[] }>('/billing/plans');
export const fetchOrders = () => request<{ items: PaymentOrder[]; page: number; page_size: number }>('/billing/orders');
export const fetchSubscription = () => request<Subscription>('/billing/subscriptions/current');
export const createOrder = (planId: string) => request<PaymentOrder & { plan_detail: BillingPlan }>('/billing/orders', {
  method: 'POST', body: JSON.stringify({ plan_id: planId })
});
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

export function fetchFinancialQueue() {
  return request<{ items: PaymentOrder[]; page: number; page_size: number }>('/admin/financial/payment-orders');
}
export const approveTestOrder = (id: string) => request<PaymentOrder>(`/admin/financial/payment-orders/${encodeURIComponent(id)}/approve`, { method: 'POST' });
export const rejectOrder = (id: string, reason: string) => request<PaymentOrder>(`/admin/financial/payment-orders/${encodeURIComponent(id)}/reject`, {
  method: 'POST', body: JSON.stringify({ reason })
});
export const receiptUrl = (id: string) => `${apiBaseUrl()}/admin/financial/payment-orders/${encodeURIComponent(id)}/receipt`;

export const toman = (amount: number) => new Intl.NumberFormat('fa-IR').format(amount);
export const groupedCard = (digits: string) => digits.replace(/\D/g, '').replace(/(.{4})/g, '$1 ').trim();