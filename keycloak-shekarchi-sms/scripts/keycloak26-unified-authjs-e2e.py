"""Real Keycloak unified password/SMS + Auth.js checks against a disposable Clone.

Required env: SHEKARCHI_KC_BASE, SHEKARCHI_FRONTEND_BASE, SHEKARCHI_TEST_CREDENTIAL_FILE,
SHEKARCHI_TEST_KEYCLOAK_CONTAINER. The credential file is mode 0600 and never printed.
The fake SMS code is copied out of the isolated test container, then immediately removed.
"""
import base64
import hashlib
import http.cookiejar
import json
import os
import re
import subprocess
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

KC = os.environ.get("SHEKARCHI_KC_BASE", "http://172.30.0.1:18092").rstrip("/")
FRONT = os.environ.get("SHEKARCHI_FRONTEND_BASE", "http://localhost:13000").rstrip("/")
REALM = os.environ.get("SHEKARCHI_TEST_REALM", "captcha-e2e")
CREDENTIAL_FILE = Path(os.environ.get(
    "SHEKARCHI_TEST_CREDENTIAL_FILE",
    "/home/app/.local/state/shekarchi-keycloak-backups/captcha-e2e-user.env",
))
CONTAINER = os.environ.get("SHEKARCHI_TEST_KEYCLOAK_CONTAINER", "shekarchi-kc-unified-test-20261020")
CAPTURE = "/tmp/shekarchi-test-otp-capture"
LOCAL_CAPTURE = Path("/tmp/she-unified-otp-capture")
SHARED_CAPTURE_FILE = os.environ.get("SHEKARCHI_TEST_OTP_CAPTURE_FILE")
SHARED_CAPTCHA_CAPTURE_FILE = os.environ.get("SHEKARCHI_TEST_CAPTCHA_CAPTURE_FILE")


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = {}
        self.current = None
        self.questions = {}
        self.capture = None
        self.text_parts = []
        self.suppressed_depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.suppressed_depth += 1
        if tag == "form":
            name = a.get("id", f"form-{len(self.forms)}")
            self.current = name
            self.forms[name] = {"action": a.get("action", ""), "fields": {}, "buttons": []}
        elif tag == "button" and self.current:
            name = a.get("name")
            if name:
                self.forms[self.current]["buttons"].append((name, a.get("value", "")))
        elif tag == "input" and self.current:
            name = a.get("name")
            if name:
                self.forms[self.current]["fields"][name] = a.get("value", "")
        if a.get("id", "").startswith("mk-captcha-question"):
            self.capture = a["id"]
            self.questions[self.capture] = ""

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.suppressed_depth = max(0, self.suppressed_depth - 1)
        if tag == "form":
            self.current = None
        if tag in ("p", "legend"):
            self.capture = None

    def handle_data(self, data):
        if not self.suppressed_depth:
            self.text_parts.append(data)
        if self.capture:
            self.questions[self.capture] += data


def parse(html):
    result = Page()
    result.feed(html)
    return result


def visible_text(html):
    return " ".join(" ".join(parse(html).text_parts).split())


