"""Review-only cold recovery draft. --describe never starts services or Chrome.

The existing workflow is deliberately unchanged. The current server helper's
worst time allowances do not fit after the measured walk in a 180s step. No CI
entry is provided until that timing contract is reviewed and closed.
"""
from hashlib import sha256
from html import escape
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit

from scripts import fictional_park_browser_once as original

CAPTURE_NAMES = frozenset(('01-fictional-guide', '03-first-acknowledged-receipt',
    '06-again-cancelled', '07-mobile-first-history-retained'))
DESIGN = dict(status='DRAFT_NOT_READY_FOR_CI', workflow_changed=False,
    browser_step_seconds=180, job_seconds=420, measured_walk_seconds=72.912,
    server_start_allowance_seconds=50, server_stop_allowance_seconds=40,
    recovery_reads_allowance_seconds=30, publication_allowance_seconds=10,
    remaining_after_measured_walk_seconds=107.088,
    minimum_second_phase_reservation_seconds=130,
    remaining_timing_gap='22.912s plus browser context close/serialization allowances not yet bounded',
    planned_fresh_setup_calls=1, planned_setup_calls_during_recovery=0, recovery_business_POST_budget=0,
    GET_budget_shared_with_first_walk=800, artifact_max_files=10,
    artifact_max_bytes=8388608, selected_initial_screenshots=sorted(CAPTURE_NAMES),
    font_policy='Only already installed system fonts covering actual UI CJK codepoints; otherwise block before setup',
    runner_font_status='NOT_OBSERVED: previous hosted instance ended; image inventory is not fc-list evidence',
    references=dict(fontconfig='https://www.freedesktop.org/software/fontconfig/fontconfig-user.html',
        runner_image='https://github.com/actions/runner-images/blob/ubuntu24/20261012.334/images/ubuntu/Ubuntu2404-Readme.md'),
    uninstalled_font_candidate=dict(source='https://github.com/notofonts/noto-cjk/tree/main/Sans',
        license='SIL Open Font License 1.1', license_source='https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE',
        downloaded=False, installed=False, new_license_accepted=False),
    pending_before_execution=['close the absolute timeout and cleanup/publication envelope',
        'connect preflight returned FONTCONFIG_FILE to actual Chrome environment',
        'wire final recovery result, fixed screenshots and bounded credential-scanned publication',
        'freeze cold-before executor permission/dispatch view if broader equality is required'])


class BudgetRefused(RuntimeError):
    pass


class Deadline:
    """One absolute clock, including the first walk; never restart the clock."""
    def __init__(self, started):
        self.end = started + 180

    def require(self, seconds, phase):
        remaining = self.end - time.monotonic()
        if remaining < seconds:
            raise BudgetRefused(f'{phase}: {seconds}s reservation required; {remaining:.3f}s remains')

    def ui_timeout(self):
        # Reserve the existing 40s stop and 10s publication even on UI failure.
        remaining = self.end - time.monotonic() - 50
        if remaining <= 0:
            raise BudgetRefused('recovery UI deadline reached; retain cleanup reservation')
        return max(1, min(2500, int(remaining * 1000)))


def covers(charset, codepoints):
    intervals = []
    for item in charset.split():
        ends = item.split('-')
        if len(ends) not in (1, 2) or any(not re.fullmatch('[0-9a-fA-F]{1,6}', x) for x in ends):
            raise ValueError('unrecognized fontconfig charset')
        first, last = int(ends[0], 16), int(ends[-1], 16)
        if not 0 <= first <= last <= 0x10ffff:
            raise ValueError('invalid fontconfig range')
        intervals.append((first, last))
    return bool(codepoints) and all(any(a <= point <= b for a, b in intervals) for point in codepoints)


