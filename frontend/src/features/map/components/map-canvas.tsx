"use client";

import { Fragment, useEffect, useMemo } from 'react';
import { Circle, CircleMarker, MapContainer, Marker, TileLayer, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import {
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  MAX_ZOOM,
  TILE_ATTRIBUTION,
  TILE_URL,
  tileErrorMessage
} from '../config/tiles';

export interface MapPin {
  id: string;
  lat: number;
  lng: number;
  /** Shown in the tooltip. Never put owner contact here -- it is PII. */
  label: string;
  /** bargain = under market, overpriced = over market. */
  tone?: "bargain" | "fair" | "overpriced";
  /**
   * Draw a privacy halo of this many METRES around the pin.
   *
   * Not pixels: the radius has to mean the same thing on screen at any zoom,
   * and it is the same number the backend masks to, so an observer sees one
   * consistent area. Pass the value from the API rather than hard-coding it.
   */
  privacyRadiusM?: number;
  /**
   * Stroke/fill colour for the privacy halo.
   *
   * Defaults to the portal-convention pink. The listing showcase passes the
   * brand rose-gold instead, which is why the halo is an override rather than a
   * fixed colour: the semantic (this is the masked area, not a valuation) must
   * never be readable from hue alone, so the default stays the one advisors
   * already recognise and only the presentation surface varies.
   */
  privacyAccent?: string;
}

const TONE_COLORS: Record<NonNullable<MapPin["tone"]>, string> = {
  bargain: "#059669",
  fair: "#b87548",
  overpriced: "#dc2626"
};

/**
 * CircleMarker rather than Marker on purpose: Leaflet's default Marker icon is
 * referenced by relative CSS URL, which breaks under the bundler and renders as
 * a broken-image glyph. CircleMarker is pure SVG, needs no asset, and matches the
 * bargain/fair/overpriced colouring used on the property cards.
 *
 * This file must only ever be imported with `ssr: false` -- Leaflet touches
 * `window` at module scope. See property-map.tsx.
 */
/**
 * Leaflet needs an imperative handle to fit the viewport, and that handle only
 * exists once the map is mounted -- hence a child component rather than an
 * effect in the parent.
 */
function FitToPins({ pins }: { pins: MapPin[] }) {
  const map = useMap();

  useEffect(() => {
    if (pins.length === 0) return;
    if (pins.length === 1) {
      map.setView([pins[0].lat, pins[0].lng], Math.max(map.getZoom(), 14));
      return;
    }
    map.fitBounds(L.latLngBounds(pins.map((pin) => [pin.lat, pin.lng])), {
      padding: [32, 32],
      maxZoom: 16
    });
  }, [map, pins]);

  return null;
}

export default function MapCanvas({
  pins,
  center,
  zoom,
  className
}: {
  pins: MapPin[];
  center?: [number, number];
  zoom?: number;
  className?: string;
}) {
  const fallback = center ?? DEFAULT_CENTER;

  // Leaflet mutates the array it is given, so hand it a private copy.
  const positions = useMemo(
    () => pins.filter((pin) => Number.isFinite(pin.lat) && Number.isFinite(pin.lng)),
    [pins]
  );

  return (
    <MapContainer
      center={fallback}
      zoom={zoom ?? DEFAULT_ZOOM}
      maxZoom={MAX_ZOOM}
      className={className}
      style={{ height: "100%", width: "100%" }}
    >
      {/* Local raster tiles only — no external map provider layer. */}
      <TileLayer
        url={`${TILE_URL}/{z}/{x}/{y}.png`}
            attribution={TILE_ATTRIBUTION}
            maxZoom={MAX_ZOOM}
            // Surface a dead tile server instead of showing a silently blank map.
            eventHandlers={{
              tileerror: () => {
                if (typeof window !== 'undefined') {
                  window.dispatchEvent(new CustomEvent('tiles:error'));
                }
              },
              // Without this the alert in property-map.tsx latches on forever:
              // a recovered server would still leave the warning up.
              tileload: () => {
                if (typeof window !== 'undefined') {
                  window.dispatchEvent(new CustomEvent('tiles:load'));
                }
              }
            }} />
      <FitToPins pins={positions} />
      {positions.map((pin) => {
        // Pink by default: the portal convention for "approximate area", and
        // distinct from the three valuation pin colours so it can never be
        // mistaken for one.
        const accent = pin.privacyAccent ?? "#db2777";
        const fill = pin.privacyAccent ?? "#f472b6";
        return (
          <Fragment key={pin.id}>
            {pin.privacyRadiusM !== undefined && pin.privacyRadiusM > 0 && (
              <>
                <Circle
                  center={[pin.lat, pin.lng]}
                  radius={pin.privacyRadiusM}
                  pathOptions={{
                    color: accent,
                    weight: 1.5,
                    dashArray: "6 6",
                    fillColor: fill,
                    fillOpacity: 0.18
                  }}
                >
                  <Tooltip direction='top' sticky>
                    {`موقعیت تقریبی — شعاع ${pin.privacyRadiusM.toLocaleString("en-US")} متر`}
                  </Tooltip>
                </Circle>
                {/* A labelled centre point, not a bare pin: the whole point of the
                    halo is that the viewer should not assume it is the address. */}
                <Marker
                  position={[pin.lat, pin.lng]}
                  interactive={false}
                  icon={L.divIcon({
                    className: "privacy-halo-label",
                    html: "موقعیت تقریبی",
                    iconSize: [96, 24],
                    iconAnchor: [48, 12]
                  })}
                />
              </>
            )}
            <CircleMarker
              center={[pin.lat, pin.lng]}
              radius={9}
              pathOptions={{
                color: "#0a121e",
                weight: 2,
                fillColor: TONE_COLORS[pin.tone ?? "fair"],
                fillOpacity: 1
              }}
            >
              <Tooltip direction='top'>{pin.label}</Tooltip>
            </CircleMarker>
          </Fragment>
        );
      })}
    </MapContainer>
  );
}

export { tileErrorMessage };
