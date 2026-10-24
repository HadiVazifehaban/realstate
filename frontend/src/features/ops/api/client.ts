/**
 * Client for the scraper / ingestion-ops endpoints (`/api/v1/scraper`).
 *
 * Every call carries the realm access token from the Auth.js session, which the
 * FastAPI node re-verifies and authorises from the signed claims. Every route
 * here sits behind `API_GUARD`, so an unauthenticated call answers 401/403 and
 * the page must show that as a refusal, not as zero counters.
 */

import { apiBaseUrl, networkFailureMessage } from '@/lib/api-base-url';
import { authHeaders } from '@/lib/auth/session';
import type { ScrapeJob, ScrapeJobListResponse, ScraperStats } from '../types';

export class OpsApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'OpsApiError';
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      cache: 'no-store',
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(await authHeaders()),
        ...init.headers
      }
    });
  } catch (error) {
    // A rejected fetch never saw a status; `status: 0` keeps that distinct
    // from an API error the caller can retry meaningfully.
    throw new OpsApiError(0, 'network_unreachable', networkFailureMessage(error));
  }

  if (!response.ok) {
    let code = 'request_failed';
    let message = response.statusText || 'درخواست ناموفق بود.';
    try {
      const body = (await response.json()) as {
        detail?: { error?: string; message?: string } | string;
      };
      if (typeof body.detail === 'string') {
        message = body.detail;
      } else if (body.detail) {
        code = body.detail.error ?? code;
        message = body.detail.message ?? message;
      }
    } catch {
      // Non-JSON error body — keep the fallback.
    }
    throw new OpsApiError(response.status, code, message);
  }

  return (await response.json()) as T;
}

/** Aggregate counters over a trailing window; `hours` is clamped to >= 1 server-side. */
export function fetchScraperStats(hours = 24): Promise<ScraperStats> {
  return request<ScraperStats>(`/scraper/stats?hours=${hours}`);
}

export function fetchScrapeJobs(limit = 50, offset = 0): Promise<ScrapeJobListResponse> {
  return request<ScrapeJobListResponse>(`/scraper/jobs?limit=${limit}&offset=${offset}`);
}

export function fetchScrapeJob(jobId: string): Promise<ScrapeJob> {
  return request<ScrapeJob>(`/scraper/jobs/${jobId}`);
}
