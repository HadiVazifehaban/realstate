#!/usr/bin/env python3
"""Grant the isolated test directory client its minimal Keycloak permissions."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


async def main() -> None:
    issuer = required("PHASE15_TEST_KEYCLOAK_ISSUER").rstrip("/")
    realm = required("PHASE15_TEST_KEYCLOAK_REALM")
    client_id = required("PHASE15_TEST_KEYCLOAK_CLIENT_ID")
    client_secret = required("PHASE15_TEST_KEYCLOAK_CLIENT_SECRET")
    admin_user = required("PHASE15_TEST_KEYCLOAK_BOOTSTRAP_USER")
    admin_password = required("PHASE15_TEST_KEYCLOAK_BOOTSTRAP_PASSWORD")
    if realm != "shekarchi-phase15-test" or "phase15" not in issuer.lower():
        raise SystemExit("Refusing a non-Phase-1.5 Keycloak target")
    base = issuer.split("/realms/", 1)[0]
    async with httpx.AsyncClient(timeout=5.0) as client:
        token_response = await client.post(
            f"{base}/realms/master/protocol/openid-connect/token",
            data={"grant_type": "password", "client_id": "admin-cli",
                  "username": admin_user, "password": admin_password},
        )
        token_response.raise_for_status()
        admin_token = token_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        realm_check = await client.get(f"{base}/admin/realms/{realm}", headers=headers)
        if realm_check.status_code == 404:
            realm_file = Path(os.getenv("PHASE15_REALM_FILE", "/tmp/shekarchi-phase15-test-realm.json"))
            payload = json.loads(realm_file.read_text(encoding="utf-8"))
            created = await client.post(
                f"{base}/admin/realms", headers={**headers, "Content-Type": "application/json"},
                json=payload,
            )
            created.raise_for_status()
        elif realm_check.status_code != 200:
            realm_check.raise_for_status()

        clients = (await client.get(f"{base}/admin/realms/{realm}/clients",
                                    headers=headers, params={"clientId": client_id})).json()
        if len(clients) != 1:
            raise SystemExit("test directory client was not found uniquely")
        client_uuid = clients[0]["id"]
        client_config = dict(clients[0])
        client_config["defaultClientScopes"] = ["roles"]
        # Keycloak only emits the service-account client roles for this Admin
        # API client when full scope is enabled. The account itself is still
        # limited to the three explicit realm-management roles below.
        client_config["fullScopeAllowed"] = True
        updated = await client.put(
            f"{base}/admin/realms/{realm}/clients/{client_uuid}",
            headers={**headers, "Content-Type": "application/json"},
            json=client_config,
        )
        updated.raise_for_status()
        service_user = await client.get(
            f"{base}/admin/realms/{realm}/clients/{client_uuid}/service-account-user",
            headers=headers,
        )
        service_user.raise_for_status()
        service_user_id = service_user.json()["id"]
        management = (await client.get(
            f"{base}/admin/realms/{realm}/clients", headers=headers,
            params={"clientId": "realm-management"}
        )).json()
        if len(management) != 1:
            raise SystemExit("realm-management client was not found")
        management_id = management[0]["id"]
        roles = (await client.get(
            f"{base}/admin/realms/{realm}/clients/{management_id}/roles",
            headers=headers, params={"max": 100}
        )).json()
        wanted = {role["name"]: role for role in roles if role["name"] in {
            "view-users", "query-users", "manage-users"
        }}
        if len(wanted) != 3:
            raise SystemExit("required limited realm-management roles were not found")
        response = await client.post(
            f"{base}/admin/realms/{realm}/users/{service_user_id}/role-mappings/clients/{management_id}",
            headers={**headers, "Content-Type": "application/json"},
            json=list(wanted.values()),
        )
        response.raise_for_status()

        service_token = await client.post(
            f"{issuer}/protocol/openid-connect/token",
            data={"grant_type": "client_credentials", "client_id": client_id,
                  "client_secret": client_secret},
        )
        service_token.raise_for_status()
        directory = await client.get(
            f"{base}/admin/realms/{realm}/users", headers={
                "Authorization": f"Bearer {service_token.json()['access_token']}"
            }, params={"max": 1},
        )
        directory.raise_for_status()
    print("Phase 1.6.2 Keycloak service account verified with limited directory access")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (httpx.HTTPError, KeyError) as exc:
        print(f"Phase 1.6.2 Keycloak bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
