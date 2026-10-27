import * as React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ReportsView } from './reports-view';

const state = vi.hoisted(() => ({
  query: vi.fn(),
  result: {
    isPending: false, isError: false, refetch: vi.fn(),
    data: {
      shares_by_status: [{ status: 'ACTIVE', label_fa: 'فعال', count: 1 }],
      referrals_by_stage: [], transfers_by_status: [], commissions_by_status: [],
      disputes_by_status: [], cooperations_by_status: [], audit_by_action: [],
      total_basis: 987654321, total_paid: 987654320, total_remaining: 1, conversion_rate_pct: 25
    }
  }
}));
vi.mock('@/features/network/hooks', () => ({ useNetworkReports: (params: unknown) => {
  state.query(params);
  return state.result;
} }));
vi.mock('recharts', () => {
  const Container = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;
  return Object.fromEntries(['Bar', 'BarChart', 'CartesianGrid', 'Cell', 'Pie', 'PieChart', 'ResponsiveContainer', 'Tooltip', 'XAxis', 'YAxis'].map(key => [key, Container]));
});
afterEach(() => { cleanup(); state.result.isError = false; state.result.isPending = false; });

it('keeps the real scoped counts but never renders uncertain money as financial results', () => {
  render(<ReportsView />);
  expect(state.query).toHaveBeenCalledWith({ agencyId: undefined });
  expect(screen.getByText('فعال')).toBeTruthy();
  expect(screen.getByText('نیازمند تأیید واحد پول')).toBeTruthy();
  expect(screen.getByText('فعلاً قابل اتکا نیست')).toBeTruthy();
  expect(screen.getByRole('note').textContent).toContain('مبلغ پایه درآمد دفتر نیست');
  expect(screen.queryByText(/۹۸۷/)).toBeNull();
  expect(screen.getByText('25٪')).toBeTruthy();
});

it('does not render cached confidential results after an authorization failure', () => {
  state.result.isError = true;
  render(<ReportsView />);
  expect(screen.queryByText('فعال')).toBeNull();
  expect(screen.queryByText('25٪')).toBeNull();
});