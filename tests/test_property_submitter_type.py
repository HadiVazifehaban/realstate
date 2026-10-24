"""Who filed a listing: the submitter class, and the trust boundary around it.

Before this, ``POST /properties`` took no ``Principal`` at all and the service
hard-coded ``source = MANUAL_OFFICE``. Two consequences are locked down here:

1. **Identity.** The class of party (شخص حقیقی / بنگاه) is derived from the
   signed token, never from the request body. A broker who can name their own
   submitter class can file an office listing as a private owner and inherit the
   owner's provenance ranking plus the «مالک مستقیم» badge.
2. **Provenance.** ``source`` is derived from that class instead of hard-coded,
   so a genuine owner registration finally outranks an office one, and the
   ``PriceChangeSource`` on the price row says *who announced the figure* rather
   than always claiming the owner did.

The three concepts stay separate, because they are three facts: the account that
filed it, the class of party that filed it, and who actually owns the unit.
"""

from __future__ import annotations

import pytest

from app.core.identity import (
    BOOTSTRAP_SUBJECT,
    IdentityError,
    Principal,
    submitter_type_for,
)
from app.models.enums import (
    SOURCE_PRECEDENCE,
    SUBMITTER_ROLES,
    SUBMITTER_TYPE_BY_ROLE,
    PriceChangeSource,
    PropertySource,
    SubmitterType,
    UserRole,
)


def _principal(*roles: UserRole) -> Principal:
    return Principal(
        subject="usr-submit-1",
        username="09120000000",
        full_name="زهرا محمدی",
        roles=frozenset(roles),
        kyc_status="VERIFIED",
    )


# --------------------------------------------------------------------------- #
# The submitter class comes from the token, not the body
# --------------------------------------------------------------------------- #
def test_owner_role_is_a_natural_person() -> None:
    assert submitter_type_for(_principal(UserRole.OWNER)) is SubmitterType.PERSON


@pytest.mark.parametrize(
    "role",
    [UserRole.AGENT, UserRole.OFFICE_MANAGER, UserRole.SUPERVISOR, UserRole.ADMIN],
)
def test_desk_roles_are_an_agency(role: UserRole) -> None:
    assert submitter_type_for(_principal(role)) is SubmitterType.AGENCY


def test_a_role_with_no_submitter_class_is_refused_not_defaulted() -> None:
    """A silent default to AGENCY is how an unattributed write becomes office
    business in the audit trail."""
    with pytest.raises(IdentityError) as excinfo:
        submitter_type_for(_principal(UserRole.USER))
    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_a_submitter"


def test_the_least_privileged_submitter_role_wins() -> None:
    """Deliberately the inverse of ``ROLE_ORDER``'s higher-wins fold.

    A token holding both ROLE_OWNER and ROLE_SENIOR_BROKER is somebody who both
    owns property and works a desk. Folding that to AGENT would silently
    reclassify their own listing as office business.
    """
    dual = submitter_type_for(_principal(UserRole.OWNER, UserRole.AGENT))
    assert dual is SubmitterType.PERSON


def test_admin_alone_is_not_a_person() -> None:
    """``ROLE_ADMIN`` is not a shortcut to the owner's trust ranking either."""
    assert submitter_type_for(_principal(UserRole.ADMIN)) is SubmitterType.AGENCY


def test_the_bootstrap_node_operator_is_an_agency() -> None:
    """LICENSE mode has no IdP, so its synthetic principal still has to resolve.

    Refusing it would take the whole offline-office node down with it.
    """
    from app.core.identity import bootstrap_principal

    assert submitter_type_for(bootstrap_principal()) is SubmitterType.AGENCY
    assert bootstrap_principal().subject == BOOTSTRAP_SUBJECT


def test_every_submitter_role_names_a_class_and_vice_versa() -> None:
    assert set(SUBMITTER_TYPE_BY_ROLE) == set(SUBMITTER_ROLES)


def test_a_plain_authenticated_visitor_is_not_a_submitter() -> None:
    """USER/GUEST may browse the showcase and file a report -- not register."""
    assert UserRole.USER not in SUBMITTER_ROLES
    assert UserRole.GUEST not in SUBMITTER_ROLES


