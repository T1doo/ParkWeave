"""Real Chromium/local API/worker/PG, three synthetic roles, no external execution."""
from pathlib import Path
import argparse,json,os,subprocess,time,uuid
from parkweave.process_env import minimal_environment
from parkweave.store import Store
root=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--report',required=True,type=Path);p.add_argument('--screenshots',required=True,type=Path);args=p.parse_args()
if os.name=='nt':raise RuntimeError('NOT_RUN: Linux harness is not native Windows evidence')
owner=Store(os.environ['PARKWEAVE_DISPATCH_FIXTURE_OWNER_DSN'])
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
candidates=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2'];assert candidates
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','parkweave-notices','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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
    diagnostic=value("({notice_error:document.querySelector('#notice-error').textContent,notice_selected:!!noticeView,notice_context_present:!!noticeContext,notice_read_disabled:document.querySelector('#notice-read').disabled})")
    raise AssertionError('browser readiness failed: '+expr+' '+json.dumps(diagnostic))
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
    value("(()=>{const panel=document.querySelector('#notice-detail:not([hidden])')||document.querySelector('#dispatch-detail:not([hidden])');if(panel)panel.scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/name))
try:
    sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());specialists=json.loads((root/'.runtime/preparation-sessions.json').read_text());executors=json.loads((root/'.runtime/receipt-sessions.json').read_text())
    browser('open','http://127.0.0.1:8765');browser('snapshot','-i');switch(sessions['fixture-a'])
    goal='SYNTHETIC executor receipt '+uuid.uuid4().hex[:8]
    click('#prep-catalog');wait('prepCatalog',lambda x:isinstance(x,dict));browser('fill','#prep-goal',goal);browser('find','role','button','click','--name','开始资料准备');browser('snapshot','-i');wait('preparationView',lambda x:isinstance(x,dict))
    for slot,text in [('need_summary','SYNTHETIC request'),('material_outline','SYNTHETIC private material body')]:
        revision=value('preparationView.preparation.revision');browser('select','#prep-slot',slot);browser('fill','#prep-text',text);browser('fill','#prep-source-label','SYNTHETIC fixture document v1');browser('find','role','button','click','--name','追加材料版本');browser('snapshot','-i');wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>revision)
    click('[data-tab=collaboration]');switch(specialists['prep-specialist-fixture-a']);prep_select(goal);prep_act('#prep-review')
    switch(sessions['fixture-a']);prep_select(goal);parent=prep_act('#prep-confirm')['preparation']
    # Explicit fixture-owner setup of this new synthetic Run. No app assignment API.
    owner.assign_status('receipt-executor-fixture-a',uuid.UUID(parent['run_id']),active=True)
    switch(specialists['prep-specialist-fixture-a']);prep_select(goal)
    click('#dispatch-prepare');wait('dispatchView',lambda x:isinstance(x,dict) and x['revision']==0)
    def dispatch_offer(reason):
        previous=value('dispatchView.revision');browser('fill','#dispatch-offer-reason',reason);click('#dispatch-offer-button')
        return wait('dispatchView',lambda x:isinstance(x,dict) and x['revision']>previous)
    def dispatch_select():
        click('#dispatch-list');wait("document.querySelector('#dispatch-items').textContent",lambda x:goal in x)
        browser('find','role','button','click','--name',goal);browser('snapshot','-i');return wait('dispatchView',lambda x:isinstance(x,dict))
    def dispatch_decide(selector,reason):
        previous=value('dispatchView.revision');browser('fill','#dispatch-decision-reason',reason);click(selector)
        return wait('dispatchView',lambda x:isinstance(x,dict) and x['revision']>previous)
    offered=dispatch_offer('<script>globalThis.BAD_DISPATCH=true</script> SYNTHETIC please handle locally');dispatch_id=offered['dispatch_id']
    assert not value('Boolean(globalThis.BAD_DISPATCH||document.querySelector("#dispatch-current script"))');screenshot('specialist-offered.png')
    def notices(action):
        end=time.monotonic()+20
        while time.monotonic()<end:
            click('#notice-list')
            x=wait("(async()=>{const r=await fetch('/api/dispatch-notices',{headers:{Authorization:'Bearer '+document.querySelector('#token').value}});return await r.json();})()",lambda x:isinstance(x,dict))
            match=[n for n in x['items'] if n['dispatch_id']==dispatch_id and n['action']==action]
            if match:return sorted(match,key=lambda n:n['revision'])[-1]
            time.sleep(.2)
        raise AssertionError('notice worker did not deliver '+action)
    def open_notice(n,expected_state):
        click('[data-notice-id="'+n['event_id']+'"] button');wait('noticeView',lambda x:isinstance(x,dict) and x['event_id']==n['event_id'])
        assert value("document.querySelector('#notice-read').disabled")
        click('#notice-open');wait('dispatchView',lambda x:isinstance(x,dict) and x['current_offer']['state']==expected_state)
        wait('noticeView',lambda x:isinstance(x,dict) and bool(x['open_requested_at']))
        # Source rendering expands the page after OPEN. Locate the explicit action
        # again after layout settles instead of clicking its previous coordinates.
        value("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))")
        browser('find','role','button','click','--name','我已读此通知');browser('snapshot','-i')
        return wait('noticeView',lambda x:isinstance(x,dict) and bool(x['read_at']))
    switch(executors['receipt-executor-fixture-a']);first=notices('OFFER');open_notice(first,'OFFERED');screenshot('executor-open-read.png')
    refused=dispatch_decide('#dispatch-decline','SYNTHETIC local schedule unavailable');assert refused['current_offer']['state']=='DECLINED'
    switch(specialists['prep-specialist-fixture-a']);declined=notices('DECLINE');open_notice(declined,'DECLINED');screenshot('specialist-decline-read.png')
    dispatch_offer('SYNTHETIC second offer');dispatch_decide('#dispatch-withdraw','SYNTHETIC revised local schedule')
    switch(executors['receipt-executor-fixture-a']);withdrawn=notices('WITHDRAW');open_notice(withdrawn,'WITHDRAWN');click('#notice-back');wait('noticeView',lambda x:x is None)
    switch(specialists['prep-specialist-fixture-a']);dispatch_select();dispatch_offer('SYNTHETIC final offer')
    switch(executors['receipt-executor-fixture-a']);latest=notices('REOFFER');assert latest['revision']==5;open_notice(latest,'OFFERED');accepted=dispatch_decide('#dispatch-accept','SYNTHETIC current local acceptance');assert accepted['revision']==6
    switch(sessions['fixture-a']);accepted_notice=notices('ACCEPT');open_notice(accepted_notice,'ACCEPTED');screenshot('enterprise-accept-read.png')
    historical=notices('OFFER');assert historical['historical'];oldread=open_notice(historical,'ACCEPTED');assert oldread['historical'];screenshot('enterprise-history-current.png')
    metrics=[]
    for width in (320,390):
        browser('set','viewport',str(width),'844');browser('snapshot','-i');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['scroll']<=m['width'];metrics.append(m);screenshot('notice-'+str(width)+'.png')
    browser('set','viewport','1200','900');browser('reload');browser('snapshot','-i');switch(sessions['fixture-a']);click('[data-tab=collaboration]');persistent=notices('ACCEPT');assert persistent['read_at']
    switch(sessions['fixture-b']);click('#notice-list');wait("document.querySelector('#notice-list-summary').textContent",lambda x:bool(x));assert not value("Boolean(document.querySelector('[data-notice-id=\""+accepted_notice['event_id']+"\"]'))")
    switch(executors['receipt-executor-fixture-a']);open_notice(notices('REOFFER'),'ACCEPTED')
    owner.assign_status('receipt-executor-fixture-a',uuid.UUID(parent['run_id']),active=False)
    # The rendered view must clear on a fresh denied source request, without cached authority.
    click('#notice-open');wait("document.querySelector('#notice-error').textContent",lambda x:bool(x));assert value('noticeView') is None and value('dispatchView') is None
    status=value("(async()=>{const r=await fetch('/api/dispatch-notices/"+latest['event_id']+"',{headers:{Authorization:'Bearer '+document.querySelector('#token').value}});return r.status;})()");assert status==403
    screenshot('executor-revoked-clear.png');assert not browser('errors')
    report=dict(scope='SYNTHETIC_INTERNAL_DISPATCH_NOTICES_ONLY',dispatch_id=dispatch_id,run_id=parent['run_id'],case_id=parent['case_id'],dispatch_revision=6,three_roles_real_UI=True,offer_decline_reoffer_withdraw_accept=True,worker_delivery=True,explicit_open_and_read=True,history_opens_current_source=True,back_to_list=True,reload_read_persistent=True,cross_tenant_isolated=True,current_revocation_clears_private_views=True,no_grants_created_by_application=True,narrow_viewports=metrics,screenshots=len(list(args.screenshots.glob('*.png'))),model_calls=0,real_budget=0,external_notifications=0,case_goal_completed=False,F1='UNACCEPTED',F2='NOT_PASSED',R4='DISABLED',native_Windows='NOT_RUN',whole_AT_EX='NOT_RUN')
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
finally:browser('close')
