"""Cold recovery candidate; workflow activation awaits review, not user permission.

--describe is read-only. --candidate requires the exact public hosted run8 gate.
No workflow is changed here. Healthy timing estimates do not guarantee PASS.
"""
from hashlib import sha256
from html import escape
from datetime import datetime, timezone
import base64
import json
from pathlib import Path
import re
import subprocess
import time
import zlib
from urllib.parse import urlsplit

from scripts import fictional_park_browser_once as original

CAPTURE_NAMES = frozenset(('01-fictional-guide', '03-first-acknowledged-receipt',
    '06-again-cancelled', '07-mobile-first-history-retained'))
PUBLIC_FILES = frozenset({name + '.png' for name in CAPTURE_NAMES} | {
    '08-restarted-first-record.png', '09-restarted-second-cancelled.png',
    'first-case-record-pack.txt', 'restarted-case-record-pack.txt', 'result.json'})
DESIGN = dict(status='FONT_FALLBACK_SET_CANDIDATE_NOT_EXECUTED', workflow_changed=False,
    proposed_browser_step_seconds=360, proposed_job_seconds=600, measured_walk_seconds=72.912,
    measured_job_seconds=115, first_scenario_and_stop_seconds=180,
    first_scenario_work_seconds=130, first_context_close_reserved_seconds=10, first_stop_reserved_seconds=40,
    server_start_allowance_seconds=50, server_stop_allowance_seconds=40,
    recovery_reads_allowance_seconds=60, context_publication_seconds=20, margin_seconds=10,
    second_phase_admission_reservation_seconds=180,
    budget_sum='180 first + 50 restart + 60 recovery reads + 40 second stop + 20 context/publication + 10 margin = 360',
    job_sum='180 existing dependency cap + 360 browser candidate + 60 checkout/artifact = 600',
    budget_qualification='bounded failure windows, not a guarantee when every operation reaches its timeout',
    planned_fresh_setup_calls=1, planned_setup_calls_during_recovery=0, recovery_business_POST_budget=0,
    GET_budget_shared_with_first_walk=800, artifact_max_files=10,
    artifact_max_bytes=8388608, selected_initial_screenshots=sorted(CAPTURE_NAMES),
    font_policy='Unchanged UI codepoints covered by trusted system fonts plus exactly verified approved original Noto file; private fontconfig only',
    runner_font_status='Run7 verified pinned font,683-codepoint chains and guide glyphs; cold startup failed with generic OSError; bounded run8 retry pending',
    references=dict(fontconfig='https://www.freedesktop.org/software/fontconfig/fontconfig-user.html',
        runner_image='https://github.com/actions/runner-images/blob/ubuntu24/20261012.334/images/ubuntu/Ubuntu2404-Readme.md'),
    uninstalled_font_candidate=dict(source='https://github.com/notofonts/noto-cjk/blob/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf',
        license='SIL Open Font License 1.1', license_source='https://github.com/notofonts/noto-cjk/blob/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Sans/LICENSE',
        downloaded=False, installed=False, new_license_accepted=True),
    pending_before_execution=['This execution is gated to exact hosted run8/attempt1; no automatic retry',
        'only the explicitly approved pinned font and original license may be staged privately; no system installation'])


class BudgetRefused(RuntimeError):
    pass


class Deadline:
    """One absolute clock, including the first walk; never restart the clock."""
    def __init__(self, started):
        self.end = started + 360
        self.phase_end = started + 130

    def require(self, seconds, phase):
        remaining = self.end - time.monotonic()
        if remaining < seconds:
            raise BudgetRefused(f'{phase}: {seconds}s reservation required; {remaining:.3f}s remains')

    def stage_require(self, seconds, phase):
        remaining = self.phase_end - time.monotonic()
        if remaining < seconds:
            raise BudgetRefused(f'{phase}: full {seconds}s wait needs stage time; {remaining:.3f}s remains')

    def recovery_phase(self):
        self.phase_started = time.monotonic()
        self.phase_end = min(self.phase_started + 60, self.end - 70)

    def ui_timeout(self, milliseconds=15000):
        self.stage_require(milliseconds / 1000, 'original UI wait')
        return milliseconds  # Never shrink the original 15s/30s wait to fit.


def ui_codepoints(text):
    return {ord(c) for c in text if 0x3400 <= ord(c) <= 0x9fff or
        0x3000 <= ord(c) <= 0x303f or 0xff00 <= ord(c) <= 0xffef}


