"""One hosted-CI, no-session smoke of the original configured app and page.

No browser installation, business fixtures, database, worker, or security fallback.
The local contract test uses readonly_application only; main refuses local launch.
"""
from contextlib import contextmanager
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import threading
import time
from unittest.mock import patch
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "refs/heads/dev/f2-unaccepted-step-redispatch-20261019"
NOT_RUN = ["database", "Case", "worker", "P1-P5", "TXT_download", "business_cold_recovery", "Windows_AT"]


def require_hosted_once(environment):
    expected = {
        "SMOKE_REPOSITORY": "T1doo/ParkWeave", "SMOKE_REF": BRANCH,
        "SMOKE_EVENT": "push", "SMOKE_ATTEMPT": "1", "SMOKE_NUMBER": "6",
        "SMOKE_PUBLIC": "true", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux",
    }
    if any(environment.get(k) != v for k, v in expected.items()):
        raise RuntimeError("only the authorized public dedicated hosted Linux push is allowed")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", environment.get("SMOKE_SHA", "")) or commit != environment["SMOKE_SHA"]:
        raise RuntimeError("exact checked-out source SHA required")
    return commit


@contextmanager
def readonly_application():
    if any(k.startswith("PARKWEAVE_") for k in os.environ):
        raise RuntimeError("clean application environment required; no inherited providers or credentials")
    from parkweave import api
    from parkweave.store import Store
    if Path(api.__file__).resolve() != ROOT / "src/parkweave/api.py":
        raise RuntimeError("original checkout module required")
    evidence = {"db_connect_attempts": 0, "requests": [], "blocked_write_probes": 0}

    def refuse_connect(_store):
        evidence["db_connect_attempts"] += 1
        raise RuntimeError("database access forbidden in read-only page smoke")

    # No socket exists, and no username/password/real connection string is supplied.
    with patch.object(Store, "connect", refuse_connect), patch.dict(os.environ, {
        "PARKWEAVE_DSN": "dbname=readonly_smoke_unused host=/nonexistent/parkweave-readonly-smoke",
        "PARKWEAVE_MODE": "LOCAL",
    }):
        app = api.configured_app()

        @app.middleware("http")
        async def readonly_gate(request, call_next):
            from starlette.responses import JSONResponse
            if request.method not in {"GET", "HEAD"}:
                evidence["blocked_write_probes"] += 1
                response = JSONResponse({"detail": "read-only smoke guard"}, status_code=405)
            else:
                response = await call_next(request)
            evidence["requests"].append({"method": request.method, "path": request.url.path,
                                         "status": response.status_code})
            return response

        try:
            yield app, evidence
        finally:
            if evidence["db_connect_attempts"]:
                raise RuntimeError("database access was attempted; smoke cannot pass")


@contextmanager
def serve_original(app):
    import uvicorn
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("owned original HTTP server failed to start")
            time.sleep(0.02)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        if thread.is_alive():
            raise RuntimeError("owned server did not stop within five seconds")


