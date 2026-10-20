"""One sandboxed hosted Chrome check of notification transport/refusal handling.

Serves exact shipped HTML and bounded synthetic HTTP responses, not a business
backend. No database, real identity, model, external service or product mutation.
"""
from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from urllib.parse import urlsplit

from scripts.ordinary_resource_browser_once import verify_sandbox

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "refs/heads/dev/f2-notice-auth-browser-20261020"
PRODUCT_TREE = "5d2a66b3fffc1caabc01109172527522f88c251e"
WEB_HASH = "a50f602bbc1bf84f28afbae16b9ff4f5e9bdbe9d951eaa7700d09122bc497301"
OUT = ROOT / ".runtime/notice-auth-browser-ci-20261020"
A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"


def require_hosted_once(environment):
    expected = dict(NOTICE_REPOSITORY="T1doo/ParkWeave", NOTICE_REF=BRANCH, NOTICE_EVENT="push",
                    NOTICE_ATTEMPT="1", NOTICE_NUMBER="1", NOTICE_PUBLIC="true",
                    RUNNER_ENVIRONMENT="github-hosted", RUNNER_OS="Linux")
    if any(environment.get(k) != v for k, v in expected.items()) or any(k.startswith("PARKWEAVE_") for k in environment):
        raise RuntimeError("only the authorized public hosted Linux first push/attempt is allowed")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", environment.get("NOTICE_SHA", "")) or commit != environment["NOTICE_SHA"]:
        raise RuntimeError("exact checked-out source SHA required")
    tree = subprocess.check_output(["git", "rev-parse", "HEAD:src"], cwd=ROOT, text=True).strip()
    if tree != PRODUCT_TREE or sha256((ROOT / "src/parkweave/web.html").read_bytes()).hexdigest() != WEB_HASH:
        raise RuntimeError("the reviewed df0849dc product bytes are required")
    return commit


class Boundary:
    def __init__(self, base, mode, report):
        self.base = base
        self.report = report
        self.remaining = Counter({("GET", "/"): 1, ("GET", "/favicon.ico"): 1,
                                  ("GET", "/api/dispatch-notices"): 2 if mode == "late" else 1,
                                  ("GET", "/api/dispatch-notices/" + A): 1})
        if mode == "late":
            self.remaining[("GET", "/api/dispatch-notices/" + B)] = 1
        else:
            self.remaining[("POST", "/api/dispatch-notices/" + A + "/commands")] = 1

    def permit(self, method, url):
        parsed = urlsplit(url)
        key = (method, parsed.path)
        if (parsed.scheme + "://" + parsed.netloc != self.base or parsed.username or parsed.password
                or parsed.query or parsed.fragment or self.remaining[key] < 1):
            return False
        self.remaining[key] -= 1
        return True

    def route(self, route):
        request = route.request
        allowed = self.permit(request.method, request.url)
        row = dict(method=request.method, path=urlsplit(request.url).path, allowed=allowed)
        self.report["requests"].append(row)
        if allowed:
            route.continue_()
        else:
            self.report["violations"].append(row)
            route.abort()


def item(identifier, read=False):
    return dict(event_id=identifier, preparation_id="33333333-3333-4333-8333-333333333333",
                dispatch_id="44444444-4444-4444-8444-444444444444", revision=1, action="OFFER",
                delivered_at="SYNTHETIC delivered", historical=False,
                open_requested_at="SYNTHETIC prior explicit OPEN", read_at="SYNTHETIC read" if read else None)