def charset_coverage(charset, codepoints):
    intervals = []
    for item in charset.split():
        ends = item.split('-')
        if len(ends) not in (1, 2) or any(not re.fullmatch('[0-9a-fA-F]{1,6}', x) for x in ends):
            raise ValueError('unrecognized fontconfig charset')
        first, last = int(ends[0], 16), int(ends[-1], 16)
        if not 0 <= first <= last <= 0x10ffff:
            raise ValueError('invalid fontconfig range')
        intervals.append((first, last))
    return {point for point in codepoints if any(a <= point <= b for a, b in intervals)}


def covers(charset, codepoints):
    return bool(codepoints) and charset_coverage(charset, codepoints) == set(codepoints)


FONT_FORMAT = '%{file}\t%{index}\t%{family}\t%{postscriptname}\t%{charset}\n'
FONT_DIAGNOSTIC_LIMIT = 1024 * 1024  # Within the unchanged total 8MiB publication limit.
FONT_DIAGNOSTIC_RAW_LIMIT = 16 * 1024 * 1024


def font_candidates(text, points, approved=None):
    """Keep every row and rejection reason, including Unicode family names."""
    rows = []
    for raw in text.splitlines():
        row = dict(raw=raw, eligible=False, exclusion_reason=None, covered_codepoints=[])
        try:
            file, index, families, postscript, charset = raw.split('\t')
            row.update(file=file, index=index, families=families.split(','),
                postscript_names=postscript.split(',') if postscript else [])
            covered = charset_coverage(charset, points)
            row['covered_codepoints'] = sorted(covered)
            path = Path(file).resolve(strict=True)
            exact = (approved is not None and str(path) == approved['path'] and index == '0'
                and row['postscript_names'] == [approved['postscript_name']])
            if not exact and not any(path.is_relative_to(p) for p in (Path('/usr/share/fonts'), Path('/usr/local/share/fonts'))):
                raise ValueError('outside trusted installed-system font roots')
            if not path.is_file() or not index.isdecimal():
                raise ValueError('not a regular font file or invalid face index')
            if not families or any(not f or len(f) > 160 or any(ord(c) < 32 for c in f) for f in row['families']):
                raise ValueError('invalid family metadata; Unicode names are allowed')
            row.update(file=str(path), index=int(index), eligible=True,
                source='EXACT_APPROVED_OFFICIAL_FONT' if exact else 'INSTALLED_SYSTEM_FONT')
        except (ValueError, OSError) as error:
            row['exclusion_reason'] = str(error)
        row.update(covered_count=len(row['covered_codepoints']),
            missing_codepoints=sorted(points - set(row['covered_codepoints'])))
        rows.append(row)
    return rows


def fontconfig_read(argv, environment, directory, diagnostics, name):
    """Preserve bounded public diagnostics and original private command bytes."""
    record = diagnostics['commands'][name] = dict(argv=argv)
    try:
        result = subprocess.run(argv, env=environment, capture_output=True, timeout=3)
        stdout, stderr = result.stdout, result.stderr
        record['returncode'] = result.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or b'', error.stderr or b''
        record['timed_out'] = True
    for key, raw in (('stdout', stdout), ('stderr', stderr)):
        path = directory / (name + '.' + key)
        path.write_bytes(raw)
        record[key + '_private_file'] = str(path)
        record[key + '_bytes'] = len(raw)
        record[key + '_sha256'] = sha256(raw).hexdigest()
    record['raw_public_complete'] = all(len(raw) <= 2 * 1024 * 1024 for raw in (stdout, stderr))
    invalid_utf8 = False
    for key, raw in (('stdout', stdout), ('stderr', stderr)):
        if len(raw) <= 2 * 1024 * 1024:
            try:
                record[key] = raw.decode('utf-8')
            except UnicodeDecodeError:
                record[key + '_base64'] = base64.b64encode(raw).decode('ascii')
                invalid_utf8 = True
    if any(len(raw) > 2 * 1024 * 1024 for raw in (stdout, stderr)):
        raise RuntimeError('fontconfig output exceeds 2MiB; complete bytes retained privately, not claimed published')
    if record.get('timed_out') or record['returncode'] != 0:
        raise RuntimeError('fontconfig command failed; original output retained')
    if invalid_utf8:
        raise RuntimeError('fontconfig emitted invalid UTF8; both original byte streams retained without loss')
    return record['stdout']