def browser_smoke(report):
    from playwright.sync_api import expect, sync_playwright
    with readonly_application() as (app, evidence), serve_original(app) as base:
        report["application"] = evidence
        with sync_playwright() as playwright:
            # Use runner's already installed Chrome; never install or fall back.
            with playwright.chromium.launch(channel="chrome", headless=True, chromium_sandbox=True,
                                            args=["--enable-automation"]) as browser:
                report["chrome_version"] = browser.version
                command = browser.new_browser_cdp_session().send("Browser.getBrowserCommandLine")["arguments"]
                forbidden = {"--no-sandbox", "--disable-setuid-sandbox", "--disable-seccomp-filter-sandbox",
                             "--disable-namespace-sandbox", "--disable-gpu-sandbox", "--no-zygote", "--disable-web-security"}
                if any(arg.split("=", 1)[0] in forbidden for arg in command):
                    raise RuntimeError("Chrome reports forbidden sandbox/security switches")
                report["chrome_arguments"] = command
                sandbox_page = browser.new_page()
                sandbox_page.goto("chrome://sandbox", timeout=10000)
                sandbox_text = sandbox_page.locator("body").inner_text()
                report["sandbox_status"] = sandbox_text
                if ("You are adequately sandboxed." not in sandbox_text
                        or not re.search(r"Seccomp-BPF sandbox\s+Yes", sandbox_text)
                        or not re.search(r"PID namespaces\s+Yes", sandbox_text)):
                    raise RuntimeError("actual Chrome namespace/seccomp sandbox not proven")
                sandbox_page.close()
                context = browser.new_context(service_workers="block")
                violations = []
                requests = []
                allowed_paths = {"/", "/favicon.ico", "/api/preparations", "/api/preparation-catalog"}

                def allow_readonly(route):
                    request = route.request
                    url = urlsplit(request.url)
                    permitted = (request.method in {"GET", "HEAD"} and request.url.startswith(base + "/")
                                 and url.path in allowed_paths and not url.query)
                    requests.append({"method": request.method, "path": url.path, "allowed": permitted})
                    if permitted:
                        route.continue_()
                    else:
                        violations.append("unexpected application request")
                        route.abort()

                context.route("**/*", allow_readonly)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                response = page.goto(base + "/", wait_until="load", timeout=10000)
                original = (ROOT / "src/parkweave/web.html").read_bytes()
                if response is None or response.status != 200 or response.body() != original:
                    raise RuntimeError("original page bytes not served")
                report["web_html_sha256"] = sha256(original).hexdigest()
                expect(page).to_have_title("园合 ParkWeave · 合成工程验证")
                expect(page.locator("h1")).to_have_text("园合 ParkWeave")
                for tab in ["collaboration", "resource", "service"]:
                    page.locator(f'[data-tab="{tab}"]').click()
                    expect(page.locator(f"#{tab}")).to_be_visible()
                    expect(page.locator(f'[data-tab="{tab}"]')).to_have_attribute("aria-current", "page")
                expect(page.locator("#token")).to_have_value("")
                # Nonempty inputs satisfy native `required`; each actual click reaches original JS.
                page.locator("#existing-preparation-id").fill("not-a-uuid")
                page.locator("#existing-preparation-read").click()
                expect(page.locator("#existing-preparation-status")).to_have_text("请填写原资料准备 UUID 编号。")
                page.locator("#existing-preparation-id").fill("11111111-1111-4111-8111-111111111111")
                page.locator("#existing-preparation-read").click()
                expect(page.locator("#existing-preparation-status")).to_have_text("请填写当前已有会话。")
                page.locator("#formal-preparation-check").click()
                expect(page.locator("#formal-preparation-status")).to_have_text("请填写当前已有会话。")
                expect(page.locator("#case-record-pack-download")).to_be_disabled()
                # Browser-origin GETs exercise original API authentication, with no token or mock DTO.
                for path in ["/api/preparations", "/api/preparation-catalog"]:
                    actual = page.evaluate("async path => {const r=await fetch(path);return {status:r.status,body:await r.json()}}", path)
                    if actual != {"status": 401, "body": {"detail": "session required"}}:
                        raise RuntimeError("original unauthenticated GET did not refuse")
                report["browser_requests"] = requests
                report["page_errors"] = errors
                if violations or errors or evidence["db_connect_attempts"] or evidence["blocked_write_probes"]:
                    raise RuntimeError("read-only browser boundary violated")
                if any(x["path"].endswith("/entry") for x in requests):
                    raise RuntimeError("empty-session UI made an entry request")
                context.close()
                directory_error_fixture_smoke(browser, base, report)
                personal_task_fixture_smoke(browser, base, report)
                ordinary_redispatch_fixture_smoke(browser, base, report)
                if evidence['blocked_write_probes'] or evidence['db_connect_attempts']:
                    raise RuntimeError('client-only fixture reached application write or database')
    report["checks"] = ["original_page_bytes", "title_and_heading", "three_workspace_clicks",
                        "invalid_id_feedback", "existing_entry_empty_session", "formal_entry_empty_session",
                        "two_original_401_GETs", "TXT_disabled", "zero_DB", "namespace_seccomp_sandbox"]


