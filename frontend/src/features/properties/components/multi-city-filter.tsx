'use client';

import * as React from 'react';
import { Icons } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover';
import { toPersianDigits, cn } from '@/lib/utils';
import { useGisAreas, useInventoryCities } from '../hooks';

/**
 * The market filter: pick any mix of provinces and cities.
 *
 * **Why multi-select.** A desk's market is almost never one city: a Tehran
 * advisor works the capital and its satellites, a Mashhad one the city and its
 * counties. The old single-select made that impossible without reloading the
 * page between cities, so a six-city buyer's brief was six separate feeds.
 *
 * **Why provinces too.** Picking a province is shorthand for every county in
 * it, which is exactly what an advisor means by «آذربایجان شرقی» — they do not
 * want to enumerate twelve counties by hand. Selecting one therefore expands to
 * those counties, and the parents stay ticked while all their children are.
 *
 * The applied value is a flat list of *cities*, never provinces: the node
 * filters on `Property.city`, so a province that arrived as-is would match
 * nothing. Expansion happens here, in the UI, where the tree is known.
 */

/**
 * One province and the cities it carries, exactly as the node sends it:
 * ``{ name, cities: string[] }``.
 *
 * Deliberately the *response* shape rather than a nested tree of children. The
 * gateway's contract is `cities` (see `GisAreaProvince`), and reading it as
 * `children` silently dropped every county from the picker: the province row
 * remained, so selecting a province appeared to work, while the cities it was
 * supposed to carry never appeared at all.
 */
interface CityNode {
  name: string;
  /** Cities under this province. Absent for a standalone city. */
  cities?: string[];
}

export interface MultiCityFilterProps {
  /** Applied cities; empty means every city is in scope. */
  cities: string[];
  onCities: (cities: string[]) => void;
  disabled?: boolean;
  className?: string;
}

/** Every city a node carries; a standalone city is its own list. */
function citiesOf(node: CityNode): string[] {
  return node.cities?.length ? node.cities : [node.name];
}

