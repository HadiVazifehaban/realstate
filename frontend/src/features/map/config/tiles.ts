/**
 * Tile source configuration for the interactive map's raster layer.
 *
 * The node serves its own raster tiles via `overv/openstreetmap-tile-server`
 * (see docker-compose.yml) -- Apache inside that image answers
 * `/tile/{z}/{x}/{y}.png`, singular, per the image's own usage banner and
 * renderd's `uri(/tile/)`. It listens on port 80 in the container, published to
 * 8081 on the host.
 *
 * Point `NEXT_PUBLIC_TILE_URL` at the LAN address of the office machine so
 * other devices in the office load tiles too -- `localhost` would resolve to
 * the viewer's machine, not the server.
 */

const DEFAULT_TILE_URL = 'http://localhost:8081/tile';

export const TILE_URL = (process.env.NEXT_PUBLIC_TILE_URL ?? DEFAULT_TILE_URL).replace(/\/$/, '');

export const TILE_LAYER_LABEL = 'نقشه زنده · تایل محلی';

export const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> -- تایل از نود داخلی';

export const DEFAULT_CENTER: [number, number] = [35.7448, 51.5];

export const DEFAULT_ZOOM = 12;

export const MAX_ZOOM = 18;

export function tileErrorMessage(): string {
  return 'بارگذاری نقشه ناموفق بود. سرویس تایل (tiles) را بررسی کنید: docker compose ps tiles';
}
