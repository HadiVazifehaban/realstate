"""Administrator-only review of pending agency applications."""

import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.api import deps
from app.api.v1.endpoints.network import router
from app.core.identity import Principal
from app.models.agency_network import Agency


@pytest.fixture
async def agency_review():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: Agency.metadata.create_all(
            conn, tables=[Agency.__table__]
        ))
    async with AsyncSession(engine, expire_on_commit=False) as session:
        pending_id, verified_id = uuid.uuid4(), uuid.uuid4()
        session.add_all([
            Agency(id=pending_id, slug="pending-office", name="Pending Office", status="PENDING",
                   referral_code="pending-ref"),
            Agency(id=verified_id, slug="verified-office", name="Verified Office", status="VERIFIED",
                   referral_code="verified-ref"),
        ])
        await session.commit()
        state = {"principal": Principal(subject="admin-1", realm_roles=frozenset({"ROLE_ADMIN"}))}
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/network")
        app.dependency_overrides[deps.get_session] = lambda: session
        app.dependency_overrides[deps.get_principal] = lambda: state["principal"]
        app.dependency_overrides[deps.verify_license_active] = lambda: None
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, state, session, pending_id, verified_id
    await engine.dispose()


async def test_admin_can_approve_pending_agency(agency_review):
    client, _, session, pending_id, _ = agency_review
    response = await client.post(
        f"/api/v1/network/agencies/{pending_id}/review", json={"decision": "APPROVE"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "VERIFIED"
    row = await session.get(Agency, pending_id)
    assert row.verified_by == "admin-1"


async def test_admin_must_supply_reason_to_reject(agency_review):
    client, _, session, pending_id, _ = agency_review
    response = await client.post(
        f"/api/v1/network/agencies/{pending_id}/review", json={"decision": "REJECT"}
    )
    assert response.status_code == 422
    assert (await session.get(Agency, pending_id)).status == "PENDING"


async def test_non_admin_cannot_review_agency(agency_review):
    client, state, session, pending_id, _ = agency_review
    state["principal"] = Principal(subject="manager-1", realm_roles=frozenset({"ROLE_AGENCY_MANAGER"}))
    response = await client.post(
        f"/api/v1/network/agencies/{pending_id}/review",
        json={"decision": "APPROVE"},
    )
    assert response.status_code == 403
    assert (await session.get(Agency, pending_id)).status == "PENDING"


async def test_already_reviewed_agency_cannot_be_changed(agency_review):
    client, _, session, _, verified_id = agency_review
    response = await client.post(
        f"/api/v1/network/agencies/{verified_id}/review",
        json={"decision": "REJECT", "reason": "Not eligible"},
    )
    assert response.status_code == 409
    assert (await session.get(Agency, verified_id)).status == "VERIFIED"


async def test_invalid_decision_is_rejected(agency_review):
    client, _, session, pending_id, _ = agency_review
    response = await client.post(
        f"/api/v1/network/agencies/{pending_id}/review", json={"decision": "SUSPEND"}
    )
    assert response.status_code == 422
    assert (await session.get(Agency, pending_id)).status == "PENDING"