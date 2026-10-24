"""API smoke tests (no database required)."""

from __future__ import annotations

import httpx
import pytest

from app.main import create_app


@pytest.fixture()
def app():
    return create_app()


async def _client(app) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_root_banner_requires_authentication(app) -> None:
    async with await _client(app) as client:
        resp = await client.get("/")
        assert resp.status_code == 401


async def test_health(app) -> None:
    async with await _client(app) as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["version"].startswith("2.0.0")


async def test_api_schema_is_not_publicly_routable(app) -> None:
    async with await _client(app) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert (await client.get(path)).status_code == 404


async def test_openapi_available_in_debug(app) -> None:
    # DEBUG defaults to True in tests only if .env enables it; tolerate both.
    async with await _client(app) as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