def installed_font_environment(environment, directory, report):
    """Run before launching Chrome or setup. No downloads, installs or font copy."""
    directory.mkdir(mode=0o700, exist_ok=False)
    font_env = dict(environment, XDG_CACHE_HOME=str(directory))
    result = subprocess.run(['fc-list', ':lang=zh-cn', '-f',
        '%{file}\t%{index}\t%{family}\t%{charset}\n'], env=font_env,
        capture_output=True, text=True, timeout=3, check=True)
    if len(result.stdout.encode()) > 2 * 1024 * 1024:
        raise RuntimeError('font inventory exceeds bound')
    text = ''.join((original.ROOT / f).read_text() for f in
        ('src/parkweave/web.html', 'src/parkweave/park_demo_web.html'))
    points = {ord(c) for c in text if 0x3400 <= ord(c) <= 0x9fff or
        0x3000 <= ord(c) <= 0x303f or 0xff00 <= ord(c) <= 0xffef}
    choices = []
    for line in result.stdout.splitlines():
        fields = line.split('\t')
        if len(fields) != 4:
            raise RuntimeError('unrecognized installed-font inventory')
        file, index, families, charset = fields
        path = Path(file).resolve(strict=True)
        if not any(path.is_relative_to(p) for p in (Path('/usr/share/fonts'), Path('/usr/local/share/fonts'))):
            continue
        family = families.split(',')[0]
        if index.isdecimal() and re.fullmatch(r'[A-Za-z0-9 _-]{1,80}', family) and covers(charset, points):
            choices.append((family != 'Noto Sans CJK SC', 'Regular' not in path.name, family, path, int(index)))
    if not choices:
        report['installed_CJK_font'] = dict(status='NO_INSTALLED_CJK_COVERAGE', downloads=0)
        raise RuntimeError('no installed system font covers shipped UI CJK; no setup or download allowed')
    _, _, family, path, index = sorted(choices)[0]
    config = directory / 'fonts.conf'
    aliases = ''.join('<alias><family>' + generic + '</family><prefer><family>' +
        escape(family) + '</family></prefer></alias>' for generic in ('system-ui', 'sans-serif'))
    config.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">'
        '<fontconfig><include>/etc/fonts/fonts.conf</include>' + aliases + '</fontconfig>')
    report['installed_CJK_font'] = dict(status='INSTALLED_CHARSET_COVERS_UI', family=family,
        file=str(path), index=index, sha256=sha256(path.read_bytes()).hexdigest(),
        required_codepoints=len(points), downloads=0, heading_font_observed=False,
        rendering_observation_scope='h1 node only; not whole-page or all-codepoint visual acceptance')
    return dict(environment, FONTCONFIG_FILE=str(config), XDG_CACHE_HOME=str(directory))


def verify_rendered_font(page, report):
    """Inspect actual Chrome glyph usage, never replace screenshot pixels."""
    selected = report['installed_CJK_font']
    assert any(0x3400 <= ord(c) <= 0x9fff for c in page.locator('h1').inner_text())
    session = page.context.new_cdp_session(page)
    try:
        session.send('DOM.enable'); session.send('CSS.enable')
        root = session.send('DOM.getDocument')['root']['nodeId']
        node = session.send('DOM.querySelector', dict(nodeId=root, selector='h1'))['nodeId']
        fonts = session.send('CSS.getPlatformFontsForNode', dict(nodeId=node))['fonts']
        assert any(f['familyName'] == selected['family'] and f['glyphCount'] > 0 for f in fonts)
        selected.update(heading_font_observed=True, observed_fonts=fonts)
    finally:
        session.detach()


def readonly_store(state):
    from psycopg.conninfo import make_conninfo
    from parkweave.store import Store
    from scripts import ordinary_synthetic_demo as demo
    return Store(make_conninfo(demo.lifecycle.dsn(state),
        options='-c default_transaction_read_only=on -c statement_timeout=500 -c lock_timeout=200'))


def checkpoint(details, page):
    """Called while the first owned server is alive, after both original Cases."""
    from service_release_acceptance_support import case_history
    saved = dict(details)
    saved['history'] = {key: case_history(readonly_store(details['state']), details[key]['preparation_id'])
        for key in ('first', 'second')}
    assert details['receipt']['assignment_valid_until']
    saved['reuse'] = [e['payload']['material_reuse'] for e in saved['history']['second']['preparation_events']
        if e['payload'].get('material_reuse')]
    assert len(saved['reuse']) == 1
    assert page.evaluate('goalResultView') == details['results']
    return saved