class Fixture:
    def __init__(self, mode, status):
        self.mode, self.status = mode, status
        self.allow_headers, self.release_body = threading.Event(), threading.Event()
        self.detail_started, self.headers_sent = threading.Event(), threading.Event()
        self.body_handler_done = threading.Event()
        self.lists = 0
        self.errors = []
        self.threads = []

    def handler(self):
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                fixture.threads.append(threading.current_thread())

            def log_message(self, *_args):
                pass

            def json_reply(self, status, value):
                data = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def stalled_refusal(self):
                self.send_response(fixture.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", "1024")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.flush()
                fixture.headers_sent.set()
                # No body bytes are sent, even during teardown; bounded lifetime.
                try:
                    fixture.release_body.wait(8)
                finally:
                    fixture.body_handler_done.set()
                self.close_connection = True

            def do_GET(self):
                if self.path == "/":
                    data = (ROOT / "src/parkweave/web.html").read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                elif self.path == "/favicon.ico":
                    self.send_response(204)
                    self.end_headers()
                elif self.path == "/api/dispatch-notices":
                    fixture.lists += 1
                    identifier = B if fixture.mode == "late" and fixture.lists > 1 else A
                    self.json_reply(200, dict(scope="SYNTHETIC_INTERNAL_DISPATCH_NOTICES_ONLY",
                                             items=[item(identifier)], check_limit=100, page_limit=20, next_cursor=None))
                elif self.path in {"/api/dispatch-notices/" + A, "/api/dispatch-notices/" + B}:
                    if fixture.mode == "late" and self.path.endswith(A):
                        fixture.detail_started.set()
                        if not fixture.allow_headers.wait(8):
                            fixture.errors.append("late header release timed out")
                            return
                        self.stalled_refusal()
                    else:
                        self.json_reply(200, dict(notice=item(self.path.rsplit("/", 1)[1])))
                else:
                    fixture.errors.append("unexpected GET path")
                    self.json_reply(405, {})

            def do_POST(self):
                size = int(self.headers.get("Content-Length", "0"))
                if self.path != "/api/dispatch-notices/" + A + "/commands" or not 0 < size <= 256:
                    fixture.errors.append("unexpected POST path or size")
                    self.json_reply(405, {})
                    return
                self.connection.settimeout(2)
                body = json.loads(self.rfile.read(size))
                if body != {"action": "MARK_READ", "expected_revision": 1}:
                    fixture.errors.append("unexpected command")
                    self.json_reply(405, {})
                elif fixture.mode == "refusal":
                    self.stalled_refusal()
                elif fixture.status == 200:
                    self.json_reply(200, dict(notice=item(A, read=True)))
                else:
                    self.json_reply(fixture.status, dict(detail="SYNTHETIC conflict"))

        return Handler


@contextmanager
def serve(fixture):
    server = ThreadingHTTPServer(("127.0.0.1", 0), fixture.handler())
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port)
    finally:
        fixture.allow_headers.set()
        fixture.release_body.set()
        server.shutdown()
        server.server_close()
        thread.join(2)
        deadline = time.monotonic() + 2
        for owned in fixture.threads:
            owned.join(max(0, deadline - time.monotonic()))
        if thread.is_alive() or any(owned.is_alive() for owned in fixture.threads):
            raise RuntimeError("owned HTTP fixture did not stop")


