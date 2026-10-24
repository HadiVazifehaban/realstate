"use client";

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { TILE_URL, tileErrorMessage } from '../config/tiles';
import type { MapPin } from './map-canvas';

/**
 * Leaflet reads `window` at module scope, so the canvas can only be imported
 * with `ssr: false`. In the App Router that has to happen in a client component,
 * which is why this wrapper exists rather than a plain re-export.
 */
const MapCanvas = dynamic(() => import("./map-canvas"), {
  ssr: false,
  loading: () => <Skeleton className='size-full' />
});

export function PropertyMap({
  pins,
  center,
  zoom,
  height = 380,
  className,
  darkTiles = false
}: {
  pins: MapPin[];
  center?: [number, number];
  zoom?: number;
  height?: number;
  className?: string;
  /** Invert the raster tiles to a dark basemap. Opt-in; the default stays readable. */
  darkTiles?: boolean;
}) {
  // Tile errors arrive through a window event because Leaflet's TileLayer is
  // created inside react-leaflet, out of reach of React state here.
  const [tilesDown, setTilesDown] = useState(false);

  useEffect(() => {
    const onError = () => setTilesDown(true);
    const onLoad = () => setTilesDown(false);
    window.addEventListener("tiles:error", onError);
    window.addEventListener("tiles:load", onLoad);
    return () => {
      window.removeEventListener("tiles:error", onError);
      window.removeEventListener("tiles:load", onLoad);
    };
  }, []);

  return (
    <div className='min-w-0 space-y-2'>
      <div
        className={`min-w-0 overflow-hidden rounded-xl border ${
          darkTiles ? 'showcase-dark-tiles border-showcase-border' : 'border-border'
        } ${className ?? ""}`}
        style={{ height }}
      >
        <MapCanvas pins={pins} center={center} zoom={zoom} />
      </div>

      {tilesDown && (
        <Alert variant='destructive'>
          <AlertTitle>سرویس تایل در دسترس نیست</AlertTitle>
          <AlertDescription>
            {tileErrorMessage()}
            <span className='mt-1 block font-mono text-xs' dir='ltr'>
              {TILE_URL}
            </span>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}

export type { MapPin };
