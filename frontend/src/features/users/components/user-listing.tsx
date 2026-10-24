import { HydrationBoundary, dehydrate } from '@tanstack/react-query';
import { getQueryClient } from '@/lib/query-client';
import { searchParamsCache } from '@/lib/searchparams';
import { usersQueryOptions } from '../api/queries';
import { getUsersForServer } from '../api/server-service';
import { UsersTable } from './users-table';

export default async function UserListingPage({
  showRoleBreakdown = false
}: {
  showRoleBreakdown?: boolean;
} = {}) {
  const page = searchParamsCache.get("page");
  const search = searchParamsCache.get("name");
  const pageLimit = searchParamsCache.get("perPage");
  const roles = searchParamsCache.get("role");
  const sort = searchParamsCache.get("sort");

  const filters = {
    page,
    limit: pageLimit,
    ...(search && { search }),
    ...(roles && { roles }),
    ...(sort && { sort })
  };

  const queryClient = getQueryClient();

  // The role histogram ships inside this same response, so the summary above
  // the table and the rows below it are always from one consistent snapshot.
  // Await the prefetch: the client below hydrates from this exact cache entry,
  // so a fire-and-forget here would leave the table on a *different* cache and
  // the new-user invalidation below would never refresh the visible rows.
  const options = usersQueryOptions(filters);
  const data = await getUsersForServer(filters);
  queryClient.setQueryData(options.queryKey, data);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <UsersTable showRoleBreakdown={showRoleBreakdown} />
    </HydrationBoundary>
  );
}