def draft_flow(browser, report, secrets, public, started):
    """Future caller must preflight fonts and use the returned Chrome env.

    Deliberately not connected to main/workflow. The current budget reservation
    may refuse after the first stop; that is a failure, never restart acceptance.
    """
    if report.get('installed_CJK_font', {}).get('status') != 'INSTALLED_CHARSET_COVERS_UI':
        raise RuntimeError('installed-font preflight required before fresh setup')
    saved = {}

    def capture(details, page):
        verify_rendered_font(page, report)
        saved.update(checkpoint(details, page))

    original.walk(browser, report, secrets, public, before_stop=capture, capture_names=CAPTURE_NAMES)
    # The future caller must carry the original Boundary, not create/reset one.
    boundary = saved['boundary']
    recover_retained(browser, saved, boundary, report, secrets, public, Deadline(started))


class ReadUI:
    def __init__(self, page, budget):
        self.page, self.budget = page, budget

    def click(self, selector):
        self.page.locator(selector).click(timeout=self.budget.ui_timeout())

    def wait(self, expression, arg=None):
        self.page.wait_for_function(expression, arg=arg, timeout=self.budget.ui_timeout())

    def preparation(self, parent):
        from playwright.sync_api import expect
        self.click('[data-tab="collaboration"]'); self.click('#prep-list')
        item = self.page.locator('#prep-items button').filter(has_text=parent['goal'])
        expect(item).to_have_count(1, timeout=self.budget.ui_timeout())
        item.click(timeout=self.budget.ui_timeout())
        self.wait('id=>preparationId===id&&preparationView!==null&&preparationReadReady()', parent['preparation_id'])
        assert self.page.evaluate('preparationView.preparation.case_id') == parent['case_id']
        assert self.page.evaluate('preparationView.preparation.run_id') == parent['run_id']


