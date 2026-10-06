"""Real Chromium/local API/worker/PG, reuse existing synthetic Case and assignment, no new grants."""
from pathlib import Path
import argparse,json,os,subprocess,time,uuid
from parkweave.process_env import minimal_environment
from parkweave.store import Store
root=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--case-id',required=True,type=uuid.UUID);p.add_argument('--report',required=True,type=Path);p.add_argument('--screenshots',required=True,type=Path);args=p.parse_args()
if os.name=='nt':raise RuntimeError('NOT_RUN: Linux harness is not native Windows evidence')
owner=Store(os.environ['PARKWEAVE_CASE_FIXTURE_OWNER_DSN'])
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
candidates=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2'];assert candidates
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','parkweave-correction-local','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
def browser(*items,stdin=None):
    r=subprocess.run(cmd+list(items),input=stdin,capture_output=True,text=True,env=env,timeout=30)
    if r.returncode:raise RuntimeError('cached local browser command failed')
    return r.stdout.strip()
def value(expr):
    r=json.loads(browser('eval','(async()=>JSON.stringify(await ('+expr+')))()'));return json.loads(r) if isinstance(r,str) else r

def wait(expr,predicate,timeout=20):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        x=value(expr)
        if predicate(x):return x
        time.sleep(.1)
    raise AssertionError('browser readiness failed: '+expr)
def click(selector):browser('click',selector);browser('snapshot','-i')
def switch(token):
    browser('eval','--stdin',stdin="document.querySelector('#token').value="+json.dumps(token)+";document.querySelector('#token').dispatchEvent(new Event('input'));undefined")
    assert value('receiptView') is None and value('preparationView') is None
    assert value("document.querySelector('#receipt-history').textContent")==''
    browser('snapshot','-i')
def prep_act(selector):
    revision=value('preparationView.preparation.revision');browser('fill','#prep-reason','SYNTHETIC local manual check');click(selector)
    return wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>revision)
def prep_select(goal):
    click('#prep-list');wait("document.querySelector('#prep-items').textContent",lambda x:goal in x)
    name=value("Array.from(document.querySelectorAll('#prep-items button')).find(x=>x.textContent.startsWith("+json.dumps(goal)+")).textContent")
    browser('find','role','button','click','--name',name);browser('snapshot','-i');wait('preparationView',lambda x:isinstance(x,dict))
def receipt_select(goal):
    click('#receipt-list');wait("document.querySelector('#receipt-items').textContent",lambda x:goal in x)
    name=value("Array.from(document.querySelectorAll('#receipt-items button')).find(x=>x.textContent.startsWith("+json.dumps(goal)+")).textContent")
    browser('find','role','button','click','--name',name);browser('snapshot','-i');return wait('receiptView',lambda x:isinstance(x,dict))
def submit(text,label):
    revision=value('receiptView.step.revision');browser('fill','#receipt-text',text);browser('fill','#receipt-source',label);click('#receipt-submit-button')
    return wait('receiptView',lambda x:isinstance(x,dict) and x['step']['revision']>revision)
def decision(selector,reason):
    revision=value('receiptView.step.revision');browser('fill','#receipt-reason',reason);click(selector)
    return wait('receiptView',lambda x:isinstance(x,dict) and x['step']['revision']>revision)