def directory_error_fixture_smoke(browser, base, report):
    """Original page/clicks, but synthetic client-only API replies; no real session.

    The fixture token is only an input string. Every API request is intercepted
    before the original server, and no API write or external request is allowed.
    """
    from playwright.sync_api import expect
    fixture = {"scope": "SYNTHETIC_CLIENT_RESPONSE_FIXTURES_ONLY", "cases": [], "requests": [], "page_errors": []}
    report["directory_error_fixture"] = fixture
    violations = []
    empty = {"scope": "CURRENT_OWNER_LOCAL_CASE_RECORDS", "read_only": True,
             "automatically_replayed": False, "items": [], "next_after": None}
    for mode in ["403-json", "403-html", "401-html", "502-html", "late-identity", "late-navigation", "other-feedback-during-retry"]:
        context = browser.new_context(service_workers="block", viewport={"width": 390, "height": 900})
        state = {"reads": 0, "held": None}

        def route_fixture(route):
            request = route.request
            url = urlsplit(request.url)
            fixture["requests"].append({"case": mode, "method": request.method, "path": url.path})
            if not request.url.startswith(base + "/") or request.method not in {"GET", "HEAD"}:
                violations.append("nonlocal or write request")
                route.abort()
            elif url.path in {"/", "/favicon.ico"} and not url.query:
                route.continue_()
            elif url.path == "/api/run-access/status" and not url.query:
                route.fulfill(status=401, json={"detail": "synthetic client fixture has no authority"})
            elif url.path == "/api/runs/" and not url.query and mode == "other-feedback-during-retry":
                route.fulfill(status=502, json={"detail": "synthetic unrelated read failure"})
            elif url.path == "/api/runs" and url.query == "limit=20":
                state["reads"] += 1
                if (mode.startswith("late-") and state["reads"] == 1
                        or mode == "other-feedback-during-retry" and state["reads"] == 2):
                    state["held"] = route
                elif state["reads"] == 1:
                    status = 403 if mode == "other-feedback-during-retry" else int(mode[:3])
                    if mode.endswith("html"):
                        route.fulfill(status=status, content_type="text/html", body="<h1>SYNTHETIC non-JSON error</h1>")
                    else:
                        route.fulfill(status=status, json={"detail": "synthetic denial"})
                else:
                    route.fulfill(status=200, json=empty)
            else:
                violations.append("unexpected application request")
                route.abort()

        context.route("**/*", route_fixture)
        page = context.new_page()
        page.on("pageerror", lambda error: fixture["page_errors"].append(str(error)))
        response = page.goto(base + "/", wait_until="load", timeout=10000)
        if response is None or response.body() != (ROOT / "src/parkweave/web.html").read_bytes():
            raise RuntimeError("fixture must use exact original page bytes")
        page.locator('[data-tab="collaboration"]').click()
        page.locator("#token").fill("SYNTHETIC_CLIENT_FIXTURE_A")
        page.locator("#record-directory-read").click()
        status = page.locator("#record-directory-status")
        if mode == "other-feedback-during-retry":
            expect(status).to_have_text("当前记录不可读或权限已撤回，请核对本人会话。")
            page.locator("#record-directory-read").focus()
            page.keyboard.press("Enter")
            deadline = time.monotonic() + 5
            while state["held"] is None and time.monotonic() < deadline:
                page.wait_for_timeout(10)
            if state["held"] is None:
                raise RuntimeError("synthetic retry response was not captured")
            # A different original read, not direct DOM/show manipulation.
            page.locator("#refresh").click()
            expect(page.locator("#page-feedback")).to_have_text("请求未完成")
            state["held"].fulfill(status=200, json=empty)
            expect(status).to_have_text("当前没有可读的本地建单记录。")
            expect(page.locator("#page-feedback")).to_have_text("请求未完成")
        elif mode.startswith("late-"):
            deadline = time.monotonic() + 5
            while state["held"] is None and time.monotonic() < deadline:
                page.wait_for_timeout(10)
            if state["held"] is None:
                raise RuntimeError("synthetic delayed response was not captured")
            if mode == "late-identity":
                page.locator("#token").fill("SYNTHETIC_CLIENT_FIXTURE_B")
            else:
                page.locator('[data-tab="service"]').click()
                page.locator('[data-tab="collaboration"]').click()
            page.locator("#record-directory-read").click()
            expect(status).to_have_text("当前没有可读的本地建单记录。")
            # 1.62 Response.finished() leaves a target-close task behind after
            # success. Wait for this exact held request's completion instead.
            held_request = state["held"].request
            with page.expect_request_finished(lambda request: request == held_request, timeout=5000) as finished_request:
                state["held"].fulfill(status=403, content_type="text/html", body="<h1>SYNTHETIC late denial</h1>")
            if finished_request.value.response().status != 403:
                raise RuntimeError("delayed denial did not finish with expected status")
            page.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
            expect(status).to_have_text("当前没有可读的本地建单记录。")
            expect(page.locator("#page-feedback")).to_have_text("")
        else:
            message = ("当前记录不可读或权限已撤回，请核对本人会话。" if mode.startswith("403") else
                       "会话已失效，请重新输入本人已有会话后读取。" if mode.startswith("401") else
                       "记录暂时无法读取，请稍后重新核对。")
            expect(status).to_have_text(message)
            expect(status).to_be_visible()
            expect(status).to_have_attribute("role", "status")
            expect(status).to_have_attribute("aria-live", "polite")
            if mode.startswith(("401", "403")):
                expect(page.locator("#page-feedback")).to_have_text(message)
            if page.locator("details.engineering-record").evaluate("element=>element.open"):
                raise RuntimeError("error feedback must not require opening engineering logs")
            expect(page.locator("#record-directory-read")).to_be_enabled()
            page.locator("#record-directory-read").focus()
            page.keyboard.press("Enter")
            expect(status).to_have_text("当前没有可读的本地建单记录。")
            expect(page.locator("#page-feedback")).to_have_text("")
        expect(page.locator("#record-directory-items button")).to_have_count(0)
        expect(page.locator("#record-directory-next")).to_be_hidden()
        expect(page.locator("#record-directory-read")).to_be_enabled()
        if state["reads"] != 2:
            raise RuntimeError("fixture expects two explicit reads, no automatic retries")
        fixture["cases"].append({"mode": mode, "status": "PASS", "explicit_directory_GETs": 2})
        context.close()
    if violations or fixture["page_errors"]:
        raise RuntimeError("synthetic browser fixture boundary violated")