def recover_retained(browser, saved, boundary, report, secrets, public, budget):
    """Review draft: the reservation currently refuses the measured 3m window."""
    from playwright.sync_api import expect
    from service_release_acceptance_support import case_history
    from test_ordinary_synthetic_demo import server
    from scripts import ordinary_synthetic_demo as demo

    # This check is AFTER original.walk returned: first context/services stopped.
    budget.require(DESIGN['minimum_second_phase_reservation_seconds'], 'cold server restart')
    state, config = saved['state'], saved['config']
    assert not (state / 'data/postmaster.pid').exists() and not (state / 'stop-unconfirmed').exists()
    assert saved['input_hashes'] == {str(p): sha256(p.read_bytes()).hexdigest() for p in saved['inputs']}
    tokens = json.loads((state / 'sessions.json').read_text())
    assert set(tokens.values()).issubset(set(secrets))  # use exactly the original six private sessions
    boundary.readonly()
    port = urlsplit(saved['processes']['url']).port
    with server(state, original.PRIVATE / 'cold-server', selected_port=port, local_demo_config=config) as (api, launched):
        assert all(launched[k] != saved['processes'][k] for k in ('api_pid', 'worker_pid', 'postgres_pid'))
        original_deadline = saved['receipt']['assignment_valid_until']
        if datetime.now(timezone.utc) >= datetime.fromisoformat(original_deadline):
            report['restart_deadline_outcome'] = 'ORIGINAL_DEADLINE_EXPIRED_NO_RENEWAL'
            raise RuntimeError('original assignment deadline expired; do not renew or retry business writes')
        context = browser.new_context(service_workers='block', accept_downloads=True,
            viewport=dict(width=1440, height=1100))
        context.route('**/*', boundary.route)  # same GET counter; no new POST authorization
        context.on('page', lambda p: p.on('pageerror', lambda error: report['page_errors'].append(str(error))))
        context.on('response', lambda r: report['responses'].append(dict(stage='COLD_READ_ONLY',
            method=r.request.method, path=urlsplit(r.url).path, status=r.status)))
        page = context.new_page(); ui = ReadUI(page, budget)
        try:
            assert not context.cookies()
            page.goto(str(api.base_url), timeout=budget.ui_timeout())
            assert page.locator('#token').input_value() == ''
            assert page.evaluate('localStorage.length===0&&sessionStorage.length===0')
            page.locator('#token').fill(tokens['enterprise'], timeout=budget.ui_timeout())
            page.locator('#token').dispatch_event('change', timeout=budget.ui_timeout())
            ui.preparation(saved['first']); ui.click('#service-plan-prepare')
            ui.wait('()=>servicePlanView!==null&&!servicePlanPending')
            ui.click('#goal-results-read'); ui.wait('()=>goalResultView!==null')
            assert page.evaluate('goalResultView') == saved['results']
            ui.click('#case-record-pack-generate')
            expect(page.locator('#case-record-pack-download')).to_be_enabled(timeout=budget.ui_timeout())
            with page.expect_download(timeout=budget.ui_timeout()) as downloaded:
                ui.click('#case-record-pack-download')
            downloaded.value.save_as(public / 'restarted-case-record-pack.txt')
            assert (public / 'restarted-case-record-pack.txt').read_bytes() == (public / 'first-case-record-pack.txt').read_bytes()
            ui.click('[data-tab="collaboration"]'); ui.click('#receipt-list')
            items = page.locator('#receipt-items button')
            expect(items).to_have_count(1, timeout=budget.ui_timeout()); items.click(timeout=budget.ui_timeout())
            ui.wait('id=>receiptView?.step.id===id', saved['first']['receipt_step_id'])
            # Keep all dependency/permission/deadline fields: natural expiry must fail, never renew.
            assert page.evaluate('receiptView') == saved['receipt']
            page.locator('#token').fill(tokens['executor'], timeout=budget.ui_timeout())
            page.locator('#token').dispatch_event('change', timeout=budget.ui_timeout())
            ui.click('[data-tab="collaboration"]'); ui.click('#receipt-list')
            items = page.locator('#receipt-items button')
            expect(items).to_have_count(1, timeout=budget.ui_timeout()); items.click(timeout=budget.ui_timeout())
            ui.wait('id=>receiptView?.step.id===id', saved['first']['receipt_step_id'])
            executor_view = page.evaluate('receiptView')
            assert executor_view['role'] == 'service_executor'
            assert executor_view['assignment_valid_until'] == original_deadline
            assert executor_view['step'] == saved['receipt']['step']
            assert executor_view['current_receipt'] == saved['receipt']['current_receipt']
            page.locator('#token').fill(tokens['enterprise'], timeout=budget.ui_timeout())
            page.locator('#token').dispatch_event('change', timeout=budget.ui_timeout())
            ui.preparation(saved['second'])
            assert page.evaluate('preparationView.case_cancelled') is True
            reuse = page.evaluate('preparationView.history.filter(e=>e.payload.material_reuse).map(e=>e.payload.material_reuse)')
            assert reuse == saved['reuse']
            # Second Case never ADOPTed: do not invent a plan or treat its 404 as success.
            for key in ('first', 'second'):
                budget.require(55, 'read-only history projection and final cleanup')
                assert case_history(readonly_store(state), saved[key]['preparation_id']) == saved['history'][key]
            with readonly_store(state).connect() as connection:
                assert demo.authority(connection) == saved['marker']['authority']
                assert not connection.execute('SELECT 1 FROM run_assignments').fetchone()
            boundary.readonly()
            assert not report['violations'] and not report['page_errors']
        finally:
            context.close()
    assert not (state / 'data/postmaster.pid').exists()
    assert saved['input_hashes'] == {str(p): sha256(p.read_bytes()).hexdigest() for p in saved['inputs']}
    report['restart_read_only'] = dict(input_files_unchanged=True, new_context=True,
        extra_business_POSTs=0, history_scope='existing two-Case case_history projection only',
        first_goalResultView_equal=True, first_TXT_bytes_equal=True,
        executor_compared_fields=['role', 'step', 'current_receipt', 'assignment_valid_until'],
        complete_executor_permission_or_dispatch_view_equality_claimed=False)


if __name__ == '__main__':
    # No executable CI entry: not even --run can launch this review draft.
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--describe', action='store_true', required=True)
    parser.parse_args()
    print(json.dumps(DESIGN, ensure_ascii=False, indent=2))
