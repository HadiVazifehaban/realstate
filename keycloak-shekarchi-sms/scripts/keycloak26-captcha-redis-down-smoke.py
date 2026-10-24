"""Assert unified login fails closed when its isolated CAPTCHA Redis is offline."""
import json
import http.cookiejar
import os
import re
import urllib.error
import urllib.parse
import urllib.request

FRONT = os.environ.get("SHEKARCHI_FRONTEND_BASE", "http://frontend-test:3000").rstrip("/")
KC = os.environ.get("SHEKARCHI_KC_BASE", "http://keycloak:8080").rstrip("/")
REALM = os.environ.get("SHEKARCHI_TEST_REALM", "shekarchi-runtime-test")


def request(opener, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {},
                                 method="POST" if data is not None else "GET")
    try:
        with opener.open(req, timeout=15) as response:
            return response.status, response.read(), response.geturl()
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.geturl()


def main():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    status, body, _ = request(opener, FRONT + "/api/auth/csrf")
    if status != 200:
        raise RuntimeError("Auth.js CSRF endpoint failed while testing Redis outage")
    csrf = json.loads(body)["csrfToken"]
    status, body, _ = request(opener, FRONT + "/api/auth/signin/keycloak",
        urllib.parse.urlencode({"csrfToken": csrf, "callbackUrl": FRONT + "/dashboard"}).encode(),
        {"Content-Type": "application/x-www-form-urlencoded", "X-Auth-Return-Redirect": "1"})
    if status != 200:
        raise RuntimeError("Auth.js sign-in initiation failed while testing Redis outage")
    sign_in_url = json.loads(body).get("url", "")
    if not sign_in_url.startswith(KC + f"/realms/{REALM}/"):
        raise RuntimeError("Auth.js did not use the isolated Keycloak test realm")
    status, body, _ = request(opener, sign_in_url)
    html = body.decode("utf-8", "replace")
    if status != 200 or "kc-form-login" not in html or "mk-form-sms" not in html:
        raise RuntimeError("Unified login did not render during Redis outage")
    # Raise the real Keycloak user failure counter in this disposable realm.
    # On the third failure CAPTCHA is required, and with Redis stopped both
    # methods must fail closed instead of presenting an unprotected submit.
    probe = os.environ.get("SHEKARCHI_TEST_CAPTCHA_USERNAME")
    if not probe:
        raise RuntimeError("Disposable CAPTCHA probe user was not supplied")
    for _ in range(3):
        match = re.search(r'<form\b[^>]*id="kc-form-login"[^>]*action="([^"]+)"', html)
        if not match:
            raise RuntimeError("Password form was missing during the Redis-down probe")
        action = urllib.parse.urljoin(sign_in_url, match.group(1))
        status, body, sign_in_url = request(opener, action, urllib.parse.urlencode({
            "username": probe, "password": "synthetic-invalid-password", "loginMode": "password"
        }).encode(), {"Content-Type": "application/x-www-form-urlencoded"})
        html = body.decode("utf-8", "replace")
        if status != 200:
            raise RuntimeError("Synthetic failed login did not return a Keycloak form")
    if "mk-captcha-question" in html or 'id="kc-login"' not in html:
        raise RuntimeError("CAPTCHA outage did not fail closed on the login form")
    if not re.search(r'<input\b(?=[^>]*\bid="kc-login")(?=[^>]*\bdisabled)[^>]*>', html):
        raise RuntimeError("Password login remained enabled without server-validated CAPTCHA")
    if not re.search(r'<button\b(?=[^>]*\bdisabled)[^>]*>\s*ارسال کد تأیید', html):
        raise RuntimeError("SMS login remained enabled without server-validated CAPTCHA")
    status, body, _ = request(opener, FRONT + "/api/auth/session")
    session = json.loads(body) if body else {}
    if not isinstance(session, dict):
        session = {}
    if status != 200 or session.get("accessToken") or session.get("idToken"):
        raise RuntimeError("Redis outage created an Auth.js session")
    print("CAPTCHA_REDIS_DOWN_FAIL_CLOSED_PASS")


if __name__ == "__main__":
    main()