def personal_task_fixture_smoke(browser, base, report):
    """Real original task-list clicks; all API replies are client-only fixtures."""
    from playwright.sync_api import expect
    fixture = {"scope": "SYNTHETIC_CLIENT_RESPONSE_FIXTURES_ONLY", "cases": [], "requests": [], "page_errors": []}
    report["personal_task_pagination_fixture"] = fixture
    violations = []
    cursor_a = "11111111-1111-4111-8111-111111111111"
    cursor_b = "22222222-2222-4222-8222-222222222222"
    path = "/api/preparation-tasks"
    first_task = {"id": "33333333-3333-4333-8333-333333333333", "case_id": "44444444-4444-4444-8444-444444444444",
                  "goal": "SYNTHETIC 分页待办", "kind": "SUPPLY_MATERIALS", "state": "IN_PREPARATION",
                  "revision": 1, "missing_slots": ["material_outline"]}

    def task_page(cursor, items=None):
        return {"scope": "SYNTHETIC_LOCAL_PREPARATION_ONLY", "read_only": True, "recorded_states_only": True,
                "role": "enterprise_operator", "check_limit": 100, "checked_count": 100,
                "items": [] if items is None else items, "next_before": cursor, "has_older_records": cursor is not None}

    for mode in ["502-json", "502-html", "network", "first-page", "401", "403",
                 "late-identity", "late-navigation"]:
        context = browser.new_context(service_workers="block", viewport={"width": 390, "height": 900})
        state = {"reads": [], "held": None}

        def route_fixture(route):
            request = route.request
            url = urlsplit(request.url)
            fixture["requests"].append({"case": mode, "method": request.method, "path": url.path, "query": url.query})
            if not request.url.startswith(base + "/") or request.method not in {"GET", "HEAD"}:
                violations.append("nonlocal or write request")
                route.abort()
            elif url.path in {"/", "/favicon.ico"} and not url.query:
                route.continue_()
            elif url.path == "/api/run-access/status" and not url.query:
                route.fulfill(status=401, json={"detail": "synthetic client fixture has no authority"})
            elif url.path == path and url.query in {"", "before=" + cursor_a, "before=" + cursor_b}:
                state["reads"].append(url.path + ("?" + url.query if url.query else ""))
                n = len(state["reads"])
                if mode.startswith("late-") and n == 2:
                    state["held"] = route
                elif n == 1 and mode != "first-page":
                    route.fulfill(status=200, json=task_page(cursor_a, [first_task]))
                elif n == (1 if mode == "first-page" else 2):
                    if mode == "network":
                        route.abort("failed")
                    elif mode == "502-html":
                        route.fulfill(status=502, content_type="text/html", body="<h1>SYNTHETIC upstream unavailable</h1>")
                    else:
                        route.fulfill(status=int(mode) if mode in {"401", "403"} else 502,
                                      json={"detail": "SYNTHETIC failed task page"})
                else:
                    end = url.query == "before=" + cursor_b or mode in {"401", "403"}
                    route.fulfill(status=200, json=task_page(None if end else cursor_b))
            else:
                violations.append("unexpected application request")
                route.abort()

        context.route("**/*", route_fixture)
        page = context.new_page()
        page.on("pageerror", lambda error: fixture["page_errors"].append(str(error)))
        response = page.goto(base + "/", wait_until="load", timeout=10000)
        if response is None or response.body() != (ROOT / "src/parkweave/web.html").read_bytes():
            raise RuntimeError("task fixture must use exact original page bytes")
        page.locator('[data-tab="collaboration"]').click()
        page.locator("#token").fill("SYNTHETIC_CLIENT_FIXTURE_A")
        read, next_page, status = (page.locator(selector) for selector in ["#prep-tasks", "#prep-tasks-next", "#prep-task-status"])
        read.click()
        if mode != "first-page":
            expect(status).to_contain_text("本页检查100件事项")
            expect(page.locator("#prep-task-items article")).to_have_count(1)
            next_page.click()
        if mode.startswith("late-"):
            deadline = time.monotonic() + 5
            while state["held"] is None and time.monotonic() < deadline:
                page.wait_for_timeout(10)
            if state["held"] is None:
                raise RuntimeError("synthetic task page was not captured")
            expect(status).to_have_text("正在读取本页资料准备待办…")
            if mode == "late-identity":
                page.locator("#token").fill("SYNTHETIC_CLIENT_FIXTURE_B")
            elif mode == "late-navigation":
                page.locator('[data-tab="service"]').click()
                page.locator('[data-tab="collaboration"]').click()
            expect(status).to_have_text("")
            expect(next_page).to_be_hidden()
            read.click()
            expect(status).to_contain_text("本页检查100件事项")
            held_request = state["held"].request
            delayed_status = 403
            with page.expect_request_finished(lambda request: request == held_request, timeout=5000) as finished_request:
                state["held"].fulfill(status=delayed_status, json=task_page(None))
            if finished_request.value.response().status != delayed_status:
                raise RuntimeError("delayed task response did not finish with expected status")
            page.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
            expect(status).to_contain_text("本页检查100件事项")
            expect(page.locator("#page-feedback")).to_have_text("")
            expect(next_page).to_have_text("检查更早的待办事项")
            next_page.click()
            expected_paths = [path, path + "?before=" + cursor_a, path, path + "?before=" + cursor_b]
        elif mode in {"401", "403"}:
            expect(status).to_contain_text("会话已失效" if mode == "401" else "当前身份无此事项或操作权限")
            expect(next_page).to_be_hidden()
            expect(page.locator("#prep-task-items article")).to_have_count(0)
            expect(page.locator("#prep-detail")).to_be_hidden()
            expect(page.locator("#page-feedback")).to_have_text("")
            expect(read).to_be_enabled()
            read.click()
            expected_paths = [path, path + "?before=" + cursor_a, path]
        else:
            expect(status).to_contain_text("本页资料准备待办读取失败")
            expect(status).to_be_visible()
            expect(status).to_have_attribute("role", "status")
            expect(status).to_have_attribute("aria-live", "polite")
            expect(page.locator("#prep-task-items article")).to_have_count(0)
            expect(page.locator("#page-feedback")).to_have_text("")
            expect(next_page).to_have_text("重试本页待办")
            expect(next_page).to_be_enabled()
            next_page.focus()
            page.keyboard.press("Enter")
            expect(status).to_contain_text("本页检查100件事项")
            expect(next_page).to_have_text("检查更早的待办事项")
            next_page.click()
            failed_path = path if mode == "first-page" else path + "?before=" + cursor_a
            expected_paths = ([] if mode == "first-page" else [path]) + [failed_path, failed_path, path + "?before=" + cursor_b]
        expect(status).to_contain_text("本页检查100件事项")
        expect(next_page).to_be_hidden()
        expect(read).to_be_enabled()
        expect(page.locator("#page-feedback")).to_have_text("")
        if state["reads"] != expected_paths:
            raise RuntimeError("task fixture requires exact explicit GET/cursor sequence, no automatic retries")
        fixture["cases"].append({"mode": mode, "status": "PASS", "task_GET_paths": state["reads"]})
        context.close()
    if violations or fixture["page_errors"]:
        raise RuntimeError("synthetic task browser fixture boundary violated")


