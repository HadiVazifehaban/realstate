"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchSubscription } from "@/features/billing/api/client";

export function useCurrentSubscription(enabled: boolean) {
  const query = useQuery({
    queryKey: ["billing", "subscription"],
    queryFn: fetchSubscription,
    enabled,
    staleTime: 30_000
  });

  return {
    ...query,
    state: query.isPending ? "loading" : query.isError ? "error" : query.data ? "success" : "idle"
  } as const;
}
