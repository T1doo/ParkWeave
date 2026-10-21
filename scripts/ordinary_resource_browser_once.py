"""One sandboxed hosted-CI resource UI walk against a fresh ordinary demo.

Preparation preconditions use the original ordinary API/worker helper. All resource
previews, holds, combination confirmation and Case association use real page clicks.
No local browser fallback, fixture business rows, external IO, or automatic retry.
"""
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "refs/heads/dev/pr0-resource-browser-20261020"
OUT = ROOT / ".runtime/ordinary-resource-browser-ci-20261020"


def require_hosted_once(environment):
    expected = {
        "RESOURCE_REPOSITORY": "T1doo/ParkWeave", "RESOURCE_REF": BRANCH,
        "RESOURCE_EVENT": "push", "RESOURCE_ATTEMPT": "1", "RESOURCE_NUMBER": "1",
        "RESOURCE_PUBLIC": "true", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux",
    }
    if any(environment.get(k) != v for k, v in expected.items()):
        raise RuntimeError("only the authorized public hosted Linux first push/attempt is allowed")
    if any(k.startswith("PARKWEAVE_") for k in environment):
        raise RuntimeError("no inherited business configuration is allowed")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", environment.get("RESOURCE_SHA", "")) or commit != environment["RESOURCE_SHA"]:
        raise RuntimeError("exact checked-out source SHA required")
    return commit


class BrowserBoundary:
    """Pass real HTTP through; budget only the explicit current scope's clicks."""

    def __init__(self, base, report):
        self.base = urlsplit(base)
        self.remaining = Counter()
        self.report = report
        self.phase = "READ_ONLY"

    def allow_scope_writes(self, scope, preparation_id):
        self.phase = "RESOURCE_UI_WRITES"
        paths = ["/api/resource-combinations", "/api/preparations/" + preparation_id + "/resource-link"]
        for row in scope["resources"]:
            paths.extend("/api/synthetic-resources/" + str(row["id"]) + suffix for suffix in ("/preview", "/holds"))
        self.remaining = Counter(paths)

    def readonly(self):
        if any(self.remaining.values()):
            raise RuntimeError("resource UI did not consume its exact six-request budget")
        self.phase = "READ_ONLY"

    def permit(self, method, url):
        parsed = urlsplit(url)
        if (parsed.scheme, parsed.netloc) != (self.base.scheme, self.base.netloc) or parsed.username or parsed.password:
            return False
        if method in {"GET", "HEAD"}:
            return parsed.path in {"/", "/favicon.ico", "/api/run-access/status", "/api/resource-bundles", "/api/plan-approval/status"} or bool(re.fullmatch(
                r"/api/(preparations|synthetic-resources|resource-holds|resource-combinations)(/[^?#]*)?", parsed.path))
        if method == "POST" and not parsed.query and self.remaining[parsed.path] > 0:
            self.remaining[parsed.path] -= 1
            return True
        return False

    def route(self, route):
        request = route.request
        path = urlsplit(request.url).path
        allowed = self.permit(request.method, request.url)
        self.report["browser_requests"].append(dict(phase=self.phase, method=request.method, path=path, allowed=allowed))
        if allowed:
            route.continue_()
        else:
            self.report["violations"].append(dict(method=request.method, path=path))
            route.abort()


def attach_context(browser, base, report):
    context = browser.new_context(service_workers="block", viewport={"width": 1200, "height": 950})
    boundary = BrowserBoundary(base, report)
    context.route("**/*", boundary.route)
    context.on("page", lambda p: p.on("pageerror", lambda error: report["page_errors"].append(str(error))))

    def response_observed(response):
        request = response.request
        row = dict(method=request.method, path=urlsplit(response.url).path, status=response.status)
        if request.method == "POST":
            row["request_key"] = request.headers.get("idempotency-key")
            row["body_sha256"] = sha256((request.post_data or "").encode()).hexdigest()
        report["browser_responses"].append(row)

    context.on("response", response_observed)
    return context, boundary


def open_page(context, base, token, report):
    page = context.new_page()
    page.set_default_timeout(10000)
    response = page.goto(base + "/", wait_until="load")
    original = (ROOT / "src/parkweave/web.html").read_bytes()
    assert response.status == 200 and response.body() == original
    report["web_html_sha256"] = sha256(original).hexdigest()
    page.locator("#token").fill(token)
    page.locator("#token").dispatch_event("change")
    return page


