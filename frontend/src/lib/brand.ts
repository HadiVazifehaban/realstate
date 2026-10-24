/**
 * Cache-busting version for the brand assets under `public/brand/`.
 *
 * Bump this whenever a logo or icon file is replaced. Browsers keep the favicon
 * in a cache that lives outside the normal HTTP cache (Chrome and Firefox both
 * ignore `Cache-Control`/`ETag` for it), so swapping the bytes at the same URL
 * never reaches an existing visitor — the previous mark stays pinned to the tab
 * until they clear site data by hand. Appending `?v=<version>` gives the asset a
 * fresh URL, which every browser is forced to re-fetch.
 */
export const BRAND_ASSET_VERSION = 2;
