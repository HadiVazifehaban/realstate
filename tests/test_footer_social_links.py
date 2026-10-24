import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.router import api_router
from app.core.config import AuthMode, Settings, get_settings
from app.core.identity import Principal
from app.db.session import get_session
from app.models.footer_social_link import FooterSocialLink


@pytest.fixture
async def social_client(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(FooterSocialLink.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def session():
        async with factory() as value:
            yield value

    application = FastAPI()
    from app.api.v1.endpoints import social_links

    async def verified_token(token, settings):
        return application.state.principal

    monkeypatch.setattr(social_links, "principal_from_token", verified_token)
    application.include_router(api_router, prefix="/api/v1")
    application.dependency_overrides[get_session] = session
    application.dependency_overrides[get_settings] = lambda: Settings(
        auth_mode=AuthMode.KEYCLOAK, keycloak_issuer="https://id.example/realms/test"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        application.state.client = client
        yield client, application
    await engine.dispose()


def admin(application, role="ROLE_ADMIN"):
    application.state.principal = Principal(
        subject="test-admin", realm_roles=frozenset({role}), kyc_status="VERIFIED"
    )
    application.state.client.headers["Authorization"] = "Bearer verified-test-token"


def values(**changes):
    return dict(platform_key="eitaa", display_name="ایتا", icon_name="eitaa",
                url="https://eitaa.com/test", is_active=True, sort_order=0, **changes)


async def test_public_read_and_admin_crud_visibility_order(social_client):
    client, application = social_client
    assert (await client.get("/api/v1/site/social-links")).json() == []
    admin(application)
    first = await client.post("/api/v1/admin/social-links", json=values())
    assert first.status_code == 201, first.text
    a = first.json()
    payload = values()
    payload.update(platform_key="rubika", icon_name="rubika", display_name="روبیکا", sort_order=1)
    b = (await client.post("/api/v1/admin/social-links", json=payload)).json()
    response = await client.put("/api/v1/admin/social-links/reorder", json={"ids": [b["id"], a["id"]]})
    assert [row["id"] for row in response.json()] == [b["id"], a["id"]]
    response = await client.patch(f'/api/v1/admin/social-links/{a["id"]}', json={"is_active": False})
    assert response.json()["is_active"] is False
    payload.update(display_name="نام سفارشی", url="https://rubika.ir/custom")
    assert (await client.put(f'/api/v1/admin/social-links/{b["id"]}', json=payload)).status_code == 200
    client.headers.pop("Authorization")
    public = (await client.get("/api/v1/site/social-links")).json()
    assert len(public) == 1 and public[0]["display_name"] == "نام سفارشی"
    admin(application)
    assert len((await client.get("/api/v1/admin/social-links")).json()) == 2
    assert (await client.delete(f'/api/v1/admin/social-links/{a["id"]}')).status_code == 204
    assert (await client.delete(f'/api/v1/admin/social-links/{a["id"]}')).status_code == 404


@pytest.mark.parametrize("role", [None, "ROLE_SUPERVISOR", "ROLE_AGENCY_MANAGER", "ROLE_JUNIOR_BROKER"])
async def test_all_admin_methods_are_protected(social_client, role):
    client, application = social_client
    if role:
        admin(application, role)
    expected = 403 if role else 401
    for method, suffix, payload in [
        ("GET", "", None), ("POST", "", values()),
        ("PUT", "/reorder", {"ids": [str(uuid.uuid4())]}),
        ("PUT", f"/{uuid.uuid4()}", values()),
        ("PATCH", f"/{uuid.uuid4()}", {"is_active": False}),
        ("DELETE", f"/{uuid.uuid4()}", None),
    ]:
        response = await client.request(method, "/api/v1/admin/social-links" + suffix, json=payload)
        assert response.status_code == expected, (method, response.text)


@pytest.mark.parametrize("role", ["ROLE_ADMIN", "ROLE_SUPER_ADMIN", "admin", "super_admin"])
async def test_supported_admin_roles(social_client, role):
    client, application = social_client
    admin(application, role)
    assert (await client.get("/api/v1/admin/social-links")).status_code == 200


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,test", "ftp://example.com", "https://user:pass@example.com", "//example.com", "https://exam ple.com", "https://example.com\\evil"])
async def test_rejects_unsafe_urls(social_client, url):
    client, application = social_client
    admin(application)
    payload = values()
    payload["url"] = url
    assert (await client.post("/api/v1/admin/social-links", json=payload)).status_code == 422


async def test_pending_admin_and_invalid_token_fail_closed(social_client, monkeypatch):
    from app.api.v1.endpoints import social_links
    from app.core.identity import IdentityError

    client, application = social_client
    admin(application, "super_admin")
    application.state.principal = Principal(
        subject="pending", realm_roles=frozenset({"super_admin"}), kyc_status="PENDING"
    )
    assert (await client.get("/api/v1/admin/social-links")).status_code == 403

    async def invalid_token(token, settings):
        raise IdentityError(401, "invalid_token", "Invalid token")

    monkeypatch.setattr(social_links, "principal_from_token", invalid_token)
    assert (await client.get("/api/v1/admin/social-links")).status_code == 401


async def test_reorder_rejects_duplicates_and_missing_ids_atomically(social_client):
    client, application = social_client
    admin(application)
    row = (await client.post("/api/v1/admin/social-links", json=values())).json()
    for ids in [[row["id"], row["id"]], [str(uuid.uuid4())]]:
        assert (await client.put("/api/v1/admin/social-links/reorder", json={"ids": ids})).status_code == 409
    assert (await client.get("/api/v1/admin/social-links")).json()[0]["sort_order"] == 0


@pytest.mark.parametrize("field,value", [("display_name", " "), ("platform_key", "../x"), ("icon_name", "arbitrary-svg"), ("sort_order", -1)])
async def test_validates_fields(social_client, field, value):
    client, application = social_client
    admin(application)
    payload = values()
    payload[field] = value
    assert (await client.post("/api/v1/admin/social-links", json=payload)).status_code == 422