def open_case(page, preparation_id, label):
    page.locator('[data-tab="collaboration"]').click()
    page.locator("#prep-list").click()
    page.locator("#prep-items button").filter(has_text=label).click()
    page.wait_for_function("id => preparationId === id && preparationView !== null && preparationReadReady()", arg=preparation_id)
    page.locator("#case-resource-load").click()
    page.wait_for_function("() => caseResourceView !== null")
    assert page.evaluate("caseResourceContext.id") == preparation_id


def click_post(page, selector, path, status):
    with page.expect_response(lambda r: urlsplit(r.url).path == path and r.request.method == "POST") as observed:
        page.locator(selector).click()
    assert observed.value.status == status, "original resource UI request refused"
    return observed.value.json()


def resource_walk(page, boundary, scope, p, label, *, before_action=None):
    from playwright.sync_api import expect

    def submit(selector,path,status):
        if before_action is not None:before_action(page,selector)
        return click_post(page,selector,path,status)

    boundary.allow_scope_writes(scope, p["preparation_id"])
    page.locator('[data-tab="resource"]').click()
    page.locator("#resource-catalog").click()
    expect(page.locator("#resource-form")).to_be_visible()
    page.wait_for_function("() => bundleActor !== null")
    ids = page.locator("#resource-select option").evaluate_all("rows => rows.map(r => r.value)")
    assert set(ids) == {str(r["id"]) for r in scope["resources"]}
    start = page.locator("#resource-start").input_value()
    end = page.locator("#resource-end").input_value()
    hold_ids = []
    for n, resource_id in enumerate(ids):
        page.locator("#resource-select").select_option(resource_id)
        page.locator("#resource-start").fill(start)
        page.locator("#resource-end").fill(end)
        page.locator("#resource-quantity").fill("1")
        page.locator("#resource-ttl").fill("120")
        page.locator("#resource-purpose").fill("SYNTHETIC browser " + label + " resource " + str(n))
        path = "/api/synthetic-resources/" + resource_id
        submit("#resource-preview", path + "/preview", 200)
        expect(page.locator("#resource-hold")).to_be_enabled()
        assert page.evaluate("resourcePreview.view.available") is True
        created = submit("#resource-hold", path + "/holds", 201)
        card = page.locator("#resource-current [data-hold-id]")
        expect(card).to_have_count(1)
        expect(card).to_have_attribute("data-hold-id", created["hold"]["id"])
        expect(card).to_contain_text("短期占位有效")
        hold_ids.append(card.get_attribute("data-hold-id"))
    assert len(set(hold_ids)) == 2
    page.locator("#resource-mine").click()
    for hold_id in hold_ids:
        page.locator('[data-combination-hold="' + hold_id + '"]').check()
    expect(page.locator("#combination-confirm")).to_be_enabled()
    submit("#combination-confirm", "/api/resource-combinations", 201)
    group = page.locator("#combination-items [data-combination-id]")
    expect(group).to_have_attribute("data-state", "CONFIRMED")
    combination_id = group.get_attribute("data-combination-id")
    expect(page.locator("#combination-confirm")).to_be_disabled()
    open_case(page, p["preparation_id"], label)
    assert page.evaluate("caseResourceView.current") is None
    page.locator("#case-resource-choice").select_option(combination_id)
    page.locator("#case-resource-reason").fill("SYNTHETIC browser explicit Case association " + label)
    submit("#case-resource-form button", "/api/preparations/" + p["preparation_id"] + "/resource-link", 201)
    page.wait_for_function("id => caseResourceView?.current?.combination.id === id && caseResourceView.link_revision === 1", arg=combination_id)
    expect(page.locator("#case-resource-summary")).to_contain_text("当前资料版本与资源关联有效")
    boundary.readonly()
    return dict(preparation_id=p["preparation_id"], case_id=p["case_id"], run_id=p["run_id"],
                label=label, hold_ids=hold_ids, combination_id=combination_id,
                resource_link_view=durable_view(page.evaluate("caseResourceView")))


def durable_view(view):
    # Only the explicitly per-read observation time changes across reads/restarts.
    return {key: value for key, value in view.items() if key != "server_time"}


def foreign_read_probes(page, foreign, report):
    # Explicit browser-origin GET probes, separate from the user-click write path.
    paths = ["/api/resource-combinations/" + foreign["combination_id"],
             "/api/preparations/" + foreign["preparation_id"] + "/resource-link"]
    paths.extend("/api/resource-holds/" + h for h in foreign["hold_ids"])
    for path in paths:
        status = page.evaluate("async path => (await fetch(path, {headers:{Authorization:'Bearer '+document.getElementById('token').value}})).status", path)
        report["foreign_GET_probes"].append(dict(path=path, status=status))
        assert status == 403


