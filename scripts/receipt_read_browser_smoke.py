"""Read-only existing Case UI: real 403, refresh fault, delayed reads across identities.
Requires an already running local synthetic fixture and existing assignments.
No seed, grant mutation, business command, external network or model call.
"""
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
def receipt_select(goal):
    click('#receipt-list');wait("document.querySelector('#receipt-items').textContent",lambda x:goal in x)
    name=value("Array.from(document.querySelectorAll('#receipt-items button')).find(x=>x.textContent.startsWith("+json.dumps(goal)+")).textContent")
    browser('find','role','button','click','--name',name);browser('snapshot','-i');return wait('receiptView',lambda x:isinstance(x,dict))
args.screenshots.mkdir(parents=True,exist_ok=False)
viewport_checks=[]
def feedback_widths(label):
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');browser('snapshot','-i')
        metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width']
        viewport_checks.append(dict(stage=label,**metric))
        value("(()=>{document.querySelector('#page-feedback').scrollIntoView({block:'center'});return true;})()");browser('screenshot',str(args.screenshots.resolve()/(label+'-'+str(width)+'.png')))
    browser('set','viewport','1200','900')
def screenshot(name):
    value("(()=>{const panel=document.querySelector('#local-case-detail:not([hidden])')||document.querySelector('#receipt-detail:not([hidden])');if(panel)panel.scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/name))



def grant_snapshot():
    # Private fixture-owner reads only. Never seed/assign/migrate or alter grants.
    with owner.connect() as c:
        return {table:[dict(row) for row in c.execute('SELECT * FROM '+table+' ORDER BY 1,2').fetchall()]
                for table in ('run_assignments','capability_grants')}

try:
    before=grant_snapshot()
    with owner.connect() as c:
        parent=c.execute('SELECT id,run_id,case_id,goal FROM preparations WHERE case_id=%s',(args.case_id,)).fetchone()
        assert parent is not None
    sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());executors=json.loads((root/'.runtime/receipt-sessions.json').read_text())
    browser('open','http://127.0.0.1:8765');browser('snapshot','-i');switch(sessions['fixture-a']);click('[data-tab=collaboration]')
    initial=receipt_select(parent['goal']);receipt_id=initial['step']['id']
    # Real HTTP 403 from the unchanged local API; no grant mutation.
    value("(()=>{window.captureFetch=window.fetch;window.invalidStatus=null;window.fetch=async(p,o)=>{const r=await window.captureFetch(p,o);if(String(p)==='/api/executor-receipts')window.invalidStatus=r.status;return r;};return true;})()");switch('SYNTHETIC_INVALID_SESSION');click('#receipt-list')
    wait("document.querySelector('#receipt-error').textContent",lambda x:bool(x))
    assert value('invalidStatus')==403;value("(()=>{window.fetch=window.captureFetch;return true;})()");invalid=value("({httpStatus:invalidStatus,detailHidden:document.querySelector('#receipt-detail').hidden,error:document.querySelector('#receipt-error').textContent,feedback:document.querySelector('#page-feedback').textContent})")
    assert invalid['feedback']==invalid['error'] and '权限' in invalid['feedback'];value("(()=>{document.querySelector('#page-feedback').scrollIntoView({block:'center'});return true;})()");screenshot('invalid-session-feedback.png');feedback_widths('invalid-session-feedback')
    switch(sessions['fixture-a']);receipt_select(parent['goal'])
    # One deterministic local browser network fault, not a backend permission result.
    value("(()=>{window.realFetch=window.fetch;window.fetch=async(p,o)=>{if(String(p).startsWith('/api/executor-receipts/')){window.fetch=window.realFetch;throw Error('SYNTHETIC_OFFLINE_FAULT');}return window.realFetch(p,o);};return true;})()")
    click('#receipt-refresh');wait("document.querySelector('#receipt-error').textContent",lambda x:bool(x))
    offline=value("({detailHidden:document.querySelector('#receipt-detail').hidden,error:document.querySelector('#receipt-error').textContent,feedback:document.querySelector('#page-feedback').textContent})")
    assert offline['feedback']==offline['error'] and '检查本地连接' in offline['feedback'];value("(()=>{document.querySelector('#page-feedback').scrollIntoView({block:'center'});return true;})()");screenshot('refresh-failure-feedback.png');feedback_widths('refresh-failure-feedback')
    click('#receipt-list');wait("document.querySelector('#receipt-items').textContent",lambda x:parent['goal'] in x);assert not value("document.querySelector('#page-feedback').textContent");receipt_select(parent['goal'])
    assert not value("document.querySelector('#page-feedback').textContent")
    # Hold an actual successful read until after identity switch, without changing payload.
    value("(()=>{window.realFetch=window.fetch;window.heldRead=null;window.fetch=async(p,o)=>{if(String(p).startsWith('/api/executor-receipts/')){const r=await window.realFetch(p,o);await new Promise(resolve=>window.heldRead=resolve);return r;}return window.realFetch(p,o);};return true;})()")
    click('#receipt-refresh');wait('typeof heldRead',lambda x:x=='function')
    switch(executors['receipt-executor-fixture-a'])
    value("(()=>{window.fetch=window.realFetch;window.heldRead();return true;})()")
    browser('snapshot','-i')
    cleared=value("({viewCleared:receiptView===null,history:document.querySelector('#receipt-history').textContent,current:document.querySelector('#receipt-current').textContent,feedback:document.querySelector('#page-feedback').textContent})")
    assert cleared['viewCleared'] and not cleared['history'] and not cleared['current'] and not cleared['feedback']
    loaded=receipt_select(parent['goal']);assert loaded['role']=='service_executor'
    assert loaded['step']['revision']==initial['step']['revision'] and loaded['receipt_history']==initial['receipt_history']
    screenshot('executor-current-history.png')
    # Hold an older request's rejection while the new identity loads its genuine view.
    value("(()=>{window.realFetch=window.fetch;window.oldReject=null;window.fetch=(p,o)=>{if(String(p).startsWith('/api/executor-receipts/'))return new Promise((resolve,reject)=>window.oldReject=reject);return window.realFetch(p,o);};return true;})()")
    click('#receipt-refresh');wait('typeof oldReject',lambda x:x=='function')
    switch(sessions['fixture-a']);value("(()=>{window.fetch=window.realFetch;return true;})()")
    current=receipt_select(parent['goal']);value("(()=>{window.oldReject(Error('SYNTHETIC_OLD_FAILURE'));return true;})()")
    browser('snapshot','-i')
    stale_error=value("({role:receiptView.role,error:document.querySelector('#receipt-error').textContent,feedback:document.querySelector('#page-feedback').textContent})")
    assert stale_error['role']=='enterprise_operator' and not stale_error['error'] and not stale_error['feedback']
    assert grant_snapshot()==before and current['step']['revision']==initial['step']['revision'] and current['receipt_history']==initial['receipt_history']
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');browser('snapshot','-i')
        metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];viewport_checks.append(dict(stage='current-receipt-history',**metric));screenshot('current-receipt-'+str(width)+'.png')
    click('#local-case-receipt');local=wait('localCaseView',lambda x:isinstance(x,dict))
    assert local['case_id']==str(args.case_id) and local['local_record_state']=='LOCAL_RECORD_CLOSED' and not local['case_goal_completed']
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');browser('snapshot','-i')
        metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];viewport_checks.append(dict(stage='current-case-local-record',**metric));screenshot('current-case-'+str(width)+'.png')
    assert not browser('errors')
    report={'scope':'EXISTING_CASE_READONLY_RECEIPT_REAL_UI_SESSION_AND_LATE_RESPONSES','case_id':str(args.case_id),'receipt_revision':initial['step']['revision'],'receipt_versions':len(initial['receipt_history']),'real_API_invalid_session':invalid,'injected_browser_network_failure':offline,'late_success_identity_switch':cleared,'late_error_new_identity':stale_error,'receipt_revision_and_history_unchanged':True,'grants_unchanged':True,'new_assignments':0,'business_writes':0,'model_calls':0,'R4':'DISABLED','viewport_checks':viewport_checks,'case_local_revision':local['revision'],'case_cycle':local['cycle'],'case_goal_completed':local['case_goal_completed'],'case_state':local['case_state']}
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
finally:browser('close')