def request(opener, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with opener.open(req, timeout=30) as response:
            return response.status, response.headers, response.read(), response.geturl()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read(), exc.geturl()


def post_form(opener, action, fields):
    return request(opener, action, urllib.parse.urlencode(fields).encode(),
                   {"Content-Type": "application/x-www-form-urlencoded"})


def submit_button(form, name, value):
    fields = dict(form["fields"])
    fields[name] = value
    return fields


def has_button(form, name, value):
    return (name, value) in form.get("buttons", [])


def captcha_answer(page):
    if SHARED_CAPTCHA_CAPTURE_FILE:
        path = Path(SHARED_CAPTCHA_CAPTURE_FILE)
        answer = path.read_text().strip()
        path.write_text("")
        if not answer and not any(page.questions.values()):
            return ""
        if not re.fullmatch(r"[A-Z2-9]{6}", answer):
            raise RuntimeError("test-only CAPTCHA capture did not contain a fresh answer")
        return answer
    for question in page.questions.values():
        values = re.findall(r"[0-9۰-۹٠-٩]+", question)
        if len(values) >= 3:
            numbers = [int("".join(str(unicodedata.digit(c)) for c in value)) for value in values[:3]]
            return numbers[0] + numbers[1] - numbers[2]
    raise RuntimeError("server-rendered CAPTCHA question was missing")


def incorrect_captcha_answer(page):
    answer = captcha_answer(page)
    replacement = "A" if answer[-1] != "A" else "B"
    return answer[:-1] + replacement


def start_authjs(require_captcha=False):
    clear_captcha_capture()
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    status, _, body, _ = request(opener, FRONT + "/api/auth/csrf")
    if status != 200:
        raise RuntimeError("Auth.js CSRF endpoint failed")
    csrf = json.loads(body)["csrfToken"]
    status, _, body, _ = request(opener, FRONT + "/api/auth/signin/keycloak",
        urllib.parse.urlencode({"csrfToken": csrf, "callbackUrl": FRONT + "/dashboard"}).encode(),
        {"Content-Type": "application/x-www-form-urlencoded", "X-Auth-Return-Redirect": "1"})
    if status != 200:
        raise RuntimeError("Auth.js sign-in initiation failed")
    sign_in_url = json.loads(body).get("url", "")
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(sign_in_url).query)
    if not sign_in_url.startswith(KC + f"/realms/{REALM}/") or query.get("response_type") != ["code"]:
        raise RuntimeError("Auth.js did not start an OIDC Authorization Code request")
    if query.get("code_challenge_method") != ["S256"] or not query.get("state"):
        raise RuntimeError("Auth.js PKCE/state parameters were missing")
    status, _, body, page_url = request(opener, sign_in_url)
    html = body.decode("utf-8", "replace")
    page = parse(html)
    if status != 200 or "kc-form-login" not in page.forms or "mk-form-sms" not in page.forms:
        raise RuntimeError("unified password and SMS forms were not both rendered")
    for marker in ("mk-login-tabs", "mk-panel-password", "mk-panel-sms"):
        if marker not in html:
            raise RuntimeError(f"unified login tab markup was missing: {marker}")
    assets = re.findall(r'(?:href|src)=["\']([^"\']+)["\']', html)
    css_urls = [urllib.parse.urljoin(page_url, asset) for asset in assets if asset.endswith("/css/shekarchi.css")]
    js_urls = [urllib.parse.urljoin(page_url, asset) for asset in assets if asset.endswith("/js/login.js")]
    if len(css_urls) != 1 or len(js_urls) != 1:
        raise RuntimeError("Shekarchi CSS or login JavaScript was not linked exactly once")
    for asset_url in css_urls + js_urls:
        asset_status, _, asset_body, _ = request(opener, asset_url)
        if asset_status != 200 or not asset_body:
            raise RuntimeError("a linked Shekarchi CSS/JavaScript asset did not load")
    # Prove the adaptive CAPTCHA is absent initially and appears only after
    # three incorrect password submissions in this isolated OIDC session.
    if require_captcha and not any(page.questions.values()):
        for _ in range(3):
            form = dict(page.forms["kc-form-login"]["fields"])
            form.update({
                "username": os.environ.get("SHEKARCHI_TEST_CAPTCHA_USERNAME", "captcha-probe-nonexistent"),
                "password": "synthetic-invalid-password",
            })
            action = urllib.parse.urljoin(page_url, page.forms["kc-form-login"]["action"])
            status, _, body, page_url = post_form(opener, action, form)
            if status != 200:
                raise RuntimeError("synthetic CAPTCHA priming attempt did not return the login page")
            page = parse(body.decode("utf-8", "replace"))
            if any(page.questions.values()) and _ < 2:
                raise RuntimeError("CAPTCHA appeared before three failed password attempts")
        if not any(page.questions.values()):
            raise RuntimeError("adaptive CAPTCHA question missing after three synthetic failures")
    if require_captcha:
        # Force a newly generated challenge for this OIDC transaction so the
        # private test capture can never be stale from an earlier test session.
        refresh = page.forms.get("kc-captcha-refresh-form")
        if refresh:
            status, _, body, page_url = post_form(
                opener, urllib.parse.urljoin(page_url, refresh["action"]), refresh["fields"])
            if status != 200:
                raise RuntimeError("fresh CAPTCHA generation failed in the disposable session")
            page = parse(body.decode("utf-8", "replace"))
            if not any(page.questions.values()):
                raise RuntimeError("fresh CAPTCHA was not present after explicit refresh")
    return opener, page, page_url


def get_session(opener):
    status, _, body, _ = request(opener, FRONT + "/api/auth/session")
    return status, json.loads(body) if body else {}