# --------------------------------------------------------------------------- #
# The request body cannot carry the class
# --------------------------------------------------------------------------- #
def test_the_submit_request_has_no_submitter_type_field() -> None:
    """The whole point: a body-supplied class is a spoofable grant.

    ``PERSON`` outranks ``AGENCY`` at provenance 100 vs 80, so letting a caller
    name it would let an office overwrite a genuine owner's listing.
    """
    from app.schemas.properties import PropertySubmitRequest

    assert "submitter_type" not in PropertySubmitRequest.model_fields


def test_a_spoofed_submitter_type_in_the_body_is_ignored() -> None:
    """An older client that still sends one must keep working, not 422."""
    from app.schemas.properties import PropertySubmitRequest

    payload = PropertySubmitRequest(
        latitude=35.7,
        longitude=51.4,
        title="آپارتمان تست",
        submitter_type="PERSON",  # type: ignore[call-arg]
    )
    assert not hasattr(payload, "submitter_type")


# --------------------------------------------------------------------------- #
# Provenance: source and price history follow the class
# --------------------------------------------------------------------------- #
def test_an_owner_registration_outranks_an_office_one() -> None:
    """The precedence table only means something if the two differ."""
    assert (
        SOURCE_PRECEDENCE[PropertySource.INTERNAL_USER]
        > SOURCE_PRECEDENCE[PropertySource.INTERNAL_AGENCY]
    )
    assert PriceChangeSource.OWNER.value == "OWNER"
    assert PriceChangeSource.MANUAL.value == "MANUAL"


# --------------------------------------------------------------------------- #
# The endpoint is no longer anonymous
# --------------------------------------------------------------------------- #
def _submit_route():
    """The mounted POST /properties operation, read off the generated schema.

    FastAPI 1.x nests routers behind ``_IncludedRouter`` wrappers whose route
    trees are not uniformly walkable, so the OpenAPI document is the one place
    the fully-resolved path is guaranteed to be visible.
    """
    from app.main import create_app

    spec = create_app().openapi()["paths"].get("/api/v1/properties", {})
    assert "post" in spec, "POST /api/v1/properties is not mounted"
    return spec["post"]


def test_the_submit_route_is_mounted_and_takes_a_body() -> None:
    """Guards against the route silently moving out from under the tests."""
    operation = _submit_route()
    assert "requestBody" in operation


def test_the_submit_route_demands_a_principal() -> None:
    """The regression that mattered most: the route used to take no identity.

    ``POST /properties`` is the write that creates a listing, prices it, and
    writes owner contacts into the encrypted vault. It sat behind the licence
    guard alone, so any caller on a licensed node could register a property and
    nobody could tell afterwards who had.
    """
    import inspect

    from app.api.v1.endpoints.properties import submit_property

    parameters = inspect.signature(submit_property).parameters
    assert "principal" in parameters, "the handler no longer resolves a caller"
    assert "PrincipalDep" in str(parameters["principal"].annotation)


def test_an_unauthenticated_submit_is_refused() -> None:
    """End to end through the real dependency chain, in Keycloak mode.

    LICENSE mode substitutes a bootstrap principal (an isolated office with no
    IdP), so the 401 only appears where a token is actually the identity.
    """
    import asyncio

    from fastapi.testclient import TestClient

    from app.core.config import AuthMode, Settings
    from app.main import create_app
    from app.api import deps as deps_module

    app = create_app()
    app.dependency_overrides[deps_module.SettingsDep] = lambda: Settings(
        auth_mode=AuthMode.KEYCLOAK,
        keycloak_issuer="https://auth.example.test/realms/maskanchi",
        keycloak_audience="maskanchi-backend-api",
    )

    def _status() -> int:
        with TestClient(app, raise_server_exceptions=False) as client:
            return client.post(
                "/api/v1/properties",
                json={"latitude": 35.7, "longitude": 51.4, "title": "آگهی ناشناس"},
            ).status_code

    try:
        assert asyncio.run(asyncio.to_thread(_status)) == 401
    finally:
        app.dependency_overrides.pop(deps_module.SettingsDep, None)


