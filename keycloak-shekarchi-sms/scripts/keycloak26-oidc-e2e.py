"""Disposable Keycloak Admin API setup and real Browser-flow OIDC checks.

This runs only in the Compose test network. The admin password grant is used
solely for the disposable bootstrap admin API. The test user's login is a
browser-style authorization request, form submission, and code + PKCE exchange.
"""
import base64
import hashlib
import http.cookiejar
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "http://keycloak:8080"
MANAGEMENT = "http://keycloak:9000"
ADMIN_PASSWORD = os.environ["KC_ADMIN_PASSWORD"]
USERNAME = os.environ["E2E_USERNAME"]
PASSWORD = os.environ["E2E_PASSWORD"]
REALM = "shekarchi-runtime-test"
CLIENT = "shekarchi-runtime-browser"
CALLBACK = "http://client.test/callback"
AUTHJS_CALLBACK = "http://frontend-test:3000/api/auth/callback/keycloak"
FRONTEND = "http://frontend-test:3000"


def response(req, opener=None):
    try:
        with (opener or urllib.request.build_opener()).open(req, timeout=15) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def api(method, path, token=None, payload=None, form=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    elif form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    status, _, data = response(req)
    if status < 200 or status >= 300:
        raise RuntimeError(f"HTTP {status} from Keycloak API {path}: {data[:300]!r}")
    return json.loads(data) if data else None


def admin_token():
    result = api(
        "POST",
        "/realms/master/protocol/openid-connect/token",
        form={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "kc_test_admin",
            "password": ADMIN_PASSWORD,
        },
    )
    return result["access_token"]


def setup_realm(token):
    status, _, body = response(
        urllib.request.Request(
            BASE + "/admin/realms",
            data=json.dumps({"realm": REALM, "enabled": True, "accessTokenLifespan": 75}).encode(),
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
            },
            method="POST",
        )
    )
    if status not in (201, 409):
        raise RuntimeError(f"Realm setup failed with HTTP {status}: {body[:300]!r}")
    clients = api("GET", f"/admin/realms/{REALM}/clients?clientId={CLIENT}", token)
    if not clients:
        api(
            "POST",
            f"/admin/realms/{REALM}/clients",
            token,
            {
                "clientId": CLIENT,
                "enabled": True,
                "protocol": "openid-connect",
                "publicClient": True,
                "standardFlowEnabled": True,
                "directAccessGrantsEnabled": False,
                "implicitFlowEnabled": False,
                "serviceAccountsEnabled": False,
                "redirectUris": [CALLBACK, AUTHJS_CALLBACK],
                "webOrigins": ["http://client.test", FRONTEND],
                "attributes": {
                    "pkce.code.challenge.method": "S256",
                    "access.token.lifespan": "75",
                },
            },
        )
        clients = api("GET", f"/admin/realms/{REALM}/clients?clientId={CLIENT}", token)
    client_uuid = clients[0]["id"]
    users = api("GET", f"/admin/realms/{REALM}/users?username={USERNAME}&exact=true", token)
    if not users:
        api(
            "POST",
            f"/admin/realms/{REALM}/users",
            token,
            {
                "username": USERNAME,
                "enabled": True,
                "email": USERNAME + "@example.invalid",
                "firstName": "Test",
                "lastName": "User",
                "emailVerified": True,
            },
        )
        users = api("GET", f"/admin/realms/{REALM}/users?username={USERNAME}&exact=true", token)
    api(
        "PUT",
        f"/admin/realms/{REALM}/users/{users[0]['id']}/reset-password",
        token,
        {"type": "password", "value": PASSWORD, "temporary": False},
    )
    return client_uuid


class LoginForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.inputs = {}
        self.in_login_form = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "kc-form-login":
            self.action = attrs.get("action")
            self.in_login_form = True
        elif tag == "input" and self.in_login_form and attrs.get("name"):
            if attrs.get("type") == "hidden":
                self.inputs[attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_login_form = False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def start_login(metadata, client_id, username, password):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    no_redirect = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar), NoRedirect()
    )
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": client_id,
        "redirect_uri": CALLBACK,
        "response_type": "code",
        "scope": "openid profile email",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = metadata["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)
    status, _, page = response(urllib.request.Request(auth_url), opener)
    if status != 200:
        raise RuntimeError(f"Authorization page returned HTTP {status}")
    parser = LoginForm()
    parser.feed(page.decode("utf-8", "replace"))
    if not parser.action or "username" not in page.decode("utf-8", "replace"):
        raise RuntimeError("Standard Keycloak username/password form was not rendered")
    action = urllib.parse.urljoin(auth_url, parser.action)
    values = dict(parser.inputs)
    values.update({"username": username, "password": password})
    req = urllib.request.Request(
        action,
        data=urllib.parse.urlencode(values).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    status, headers, body = response(req, no_redirect)
    return status, headers, body, state, verifier, opener, no_redirect


def decode_jwt_payload(token):
    part = token.split(".")[1]
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part))


