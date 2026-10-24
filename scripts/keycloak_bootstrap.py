#!/usr/bin/env python3
"""Grant the backend's service account the realm-management roles it needs.

Why this exists
---------------
``keycloak/realm-export.json`` declares the ``maskanchi-admin-cli`` client and
its service account, but a realm import silently drops the ``clientRoles`` block
on a service-account user: Keycloak synthesises that user from the client, so
the role mappings never get applied and every Admin REST call comes back 403.

Rather than fight the importer, the realm file stays the declarative source of
roles/clients/seed users and this script finishes the one assignment the
importer cannot express. It is idempotent -- it computes the missing roles and
adds only those -- so it is safe to run on every boot and after every re-import.

Usage:
    python scripts/keycloak_bootstrap.py
    python scripts/keycloak_bootstrap.py --url http://localhost:8082

Reads KEYCLOAK_ADMIN / KEYCLOAK_ADMIN_PASSWORD from the environment or .env.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

#: The minimum the user directory needs. `view-users`/`query-users` cover
#: listing; `manage-users` additionally backs the dashboard's invite/edit
#: buttons. Deliberately no `admin-console` and nothing that can read realm
#: keys -- this token is minted with no user present.
REQUIRED_ROLES = ("view-users", "query-users", "manage-users")

#: Custom user attributes the FastAPI core reads out of the token. Without them
#: declared in the realm's user profile, Keycloak *silently drops* them on any
#: Admin REST write: a user invited from the dashboard would come out with no
#: `kyc_status`, and `require_approval` would then refuse every one of their API
#: calls with no obvious way out.
REQUIRED_ATTRIBUTES: tuple[tuple[str, str, int], ...] = (
    ("kyc_status", "KYC status", 32),
    ("tenant_id", "Tenant", 128),
    ("agency_name", "Agency", 128),
    ("daily_pii_quota", "Daily PII quota", 16),
    ("mobile_verified", "Mobile verified", 8),
    ("phone", "Phone", 32),
)

REALM_MANAGEMENT = "realm-management"
ADMIN_CLIENT = "maskanchi-admin-cli"


def load_dotenv(path: Path) -> None:
    """Minimal .env reader: does not overwrite variables already in the env."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


class KeycloakError(RuntimeError):
    pass


def _request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    form: dict | None = None,
    js: dict | None = None,
) -> object:
    if form and js:
        raise KeycloakError("_request accepts either form= or js=, not both")
    data = urllib.parse.urlencode(form).encode() if form else (json.dumps(js).encode() if js is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data:
        req.add_header(
            "Content-Type",
            "application/json" if js is not None else "application/x-www-form-urlencoded",
        )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:400]
        raise KeycloakError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise KeycloakError(f"{method} {url} -> {exc.reason}") from exc
    if not body:
        return None
    return json.loads(body)


def wait_for_keycloak(base: str, timeout: int) -> None:
    """Block until the realm endpoint answers, so compose and this can race."""
    deadline = time.monotonic() + timeout
    probe = f"{base}/realms/master"
    last = ""
    while time.monotonic() < deadline:
        try:
            _request("GET", probe)
            return
        except KeycloakError as exc:
            last = str(exc)
            time.sleep(3)
    raise KeycloakError(f"Keycloak not reachable at {base} after {timeout}s: {last}")


def admin_token(base: str, username: str, password: str) -> str:
    payload = _request(
        "POST",
        f"{base}/realms/master/protocol/openid-connect/token",
        form={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": username,
            "password": password,
        },
    )
    assert isinstance(payload, dict)
    token = payload.get("access_token")
    if not token:
        raise KeycloakError("master realm returned no access_token")
    return str(token)


def find_client(base: str, token: str, realm: str, client_id: str) -> dict:
    clients = _request(
        "GET",
        f"{base}/admin/realms/{realm}/clients",
        token=token,
    )
    for client in clients or []:  # type: ignore[union-attr]
        if client.get("clientId") == client_id:
            return client
    raise KeycloakError(f"client {client_id!r} not found in realm {realm!r}")


def service_account_id(base: str, token: str, realm: str, client_id: str) -> str:
    """Look the service account up by username.

    The collection endpoint (`/admin/realms/{realm}/users`) does not return
    service accounts at all, so filtering the list client-side can never find
    this user. The `username=` filter does match it.
    """
    wanted = f"service-account-{client_id}"
    users = _request(
        "GET",
        f"{base}/admin/realms/{realm}/users?username={urllib.parse.quote(wanted)}&exact=true",
        token=token,
    ) or []
    for user in users:
        if user.get("username") == wanted:
            return str(user["id"])
    raise KeycloakError(f"service account user {wanted!r} not found")


def granted_roles(base: str, token: str, realm: str, rm_uuid: str, user_id: str) -> set[str]:
    roles = _request(
        "GET",
        f"{base}/admin/realms/{realm}/users/{user_id}/role-mappings/clients/{rm_uuid}",
        token=token,
    ) or []
    return {r["name"] for r in roles}


def realm_management_uuid(base: str, token: str, realm: str) -> str:
    clients = _request(
        "GET",
        f"{base}/admin/realms/{realm}/clients",
        token=token,
    ) or []
    for client in clients:
        if client.get("clientId") == REALM_MANAGEMENT:
            return str(client["id"])
    raise KeycloakError(f"{REALM_MANAGEMENT} client missing from realm {realm!r}")


