import type { OverviewData } from './types';
import { apiClient } from '@/lib/api-client';

/**
 * Fetch overview statistics from the API
 */
export async function getOverviewData(): Promise<OverviewData> {
  return apiClient<OverviewData>('/statistics/overview');
}
