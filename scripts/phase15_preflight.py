#!/usr/bin/env python3
"""Fail-closed preflight for disposable Phase 1.6 integration targets."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
import psycopg

PROJECT = "shekarchi-phase15-test"
NETWORK = "shekarchi_phase15_net"
REALM = "shekarchi-phase15-test"
COMPOSE_FILE = Path(__file__).resolve().parents[1] / "docker-compose.phase15-test.yml"


def _inspect(container: str) -> dict:
    result = subprocess.run(
        ["docker", "inspect", container], check=True, capture_output=True,
        text=True, timeout=5,
    )
    return json.loads(result.stdout)[0]


def _ip(info: dict) -> str:
    value = (info.get("NetworkSettings", {}).get("Networks", {}).get(NETWORK) or {}).get("IPAddress")
    if not value:
        raise RuntimeError("container is not attached to the approved test network")
    return value


def _assert_compose_identity(info: dict, service: str) -> None:
    labels = info.get("Config", {}).get("Labels") or {}
    if info.get("State", {}).get("Status") != "running":
        raise RuntimeError(f"isolated test service {service} is not running")
    if labels.get("com.docker.compose.project") != PROJECT:
        raise RuntimeError(f"service {service} is not in the approved test Compose project")
    if labels.get("com.docker.compose.service") != service:
        raise RuntimeError(f"container service identity mismatch for {service}")
    if Path(labels.get("com.docker.compose.project.config_files", "")).resolve() != COMPOSE_FILE.resolve():
        raise RuntimeError(f"service {service} was not provisioned by the approved Compose file")
    env_file = labels.get("com.docker.compose.project.environment_file", "")
    if not env_file or not Path(env_file).is_file():
        raise RuntimeError(f"independent provisioning inputs unavailable for {service}")


def _verify_db(url: str) -> None:
    parsed = urlparse(url.replace("+psycopg", ""))
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError("Phase 1.6 requires PostgreSQL/PostGIS")
    if parsed.path.lstrip("/") in {"", "avgcrm", "avg"}:
        raise RuntimeError("refusing development/production database name")
    clone_target = os.getenv("PHASE15_TEST_TARGET", "original") == "clone"
    expected_db, expected_user = (
        ("shekarchi_phase15_clone", "phase15_clone")
        if clone_target else ("shekarchi_phase15", "phase15_app")
    )
    if parsed.path.lstrip("/") != expected_db or parsed.username != expected_user:
        raise RuntimeError("database URL does not target the approved disposable database")

    info = _inspect("shekarchi-phase15-clone-db" if clone_target else f"{PROJECT}-app-test-db-1")
    if not clone_target:
        _assert_compose_identity(info, "app-test-db")
    ip = _ip(info)
    if parsed.hostname != ip or parsed.port != 5432:
        raise RuntimeError("database URL does not address the exact isolated container IP")

    with psycopg.connect(url.replace("+psycopg", ""), connect_timeout=3) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database(), current_user, inet_server_addr()::text, "
                "to_regclass('phase15_test_identity.provisioning_marker')"
            )
            database, role, server_ip, marker_table = cur.fetchone()
            if (database, role, server_ip.split("/")[0]) != (expected_db, expected_user, ip):
                raise RuntimeError("connected PostgreSQL identity differs from Docker-provisioned target")
            if not clone_target and marker_table != "phase15_test_identity.provisioning_marker":
                raise RuntimeError("independent Phase 1.6 database provisioning marker is missing")
            if clone_target:
                return
            cur.execute(
                "SELECT marker, compose_project, service_name, container_id, network_name "
                "FROM phase15_test_identity.provisioning_marker WHERE marker = %s",
                ("phase15-test",),
            )
            marker = cur.fetchone()
            if marker is None:
                raise RuntimeError("independent Phase 1.6 database identity row is missing")
            expected = (
                "phase15-test", PROJECT, "app-test-db", info.get("Id"), NETWORK
            )
            if tuple(marker) != expected:
                raise RuntimeError("database provisioning marker does not match the current test container")


def _verify_keycloak(issuer: str, realm: str) -> str:
    parsed = urlparse(issuer)
    if realm != REALM or parsed.scheme != "http" or parsed.path.rstrip("/") != f"/realms/{realm}":
        raise RuntimeError("issuer does not target the approved Phase 1.6 test realm")
    info = _inspect(f"{PROJECT}-keycloak-test-1")
    _assert_compose_identity(info, "keycloak-test")
    origin = f"http://{_ip(info)}:8080"
    if parsed.netloc != urlparse(origin).netloc:
        raise RuntimeError("issuer does not target the provisioned isolated Keycloak container")
    return origin


async def main() -> None:
    database_url = os.getenv("PHASE15_TEST_DATABASE_URL", "").strip()
    issuer = os.getenv("PHASE15_TEST_KEYCLOAK_ISSUER", "").strip()
    realm = os.getenv("PHASE15_TEST_KEYCLOAK_REALM", "").strip()
    if not database_url or not issuer or not realm:
        raise RuntimeError("Phase 1.6 test database URL, Keycloak issuer and realm are required")
    if os.getenv("PHASE15_TEST_SMS_PROVIDER", "").lower() != "fake":
        raise RuntimeError("PHASE15_TEST_SMS_PROVIDER must be fake")
    if os.getenv("PHASE15_TEST_ZIBAL_ENABLED", "").lower() != "false":
        raise RuntimeError("PHASE15_TEST_ZIBAL_ENABLED must be false")

    _verify_db(database_url)
    origin = _verify_keycloak(issuer, realm)
    async with httpx.AsyncClient(timeout=3.0, follow_redirects=False) as client:
        response = await client.get(f"{issuer.rstrip('/')}/.well-known/openid-configuration")
    if response.status_code != 200:
        raise RuntimeError(f"test Keycloak discovery failed: HTTP {response.status_code}")
    metadata = response.json()
    if metadata.get("issuer", "").rstrip("/") != issuer.rstrip("/"):
        raise RuntimeError("Keycloak discovery issuer mismatch")
    for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        endpoint = urlparse(metadata.get(name, ""))
        if endpoint.scheme != "http" or endpoint.netloc != urlparse(origin).netloc:
            raise RuntimeError(f"Keycloak {name} escapes the isolated test container")
    print("Phase 1.6 preflight passed: independently marked disposable PostgreSQL and pinned test Keycloak realm")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (RuntimeError, OSError, subprocess.SubprocessError, psycopg.Error, httpx.HTTPError) as exc:
        print(f"Phase 1.6 preflight FAILED: {exc}", file=sys.stderr)
        raise SystemExit(2)