def available_roles(base: str, token: str, realm: str, rm_uuid: str) -> dict[str, dict]:
    roles = _request(
        "GET",
        f"{base}/admin/realms/{realm}/clients/{rm_uuid}/roles",
        token=token,
    ) or []
    return {r["name"]: r for r in roles if r.get("name") in REQUIRED_ROLES}


def grant_roles(
    base: str, token: str, realm: str, rm_uuid: str, user_id: str, roles: list[dict]
) -> None:
    """POST the role mappings as a bare JSON array.

    Keycloak wants a raw JSON body here, which the urlencoded helper cannot
    express, so this call is issued by hand.
    """
    req = urllib.request.Request(
        f"{base}/admin/realms/{realm}/users/{user_id}/role-mappings/clients/{rm_uuid}",
        data=json.dumps(roles).encode(),
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30):
            pass
    except urllib.error.HTTPError as exc:
        raise KeycloakError(
            f"role grant failed: HTTP {exc.code}: {exc.read().decode(errors='replace')[:400]}"
        ) from exc


def ensure_user_profile(base: str, token: str, realm: str) -> str:
    """Declare the custom attributes on the realm's user profile.

    Keycloak 26 keeps this configuration *outside* the realm representation, so
    it cannot live in ``realm-export.json`` -- like the service-account roles,
    it has to be applied after the realm exists.

    Two sharp edges, both found the hard way:

    * ``unmanagedAttributePolicy`` makes the PUT fail with a bare
      "Cannot parse the JSON", so it is deliberately not sent.
    * The resolved GET form carries display metadata (``displayHeader`` on
      groups, exotic validator names on attributes) that the PUT parser
      rejects, so the payload is rebuilt rather than echoed back.
    """
    profile = _request("GET", f"{base}/admin/realms/{realm}/users/profile", token=token)
    if not isinstance(profile, dict):
        raise KeycloakError(f"could not read the user profile of realm {realm!r}")

    attributes: list[dict] = []
    for attr in profile.get("attributes") or []:
        validations = attr.get("validations") or {}
        # Keep only the validators the PUT parser understands.
        kept = {k: validations[k] for k in ("length", "email") if k in validations}
        entry: dict = {
            "name": attr["name"],
            "displayName": attr.get("displayName") or attr["name"],
        }
        if kept:
            entry["validations"] = kept
        if attr.get("required"):
            entry["required"] = attr["required"]
        entry["permissions"] = attr.get("permissions") or {
            "view": ["admin", "user"],
            "edit": ["admin", "user"],
        }
        entry["multivalued"] = bool(attr.get("multivalued"))
        attributes.append(entry)

    present = {a["name"] for a in attributes}
    missing = [(n, d, m) for n, d, m in REQUIRED_ATTRIBUTES if n not in present]
    for name, display, max_len in missing:
        attributes.append(
            {
                "name": name,
                "displayName": display,
                "validations": {"length": {"max": max_len}},
                "permissions": {"view": ["admin", "user"], "edit": ["admin", "user"]},
                "multivalued": False,
            }
        )

    if not missing:
        return "already declared"

    # The resolved groups carry displayHeader/displayDescription, which the PUT
    # parser rejects; reduce them to bare names.
    groups = [{"name": g["name"]} for g in profile.get("groups") or []]
    _request(
        "PUT",
        f"{base}/admin/realms/{realm}/users/profile",
        token=token,
        js={"attributes": attributes, "groups": groups},
    )
    return f"declared {', '.join(n for n, _, _ in missing)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.environ.get("KEYCLOAK_PUBLIC_URL", "http://localhost:8082"),
        help="Base URL of the Keycloak server (default: KEYCLOAK_PUBLIC_URL)",
    )
    parser.add_argument("--realm", default=os.environ.get("KEYCLOAK_REALM", "maskanchi"))
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    base = args.url.rstrip("/")
    username = os.environ.get("KEYCLOAK_ADMIN", "admin")
    password = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin")

    try:
        wait_for_keycloak(base, args.timeout)
        token = admin_token(base, username, password)
        # The roles are realm-management *client* roles, so every read and grant
        # below is addressed to the realm-management client UUID -- not to the
        # UUID of maskanchi-admin-cli, which owns no roles of its own.
        find_client(base, token, args.realm, ADMIN_CLIENT)  # fail fast if absent
        rm_uuid = realm_management_uuid(base, token, args.realm)
        user_id = service_account_id(base, token, args.realm, ADMIN_CLIENT)
        current = granted_roles(base, token, args.realm, rm_uuid, user_id)
        catalog = available_roles(base, token, args.realm, rm_uuid)

        missing = [r for r in REQUIRED_ROLES if r in catalog and r not in current]
        absent = [r for r in REQUIRED_ROLES if r not in catalog]

        if absent:
            print(
                "ERROR: realm-management is missing "
                f"{', '.join(absent)}. Is {args.realm!r} the imported realm?",
                file=sys.stderr,
            )
            return 1

        if missing:
            grant_roles(base, token, args.realm, rm_uuid, user_id, [catalog[r] for r in missing])
            print(f"{ADMIN_CLIENT}: granted {', '.join(missing)} to service account")
        else:
            print(
                f"{ADMIN_CLIENT}: all required roles already granted "
                f"({', '.join(REQUIRED_ROLES)})"
            )

        profile = ensure_user_profile(base, token, args.realm)
        print(f"user profile: {profile}")
        return 0
    except KeycloakError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())