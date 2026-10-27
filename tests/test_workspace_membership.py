"""Workspace membership resolution is server-owned and revocable."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.deps import get_active_agency_membership
from app.core.identity import Principal
from app.models.agency_network import Agency, AgencyMembership


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, memberships, agencies):
        self.memberships = memberships
        self.agencies = agencies

    async def exec(self, _query):
        result = str(_query)
        rows = self.memberships
        if "agency_membership.agency_id =" in result:
            requested_id = next(
                value for value in _query.compile().params.values() if isinstance(value, uuid.UUID)
            )
            rows = [row for row in rows if row.agency_id == requested_id]
        return FakeResult(rows)

    async def get(self, model, key):
        assert model is Agency
        return self.agencies.get(key)


def _request(headers=None):
    return SimpleNamespace(headers=headers or {}, url=SimpleNamespace(path="/api/v1/network/workspaces/current"))


def _membership(agency_id, subject="user-1", *, revoked_at=None):
    return AgencyMembership(
        id=uuid.uuid4(), agency_id=agency_id, user_subject=subject,
        role="FOUNDER", created_by_subject=subject, revoked_at=revoked_at,
    )


def _agency(agency_id, status="VERIFIED"):
    return Agency(id=agency_id, slug="office", name="Office", status=status)


def test_workspace_is_derived_from_db_not_claim_and_revocation_is_immediate():
    async def scenario():
        agency_id = uuid.uuid4()
        principal = Principal(subject="user-1", tenant_id=str(uuid.uuid4()))
        session = FakeSession([_membership(agency_id)], {agency_id: _agency(agency_id)})
        scoped, membership, agency = await get_active_agency_membership(
            session, principal, _request()
        )
        assert scoped.tenant_id == str(agency_id)
        assert scoped.active_agency_id == str(agency_id)
        assert membership.user_subject == principal.subject
        assert agency.id == agency_id

        with pytest.raises(HTTPException) as error:
            await get_active_agency_membership(FakeSession([], {}), principal, _request())
        assert error.value.status_code == 403
        assert error.value.detail["error"] == "workspace_membership_required"

    asyncio.run(scenario())


def test_workspace_selector_cannot_select_another_users_membership():
    async def scenario():
        own_id, foreign_id = uuid.uuid4(), uuid.uuid4()
        principal = Principal(subject="user-1")
        session = FakeSession(
            [_membership(own_id)], {own_id: _agency(own_id), foreign_id: _agency(foreign_id)}
        )
        with pytest.raises(HTTPException) as error:
            await get_active_agency_membership(
                session, principal, _request({"x-workspace-id": str(foreign_id)})
            )
        assert error.value.status_code == 403

    asyncio.run(scenario())


def test_verified_legacy_office_operator_can_resolve_signed_tenant_workspace():
    async def scenario():
        agency_id = uuid.uuid4()
        agency = _agency(agency_id)
        principal = Principal(
            subject="legacy-user",
            tenant_id=str(agency_id),
            realm_roles=frozenset({"ROLE_AGENCY_MANAGER"}),
            kyc_status="VERIFIED",
        )
        scoped, membership, resolved = await get_active_agency_membership(
            FakeSession([], {agency_id: agency}), principal, _request()
        )
        assert scoped.active_agency_id == str(agency_id)
        assert membership.user_subject == "legacy-user"
        assert membership.role == "LEGACY_OFFICE_OPERATOR"
        assert resolved is agency

    asyncio.run(scenario())


def test_legacy_workspace_does_not_override_a_different_selector():
    async def scenario():
        agency_id, selected_id = uuid.uuid4(), uuid.uuid4()
        principal = Principal(
            subject="legacy-user",
            tenant_id=str(agency_id),
            realm_roles=frozenset({"ROLE_AGENCY_MANAGER"}),
            kyc_status="VERIFIED",
        )
        with pytest.raises(HTTPException) as error:
            await get_active_agency_membership(
                FakeSession([], {agency_id: _agency(agency_id)}),
                principal,
                _request({"x-workspace-id": str(selected_id)}),
            )
        assert error.value.status_code == 403

    asyncio.run(scenario())


def test_only_verified_office_roles_use_legacy_workspace_fallback():
    async def scenario():
        agency_id = uuid.uuid4()
        agency = _agency(agency_id)
        for principal in (
            Principal(subject="pending", tenant_id=str(agency_id),
                      realm_roles=frozenset({"ROLE_AGENCY_MANAGER"}), kyc_status="PENDING"),
            Principal(subject="broker", tenant_id=str(agency_id),
                      realm_roles=frozenset({"ROLE_SENIOR_BROKER"}), kyc_status="VERIFIED"),
        ):
            with pytest.raises(HTTPException) as error:
                await get_active_agency_membership(
                    FakeSession([], {agency_id: agency}), principal, _request()
                )
            assert error.value.status_code == 403
            assert error.value.detail["error"] == "workspace_membership_required"

    asyncio.run(scenario())