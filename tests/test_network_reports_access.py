"""HTTP + real SQL isolation tests; synthetic data in an in-memory database only."""
import uuid

import httpx
import pytest
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import deps
from app.api.v1.endpoints.network_reports import router
from app.core.config import AuthMode, Settings, get_settings
from app.core.identity import Principal
from app.models.agency_network import Agency, AgencyCooperation
from app.models.enums import AuditAction, DisputeCategory, UserRole
from app.models.network_collab import (
    AuditEvent, CommissionAgreement, CommissionAllocation, CommissionPayment,
    DisputeCase, LeadReferral, ListingShare, ListingTransferHistory,
)


@pytest.fixture
async def reports():
    # No application engine or configured database is connected by these tests.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    models = [Agency, AgencyCooperation, ListingShare, LeadReferral,
              ListingTransferHistory, CommissionAgreement, CommissionAllocation,
              CommissionPayment, DisputeCase, AuditEvent]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Agency.metadata.create_all(
            c, tables=[model.__table__ for model in models]
        ))
    async with AsyncSession(engine, expire_on_commit=False) as session:
        a, b, c, d = [uuid.uuid4() for _ in range(4)]
        session.add_all([
            Agency(id=ident, slug=f"office-{i}", name=f"Office {i}")
            for i, ident in enumerate((a, b, c, d))
        ])
        # A's incoming and outgoing records; B/C-only records must not leak.
        for source, target in [(a, b), (b, a), (b, c), (c, b)]:
            session.add_all([
                ListingShare(property_id=uuid.uuid4(), source_agency_id=source, target_agency_id=target),
                LeadReferral(subject="Synthetic referral", source_agency_id=source, target_agency_id=target),
                ListingTransferHistory(property_id=uuid.uuid4(), from_agency_id=source, to_agency_id=target),
                AgencyCooperation(requester_agency_id=source, target_agency_id=target),
                DisputeCase(title="Synthetic case", category=DisputeCategory.OWNERSHIP,
                            claimant_agency_id=source, respondent_agency_id=target),
            ])
        ab = CommissionAgreement(source_agency_id=a, target_agency_id=b, basis_amount=1000)
        ba = CommissionAgreement(source_agency_id=b, target_agency_id=a, basis_amount=2000)
        bc = CommissionAgreement(source_agency_id=b, target_agency_id=c, basis_amount=9000)
        session.add_all([ab, ba, bc])
        # Multiple own payments must be summed once, not duplicated by joins.
        for agreement, beneficiary, amounts in [
            (ab, a, [10, 20]), (ba, a, [30]), (ab, b, [700]),
            (bc, b, [8000]), (bc, a, [900]),  # malformed A allocation on B/C agreement
            (ab, None, [600]),  # no explicit agency entitlement: excluded
        ]:
            allocation = CommissionAllocation(agreement_id=agreement.id, agency_id=beneficiary)
            session.add(allocation)
            session.add_all([CommissionPayment(allocation_id=allocation.id, amount=n) for n in amounts])
        # Orphans must not grant access or inflate any total.
        session.add(CommissionPayment(allocation_id=uuid.uuid4(), amount=12345))
        orphan = CommissionAllocation(agreement_id=uuid.uuid4(), agency_id=a)
        session.add(orphan)
        session.add(CommissionPayment(allocation_id=orphan.id, amount=6789))
        for actor, target in [(a, b), (b, a), (a, a), (b, c), (None, None)]:
            session.add(AuditEvent(action=AuditAction.PAYMENT_RECORDED,
                                   actor_agency_id=actor, target_agency_id=target))
        await session.commit()

        app = FastAPI()
        # Same authentication and route-role floor as the production private router.
        app.include_router(router, prefix="/api/v1/network",
                           dependencies=[Depends(deps.get_principal), Depends(deps.require_api_permissions)])
        app.dependency_overrides[deps.get_session] = lambda: session
        app.dependency_overrides[deps.verify_license_active] = lambda: None
        app.dependency_overrides[get_settings] = lambda: Settings(auth_mode=AuthMode.KEYCLOAK)

        def identity(role="ROLE_AGENCY_MANAGER", tenant=a):
            app.dependency_overrides[deps.get_principal] = lambda: Principal(
                subject="synthetic-user", username="synthetic-user",
                realm_roles=frozenset({role}), roles=frozenset({
                    {"ROLE_ADMIN": UserRole.ADMIN, "ROLE_SUPERVISOR": UserRole.SUPERVISOR,
                     "ROLE_AGENCY_MANAGER": UserRole.OFFICE_MANAGER}.get(role, UserRole.AGENT)
                }),
                tenant_id=str(tenant) if tenant is not None else None, kyc_status="VERIFIED",
            )

        identity()
        statements = []
        from sqlalchemy import event

        @event.listens_for(engine.sync_engine, "before_cursor_execute")
        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield client, identity, (a, b, c, d), statements, app
    await engine.dispose()


