"""Real Chromium UI flow for the opt-in fresh isolated Run-access demo.

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
               '--session', 'pw-run-access-' + uuid.uuid4().hex[:10],
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

    metrics = []
    observed_posts = []
    browser_opened = False
    try:
        browser('open', base_url)
        browser_opened = True
        wait('document.readyState', lambda x: x == 'complete')
        # Measure only API writes after browser startup. Headers/tokens are never
        # recorded, and body values are reduced to action names only.
        def install_network_tap(inject_approve: bool):
            value("(()=>{window.ownedRunAccessFetch=window.fetch;window.ownedRunAccessPosts=[];window.ownedRunAccessReads=[];window.runAccessApproveProjectionInjection=[];window.localExecutionProjection=[];window.localExecutionAttempts=[];window.failNextLocalExecutionProjection=false;window.injectProjectionPendingAfterRealCommit=" + ("true" if inject_approve else "false") + ";window.fetch=async(path,opts)=>{"
              "const response=await ownedRunAccessFetch(path,opts);let exposed=response;if(opts?.method&&opts.method!=='GET'){let action='';try{const parsed=JSON.parse(opts.body||'{}');action=parsed.action||((String(path).includes('/execute-local'))?'EXECUTE_LOCAL':'')}catch(_){if(String(path).includes('/execute-local'))action='EXECUTE_LOCAL'};"
              "if(String(path).includes('/execute-local')){const key=new Headers(opts.headers||{}).get('Idempotency-Key')||'';const body=String(opts.body||'');const bytes=new TextEncoder().encode(key+'\\n'+body);const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');let execution_id=null;try{execution_id=(await response.clone().json()).local_execution?.record?.execution_id||null}catch(_){}window.localExecutionAttempts.push({actual_server_status:response.status,request_fingerprint_sha256:digest,execution_id});if(response.ok&&window.localExecutionAttempts.length===1)window.failNextLocalExecutionProjection=true;}"
              "if(String(path).includes('/access/commands')&&action==='APPROVE'){const key=new Headers(opts.headers||{}).get('Idempotency-Key')||'';const body=String(opts.body||'');const bytes=new TextEncoder().encode(key+'\\n'+body);const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');"
              "const inject=window.injectProjectionPendingAfterRealCommit;window.runAccessApproveProjectionInjection.push({actual_server_status:response.status,client_status:inject?409:response.status,request_fingerprint_sha256:digest});"
              "if(inject){window.injectProjectionPendingAfterRealCommit=false;exposed=new Response(JSON.stringify({decision_committed:true,projection_pending:true}),{status:409,headers:{'Content-Type':'application/json'}});}}"
              "window.ownedRunAccessPosts.push({path:String(path),action,actual_server_status:response.status,client_status:exposed.status});}else if((!opts?.method||opts.method==='GET')&&window.failNextLocalExecutionProjection&&/^\\/api\\/executor-receipts\\/[^/?]+$/.test(String(path))){window.failNextLocalExecutionProjection=false;window.localExecutionProjection.push({path:String(path),actual_server_status:response.status,client_status:503});exposed=new Response(JSON.stringify({detail:'client-side projection failure injection after actual commit'}),{status:503,headers:{'Content-Type':'application/json'}});}if(!opts?.method||opts.method==='GET')ownedRunAccessReads.push({path:String(path),actual_server_status:response.status,client_status:exposed.status});return exposed};return true})()")

        install_network_tap(True)

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

        goal = 'SYNTHETIC single Run access cold start ' + uuid.uuid4().hex[:8]
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

        click('#case-fact-source-entry summary')
        now = datetime.now(timezone.utc)
        valid_from = (now - timedelta(minutes=5)).isoformat().replace('+00:00', 'Z')
        valid_until = (now + timedelta(days=30)).isoformat().replace('+00:00', 'Z')
        for field, text in [('region', 'synthetic region'), ('employees', '19'), ('service_need', 'synthetic planning')]:
            select('#case-fact-source-field', field)
            fill('#case-fact-source-value', text)
            fill('#case-fact-source-ref', 'RUN-ACCESS-' + field)
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

        for slot, text in [('need_summary', 'Synthetic need summary'), ('material_outline', 'Synthetic material outline')]:
            before_revision = value('preparationView.preparation.revision')
            before_evidence = write_count('/api/preparations/', 'ADD_EVIDENCE')
            select('#prep-slot', slot)
            fill('#prep-text', text)
            select('#prep-source-kind', 'USER_STATEMENT')
            fill('#prep-source-label', 'Synthetic owner material v1')
            click('#prep-evidence button')
            wait_for_write('/api/preparations/', before_evidence, 'ADD_EVIDENCE')
            wait('preparationView.preparation.revision', lambda n: isinstance(n, int) and n > before_revision)
        switch('prep-specialist-fixture-a')
        prep = open_prep(goal)
        fill('#prep-reason', 'Manual review of current synthetic materials; no source truth or qualification claim.')
        click('#prep-review')
        wait('preparationView.preparation.state', lambda x: x == 'REVIEWED')
        switch('fixture-a')
        prep = open_prep(goal)
        fill('#prep-reason', 'Confirm local synthetic preparation only; no external fulfillment.')
        click('#prep-confirm')
        wait('preparationView.preparation.state', lambda x: x == 'LOCAL_CONFIRMED')
        prep = value('preparationView')
        if (prep['preparation']['id'], prep['preparation']['case_id'], prep['preparation']['run_id']) != (prep_id, case_id, run_id):
            raise AssertionError('Case, Run, and preparation identity changed during the flow')
        if prep.get('qualification') != 'NOT_EVALUATED':
            raise AssertionError('Qualification must remain NOT_EVALUATED')

        # Owner loads the exact Case/Run from the read-only Case path and requests
        # a specific existing executor with an explicit bounded UTC interval.
        click('#plan-prepare')
        wait('planView', lambda x: isinstance(x, dict) and x.get('preparation_id') == prep_id)
        click('#case-path-read')
        wait('casePathView', lambda x: isinstance(x, dict) and x.get('run_id') == run_id)
        owner_btn = value('!document.querySelector("#case-path-result button")?.disabled')
        if owner_btn is not True:
            raise AssertionError('Owner Case-path access entry is unavailable')
        click('#case-path-result button')
        wait('runAccessView', lambda x: isinstance(x, dict) and x.get('scope', {}).get('run_id') == run_id)
        if value('runAccessView.actual_run_access') is not False:
            raise AssertionError('No Run access may pre-exist the explicit request')
        executor_id = 'receipt-executor-fixture-a'
        if not value('Array.from(document.querySelector("#run-access-target").options).some(o=>o.value==="' + executor_id + '")'):
            raise AssertionError('Expected existing same-tenant READ executor missing')
        start = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat().replace('+00:00', 'Z')
        end = (datetime.now(timezone.utc) + timedelta(minutes=55)).isoformat().replace('+00:00', 'Z')
        select('#run-access-target', executor_id)
        fill('#run-access-valid-from', start)
        fill('#run-access-valid-until', end)
        fill('#run-access-reason', 'Explicit owner request for this exact synthetic Run only.')
        click('#run-access-request button')
        request_view = wait('runAccessView', lambda x: isinstance(x, dict) and x.get('state') == 'REQUESTED', timeout=20)
        if request_view.get('actual_run_access') is not False:
            raise AssertionError('A request must not create access before independent approval')
        capture('owner-request-pending')

        # Reviewer enters the exact Run ID manually and approves only the same
        # requested interval. The existing preparation review action is distinct.
        switch('prep-specialist-fixture-a')
        click('#run-access-open')
        fill('#run-access-id', run_id)
        click('#run-access-read')
        approver = wait('runAccessView', lambda x: isinstance(x, dict) and x.get('state') == 'REQUESTED')
        if approver.get('role') != 'park_specialist' or approver.get('can_approve') is not True:
            raise AssertionError('Approval must require the explicit configured approver flag')
        if not value('document.querySelector("#run-access-decision").hidden===false'):
            raise AssertionError('Explicit Run decision controls should be visible to approver')
        fill('#run-access-approved-from', start)
        fill('#run-access-approved-until', end)
        fill('#run-access-decision-reason', 'Independent explicit approval limited to requested Run and interval.')
        click('#run-access-approve')
        wait('runAccessPending?.stage', lambda x: x == 'UNKNOWN', timeout=20)
        injected = value('runAccessApproveProjectionInjection.slice()')
        if len(injected) != 1 or injected[0]['actual_server_status'] != 200 or injected[0]['client_status'] != 409:
            raise AssertionError('Projection-pending UI case must follow one actual committed server approval, then inject only a negative client acknowledgement')
        if '原请求正文与编号' not in value('document.querySelector("#run-access-error").textContent'):
            raise AssertionError('Projection-pending view did not preserve and explain the original request')
        capture('approver-projection-pending-retry')
        lease_timeout_ui = value('(()=>{const p=runAccessPending;if(!p||p.stage!=="UNKNOWN")throw Error("missing uncertain command");expireRunAccessLease({...p.context});return {private_view_cleared:runAccessView===null,pending_stage:runAccessPending?.stage,retry_visible:!document.querySelector("#run-access-retry").hidden}})()')
        if lease_timeout_ui != {'private_view_cleared': True, 'pending_stage': 'UNKNOWN', 'retry_visible': True}:
            raise AssertionError('Counterfactual client-side lease timeout must clear the private projection while preserving exact retry')
        click('#run-access-retry')
        approved = wait('runAccessView', lambda x: isinstance(x, dict) and x.get('state') == 'APPROVED', timeout=20)
        if approved.get('actual_run_access') is not True or approved.get('projection_state') != 'APPLIED':
            raise AssertionError('Approval needs its real managed assignment projection; status alone is insufficient')
        injected = value('runAccessApproveProjectionInjection.slice()')
        if len(injected) != 2 or injected[1]['actual_server_status'] != 200 or injected[1]['client_status'] != 200 or injected[0]['request_fingerprint_sha256'] != injected[1]['request_fingerprint_sha256']:
            raise AssertionError('The retry must reach the real server with the exact original idempotency key and body')
        if sum(event.get('action') == 'APPROVE' for event in approved.get('history', [])) != 1:
            raise AssertionError('The committed approval retry must produce one auditable approval event')
        capture('approver-approved-applied')

        # Original product business flow: specialist offer -> executor accepts and
        # submits receipt -> owner acknowledges, all against the newly authorized Run.
        switch('prep-specialist-fixture-a')
        open_prep(goal)
        click('#dispatch-prepare')
        dispatch = wait('dispatchView', lambda x: isinstance(x, dict) and x.get('preparation_id') == prep_id)
        if not value('Array.from(document.querySelector("#dispatch-executor").options).some(o=>o.value==="' + executor_id + '")'):
            raise AssertionError('The explicit managed access projection did not expose this existing executor to the original dispatch path')
        select('#dispatch-executor', executor_id)
        fill('#dispatch-offer-reason', 'Explicit original Run dispatch after current access approval.')
        click('#dispatch-offer-button')
        dispatch = wait('dispatchView', lambda x: isinstance(x, dict) and x.get('current_offer', {}).get('state') == 'OFFERED')

        switch(executor_id)
        click('[data-tab="collaboration"]')
        click('#dispatch-list')
        wait('document.querySelector("#dispatch-items").textContent', lambda x: goal in x)
        offer_index = value('Array.from(document.querySelectorAll("#dispatch-items button")).findIndex(b=>b.textContent.includes(' + json.dumps(goal) + '))+1')
        if offer_index < 1:
            raise AssertionError('Executor cannot see the explicitly offered Run in the existing dispatch list')
        click('#dispatch-items button:nth-child(' + str(offer_index) + ')')
        wait('dispatchView.current_offer.state', lambda x: x == 'OFFERED')
        fill('#dispatch-decision-reason', 'Executor explicitly accepts this exact synthetic dispatch after access approval.')
        click('#dispatch-accept')
        dispatch = wait('dispatchView', lambda x: isinstance(x, dict) and x.get('current_offer', {}).get('state') == 'ACCEPTED')
        receipt_step_id = dispatch.get('receipt_step_id')
        if not receipt_step_id:
            raise AssertionError('Accepted dispatch did not expose its receipt step')
        switch(executor_id)
        click('[data-tab="collaboration"]')
        click('#run-access-open')
        fill('#run-access-id', run_id)
        click('#run-access-read')
        active_view = wait('runAccessView', lambda x: isinstance(x, dict) and x.get('scope', {}).get('run_id') == run_id)
        if active_view.get('actual_run_access') is not True or active_view.get('projection_state') != 'APPLIED':
            raise AssertionError('Executor did not receive current actual Run access after approval')
        fill('#run', run_id)
        click('#refresh')
        wait('document.querySelector("#page-feedback").textContent', lambda x: bool(x))
        active_read = value('ownedRunAccessReads.filter(x=>x.path==="/api/runs/'+run_id+'").slice(-1)[0] || null')
        if not active_read or active_read['actual_server_status'] != 200 or active_read['client_status'] != 200:
            raise AssertionError('Original Run read must return actual and client HTTP 200 for the approved executor')
        capture('executor-access-active')
        click('#dispatch-list')
        wait('document.querySelector("#dispatch-items").textContent', lambda x: bool(x))
        offer_index = value('Array.from(document.querySelectorAll("#dispatch-items button")).findIndex(b=>b.textContent.includes('+json.dumps(goal)+'))+1')
        click('#dispatch-items button:nth-child('+str(offer_index)+')')
        wait('dispatchView.current_offer.state', lambda x: x == 'ACCEPTED')
        click('#dispatch-receipt')
        receipt = wait('receiptView', lambda x: isinstance(x, dict) and x.get('step', {}).get('id') == receipt_step_id)
        if receipt.get('local_execution', {}).get('can_execute') is not True:
            raise AssertionError('Accepted current executor step did not expose the server-authorized local adapter action')
        if value('document.querySelector("#receipt-submit-button").disabled'):
            raise AssertionError('The existing manual receipt path should remain distinct and available before adapter generation')
        fill('#receipt-local-execution-reason', 'Generate the bounded synthetic handoff report for this accepted Run.')
        before_local_execution = write_count('/execute-local')
        click('#receipt-local-execution-button')
        wait_for_write('/execute-local', before_local_execution, 'EXECUTE_LOCAL')
        wait('document.querySelector("#receipt-local-execution-retry").hidden', lambda hidden: hidden is False)
        if not value('document.querySelector("#receipt-current").textContent.includes("旧回执快照已隐藏")'):
            raise AssertionError('Unknown adapter result must hide the previous receipt snapshot')
        if not value('document.querySelector("#receipt-submit-button").disabled'):
            raise AssertionError('Manual receipt mutation must be blocked while adapter outcome is unknown')
        capture('executor-adapter-projection-unknown')
        click('#receipt-local-execution-retry')
        receipt = wait('receiptView', lambda x: isinstance(x, dict) and
                       x.get('step', {}).get('id') == receipt_step_id and
                       x.get('local_execution', {}).get('current') is True and
                       x.get('local_execution', {}).get('record', {}).get('execution_id'))
        if receipt['step']['state'] != 'RECEIPT_RECORDED':
            raise AssertionError('Adapter execution did not produce the normal new receipt state')
        if receipt['local_execution']['record'].get('adapter_id') != 'synthetic.accepted-handoff-report':
            raise AssertionError('Receipt did not come from the expected server adapter')
        if receipt['local_execution']['record'].get('case_goal_completed') is not False:
            raise AssertionError('Adapter output must not claim Case completion')
        if receipt.get('qualification') != 'NOT_EVALUATED' or receipt.get('offline_fulfillment') != 'NO_EVIDENCE':
            raise AssertionError('Adapter result must not claim qualification or offline fulfillment')
        execution_id = receipt['local_execution']['record']['execution_id']
        generated_source_sha256 = receipt['current_receipt']['source_sha256']
        local_projection_attempts = value('window.localExecutionProjection.slice()')
        local_execution_attempts = value('window.localExecutionAttempts.slice()')
        if len(local_projection_attempts) != 1 or local_projection_attempts[0]['actual_server_status'] != 200 or local_projection_attempts[0]['client_status'] != 503:
            raise AssertionError('Expected only a client-side follow-up GET failure injected after a real committed server POST')
        if len(local_execution_attempts) != 2 or any(x['actual_server_status'] != 200 for x in local_execution_attempts) or len({x['request_fingerprint_sha256'] for x in local_execution_attempts}) != 1 or {x['execution_id'] for x in local_execution_attempts} != {execution_id}:
            raise AssertionError('Exact same-key/body server replay did not recover the original committed execution UUID')
        adapter_submit_events = sum(event.get('action') == 'SUBMIT' and event.get('payload', {}).get('record_mode') == 'SERVER_GENERATED_LOCAL_EXECUTION' for event in receipt.get('history', []))
        if adapter_submit_events != 1:
            raise AssertionError('Same-key replay must retain exactly one adapter-generated SUBMIT event')
        if not generated_source_sha256 or receipt['local_execution']['record'].get('external_acceptance') != 'NOT_SUBMITTED':
            raise AssertionError('Generated receipt must retain a source digest and no external acceptance')
        if value('document.querySelector("#receipt-text").value') or value('document.querySelector("#receipt-source").value'):
            raise AssertionError('Adapter-generated body must not be entered through the manual receipt form')
        if not value('document.querySelector("#receipt-submit-button").disabled'):
            raise AssertionError('Once a local adapter report exists, the manual-submit path must remain disabled for this step')
        if 'managed_access' in value('document.querySelector("#receipt-current").textContent') or 'CURRENT_MANAGED_EXECUTOR_LEASE' in value('document.querySelector("#receipt-current").textContent'):
            raise AssertionError('Raw local adapter binding internals must not be dumped into the receipt UI')
        capture('executor-adapter-report-generated')
        # Re-open the UI without carrying in-memory views; the same executor can
        # recover only its own committed adapter receipt from the product API.
        observed_posts.extend(value('window.ownedRunAccessPosts.map(x=>({path:x.path,action:x.action,actual_server_status:x.actual_server_status,client_status:x.client_status}))'))
        browser('open', base_url)
        wait('document.readyState', lambda x: x == 'complete')
        install_network_tap(False)
        switch(executor_id)
        click('[data-tab="collaboration"]')
        click('#dispatch-list')
        wait('document.querySelector("#dispatch-items").textContent', lambda x: goal in x)
        offer_index = value('Array.from(document.querySelectorAll("#dispatch-items button")).findIndex(b=>b.textContent.includes(' + json.dumps(goal) + '))+1')
        click('#dispatch-items button:nth-child(' + str(offer_index) + ')')
        click('#dispatch-receipt')
        persisted = wait('receiptView', lambda x: isinstance(x, dict) and
                         x.get('local_execution', {}).get('current') is True and
                         x.get('local_execution', {}).get('record', {}).get('execution_id') == execution_id)
        if persisted['current_receipt']['source_sha256'] != generated_source_sha256:
            raise AssertionError('Reload did not recover the same server-generated report source hash')
        capture('executor-adapter-report-after-reload')

        switch('fixture-a')
        click('[data-tab="collaboration"]')
        click('#receipt-list')
        wait('document.querySelector("#receipt-items").textContent', lambda x: goal in x)
        receipt_index = value('Array.from(document.querySelectorAll("#receipt-items button")).findIndex(b=>b.textContent.includes(' + json.dumps(goal) + '))+1')
        if receipt_index < 1:
            raise AssertionError('The owner cannot find the current same-Case receipt in the existing receipt list')
        click('#receipt-items button:nth-child(' + str(receipt_index) + ')')
        receipt = wait('receiptView', lambda x: isinstance(x, dict) and x.get('step', {}).get('preparation_id') == prep_id)
        if not receipt.get('current_receipt'):
            raise AssertionError('Owner cannot read the current receipt for acknowledgement')
        local_execution = receipt.get('local_execution') or {}
        if local_execution.get('current') is not True or local_execution.get('record', {}).get('execution_id') != execution_id:
            raise AssertionError('Owner cannot read the current adapter report independently of executor submission')
        if value('!document.querySelector("#receipt-local-execution-form").hidden'):
            raise AssertionError('Owner must not receive the executor-only adapter-generation form')
        if 'managed_access' in value('document.querySelector("#receipt-local-execution-record").textContent'):
            raise AssertionError('Owner report summary must not expose the underlying managed access binding')
        capture('owner-current-adapter-report')
        fill('#receipt-reason', 'Owner manually acknowledges the current server-generated synthetic report only.')
        click('#receipt-ack')
        receipt = wait('receiptView', lambda x: isinstance(x, dict) and x.get('step', {}).get('state') == 'LOCAL_ACKNOWLEDGED')
        click('#plan-from-receipt')
        wait('planView', lambda x: isinstance(x, dict) and x.get('preparation_id') == prep_id)
        click('#case-path-read')
        wait('casePathView', lambda x: isinstance(x, dict) and x.get('run_id') == run_id)
        click('#case-path-result button')
        approved_owner = wait('runAccessView', lambda x: isinstance(x, dict) and x.get('state') == 'APPROVED')
        if approved_owner.get('actual_run_access') is not True:
            raise AssertionError('Owner must see the currently projected access separately from candidate approval')
        fill('#run-access-decision-reason', 'Explicit owner revocation after local receipt acknowledgement.')
        click('#run-access-revoke')
        revoked = wait('runAccessView', lambda x: isinstance(x, dict) and x.get('state') == 'REVOKED', timeout=20)
        if revoked.get('actual_run_access') is not False or not any(e.get('action') == 'REVOKE' for e in revoked.get('history', [])):
            raise AssertionError('Revocation must deny future access and retain an audit record')
        capture('owner-revoked-history')

        switch(executor_id)
        click('#run-access-open')
        fill('#run-access-id', run_id)
        click('#run-access-read')
        beneficiary_view = wait('runAccessView', lambda x: isinstance(x, dict) and x.get('scope', {}).get('run_id') == run_id)
        if beneficiary_view.get('actual_run_access') is not False or beneficiary_view.get('state') != 'REVOKED':
            raise AssertionError('Executor access projection remained after revocation')
        fill('#run', run_id)
        click('#refresh')
        wait('document.querySelector("#page-feedback").textContent', lambda x: bool(x))
        denied_read = wait('ownedRunAccessReads.filter(x=>x.path=="/api/runs/'+run_id+'").slice(-1)[0] || null', lambda x: isinstance(x, dict) and x['actual_server_status'] != 200)
        if denied_read['actual_server_status'] != 403 or denied_read['client_status'] != 403:
            raise AssertionError('Expected actual and client HTTP 403 on original Run read after revoke, got: ' + str(denied_read))
        click('#dispatch-list')
        wait('document.querySelector("#dispatch-items").textContent.length', lambda x: x > 0)
        # Authorized list is role-scoped; no item for the revoked Run is expected.
        if goal in value('document.querySelector("#dispatch-items").textContent'):
            raise AssertionError('Revoked executor still sees the Run in dispatch list')
        capture('executor-revoked')

        post_info = observed_posts + value('ownedRunAccessPosts.map(x=>({path:x.path,action:x.action,actual_server_status:x.actual_server_status,client_status:x.client_status}))')
        actions = [x['action'] for x in post_info]
        offer_post = any(x['path'].endswith('/api/preparations/'+prep_id+'/dispatch') and
                         x['actual_server_status'] == 201 for x in post_info)
        # OFFER has no action field; the route and created status identify the POST.
        if not offer_post or not all(action in actions for action in ('REQUEST', 'ACCEPT', 'EXECUTE_LOCAL', 'ACKNOWLEDGE', 'REVOKE')):
            raise AssertionError('Expected the actual adapter-backed product POST chain was not observed: ' + repr(actions))
        if 'SUBMIT' in actions:
            raise AssertionError('The final happy path must use the server adapter, not manual receipt submission')
        adapter_posts = [x for x in post_info if x['path'].endswith('/execute-local')]
        if len(adapter_posts) != 2 or any(x['actual_server_status'] != 200 for x in adapter_posts):
            raise AssertionError('Expected two successful actual server POSTs: initial execution and exact idempotent retry')
        if [x['action'] for x in adapter_posts] != ['EXECUTE_LOCAL', 'EXECUTE_LOCAL']:
            raise AssertionError('Both adapter requests must be recorded as EXECUTE_LOCAL')
        if not any('/access/commands' in x['path'] and x['action'] == 'REQUEST' for x in post_info):
            raise AssertionError('Expected an authenticated access request UI command')
        if not any('/access/commands' in x['path'] and x['action'] == 'APPROVE' for x in post_info):
            raise AssertionError('Expected an authenticated independent approval UI command')
        if not any('/access/commands' in x['path'] and x['action'] == 'REVOKE' for x in post_info):
            raise AssertionError('Expected an authenticated revoke UI command')
        report = {
            'status': 'PASS', 'scope': 'FRESH_ZERO_BUSINESS_RUN_ACCESS_TO_SERVER_ADAPTER_RECEIPT_ACK_AND_REVOKE',
            'runtime_directory': str(runtime), 'base_url': base_url,
            'case_id': case_id, 'run_id': run_id, 'preparation_id': prep_id,
            'receipt_step_id': receipt_step_id, 'owner_role': 'fixture-a',
            'executor_role': executor_id, 'approver_role': 'prep-specialist-fixture-a',
            'initial_business_counts': initial_counts,
            'live_owner_preparations_before_browser': 0,
            'request_state': request_view['state'], 'approval_state': approved['state'],
            'actual_access_after_approval': True, 'dispatch_state': 'ACCEPTED',
            'receipt_state': 'LOCAL_ACKNOWLEDGED', 'receipt_generation': 'SERVER_EXECUTE_LOCAL_ADAPTER',
            'local_execution_id': execution_id, 'local_execution_adapter_id': 'synthetic.accepted-handoff-report',
            'generated_receipt_source_sha256': generated_source_sha256, 'revoked_state': revoked['state'],
            'actual_access_after_revoke': False, 'owner_audit_retained': True,
            'run_read_denied_after_revoke': True, 'executor_dispatch_item_removed': True,
            'specialist_offer_route_post_confirmed': offer_post,
            'business_post_actions': actions, 'viewport_checks': metrics,
            'qualification': 'NOT_EVALUATED', 'external_acceptance': 'NOT_SUBMITTED',
            'offline_fulfillment': 'NO_EVIDENCE', 'live_model_calls': 0,
            'actual_assignment_write': 'EXPLICIT_MANAGED_PROJECTION_AFTER_APPROVAL_ONLY',
            'projection_pending_ui_case': 'NEGATIVE_CLIENT_ACK_INJECTED_ONLY_AFTER_REAL_SERVER_COMMIT',
            'projection_pending_retry_same_key_and_body_verified': True,
            'manual_receipt_submit_observed': False, 'server_adapter_execution_observed': True,
            'cold_reload_same_executor_report_recovered': True, 'owner_current_report_readable': True,
            'followup_get_failure': 'CLIENT_INJECTED_AFTER_ACTUAL_SERVER_EXECUTE_LOCAL_COMMIT',
            'execute_local_actual_posts': len(local_execution_attempts),
            'execute_local_successful_server_posts': len(adapter_posts),
            'execute_local_request_fingerprints_equal': True,
            'adapter_generated_submit_events': adapter_submit_events,
            'adapter_effect_count': 1,
            'adapter_execution_id_stable_across_retry': True,
            'executor_generated_source_sha256': generated_source_sha256,
            'lease_timeout_pending_retry_ui': 'CLIENT_TIMER_BRANCH_EXERCISED_BEFORE_REAL_LEASE_DEADLINE; SERVER_LEASE_NOT_CHANGED',
            'approval_audit_events_after_retry': sum(event.get('action') == 'APPROVE' for event in approved.get('history', [])),
            'deployment_enabled': False,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except Exception as error:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({'status': 'FAIL', 'error_type': type(error).__name__,
                                           'error': str(error),
                                           'screenshots': sorted(p.name for p in args.screenshots.glob('*.png'))},
                                          ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        raise
    finally:
        subprocess.run(command + ['close'], capture_output=True, text=True, env=env, timeout=15)
        shutil.rmtree(socket_directory, ignore_errors=True)

if __name__ == '__main__':
    main()
