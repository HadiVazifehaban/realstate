import * as React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ensureMarketInventory } from '../api/client';
import { EmptyMarketCollector } from './empty-market-collector';

vi.mock('../api/client', () => ({ ensureMarketInventory: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function setup(cities: string[], empty: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const wrapper = ({ children }: React.PropsWithChildren) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, ...render(<EmptyMarketCollector cities={cities} empty={empty} />, { wrapper }) };
}

describe('empty market collection', () => {
  it('requests the selected empty city and renders actual collection status', async () => {
    vi.mocked(ensureMarketInventory).mockResolvedValue({ items: [{ city: 'مراغه', status: 'collecting', jobs: [] }] });
    const { client } = setup(['مراغه'], true);
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('در حال جمع‌آوری'));
    expect(ensureMarketInventory).toHaveBeenCalledExactlyOnceWith(['مراغه']);
    client.clear();
  });
  it('never requests a nationwide crawl', () => {
    const { client } = setup([], true);
    expect(ensureMarketInventory).not.toHaveBeenCalled();
    client.clear();
  });
  it('never crawls when results exist', () => {
    const { client } = setup(['مراغه'], false);
    expect(ensureMarketInventory).not.toHaveBeenCalled();
    client.clear();
  });
  it('shows failures instead of claiming that collection started', async () => {
    vi.mocked(ensureMarketInventory).mockRejectedValue(new Error('permission denied'));
    const { client } = setup(['مراغه'], true);
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('permission denied'));
    client.clear();
  });
});