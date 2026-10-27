"""Identity tests: realm-role mapping, the approval gate and the PII veto.

These encode the security posture from the blueprint: a token decides who you
are, a role decides what you may do, and *neither* is enough while KYC is
pending. The cases below are the ones where a plausible implementation leaks.
"""

from __future__ import annotations

import pytest

from app.core.config import AuthMode, Settings
from app.core.identity import (
    IdentityError,
    Principal,
    bootstrap_principal,
    principal_from_claims,
    require_approval,
    require_pii_access,
    require_roles,
)
from app.models.enums import SaasTier, UserRole

ISSUER = "https://auth.maskanchi.ir/realms/maskanchi-platform"


def _settings(**overrides) -> Settings:
    """Keycloak-mode settings; the issuer is present but never contacted here."""
    return Settings(
        auth_mode=AuthMode.KEYCLOAK,
        keycloak_issuer=ISSUER,
        keycloak_audience="maskanchi-backend-api",
        **overrides,
    )


def _claims(**overrides) -> dict:
    base = {
        "sub": "usr-1",
        "iss": ISSUER,
        "aud": "maskanchi-backend-api",
        "realm_access": {"roles": ["ROLE_SENIOR_BROKER"]},
        "kyc_status": "VERIFIED",
        "preferred_username": "09121854920",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Role mapping
# --------------------------------------------------------------------------- #
def test_realm_roles_map_onto_the_internal_ladder() -> None:
    principal = principal_from_claims(_claims(), _settings())
    assert UserRole.AGENT in principal.roles
    assert principal.saas_tier is SaasTier.BASIC


def test_the_most_privileged_role_wins() -> None:
    """An admin who also holds a broker role is still an admin."""
    principal = principal_from_claims(
        _claims(realm_access={"roles": ["ROLE_SENIOR_BROKER", "ROLE_ADMIN"]}),
        _settings(),
    )
    assert principal.roles == frozenset({UserRole.ADMIN})
    assert principal.saas_tier is SaasTier.ENTERPRISE


def test_the_default_realm_role_is_not_treated_as_a_grant() -> None:
    principal = principal_from_claims(
        _claims(realm_access={"roles": ["default-roles-maskanchi-platform"]}),
        _settings(),
    )
    assert principal.roles == frozenset()


def test_an_unknown_role_grants_nothing() -> None:
    principal = principal_from_claims(
        _claims(realm_access={"roles": ["ROLE_WHATEVER"]}), _settings()
    )
    assert principal.roles == frozenset()
    with pytest.raises(IdentityError):
        require_roles(principal, {UserRole.AGENT})


def test_a_token_cannot_grant_itself_an_unlimited_quota() -> None:
    """The quota claim is capped by node configuration, not trusted as-is."""
    principal = principal_from_claims(
        _claims(daily_pii_quota=10_000_000), _settings(pii_quota_hard_cap=200)
    )
    assert principal.daily_pii_quota == 200


def test_a_non_numeric_quota_claim_degrades_to_zero() -> None:
    principal = principal_from_claims(_claims(daily_pii_quota="lots"), _settings())
    assert principal.daily_pii_quota == 0


# --------------------------------------------------------------------------- #
# Approval gate
# --------------------------------------------------------------------------- #
def test_a_pending_identity_is_refused_even_with_a_broker_role() -> None:
    """The core rule: a role is never enough on its own."""
    principal = principal_from_claims(
        _claims(
            realm_access={"roles": ["ROLE_ADMIN"]},
            kyc_status="PENDING",
        ),
        _settings(),
    )
    with pytest.raises(IdentityError) as exc:
        require_approval(principal, _settings())
    assert exc.value.status_code == 403
    assert exc.value.code == "kyc_pending"


def test_a_verified_identity_passes_the_gate() -> None:
    principal = principal_from_claims(_claims(), _settings())
    require_approval(principal, _settings())


# --------------------------------------------------------------------------- #
# PII veto
# --------------------------------------------------------------------------- #
def test_an_analyst_is_refused_the_vault() -> None:
    """Even with a broker role, the explicit deny role wins."""
    principal = principal_from_claims(
        _claims(realm_access={"roles": ["ROLE_DATA_ANALYST", "ROLE_ADMIN"]}),
        _settings(),
    )
    with pytest.raises(IdentityError) as exc:
        require_pii_access(principal)
    assert exc.value.code == "pii_forbidden"


def test_a_broker_may_read_the_vault() -> None:
    require_pii_access(principal_from_claims(_claims(), _settings()))


def test_an_ordinary_verified_user_may_not_read_the_vault() -> None:
    principal = principal_from_claims(
        _claims(realm_access={"roles": ["ROLE_VERIFIED_USER"]}), _settings()
    )
    with pytest.raises(IdentityError):
        require_pii_access(principal)


def test_verified_realm_role_without_mobile_claim_is_not_effective() -> None:
    principal = principal_from_claims(
        _claims(realm_access={"roles": ["ROLE_VERIFIED_USER"]}), _settings()
    )
    assert "ROLE_VERIFIED_USER" not in principal.realm_roles
    assert principal.roles == frozenset()


def test_verified_realm_role_with_mobile_claim_remains_effective() -> None:
    principal = principal_from_claims(
        _claims(
            realm_access={"roles": ["ROLE_VERIFIED_USER"]},
            mobile_verified=True,
        ),
        _settings(),
    )
    assert "ROLE_VERIFIED_USER" in principal.realm_roles
    assert UserRole.USER in principal.roles


# --------------------------------------------------------------------------- #
# Offline office mode
# --------------------------------------------------------------------------- #
def test_the_bootstrap_principal_is_flagged_as_synthetic() -> None:
    """An audit row must say "the node did this", not imply a signed-in person."""
    principal = bootstrap_principal()
    assert principal.subject == "node-bootstrap"
    assert principal.is_verified
    assert principal.roles == frozenset({UserRole.ADMIN})


def test_describe_never_leaks_the_token() -> None:
    summary = bootstrap_principal().describe()
    assert "token" not in summary
    assert summary["subject"] == "node-bootstrap"
