'use client';

import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { getQueryClient } from '@/lib/query-client';
import CityQuerySync from '@/components/city/CityQuerySync';
import CityIdentityBinder from '@/components/city/CityIdentityBinder';
import type * as React from 'react';

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <CityIdentityBinder />
      <CityQuerySync />
      <ReactQueryDevtools />
    </QueryClientProvider>
  );
}
