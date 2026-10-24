"use client";

import { Circle, MapContainer, Marker, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import { MAX_ZOOM, TILE_ATTRIBUTION, TILE_URL, tileErrorMessage } from '../config/tiles';
import { APPROXIMATE_RADIUS_M } from '../config/cities';
import type { LatLngLiteral } from '../types';

/**
 * Leaflet touches `window` at module scope, so this file is only ever reached
 * through a `dynamic({ ssr: false })` boundary -- see picker-canvas.tsx.
 *
 * The pin is a Marker with an explicit `divIcon`, not the Leaflet default: the
 * default icon is loaded by relative CSS URL, which the bundler cannot resolve
 * and which renders as a broken-image glyph. See map-canvas.tsx for the same
 * reasoning behind CircleMarker there.
 */
function Pin({ position }: { position: LatLngLiteral }) {
  return (
    <Marker
      position={[position.lat, position.lng]}
      draggable
      autoPan
      icon={L.divIcon({
        className: '',
        html: '<div class="maskanchi-pin"></div>',
        iconSize: [26, 26],
        iconAnchor: [13, 25]
      })}
    />
  );
}

/**
 * Flies the camera on city change. Kept as a child because `useMap` is only
 * valid once the container has mounted -- an effect in the parent would run
 * before the map instance exists.
 */
function FlyToCity({ lat, lng, zoom }: { lat: number; lng: number; zoom: number }) {
  const map = useMap();

  map.flyTo([lat, lng], zoom, { duration: 1.1 });

  return null;
}

export default function PickerCanvas({
  center,
  zoom,
  position,
  onPick
}: {
  center: LatLngLiteral;
  zoom: number;
  position: LatLngLiteral;
  onPick: (next: LatLngLiteral) => void;
}) {
  return (
    <MapContainer
      center={[center.lat, center.lng]}
      zoom={zoom}
      // The container is a flex child in a CSS grid; without an explicit
      // invalidateSize on mount Leaflet measures a 0x0 box and renders grey.
      zoomControl
      className='h-full w-full'
    >
      {/* Local raster tiles only — no external map provider layer. */}
      <TileLayer
        url={`${TILE_URL}/{z}/{x}/{y}.png`}
        attribution={TILE_ATTRIBUTION}
        maxZoom={MAX_ZOOM}
      />

      {/* Click-to-place. Leaflet fires this for every click that did not land
          on a control, so the zoom buttons do not move the pin. */}
      <MapClickHandler onPick={onPick} />

      <Circle
        center={[position.lat, position.lng]}
        radius={APPROXIMATE_RADIUS_M}
        pathOptions={{
          color: "#e5a87b",
          weight: 1,
          opacity: 0.6,
          fillColor: "#e5a87b",
          fillOpacity: 0.05
        }}
      />

      <Pin position={position} />
      <FlyToCity lat={center.lat} lng={center.lng} zoom={zoom} />
    </MapContainer>
  );
}

function MapClickHandler({ onPick }: { onPick: (next: LatLngLiteral) => void }) {
  const map = useMap();

  map.on("click", (event: L.LeafletMouseEvent) => {
    onPick({ lat: event.latlng.lat, lng: event.latlng.lng });
  });

  return null;
}

export { tileErrorMessage };
