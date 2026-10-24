'use client';

import * as React from 'react';
import dynamic from 'next/dynamic';
import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

/**
 * Pure Leaflet + OpenStreetMap location picker for the property submission form.
 *
 * Uses the node's self-hosted OSM tile server over the node's internal OSM
 * raster tiles (see features/map/config/tiles). No vendor map API key:
 * tiles are loaded from NEXT_PUBLIC_TILE_URL and coordinate selection is fully
 * client-side.
 *
 * Features:
 *  - Drag the pin or click the map to place a coordinate.
 *  - Type latitude/longitude manually.
 *  - GPS auto-pin button centers the map on the browser's current position and
 *    lets the advisor drop the pin there (requires geolocation permission).
 */

const PickerCanvas = dynamic(() => import('@/features/map/components/picker-canvas'), {
  ssr: false,
  loading: () => <Skeleton className='h-full w-full' />
});

/** Tehran city centre -- the form starts somewhere every agent recognises. */
const DEFAULT_CENTER = { lat: 35.6892, lng: 51.389 };

export interface LocationPickerProps {
  value?: { lat: number; lng: number };
  onChange?: (lat: number, lng: number) => void;
  className?: string;
  height?: string;
}

export function OsmLocationPicker({
  value,
  onChange,
  className,
  height = '400px'
}: LocationPickerProps) {
  const [position, setPosition] = React.useState(value ?? DEFAULT_CENTER);
  const [gpsLoading, setGpsLoading] = React.useState(false);
  const [gpsError, setGpsError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (value) setPosition(value);
  }, [value]);

  const handlePick = React.useCallback(
    (next: { lat: number; lng: number }) => {
      setPosition(next);
      setGpsError(null);
      onChange?.(next.lat, next.lng);
    },
    [onChange]
  );

  const handleManualLat = (nextLat: number) => {
    setGpsError(null);
    handlePick({ lat: nextLat, lng: position.lng });
  };

  const handleManualLng = (nextLng: number) => {
    setGpsError(null);
    handlePick({ lat: position.lat, lng: nextLng });
  };

  const useCurrentLocation = React.useCallback(() => {
    setGpsLoading(true);
    setGpsError(null);

    if (!navigator.geolocation) {
      setGpsError('مرورگر شما از موقعیت مکانی پشتیبانی نمی‌کند.');
      setGpsLoading(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const next = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        handlePick(next);
        setGpsLoading(false);
      },
      (err) => {
        const message =
          err.code === err.PERMISSION_DENIED
            ? 'اجازهٔ دسترسی به موقعیت مکانی داده نشد.'
            : err.code === err.POSITION_UNAVAILABLE
              ? 'اطلاعات موقعیت در دسترس نیست.'
              : err.code === err.TIMEOUT
                ? 'درخواست موقعیت به وقت‌شناسی انجامید.'
                : 'خطا در دریافت موقعیت مکانی.';
        setGpsError(message);
        setGpsLoading(false);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
    );
  }, [handlePick]);

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      <div className='flex items-center justify-between gap-2'>
        <div className='flex items-center gap-2'>
          <Label htmlFor='local-latitude'>عرض جغرافیایی</Label>
          <Input
            id='local-latitude'
            type='number'
            step='0.000001'
            min={-90}
            max={90}
            value={position.lat}
            onChange={(event) => handleManualLat(Number(event.target.value))}
            className='w-28'
          />
        </div>
        <div className='flex items-center gap-2'>
          <Label htmlFor='local-longitude'>طول جغرافیایی</Label>
          <Input
            id='local-longitude'
            type='number'
            step='0.000001'
            min={-180}
            max={180}
            value={position.lng}
            onChange={(event) => handleManualLng(Number(event.target.value))}
            className='w-32'
          />
        </div>
      </div>

      <div
        className={cn(
          'flex flex-row items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-xs',
          gpsError ? 'bg-destructive/10' : 'bg-muted/40'
        )}
      >
        <span className='text-muted-foreground'>
          روی نقشه کلیک کنید یا پین را بکشید.
        </span>
        <Button
          type='button'
          variant={gpsError ? 'destructive' : 'outline'}
          size='sm'
          disabled={gpsLoading}
          onClick={useCurrentLocation}
          className='gap-2'
        >
          {gpsLoading ? (
            <Icons.spinner className='h-3.5 w-3.5 animate-spin' aria-hidden />
          ) : gpsError ? (
            <Icons.warning className='h-3.5 w-3.5' aria-hidden />
          ) : (
            <Icons.locationFinder className='h-3.5 w-3.5' aria-hidden />
          )}
          {gpsError || (gpsLoading ? 'در حال دریافت…' : 'GPS auto-pin')}
        </Button>
      </div>

      {gpsError && (
        <p className='text-destructive text-xs'>{gpsError}</p>
      )}

      <div className='border-border relative overflow-hidden rounded-xl border' style={{ height }}>
        <PickerCanvas center={position} zoom={15} position={position} onPick={handlePick} />
      </div>
    </div>
  );
}

export default OsmLocationPicker;
