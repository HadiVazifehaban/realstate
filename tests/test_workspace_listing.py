"""Exercise workspace listing through HTTP, including Request injection."""

import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import deps
from app.api.v1.endpoints.network import router
from app.core.identity import Principal
from app.models.agency_network import Agency, AgencyMembership


@pytest.fixture
async def workspace_listing():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: Agency.metadata.create_all(
            conn, tables=[Agency.__table__, AgencyMembership.__table__]
        ))
    async with AsyncSession(engine, expire_on_commit=False) as session:
        legacy_id, member_id = uuid.uuid4(), uuid.uuid4()
        session.add_all([
            Agency(id=legacy_id, slug="legacy", name="Legacy", status="VERIFIED",
                   referral_code="legacy-office"),
            Agency(id=member_id, slug="member", name="Member", status="VERIFIED",
                   referral_code="member-office"),
            AgencyMembership(
                agency_id=member_id, user_subject="user-1", role="FOUNDER",
                created_by_subject="user-1",
            ),
        ])
        await session.commit()
        identity = {"principal": Principal(
            subject="user-1", tenant_id=str(legacy_id),
            realm_roles=frozenset({"ROLE_AGENCY_MANAGER"}), kyc_status="VERIFIED",
        )}
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/network")
        app.dependency_overrides[deps.get_session] = lambda: session
        app.dependency_overrides[deps.get_principal] = lambda: identity["principal"]
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, identity, session, legacy_id, member_id
    await engine.dispose()


async def test_verified_legacy_operator_can_list_office(workspace_listing):
    client, _, _, legacy_id, _ = workspace_listing
    response = await client.get("/api/v1/network/workspaces")
    assert response.status_code == 200
    assert [(row["id"], row["role"]) for row in response.json()] == [
        (str(legacy_id), "LEGACY_OFFICE_OPERATOR")
    ]


async def test_explicit_selector_uses_memberships_not_legacy_claim(workspace_listing):
    client, _, _, _, member_id = workspace_listing
    response = await client.get(
        "/api/v1/network/workspaces", headers={"x-workspace-id": str(member_id)}
    )
    assert response.status_code == 200
    assert [(row["id"], row["role"]) for row in response.json()] == [
        (str(member_id), "FOUNDER")
    ]


async def test_user_without_offices_gets_empty_list(workspace_listing):
    client, identity, _, _, _ = workspace_listing
    identity["principal"] = Principal(subject="no-office")
    response = await client.get("/api/v1/network/workspaces")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("status", ["PENDING", "VERIFIED"])
async def test_unprivileged_tenant_claim_does_not_grant_access(workspace_listing, status):
    client, identity, _, legacy_id, _ = workspace_listing
    identity["principal"] = Principal(
        subject="outsider", tenant_id=str(legacy_id), kyc_status=status,
        realm_roles=frozenset({"ROLE_SENIOR_BROKER"}),
    )
    response = await client.get("/api/v1/network/workspaces")
    assert response.status_code == 200
    assert response.json() == []


async def test_revoked_membership_is_not_listed(workspace_listing):
    from app.models.base import utcnow
    from sqlmodel import select

    client, _, session, _, member_id = workspace_listing
    membership = (await session.exec(select(AgencyMembership))).one()
    membership.revoked_at = utcnow()
    await session.commit()
    response = await client.get(
        "/api/v1/network/workspaces", headers={"x-workspace-id": str(member_id)}
    )
    assert response.status_code == 200
    assert response.json() == []