def scope_lists(page, own, foreign):
    page.locator('[data-tab="resource"]').click()
    with page.expect_response(lambda r: urlsplit(r.url).path == "/api/resource-combinations" and r.request.method == "GET"):
        page.locator("#combination-mine").click()
    page.wait_for_function("id => !!document.querySelector('[data-combination-id=\"'+id+'\"]')", arg=own["combination_id"])
    assert page.locator('[data-combination-id="' + foreign["combination_id"] + '"]').count() == 0
    open_case(page, own["preparation_id"], own["label"])
    view = page.evaluate("caseResourceView")
    assert view["current"]["combination"]["id"] == own["combination_id"]
    assert foreign["combination_id"] not in page.locator("#case-resource-panel").inner_text()
    return durable_view(view)


def verify_sandbox(browser, report):
    command = browser.new_browser_cdp_session().send("Browser.getBrowserCommandLine")["arguments"]
    forbidden = {"--no-sandbox", "--disable-setuid-sandbox", "--disable-seccomp-filter-sandbox",
                 "--disable-namespace-sandbox", "--disable-gpu-sandbox", "--no-zygote", "--disable-web-security"}
    if any(arg.split("=", 1)[0] in forbidden for arg in command):
        raise RuntimeError("Chrome reports forbidden sandbox/security switches")
    report["chrome_arguments"] = command
    sandbox_page = browser.new_page()
    try:
        sandbox_page.goto("chrome://sandbox", timeout=10000)
        text = sandbox_page.locator("body").inner_text()
        report["sandbox_status"] = text
        assert "You are adequately sandboxed." in text
        assert re.search(r"Seccomp-BPF sandbox\s+Yes", text) and re.search(r"PID namespaces\s+Yes", text)
    finally:
        sandbox_page.close()


def business_walk(browser, report, secrets):
    # The original helpers launch the actual CLI; no fixture injects business rows.
    from test_ordinary_synthetic_demo import command, environment, server, prepare_case, PrivateTokens, call
    from scripts import ordinary_synthetic_demo as demo
    from parkweave.store import Store

    setup = subprocess.run(command("setup"), cwd=ROOT, env=environment(), capture_output=True, text=True, timeout=45)
    (OUT / "setup.stdout").write_text(setup.stdout)
    (OUT / "setup.stderr").write_text(setup.stderr)
    assert setup.returncode == 0, "original fresh synthetic setup failed; private log retained"
    rows = [json.loads(line) for line in setup.stdout.splitlines() if line.startswith("{")]
    state = Path(rows[-1]["state_dir"])
    assert state.parent == Path("/tmp") and state.name.startswith("parkweave-ordinary-demo-")
    report["state_dir"] = str(state)
    tokens = PrivateTokens(json.loads((state / "sessions.json").read_text()))
    secrets.extend(tokens.values())
    original_marker = (state / "state.json").read_bytes()
    marker = json.loads(original_marker)
    report["source_binding_sha256"] = marker["source"]["sha256"]
    starts, prepared, results = [], [], []
    report["starts"] = starts
    report["cases"] = results
    scopes = [demo.SCOPES["primary"], demo.SCOPES["secondary"]]
    counts = ("runs", "cases", "preparations", "synthetic_resource_holds", "synthetic_resource_combinations", "case_resource_links", "run_assignments")
    with server(state, OUT / "first-start") as (api, ready):
        starts.append(ready)
        with Store(demo.lifecycle.dsn(state)).connect() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            report["initial_counts"] = {t: conn.execute("SELECT count(*) n FROM " + t).fetchone()["n"] for t in counts}
            assert all(n == 0 for n in report["initial_counts"].values())
        for scope, label in zip(scopes, ("ci-resource-primary", "ci-resource-secondary")):
            scoped = PrivateTokens({k: tokens[v] for k, v in scope["sessions"].items()})
            p, _ = prepare_case(api, scoped, label, scope)
            prepared.append((p, scoped))
        context, boundary = attach_context(browser, ready["url"], report)
        try:
            pages = []
            for scope, (p, scoped), label in zip(scopes, prepared, ("ci-resource-primary", "ci-resource-secondary")):
                page = open_page(context, ready["url"], scoped["enterprise"], report)
                pages.append(page)
                results.append(resource_walk(page, boundary, scope, p, label))
            for n, page in enumerate(pages):
                own, foreign = results[n], results[1 - n]
                assert scope_lists(page, own, foreign) == own["resource_link_view"]
                foreign_read_probes(page, foreign, report)
                actual = call(api, prepared[n][1], "/api/preparations/" + own["preparation_id"] + "/resource-link")
                assert durable_view(actual) == own["resource_link_view"]
        finally:
            context.close()
    with server(state, OUT / "cold-start") as (api, ready):
        starts.append(ready)
        assert all(starts[0][key] != ready[key] for key in ("api_pid", "worker_pid", "postgres_pid"))
        before = len(report["browser_requests"])
        context, boundary = attach_context(browser, ready["url"], report)
        try:
            for n, own in enumerate(results):
                page = open_page(context, ready["url"], prepared[n][1]["enterprise"], report)
                assert scope_lists(page, own, results[1 - n]) == own["resource_link_view"]
                page.close()
            assert all(r["method"] in {"GET", "HEAD"} for r in report["browser_requests"][before:])
        finally:
            context.close()
        with Store(demo.lifecycle.dsn(state)).connect() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            assert demo.authority(conn) == marker["authority"]
            report["final_counts"] = {t: conn.execute("SELECT count(*) n FROM " + t).fetchone()["n"] for t in counts}
        assert report["final_counts"] == dict(runs=2, cases=2, preparations=2, synthetic_resource_holds=4,
                                               synthetic_resource_combinations=2, case_resource_links=2, run_assignments=0)
    assert (state / "state.json").read_bytes() == original_marker
    assert not (state / "data/postmaster.pid").exists() and not (state / "stop-unconfirmed").exists()
    assert not report["page_errors"] and not report["violations"]
    posts = [r for r in report["browser_responses"] if r["method"] == "POST"]
    assert len(posts) == 12 and sum(r["status"] == 200 for r in posts) == 4 and sum(r["status"] == 201 for r in posts) == 8
    keys = [r["request_key"] for r in posts if r["status"] == 201]
    assert len(set(keys)) == 8 and all(keys)
    report.update(cases=results, starts=starts, authority_unchanged=True, marker_unchanged=True,
                  cold_resource_views_equal=True, cold_GET_only=True, owned_services_stopped=True,
                  preparation_preconditions="original ordinary worker/API helper; not browser clicks")