def scenario(browser, mode, status, result):
    from playwright.sync_api import expect
    result.update(mode=mode, status=status, requests=[], violations=[], page_errors=[], result="RUNNING")
    fixture = Fixture(mode, status)
    with serve(fixture) as base:
        context = browser.new_context(service_workers="block", viewport={"width": 1200, "height": 900})
        try:
            boundary = Boundary(base, mode, result)
            context.route("**/*", boundary.route)
            # Observe native Response parsing; return its original promise unchanged.
            context.add_init_script("""window.__noticeJSON=[];const originalJSON=Response.prototype.json;
                Response.prototype.json=function(...args){window.__noticeJSON.push({status:this.status,url:this.url});
                return originalJSON.apply(this,args);};""")
            page = context.new_page()
            page.set_default_timeout(3000)
            page.on("pageerror", lambda error: result["page_errors"].append(str(error)))
            response = page.goto(base + "/", wait_until="load", timeout=10000)
            assert response.status == 200 and sha256(response.body()).hexdigest() == WEB_HASH
            # Preserve each original promise/return value; observe the actual error
            # handler completion rather than guessing from frames or response events.
            page.evaluate("""() => {
                window.__noticeReads={};window.__noticeErrorSettled=0;
                const originalLoad=loadNotice;
                loadNotice=function(...args){window.__noticeReads[args[0]]='PENDING';
                    const promise=originalLoad.apply(this,args);
                    promise.then(()=>window.__noticeReads[args[0]]='FULFILLED',
                                 ()=>window.__noticeReads[args[0]]='REJECTED');return promise;};
                const originalError=noticeError;
                noticeError=function(...args){try{return originalError.apply(this,args);}
                    finally{window.__noticeErrorSettled++;}};
            }""")
            page.locator("#token").fill("SYNTHETIC_NOTICE_BROWSER_A")
            page.locator('[data-tab="collaboration"]').click()
            page.locator("#notice-list").click()
            card = page.locator('[data-notice-id="' + A + '"] button')
            expect(card).to_be_visible()
            with page.expect_request(lambda r: urlsplit(r.url).path.endswith(A) and r.method == "GET"):
                card.click()
            if mode == "late":
                page.locator("#token").fill("SYNTHETIC_NOTICE_BROWSER_B")
                page.locator("#notice-list").click()
                page.locator('[data-notice-id="' + B + '"] button').click()
                page.wait_for_function("id => noticeView?.event_id === id", arg=B)
                before = page.evaluate("JSON.stringify({noticeView,noticeContext,noticeId})")
                with page.expect_response(lambda r: urlsplit(r.url).path.endswith(A) and r.status == status):
                    fixture.allow_headers.set()
                page.wait_for_function("id => window.__noticeReads[id] === 'REJECTED' && window.__noticeErrorSettled === 1", arg=A)
                assert page.evaluate("JSON.stringify({noticeView,noticeContext,noticeId})") == before
                expect(page.locator("#notice-error")).to_have_text("")
                result["late_identity_and_selection_preserved"] = True
            else:
                page.wait_for_function("id => noticeView?.event_id === id", arg=A)
                expect(page.locator("#notice-detail")).to_be_visible()
                expect(page.locator("#notice-read")).to_be_enabled()
                with page.expect_response(lambda r: r.request.method == "POST" and r.status == status):
                    page.locator("#notice-read").click()
                if mode == "refusal":
                    expect(page.locator("#notice-detail")).to_be_hidden(timeout=1500)
                    expect(page.locator("#notice-error")).to_contain_text("刷新")
                    assert page.evaluate("noticeView===null&&noticeContext===null&&noticeId===null&&noticeNextCursor===null&&preparationView===null&&dispatchView===null&&receiptView===null")
                    expect(page.locator("#notice-summary")).to_have_text("")
                    result["private_notice_cleared_before_body"] = True
                elif status == 200:
                    page.wait_for_function("noticeView?.read_at !== null")
                    expect(page.locator("#notice-read")).to_be_disabled()
                    expect(page.locator("#notice-summary")).to_contain_text("本人已确认已读")
                else:
                    expect(page.locator("#notice-error")).to_contain_text("版本已改变")
                    assert page.evaluate("noticeView.event_id") == A
                    expect(page.locator("#notice-detail")).to_be_visible()
            if mode in {"refusal", "late"}:
                assert fixture.headers_sent.is_set() and not fixture.release_body.is_set() and not fixture.body_handler_done.is_set()
                assert page.evaluate("window.__noticeJSON.every(x => x.status !== 401 && x.status !== 403)")
                result["error_headers_received_body_never_finished"] = True
            assert not result["page_errors"] and not result["violations"] and not fixture.errors
            expected_posts = 0 if mode == "late" else 1
            assert sum(r["method"] == "POST" for r in result["requests"]) == expected_posts
            assert all(count == 0 for key, count in boundary.remaining.items() if key[1] != "/favicon.ico")
            result.update(result="PASS", automatic_command_requests=0)
        finally:
            context.close()
    result["owned_http_stopped"] = True
    return result


def main():
    os.umask(0o077)
    report = dict(scope="SANDBOXED_REAL_CHROME_SYNTHETIC_NOTICE_HTTP_ONLY", status="NOT_RUN", scenarios=[],
                  real_model_calls=0, business_database_connections=0,
                  not_run=["real_business_authorization", "Windows", "formal_AT", "full_project_regression"])
    started = time.monotonic()
    try:
        report["source_sha"] = require_hosted_once(os.environ)
        OUT.mkdir(mode=0o700, parents=True, exist_ok=False)
        report.update(product_src_tree=PRODUCT_TREE, web_html_sha256=WEB_HASH,
                      playwright_version=version("playwright"))
        browser_environment = dict(os.environ)
        for name, directory in (("XDG_CONFIG_HOME", "chrome-config"), ("XDG_CACHE_HOME", "chrome-cache")):
            path = OUT / directory
            path.mkdir(mode=0o700)
            browser_environment[name] = str(path)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            with playwright.chromium.launch(channel="chrome", headless=True, chromium_sandbox=True,
                                            args=["--enable-automation"], env=browser_environment) as browser:
                report["chrome_version"] = browser.version
                verify_sandbox(browser, report)
                for mode, status in [("refusal", 401), ("refusal", 403), ("late", 401), ("late", 403),
                                     ("normal", 200), ("normal", 409)]:
                    result = {}
                    report["scenarios"].append(result)
                    scenario(browser, mode, status, result)
        report["status"] = "PASS"
    except BaseException as error:
        report.update(status="FAIL", error_type=type(error).__name__, error=str(error))
        if report["scenarios"] and report["scenarios"][-1].get("result") == "RUNNING":
            report["scenarios"][-1]["result"] = "FAIL"
    report["seconds"] = round(time.monotonic() - started, 3)
    serialized = json.dumps(report, ensure_ascii=False, default=str)
    if OUT.exists():
        (OUT / "result.json").write_text(serialized + "\n")
    print(serialized, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write("```json\n" + serialized + "\n```\n")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
