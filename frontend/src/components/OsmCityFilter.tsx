'use client';

import * as React from 'react';
import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { useGisAreas, useInventoryCities } from '@/features/properties/hooks';

/**
 * City picker for the listing filter, driven by the node's GIS gateway.
 *
 * The provinces and cities arrive from `/api/v1/gis/cities`, already normalized
 * and deduplicated server-side, so what the user reads is exactly the
 * `Property.city` string the node stores. A filter on a name the crawler never
 * wrote matches nothing -- which is what the old hard-coded button row did on
 * any city outside its fixed six.
 *
 * The gateway prefers the self-hosted Iran Locations dataset and falls back to
 * OpenStreetMap, so the list needs no platform key.
 *
 * Picking a suburb reports that canonical name back. Picking a *province*
 * narrows the list to that province's cities, which is enough to step down to a
 * neighbourhood without a second dropdown.
 */
export interface OsmCityFilterProps {
  /** Currently applied city name, or undefined for 'all cities'. */
  value?: string;
  onChange: (city: string | undefined) => void;
  className?: string;
}

export function OsmCityFilter({ value, onChange, className }: OsmCityFilterProps) {
  const { data, isPending, isError } = useGisAreas();
  const inventoryCitiesQuery = useInventoryCities();

  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState('');

  const provinces = React.useMemo(() => data?.provinces ?? [], [data]);
  const allCities = React.useMemo(() => data?.cities ?? [], [data]);

  /**
   * Fallback pool when the GIS gateway has nothing to offer -- the Iran
   * Locations container and the OSM fallback both failed, so the flattened
   * list comes back empty. Cities read off the node's own inventory are always
   * filterable, so the dropdown stays useful on an office LAN install.
   */
  const inventoryCities = React.useMemo(
    () => inventoryCitiesQuery.data?.cities ?? [],
    [inventoryCitiesQuery.data]
  );
  const usingInventoryFallback = allCities.length === 0 && inventoryCities.length > 0;

  /**
   * The province the current selection sits in, so a listing filtered on, say,
   * 'کرج' offers the rest of Alborz underneath it rather than the whole country.
   */
  const activeProvince = React.useMemo(
    () => provinces.find((p) => p.name === value || p.cities.includes(value ?? '')),
    [provinces, value]
  );

  /** Cities on screen: the active province's when one is selected, otherwise all. */
  const visibleCities = React.useMemo(() => {
    const pool = activeProvince ? activeProvince.cities : usingInventoryFallback ? inventoryCities : allCities;
    const q = query.trim();
    return q ? pool.filter((city) => city.includes(q)) : pool;
  }, [activeProvince, allCities, inventoryCities, usingInventoryFallback, query]);

  /**
   * Provinces offered when no city is applied. Only the ones with cities to
   * show are offered -- a province with an empty list would be a dead row.
   */
  const visibleProvinces = React.useMemo(() => {
    if (usingInventoryFallback) return [];
    const q = query.trim();
    const pool = provinces.filter((p) => p.cities.length > 0);
    return q ? pool.filter((p) => p.name.includes(q)) : pool;
  }, [provinces, query, usingInventoryFallback]);

  const label = value ?? 'همهٔ شهرها';

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      const trimmed = query.trim();
      if (trimmed) {
        // Treat the typed value as the city selection
        onChange(trimmed);
        setOpen(false);
      }
    }
  };

  const selectCity = (city: string) => {
    onChange(city === value ? undefined : city);
    setOpen(false);
    setQuery('');
  };

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setQuery('');
      }}
    >
      <PopoverTrigger
        render={
          <Button
            variant='outline'
            size='sm'
            role='combobox'
            aria-expanded={open}
            className={cn('min-w-40 justify-between gap-2 text-xs font-normal', className)}
          >
            <Icons.mapPin className='text-gold-accent size-3.5' aria-hidden />
            <span className={cn(!value && 'text-muted-foreground')}>{label}</span>
            <Icons.chevronDown className='size-3.5 opacity-50' aria-hidden />
          </Button>
        }
      />

      <PopoverContent align='start' className='w-64 p-0'>
        <Command shouldFilter={false}>
          {/* `shouldFilter={false}` because the list is filtered here: the pool
              switches between 'all cities' and "one province's cities", and the
              built-in filter would only search the rows it was handed. */}
           <CommandInput
             placeholder='جست‌وجوی شهر یا استان…'
             value={query}
             onValueChange={setQuery}
             onKeyDown={handleKeyDown}
           />
          <CommandList>
            {/*
              Three dead ends, three different sentences. The middle one is the
              case an office LAN install actually hits -- the GIS gateway and
              the inventory both silent -- so it says what is being used
              instead rather than showing an empty list.
            */}
            <CommandEmpty>
              {isPending
                ? 'در حال دریافت فهرست شهرها…'
                : usingInventoryFallback
                  ? 'شهری با این نام در آگهی‌های دفتر پیدا نشد.'
                  : isError
                    ? 'دریافت فهرست شهرها از سرویس نقشه ناموفق بود.'
                    : 'شهری با این نام پیدا نشد.'}
            </CommandEmpty>

            {usingInventoryFallback && (
              <p className='text-muted-foreground border-b px-3 py-2 text-[11px] leading-relaxed'>
                سرویس نقشه در دسترس نیست؛ فهرست از روی آگهی‌های همین دفتر ساخته شده است.
              </p>
            )}

            {/*
              The inventory fallback also covers a hard gateway failure --
              Nominatim and Overpass fail as readily as they answer -- so it is
              not gated behind `!isError`.
            */}
            {(usingInventoryFallback || (!isPending && !isError)) && (
              <>
                {visibleCities.map((city) => (
                  <CommandItem
                    key={city}
                    value={city}
                    onSelect={() => selectCity(city)}
                  >
                    <Icons.check
                      className={cn('size-3.5', value === city ? 'opacity-100' : 'opacity-0')}
                      aria-hidden
                    />
                    {city}
                  </CommandItem>
                ))}

                {visibleProvinces.map((province) => (
                  <CommandGroup key={province.name}>
                    <CommandItem
                      value={`province:${province.name}`}
                      onSelect={() => {
                        // Narrowing to a province is a navigation step, not a
                        // city selection; leave the popover open for city choice.
                        onChange(province.cities[0]);
                        setQuery('');
                      }}
                      className='text-muted-foreground'
                    >
                      <Icons.chevronLeft className='size-3.5 opacity-60' aria-hidden />
                      همهٔ شهرهای {province.name}
                    </CommandItem>
                  </CommandGroup>
                ))}
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export default OsmCityFilter;
