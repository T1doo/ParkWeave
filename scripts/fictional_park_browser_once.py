"""Bounded hosted Chrome walk: shipped fictional guide, actual DOM writes only.

Fresh SYNTHETIC setup is installation input. No API helper, JavaScript business
function or fixture creates any Run, material, ADOPT, dispatch or receipt.
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

from scripts import ordinary_resource_browser_once as resource

ROOT = Path(__file__).resolve().parents[1]
BRANCH = 'refs/heads/dev/fictional-park-browser-once-20261020'
PRIVATE = ROOT / '.runtime/fictional-park-browser-once'


def require_hosted(environment, *, run_number='4'):
    expected = dict(PW_BROWSER_REPOSITORY='T1doo/ParkWeave', PW_BROWSER_REF=BRANCH,
        PW_BROWSER_EVENT='push', PW_BROWSER_ATTEMPT='1', PW_BROWSER_PUBLIC='true',
        RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Linux')
    if any(environment.get(k) != v for k, v in expected.items()) or environment.get('PW_BROWSER_NUMBER') != run_number:
        raise RuntimeError('only the bounded public hosted branch push is authorized')
    if any(k.startswith('PARKWEAVE_') for k in environment):
        raise RuntimeError('inherited business configuration refused')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if not re.fullmatch('[0-9a-f]{40}', environment.get('PW_BROWSER_SHA', '')) or environment['PW_BROWSER_SHA'] != head:
        raise RuntimeError('exact checked-out SHA required')
    return head


class Boundary:
    def __init__(self, base, report):
        self.base, self.report = urlsplit(base), report
        self.remaining, self.actions = Counter(), {}
        self.reads = 0

    def authorize(self, path, action=None):
        assert not any(self.remaining.values()), 'previous explicit write has not completed'
        self.remaining[path] = 1
        self.actions = {path: action}

    def intake(self):
        assert not any(self.remaining.values())
        self.remaining = Counter(['/api/runs', '/api/preparations'])
        self.actions = {}

    def allow_scope_writes(self, scope, preparation_id):
        assert not any(self.remaining.values())
        paths = ['/api/resource-combinations', '/api/preparations/' + preparation_id + '/resource-link']
        for row in scope['resources']:
            paths.extend('/api/synthetic-resources/' + str(row['id']) + suffix for suffix in ('/preview', '/holds'))
        self.remaining, self.actions = Counter(paths), {}

    def readonly(self):
        assert not any(self.remaining.values()), 'explicit DOM write budget was not consumed'

    def route(self, route):
        request = route.request
        url = urlsplit(request.url)
        same = ((url.scheme, url.netloc) == (self.base.scheme, self.base.netloc)
                and not url.username and not url.password)
        allowed = False
        if same and request.method in ('GET', 'HEAD'):
            self.reads += 1
            allowed = self.reads <= 800 and (url.path in ('/', '/demo', '/favicon.ico') or url.path.startswith('/api/'))
        elif same and request.method == 'POST' and not url.query and self.remaining[url.path] > 0:
            action = self.actions.get(url.path)
            allowed = action is None or request.post_data_json.get('action') == action
            if allowed and url.path.endswith('/service-case-plan'):
                from parkweave.service_case_steps import Adopt
                try:
                    adopt = Adopt.model_validate(request.post_data_json)
                    allowed = bool(adopt.candidate_id and not adopt.partial_adoption and not adopt.local_revision)
                except ValueError:
                    allowed = False
            if allowed:
                self.remaining[url.path] -= 1
        if not allowed:
            self.report['violations'].append(dict(method=request.method, path=url.path))
        route.continue_() if allowed else route.abort()


def walk(browser, report, secrets, public, *, before_stop=None, capture_names=None, page_ready=None):
    from playwright.sync_api import expect
    from test_ordinary_synthetic_demo import command, environment, server
    from test_demo_original_page_intake_browser import settled, open_from_list, open_service_plan, verify
    from scripts import ordinary_synthetic_demo as demo
    from parkweave.store import Store
    from service_release_acceptance_support import case_history

    report['stage'] = 'FRESH_SYNTHETIC_INSTALLATION'
    setup = subprocess.run(command('setup', '--with-local-catalog'), cwd=ROOT, env=environment(),
                           capture_output=True, text=True, timeout=45)
    (PRIVATE / 'setup.stdout').write_text(setup.stdout)
    (PRIVATE / 'setup.stderr').write_text(setup.stderr)
    assert setup.returncode == 0, 'fresh setup failed; raw output retained privately'
    ready = json.loads(setup.stdout.splitlines()[-1])
    state, config = Path(ready['state_dir']), Path(ready['local_demo_config'])
    tokens = json.loads((state / 'sessions.json').read_text())
    secrets.extend(tokens.values())
    inputs = [state / 'state.json', state / 'sessions.json', config, config.parent / 'pack.json', config.parent / 'journal.json']
    before = {str(p): sha256(p.read_bytes()).hexdigest() for p in inputs}
    marker = json.loads((state / 'state.json').read_text())
    report['state_dir'] = str(state)
    with server(state, PRIVATE / 'server', local_demo_config=config) as (api, launched):
        base = str(api.base_url).rstrip('/')
        report['processes'] = launched
        with Store(demo.lifecycle.dsn(state)).connect() as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            assert all(conn.execute('SELECT count(*) n FROM ' + table).fetchone()['n'] == 0
                for table in ('runs', 'cases', 'preparations', 'service_dispatches', 'service_receipt_steps', 'run_assignments'))
        context = browser.new_context(service_workers='block', accept_downloads=True, viewport=dict(width=1440, height=1100))
        boundary = Boundary(base, report)
        context.route('**/*', boundary.route)
        context.on('page', lambda p: p.on('pageerror', lambda error: report['page_errors'].append(str(error))))
        page = context.new_page()
        page.set_default_timeout(15000)
        w = None

        def observed(response):
            request = response.request
            row = dict(stage=report['stage'], method=request.method, path=urlsplit(response.url).path, status=response.status)
            if request.method == 'GET' and row['path'] in ('/', '/demo'):
                row['content_security_policy'] = response.headers.get('content-security-policy')
            if request.method == 'POST':
                row.update(request_key=request.headers.get('idempotency-key'), body_sha256=sha256((request.post_data or '').encode()).hexdigest())
            report['responses'].append(row)
        context.on('response', observed)

        def shot(name):
            if capture_names is not None and name not in capture_names and not name.startswith('failure-'):
                return
            path = public / (name + '.png')
            target = w if w is not None and not w.is_closed() else page
            masks = [target.locator('#token')] if target is w else [page.locator('#sessions')]
            target.screenshot(path=str(path), full_page=False, timeout=10000, mask=masks)
            report['screenshots'].append(dict(file=path.name, sha256=sha256(path.read_bytes()).hexdigest()))

        def role(name):
            page.locator('[data-role="' + name + '"]').click()
            expect(page.locator('#status')).to_contain_text('已切换')

        def post(selector, path, status=200, action=None):
            report['current_control'] = dict(selector=selector, path=path)
            boundary.authorize(path, action)
            result = resource.click_post(w, selector, path, status)
            boundary.readonly()
            return result

        def open_case(parent):
            open_from_list(w, parent['goal'])
            assert w.evaluate('preparationId') == parent['preparation_id']

        def verify_step(parent, adapter):
            boundary.authorize('/api/preparations/' + parent['preparation_id'] + '/service-case-plan/commands', 'VERIFY')
            verify(w, adapter)
            boundary.readonly()

        def open_dispatch(parent, dispatch_id):
            w.locator('[data-tab="collaboration"]').click()
            w.locator('#dispatch-list').click()
            # The current CaseStep list deliberately uses its fixed contract
            # title. This fresh zero-business demo has exactly one dispatch;
            # verify its actual identity after the explicit original UI click.
            items = w.locator('#dispatch-items button')
            expect(items).to_have_count(1)
            items.click()
            w.wait_for_function('id=>dispatchView?.dispatch_id===id', arg=dispatch_id)
            assert w.evaluate('dispatchView.preparation_id') == parent['preparation_id']

        def prepare(phase):
            role('enterprise')
            w.locator('[data-tab="service"]').click()
            page.locator('#scenario').select_option(phase)
            w.locator('#prep-catalog').click()
            expect(w.locator('#prep-create')).to_be_visible()
            w.locator('#prep-reviewer').select_option(demo.IDS['specialist'])
            page.locator('#fill-goal').click()
            goal = w.locator('#prep-goal').input_value()
            boundary.intake()
            w.locator('#prep-create button').click()
            settled(w, preparation=True)
            boundary.readonly()
            p = w.evaluate('({preparation_id:preparationId,case_id:preparationView.preparation.case_id,run_id:preparationView.preparation.run_id})')
            p['goal'] = goal
            w.locator('#plan-prepare').click()
            expect(w.locator('#request-intent-form')).to_be_visible()
            page.locator('#fill-request').click()
            post('#request-save', '/api/preparations/' + p['preparation_id'] + '/request-intent')
            settled(w)
            w.locator('#plan-materials').click()
            settled(w, preparation=True)
            if phase == 'again':
                w.locator('#material-reuse-read').click()
                w.wait_for_function('()=>materialReuseView?.items.length===1')
                source = w.evaluate('materialReuseView.items[0].source_evidence_id')
                w.locator('#material-reuse-source').select_option(source)
                w.locator('#material-reuse-preview').click()
                w.wait_for_function('()=>!!materialReuseView?.source_preview')
                w.locator('#material-reuse-purpose').check()
                w.locator('#material-reuse-reason').fill('SYNTHETIC 林岚明确复用本人同用途通用目录')
                post('#material-reuse-confirm', '/api/preparations/' + p['preparation_id'] + '/material-reuse', 201)
                settled(w, preparation=True)
            for fill in (['#fill-need', '#fill-outline'] if phase == 'first' else ['#fill-need']):
                page.locator(fill).click()
                text = w.locator('#prep-text').input_value()
                post('#prep-evidence button', '/api/preparations/' + p['preparation_id'] + '/commands', action='ADD_EVIDENCE')
                settled(w, preparation=True)
                expect(w.locator('#prep-materials')).to_contain_text(text)
            expect(w.locator('#prep-confirm')).to_be_disabled()
            report['expected_refusals'].append(dict(stage=phase, kind='CLIENT_GUARD', reason='unreviewed preparation cannot confirm'))
            role('specialist')
            open_case(p)
            w.locator('#prep-reason').fill('SYNTHETIC 周禾本人审核虚构资料')
            post('#prep-review', '/api/preparations/' + p['preparation_id'] + '/commands', action='REVIEW')
            settled(w, preparation=True)
            role('enterprise')
            open_case(p)
            w.locator('#prep-reason').fill('SYNTHETIC 林岚本人确认已审资料')
            post('#prep-confirm', '/api/preparations/' + p['preparation_id'] + '/commands', action='CONFIRM')
            settled(w, preparation=True)
            p['revision'] = w.evaluate('preparationView.preparation.revision')
            return p

        try:
            report['stage'] = 'SHIPPED_GUIDE'
            response = page.goto(base + '/demo', wait_until='load')
            assert response.status == 200 and response.body() == (ROOT / 'src/parkweave/park_demo_web.html').read_bytes()
            if page_ready is not None:
                page_ready(page, report)
            page.locator('#sessions').set_input_files(dict(name='invalid.json', mimeType='application/json', buffer=b'{}'))
            expect(page.locator('[data-role="enterprise"]')).to_be_disabled()
            expect(page.locator('#status')).to_contain_text('未上传')
            report['expected_refusals'].append(dict(kind='CLIENT_GUARD', reason='invalid synthetic session file rejected without POST'))
            page.locator('#sessions').set_input_files(state / 'sessions.json')
            expect(page.locator('#workspace-open')).to_be_enabled()
            assert page.locator('iframe').count() == 0
            shot('01-fictional-guide')
            with page.expect_popup() as popup:
                page.locator('#workspace-open').click()
            w = popup.value
            w.set_default_timeout(15000)
            w.wait_for_load_state('load')
            assert w.url == base + '/'
            expect(w.locator('#token')).to_be_visible()
            roots = [r for r in report['responses'] if r['path'] in ('/', '/demo')]
            assert len(roots) == 2 and all("frame-ancestors 'none'" in r['content_security_policy'] for r in roots)
            report['window_contract'] = 'EXPLICIT_SAME_ORIGIN_TOP_LEVEL_POPUP_NO_IFRAME_CSP_UNCHANGED'
            report['stage'] = 'FIRST_INTAKE_REVIEW_CONFIRM'
            first = prepare('first')
            report['first'] = first
            open_service_plan(w)
            w.locator('#service-selection-read').click()
            w.wait_for_function('()=>serviceSelectionCatalog!==null&&!serviceSelectionBusy')
            post('#service-selection-generate', '/api/preparations/' + first['preparation_id'] + '/service-selections', 201)
            w.wait_for_function('()=>serviceSelectionView!==null&&!serviceSelectionBusy')
            assert w.evaluate('serviceSelectionView.producer.mode') == 'NO_MODEL'
            w.locator('#service-selection-confirm').check()
            w.locator('#service-plan-reason').fill('SYNTHETIC 林岚明确采纳模拟目录方案')
            post('#service-plan-adopt', '/api/preparations/' + first['preparation_id'] + '/service-case-plan', 201)
            settled(w)
            first['plan_id'] = w.evaluate('servicePlanView.plan_id')
            shot('02-first-adopted-plan')
            report['stage'] = 'FIRST_RESOURCE_AND_P1_P2'
            verify_step(first, 'P1')
            report['resources'] = resource.resource_walk(w, boundary, demo.SCOPES['primary'], first, first['goal'])
            settled(w, preparation=True)
            verify_step(first, 'P2')
            report['stage'] = 'FIRST_DISPATCH_ACCEPT'
            role('specialist')
            open_case(first)
            w.locator('#dispatch-prepare').click()
            expect(w.locator('#dispatch-offer')).to_be_visible()
            w.locator('#dispatch-executor').select_option(demo.IDS['executor'])
            w.locator('#dispatch-offer-reason').fill('SYNTHETIC 周禾明确分派许辰')
            dispatch = post('#dispatch-offer-button', '/api/preparations/' + first['preparation_id'] + '/dispatch', 201)
            settled(w)
            role('executor')
            open_dispatch(first, dispatch['dispatch_id'])
            expect(w.locator('#dispatch-decision')).to_be_visible()
            w.locator('#dispatch-decision-reason').fill('SYNTHETIC 许辰本人接受虚构事项')
            accepted = post('#dispatch-accept', '/api/service-dispatches/' + dispatch['dispatch_id'] + '/commands', action='ACCEPT')
            settled(w)
            first['dispatch_id'], first['receipt_step_id'] = accepted['dispatch_id'], accepted['receipt_step_id']
            role('enterprise')
            open_case(first)
            verify_step(first, 'P3')
            report['stage'] = 'FIRST_MANUAL_RECEIPT_ACK'
            role('executor')
            open_dispatch(first, dispatch['dispatch_id'])
            w.locator('#dispatch-receipt').click()
            expect(w.locator('#receipt-submit')).to_be_visible()
            w.locator('#receipt-text').fill('SYNTHETIC 许辰已整理云杉智造6台虚构设备巡检资料；仅本地演示，无实际履约。')
            w.locator('#receipt-source').fill('SYNTHETIC 青禾园本地虚构办理记录 v1')
            post('#receipt-submit-button', '/api/executor-receipts/' + first['receipt_step_id'] + '/commands', action='SUBMIT')
            settled(w)
            role('enterprise')
            w.locator('[data-tab="collaboration"]').click()
            w.locator('#receipt-list').click()
            receipts = w.locator('#receipt-items button')
            expect(receipts).to_have_count(1)
            receipts.click()
            w.wait_for_function('id=>receiptView?.step.id===id', arg=first['receipt_step_id'])
            expect(w.locator('#receipt-decisions')).to_be_visible()
            w.locator('#receipt-reason').fill('SYNTHETIC 林岚明确核对本次虚构回执')
            post('#receipt-ack', '/api/executor-receipts/' + first['receipt_step_id'] + '/commands', action='ACKNOWLEDGE')
            settled(w)
            assert w.evaluate('receiptView.step.state') == 'LOCAL_ACKNOWLEDGED'
            report['receipt'] = w.evaluate('receiptView')
            shot('03-first-acknowledged-receipt')
            report['stage'] = 'FIRST_P4_P5_AND_DOWNLOAD'
            open_case(first)
            verify_step(first, 'P4')
            open_case(first)
            w.locator('#local-case-prepare').click()
            expect(w.locator('#local-case-detail')).to_be_visible()
            for selector, action in (('#local-case-validate', 'REVALIDATE'), ('#local-case-close', 'CLOSE_LOCAL_RECORD')):
                w.locator('#local-case-reason').fill('SYNTHETIC 林岚本人核对并关闭本地记录')
                post(selector, '/api/preparations/' + first['preparation_id'] + '/local-case/commands', action=action)
                settled(w)
            open_case(first)
            verify_step(first, 'P5')
            w.locator('#goal-results-read').click()
            w.wait_for_function('()=>goalResultView!==null')
            result = w.evaluate('goalResultView')
            assert result['state'] == 'LOCAL_OUTPUTS_VERIFIED' and len(result['results']) == 5
            assert all(x['state'] == 'LOCAL_OUTPUT_VERIFIED' for x in result['results'])
            assert not result['case_goal_completed']
            report['results'] = result
            w.locator('#goal-results-source-read').click()
            expect(w.locator('#goal-results-source')).to_contain_text('NO_MODEL')
            w.locator('#case-record-pack-generate').click()
            expect(w.locator('#case-record-pack-output')).to_be_visible()
            expect(w.locator('#case-record-pack-text')).not_to_have_value('')
            expect(w.locator('#case-record-pack-download')).to_be_enabled()
            with w.expect_download() as downloaded:
                w.locator('#case-record-pack-download').click()
            downloaded.value.save_as(public / 'first-case-record-pack.txt')
            assert first['plan_id'] in (public / 'first-case-record-pack.txt').read_text()
            shot('04-first-five-goals-and-source')
            history = case_history(Store(demo.lifecycle.dsn(state)), first['preparation_id'])
            report['stage'] = 'AGAIN_EXPLICIT_REUSE_REVIEW_CONFIRM'
            again = prepare('again')
            report['second'] = again
            assert again['run_id'] != first['run_id'] and again['case_id'] != first['case_id']
            assert w.evaluate('preparationView.history.some(e=>!!e.payload.material_reuse)')
            shot('05-again-independent-reused-materials')
            report['stage'] = 'AGAIN_EXPLICIT_CANCEL'
            w.locator('#case-cancel-read').click()
            w.wait_for_function('()=>caseCancelView?.can_cancel===true')
            w.locator('#case-cancel-reason').fill('SYNTHETIC 林岚取消新增2台设备事项，首办回执和历史保留')
            w.locator('#case-cancel-confirm').check()
            post('#case-cancel-submit', '/api/preparations/' + again['preparation_id'] + '/case-cancellation')
            w.wait_for_function('()=>preparationView?.case_cancelled===true')
            shot('06-again-cancelled')
            assert case_history(Store(demo.lifecycle.dsn(state)), first['preparation_id']) == history
            report['first_history_unchanged'] = True
            report['stage'] = 'FIRST_READ_AFTER_SECOND_CANCEL'
            open_case(first)
            open_service_plan(w)
            w.locator('#goal-results-read').click()
            w.wait_for_function('()=>goalResultView!==null')
            assert w.evaluate('goalResultView') == result
            w.set_viewport_size(dict(width=390, height=1000))
            w.locator('#goal-results-status').scroll_into_view_if_needed()
            assert w.evaluate('document.documentElement.scrollWidth<=innerWidth')
            shot('07-mobile-first-history-retained')
            boundary.readonly()
            assert not report['violations'] and not report['page_errors']
            assert all(r['status'] in (200, 201, 202) for r in report['responses'] if r['method'] == 'POST')
            with Store(demo.lifecycle.dsn(state)).connect() as conn:
                conn.execute('SET TRANSACTION READ ONLY')
                assert demo.authority(conn) == marker['authority']
                assert not conn.execute('SELECT 1 FROM run_assignments').fetchone()
                assert conn.execute('SELECT state FROM cases WHERE id=%s', (again['case_id'],)).fetchone()['state'] == 'CANCELLED'
            report.update(authority_unchanged=True, run_assignments=0, all_business_writes='REAL_BROWSER_DOM_ONLY',
                JS_business_calls=0, API_business_writes=0, real_browser=True)
            if before_stop is not None:
                before_stop(dict(state=state, config=config, inputs=inputs, input_hashes=before,
                    marker=marker, processes=launched, first=first, second=again,
                    results=result, receipt=report['receipt'], boundary=boundary), w)
        except BaseException:
            report['remaining_write_budget'] = dict(boundary.remaining)
            if w is not None and not w.is_closed():
                try:
                    report['failure_dom'] = w.evaluate("""() => ({
                        preparation_read_state: preparationRead?.state,
                        preparation_read_ready: preparationReadReady(),
                        active_write: !!activeEntryWriteFlow,
                        pending_write_count: entryWriteRequests.size,
                        messages: Object.fromEntries(['prep-read-status','prep-error','case-resource-error',
                            'service-plan-error','dispatch-error','receipt-error','case-cancel-status']
                            .map(id=>[id,document.getElementById(id)?.textContent||'']))})""")
                except BaseException as error:
                    report['failure_dom_error'] = type(error).__name__
            try:
                shot('failure-' + re.sub('[^a-z0-9]+', '-', report['stage'].lower()))
            except BaseException as error:
                report['failure_screenshot_error'] = type(error).__name__
            raise
        finally:
            context.close()
    assert before == {str(p): sha256(p.read_bytes()).hexdigest() for p in inputs}
    report.update(input_files_unchanged=True, owned_services_stopped=not (state / 'data/postmaster.pid').exists())
    assert report['owned_services_stopped']


def write_result(directory, report, secrets):
    serialized = resource.redact(report, secrets)
    raw = (serialized + '\n').encode()
    assert not any(token.encode() in raw or token[:12].encode() in raw for token in secrets)
    other_bytes = sum(p.stat().st_size for p in directory.iterdir() if p.name != 'result.json')
    assert other_bytes + len(raw) <= 8 * 1024 * 1024
    (directory / 'result.json').write_bytes(raw)
    return serialized


def publish_artifacts(public, report, secrets, *, restart=False, started=None):
    serialized = write_result(public, report, secrets)
    files = list(public.iterdir())
    assert len(files) <= 10 and sum(p.stat().st_size for p in files) <= 8 * 1024 * 1024
    text_names = ('result.json', 'first-case-record-pack.txt') + (('restarted-case-record-pack.txt',) if restart else ())
    image_pattern = r'(?:0[1-9]-[a-z-]+|failure-[a-z0-9-]+)\.png' if restart else r'(?:0[1-7]-[a-z-]+|failure-[a-z0-9-]+)\.png'
    for p in files:
        if restart:
            from scripts.fictional_park_restart_browser_once import PUBLIC_FILES
            allowed = p.name in PUBLIC_FILES or re.fullmatch(r'failure-[a-z0-9-]+\.png', p.name)
        else:
            allowed = p.name in text_names or re.fullmatch(image_pattern, p.name)
        assert allowed and not p.is_symlink()
        assert not any(token.encode() in p.read_bytes() or token[:12].encode() in p.read_bytes() for token in secrets)
    if started is not None:
        elapsed = time.monotonic() - started
        report.update(seconds=round(elapsed, 3),
            seconds_scope='through artifact scan; file/summary finalization and absolute deadline checks still follow')
        if elapsed > 350:
            finalization_failure(report, TimeoutError('publication exhausted the absolute-clock final margin'))
        serialized = write_result(public, report, secrets)
    published = public.with_name('parkweave-fictional-browser-evidence')
    public.rename(published)
    if started is not None and time.monotonic() - started > 360:
        finalization_failure(report, TimeoutError('publication crossed absolute 360s deadline'))
        try:
            serialized = write_result(published, report, secrets)
        except BaseException:
            # Preserve our own staged files, but do not expose a stale PASS.
            published.rename(public)
            raise
    return serialized


def finalization_failure(report, error):
    """Keep the business failure, if any, alongside later evidence failures."""
    detail = dict(error_type=type(error).__name__, error=str(error))
    report.setdefault('error_type', detail['error_type'])
    report.setdefault('error', detail['error'])
    report.setdefault('finalization_errors', []).append(detail)
    report['status'] = 'FAIL'


def write_summary(stream, offset, serialized):
    # Replace only this invocation's section, including a previous PASS. The
    # unbuffered descriptor also permits truncation after a failed write.
    stream.truncate(offset)
    raw = ('```json\n' + serialized + '\n```\n').encode()
    assert stream.write(raw) == len(raw)


def finish_report(report, secrets, public, *, restart=False, started=None):
    """No stdout PASS precedes fallible output or the final deadline check."""
    summary, offset = None, None
    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    published = public.with_name('parkweave-fictional-browser-evidence') if public else None

    def deadline():
        elapsed = time.monotonic() - started if started is not None else None
        if elapsed is not None and elapsed > 360:
            raise TimeoutError('finalization crossed absolute 360s deadline')
        return elapsed

    def withdraw():
        # Only our rename can leave candidate absent and published present.
        if public is not None and not public.exists() and published.exists():
            published.rename(public)

    try:
        if summary_path:
            summary = Path(summary_path).open('a+b', buffering=0)
            offset = summary.seek(0, 2)
        observation = dict(report, status='PENDING_FINALIZATION',
            observation_outcome=report['status'],
            terminal_result='result.json and step summary after finalization; process exit is authoritative')
        print(resource.redact(observation, secrets), flush=True)
        elapsed = deadline()
        if started is not None:
            print('FINALIZATION_OUTPUT_CHECKPOINT ' + json.dumps(dict(status='PENDING_FINALIZATION',
                completion_seconds=round(elapsed, 3), limit_seconds=360,
                measurement_scope='output checkpoint; artifact/summary finalization and final deadline check still follow')), flush=True)
        serialized = resource.redact(report, secrets)
        if public is not None:
            serialized = publish_artifacts(public, report, secrets, restart=restart, started=started)
        if summary is not None:
            write_summary(summary, offset, serialized)
        deadline()
        if summary is not None:
            summary.close()
        deadline()
        return 0 if report['status'] == 'PASS' else 1
    except BaseException as error:
        finalization_failure(report, error)
        withdraw()  # Withhold any previously published PASS before recovery IO.
        if summary_path and summary is not None and offset is not None:
            try:
                if summary.closed:
                    summary = Path(summary_path).open('a+b', buffering=0)
                # Clear our entire previous section before attempting FAIL.
                summary.truncate(offset)
                write_summary(summary, offset, resource.redact(report, secrets))
            except BaseException as summary_error:
                finalization_failure(report, summary_error)
                # A partial failure record must not retain the prior PASS.
                try:
                    summary.truncate(offset)
                except BaseException as truncate_error:
                    finalization_failure(report, truncate_error)
        try:
            print(resource.redact(report, secrets), flush=True)
        except BaseException as output_error:
            finalization_failure(report, output_error)
        if public is not None and public.exists():
            try:
                publish_artifacts(public, report, secrets, restart=restart)
            except BaseException as publication_error:
                finalization_failure(report, publication_error)
                withdraw()
        return 1
    finally:
        if summary is not None and not summary.closed:
            summary.close()


def main(*, restart_candidate=False):
    os.umask(0o077)
    report = dict(scope='FICTIONAL_PARK_SANDBOXED_REAL_CHROME_DOM', status='NOT_RUN', stage='HOST_GATE',
        screenshots=[], responses=[], violations=[], page_errors=[], expected_refusals=[],
        formal_source=False, formal_AT35=False, Windows=False, real_model_calls=0, real_browser=False,
        cancel_scope='SECOND_CASE_AFTER_REVIEW_CONFIRM_BEFORE_ADOPT_OR_DISPATCH')
    secrets, public = [], None
    started = time.monotonic()
    try:
        report['source_sha'] = require_hosted(os.environ, run_number='8' if restart_candidate else '4')
        PRIVATE.mkdir(parents=True, mode=0o700, exist_ok=False)
        public = Path(os.environ['RUNNER_TEMP']) / 'parkweave-fictional-browser-candidate'
        public.mkdir(mode=0o700, exist_ok=False)
        report['packages'] = {p: version(p) for p in ('playwright', 'pgserver', 'psycopg', 'fastapi')}
        env = dict(os.environ)
        for key, name in (('XDG_CONFIG_HOME', 'chrome-config'), ('XDG_CACHE_HOME', 'chrome-cache')):
            directory = PRIVATE / name
            directory.mkdir(mode=0o700)
            env[key] = str(directory)
        if restart_candidate:
            from scripts import fictional_park_restart_browser_once as restart
            report.update(scope='FICTIONAL_PARK_COLD_RESTART_CANDIDATE', cold_restart=False,
                proposed_browser_step_seconds=360, proposed_job_seconds=600)
            report['stage'] = 'INSTALLED_CJK_PREFLIGHT'
            env = restart.installed_font_environment(env, PRIVATE / 'installed-fonts', report)
        from playwright.sync_api import sync_playwright
        report['stage'] = 'CHROME_SANDBOX'
        with sync_playwright() as pw:
            with pw.chromium.launch(channel='chrome', headless=True, chromium_sandbox=True,
                                   args=['--enable-automation'], env=env) as browser:
                report['chrome_version'] = browser.version
                report['real_browser'] = True
                resource.verify_sandbox(browser, report)
                if restart_candidate:
                    restart.candidate_flow(browser, report, secrets, public, started)
                    restart.Deadline(started).require(20, 'Chrome/context close and publication')
                else:
                    walk(browser, report, secrets, public)
                if restart_candidate:
                    chrome_close_started = time.monotonic()
        if restart_candidate and time.monotonic() - chrome_close_started > 5:
            raise RuntimeError('Chrome/driver close exceeded its 5s share of context/publication allowance')
        report['status'] = 'PASS'
    except BaseException as error:
        report.update(status='FAIL', error_type=type(error).__name__, error=str(error))
        if hasattr(error, 'server_observation'):
            report['server_failure_observation'] = error.server_observation
    if restart_candidate and time.monotonic() - started > 350:
        finalization_failure(report, TimeoutError('absolute clock exhausted final publication reserve'))
    report['seconds'] = round(time.monotonic() - started, 3)
    return finish_report(report, secrets, public, restart=restart_candidate,
        started=started if restart_candidate else None)


if __name__ == '__main__':
    raise SystemExit(main())
