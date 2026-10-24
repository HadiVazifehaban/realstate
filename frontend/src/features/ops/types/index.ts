/**
 * Ingestion-operations contracts — mirrors the scraper endpoints and
 * `app/services/scraper_stats.py`.
 *
 * The five pipeline phases (ingest → normalize → AVM → dedup → distribute) are
 * not individually exposed over HTTP; the node reports the aggregate counters
 * and per-source job state instead. These types describe what it actually
 * returns so the UI never has to invent a phase breakdown that isn't there.
 */

export const JOB_STATUSES = ['PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

export const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  PENDING: 'در صف',
  RUNNING: 'در حال اجرا',
  COMPLETED: 'تکمیل‌شده',
  FAILED: 'ناموفق',
  CANCELLED: 'لغو‌شده'
};

/** Mirrors `ScrapeSource`; the node names each ingestion stream after its source. */
export const SCRAPE_SOURCES = [
  'INTERNAL_USER',
  'INTERNAL_AGENCY',
  'DIVAR',
  'SHEYPOOR',
  'DELTA'
] as const;
export type ScrapeSource = (typeof SCRAPE_SOURCES)[number];

export const SCRAPE_SOURCE_LABELS: Record<ScrapeSource, string> = {
  INTERNAL_USER: 'مالک مستقیم',
  INTERNAL_AGENCY: 'آژانس داخلی',
  DIVAR: 'دیوار',
  SHEYPOOR: 'شیپور',
  DELTA: 'دلتا'
};

/** Mirrors `collect_stats` in `app/services/scraper_stats.py`. */
export interface ScraperStats {
  window_hours: number;
  jobs: {
    total: number;
    completed: number;
    failed: number;
    running: number;
    pending: number;
    cancelled: number;
  };
  items: {
    found: number;
    new: number;
    duplicate: number;
    failed: number;
  };
  /** Fractions in 0..1, already divided by `items.found`. */
  rates: {
    new: number;
    duplicate: number;
    failure: number;
  };
}

/** Mirrors `ScrapeJobResponse`. */
export interface ScrapeJob {
  id: string;
  source: ScrapeSource;
  status: JobStatus;
  items_found: number;
  items_new: number;
  items_duplicate: number;
  items_failed: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface ScrapeJobListResponse {
  items: ScrapeJob[];
  total: number;
  limit: number;
  offset: number;
}

export function formatRate(rate: number): string {
  return `${(rate * 100).toFixed(1)}٪`;
}

export function formatCount(value: number): string {
  return new Intl.NumberFormat('fa-IR').format(value);
}
