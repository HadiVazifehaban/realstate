/**
 * Resolve a media URL the API handed back into something a browser can fetch.
 *
 * The API serves two provenances: a crawled photo carries an absolute CDN URL,
 * while a file an advisor uploaded through the submit form has no CDN at all
 * and is streamed by this node's own `/properties/media/file/...` route. That
 * route answers on the API's origin, which from the browser is reached through
 * the dashboard's `/backend` proxy -- so a relative path is prefixed with the
 * same base the JSON calls use, and an absolute one is left untouched.
 */

const ABSOLUTE = /^(https?:)?\/\//i;
const BROWSER_API_BASE = '/backend/api/v1';

/**
 * A media URL ready for `src=`.
 *
 * Absolute URLs (``https://cdn.divar.im/...``) pass through; API-relative ones
 * (``/properties/media/file/{id}``) are resolved against the API base, which is
 * the ``/backend/api/v1`` proxy in the browser and the internal service origin
 * on the server.
 */
export function mediaUrl(url: string): string {
  if (!url) return url;
  if (ABSOLUTE.test(url)) {
    try {
      const parsed = new URL(url, typeof window === 'undefined' ? 'http://localhost' : window.location.origin);
      if (parsed.pathname.startsWith('/api/v1/properties/media/')) {
        return `${BROWSER_API_BASE}${parsed.pathname.slice('/api/v1'.length)}${parsed.search}`;
      }
    } catch {
      return url;
    }
    return url;
  }
  return `${BROWSER_API_BASE}${url.startsWith('/api/v1/') ? url.slice('/api/v1'.length) : url}`;
}
