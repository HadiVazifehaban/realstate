"""Pydantic request/response schemas for Phase 2 scraper triggers and jobs."""

from app.schemas.scraper import (
    ScrapeJobCreate,
    ScrapeJobListResponse,
    ScrapeJobResponse,
)

__all__ = ["ScrapeJobCreate", "ScrapeJobResponse", "ScrapeJobListResponse"]

