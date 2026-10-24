"use client";

import * as React from 'react';
import dynamic from 'next/dynamic';
import { Icons } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  CITIES,
  DEFAULT_CITY,
  MEGA_CITIES,
  SATELLITE_CITIES,
  normalizePersian,
  toPersianDigits,
  type City
} from '../config/cities';
import { TILE_LAYER_LABEL } from '../config/tiles';
import type { LatLngLiteral } from '../types';

/** Leaflet reads `window` at module scope -- see picker-canvas.tsx. */
const PickerCanvas = dynamic(() => import("./picker-canvas"), {
  ssr: false,
  loading: () => <Skeleton className='h-full w-full' />
});

/**
 * Distance between two points in kilometres, haversine on a spherical earth.
 *
 * This is the whole of the "is the pin inside the city" check, and it is
 * explicitly *not* a PostGIS ST_Contains against the official boundary polygon:
 * no boundary table exists in the schema yet. So the component reports a
 * radius-based neighbourhood instead of claiming a boundary check it does not
 * perform -- an agent pricing a listing off a false "confirmed inside the city"
 * is worse off than with an honest approximation.
 */
function distanceKm(a: LatLngLiteral, b: LatLngLiteral): number {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** Beyond this the pin is almost certainly a geocoding slip, not a suburb. */
const PLAUSIBLE_RADIUS_KM = 60;

export type Verdict ='inside' | "near" | "outside";

function judge(city: City, point: LatLngLiteral): Verdict {
  const km = distanceKm({ lat: city.lat, lng: city.lng }, point);
  if (km <= PLAUSIBLE_RADIUS_KM) return "inside";
  if (km <= PLAUSIBLE_RADIUS_KM * 2) return "near";
  return "outside";
}

const VERDICT_LABEL: Record<Verdict, string> = {
  inside: "در محدوده شهر",
  near: "نزدیک شهر",
  outside: "خارج از محدوده"
};

export interface PickerResult {
  position: LatLngLiteral;
  districts: string[];
}

export function CityMapPicker({
  value,
  onChange,
  onConfirm
}: {
  value: LatLngLiteral;
  onChange: (next: LatLngLiteral) => void;
  onConfirm?: (result: PickerResult) => void;
}) {
  const [city, setCity] = React.useState<City>(DEFAULT_CITY);
  const [districts, setDistricts] = React.useState<string[]>([DEFAULT_CITY.districts[0]]);
  const [query, setQuery] = React.useState("");

  const verdict = judge(city, value);

  const selectCity = React.useCallback(
    (next: City) => {
      setCity(next);
      setDistricts([next.districts[0]]);
      setQuery("");
      onChange({ lat: next.lat, lng: next.lng });
    },
    [onChange]
  );

  // Live search matches the Persian name, the Latin transliteration and the
  // district list -- an advisor typing "pardis" or "فاز ۲" should both land.
  const results = React.useMemo(() => {
    const q = normalizePersian(query);
    if (!q) return [];
    return CITIES.filter(
      (item) =>
        normalizePersian(item.name).includes(q) ||
        item.latin.includes(query.trim().toLowerCase()) ||
        normalizePersian(item.province).includes(q) ||
        item.districts.some((d) => normalizePersian(d).includes(q))
    );
  }, [query]);

  const toggleDistrict = (name: string) => {
    setDistricts((prev) =>
      prev.includes(name) ? prev.filter((d) => d !== name) : [...prev, name]
    );
  };

  return (
    <div className='grid grid-cols-1 gap-4 lg:grid-cols-[22rem_1fr]'>
      <CitySidebar
        city={city}
        districts={districts}
        query={query}
        results={results}
        value={value}
        onQueryChange={setQuery}
        onSelectCity={selectCity}
        onToggleDistrict={toggleDistrict}
        onConfirm={onConfirm ? () => onConfirm({ position: value, districts }) : undefined}
        confirmDisabled={verdict ==='outside'}
      />

      <div className='border-border relative min-h-[26rem] overflow-hidden rounded-xl border'>
        <PickerCanvas
          center={{ lat: city.lat, lng: city.lng }}
          zoom={city.zoom}
          position={value}
          onPick={onChange}
        />

        <MapOverlays city={city} district={districts[0]} position={value} verdict={verdict} />
      </div>
    </div>
  );
}

function CitySidebar({
  city,
  districts,
  query,
  results,
  value,
  onQueryChange,
  onSelectCity,
  onToggleDistrict,
  onConfirm,
  confirmDisabled
}: {
  city: City;
  districts: string[];
  query: string;
  results: City[];
  value: LatLngLiteral;
  onQueryChange: (next: string) => void;
  onSelectCity: (city: City) => void;
  onToggleDistrict: (name: string) => void;
  onConfirm?: () => void;
  confirmDisabled: boolean;
}) {
  return (
    <div className='border-border bg-card/60 flex flex-col gap-4 rounded-xl border p-4 backdrop-blur-xl'>
      <div className='space-y-1'>
        <h2 className='text-base font-medium'>انتخاب محدوده</h2>
        <p className='text-muted-foreground text-xs'>نام شهر یا محله را جست‌وجو کنید</p>
      </div>

      <div className='relative'>
        <Icons.search className='text-primary absolute top-1/2 right-3 size-4 -translate-y-1/2' />
        <Input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder='مثلاً: سعادت‌آباد یا پردیس'
          className='pr-9'
          aria-label='جست‌وجوی شهر یا محله'
        />

        {results.length > 0 && (
          <div className='bg-popover absolute inset-x-0 top-full z-20 mt-1 overflow-hidden rounded-lg border shadow-lg'>
            {results.map((item) => (
              <button
                key={item.name}
                type='button'
                onClick={() => onSelectCity(item)}
                className='hover:bg-accent flex w-full items-center justify-between px-3 py-2 text-right text-xs'
              >
                <span>{item.name}</span>
                <span className='text-muted-foreground text-[10px]'>{item.province}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className='space-y-3'>
        <CityGrid
          title='کلان‌شهرهای پرجست‌وجو'
          cities={MEGA_CITIES}
          active={city}
          onSelect={onSelectCity}
        />
        <CityGrid
          title='شهرهای اقماری'
          cities={SATELLITE_CITIES}
          active={city}
          onSelect={onSelectCity}
        />
      </div>

      <div className='border-border/60 space-y-2 border-t pt-3'>
        <div className='flex items-center justify-between'>
          <span className='text-muted-foreground text-xs'>محله‌های {city.name}</span>
          <Badge variant='secondary' className='text-[10px]'>
            {toPersianDigits(districts.length)} انتخاب
          </Badge>
        </div>
        <div className='flex flex-wrap gap-1.5'>
          {city.districts.map((name) => (
            <button
              key={name}
              type='button'
              onClick={() => onToggleDistrict(name)}
              aria-pressed={districts.includes(name)}
              className={
                districts.includes(name)
                  ? "border-primary bg-primary/10 text-primary rounded-md border px-2 py-1 text-[11px]"
                  : "border-border hover:border-primary/50 rounded-md border px-2 py-1 text-[11px] opacity-70"
              }
            >
              {name}
            </button>
          ))}
        </div>
      </div>

      <div className='border-border/60 bg-muted/30 mt-auto space-y-2 rounded-lg border p-3'>
        <span className='text-muted-foreground text-[10px]'>محدوده انتخاب‌شده</span>
        <p className='text-sm font-medium'>
          {city.name}
          {districts.length > 0 && `، ${districts[0]}`}
        </p>
        <p className='text-muted-foreground font-mono text-[10px]' dir='ltr'>
          {value.lat.toFixed(4)}, {value.lng.toFixed(4)}
        </p>
      </div>

      {onConfirm && (
        <Button onClick={onConfirm} disabled={confirmDisabled}>
          تأیید محدوده و ادامه
        </Button>
      )}
    </div>
  );
}

function CityGrid({
  title,
  cities,
  active,
  onSelect
}: {
  title: string;
  cities: City[];
  active: City;
  onSelect: (city: City) => void;
}) {
  return (
    <div className='space-y-1.5'>
      <span className='text-muted-foreground text-[10px]'>{title}</span>
      <div className='grid grid-cols-3 gap-1.5'>
        {cities.map((item) => (
          <button
            key={item.name}
            type='button'
            onClick={() => onSelect(item)}
            aria-pressed={active.name === item.name}
            className={
              active.name === item.name
                ? "border-primary bg-primary/10 text-primary rounded-md border px-1 py-1.5 text-[11px]"
                : "border-border hover:border-primary/50 rounded-md border px-1 py-1.5 text-[11px]"
            }
          >
            {item.name}
            <span className='text-muted-foreground block text-[9px]'>{item.province}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function MapOverlays({
  city,
  district,
  position,
  verdict
}: {
  city: City;
  district?: string;
  position: LatLngLiteral;
  verdict: Verdict;
}) {
  return (
    <>
      <div className='bg-background/85 absolute top-3 right-3 left-3 flex items-center justify-between gap-2 text-[10px] backdrop-blur-md'>
        <span className='text-muted-foreground flex items-center gap-1.5 rounded-md border px-2 py-1.5'>
          <Icons.sparkles className='text-primary size-3' />
          {TILE_LAYER_LABEL}
        </span>
        <span className='text-muted-foreground flex items-center gap-1.5 rounded-md border px-2 py-1.5 font-mono'>
          <Icons.crosshair className='size-3' />
          <span dir='ltr'>
            {toPersianDigits(position.lat.toFixed(4))}° شمالی،{" "}
            {toPersianDigits(position.lng.toFixed(4))}° شرقی
          </span>
        </span>
      </div>

      <div
        className={`absolute bottom-3 left-3 flex items-center gap-2 rounded-md border px-3 py-2 text-[10px] backdrop-blur-md ${
          verdict ==='outside' ? "border-destructive/50 text-destructive" : "border-primary/40"
        }`}
      >
        {verdict ==='outside' ? (
          <Icons.warning className='size-3.5' />
        ) : (
          <Icons.mapPin className='text-primary size-3.5' />
        )}
        <span>
          {VERDICT_LABEL[verdict]} · {city.name}، {district ?? "محدوده انتخابی"}
        </span>
      </div>
    </>
  );
}
