"""Real Chromium material preparation brief flow in a fresh owned fixture.

Read the private runtime directory from stdin context; never accepts tokens on
argv and never launches PostgreSQL, the API, or the worker itself.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
import argparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--screenshots', type=Path, required=True)
    args = parser.parse_args()
    context = json.load(sys.stdin)
    runtime = Path(context['runtime_directory']).resolve()
    fixture_path = runtime / 'fixture-info.json'
    if not fixture_path.is_file() or fixture_path.is_symlink():
        raise RuntimeError('Owned launcher fixture-info.json is unavailable')
    fixture = json.loads(fixture_path.read_text(encoding='utf-8'))
    tokens = fixture['tokens']
    initial_counts = fixture['environment'].get('initial_business_counts', {})
    expected_empty_tables = ('cases', 'runs', 'preparations', 'run_assignments',
                             'service_dispatches', 'service_receipt_steps', 'service_step_receipts')
    if any(initial_counts.get(name) != 0 for name in expected_empty_tables):
        raise RuntimeError('Owned fresh fixture does not have an empty initial business baseline')
    base_url = context.get('base_url') or f"http://127.0.0.1:{fixture['environment']['port']}"
    if not base_url.startswith('http://127.0.0.1:'):
        raise RuntimeError('Only this owned loopback demo may be opened')
    # Startup metadata alone cannot prove that a retry still has empty business
    # state. Check the existing owner endpoint before any browser writes.
    request = Request(base_url + '/api/preparations',
                      headers={'Authorization': 'Bearer ' + tokens['fixture-a']})
    with urlopen(request, timeout=10) as response:
        live_preparations = json.load(response)
    if live_preparations.get('items') != []:
        raise RuntimeError('Owned demo already contains preparations; a fresh launcher is required')
    args.screenshots.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env['npm_config_cache'] = str(ROOT / '.cache/npm')
    env['PATH'] = '/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:' + env.get('PATH', '')
    socket_directory = Path('/tmp') / ('pwra-' + uuid.uuid4().hex[:8])
    socket_directory.mkdir(parents=True, exist_ok=True)
    env['AGENT_BROWSER_SOCKET_DIR'] = str(socket_directory.resolve())
    env['AGENT_BROWSER_SCREENSHOT_DIR'] = str(args.screenshots.resolve())
    packages = [p for base in (ROOT / '.cache/npm/_npx', Path('/tmp/parkweave-eng073-product-ytp_zhmu/.cache/npm/_npx'))
                for p in base.glob('*/node_modules/agent-browser/package.json')
                if json.loads(p.read_text(encoding='utf-8')).get('version') == '0.38.2']
    if not packages:
        raise RuntimeError('The existing cached agent-browser 0.38.2 package was not found')
    command = ['node', str(sorted(packages)[0].parent / 'bin/agent-browser.js'),
               '--session', 'pw-material-brief-' + uuid.uuid4().hex[:10],
               '--executable-path', '/usr/bin/chromium', '--args', '--no-sandbox']

    def browser(*items: str, stdin: str | None = None) -> str:
        proc = subprocess.run(command + list(items), input=stdin, capture_output=True,
                              text=True, env=env, timeout=40)
        if proc.returncode:
            raise RuntimeError('Cached Chromium command failed: ' + proc.stderr[-1200:])
        return proc.stdout.strip()

    def value(expression: str):
        raw = browser('eval', '(async()=>JSON.stringify(await (' + expression + ')))()')
        parsed = json.loads(raw)
        return json.loads(parsed) if isinstance(parsed, str) else parsed

    def wait(expression: str, predicate, timeout: float = 45):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = value(expression)
            if predicate(result):
                return result
            time.sleep(.15)
        raise AssertionError('Timed out waiting for browser state: ' + expression)

    def click(selector: str):
        value('(()=>{const e=document.querySelector(' + json.dumps(selector) + ');'
              'if(!e||e.disabled||e.closest("[hidden]"))throw Error(' + json.dumps('native click unavailable: ' + selector) + ');'
              'window.runAccessNativeClicks=0;e.addEventListener("click",()=>runAccessNativeClicks++,{once:true});'
              'e.scrollIntoView({block:"center"});return true})()')
        browser('snapshot', '-i')
        browser('click', selector)
        if value('window.runAccessNativeClicks') != 1:
            raise AssertionError('Expected exactly one native click for ' + selector)
        browser('snapshot', '-i')

    def fill(selector: str, text: str):
        browser('fill', selector, text)

    def select(selector: str, text: str):
        browser('select', selector, text)

    def check(selector: str):
        browser('check', selector)

    def write_count(path_part: str, action: str | None = None) -> int:
        path_expr = json.dumps(path_part)
        action_clause = '' if action is None else '&&x.action===' + json.dumps(action)
        return value('ownedRunAccessPosts.filter(x=>x.path.includes(' + path_expr + ')' + action_clause + ').length')

    def wait_for_write(path_part: str, prior_count: int, action: str | None = None):
        return wait('ownedRunAccessPosts.filter(x=>x.path.includes(' + json.dumps(path_part) + ')' +
                    ('' if action is None else '&&x.action===' + json.dumps(action)) + ').length',
                    lambda count: count > prior_count, timeout=30)

    metrics=[]
    browser_opened=False
    try:
        browser('open',base_url);browser_opened=True
        wait('document.readyState',lambda x:x=='complete')
        value("(()=>{window.briefFetch=window.fetch;window.ownedRunAccessPosts=[];window.briefAttempts=[];window.briefProjectionFailure=[];window.failBriefProjection=false;window.fetch=async(path,opts)=>{const r=await briefFetch(path,opts);if(opts?.method==='POST'){let action='';try{action=JSON.parse(opts.body||'{}').action||''}catch(_){};ownedRunAccessPosts.push({path:String(path),action,actual_server_status:r.status});if(String(path).endsWith('/material-draft')){const key=new Headers(opts.headers||{}).get('Idempotency-Key')||'';const raw=new TextEncoder().encode(key+'\\n'+String(opts.body||''));const h=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw))).map(x=>x.toString(16).padStart(2,'0')).join('');const result=await r.clone().json();briefAttempts.push({actual_server_status:r.status,request_fingerprint_sha256:h,evidence_id:result.material_draft?.evidence_id});if(r.ok&&briefAttempts.length===1)failBriefProjection=true;}}else if(failBriefProjection&&/^\\/api\\/preparations\\/[^/?]+$/.test(String(path))){failBriefProjection=false;briefProjectionFailure.push({actual_server_status:r.status,client_status:503});return new Response(JSON.stringify({detail:'client projection failure after actual brief commit'}),{status:503,headers:{'Content-Type':'application/json'}});}return r};return true})()")
        def switch(role_id: str):
            if role_id not in tokens:
                raise RuntimeError('Requested demo role is missing from private fixture info')
            browser('eval', '--stdin', stdin='document.querySelector("#token").value=' +
                    json.dumps(tokens[role_id]) + ';document.querySelector("#token").dispatchEvent(new Event("input"));'
                    'document.querySelector("#token").dispatchEvent(new Event("change"));undefined')
            wait('document.querySelector("#run-access-open").hidden', lambda hidden: hidden is True or hidden is False)
            # An enabled status is expected for the current explicit fixture role.
            wait('document.querySelector("#run-access-open").hidden', lambda hidden: hidden is False)

        def capture(stage: str):
            for width, height in ((1200, 900), (390, 844), (320, 844)):
                browser('set', 'viewport', str(width), str(height))
                dimensions = value('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
                if dimensions['scroll'] > dimensions['width']:
                    raise AssertionError(f'horizontal overflow at {stage}: {dimensions}')
                metrics.append({'stage': stage, **dimensions})
                browser('snapshot', '-i')
                before_screenshots = set(args.screenshots.glob('*.png'))
                browser('screenshot')
                created = sorted(set(args.screenshots.glob('*.png')) - before_screenshots,
                                 key=lambda path: path.stat().st_mtime_ns)
                if not created:
                    raise AssertionError(f'Chromium did not create a screenshot for {stage} at width {width}')
                created[-1].replace(args.screenshots / f'{stage}-{width}.png')
            browser('set', 'viewport', '1200', '900')

        def open_prep(goal: str):
            click('[data-tab="collaboration"]')
            click('#prep-list')
            wait('prepRole', lambda x: x in ('enterprise_operator', 'park_specialist'))
            wait('document.querySelector("#prep-items").textContent', lambda x: goal in x)
            index = value('Array.from(document.querySelectorAll("#prep-items button")).findIndex(b=>b.textContent.includes('
                          + json.dumps(goal) + '))+1')
            if index < 1:
                raise AssertionError('Fresh preparation is not in the current role list')
            click('#prep-items button:nth-child(' + str(index) + ')')
            return wait('preparationView', lambda x: isinstance(x, dict) and x['preparation']['goal'] == goal)

        goal = 'SYNTHETIC 企业咨询资料整理 ' + uuid.uuid4().hex[:8]
        # Fresh owner case: create via the product UI, then submit actual synthetic
        # facts/materials and obtain the original reviewer/owner preparation gates.
        switch('fixture-a')
        click('[data-tab="service"]')
        click('#prep-catalog')
        wait('prepCatalog', lambda x: isinstance(x, dict) and bool(x.get('services')))
        fill('#prep-goal', goal)
        click('#prep-create button')
        prep = wait('preparationView', lambda x: isinstance(x, dict) and x['preparation']['goal'] == goal, timeout=60)
        prep_id = prep['preparation']['id']
        case_id = prep['preparation']['case_id']
        run_id = prep['preparation']['run_id']

        wait('caseFactView&& !document.querySelector("#case-fact-source-entry").hidden',lambda x:x is True)
        click('#case-fact-source-entry summary')
        now = datetime.now(timezone.utc)
        valid_from = (now - timedelta(minutes=5)).isoformat().replace('+00:00', 'Z')
        valid_until = (now + timedelta(days=30)).isoformat().replace('+00:00', 'Z')
        for field, text in [('region', 'synthetic region'), ('employees', '19'), ('service_need', 'synthetic planning')]:
            select('#case-fact-source-field', field)
            fill('#case-fact-source-value', text)
            fill('#case-fact-source-ref', 'MATERIAL-BRIEF-' + field)
            fill('#case-fact-source-version', '1')
            fill('#case-fact-source-excerpt', 'Synthetic only: ' + text)
            fill('#case-fact-source-from', valid_from)
            fill('#case-fact-source-until', valid_until)
            check('#case-fact-source-purpose')
            before_fact = write_count('/api/facts')
            click('#case-fact-source-save')
            wait_for_write('/api/facts', before_fact)
            wait('caseFactPending', lambda x: x is None, timeout=25)
            click('#case-fact-read')
            wait('caseFactView.source_sha256', lambda x: isinstance(x, str) and len(x) == 64)
        check('#case-fact-declare-purpose')
        fill('#case-fact-declare-reason', 'Synthetic facts for this new Case only; no qualification claim.')
        before_declare = write_count('/fact-clarifications/declare')
        click('#case-fact-declare')
        wait_for_write('/fact-clarifications/declare', before_declare)
        wait('caseFactView.enabled', lambda x: x is True)
        choices = value('caseFactView.fields.map(r=>({field:r.field,id:(r.evidence.find(e=>e.applicable)||{}).id}))')
        if len(choices) != 3 or any(not row['id'] for row in choices):
            raise AssertionError('Three current synthetic fact sources are required')
        for row in choices:
            select('select[data-fact-field="' + row['field'] + '"]', row['id'])
        check('#case-fact-purpose')
        fill('#case-fact-confirm-reason', 'Explicit source selection for this synthetic Case; still requires manual review.')
        before_fact_confirm = write_count('/fact-clarifications/confirm')
        click('#case-fact-confirm')
        wait_for_write('/fact-clarifications/confirm', before_fact_confirm)
        wait('caseFactView.state', lambda x: x in ('CURRENT', 'USER_SELECTED_FOR_CASE'))

        click('#material-draft-read')
        candidate=wait('materialDraftView',lambda x:isinstance(x,dict) and x.get('state')=='DRAFT')
        if not all(t in candidate['draft']['text'] for t in ('synthetic region','19','synthetic planning',goal)):
            raise AssertionError('Actual generated brief must contain current request and selected values')
        if candidate['reviewer_id']!='prep-specialist-fixture-a':raise AssertionError('Exact original reviewer required')
        capture('owner-brief-preview')
        check('#material-draft-share');click('#material-draft-save')
        wait('prepCommandPending?.state',lambda x:x=='UNKNOWN')
        negative=value('({draftHidden:!document.querySelector("#material-draft-content").textContent,checklistHidden:!document.querySelector("#material-draft-checklist").textContent,recipientHidden:!document.querySelector("#material-draft-recipient").textContent,materialsHidden:!document.querySelector("#prep-materials").textContent,refreshBlocked:document.querySelector("#prep-refresh").disabled,assessmentBlocked:document.querySelector("#readiness-assess").disabled,manualBlocked:document.querySelector("#prep-evidence button").disabled,newBriefBlocked:document.querySelector("#material-draft-save").disabled,factsBlocked:document.querySelector("#case-fact-source-save").disabled})')
        if not all(negative.values()):raise AssertionError('Unknown operation must hide old projection and block other writes')
        capture('owner-brief-result-unknown')
        click('#prep-command-retry')
        wait('prepCommandPending',lambda x:x is None)
        pack=wait('preparationView',lambda x:isinstance(x,dict) and any(m.get('material_draft_source') for m in x['current_materials']))
        material=next(m for m in pack['current_materials'] if m.get('material_draft_source'))
        if material['text']!=candidate['draft']['text'] or not material['material_draft_source']['source_current'] or material['version']!=1:raise AssertionError('Exact one-version saved brief required')
        attempts=value('briefAttempts')
        if len(attempts)!=2 or any(a['actual_server_status']!=201 for a in attempts) or len({a['request_fingerprint_sha256'] for a in attempts})!=1 or len({a['evidence_id'] for a in attempts})!=1:raise AssertionError('Two identical native retries must produce one same brief')
        capture('owner-saved-unverified-brief')
        before_revision=value('preparationView.preparation.revision');before_evidence=write_count('/api/preparations/','ADD_EVIDENCE')
        select('#prep-slot','material_outline');fill('#prep-text','SYNTHETIC 企业明确提供的咨询问题目录；真实政策证明要求待合法来源确认')
        select('#prep-source-kind','USER_STATEMENT');fill('#prep-source-label','Synthetic owner directory v1');click('#prep-evidence button')
        wait_for_write('/api/preparations/',before_evidence,'ADD_EVIDENCE');wait('preparationView.preparation.revision',lambda n:isinstance(n,int) and n>before_revision)
        switch('prep-specialist-fixture-a');pack=open_prep(goal)
        if candidate['draft']['text'] not in value('document.querySelector("#prep-materials").textContent'):raise AssertionError('Original reviewer must read actual shared brief text')
        capture('assigned-reviewer-current-materials')
        fill('#prep-reason','Independently checked the exact current user-selected brief and owner directory; truth and qualification unverified');click('#prep-review')
        wait('preparationView.preparation.state',lambda x:x=='REVIEWED')
        switch('fixture-a');pack=open_prep(goal);fill('#prep-reason','Owner confirms exact independently reviewed synthetic material versions, not fulfillment');click('#prep-confirm')
        pack=wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['state']=='LOCAL_CONFIRMED')
        capture('owner-reviewed-pack-confirmed')
        if pack['qualification']!='NOT_EVALUATED' or pack['external_acceptance']!='NOT_SUBMITTED' or pack['offline_fulfillment']!='NO_EVIDENCE':raise AssertionError('Business completion boundaries required')
        report=dict(status='PASS',scope='USER_SELECTED_SYNTHETIC_PREPARATION_BRIEF_ONLY',case_id=case_id,run_id=run_id,preparation_id=prep_id,evidence_id=material['id'],text_sha256=material['source_sha256'],actual_text=candidate['draft']['text'],successful_brief_posts=2,brief_effect_count=1,request_fingerprints_equal=True,unknown_projection_checks=negative,projection_failure=value('briefProjectionFailure'),viewport_checks=metrics,reviewed_material_versions=[dict(slot=m['slot'],version=m['version'],sha256=m['source_sha256']) for m in pack['current_materials']],qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE',live_model_calls=0,policy_requirements_generated=False)
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'status':'PASS','scope':report['scope'],'report':str(args.report),'screenshots':len(metrics)}))
    finally:
        if browser_opened:
            try: browser('close')
            except Exception: pass
        shutil.rmtree(socket_directory,ignore_errors=True)

if __name__=='__main__':main()
