import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/api-base-url', () => ({ apiBaseUrl: () => '/backend/api/v1' }));

import { createOrder, startZibalCheckout } from './client';

describe('billing payment selection API', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('sends the selected provider and stable idempotency key when creating an order', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      id: 'order-1', order_number: 'SHK-1', payment_method: 'ZIBAL', status: 'created',
      payment_attempt: null, plan_detail: { id: 'quarterly' }
    }), { status: 201, headers: { 'Content-Type': 'application/json' } }));

    await createOrder('quarterly', 'ZIBAL', 'checkout-click-12345678');

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/backend/api/v1/billing/orders');
    expect(init?.method).toBe('POST');
    expect(init?.headers).toMatchObject({
      'Content-Type': 'application/json',
      'Idempotency-Key': 'checkout-click-12345678'
    });
    expect(JSON.parse(String(init?.body))).toEqual({ plan_id: 'quarterly', payment_method: 'ZIBAL' });
  });

  it('uses the authenticated BFF path to resume an existing Zibal order', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      order: { id: 'order/with spaces', status: 'pending_payment' },
      payment_attempt: { status: 'PENDING', payment_url: 'https://gateway.zibal.ir/start/123' }
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

    const result = await startZibalCheckout('order/with spaces');

    expect(fetchMock.mock.calls[0][0]).toBe('/backend/api/v1/billing/orders/order%2Fwith%20spaces/checkout');
    expect(result.payment_attempt.payment_url).toBe('https://gateway.zibal.ir/start/123');
  });
});
