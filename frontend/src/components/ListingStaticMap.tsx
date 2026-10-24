'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { TILE_URL } from '@/features/map/config/tiles';

/**
 * Static property map thumbnail rendered from the node's own tile server.
 *
 * Fully local: a single OSM raster tile from TILE_URL centred on the pin,
 * with a CSS pin overlay. No vendor map API, no external network, no map instance.
 */

export interface ListingStaticMapProps {
  lat: number;
  lng: number;
  className?: string;
  width?: number;
  height?: number;
  zoom?: number;
  /** Hide the coordinates badge when the surrounding card already shows them. */
  showBadge?: boolean;
}

/** Slippy-map tile numbers for a WGS84 point at a zoom level. */
function pointToTile(lat: number, lng: number, zoom: number): { x: number; y: number } {
  const n = 2 ** zoom;
  const x = Math.floor(((lng + 180) / 360) * n);
  const latRad = (lat * Math.PI) / 180;
  const y = Math.floor(
    ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n
  );
  return { x, y };
}

export function ListingStaticMap({
  lat,
  lng,
  className,
  width = 600,
  height = 400,
  zoom = 15,
  showBadge = true
}: ListingStaticMapProps) {
  const [failed, setFailed] = React.useState(false);

  const { x, y } = pointToTile(lat, lng, zoom);
  const src = `${TILE_URL}/${zoom}/${x}/${y}.png`;

  if (failed) {
    return (
      <div
        role='img'
        aria-label={`نقشه موقعیت ${lat}, ${lng}`}
        className={cn(
          'bg-muted text-muted-foreground relative flex items-center justify-center overflow-hidden rounded-xl border border-[rgba(229,168,123,0.25)] text-xs',
          className
        )}
        style={{ width, height }}
      >
        نقشه این ملک در دسترس نیست
      </div>
    );
  }

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-xl border border-[rgba(229,168,123,0.25)]',
        className
      )}
      style={{ width, height }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={`نقشه موقعیت ملک — ${lat}, ${lng}`}
        className='absolute inset-0 h-full w-full object-cover'
        onError={() => setFailed(true)}
      />
      {/* Centre pin: the tile is centred on the point's tile, so the pin sits mid-frame. */}
      <span
        aria-hidden
        className='absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2'
      >
        <span className='block size-4 rounded-full border-2 border-white bg-[#b87548] shadow-md' />
      </span>

      {showBadge && (
        <span className='absolute bottom-3 left-3 rounded-full border border-[rgba(229,168,123,0.5)] bg-black/40 px-2.5 py-1 text-[0.7rem] font-medium text-white backdrop-blur-sm'>
          {lat.toFixed(5)}, {lng.toFixed(5)}
        </span>
      )}
    </div>
  );
}

export default ListingStaticMap;