args.screenshots.mkdir(parents=True,exist_ok=False)
def screenshot(name):
    value("(()=>{const panel=document.querySelector('#local-case-detail:not([hidden])')||document.querySelector('#receipt-detail:not([hidden])');if(panel)panel.scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/name))

def case_act(selector,reason):
    previous=value('localCaseView.revision');browser('fill','#local-case-reason',reason);click(selector)
    return wait('localCaseView',lambda x:isinstance(x,dict) and x['revision']>previous)

def open_case():
    click('#local-case-receipt');return wait('localCaseView',lambda x:isinstance(x,dict))

def grant_snapshot():
    # Private fixture-owner reads only. Never seed/assign/migrate or alter grants.
    with owner.connect() as c:
        return {table:[dict(row) for row in c.execute('SELECT * FROM '+table+' ORDER BY 1,2').fetchall()]
                for table in ('run_assignments','capability_grants')}

try:
    grants_before=grant_snapshot()
    with owner.connect() as c:
        parent=c.execute('SELECT id,run_id,case_id,goal FROM preparations WHERE case_id=%s',(args.case_id,)).fetchone()
        assert parent is not None
        assert c.execute("SELECT 1 FROM run_assignments WHERE principal_id='receipt-executor-fixture-a' AND run_id=%s AND active=true",(parent['run_id'],)).fetchone()
    sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());executors=json.loads((root/'.runtime/receipt-sessions.json').read_text())
    goal=parent['goal'];browser('open','http://127.0.0.1:8765');browser('snapshot','-i');switch(sessions['fixture-a']);click('[data-tab=collaboration]')
    before_receipt=receipt_select(goal);assert before_receipt['step']['state']=='LOCAL_ACKNOWLEDGED'
    before=open_case();assert before['case_id']==str(args.case_id) and before['local_record_state']=='LOCAL_RECORD_CLOSED'
    reopened=case_act('#local-case-reopen','SYNTHETIC reopen same Case to inspect changed receipt');assert reopened['cycle']==before['cycle']+1
    ready=case_act('#local-case-validate','SYNTHETIC baseline current dependencies before receipt correction');assert ready['verification_current'] and ready['can_close_local_record']
    baseline_sha=ready['verified_snapshot_sha256'];screenshot('same-case-ready-before-correction.png')
    # Acknowledged receipts must reopen before a reviewable submission/correction.
    receipt_select(goal);decision('#receipt-reopen','SYNTHETIC reopen acknowledged log for further review')
    blocked=open_case();assert not blocked['verification_current'] and not blocked['can_revalidate'] and not blocked['can_close_local_record'];screenshot('same-case-receipt-reopened-blocks-close.png')
    switch(executors['receipt-executor-fixture-a']);receipt_select(goal)
    review=submit('SYNTHETIC additional work log needing clarification','SYNTHETIC review draft')
    switch(sessions['fixture-a']);receipt_select(goal);corrected=decision('#receipt-correct','SYNTHETIC specify the missing work-log detail')
    assert corrected['step']['state']=='CHANGES_REQUESTED';screenshot('enterprise-requested-correction.png')
    blocked=open_case();assert not blocked['can_revalidate'] and not blocked['can_close_local_record']
    switch(executors['receipt-executor-fixture-a']);receipt_select(goal)
    latest=submit('SYNTHETIC corrected work log with requested detail','SYNTHETIC corrected current version')
    assert latest['current_receipt']['version']==review['current_receipt']['version']+1
    assert latest['current_receipt']['source_sha256']!=review['current_receipt']['source_sha256'];screenshot('executor-new-corrected-version.png')
    switch(sessions['fixture-a']);receipt_select(goal)
    blocked=open_case();assert not blocked['can_close_local_record'] and not blocked['can_revalidate']
    receipt_select(goal);acked=decision('#receipt-ack','SYNTHETIC enterprise rechecked this corrected current version only')
    assert acked['step']['state']=='LOCAL_ACKNOWLEDGED'
    stale=open_case();assert stale['can_revalidate'] and not stale['verification_current'] and not stale['can_close_local_record']
    assert stale['verified_snapshot_sha256']==baseline_sha and stale['current_snapshot_sha256']!=baseline_sha
    assert value("document.querySelector('#local-case-close').disabled") is True
    assert '本轮原校验已失效，须重新校验' in value("document.querySelector('#local-case-summary').textContent");screenshot('enterprise-rechecked-still-needs-case-revalidation.png')
    verified=case_act('#local-case-validate','SYNTHETIC explicit revalidation after current receipt changed')
    assert verified['verification_current'] and verified['verified_snapshot_sha256']!=baseline_sha
    final=case_act('#local-case-close','SYNTHETIC close local record after corrected receipt recheck')
    assert final['case_id']==str(args.case_id) and not final['case_goal_completed'] and final['case_state']=='WAITING_CONFIRMATION'
    metrics=[]
    for width in (320,390):
        browser('set','viewport',str(width),'844');browser('snapshot','-i');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['scroll']<=m['width'];metrics.append(m);screenshot('corrected-case-'+str(width)+'.png')
    browser('set','viewport','1200','900');browser('reload');browser('snapshot','-i');switch(sessions['fixture-a']);click('[data-tab=collaboration]');loaded=receipt_select(goal)
    assert loaded['step']['revision']==acked['step']['revision'] and len(loaded['receipt_history'])==len(before_receipt['receipt_history'])+2
    reloaded=open_case();assert reloaded['revision']==final['revision'] and reloaded['cycle']==final['cycle'];screenshot('same-case-corrected-reload.png')
    assert grant_snapshot()==grants_before
    assert not browser('errors')
    report=dict(scope='EXISTING_SYNTHETIC_CASE_RECEIPT_CORRECTION_REVALIDATION',case_id=str(args.case_id),run_id=str(parent['run_id']),same_existing_Case=True,existing_assignment_reused=True,new_assignments=0,grants_unchanged=True,real_UI=True,source_receipt_revision=before_receipt['step']['revision'],final_receipt_revision=acked['step']['revision'],source_receipt_versions=len(before_receipt['receipt_history']),final_receipt_versions=len(loaded['receipt_history']),correction_requests_current_version=True,new_version_hash_changed=True,ack_blocks_close_until_explicit_revalidation=True,old_verified_snapshot_invalidated=True,local_record_revision=final['revision'],cycle=final['cycle'],reload_persistent=True,case_goal_completed=False,case_state=final['case_state'],qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE',narrow_viewports=metrics,screenshots_directory=str(args.screenshots),model_calls=0,budget=0,R4='DISABLED',native_Windows='NOT_RUN',whole_AT_EX='NOT_RUN')
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
finally:browser('close')