# --------------------------------------------------------------------------- #
# A real write: the class decides `source`, the snapshot, and the price row
# --------------------------------------------------------------------------- #
def _run(coro):
    """Drive one coroutine on a dedicated loop (see ``test_visit_slots``)."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _session():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.orm import sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

    from tests.conftest import create_sqlite_schema

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_sqlite_schema(
        engine, "property", "property_price_history", "property_owner_pii"
    )
    maker = sessionmaker(engine, class_=SQLModelAsyncSession, expire_on_commit=False)
    return maker()


def _submit(session, *, submitter_type, cipher=None, **overrides):
    """One direct submission, with the geocoder stubbed out.

    The reverse geocoder is deliberately not contacted: the point of this test
    is what gets written, and a network call would make it a flake. ``cipher``
    is injectable so a test can read the vault back afterwards.
    """
    from unittest.mock import AsyncMock, patch

    from app.core.crypto import PiiCipher
    from app.services import submission

    payload = {
        "latitude": 35.7,
        "longitude": 51.4,
        "deal_type": "SALE",
        "property_type": "APARTMENT",
        "title": "آپارتمان ۱۲۰ متری",
        "area": 120.0,
        "total_price": 12_000_000_000,
        "owner_name": "زهرا محمدی",
        "owner_phone": "09121234567",
        "submitter_type": submitter_type,
        "settings": None,
        "cipher": cipher or PiiCipher(PiiCipher.generate_key()),
    }
    payload.update(overrides)
    with patch.object(submission, "reverse_geocode", AsyncMock(return_value={})):
        return _run(submission.submit_property(session, **payload))


def _load(session, property_id):
    from sqlmodel import select

    from app.models import Property, PropertyPriceHistory

    prop = _run(session.get(Property, property_id))
    history = _run(
        session.exec(
            select(PropertyPriceHistory).where(
                PropertyPriceHistory.property_id == property_id
            )
        )
    ).first()
    return prop, history


def test_an_owner_filing_their_own_unit_is_stamped_person() -> None:
    session = _run(_session())
    try:
        result = _submit(session, submitter_type=SubmitterType.PERSON)
        prop, history = _load(session, result.property_id)
        assert prop.submitter_type is SubmitterType.PERSON
        # The provenance the owner's copy is supposed to have, which no code
        # path wrote before this.
        assert prop.source is PropertySource.INTERNAL_USER
        assert history is not None
        assert history.source is PriceChangeSource.OWNER
    finally:
        _run(session.close())


def test_a_broker_filing_a_client_unit_is_stamped_agency() -> None:
    """The case the old code could not express at all.

    The submitter is the office, so ``source`` and ``submitter_type`` say so --
    but the contacts in the vault stay the *owner's*, and the price row stops
    claiming the owner set it.
    """
    session = _run(_session())
    try:
        result = _submit(session, submitter_type=SubmitterType.AGENCY)
        prop, history = _load(session, result.property_id)
        assert prop.submitter_type is SubmitterType.AGENCY
        assert prop.source is PropertySource.INTERNAL_AGENCY
        assert history is not None
        assert history.source is PriceChangeSource.MANUAL
    finally:
        _run(session.close())


def test_owner_contacts_survive_an_agency_submission() -> None:
    """The filer's class must never overwrite who is on the deed."""
    from app.core.crypto import PiiCipher
    from app.models import PropertyOwnerPII
    from sqlmodel import select

    session = _run(_session())
    cipher = PiiCipher(PiiCipher.generate_key())
    try:
        result = _submit(
            session, submitter_type=SubmitterType.AGENCY, cipher=cipher
        )
        vault = _run(
            session.exec(
                select(PropertyOwnerPII).where(
                    PropertyOwnerPII.property_id == result.property_id
                )
            )
        ).first()
        assert vault is not None
        assert cipher.decrypt(vault.owner_name_enc) == "زهرا محمدی"
        assert cipher.decrypt(vault.owner_phone_enc) == "09121234567"
    finally:
        _run(session.close())


def test_an_unattributed_internal_write_stays_unknown() -> None:
    """No submitter to attribute must not become a guessed AGENCY."""
    session = _run(_session())
    try:
        result = _submit(session, submitter_type=None)
        prop, _history = _load(session, result.property_id)
        assert prop.submitter_type is None
    finally:
        _run(session.close())

