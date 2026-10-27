"""Real Chromium/local API/worker/PG, three synthetic roles, no external execution."""
from pathlib import Path
import argparse,json,os,subprocess,time,uuid
from parkweave.process_env import minimal_environment
from parkweave.store import Store
root=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--report',required=True,type=Path);p.add_argument('--screenshots',required=True,type=Path);args=p.parse_args()
if os.name=='nt':raise RuntimeError('NOT_RUN: Linux harness is not native Windows evidence')
owner=Store(os.environ['PARKWEAVE_RECEIPT_FIXTURE_OWNER_DSN'])
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
candidates=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2'];assert candidates
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','parkweave-cross-module','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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
args.screenshots.mkdir(parents=True,exist_ok=True)
def screenshot(name,focus='#receipt-detail'):
    if focus:browser('eval','document.querySelector('+json.dumps(focus)+').scrollIntoView({block:"start"});undefined')
    browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/name))
try:
    sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());specialists=json.loads((root/'.runtime/preparation-sessions.json').read_text());executors=json.loads((root/'.runtime/receipt-sessions.json').read_text())
    browser('open','http://127.0.0.1:8765');browser('snapshot','-i');switch(sessions['fixture-a'])
    goal='SYNTHETIC cross-module '+uuid.uuid4().hex[:8]
    click('#prep-catalog');wait('prepCatalog',lambda x:isinstance(x,dict));browser('fill','#prep-goal',goal);browser('find','role','button','click','--name','开始资料准备');browser('snapshot','-i');wait('preparationView',lambda x:isinstance(x,dict))
    for slot,text in [('need_summary','SYNTHETIC request'),('material_outline','SYNTHETIC private material body')]:
        revision=value('preparationView.preparation.revision');browser('select','#prep-slot',slot);browser('fill','#prep-text',text);browser('fill','#prep-source-label','SYNTHETIC fixture document v1');browser('find','role','button','click','--name','追加材料版本');browser('snapshot','-i');wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>revision)
    click('[data-tab=collaboration]');switch(specialists['prep-specialist-fixture-a']);prep_select(goal);prep_act('#prep-correction')
    switch(sessions['fixture-a']);prep_select(goal)
    revision=value('preparationView.preparation.revision');browser('select','#prep-slot','material_outline');browser('fill','#prep-text','SYNTHETIC corrected private material body');browser('fill','#prep-source-label','SYNTHETIC fixture document v2');browser('find','role','button','click','--name','追加材料版本');browser('snapshot','-i');wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>revision)
    switch(specialists['prep-specialist-fixture-a']);prep_select(goal);prep_act('#prep-review')
    switch(sessions['fixture-a']);prep_select(goal);parent=prep_act('#prep-confirm')['preparation']
    screenshot('materials-corrected-confirmed.png','#prep-detail')
    # Resource APIs have no Case/ServicePlan binding. This is test correlation only.
    click('[data-tab=resource]');click('#resource-catalog');wait("document.querySelector('#resource-form').hidden",lambda x:x is False)
    resources=value("Array.from(document.querySelector('#resource-select').options).map(o=>o.value)");assert len(resources)==2
    start=value("document.querySelector('#resource-start').value");end=value("document.querySelector('#resource-end').value");holds=[]
    for resource in resources:
        browser('select','#resource-select',resource)
        browser('eval','--stdin',stdin="for(const [id,value] of "+json.dumps([['resource-start',start],['resource-end',end]])+" ){const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}));}undefined")
        browser('fill','#resource-quantity','1');browser('fill','#resource-ttl','300');browser('fill','#resource-purpose',goal)
        click('#resource-preview');wait('resourcePreview',lambda x:isinstance(x,dict));assert value('resourcePreview.view.available') is True
        previous=value("document.querySelector('#resource-current article')?.dataset.holdId||null")
        click('#resource-hold');fresh=wait("({id:document.querySelector('#resource-current article')?.dataset.holdId||null,body:document.querySelector('#resource-current').textContent})",lambda x:bool(x['id']) and x['id']!=previous and x['id'] not in holds and '短期占位有效' in x['body']);holds.append(fresh['id'])
    click('#resource-mine');wait("document.querySelector('#resource-hold-items').textContent",lambda x:all(h in value("Array.from(document.querySelectorAll('#resource-hold-items article')).map(a=>a.dataset.holdId)") for h in holds))
    for h in holds:click('[data-combination-hold="'+h+'"]')
    click('#combination-confirm');wait("document.querySelector('#combination-items').textContent",lambda x:'两资源均本地合成确认' in x)
    combination=value("document.querySelector('#combination-items article').dataset.combinationId")
    resource_state=value("resourceCall('/api/resource-combinations/'+"+json.dumps(combination)+")")
    assert resource_state['combination']['state']=='CONFIRMED' and all(h['state']=='CONFIRMED' for h in resource_state['combination']['members'])
    screenshot('resources-confirmed.png','#combination-items')
    # Only the original enterprise can read its combination; other tenant sees no IDs.
    switch(sessions['fixture-b']);click('#combination-mine');wait("document.querySelector('#combination-items').textContent",lambda x:bool(x));assert combination not in value("document.querySelector('#combination-items').textContent")
    status=value("(async()=>{const r=await fetch('/api/resource-combinations/"+combination+"',{headers:{Authorization:'Bearer '+document.querySelector('#token').value}});return r.status;})()");assert status==403
    switch(sessions['fixture-a']);click('[data-tab=collaboration]');prep_select(goal)
    # Explicit fixture-owner setup of this new synthetic Run. No app assignment API.
    owner.assign_status('receipt-executor-fixture-a',uuid.UUID(parent['run_id']),active=True)
    click('#receipt-prepare');wait("document.querySelector('#receipt-create').hidden",lambda x:x is False)
    browser('find','role','button','click','--name','建立合成回执步骤');browser('snapshot','-i');initial=wait('receiptView',lambda x:isinstance(x,dict));id=initial['step']['id']
    switch(executors['receipt-executor-fixture-a']);receipt_select(goal)
    assert value("document.querySelector('#receipt-decisions').hidden") is True
    assert value("document.querySelector('#prep-materials').textContent")==''
    first=submit('<script>globalThis.BAD_RECEIPT=true</script> SYNTHETIC work log','SYNTHETIC work log v1; manual test correlation '+combination);assert first['step']['state']=='RECEIPT_RECORDED'
    assert not value('Boolean(globalThis.BAD_RECEIPT||document.querySelector("#receipt-current script"))');screenshot('executor-recorded.png')
    # API retries are evaluated independently of the real UI actions.
    status=value("(async()=>{const r=await fetch('/api/executor-receipts/"+id+"/commands',{method:'POST',headers:{Authorization:'Bearer '+document.querySelector('#token').value,'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({action:'ACKNOWLEDGE',expected_revision:2,receipt_sha256:receiptView.current_receipt.source_sha256,reason:'SYNTHETIC invalid executor decision'})});return r.status;})()")
    assert status==403
    switch(sessions['fixture-a']);receipt_select(goal);corrected=decision('#receipt-correct','SYNTHETIC please clarify the local log');assert corrected['step']['state']=='CHANGES_REQUESTED';screenshot('enterprise-correction.png')
    switch(executors['receipt-executor-fixture-a']);receipt_select(goal);submit('SYNTHETIC corrected local work log','SYNTHETIC work log v2')
    switch(sessions['fixture-a']);receipt_select(goal);acked=decision('#receipt-ack','SYNTHETIC checked current receipt only');assert acked['step']['state']=='LOCAL_ACKNOWLEDGED';screenshot('enterprise-acknowledged.png')
    reopened=decision('#receipt-reopen','SYNTHETIC further local check required');assert reopened['step']['state']=='AWAITING_RECEIPT'
    switch(executors['receipt-executor-fixture-a']);receipt_select(goal);latest=submit('SYNTHETIC reopened local work log','SYNTHETIC work log v3')
    assert len(latest['receipt_history'])==3 and len(latest['history'])==7
    assert latest['offline_fulfillment']=='NO_EVIDENCE' and latest['external_acceptance']=='NOT_SUBMITTED' and not latest['case_goal_completed']
    browser('reload');browser('snapshot','-i');switch(sessions['fixture-a']);click('[data-tab=collaboration]');loaded=receipt_select(goal);assert loaded['step']['revision']==7
    switch(sessions['fixture-b']);click('#receipt-list');wait("document.querySelector('#receipt-items').textContent",lambda x:bool(x));assert goal not in value("document.querySelector('#receipt-items').textContent")
    switch(sessions['fixture-a']);receipt_select(goal)
    metrics=[]
    for width in (320,390):
        browser('set','viewport',str(width),'844');browser('snapshot','-i');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['scroll']<=m['width'];metrics.append(m);screenshot('receipt-'+str(width)+'.png')
    browser('set','viewport','1200','900');screenshot('receipt-final.png');assert not browser('errors')
    # Receipt completion never cancels/consumes the resource reservation automatically.
    check=value("(async()=>{const r=await fetch('/api/resource-combinations/"+combination+"',{headers:{Authorization:'Bearer '+document.querySelector('#token').value}});return await r.json();})()");assert check['combination']['state']=='CONFIRMED'
    run=value("(async()=>{const r=await fetch('/api/runs/"+parent['run_id']+"',{headers:{Authorization:'Bearer '+document.querySelector('#token').value}});return await r.json();})()");assert run['case']['state']=='NEEDS_INPUT'
    click('[data-tab=resource]');click('#combination-mine');wait("document.querySelector('[data-combination-cancel=\""+combination+"\"]')!==null",lambda x:x is True);click('[data-combination-cancel="'+combination+'"]');wait("document.querySelector('#combination-feedback').textContent",lambda x:'已整组取消' in x)
    check=value("resourceCall('/api/resource-combinations/'+"+json.dumps(combination)+")");assert check['combination']['state']=='CANCELLED' and all(h['state']=='RELEASED' for h in check['combination']['members'])
    screenshot('resources-explicitly-cancelled.png','#combination-items')
    report=dict(scope='BOUNDED_SYNTHETIC_CROSS_MODULE_REPLAY',environment='Linux Chromium/local API/worker/PostgreSQL',manual_test_correlation_only=True,automatic_Case_ServicePlan_resource_binding=False,combination_id=combination,hold_ids=holds,resources_confirmed_during_receipt=True,explicit_cleanup_both_released=True,material_correction_before_confirmation=True,Case_state=run['case']['state'],step_id=id,run_id=parent['run_id'],case_id=parent['case_id'],three_roles_real_UI=True,fixture_owner_assignment_outside_UI=True,receipt_versions=3,history_events=7,correction_acknowledgement_reopen=True,executor_decision_denied=True,cross_enterprise_isolated=True,identity_clears_private_views=True,script_text_only=True,reload_persistent=True,narrow_viewports=metrics,model_calls=0,real_budget=0,F1='UNACCEPTED',F2='NOT_PASSED',R4='DISABLED',native_Windows='NOT_RUN',whole_AT_EX='NOT_RUN')
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
finally:browser('close')