@pytest.mark.parametrize("path", ["reports", "overview"])
@pytest.mark.parametrize("parameter", [None, "agency_id", "agencyId", "both"])
async def test_omitted_and_compatible_scope_only_return_own_agency(reports, path, parameter):
    client, _, (a, _, _, _), _, _ = reports
    params = {} if parameter is None else {parameter: str(a)}
    if parameter == "both":
        params = {"agency_id": str(a), "agencyId": str(a)}
    response = await client.get(f"/api/v1/network/{path}", params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    if path == "reports":
        for field in ("shares_by_status", "referrals_by_stage", "transfers_by_status",
                      "commissions_by_status", "disputes_by_status", "cooperations_by_status"):
            assert sum(item["count"] for item in body[field]) == 2, field
        assert sum(item["count"] for item in body["audit_by_action"]) == 3
        assert body["total_basis"] == 3000
        assert body["total_paid"] == 60
        # Legacy formula intentionally retained; not a verified receivable.
        assert body["total_remaining"] == 2940
        assert body["conversion_rate_pct"] == 0
    else:
        assert body["agencies_total"] == 1
        assert body["agencies_verified"] == 0
        assert body["shares_total"] == body["shares_active"] == 2
        assert body["cooperations_pending"] == body["referrals_open"] == 2
        assert body["transfers_total"] == body["commissions_open"] == body["disputes_open"] == 2
        assert body["commissions_basis_total"] == 3000
        assert body["commissions_paid_total"] == 60
        assert body["audit_total"] == 3


@pytest.mark.parametrize("path", ["reports", "overview"])
@pytest.mark.parametrize("role", ["ROLE_AGENCY_MANAGER", "ROLE_ADMIN", "ROLE_SUPERVISOR"])
@pytest.mark.parametrize("parameter", ["agency_id", "agencyId"])
async def test_foreign_scope_is_rejected_before_any_query(reports, path, role, parameter):
    client, identity, (a, b, _, _), statements, _ = reports
    identity(role, a)
    response = await client.get(f"/api/v1/network/{path}", params={parameter: str(b)})
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "agency_forbidden"
    assert statements == []


@pytest.mark.parametrize("path", ["reports", "overview"])
@pytest.mark.parametrize("tenant", [None, "invalid", str(uuid.UUID(int=0))])
@pytest.mark.parametrize("role", ["ROLE_AGENCY_MANAGER", "ROLE_ADMIN", "ROLE_SUPERVISOR"])
async def test_invalid_tenant_cannot_be_replaced_by_query_or_headers(reports, path, tenant, role):
    client, identity, (a, _, _, _), statements, _ = reports
    identity(role, tenant)
    response = await client.get(f"/api/v1/network/{path}", params={"agency_id": str(a)},
                                headers={"X-Agency-Id": str(a), "X-User-Role": "ADMIN"})
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "agency_required"
    assert statements == []


@pytest.mark.parametrize("path", ["reports", "overview"])
@pytest.mark.parametrize("role", ["ROLE_SENIOR_BROKER", "ROLE_JUNIOR_BROKER", "financial_admin", "ROLE_DATA_ANALYST", "ROLE_OWNER"])
async def test_personal_policy_and_unrelated_permissions_fail_closed(reports, path, role):
    client, identity, (a, _, _, _), statements, _ = reports
    identity(role, a)
    response = await client.get(f"/api/v1/network/{path}")
    assert response.status_code == 403
    assert statements == []


@pytest.mark.parametrize("path", ["reports", "overview"])
@pytest.mark.parametrize("role", ["ROLE_ADMIN", "ROLE_SUPERVISOR"])
async def test_network_management_roles_have_no_global_bypass(reports, path, role):
    client, identity, (a, _, _, _), _, _ = reports
    identity(role, a)
    response = await client.get(f"/api/v1/network/{path}")
    assert response.status_code == 200
    body = response.json()
    assert body["total_paid" if path == "reports" else "commissions_paid_total"] == 60


@pytest.mark.parametrize("path", ["reports", "overview"])
async def test_conflicting_and_malformed_aliases_are_rejected(reports, path):
    client, _, (a, b, _, _), statements, _ = reports
    for params in [{"agency_id": str(a), "agencyId": str(b)},
                   {"agency_id": str(b), "agencyId": str(a)},
                   {"agency_id": "invalid"}, {"agencyId": "invalid"}]:
        response = await client.get(f"/api/v1/network/{path}", params=params)
        assert response.status_code == 422
    assert statements == []


@pytest.mark.parametrize("path", ["reports", "overview"])
async def test_no_credentials_or_spoofed_headers_cannot_access_reports(reports, path):
    client, _, (a, _, _, _), statements, app = reports
    del app.dependency_overrides[deps.get_principal]
    response = await client.get(f"/api/v1/network/{path}", headers={
        "X-Agency-Id": str(a), "X-User-Role": "ADMIN",
    })
    assert response.status_code == 401
    assert statements == []


@pytest.mark.parametrize("path", ["reports", "overview"])
async def test_empty_agency_is_not_filled_with_network_totals(reports, path):
    client, identity, (_, _, _, d), _, _ = reports
    identity(tenant=d)
    response = await client.get(f"/api/v1/network/{path}")
    assert response.status_code == 200
    body = response.json()
    if path == "reports":
        assert body["total_paid"] == body["total_basis"] == body["total_remaining"] == 0
        assert all(body[field] == [] for field in body if field.endswith("status") or field.endswith("stage") or field == "audit_by_action")
    else:
        assert body["commissions_paid_total"] == body["commissions_basis_total"] == body["audit_total"] == 0


async def test_reciprocal_agency_reads_its_own_payments_not_partners(reports):
    client, identity, (_, b, _, _), _, _ = reports
    identity(tenant=b)
    response = await client.get("/api/v1/network/reports")
    assert response.status_code == 200
    assert response.json()["total_paid"] == 8700


async def test_openapi_retains_paths_fields_and_documents_both_parameters(reports):
    _, _, _, _, app = reports
    schema = app.openapi()
    for path in ("reports", "overview"):
        operation = schema["paths"][f"/api/v1/network/{path}"]["get"]
        params = {p["name"]: p for p in operation["parameters"]}
        assert "agency_id" in params
        assert params["agencyId"]["deprecated"] is True
    fields = schema["components"]["schemas"]["NetworkReportsRead"]["properties"]
    assert {"total_paid", "total_basis", "total_remaining", "audit_by_action"} <= fields.keys()


@pytest.mark.parametrize("path", ["reports", "overview"])
async def test_actual_application_router_uses_the_scope_dependency(reports, path):
    from app.api.v1.router import api_router

    _, _, (a, b, _, _), statements, probe = reports
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.dependency_overrides.update(probe.dependency_overrides)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/network/{path}")
        assert response.status_code == 200
        assert response.json()["total_paid" if path == "reports" else "commissions_paid_total"] == 60
        statements.clear()
        response = await client.get(f"/api/v1/network/{path}", params={"agency_id": str(b)})
        assert response.status_code == 403
        assert statements == []


@pytest.mark.parametrize("path", ["reports", "overview"])
async def test_pending_identity_cannot_use_report_scope(reports, monkeypatch, path):
    from unittest.mock import AsyncMock

    client, _, (a, _, _, _), statements, app = reports
    del app.dependency_overrides[deps.get_principal]
    monkeypatch.setattr(deps, "principal_from_token", AsyncMock(return_value=Principal(
        subject="pending", tenant_id=str(a), realm_roles=frozenset({"ROLE_ADMIN"}),
        roles=frozenset({UserRole.ADMIN}), kyc_status="PENDING",
    )))
    response = await client.get(f"/api/v1/network/{path}", headers={"Authorization": "Bearer synthetic"})
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "kyc_pending"
    assert statements == []