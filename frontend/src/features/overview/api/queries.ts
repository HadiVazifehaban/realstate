import { queryOptions } from '@tanstack/react-query';
import { getOverviewData } from './service';

export const overviewKeys = {
  all: ['overview'] as const,
  data: () => [...overviewKeys.all, 'data'] as const
};

export const overviewDataQueryOptions = () =>
  queryOptions({
    queryKey: overviewKeys.data(),
    queryFn: getOverviewData,
    staleTime: 1000 * 60 * 5 // 5 minutes
  });