def authjs_e2e():
    # Public paths must stay available with an empty cookie jar.
    public_opener = urllib.request.build_opener()
    for path in ("/", "/dashboard/properties"):
        status, _, _ = response(urllib.request.Request(FRONTEND + path), public_opener)
        if status != 200:
            raise RuntimeError(f"Public route failed: {path} returned HTTP {status}")
    print("AUTHJS_PUBLIC_ROUTES_PASS")

    anon_jar = http.cookiejar.CookieJar()
    anon_no_redirect = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(anon_jar), NoRedirect()
    )
    status, headers, _ = response(
        urllib.request.Request(FRONTEND + "/dashboard/events"), anon_no_redirect
    )
    target = urllib.parse.urlparse(headers.get("Location", ""))
    callback = urllib.parse.parse_qs(target.query).get("callbackUrl", [""])[0]
    if status not in (302, 303, 307, 308) or target.path != "/auth/sign-in" or callback != "/dashboard/events":
        raise RuntimeError("Anonymous private route did not redirect to sign-in with callbackUrl")
    print("AUTHJS_PRIVATE_ROUTE_REDIRECT_PASS")

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    status, _, csrf_body = response(urllib.request.Request(FRONTEND + "/api/auth/csrf"), opener)
    if status != 200:
        raise RuntimeError("Auth.js CSRF endpoint failed")
    csrf = json.loads(csrf_body)["csrfToken"]
    sign_in_req = urllib.request.Request(
        FRONTEND + "/api/auth/signin/keycloak",
        data=urllib.parse.urlencode(
            {"csrfToken": csrf, "callbackUrl": "/dashboard/events"}
        ).encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Auth-Return-Redirect": "1",
        },
        method="POST",
    )
    status, _, signin_body = response(sign_in_req, opener)
    if status != 200:
        raise RuntimeError(f"Auth.js sign-in initiation failed with HTTP {status}")
    signin_url = json.loads(signin_body).get("url", "")
    signin_query = urllib.parse.parse_qs(urllib.parse.urlparse(signin_url).query)
    if not signin_url.startswith(BASE + f"/realms/{REALM}/"):
        raise RuntimeError("Auth.js sign-in did not redirect to the test Keycloak issuer")
    if signin_query.get("response_type") != ["code"] or not signin_query.get("state"):
        raise RuntimeError("Auth.js did not create OIDC state and Authorization Code request")
    if signin_query.get("code_challenge_method") != ["S256"] or not signin_query.get("code_challenge"):
        raise RuntimeError("Auth.js PKCE S256 challenge missing")

    status, _, login_page = response(urllib.request.Request(signin_url), opener)
    if status != 200:
        raise RuntimeError("Auth.js provider redirect did not reach the Keycloak login form")
    parser = LoginForm()
    parser.feed(login_page.decode("utf-8", "replace"))
    if not parser.action:
        raise RuntimeError("Keycloak login form was absent during Auth.js callback test")
    form = dict(parser.inputs)
    form.update({"username": USERNAME, "password": PASSWORD})
    login_req = urllib.request.Request(
        urllib.parse.urljoin(signin_url, parser.action),
        data=urllib.parse.urlencode(form).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with opener.open(login_req, timeout=30) as result:
            final_url = result.geturl()
            final_status = result.status
            result.read()
    except urllib.error.HTTPError as e:
        final_url, final_status = e.geturl(), e.code
        e.read()
    final_parts = urllib.parse.urlparse(final_url)
    if final_status != 200 or final_parts.path != "/dashboard/events":
        raise RuntimeError(
            f"Auth.js callback did not resume private destination: status={final_status}, path={final_parts.path}"
        )

    status, _, session_body = response(urllib.request.Request(FRONTEND + "/api/auth/session"), opener)
    session = json.loads(session_body) if session_body else {}
    access = session.get("accessToken")
    if status != 200 or not isinstance(access, str) or not session.get("idToken"):
        raise RuntimeError("Auth.js callback did not create a Keycloak-backed session")
    initial_exp = int(decode_jwt_payload(access)["exp"])
    access_fingerprint = hashlib.sha256(access.encode()).hexdigest()
    print("AUTHJS_CALLBACK_SESSION_PASS")

    status, _, page = response(urllib.request.Request(FRONTEND + "/dashboard/events"), opener)
    if status != 200:
        raise RuntimeError("Authenticated private dashboard route was not accessible")
    print("AUTHJS_PRIVATE_ROUTE_ACCESS_PASS")

    import time
    wait_seconds = max(0, initial_exp - int(time.time()) - 55)
    if wait_seconds > 45:
        raise RuntimeError("Configured test access-token lifespan is too long for bounded refresh verification")
    time.sleep(wait_seconds + 2)
    status, _, refreshed_body = response(urllib.request.Request(FRONTEND + "/api/auth/session"), opener)
    refreshed_session = json.loads(refreshed_body) if refreshed_body else {}
    refreshed_access = refreshed_session.get("accessToken")
    if (
        status != 200
        or not isinstance(refreshed_access, str)
        or hashlib.sha256(refreshed_access.encode()).hexdigest() == access_fingerprint
        or int(decode_jwt_payload(refreshed_access)["exp"]) <= initial_exp
    ):
        raise RuntimeError("Auth.js session did not refresh the expiring Keycloak access token")
    print("AUTHJS_REFRESH_TOKEN_PASS")

    # The app's RP-initiated logout route must carry the current ID token hint.
    local_no_redirect = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar), NoRedirect()
    )
    status, headers, _ = response(
        urllib.request.Request(FRONTEND + "/api/auth/signout"), local_no_redirect
    )
    logout_url = headers.get("Location", "")
    logout_query = urllib.parse.parse_qs(urllib.parse.urlparse(logout_url).query)
    if (
        status not in (302, 303, 307, 308)
        or not logout_url.startswith(BASE + f"/realms/{REALM}/protocol/openid-connect/logout")
        or not logout_query.get("id_token_hint")
    ):
        raise RuntimeError("Auth.js RP-initiated logout did not include the ID token hint")
    response(urllib.request.Request(logout_url), opener)

    status, _, csrf_body = response(urllib.request.Request(FRONTEND + "/api/auth/csrf"), opener)
    csrf = json.loads(csrf_body)["csrfToken"]
    signout_req = urllib.request.Request(
        FRONTEND + "/api/auth/signout",
        data=urllib.parse.urlencode({"csrfToken": csrf, "callbackUrl": "/auth/sign-in"}).encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Auth-Return-Redirect": "1",
        },
        method="POST",
    )
    status, _, signout_body = response(signout_req, opener)
    if status != 200:
        raise RuntimeError(f"Auth.js CSRF-protected signout POST failed with HTTP {status}")
    status, _, after_logout_body = response(
        urllib.request.Request(FRONTEND + "/api/auth/session"), opener
    )
    after_logout = json.loads(after_logout_body) if after_logout_body else None
    if status != 200 or (
        isinstance(after_logout, dict)
        and (after_logout.get("accessToken") or after_logout.get("idToken"))
    ):
        raise RuntimeError("Auth.js local session remained after logout")
    status, headers, _ = response(
        urllib.request.Request(FRONTEND + "/dashboard/events"), local_no_redirect
    )
    if status not in (302, 303, 307, 308):
        raise RuntimeError("Private dashboard remained accessible after logout")
    print("AUTHJS_LOGOUT_PASS")


