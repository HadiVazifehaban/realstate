'use client';

import { Fragment, useEffect } from 'react';
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from 'react-leaflet';

import {
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  MAX_ZOOM,
  TILE_ATTRIBUTION,
  TILE_URL
} from '@/features/map/config/tiles';

/**
 * One neighbourhood, drawn as a bubble.
 *
 * Radius arrives in screen pixels and colour already resolved: the ramp belongs
 * to the page, so the map, the legend and the list cannot disagree about which
 * end of the scale is expensive.
 */
export interface MarketBubble {
  id: string;
  lat: number;
  lng: number;
  /** Screen pixels, not metres — a metre-sized circle vanishes at city zoom. */
  radius: number;
  color: string;
  label: string;
  /** The metric value, already formatted. */
  value: string;
  /** File count, already formatted. */
  files: string;
  selected: boolean;
}

/** Fly to the selected bubble; no-op while nothing is selected. */
function FocusOnSelection({ bubble }: { bubble: MarketBubble | null }) {
  const map = useMap();

  useEffect(() => {
    if (!bubble) return;
    map.flyTo([bubble.lat, bubble.lng], Math.max(map.getZoom(), 13), { duration: 0.6 });
  }, [map, bubble]);

  return null;
}

/**
 * Leaflet reads `window` at module scope, so this file may only be imported
 * with `ssr: false` — see market-map.tsx.
 *
 * Bubbles are `CircleMarker`s rather than scaled `Circle`s: the market map is
 * read at city zoom, where a radius in metres shrinks to invisible while a
 * screen-space one keeps every neighbourhood comparable.
 */
export default function MarketMapCanvas({
  bubbles,
  selectedId,
  onSelect
}: {
  bubbles: MarketBubble[];
  selectedId?: string | null;
  onSelect?: (id: string) => void;
}) {
  const selected = bubbles.find((bubble) => bubble.id === selectedId) ?? null;

  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={DEFAULT_ZOOM}
      maxZoom={MAX_ZOOM}
      style={{ height: '100%', width: '100%' }}
    >
      {/* Local raster tiles only — no external map provider layer. */}
      <TileLayer
          url={`${TILE_URL}/{z}/{x}/{y}.png`}
          attribution={TILE_ATTRIBUTION}
          maxZoom={MAX_ZOOM}
          // A dead tile server must say so rather than render a blank pane; the
          // wrapper owns the message, this only reports the event.
          eventHandlers={{
            tileerror: () => {
              if (typeof window !== 'undefined') {
                window.dispatchEvent(new CustomEvent('tiles:error'));
              }
            },
            tileload: () => {
              if (typeof window !== 'undefined') {
                window.dispatchEvent(new CustomEvent('tiles:load'));
              }
            }
          }}
        />

      <FocusOnSelection bubble={selected} />

      {bubbles.map((bubble) => (
        <Fragment key={bubble.id}>
          <CircleMarker
            center={[bubble.lat, bubble.lng]}
            radius={bubble.radius}
            pathOptions={{
              // A selected bubble gets a hard outline so it stays findable after
              // the map flies to it and the tooltip closes.
              color: bubble.selected ? '#0a121e' : 'rgba(10,18,30,0.55)',
              weight: bubble.selected ? 3 : 1,
              fillColor: bubble.color,
              fillOpacity: 0.85
            }}
            eventHandlers={{ click: () => onSelect?.(bubble.id) }}
          >
            <Tooltip direction='top'>
              <span dir='rtl' className='block text-right'>
                <strong className='block'>{bubble.label}</strong>
                {bubble.value}
                <span className='text-muted-foreground block'>
                  {bubble.files} فایل با قیمت
                </span>
              </span>
            </Tooltip>
          </CircleMarker>
        </Fragment>
      ))}
    </MapContainer>
  );
}
