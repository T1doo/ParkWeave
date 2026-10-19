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
BRANCH = "refs/heads/dev/f2-readonly-browser-smoke-20261019"
NOT_RUN = ["database", "Case", "worker", "P1-P5", "TXT_download", "business_cold_recovery", "Windows_AT"]


def require_hosted_once(environment):
    expected = {
        "SMOKE_REPOSITORY": "T1doo/ParkWeave", "SMOKE_REF": BRANCH,
        "SMOKE_EVENT": "push", "SMOKE_ATTEMPT": "1", "SMOKE_NUMBER": "1",
        "SMOKE_PUBLIC": "true", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux",
    }
    if any(environment.get(k) != v for k, v in expected.items()):
        raise RuntimeError("only the first public dedicated hosted Linux push is allowed")
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
            with playwright.chromium.launch(channel="chrome", headless=True, chromium_sandbox=True) as browser:
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
    report["checks"] = ["original_page_bytes", "title_and_heading", "three_workspace_clicks",
                        "invalid_id_feedback", "existing_entry_empty_session", "formal_entry_empty_session",
                        "two_original_401_GETs", "TXT_disabled", "zero_DB", "namespace_seccomp_sandbox"]


def main():
    report = {"status": "FAIL", "scope": "real Chrome unauthenticated read-only page smoke", "NOT_RUN": NOT_RUN}
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