def preserve_font_diagnostics(directory, diagnostics, selected):
    raw = (json.dumps(diagnostics, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
    path = directory / 'font-diagnostics.json'
    path.write_bytes(raw)
    packed = base64.b64encode(zlib.compress(raw)).decode('ascii')
    fits = len(packed) <= FONT_DIAGNOSTIC_LIMIT and len(raw) <= FONT_DIAGNOSTIC_RAW_LIMIT
    selected['diagnostics'] = dict(encoding='base64(zlib(UTF8 JSON))',
        uncompressed_bytes=len(raw), sha256=sha256(raw).hexdigest(), private_original=str(path),
        published_complete=fits and all(c.get('raw_public_complete', False) for c in diagnostics['commands'].values()))
    if not fits:
        selected['status'] = 'FONT_DIAGNOSTIC_PUBLICATION_LIMIT'
        raise RuntimeError('font diagnostics exceed 1MiB packed/16MiB decoded allowance; complete original retained privately only')
    selected['diagnostics']['data'] = packed


def unpack_font_diagnostics(selected, *, require_complete=True):
    meta = selected['diagnostics']
    assert not require_complete or meta['published_complete']
    assert 0 <= meta['uncompressed_bytes'] <= FONT_DIAGNOSTIC_RAW_LIMIT
    decoder = zlib.decompressobj()
    raw = decoder.decompress(base64.b64decode(meta['data'], validate=True), meta['uncompressed_bytes'] + 1)
    assert decoder.eof and not decoder.unused_data and len(raw) == meta['uncompressed_bytes']
    assert sha256(raw).hexdigest() == meta['sha256']
    return json.loads(raw)


def installed_font_environment(environment, directory, report, *, extra_text=""):
    """Read system fonts and the exact earlier approved staging; no downloads here."""
    directory.mkdir(mode=0o700, exist_ok=False)
    font_env = dict(environment, XDG_CACHE_HOME=str(directory))
    text = ''.join((original.ROOT / f).read_text() for f in
        ('src/parkweave/web.html', 'src/parkweave/park_demo_web.html'))
    points = ui_codepoints(text + extra_text)
    selected = report['installed_CJK_font'] = dict(status='FONT_SET_PREFLIGHT_PENDING',
        coverage_mode='INSTALLED_SYSTEM_FALLBACK_SET', required_codepoints=sorted(points),
        downloads=0, installs=0, rendering_observed=False)
    diagnostics = dict(required_codepoints=sorted(points), commands={})
    try:
        from scripts.fictional_park_font_once import verified_font
        approved = verified_font(required=environment.get('RUNNER_ENVIRONMENT') == 'github-hosted')
        font_dir = ''
        if approved is not None:
            report['approved_official_font'] = approved
            selected['approved_font_staged_before_browser'] = True
            font_dir = '<dir>' + escape(approved['directory']) + '</dir>'
        config = directory / 'fonts.conf'
        prefix = '<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">' + \
            '<fontconfig><include>/etc/fonts/fonts.conf</include>' + font_dir
        config.write_text(prefix + '</fontconfig>')
        font_env['FONTCONFIG_FILE'] = str(config)
        diagnostics['initial_config_xml'] = config.read_text()
        inventory = fontconfig_read(['fc-list', '-f', FONT_FORMAT], font_env, directory, diagnostics, 'inventory')
        rows = diagnostics['candidates'] = font_candidates(inventory, points, approved)
        eligible = [row for row in rows if row['eligible']]
        union = set().union(*(set(row['covered_codepoints']) for row in eligible))
        missing = selected['missing_codepoints'] = sorted(points - union)
        selected.update(candidate_count=len(rows), eligible_count=len(eligible), union_covered_count=len(union))
        if missing:
            selected['status'] = 'NO_INSTALLED_CJK_SET_COVERAGE'
            raise RuntimeError('installed system font union misses required UI codepoints; no setup or download allowed')
        remaining, chosen = set(points), []
        while remaining:
            row = min(eligible, key=lambda r: (-len(remaining.intersection(r['covered_codepoints'])),
                r['families'][0] != 'Noto Sans CJK SC', 'Regular' not in r['file'], r['file'], r['index']))
            chosen.append(row)
            remaining.difference_update(row['covered_codepoints'])
        families = list(dict.fromkeys(row['families'][0] for row in chosen))
        aliases = ''.join('<alias><family>' + generic + '</family><prefer>' +
            ''.join('<family>' + escape(family) + '</family>' for family in families) +
            '</prefer></alias>' for generic in ('system-ui', 'sans-serif'))
        config.write_text(prefix + aliases + '</fontconfig>')
        diagnostics['config_xml'] = config.read_text()
        resolved_env = dict(environment, FONTCONFIG_FILE=str(config), XDG_CACHE_HOME=str(directory))
        selected['preferred_families'] = families
        identities = {(r['file'], r['index'], tuple(r['postscript_names'])) for r in eligible}
        selected['resolved'] = {}
        for generic in ('system-ui', 'sans-serif'):
            output = fontconfig_read(['fc-match', '-s', '-f', FONT_FORMAT, generic + ':lang=zh-cn'],
                resolved_env, directory, diagnostics, generic)
            resolved = diagnostics[generic] = font_candidates(output, points, approved)
            for row in resolved:
                if row['eligible'] and (row['file'], row['index'], tuple(row['postscript_names'])) not in identities:
                    row.update(eligible=False, exclusion_reason='resolved face absent from captured trusted inventory')
            resolved_union = set().union(*(set(r['covered_codepoints']) for r in resolved if r['eligible']))
            missing = sorted(points - resolved_union)
            selected['resolved'][generic] = dict(covered_count=len(resolved_union), missing_codepoints=missing)
            if missing:
                selected['status'] = 'FONTCONFIG_RESOLVED_SET_MISSING_UI'
                raise RuntimeError('actual fontconfig generic fallback misses required UI codepoints')
        selected['status'] = 'INSTALLED_CHARSET_COVERS_UI'
        return resolved_env
    except BaseException as error:
        selected['preflight_error'] = dict(type=type(error).__name__, message=str(error))
        if selected['status'] == 'FONT_SET_PREFLIGHT_PENDING':
            selected['status'] = 'FONT_SET_PREFLIGHT_FAILED'
        raise
    finally:
        preserve_font_diagnostics(directory, diagnostics, selected)


def verify_rendered_font(page, report):
    """Read original visible guide nodes; never add glyph probes or alter pixels."""
    selected = report['installed_CJK_font']
    selected['rendering_observed'] = False
    stop = time.monotonic() + 5
    candidates = unpack_font_diagnostics(selected)['candidates']
    nodes = page.evaluate("""() => {
        const found=new Map(), walk=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
        const path=e=>e.id?'#'+CSS.escape(e.id):e===document.body?'body':path(e.parentElement)+' > '+e.tagName.toLowerCase()+':nth-child('+([...e.parentElement.children].indexOf(e)+1)+')';
        for(let n; n=walk.nextNode();){
            if(!/[\\u3400-\\u9fff\\u3000-\\u303f\\uff00-\\uffef]/u.test(n.data))continue;
            const e=n.parentElement,s=getComputedStyle(e),r=document.createRange();r.selectNodeContents(n);
            if(s.visibility!=='visible'||s.opacity==='0'||!Array.from(r.getClientRects()).some(b=>b.width&&b.height&&b.bottom>0&&b.right>0&&b.top<innerHeight&&b.left<innerWidth))continue;
            const key=path(e);found.set(key,(found.get(key)||'')+n.data);
        }return [...found].map(([selector,text])=>({selector,text}));} """)
    observations = selected['visible_node_font_usage'] = []
    selected['rendering_observation_scope'] = ('guide viewport text-node parents at page_ready only; CDP node-level font usage '
        'and charset union, not glyph-to-codepoint attribution or all683 pixel acceptance; review original screenshot separately')
    assert 0 < len(nodes) <= 256
    session = page.context.new_cdp_session(page)
    file_hashes = {}
    try:
        session.send('DOM.enable'); session.send('CSS.enable')
        root = session.send('DOM.getDocument')['root']['nodeId']
        for row in nodes:
            if time.monotonic() > stop:
                raise BudgetRefused('guide font usage inspection exceeded its5s share of unchanged first stage')
            points = ui_codepoints(row['text'])
            node = session.send('DOM.querySelector', dict(nodeId=root, selector=row['selector']))['nodeId']
            fonts = session.send('CSS.getPlatformFontsForNode', dict(nodeId=node))['fonts']
            observed = dict(selector=row['selector'], text_sha256=sha256(row['text'].encode()).hexdigest(),
                required_codepoints=sorted(points), fonts=fonts, matched_faces=[], invalid_sources=[])
            observations.append(observed)
            union = set()
            for font in fonts:
                if font['glyphCount'] <= 0:
                    continue
                matches = [r for r in candidates if font['postScriptName'] in r.get('postscript_names', ())]
                if font['isCustomFont'] or len(matches) != 1 or not matches[0]['eligible']:
                    observed['invalid_sources'].append(dict(postscript_name=font['postScriptName'],
                        custom=font['isCustomFont'], candidate_count=len(matches)))
                    continue
                face = matches[0]
                union.update(face['covered_codepoints'])
                if face['file'] not in file_hashes:
                    file_hashes[face['file']] = sha256(Path(face['file']).read_bytes()).hexdigest()
                observed['matched_faces'].append(dict(file=face['file'], index=face['index'],
                    postscript_name=font['postScriptName'], sha256=file_hashes[face['file']]))
            observed['missing_codepoints'] = sorted(points - union)
            assert not observed['invalid_sources'], 'unknown, custom or ambiguous actual font face'
            assert not observed['missing_codepoints'], 'actual participating font union misses visible node CJK'
        if time.monotonic() > stop:
            raise BudgetRefused('guide font usage inspection exceeded its5s share of unchanged first stage')
    finally:
        session.detach()
    if time.monotonic() > stop:
        raise BudgetRefused('guide font usage inspection including detach exceeded its5s share')
    selected['rendering_observed'] = True


def readonly_store(state):
    from psycopg.conninfo import make_conninfo
    from parkweave.store import Store
    from scripts import ordinary_synthetic_demo as demo
    return Store(make_conninfo(demo.lifecycle.dsn(state),
        options='-c default_transaction_read_only=on -c statement_timeout=500 -c lock_timeout=200'))


def checkpoint(details, page, budget):
    """Called while the first owned server is alive, after both original Cases."""
    from service_release_acceptance_support import case_history
    saved = dict(details)
    budget.stage_require(30, 'two Case history projections before first stop')
    saved['history'] = {key: case_history(readonly_store(details['state']), details[key]['preparation_id'])
        for key in ('first', 'second')}
    assert details['receipt']['assignment_valid_until']
    saved['reuse'] = [e['payload']['material_reuse'] for e in saved['history']['second']['preparation_events']
        if e['payload'].get('material_reuse')]
    assert len(saved['reuse']) == 1
    assert page.evaluate('goalResultView') == details['results']
    tokens = json.loads((details['state'] / 'sessions.json').read_text())
    saved['roles'] = ReadUI(page, budget).role_views(tokens, details['first'])
    assert saved['roles']['enterprise']['receipt']['assignment_valid_until'] == details['receipt']['assignment_valid_until']
    return saved


def candidate_flow(browser, report, secrets, public, started):
    """One setup/walk, actual stop, same-instance restart and new-context reads."""
    if report.get('installed_CJK_font', {}).get('status') != 'INSTALLED_CHARSET_COVERS_UI':
        raise RuntimeError('installed-font preflight required before fresh setup')
    saved, budget = {}, Deadline(started)

    def capture(details, page):
        report['stage'] = 'FIRST_COLD_CHECKPOINT'
        saved.update(checkpoint(details, page, budget))

    original.walk(browser, report, secrets, public, before_stop=capture, capture_names=CAPTURE_NAMES,
        page_ready=verify_rendered_font)
    report['first_stage_seconds'] = round(time.monotonic() - started, 3)
    report['stage'] = 'FIRST_CONFIRMED_STOP'
    # walk returned only after its context closed, child exited, PG stopped and
    # the original API port refused connections. Do not reset this clock.
    if time.monotonic() - started > 180:
        raise BudgetRefused('first scenario/checkpoint/stop exceeded its 180s stage')
    budget.require(180, 'second-stage admission after confirmed stop')
    boundary = saved['boundary']
    recover_retained(browser, saved, boundary, report, secrets, public, budget)
    report['cold_restart'] = True


class ReadUI:
    def __init__(self, page, budget):
        self.page, self.budget = page, budget

    def click(self, selector):
        self.page.locator(selector).click(timeout=self.budget.ui_timeout())

    def wait(self, expression, arg=None, milliseconds=15000):
        self.page.wait_for_function(expression, arg=arg, timeout=self.budget.ui_timeout(milliseconds))

    def login(self, token):
        self.page.locator('#token').fill(token, timeout=self.budget.ui_timeout())
        self.page.locator('#token').dispatch_event('change', timeout=self.budget.ui_timeout())

    def receipt(self, parent):
        from playwright.sync_api import expect
        self.click('[data-tab="collaboration"]'); self.click('#receipt-list')
        items = self.page.locator('#receipt-items button')
        expect(items).to_have_count(1, timeout=self.budget.ui_timeout())
        items.click(timeout=self.budget.ui_timeout())
        self.wait('id=>receiptView?.step.id===id', parent['receipt_step_id'])
        view = self.page.evaluate('receiptView')
        assert all(view['step'][field] == parent[field] for field in ('preparation_id', 'case_id', 'run_id'))
        return view

    def dispatch(self, parent):
        from playwright.sync_api import expect
        self.click('[data-tab="collaboration"]'); self.click('#dispatch-list')
        items = self.page.locator('#dispatch-items button')
        expect(items).to_have_count(1, timeout=self.budget.ui_timeout())
        items.click(timeout=self.budget.ui_timeout())
        self.wait('id=>dispatchView?.dispatch_id===id', parent['dispatch_id'])
        view = self.page.evaluate('dispatchView')
        assert view['preparation_id'] == parent['preparation_id']
        return view

    def role_views(self, tokens, parent):
        views = {}
        for role in ('enterprise', 'executor'):
            self.login(tokens[role])
            views[role] = dict(dispatch=self.dispatch(parent), receipt=self.receipt(parent))
        self.login(tokens['enterprise'])
        return views

    def preparation(self, parent):
        from playwright.sync_api import expect
        self.click('[data-tab="collaboration"]'); self.click('#prep-list')
        item = self.page.locator('#prep-items button').filter(has_text=parent['goal'])
        expect(item).to_have_count(1, timeout=self.budget.ui_timeout())
        item.click(timeout=self.budget.ui_timeout())
        self.wait('id=>preparationId===id&&preparationView!==null&&preparationReadReady()', parent['preparation_id'], 30000)
        assert self.page.evaluate('preparationView.preparation.case_id') == parent['case_id']
        assert self.page.evaluate('preparationView.preparation.run_id') == parent['run_id']


def recover_retained(browser, saved, boundary, report, secrets, public, budget):
    """All recovery business requests are reads against the original instance."""
    from playwright.sync_api import expect
    from service_release_acceptance_support import case_history
    from test_ordinary_synthetic_demo import server
    from scripts import ordinary_synthetic_demo as demo

    # This check is AFTER original.walk returned: first context/services stopped.
    budget.require(DESIGN['second_phase_admission_reservation_seconds'], 'cold server restart')
    state, config = saved['state'], saved['config']
    assert not (state / 'data/postmaster.pid').exists() and not (state / 'stop-unconfirmed').exists()
    assert saved['input_hashes'] == {str(p): sha256(p.read_bytes()).hexdigest() for p in saved['inputs']}
    tokens = json.loads((state / 'sessions.json').read_text())
    assert set(tokens.values()).issubset(set(secrets))  # use exactly the original six private sessions
    boundary.readonly()
    port = urlsplit(saved['processes']['url']).port
    report['stage'] = 'COLD_RESTART_SAME_STATE'
    restart_started = time.monotonic()
    with server(state, original.PRIVATE / 'cold-server', selected_port=port, local_demo_config=config) as (api, launched):
        report['cold_start_seconds'] = round(time.monotonic() - restart_started, 3)
        if time.monotonic() - restart_started > 50:
            raise BudgetRefused('cold start exceeded 50s allowance')
        budget.recovery_phase()
        report['cold_processes'] = launched
        assert all(launched[k] != saved['processes'][k] for k in ('api_pid', 'worker_pid', 'postgres_pid'))
        original_deadline = saved['receipt']['assignment_valid_until']
        if datetime.now(timezone.utc) >= datetime.fromisoformat(original_deadline):
            report['restart_deadline_outcome'] = 'ORIGINAL_DEADLINE_EXPIRED_NO_RENEWAL'
            raise RuntimeError('original assignment deadline expired; do not renew or retry business writes')
        report['stage'] = 'COLD_NEW_BROWSER_CONTEXT'
        context = browser.new_context(service_workers='block', accept_downloads=True,
            viewport=dict(width=1440, height=1100))
        context.route('**/*', boundary.route)  # same GET counter; no new POST authorization
        context.on('page', lambda p: p.on('pageerror', lambda error: report['page_errors'].append(str(error))))
        context.on('response', lambda r: report['responses'].append(dict(stage='COLD_READ_ONLY',
            method=r.request.method, path=urlsplit(r.url).path, status=r.status)))
        page = context.new_page(); ui = ReadUI(page, budget)

        def shot(name):
            budget.stage_require(10, 'masked recovery screenshot')
            path = public / (name + '.png')
            page.screenshot(path=str(path), full_page=False, timeout=10000, mask=[page.locator('#token')])
            report['screenshots'].append(dict(file=path.name, sha256=sha256(path.read_bytes()).hexdigest()))

        try:
            report['stage'] = 'COLD_READ_FIRST_RESULTS_AND_TXT'
            assert not context.cookies()
            page.goto(str(api.base_url), timeout=budget.ui_timeout(30000))
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
            shot('08-restarted-first-record')
            report['stage'] = 'COLD_READ_ORIGINAL_ROLES'
            # Freeze and compare the complete same-role original UI views. Do
            # not omit permissions, dependency flags or the original deadline.
            roles = ui.role_views(tokens, saved['first'])
            assert roles == saved['roles']
            assert roles['executor']['receipt']['role'] == 'service_executor'
            assert roles['executor']['receipt']['assignment_valid_until'] == original_deadline
            report['stage'] = 'COLD_READ_SECOND_CANCEL_AND_REUSE'
            ui.preparation(saved['second'])
            assert page.evaluate('preparationView.case_cancelled') is True
            reuse = page.evaluate('preparationView.history.filter(e=>e.payload.material_reuse).map(e=>e.payload.material_reuse)')
            assert reuse == saved['reuse']
            shot('09-restarted-second-cancelled')
            # Second Case never ADOPTed: do not invent a plan or treat its 404 as success.
            for key in ('first', 'second'):
                budget.stage_require(15, 'read-only Case history projection')
                assert case_history(readonly_store(state), saved[key]['preparation_id']) == saved['history'][key]
            with readonly_store(state).connect() as connection:
                assert demo.authority(connection) == saved['marker']['authority']
                assert not connection.execute('SELECT 1 FROM run_assignments').fetchone()
            boundary.readonly()
            assert not report['violations'] and not report['page_errors']
            budget.stage_require(0, 'cold-read stage completion')
            report['cold_read_seconds'] = round(time.monotonic() - budget.phase_started, 3)
        except BaseException:
            try:
                # Failure evidence uses the reserved file slot and is masked.
                path = public / 'failure-cold-recovery.png'
                page.screenshot(path=str(path), full_page=False, timeout=10000, mask=[page.locator('#token')])
                report['screenshots'].append(dict(file=path.name, sha256=sha256(path.read_bytes()).hexdigest()))
            except BaseException as error:
                report['cold_failure_screenshot_error'] = type(error).__name__
            raise
        finally:
            report['stage_before_cold_stop'] = report['stage']
            stop_started = time.monotonic()
            context.close()
            report['cold_context_close_seconds'] = round(time.monotonic() - stop_started, 3)
    report['cold_context_and_stop_seconds'] = round(time.monotonic() - stop_started, 3)
    if report['cold_context_close_seconds'] > 5 or time.monotonic() - stop_started > 45:
        raise BudgetRefused('cold context/owned stop exceeded 5s/40s allocated close/stop envelope')
    assert not (state / 'data/postmaster.pid').exists()
    assert saved['input_hashes'] == {str(p): sha256(p.read_bytes()).hexdigest() for p in saved['inputs']}
    report['restart_read_only'] = dict(input_files_unchanged=True, new_context=True,
        extra_business_POSTs=0, history_scope='existing two-Case case_history projection only',
        first_goalResultView_equal=True, first_TXT_bytes_equal=True,
        compared_views='complete enterprise/executor dispatchView and receiptView; no omitted fields',
        complete_executor_permission_or_dispatch_view_equality_claimed=True,
        snapshot_scope='only those views plus declared Case history projection, not all DB tables')
    report['stage'] = 'COLD_RECOVERY_CONFIRMED_STOP'


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--describe', action='store_true')
    mode.add_argument('--candidate', action='store_true', help='exact public hosted run8/attempt1 only; no retry')
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(DESIGN, ensure_ascii=False, indent=2))
    else:
        raise SystemExit(original.main(restart_candidate=True))
