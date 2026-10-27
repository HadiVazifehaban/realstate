"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { IconBuilding, IconPlus, IconSearch, IconX } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { useDebounce } from "@/hooks/use-debounce";
import { useAgencies, useCreateCooperation } from "@/features/network/hooks";
import {
  AgencyStatusBadge,
  ListEmpty,
  ListError,
  ListSkeleton
} from "@/features/network/components/shared";
import type { Agency } from "@/features/network/types";
import { OsmCityFilter } from "@/components/OsmCityFilter";
import { NetworkStats } from "@/features/network/components/network-page";

const STATUS_FILTERS = [
  { value: "ALL", label: "همهٔ دفاتر" },
  { value: "VERIFIED", label: "بررسی‌شده در سامانه" },
  { value: "PENDING", label: "در انتظار تأیید" },
  { value: "SUSPENDED", label: "معلق" }
] as const;

/**
 * فهرست دفاتر همکار — مستقیم از API واقعی `/network/agencies`.
 *
 * دفترِ خودِ کاربر در کارت نشان داده می‌شود اما «درخواست همکاری» برایش غیرفعال
 * است، چون دفتر نمی‌تواند با خودش همکاری کند.
 */
export function NetworkAgenciesList({
  currentAgencyId
}: {
  /** شناسهٔ دفترِ جاری کاربر — برای غیرفعال‌کردن درخواست روی کارت خودی. */
  currentAgencyId?: string | null;
}) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [query, setQuery] = React.useState(searchParams.get("q") ?? "");
  const [status, setStatus] = React.useState(searchParams.get("status") ?? "ALL");
  const lastLocationSearch = React.useRef(searchParams.toString());
  const [city, setCity] = React.useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("selected_city") ?? "";
    }
    return "";
  });
  const debouncedQuery = useDebounce(query, 350);

  React.useEffect(() => {
    const locationSearch = searchParams.toString();
    if (locationSearch !== lastLocationSearch.current) {
      lastLocationSearch.current = locationSearch;
      const params = new URLSearchParams(locationSearch);
      setQuery(params.get("q") ?? "");
      setStatus(params.get("status") ?? "ALL");
    }
  }, [searchParams]);

  React.useEffect(() => {
    const next = new URLSearchParams(searchParams.toString());
    if (debouncedQuery) next.set("q", debouncedQuery);
    else next.delete("q");
    if (status !== "ALL") next.set("status", status);
    else next.delete("status");
    const nextQuery = next.toString();
    if (nextQuery !== searchParams.toString()) {
      lastLocationSearch.current = nextQuery;
      router.replace(nextQuery ? `?${nextQuery}` : "?", { scroll: false });
    }
  }, [debouncedQuery, router, searchParams, status]);

  const {
    data: agencies,
    isPending,
    isError,
    refetch
  } = useAgencies({
    q: debouncedQuery || undefined,
    status: status === "ALL" ? undefined : status,
    city: city || undefined
  });

  const createCooperation = useCreateCooperation();

  const handleRequestCooperation = (targetAgencyId: string) => {
    if (!currentAgencyId) return;
    createCooperation.mutate(
      {
        requester_agency_id: currentAgencyId,
        target_agency_id: targetAgencyId,
        scope: "SHARE_LISTINGS",
        expires_in_days: 30
      },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries({ queryKey: ["network", "cooperations"] });
        }
      }
    );
  };

  const handleCityChange = (newCity: string | undefined) => {
    const cityValue = newCity ?? "";
    setCity(cityValue);
    if (cityValue) {
      localStorage.setItem("selected_city", cityValue);
    } else {
      localStorage.removeItem("selected_city");
    }
  };

  return (
    <div className="space-y-5">
      {!isPending && !isError && (
        <NetworkStats
          items={[
            { label: "دفاتر در نتایج فعلی", value: agencies?.length ?? 0 },
            {
              label: "بررسی‌شده در سامانه",
              value: agencies?.filter((agency) => agency.status === "VERIFIED").length ?? 0
            },
            {
              label: "شهرهای نتایج",
              value: new Set(agencies?.map((agency) => agency.city).filter(Boolean)).size
            },
            {
              label: "در انتظار تأیید",
              value: agencies?.filter((agency) => agency.status === "PENDING").length ?? 0
            }
          ]}
        />
      )}
      <div className="flex flex-col gap-3 rounded-2xl border bg-card p-4 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <IconSearch className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="جستجو بر اساس نام دفتر، شهر یا منطقه…"
            className="pr-9"
            aria-label="جستجوی دفتر همکار"
          />
        </div>
        <div className="flex w-full gap-2 sm:w-72">
          <div className="min-w-0 flex-1">
            <OsmCityFilter
              value={city || undefined}
              onChange={(c) => handleCityChange(c)}
              className="w-full"
            />
          </div>
          {query || city || status !== "ALL" ? (
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="پاک‌کردن فیلترها"
              title="پاک‌کردن فیلترها"
              onClick={() => {
                setQuery("");
                setCity("");
                setStatus("ALL");
                localStorage.removeItem("selected_city");
              }}
            >
              <IconX className="h-4 w-4" />
            </Button>
          ) : null}
        </div>
        <Select value={status} onValueChange={(value) => setStatus(value ?? "ALL")}>
          <SelectTrigger className="w-full sm:w-48" aria-label="فیلتر وضعیت">
            <SelectValue placeholder="وضعیت" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_FILTERS.map((f) => (
              <SelectItem key={f.value} value={f.value}>
                {f.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isPending ? <ListSkeleton rows={6} /> : null}
      {isError ? <ListError onRetry={() => void refetch()} /> : null}

      {!isPending && !isError && (agencies?.length ?? 0) === 0 ? (
        <ListEmpty
          title="دفتری پیدا نشد"
          description="با تغییر عبارت جستجو یا فیلتر وضعیت یا شهر، دفاتر بیشتری را ببینید."
        />
      ) : null}

      {!isPending && !isError && (agencies?.length ?? 0) > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agencies!.map((agency) => (
            <AgencyCard
              key={agency.id}
              agency={agency}
              isSelf={agency.id === currentAgencyId}
              onRequest={() => handleRequestCooperation(agency.id)}
              pending={createCooperation.isPending}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function AgencyCard({
  agency,
  isSelf,
  onRequest,
  pending
}: {
  agency: Agency;
  isSelf: boolean;
  onRequest: () => void;
  pending: boolean;
}) {
  const router = useRouter();
  return (
    <Card className="flex flex-col border border-border bg-card transition-colors hover:border-primary/40">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between gap-2 text-base">
          <span className="flex items-center gap-2 truncate">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <IconBuilding className="size-5" aria-hidden="true" />
            </span>
            <span className="truncate" dir="auto">
              {agency.name_fa || agency.name}
            </span>
          </span>
          <AgencyStatusBadge status={agency.status} />
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3 text-sm">
        <p className="text-muted-foreground" dir="auto">
          {agency.city}، {agency.district}
        </p>
        {agency.description ? (
          <p className="line-clamp-2 text-muted-foreground" dir="auto">
            {agency.description}
          </p>
        ) : null}
        <div className="mt-auto flex gap-2 pt-2">
          <Button
            size="sm"
            variant="outline"
            className="flex-1"
            onClick={() => router.push(`/dashboard/network/agencies/${agency.id}`)}
          >
            مشاهده پروفایل
          </Button>
          {isSelf ? (
            <span className="flex flex-1 items-center justify-center rounded-md bg-muted px-3 text-xs text-muted-foreground">
              دفتر شما
            </span>
          ) : (
            <Button size="sm" className="flex-1" disabled={pending} onClick={onRequest}>
              <IconPlus className="ml-1 h-3.5 w-3.5" />
              درخواست همکاری
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