def main():
    for _ in range(90):
        try:
            status, _, data = response(urllib.request.Request(MANAGEMENT + "/health/ready"))
            if status == 200:
                break
        except Exception:
            pass
        import time
        time.sleep(2)
    else:
        raise RuntimeError("Keycloak readiness endpoint did not return HTTP 200")
    print("KEYCLOAK_HEALTH_PASS")

    status, _, data = response(urllib.request.Request(BASE + "/realms/master/.well-known/openid-configuration"))
    if status != 200:
        raise RuntimeError("OIDC discovery endpoint failed")
    master_metadata = json.loads(data)
    if master_metadata.get("issuer") != BASE + "/realms/master":
        raise RuntimeError("OIDC discovery issuer mismatch")
    print("OIDC_DISCOVERY_PASS")

    token = admin_token()
    realm = setup_realm(token)
    providers = api("GET", f"/admin/realms/{REALM}/authentication/authenticator-providers", token)
    if "shekarchi-sms-authenticator" not in {str(x.get("id", "")) for x in providers}:
        raise RuntimeError("Custom authenticator missing from runtime provider catalog")
    print("PROVIDER_DISCOVERY_PASS")

    metadata = json.loads(response(urllib.request.Request(BASE + f"/realms/{REALM}/.well-known/openid-configuration"))[2])
    status, headers, _, state, verifier, opener, no_redirect = start_login(metadata, CLIENT, USERNAME, PASSWORD)
    location = headers.get("Location", "")
    query = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
    if status not in (302, 303) or not query.get("code") or query.get("state", [None])[0] != state:
        location_parts = urllib.parse.urlparse(location)
        safe_query = urllib.parse.parse_qs(location_parts.query)
        page_text = _.decode("utf-8", "replace").lower() if isinstance(_, bytes) else ""
        marker = next((m for m in ("invalid username", "invalid user", "incorrect", "error") if m in page_text), "none")
        raise RuntimeError(
            "Correct login flow did not return authorization code: "
            f"status={status}, location={location_parts.scheme}://{location_parts.netloc}{location_parts.path}, "
            f"query_keys={sorted(safe_query)}, error={safe_query.get('error', ['none'])[0]}, page_marker={marker}"
        )
    code = query["code"][0]
    exchange = urllib.request.Request(
        metadata["token_endpoint"],
        data=urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "client_id": CLIENT,
                "redirect_uri": CALLBACK,
                "code": code,
                "code_verifier": verifier,
            }
        ).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    status, _, token_body = response(exchange)
    if status != 200:
        raise RuntimeError("Authorization Code + PKCE token exchange failed")
    issued = json.loads(token_body)
    if not issued.get("access_token") or not issued.get("id_token") or not issued.get("refresh_token"):
        raise RuntimeError("Keycloak omitted a required OIDC token")
    print("USERNAME_PASSWORD_CODE_PKCE_PASS")

    refresh = urllib.request.Request(
        metadata["token_endpoint"],
        data=urllib.parse.urlencode(
            {"grant_type": "refresh_token", "client_id": CLIENT, "refresh_token": issued["refresh_token"]}
        ).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    status, _, refreshed_body = response(refresh)
    if status != 200 or not json.loads(refreshed_body).get("access_token"):
        raise RuntimeError("Refresh token exchange failed")
    print("REFRESH_TOKEN_PASS")

    status, headers, body, wrong_state, _, _, _ = start_login(metadata, CLIENT, USERNAME, PASSWORD + "-wrong")
    wrong_location = urllib.parse.parse_qs(urllib.parse.urlparse(headers.get("Location", "")).query)
    if wrong_location.get("code") or status not in (200, 302, 303):
        raise RuntimeError("Incorrect password was not rejected")
    if status == 302 and wrong_location.get("state", [None])[0] == wrong_state:
        raise RuntimeError("Incorrect password unexpectedly produced an authorization response")
    print("INCORRECT_PASSWORD_REJECTED_PASS")

    logout_params = urllib.parse.urlencode(
        {
            "client_id": CLIENT,
            "id_token_hint": issued["id_token"],
            "post_logout_redirect_uri": CALLBACK,
        }
    )
    logout_req = urllib.request.Request(metadata["end_session_endpoint"] + "?" + logout_params)
    status, logout_headers, _ = response(logout_req, no_redirect)
    if status not in (200, 302) or (status == 302 and "client.test/callback" not in logout_headers.get("Location", "")):
        raise RuntimeError("OIDC logout endpoint failed")
    print("KEYCLOAK_LOGOUT_PASS")
    authjs_e2e()
    print("TEST_USER=" + USERNAME)


if __name__ == "__main__":
    main()