def redact(value, secrets):
    raw = json.dumps(value, ensure_ascii=False, default=str)
    for secret in secrets:
        raw = raw.replace(secret, "[REDACTED_SYNTHETIC_SESSION]")
    return raw


def main():
    os.umask(0o077)
    report = dict(scope="SANDBOXED_CHROME_ORDINARY_RESOURCE_UI_HTTP_PG", status="NOT_RUN",
                  browser_requests=[], browser_responses=[], foreign_GET_probes=[], page_errors=[], violations=[],
                  real_model_calls=0, not_run=["full_57_POST_case_chain", "user_manual_acceptance", "Windows_AT", "real_business"])
    secrets = []
    started = time.monotonic()
    try:
        report["source_sha"] = require_hosted_once(os.environ)
        OUT.mkdir(parents=True, mode=0o700, exist_ok=False)
        report["packages"] = {p: version(p) for p in ("playwright", "pgserver", "psycopg", "fastapi")}
        report["runner"] = {k: os.environ.get(k) for k in ("ImageOS", "ImageVersion", "RUNNER_ENVIRONMENT", "RUNNER_OS")}
        browser_environment = dict(os.environ)
        for name, directory in (("XDG_CONFIG_HOME", "chrome-config"), ("XDG_CACHE_HOME", "chrome-cache")):
            path = OUT / directory
            path.mkdir(mode=0o700)
            browser_environment[name] = str(path)
        report["browser_profile_dirs"] = {name: browser_environment[name] for name in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME")}
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            with playwright.chromium.launch(channel="chrome", headless=True, chromium_sandbox=True,
                                            args=["--enable-automation"], env=browser_environment) as browser:
                report["chrome_version"] = browser.version
                verify_sandbox(browser, report)
                business_walk(browser, report, secrets)
        report["status"] = "PASS"
    except BaseException as error:
        report.update(status="FAIL", error_type=type(error).__name__, error=str(error))
    report["seconds"] = round(time.monotonic() - started, 3)
    serialized = redact(report, secrets)
    if OUT.exists():
        (OUT / "result.json").write_text(serialized + "\n")
    print(serialized, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write("```json\n" + serialized + "\n```\n")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
