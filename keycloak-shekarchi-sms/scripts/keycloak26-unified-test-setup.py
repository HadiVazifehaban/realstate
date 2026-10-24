"""Provision a synthetic unified-login realm in the private runtime test stack."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("SHEKARCHI_KC_BASE", "http://keycloak:8080").rstrip("/")
REALM = os.environ.get("SHEKARCHI_TEST_REALM", "shekarchi-runtime-test")
CLIENT = os.environ.get("SHEKARCHI_TEST_CLIENT", "shekarchi-runtime-browser")
USERNAME = os.environ["SHEKARCHI_TEST_USERNAME"]
PASSWORD = os.environ["SHEKARCHI_TEST_PASSWORD"]
CAPTCHA_PROBE_USERNAME = os.environ.get("SHEKARCHI_TEST_CAPTCHA_USERNAME", USERNAME + "_captcha_probe")
PHONE = os.environ.get("SHEKARCHI_TEST_PHONE", "+989120000001")


def request(method, path, token=None, payload=None, form=None):
    headers = {}
    body = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    elif form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = response.read()
            return response.status, json.loads(data) if data else None
    except urllib.error.HTTPError as error:
        data = error.read()
        raise RuntimeError(f"Keycloak API {method} {path} returned HTTP {error.code}: {data[:300]!r}")


def create_authenticator_config(token, execution_id, payload):
    req = urllib.request.Request(BASE + f"/admin/realms/{REALM}/authentication/executions/{execution_id}/config",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = response.read()
            if data:
                return json.loads(data).get("id")
            location = response.headers.get("Location", "")
            return location.rstrip("/").rsplit("/", 1)[-1] if location else None
    except urllib.error.HTTPError as error:
        data = error.read()
        raise RuntimeError(f"Keycloak authenticator config creation returned HTTP {error.code}: {data[:300]!r}")


def main():
    for _ in range(90):
        try:
            request("GET", "/realms/master/.well-known/openid-configuration")
            break
        except Exception:
            time.sleep(2)
    else:
        raise RuntimeError("Keycloak test instance did not become ready")

    _, token_data = request("POST", "/realms/master/protocol/openid-connect/token", form={
        "grant_type": "password", "client_id": "admin-cli",
        "username": "kc_test_admin", "password": os.environ["KC_ADMIN_PASSWORD"],
    })
    token = token_data["access_token"]
    request("POST", "/admin/realms", token, {
        "realm": REALM, "enabled": True, "loginTheme": "shekarchi",
        "accessTokenLifespan": 75, "refreshTokenMaxReuse": 0,
    })

    request("POST", f"/admin/realms/{REALM}/clients", token, {
        "clientId": CLIENT, "enabled": True, "protocol": "openid-connect",
        "publicClient": True, "standardFlowEnabled": True,
        "directAccessGrantsEnabled": False, "implicitFlowEnabled": False,
        "serviceAccountsEnabled": False,
        "redirectUris": ["http://frontend-test:3000/api/auth/callback/keycloak"],
        "webOrigins": ["http://frontend-test:3000"],
        "attributes": {"pkce.code.challenge.method": "S256", "access.token.lifespan": "75"},
    })

    # Keycloak 26 user-profile configuration can discard attributes that are
    # not declared by the realm profile. Declare the synthetic test attributes
    # explicitly so the runtime E2E exercises the same account lookup as prod.
    _, user_profile = request("GET", f"/admin/realms/{REALM}/users/profile", token)
    profile_attributes = user_profile.setdefault("attributes", [])
    for name, display_name in (("phoneNumber", "Test phone number"),
                               ("phoneVerified", "Test phone verified")):
        existing = next((item for item in profile_attributes if item.get("name") == name), None)
        if existing is None:
            profile_attributes.append({
                "name": name, "displayName": display_name,
                "permissions": {"view": ["admin"], "edit": ["admin"]},
                "validations": {}, "annotations": {},
            })
    request("PUT", f"/admin/realms/{REALM}/users/profile", token, user_profile)

    request("POST", f"/admin/realms/{REALM}/users", token, {
        "username": USERNAME, "enabled": True,
        "email": USERNAME + "@example.invalid", "emailVerified": True,
        "firstName": "Synthetic", "lastName": "OTP Test",
        "attributes": {"phoneNumber": [PHONE], "phoneVerified": ["true"]},
        "credentials": [{"type": "password", "value": PASSWORD, "temporary": False}],
    })
    _, created_users = request("GET", f"/admin/realms/{REALM}/users?username={urllib.parse.quote(USERNAME)}&exact=true", token)
    if len(created_users) != 1:
        raise RuntimeError("Synthetic test user was not created uniquely")
    created_user = created_users[0]
    if created_user.get("attributes", {}).get("phoneNumber") != [PHONE] or \
            created_user.get("attributes", {}).get("phoneVerified") != ["true"]:
        raise RuntimeError("Keycloak did not retain synthetic verified-phone attributes")

    request("POST", f"/admin/realms/{REALM}/users", token, {
        "username": CAPTCHA_PROBE_USERNAME, "enabled": True,
        "email": CAPTCHA_PROBE_USERNAME + "@example.invalid", "emailVerified": True,
        "firstName": "Synthetic", "lastName": "CAPTCHA Probe",
        "credentials": [{"type": "password", "value": PASSWORD, "temporary": False}],
    })
    _, probe_users = request("GET", f"/admin/realms/{REALM}/users?username={urllib.parse.quote(CAPTCHA_PROBE_USERNAME)}&exact=true", token)
    if len(probe_users) != 1:
        raise RuntimeError("Synthetic CAPTCHA probe account was not created uniquely")

    # Distinct accounts isolate first-try success, expiry, and cooldown/rate
    # state without weakening any Redis policy.
    first_try_user = USERNAME + "_first_try"
    first_try_phone = "+989120000003"
    request("POST", f"/admin/realms/{REALM}/users", token, {
        "username": first_try_user, "enabled": True,
        "email": first_try_user + "@example.invalid", "emailVerified": True,
        "firstName": "Synthetic", "lastName": "OTP First Try Test",
        "attributes": {"phoneNumber": [first_try_phone], "phoneVerified": ["true"]},
        "credentials": [{"type": "password", "value": PASSWORD, "temporary": False}],
    })
    _, first_try_users = request("GET", f"/admin/realms/{REALM}/users?username={urllib.parse.quote(first_try_user)}&exact=true", token)
    if len(first_try_users) != 1 or first_try_users[0].get("attributes", {}).get("phoneNumber") != [first_try_phone]:
        raise RuntimeError("Keycloak did not retain first-try synthetic test account")
    expiry_user = USERNAME + "_expiry"
    expiry_phone = "+989120000004"
    request("POST", f"/admin/realms/{REALM}/users", token, {
        "username": expiry_user, "enabled": True,
        "email": expiry_user + "@example.invalid", "emailVerified": True,
        "firstName": "Synthetic", "lastName": "OTP Expiry Test",
        "attributes": {"phoneNumber": [expiry_phone], "phoneVerified": ["true"]},
        "credentials": [{"type": "password", "value": PASSWORD, "temporary": False}],
    })
    _, expiry_users = request("GET", f"/admin/realms/{REALM}/users?username={urllib.parse.quote(expiry_user)}&exact=true", token)
    if len(expiry_users) != 1 or expiry_users[0].get("attributes", {}).get("phoneNumber") != [expiry_phone]:
        raise RuntimeError("Keycloak did not retain OTP-expiry synthetic test account")

    flow_alias = "shekarchi-unified-runtime-test"
    request("POST", f"/admin/realms/{REALM}/authentication/flows", token, {
        "alias": flow_alias, "providerId": "basic-flow", "topLevel": True,
        "builtIn": False, "description": "Disposable unified password and SMS test flow",
    })
    _, execution = request("POST",
        f"/admin/realms/{REALM}/authentication/flows/{flow_alias}/executions/execution",
        token, {"provider": "shekarchi-sms-authenticator"})
    execution_id = execution.get("id") if isinstance(execution, dict) else None
    if not execution_id:
        _, executions = request("GET",
            f"/admin/realms/{REALM}/authentication/flows/{flow_alias}/executions",
            token)
        candidates = [item for item in executions if item.get("providerId") == "shekarchi-sms-authenticator"]
        if len(candidates) != 1:
            raise RuntimeError("Unified authenticator execution was not created")
        execution_id = candidates[0]["id"]

    request("PUT", f"/admin/realms/{REALM}/authentication/flows/{flow_alias}/executions", token, {
        "id": execution_id, "requirement": "REQUIRED",
    })
    config_id = create_authenticator_config(token, execution_id, {
        "alias": "shekarchi-unified-runtime-test",
        "config": {
            "flow.type": "PASSWORDLESS", "ui.unified-login": "true",
            "captcha.ttl-seconds": os.environ.get("SHEKARCHI_TEST_CAPTCHA_TTL", "30"),
            "otp.ttl-seconds": os.environ.get("SHEKARCHI_TEST_OTP_TTL", "60"),
            "otp.max-attempts": "3", "otp.resend-cooldown-seconds": "120",
            "otp.rate-window-seconds": "3600", "otp.ip-hourly-soft-limit": "5",
            "otp.mobile-hourly-soft-limit": "5", "otp.daily-max-per-mobile": "15",
            "sms.provider-id": "fake-sms-shekarchi",
        },
    })
    if not config_id:
        _, execution_info = request("GET", f"/admin/realms/{REALM}/authentication/executions/{execution_id}", token)
        config_id = execution_info.get("authenticatorConfig")
    if not config_id:
        raise RuntimeError("Keycloak did not associate the authenticator config with its execution")
    request("PUT", f"/admin/realms/{REALM}", token, {
        "realm": REALM, "enabled": True, "loginTheme": "shekarchi", "browserFlow": flow_alias,
    })

    print("UNIFIED_TEST_REALM_READY")
    print("SYNTHETIC_TEST_USER_READY")
    print("UNIFIED_AUTHENTICATOR_REQUIRED")


if __name__ == "__main__":
    main()