def has_authjs_session(opener):
    status, session = get_session(opener)
    if status != 200 or not isinstance(session, dict):
        return False
    expires_at = session.get("accessTokenExpiresAt")
    user = session.get("user")
    return (isinstance(expires_at, (int, float)) and expires_at > time.time()
            and session.get("authError") is not True
            and isinstance(user, dict) and bool(user.get("id")))


def token_exp(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return int(json.loads(base64.urlsafe_b64decode(payload.encode()))["exp"])
    except Exception:
        return 0


def verify_authjs_refresh(opener):
    status, before = get_session(opener)
    expiry_before = before.get("accessTokenExpiresAt") if isinstance(before, dict) else None
    if status != 200 or not expiry_before:
        return False
    # Test realm tokens expire in 75s; Auth.js refreshes at a 60s safety margin.
    time.sleep(18)
    status, after = get_session(opener)
    expiry_after = after.get("accessTokenExpiresAt") if isinstance(after, dict) else None
    return (status == 200 and isinstance(expiry_after, (int, float))
            and expiry_after > expiry_before and after.get("authError") is not True)


def verify_private_route(opener, expected):
    status, _, _, url = request(opener, FRONT + "/dashboard")
    final_path = urllib.parse.urlsplit(url).path
    if status != 200:
        return False
    if expected:
        return final_path.startswith("/dashboard") and final_path != "/auth/sign-in"
    return final_path == "/auth/sign-in"


def clear_capture():
    if SHARED_CAPTURE_FILE:
        path = Path(SHARED_CAPTURE_FILE)
        # The capture-init service creates this file as the Keycloak UID.
        # Truncate it without changing ownership or mode so the provider can
        # safely replace its contents and keep the file private.
        if path.exists():
            path.write_text("")
        return
    subprocess.run(["docker", "exec", CONTAINER, "rm", "-f", CAPTURE], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    LOCAL_CAPTURE.unlink(missing_ok=True)


def clear_captcha_capture():
    if SHARED_CAPTCHA_CAPTURE_FILE:
        path = Path(SHARED_CAPTCHA_CAPTURE_FILE)
        if path.exists():
            path.write_text("")


def capture_fake_otp():
    if SHARED_CAPTURE_FILE:
        code = Path(SHARED_CAPTURE_FILE).read_text().strip()
        clear_capture()
        if not re.fullmatch(r"\d{6}", code):
            raise RuntimeError("test-only fake SMS provider did not produce a valid challenge")
        return code
    subprocess.run(["docker", "cp", f"{CONTAINER}:{CAPTURE}", str(LOCAL_CAPTURE)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.chmod(LOCAL_CAPTURE, 0o600)
    code = LOCAL_CAPTURE.read_text().strip()
    clear_capture()
    if not re.fullmatch(r"\d{6}", code):
        raise RuntimeError("test-only fake SMS provider did not produce a valid challenge")
    return code


def no_fake_otp():
    if SHARED_CAPTURE_FILE:
        return not Path(SHARED_CAPTURE_FILE).read_text().strip()
    return subprocess.run(["docker", "exec", CONTAINER, "test", "-f", CAPTURE],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0


def submit_sms(opener, page, page_url, phone, answer):
    form = dict(page.forms["mk-form-sms"]["fields"])
    form.update({"phone": phone, "captchaAnswer": str(answer)})
    action = urllib.parse.urljoin(page_url, page.forms["mk-form-sms"]["action"])
    status, headers, body, url = post_form(opener, action, form)
    return status, headers, body.decode("utf-8", "replace"), url, parse(body.decode("utf-8", "replace"))


def logout(opener):
    status, _, body, _ = request(opener, FRONT + "/api/auth/csrf")
    csrf = json.loads(body)["csrfToken"]
    status, _, body, _ = request(opener, FRONT + "/api/auth/signout",
        urllib.parse.urlencode({"csrfToken": csrf, "callbackUrl": FRONT + "/auth/sign-in"}).encode(),
        {"Content-Type": "application/x-www-form-urlencoded", "X-Auth-Return-Redirect": "1"})
    if status != 200:
        return False
    target = json.loads(body).get("url")
    if target:
        request(opener, target)
    return not has_authjs_session(opener) and verify_private_route(opener, False)


def main():
    username = os.environ.get("SHEKARCHI_TEST_USERNAME")
    password = os.environ.get("SHEKARCHI_TEST_PASSWORD")
    if not username or not password:
        creds = dict(line.split("=", 1) for line in CREDENTIAL_FILE.read_text().splitlines() if "=" in line)
        username, password = creds["TEST_USERNAME"], creds["TEST_PASSWORD"]
    tests = []

    # CAPTCHA is checked before sending an OTP. Empty and incorrect answers fail closed.
    for label, answer_fn in (("empty_captcha_rejected", lambda p: ""),
                             ("incorrect_captcha_rejected", incorrect_captcha_answer)):
        opener, page, page_url = start_authjs(require_captcha=True)
        clear_capture()
        status, _, body, _, result_page = submit_sms(opener, page, page_url, "+989120000001", answer_fn(page))
        tests.append((label, status == 200 and "mk-tab-password" in body and
                      "name=\"otp\"" not in body and no_fake_otp()))

    # Unverified and unknown numbers receive the same message and never receive an SMS.
    generic_response_text = None
    for label, number in (("unverified_phone_no_sms", "+989120000002"),
                          ("unknown_phone_no_sms", "+989120000099")):
        opener, page, page_url = start_authjs()
        clear_capture()
        status, _, body, _, result_page = submit_sms(
            opener, page, page_url, number, captcha_answer(page))
        response_text = visible_text(body)
        same_generic_response = bool(response_text) and (
            generic_response_text is None or response_text == generic_response_text)
        generic_response_text = response_text
        passed = status == 200 and same_generic_response and no_fake_otp() and "name=\"otp\"" not in body
        tests.append((label, passed))
        if not passed:
            print("phone_case_diagnostic", label, json.dumps({
                "status": status, "same_generic_response": same_generic_response,
                "visible_text": response_text[:700],
                "otp_input": "name=\"otp\"" in body,
                "fake_otp_present": not no_fake_otp(),
                "captcha_error": "captchaInvalid" in body,
            }, sort_keys=True))

    # CAPTCHA TTL is enforced at the server, even if the browser keeps the old page open.
    opener, page, page_url = start_authjs(require_captcha=True)
    expired_answer = captcha_answer(page)
    captcha_ttl = int(os.environ.get("SHEKARCHI_TEST_CAPTCHA_TTL", "30"))
    time.sleep(captcha_ttl + 1)
    clear_capture()
    status, _, body, _, _ = submit_sms(opener, page, page_url, "+989120000001", expired_answer)
    tests.append(("expired_captcha_rejected", status == 200 and "name=\"otp\"" not in body and no_fake_otp()))

    opener, page, page_url = start_authjs(require_captcha=True)
    old_tab = urllib.parse.parse_qs(urllib.parse.urlsplit(page.forms["kc-form-login"]["action"]).query).get("tab_id")
    refresh = dict(page.forms["kc-captcha-refresh-form"]["fields"])
    refresh["loginMode"] = "recovery"
    status, _, body, url = post_form(opener, urllib.parse.urljoin(page_url, page.forms["kc-captcha-refresh-form"]["action"]), refresh)
    recovered = parse(body.decode("utf-8", "replace"))
    new_tab = urllib.parse.parse_qs(urllib.parse.urlsplit(recovered.forms["mk-form-sms"]["action"]).query).get("tab_id")
    tests.append(("forgot_flow_same_auth_session", status == 200 and old_tab == new_tab and "mk-recovery-message" in body.decode("utf-8", "ignore")))

    # Failed password consumes its CAPTCHA and never creates an Auth.js session.
    login = dict(recovered.forms["kc-form-login"]["fields"])
    login.update({"username": username, "password": password + "-wrong", "captchaAnswer": str(captcha_answer(recovered))})
    status, _, body, _ = post_form(opener, urllib.parse.urljoin(url, recovered.forms["kc-form-login"]["action"]), login)
    tests.append(("incorrect_password_rejected", status == 200 and not has_authjs_session(opener)))

    # Correct username/password in a fresh Auth.js OIDC transaction.
    opener, page, page_url = start_authjs()
    form = dict(page.forms["kc-form-login"]["fields"])
    form.update({"username": username, "password": password, "captchaAnswer": str(captcha_answer(page))})
    status, _, _, final_url = post_form(opener, urllib.parse.urljoin(page_url, page.forms["kc-form-login"]["action"]), form)
    tests.append(("password_oidc_authjs_session", status in (200, 302, 303) and has_authjs_session(opener)))
    tests.append(("password_authjs_refresh_token", verify_authjs_refresh(opener)))
    tests.append(("password_private_dashboard", verify_private_route(opener, True)))
    tests.append(("password_logout", logout(opener)))

    # SMS OTP via the same Auth.js client, PKCE/state, and session cookie.
    opener, page, page_url = start_authjs()
    sms_form = dict(page.forms["mk-form-sms"]["fields"])
    initial_sms_captcha = str(captcha_answer(page))
    sms_form.update({"phone": "+989120000001", "captchaAnswer": initial_sms_captcha})
    clear_capture()
    status, _, body, otp_url = post_form(opener, urllib.parse.urljoin(page_url, page.forms["mk-form-sms"]["action"]), sms_form)
    otp_page = parse(body.decode("utf-8", "replace"))
    tests.append(("sms_otp_issued_after_captcha", status == 200 and any(
        has_button(form, "action", "verify") for form in otp_page.forms.values()
    )))
    verify_form = next((form for form in otp_page.forms.values() if has_button(form, "action", "verify")), None)
    if not verify_form:
        raise RuntimeError(f"SMS submission did not render an OTP verification form (HTTP {status})")
    code = capture_fake_otp()
    # A consumed CAPTCHA cannot be replayed for a resend on the same authentication session.
    resend_form = next((form for form in otp_page.forms.values() if has_button(form, "action", "resend")), None)
    old_answer = initial_sms_captcha
    if resend_form:
        # First resend request only raises the CAPTCHA requirement; it must not
        # issue another code. A replay of the CAPTCHA used for the first issue
        # is then rejected against the freshly issued one-time challenge.
        clear_capture()
        priming = submit_button(resend_form, "action", "resend")
        _, _, priming_body, _ = post_form(opener, urllib.parse.urljoin(otp_url, resend_form["action"]), priming)
        otp_page = parse(priming_body.decode("utf-8", "replace"))
        captcha_answer(otp_page)  # consume the test-only capture of the fresh challenge
        resend_form = next(form for form in otp_page.forms.values() if has_button(form, "action", "resend"))
        clear_capture()
        replay = submit_button(resend_form, "action", "resend"); replay["captchaAnswer"] = old_answer
        _, _, replay_body, _ = post_form(opener, urllib.parse.urljoin(otp_url, resend_form["action"]), replay)
        replay_html = replay_body.decode("utf-8", "replace")
        tests.append(("captcha_replay_for_resend_rejected", "name=\"otp\"" in replay_html and no_fake_otp()))
        otp_page = parse(replay_html)
        verify_form = next(form for form in otp_page.forms.values() if has_button(form, "action", "verify"))
        otp_url = urllib.parse.urljoin(otp_url, verify_form["action"])

    # A fresh CAPTCHA cannot override the server-side resend cooldown.
    if resend_form:
        current_resend = next((form for form in otp_page.forms.values()
                               if has_button(form, "action", "resend")), None)
        if current_resend:
            clear_capture()
            resend_fields = submit_button(current_resend, "action", "resend")
            resend_fields["captchaAnswer"] = str(captcha_answer(otp_page))
            _, _, cooldown_body, otp_url = post_form(
                opener, urllib.parse.urljoin(otp_url, current_resend["action"]), resend_fields)
            cooldown_html = cooldown_body.decode("utf-8", "replace")
            tests.append(("otp_resend_cooldown", "name=\"otp\"" in cooldown_html and no_fake_otp()))
            otp_page = parse(cooldown_html)
            verify_form = next(form for form in otp_page.forms.values() if has_button(form, "action", "verify"))
            otp_url = urllib.parse.urljoin(otp_url, verify_form["action"])
    bad = submit_button(verify_form, "action", "verify"); bad.update({"otp": "000000" if code != "000000" else "000001"})
    status, _, body, otp_url = post_form(opener, urllib.parse.urljoin(otp_url, verify_form["action"]), bad)
    otp_page = parse(body.decode("utf-8", "replace"))
    tests.append(("incorrect_sms_otp_rejected", status == 200 and not has_authjs_session(opener)))
    verify_form = next(form for form in otp_page.forms.values() if has_button(form, "action", "verify"))
    correct = submit_button(verify_form, "action", "verify"); correct["otp"] = code
    status, _, _, final_url = post_form(opener, urllib.parse.urljoin(otp_url, verify_form["action"]), correct)
    sms_session_ok = has_authjs_session(opener)
    if not sms_session_ok:
        session_status, session_body = get_session(opener)
        print("sms_session_diagnostic", json.dumps({
            "callback_status": status,
            "callback_path": urllib.parse.urlsplit(final_url).path,
            "session_status": session_status,
            "session_keys": sorted(session_body.keys()) if isinstance(session_body, dict) else [],
            "access_token_expiry_present": isinstance(session_body.get("accessTokenExpiresAt"), (int, float)) if isinstance(session_body, dict) else False,
            "auth_error": session_body.get("authError") if isinstance(session_body, dict) else None,
            "session_error": session_body.get("error") if isinstance(session_body, dict) else None,
        }, sort_keys=True))
    tests.append(("sms_oidc_authjs_session", status in (200, 302, 303) and sms_session_ok))
    tests.append(("sms_authjs_refresh_token", verify_authjs_refresh(opener)))
    tests.append(("sms_private_dashboard", verify_private_route(opener, True)))
    tests.append(("sms_logout", logout(opener)))

    # Independent account: verify that a correct OTP succeeds on its first try.
    opener, page, page_url = start_authjs()
    sms_form = dict(page.forms["mk-form-sms"]["fields"])
    sms_form.update({"phone": "+989120000003", "captchaAnswer": str(captcha_answer(page))})
    clear_capture()
    status, _, body, otp_url = post_form(opener, urllib.parse.urljoin(page_url, page.forms["mk-form-sms"]["action"]), sms_form)
    otp_page = parse(body.decode("utf-8", "replace"))
    code = capture_fake_otp()
    verify_form = next(form for form in otp_page.forms.values() if has_button(form, "action", "verify"))
    verify = submit_button(verify_form, "action", "verify"); verify["otp"] = code
    status, _, _, _ = post_form(opener, urllib.parse.urljoin(otp_url, verify_form["action"]), verify)
    tests.append(("sms_correct_first_try_authjs_session",
                  status in (200, 302, 303) and has_authjs_session(opener)))
    tests.append(("sms_correct_first_try_private_dashboard", verify_private_route(opener, True)))
    tests.append(("sms_correct_first_try_logout", logout(opener)))

    # SMS access recovery is sign-in only; it must leave the existing password intact.
    opener, page, page_url = start_authjs()
    form = dict(page.forms["kc-form-login"]["fields"])
    form.update({"username": username, "password": password,
                 "captchaAnswer": str(captcha_answer(page))})
    status, _, _, _ = post_form(
        opener, urllib.parse.urljoin(page_url, page.forms["kc-form-login"]["action"]), form)
    tests.append(("password_unchanged_after_sms_login",
                  status in (200, 302, 303) and has_authjs_session(opener)))

    # SMS OTP expires server-side; waiting does not produce an Auth.js session.
    opener, page, page_url = start_authjs()
    sms_form = dict(page.forms["mk-form-sms"]["fields"])
    sms_form.update({"phone": "+989120000004", "captchaAnswer": str(captcha_answer(page))})
    clear_capture()
    status, _, body, otp_url = post_form(opener, urllib.parse.urljoin(page_url, page.forms["mk-form-sms"]["action"]), sms_form)
    otp_page = parse(body.decode("utf-8", "replace"))
    expired_code = capture_fake_otp()
    verify_form = next(form for form in otp_page.forms.values() if has_button(form, "action", "verify"))
    otp_ttl = int(os.environ.get("SHEKARCHI_TEST_OTP_TTL", "60"))
    time.sleep(otp_ttl + 1)
    verify = submit_button(verify_form, "action", "verify"); verify["otp"] = expired_code
    status, _, body, _ = post_form(opener, urllib.parse.urljoin(otp_url, verify_form["action"]), verify)
    tests.append(("expired_sms_otp_rejected", status == 200 and not has_authjs_session(opener)))

    # Public routes remain reachable without a session.
    for path in ("/", "/dashboard/properties"):
        status, _, _, _ = request(urllib.request.build_opener(), FRONT + path)
        tests.append(("public_route_" + path.replace("/", "root") , status == 200))

    for name, passed in tests:
        print(name, "PASS" if passed else "FAIL")
    print("summary", sum(1 for _, passed in tests if passed), "PASS /", len(tests), "checks")
    if not all(passed for _, passed in tests):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
