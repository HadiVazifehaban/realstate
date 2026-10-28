#!/usr/bin/env python3
"""Render the test realm template without storing a secret in the repository."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path


template = Path(__file__).resolve().parents[1] / "keycloak" / "phase15-test-realm.json"
target = Path(os.getenv("PHASE15_REALM_FILE", "/tmp/shekarchi-phase15-test-realm.json"))
secret = os.getenv("PHASE15_TEST_KEYCLOAK_CLIENT_SECRET", "").strip()
if not secret:
    raise SystemExit("PHASE15_TEST_KEYCLOAK_CLIENT_SECRET is required")
payload = json.loads(template.read_text(encoding="utf-8"))
for client in payload.get("clients", []):
    if client.get("clientId") == "shekarchi-phase15-admin":
        client["secret"] = secret
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
target.chmod(stat.S_IRUSR | stat.S_IWUSR)
print(f"Prepared test realm file: {target}")
