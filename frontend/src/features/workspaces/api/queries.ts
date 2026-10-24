import { queryOptions } from '@tanstack/react-query';

import { usersQueryOptions } from '@/features/users/api/queries';

import { fetchLicenseStatus } from './client';

export const workspacesKeys = {
  all: ['workspaces'] as const,
  license: () => [...workspacesKeys.all, 'license'] as const
};

export const licenseStatusQueryOptions = () =>
  queryOptions({
    queryKey: workspacesKeys.license(),
    queryFn: () => fetchLicenseStatus()
  });

/**
 * The office roster, through the users feature's own query factory.
 *
 * Only the summary is needed here (total + `role_breakdown`), so it asks for a
 * single row. Going through the same factory rather than calling the endpoint
 * directly is what keeps these counts identical to the directory's: one mapper,
 * one envelope, no second interpretation of the backend's role names.
 *
 * The filter set deliberately differs from the users table's default, so this
 * entry is its own cache key and paginating that table cannot page this card.
 */
export const officeRosterQueryOptions = () =>
  usersQueryOptions({ page: 1, limit: 1 });