export function MultiCityFilter({
  cities,
  onCities,
  disabled,
  className
}: MultiCityFilterProps) {
  const { data } = useGisAreas();
  const inventoryQuery = useInventoryCities();
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState('');
  /**
   * Which province's counties are on screen, or null for the province list.
   *
   * Closes with the panel so reopening the picker starts where the advisor
   * left the market rather than deep inside one province's counties.
   */
  const [drilled, setDrilled] = React.useState<CityNode | null>(null);

  /**
   * The province → counties tree, from the node's own GIS gateway.
   *
   * Cities the gateway never lists still belong in the picker, so the node's
   * own inventory is merged in as flat entries: a city the office already
   * holds listings for is filterable even when the locations dataset is
   * silent about it.
   */
  const tree = React.useMemo<CityNode[]>(() => {
    const provinces = (data?.provinces ?? []) as CityNode[];
    const known = new Set(provinces.flatMap((province) => citiesOf(province)));
    const extra = (inventoryQuery.data?.cities ?? [])
      .filter((city: string) => !known.has(city))
      .map((city: string) => ({ name: city }));
    return [...provinces, ...extra];
  }, [data, inventoryQuery.data]);

  const selected = React.useMemo(() => new Set(cities), [cities]);
  const searching = query.trim().length > 0;

  /**
   * Flat matches for a search: the province plus any of its counties that
   * matched, and standalone cities that matched.
   */
  const searchMatches = React.useMemo(() => {
    const needle = query.trim();
    if (!needle) return [];
    return tree
      .map((node) => {
        const cities = citiesOf(node);
        if (cities.length === 1 && cities[0] === node.name) {
          return node.name.includes(needle) ? node : null;
        }
        if (node.name.includes(needle)) return node;
        const kids = cities.filter((city) => city.includes(needle));
        return kids.length ? { ...node, cities: kids } : null;
      })
      .filter((node): node is CityNode => node !== null);
  }, [tree, query]);

  /**
   * The top level: the tree in its stored order -- provinces first, then the
   * cities the node holds listings for but the locations dataset knows no
   * province for. The render tells the two apart (a node whose only city is
   * itself has nothing to drill into), so both stay reachable here.
   *
   * Filtering the loose cities out would make them reachable only by search,
   * which is how a market the office actively works goes missing from a picker
   * whose job is to list it.
   */
  const topLevel = React.useMemo(() => tree, [tree]);

  /** Province → whether all of its counties are applied. */
  const provinceState = React.useMemo(() => {
    const state = new Map<string, 'all' | 'some' | 'none'>();
    for (const province of tree) {
      const cities = citiesOf(province);
      if (cities.length < 2 && cities[0] === province.name) continue;
      const picked = cities.filter((city) => selected.has(city)).length;
      state.set(
        province.name,
        picked === 0 ? 'none' : picked === cities.length ? 'all' : 'some'
      );
    }
    return state;
  }, [tree, selected]);

  const toggleCity = (city: string) => {
    const next = new Set(selected);
    if (next.has(city)) next.delete(city);
    else next.add(city);
    onCities([...next]);
  };

  /** A province adds or drops every city it carries. */
  const toggleProvince = (province: CityNode) => {
    const next = new Set(selected);
    const cities = citiesOf(province);
    const allOn = cities.every((city) => next.has(city));
    for (const city of cities) {
      if (allOn) next.delete(city);
      else next.add(city);
    }
    onCities([...next]);
  };

  const label =
    cities.length === 0
      ? 'همهٔ شهرها'
      : cities.length === 1
        ? cities[0]
        : `${cities[0]} + ${toPersianDigits((cities.length - 1).toLocaleString('en-US'))} شهر`;

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setDrilled(null);
      }}
    >
      <PopoverTrigger
        render={
          <Button
            variant='outline'
              size='sm'
              disabled={disabled}
              className='gap-1.5'
              aria-label='انتخاب شهر یا استان'
            >
              <Icons.mapPin className='size-3.5' aria-hidden />
              <span className='max-w-40 truncate'>{label}</span>
              {cities.length > 0 && (
                <Badge
                  variant='secondary'
                  className='h-4 rounded-full px-1.5 text-[10px]'
                >
                  {toPersianDigits(cities.length.toLocaleString('en-US'))}
                </Badge>
              )}
              <Icons.chevronDown className='size-3.5 opacity-60' aria-hidden />
            </Button>
          }
        />

        <PopoverContent align='start' className='w-72 p-0'>
          <Command shouldFilter={false}>
            <CommandInput
              value={query}
              onValueChange={setQuery}
              placeholder='جست‌وجوی شهر یا استان…'
            />
              <CommandList className='max-h-72'>
              <CommandEmpty>شهری با این نام پیدا نشد.</CommandEmpty>

              {/*
                Two levels, one list. Provinces first, counties only after a
                province is opened -- the panel is 288px wide, and showing
                thirty provinces each with its counties underneath made it a
                scroll of the whole country when the advisor had already
                decided on a province.
              */}
              {searching ? (
                // A search is a flat lookup: narrowing it to the open province
                // would hide a county the advisor named in another one.
                searchMatches.map((node) => {
                  const cities = citiesOf(node);
                  const standalone = cities.length === 1 && cities[0] === node.name;
                  if (standalone) {
                    return (
                      <CommandItem
                        key={node.name}
                        value={node.name}
                        onSelect={() => toggleCity(node.name)}
                      >
                        <Checkbox
                          checked={selected.has(node.name)}
                          className='size-3.5'
                          aria-label={node.name}
                        />
                        {node.name}
                      </CommandItem>
                    );
                  }
                  return (
                    <CommandGroup key={node.name} heading={node.name}>
                      <CommandItem
                        value={`province:${node.name}`}
                        onSelect={() => toggleProvince(node)}
                      >
                        <span className='relative flex size-3.5 items-center justify-center'>
                          {provinceState.get(node.name) === 'some' && (
                            <span className='bg-gold-accent size-1.5 rounded-full' />
                          )}
                        </span>
                        <Checkbox
                          checked={provinceState.get(node.name) === 'all'}
                          className='sr-only'
                          aria-label={`همهٔ شهرهای ${node.name}`}
                        />
                        همهٔ شهرهای {node.name}
                      </CommandItem>
                      {cities.map((city) => (
                        <CommandItem
                          key={city}
                          value={city}
                          onSelect={() => toggleCity(city)}
                        >
                          <Checkbox
                            checked={selected.has(city)}
                            className='size-3.5'
                            aria-label={city}
                          />
                          {city}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  );
                })
              ) : drilled ? (
                <>
                  <CommandItem value='__back' onSelect={() => setDrilled(null)}>
                    <Icons.chevronRight className='size-3.5 opacity-60' aria-hidden />
                    همهٔ استان‌ها
                  </CommandItem>
                  <CommandItem
                    value={`province:${drilled.name}`}
                    onSelect={() => toggleProvince(drilled)}
                  >
                    <span className='relative flex size-3.5 items-center justify-center'>
                      {provinceState.get(drilled.name) === 'some' && (
                        <span className='bg-gold-accent size-1.5 rounded-full' />
                      )}
                    </span>
                    <Checkbox
                      checked={provinceState.get(drilled.name) === 'all'}
                      className='sr-only'
                      aria-label={`همهٔ شهرهای ${drilled.name}`}
                    />
                    همهٔ شهرهای {drilled.name}
                  </CommandItem>
                  {citiesOf(drilled).map((city) => (
                    <CommandItem
                      key={city}
                      value={city}
                      onSelect={() => toggleCity(city)}
                    >
                      <Checkbox
                        checked={selected.has(city)}
                        className='size-3.5'
                        aria-label={city}
                      />
                      {city}
                    </CommandItem>
                  ))}
                </>
              ) : (
                topLevel.map((node) => {
                  const cities = citiesOf(node);
                  const standalone = cities.length === 1 && cities[0] === node.name;
                  if (standalone) {
                    // A city the node holds listings for but the locations
                    // dataset knows no province for is still pickable.
                    return (
                      <CommandItem
                        key={node.name}
                        value={node.name}
                        onSelect={() => toggleCity(node.name)}
                      >
                        <Checkbox
                          checked={selected.has(node.name)}
                          className='size-3.5'
                          aria-label={node.name}
                        />
                        {node.name}
                      </CommandItem>
                    );
                  }
                  const chosen = cities.filter((city) => selected.has(city)).length;
                  return (
                    <CommandItem
                      key={node.name}
                      value={`open:${node.name}`}
                      onSelect={() => setDrilled(node)}
                    >
                      <span className='flex-1 truncate'>{node.name}</span>
                      {chosen > 0 && chosen < cities.length && (
                        <span className='bg-gold-accent size-1.5 shrink-0 rounded-full' />
                      )}
                      {chosen === cities.length && (
                        <Icons.check className='text-gold-primary size-3.5 shrink-0' aria-hidden />
                      )}
                      <span className='text-muted-foreground shrink-0 text-[10px] tabular-nums'>
                        {toPersianDigits(cities.length.toLocaleString('en-US'))}
                      </span>
                      <Icons.chevronLeft className='size-3.5 shrink-0 opacity-60' aria-hidden />
                    </CommandItem>
                  );
                })
              )}
            </CommandList>
          </Command>

          <div className='border-t p-2'>
            <Button
              variant='ghost'
              size='sm'
              className='w-full'
              onClick={() => onCities([])}
              disabled={cities.length === 0}
            >
              پاک کردن انتخاب شهرها
            </Button>
          </div>
        </PopoverContent>
      </Popover>
  );
}

export default MultiCityFilter;