def ordinary_redispatch_fixture_smoke(browser, base, report):
    """Real original form with exported owned-synthetic DTOs; no server API calls."""
    from playwright.sync_api import expect
    snapshot = json.loads((ROOT / 'tests/fixtures/ordinary-redispatch-ui.json').read_text())
    if (snapshot['scope'] != 'OWNED_SYNTHETIC_CLIENT_RESPONSE_SNAPSHOT_ONLY'
            or snapshot['before_view']['role'] != 'park_specialist'
            or snapshot['before_catalog']['can_offer_again'] is not True):
        raise RuntimeError('exact owned-synthetic reviewer snapshot required')
    fixture = {'scope': 'SYNTHETIC_CLIENT_RESPONSE_FIXTURES_ONLY', 'requests': [], 'page_errors': [],
               'backend_execution': 'NOT_RUN_BY_THIS_CHROME_CASE'}
    report['ordinary_redispatch_fixture'] = fixture
    path = '/api/preparations/' + snapshot['preparation_id'] + '/dispatch'
    state = {'committed': False, 'posts': []}
    violations = []
    context = browser.new_context(service_workers='block', viewport={'width': 390, 'height': 900})

    def route_fixture(route):
        request = route.request
        url = urlsplit(request.url)
        fixture['requests'].append({'method': request.method, 'path': url.path})
        if not request.url.startswith(base + '/'):
            violations.append('nonlocal request'); route.abort()
        elif request.method in {'GET', 'HEAD'} and url.path in {'/', '/favicon.ico'} and not url.query:
            route.continue_()
        elif request.method == 'GET' and url.path == '/api/run-access/status' and not url.query:
            route.fulfill(status=401, json={'detail': 'synthetic client fixture has no authority'})
        elif request.method == 'GET' and url.path == '/api/service-dispatches' and not url.query:
            route.fulfill(status=200, json=snapshot['list_view'])
        elif request.method == 'GET' and url.path == path and not url.query:
            route.fulfill(status=200, json=snapshot['after_view' if state['committed'] else 'before_view'])
        elif request.method == 'GET' and url.path == '/api/service-dispatches/catalog' and url.query == 'preparation_id=' + snapshot['preparation_id']:
            route.fulfill(status=200, json=snapshot['after_catalog' if state['committed'] else 'before_catalog'])
        elif request.method == 'POST' and url.path == path and not url.query:
            item = {'body': request.post_data_json, 'key': request.headers.get('idempotency-key')}
            if item['body'] != snapshot['post_body'] or not re.fullmatch('[0-9a-f-]{36}', item['key'] or ''):
                violations.append('unexpected client-only command'); route.abort(); return
            state['posts'].append(item)
            if len(state['posts']) == 1:
                state['committed'] = True
                route.abort('failed')  # Client-only committed-reply loss, no server write.
            elif len(state['posts']) == 2 and state['posts'][0] == item:
                route.fulfill(status=201, json=snapshot['post_response'])
            else:
                violations.append('changed or automatic retry'); route.abort()
        else:
            violations.append('unexpected application request'); route.abort()

    context.route('**/*', route_fixture)
    page = context.new_page()
    page.on('pageerror', lambda error: fixture['page_errors'].append(str(error)))
    response = page.goto(base + '/', wait_until='load', timeout=10000)
    if response is None or response.body() != (ROOT / 'src/parkweave/web.html').read_bytes():
        raise RuntimeError('redispatch fixture must use exact original page bytes')
    page.locator('[data-tab="collaboration"]').click()
    page.locator('#token').fill('SYNTHETIC_CLIENT_FIXTURE_REVIEWER')
    page.locator('#dispatch-list').click()
    expect(page.locator('#dispatch-items button')).to_have_count(1)
    page.locator('#dispatch-items button').click()
    expect(page.locator('#dispatch-offer')).to_be_visible()
    expect(page.locator('#dispatch-offer-button')).to_have_text('明确另派未接单事项')
    expect(page.locator('#dispatch-current')).to_contain_text('不延长办理时间')
    expect(page.locator('#dispatch-current')).to_contain_text(snapshot['first_deadline'])
    page.locator('#dispatch-executor').select_option(snapshot['post_body']['executor_id'])
    page.locator('#dispatch-offer-reason').fill(snapshot['post_body']['reason'])
    page.locator('#dispatch-offer-button').click()
    expect(page.locator('#dispatch-retry')).to_be_visible()
    if len(state['posts']) != 1:
        raise RuntimeError('no automatic redispatch retry permitted')
    page.locator('#dispatch-retry').click()
    expect(page.locator('#dispatch-retry')).to_be_hidden()
    expect(page.locator('#dispatch-current')).to_contain_text('执行者：unassigned')
    expect(page.locator('#dispatch-history')).to_contain_text('REOFFER')
    expect(page.locator('#dispatch-history')).to_contain_text('DECLINE')
    expect(page.locator('#dispatch-offer')).to_be_hidden()
    if len(state['posts']) != 2 or state['posts'][0] != state['posts'][1] or violations or fixture['page_errors']:
        raise RuntimeError('synthetic redispatch form boundary or retry proof failed')
    fixture.update(status='PASS', explicit_client_only_POSTs=2, same_original_key_and_body=True, server_API_requests=0)
    context.close()


def main():
    report = {"status": "FAIL", "scope": "real Chrome read-only page smoke and synthetic client directory/task/redispatch fixtures", "NOT_RUN": NOT_RUN}
    try:
        report["source_sha"] = require_hosted_once(os.environ)
        report["runner"] = {k: os.environ.get(k) for k in ["RUNNER_ENVIRONMENT", "RUNNER_OS", "ImageOS", "ImageVersion"]}
        report["packages"] = {name: version(name) for name in ["playwright", "pyee", "greenlet"]}
        browser_smoke(report)
        report["status"] = "PASS"
    except Exception as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    destination = ROOT / ".runtime/readonly-browser-report.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(encoded, encoding="utf-8")
    print(encoded, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("```json\n" + encoded + "```\n")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
