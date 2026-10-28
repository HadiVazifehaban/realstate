"""Aggregated v1 router."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_principal, require_api_permissions, require_principal_roles
from app.models.enums import UserRole

from app.api.v1.endpoints import (
    admin_users,
    auth,
    billing,
    chat,
    crm,
    gis,
    health,
    license,
    keycloak_admin,
    matching,
    market_demand,
    network,
    network_reports,
    otp,
    preferences,
    properties,
    scraper,
    statistics,
    social_links,
    users,
    zibal_settings,
)

# Identity is enforced by default. Only liveness and the explicit registration
# front door are public; routers with account data, operational data, licensing,
# or audit data all require a Keycloak bearer token.
API_GUARD = [Depends(get_principal)]

api_router = APIRouter()
api_router.include_router(billing.public_router, prefix="/billing", tags=["billing-catalog"])
api_router.include_router(social_links.public_router, prefix="/site", tags=["site"])
# Own role guard permits super_admin without granting it unrelated admin powers.
api_router.include_router(
    social_links.admin_router, prefix="/admin/social-links", tags=["site-admin"]
)
api_router.include_router(
    zibal_settings.router, prefix="/admin/integrations/zibal", tags=["gateway-admin"]
)
api_router.include_router(health.router, tags=["health"])

# The phone-verification registration endpoints are the only non-Keycloak API
# entry point retained. They cannot issue an API session in KEYCLOAK mode.
api_router.include_router(auth.public_router, prefix="/auth", tags=["registration"])
api_router.include_router(
    auth.registration_router, prefix="/registration", tags=["registration"]
)

private_router = APIRouter(
    dependencies=[*API_GUARD, Depends(require_api_permissions)]
)
private_router.include_router(license.router, prefix="/license", tags=["license"])
private_router.include_router(billing.router, prefix="/billing", tags=["billing"])
private_router.include_router(
    billing.financial_router,
    prefix="/admin/financial",
    tags=["financial"],
)
private_router.include_router(otp.router, tags=["otp"])
private_router.include_router(auth.router, prefix="/auth", tags=["auth"])
private_router.include_router(scraper.router, prefix="/scraper", tags=["scraper"])
private_router.include_router(market_demand.router, prefix="/properties", tags=["properties"])
private_router.include_router(properties.router, prefix="/properties", tags=["properties"])
private_router.include_router(matching.router, prefix="/matching", tags=["matching"])
private_router.include_router(crm.router, prefix="/crm", tags=["crm"])
private_router.include_router(chat.router, prefix="/chat", tags=["chat"])
private_router.include_router(users.router, prefix="/users", tags=["users"])
private_router.include_router(preferences.router, prefix="/users", tags=["preferences"])
private_router.include_router(gis.router, prefix="/gis", tags=["gis"])
private_router.include_router(network.router, prefix="/network", tags=["network"])
private_router.include_router(network_reports.router, prefix="/network", tags=["network"])
private_router.include_router(statistics.router, prefix="/statistics", tags=["statistics"])
# User directory and role mutation are administrative operations.
private_router.include_router(
    admin_users.router,
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_principal), Depends(require_principal_roles(UserRole.ADMIN))],
)
private_router.include_router(
    keycloak_admin.router,
    prefix="/admin/keycloak",
    tags=["keycloak-admin"],
    dependencies=[Depends(get_principal), Depends(require_principal_roles(UserRole.ADMIN))],
)
api_router.include_router(private_router)

__all__ = ["api_router"]
