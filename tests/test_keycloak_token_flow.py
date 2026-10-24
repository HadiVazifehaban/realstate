"""End-to-end verification of the Keycloak token path.

Keycloak is not reachable from the test suite, so these tests stand up a real
JWKS endpoint over loopback and issue genuine RS256 tokens. That exercises the
actual verification path -- signature, issuer, audience, expiry -- instead of
mocking the verifier, which is precisely where the interesting failures live.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import asyncio

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import AuthMode, Settings
from app.core.identity import (
    IdentityError,
    principal_from_token,
    verify_access_token,
)

AUDIENCE = "maskanchi-backend-api"
KID = "maskanchi-test-key"


def _keypair() -> tuple[rsa.RSAPrivateKey, dict]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    return private_key, {"keys": [jwk]}



def _run(coro):
    """Drive a coroutine to completion.

    The suite has no pytest-asyncio plugin, so async verifiers are driven with the
    same plain-loop helper the other tests use.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@pytest.fixture(scope="module")
def realm():
    """A loopback JWKS server standing in for the Keycloak realm."""
    private_key, jwks = _keypair()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            body = json.dumps(jwks).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield {
            "private_key": private_key,
            "issuer": f"http://127.0.0.1:{server.server_port}",
        }
    finally:
        server.shutdown()


@pytest.fixture()
def keycloak_settings(realm) -> Settings:
    return Settings(
        auth_mode=AuthMode.KEYCLOAK,
        keycloak_issuer=realm["issuer"],
        keycloak_audience=AUDIENCE,
        jwks_cache_seconds=60,
    )


def _issue(realm, **overrides) -> str:
    claims = {
        "sub": "usr-998129a0",
        "iss": realm["issuer"],
        "aud": AUDIENCE,
        "typ": "Bearer",
        "azp": "shekarchi-frontend",
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "jti": "b4e13d94-912c-4903-a218-e9f7832810a9",
        "preferred_username": "09121854920",
        "name": "علیرضا فراهانی",
        "realm_access": {"roles": ["ROLE_SENIOR_BROKER"]},
        "kyc_status": "VERIFIED",
        "saas_tier": "PRO",
        "daily_pii_quota": 50,
        "tenant_id": "agency_shemiran_01",
    }
    claims.update(overrides)
    return jwt.encode(
        claims, realm["private_key"], algorithm="RS256", headers={"kid": KID}
    )


def test_a_real_token_verifies_end_to_end(realm, keycloak_settings) -> None:
    claims = _run(verify_access_token(_issue(realm), keycloak_settings))
    assert claims["sub"] == "usr-998129a0"
    assert claims["tenant_id"] == "agency_shemiran_01"


def test_an_expired_token_is_refused(realm, keycloak_settings) -> None:
    token = _issue(realm, exp=int(time.time()) - 10)
    with pytest.raises(IdentityError) as exc:
        _run(verify_access_token(token, keycloak_settings))
    assert exc.value.code == "token_expired"


def test_a_token_for_another_audience_is_refused(realm, keycloak_settings) -> None:
    """A token minted for a different service must not open this one."""
    with pytest.raises(IdentityError) as exc:
        _run(verify_access_token(_issue(realm, aud="someone-else"), keycloak_settings))


def test_an_id_token_is_not_an_api_credential(realm, keycloak_settings) -> None:
    with pytest.raises(IdentityError) as exc:
        _run(verify_access_token(_issue(realm, typ="ID"), keycloak_settings))
    assert exc.value.status_code == 401
    assert exc.value.code == "token_type_invalid"


def test_a_token_for_another_client_is_refused(realm, keycloak_settings) -> None:
    with pytest.raises(IdentityError) as exc:
        _run(verify_access_token(_issue(realm, azp="unrelated-client"), keycloak_settings))
    assert exc.value.status_code == 401
    assert exc.value.code == "token_client_invalid"


def test_a_token_from_another_issuer_is_refused(realm, keycloak_settings) -> None:
    with pytest.raises(IdentityError) as exc:
        _run(verify_access_token(_issue(realm, iss="https://evil.example"), keycloak_settings))
    assert exc.value.code == "token_invalid"


def test_a_foreign_signing_key_is_refused(realm, keycloak_settings) -> None:
    attacker_key, _ = _keypair()
    forged = jwt.encode(
        {
            "sub": "attacker",
            "iss": realm["issuer"],
            "aud": AUDIENCE,
            "exp": int(time.time()) + 300,
            "realm_access": {"roles": ["ROLE_ADMIN"]},
            "kyc_status": "VERIFIED",
        },
        attacker_key,
        algorithm="RS256",
        headers={"kid": KID},
    )
    with pytest.raises(IdentityError):
        _run(verify_access_token(forged, keycloak_settings))


def test_an_hs256_downgrade_is_refused(realm, keycloak_settings) -> None:
    """Pinning RS256 blocks the classic "sign with the public key" attack.

    PyJWT itself refuses to *mint* such a token, so the header is crafted by hand
    and signed manually. The verifier must reject it on the pinned algorithm,
    not by accident on a decode detail.
    """
    public_pem = realm["private_key"].public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    def segment(data: dict) -> str:
        raw = json.dumps(data, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header = segment({"alg": "HS256", "typ": "JWT", "kid": KID})
    payload = segment(
        {
            "sub": "attacker",
            "iss": realm["issuer"],
            "aud": AUDIENCE,
            "exp": int(time.time()) + 300,
            "realm_access": {"roles": ["ROLE_ADMIN"]},
            "kyc_status": "VERIFIED",
        }
    )
    signing_input = f"{header}.{payload}".encode()
    signature = base64.urlsafe_b64encode(
        hmac.new(public_pem, signing_input, hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    downgrade = f"{header}.{payload}.{signature}"

    with pytest.raises(IdentityError) as exc:
        _run(verify_access_token(downgrade, keycloak_settings))
    # Refused on the algorithm pin, and always as a 401 rather than a 500.
    assert exc.value.code in ("token_invalid", "token_signature_unknown")
    assert exc.value.status_code == 401


def test_a_missing_issuer_setting_fails_loudly() -> None:
    """KEYCLOAK mode without a realm must not silently fall open."""
    settings = Settings(auth_mode=AuthMode.KEYCLOAK, keycloak_issuer="")
    with pytest.raises(IdentityError) as exc:
        _run(verify_access_token("anything", settings))
    assert exc.value.code == "keycloak_not_configured"
