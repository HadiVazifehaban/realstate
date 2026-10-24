import * as React from 'react';
import { cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/client', () => ({ fetchProperties: vi.fn(async () => ({ items: [], count: 0 })) }));
import { fetchProperties } from '../api/client';
import { useProperties } from './index';

describe('properties query city hydration', () => {
  afterEach(cleanup);
  it('keeps hook order stable and fetches only after the city is ready', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: React.PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { result, rerender } = renderHook(({ enabled }) => {
      const query = useProperties({ city: 'تهران' }, enabled);
      const [mounted] = React.useState(true);
      React.useEffect(() => {}, [mounted]);
      return query;
    }, { initialProps: { enabled: false }, wrapper });
    expect(fetchProperties).not.toHaveBeenCalled();
    rerender({ enabled: true });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchProperties).toHaveBeenCalledWith({ city: 'تهران' });
    rerender({ enabled: false });
    expect(result.current.isError).toBe(false);
    client.clear();
  });
});