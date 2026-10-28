from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.api.v1.endpoints import properties
from app.core.identity import Principal
from app.models.enums import PropertyStatus, SaasTier, UserRole
from app.schemas.properties import PublicListingDTO


def _request(*, workspace_id: str | None = None) -> Request:
    headers = []
    if workspace_id is not None:
        headers.append((b"x-workspace-id", workspace_id.encode()))
    return Request({"type": "http", "method": "GET", "path": "/api/v1/properties", "headers": headers})


def _principal(*, subject: str = "user", admin: bool = False) -> Principal:
    roles = frozenset({UserRole.ADMIN if admin else UserRole.AGENT})
    realm_roles = frozenset({"ROLE_ADMIN" if admin else "ROLE_SENIOR_BROKER"})
    return Principal(
        subject=subject,
        realm_roles=realm_roles,
        roles=roles,
        kyc_status="VERIFIED",
        saas_tier=SaasTier.PRO,
    )


def _property(*, status: PropertyStatus, agency_id=None, owner_subject="other"):
    return SimpleNamespace(
        id=uuid4(), status=status, agency_id=agency_id, owner_subject=owner_subject
    )


@pytest.mark.asyncio
async def test_global_inventory_is_active_only_and_private_owner_can_edit(monkeypatch):
    monkeypatch.setattr(properties, "_property_scope", AsyncMock(return_value=None))
    session = SimpleNamespace()
    principal = _principal(subject="owner")
    request = _request()

    active = _property(status=PropertyStatus.ACTIVE)
    allowed, exact = await properties._can_view_property(session, active, principal, request)
    assert (allowed, exact) == (True, False)

    withdrawn = _property(status=PropertyStatus.WITHDRAWN)
    allowed, _ = await properties._can_view_property(session, withdrawn, principal, request)
    assert allowed is False

    personal_draft = _property(
        status=PropertyStatus.DRAFT, owner_subject="owner"
    )
    allowed, exact = await properties._can_view_property(
        session, personal_draft, principal, request
    )
    assert (allowed, exact) == (True, True)


@pytest.mark.asyncio
async def test_cross_workspace_property_is_denied_without_active_share(monkeypatch):
    agency_id = uuid4()
    monkeypatch.setattr(properties, "_property_scope", AsyncMock(return_value=agency_id))
    session = SimpleNamespace(exec=AsyncMock(return_value=SimpleNamespace(first=lambda: None)))
    prop = _property(status=PropertyStatus.ACTIVE, agency_id=uuid4())

    allowed, exact = await properties._can_view_property(
        session, prop, _principal(), _request()
    )
    assert (allowed, exact) == (False, False)


@pytest.mark.asyncio
async def test_summary_visibility_never_escalates_to_mutation(monkeypatch):
    foreign_agency = uuid4()
    session = SimpleNamespace(get=AsyncMock())
    prop = _property(status=PropertyStatus.ACTIVE, agency_id=foreign_agency)
    session.get.return_value = prop
    monkeypatch.setattr(properties, "_property_scope", AsyncMock(return_value=uuid4()))

    with pytest.raises(Exception) as error:
        await properties._require_property_manage(
            session, prop.id, _principal(), _request()
        )
    assert getattr(error.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_workspace_member_can_manage_its_workspace_property(monkeypatch):
    agency_id = uuid4()
    session = SimpleNamespace(get=AsyncMock())
    prop = _property(status=PropertyStatus.ACTIVE, agency_id=agency_id)
    session.get.return_value = prop
    monkeypatch.setattr(properties, "_property_scope", AsyncMock(return_value=agency_id))

    assert await properties._require_property_manage(
        session, prop.id, _principal(), _request()
    ) is prop


def test_global_admin_escape_hatch_remains_explicit():
    principal = _principal(admin=True)
    assert properties._is_global_admin(principal, _request()) is True
    assert properties._is_global_admin(principal, _request(workspace_id=str(uuid4()))) is False


def test_public_listing_dto_is_an_explicit_non_pii_allowlist():
    fields = set(PublicListingDTO.model_fields)
    assert {
        "phone_number", "owner_id", "exact_address", "precise_coordinates", "private_notes"
    }.isdisjoint(fields)
    assert {
        "public_id", "sanitized_title", "sanitized_description", "city",
        "approximate_latitude", "approximate_longitude",
    }.issubset(fields)
    assert "status" not in fields
    assert {"latitude", "longitude", "precise_coordinates"}.isdisjoint(fields)
