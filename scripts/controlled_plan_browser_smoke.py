"""Real Chromium/local API/worker/PG, three synthetic roles, no external execution."""
from pathlib import Path
import argparse,json,os,subprocess,time,uuid
from parkweave.process_env import minimal_environment
from parkweave.store import Store
root=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--report',required=True,type=Path);p.add_argument('--screenshots',required=True,type=Path);args=p.parse_args()
if os.name=='nt':raise RuntimeError('NOT_RUN: Linux harness is not native Windows evidence')
owner=Store(os.environ['PARKWEAVE_CASE_FIXTURE_OWNER_DSN'])
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
candidates=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2'];assert candidates
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','parkweave-controlled-plan','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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
    value("(()=>{const panel=document.querySelector('#plan-detail:not([hidden])')||document.querySelector('#receipt-detail:not([hidden])');if(panel)panel.scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/name))
def plan_check(step):
    revision=value('planView.revision');browser('fill','#plan-reason','SYNTHETIC explicit '+step+' dependency recheck');click('#plan-'+step)
    return wait('planView',lambda x:isinstance(x,dict) and x['revision']>revision)
try:
    sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());specialists=json.loads((root/'.runtime/preparation-sessions.json').read_text());executors=json.loads((root/'.runtime/receipt-sessions.json').read_text())
    browser('open','http://127.0.0.1:8765');browser('snapshot','-i');switch(sessions['fixture-a'])
    goal='SYNTHETIC controlled template '+uuid.uuid4().hex[:8]
    click('#prep-catalog');wait('prepCatalog',lambda x:isinstance(x,dict));browser('fill','#prep-goal',goal);browser('find','role','button','click','--name','开始资料准备');browser('snapshot','-i');wait('preparationView',lambda x:isinstance(x,dict))
    click('#plan-prepare');wait('planView',lambda x:isinstance(x,dict));revision=value('planView.preparation_revision');click('#request-local-goal');click('#request-save');wait('planView',lambda x:isinstance(x,dict) and x['preparation_revision']>revision);click('#plan-materials');wait('preparationView',lambda x:isinstance(x,dict))
    for slot,text in [('need_summary','SYNTHETIC request'),('material_outline','SYNTHETIC private material body')]:
        revision=value('preparationView.preparation.revision');browser('select','#prep-slot',slot);browser('fill','#prep-text',text);browser('fill','#prep-source-label','SYNTHETIC fixture document v1');browser('find','role','button','click','--name','追加材料版本');browser('snapshot','-i');wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>revision)
    click('[data-tab=collaboration]');switch(specialists['prep-specialist-fixture-a']);prep_select(goal);prep_act('#prep-review')
    switch(sessions['fixture-a']);prep_select(goal);parent=prep_act('#prep-confirm')['preparation']
    click('#plan-prepare');wait('planView',lambda x:isinstance(x,dict) and x['state']=='NOT_STARTED');click('#plan-preview-button');wait('planPreview',lambda x:isinstance(x,dict) and x['can_adopt']);click('#plan-create');cold=wait('planView',lambda x:isinstance(x,dict) and x['revision']==1);assert cold['state']=='BLOCKED' and 'EXISTING_RUN_ASSIGNMENT_REQUIRED' in next(x for x in cold['steps'] if x['id']=='P3')['issues'];screenshot('owner-missing-assignment-blocked.png')
    # Explicit fixture-owner setup of this new synthetic Run. No app assignment API.
    owner.assign_status('receipt-executor-fixture-a',uuid.UUID(parent['run_id']),active=True)
    click('#plan-refresh');wait('planView',lambda x:isinstance(x,dict) and x['state']=='IN_PROGRESS');plan_check('P1');screenshot('owner-materials-current.png')
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
    click('[data-tab=collaboration]');prep_select(goal);click('#case-resource-load');wait('caseResourceView',lambda x:isinstance(x,dict))
    browser('select','#case-resource-choice',combination);browser('fill','#case-resource-reason','SYNTHETIC explicit Case binding');browser('find','role','button','click','--name','确认此Case资源关联');browser('snapshot','-i');wait('caseResourceView',lambda x:isinstance(x,dict) and x['link_revision']==1)
    click('#plan-prepare');wait('planView',lambda x:isinstance(x,dict));plan_check('P2')
    switch(specialists['prep-specialist-fixture-a']);prep_select(goal);click('#dispatch-prepare');wait('dispatchView',lambda x:isinstance(x,dict) and x['revision']==0)
    browser('fill','#dispatch-offer-reason','SYNTHETIC task offered');click('#dispatch-offer-button');wait('dispatchView',lambda x:isinstance(x,dict) and x['revision']==1)
    switch(executors['receipt-executor-fixture-a']);click('#dispatch-list');wait("document.querySelector('#dispatch-items').textContent",lambda x:goal in x);browser('find','role','button','click','--name',goal);browser('snapshot','-i');wait('dispatchView',lambda x:isinstance(x,dict))
    browser('fill','#dispatch-decision-reason','SYNTHETIC accepted');click('#dispatch-accept');accepted=wait('dispatchView',lambda x:isinstance(x,dict) and x['revision']==2);click('#dispatch-receipt');wait('receiptView',lambda x:isinstance(x,dict))
    click('#plan-from-receipt');executor=wait('planView',lambda x:isinstance(x,dict));assert executor['source_snapshots'] is None and executor['goal'] is None and value("document.querySelector('#plan-materials').hidden") is True;screenshot('executor-minimal-read-only.png')
    switch(sessions['fixture-a']);receipt_select(goal);click('#plan-from-receipt');wait('planView',lambda x:isinstance(x,dict));plan_check('P3')
    switch(executors['receipt-executor-fixture-a']);receipt_select(goal);submit('SYNTHETIC task work log','SYNTHETIC log v1')
    switch(sessions['fixture-a']);receipt_select(goal);decision('#receipt-ack','SYNTHETIC enterprise checked current log');click('#plan-from-receipt');wait('planView',lambda x:isinstance(x,dict));final=plan_check('P4');assert final['state']=='LOCAL_RECORDS_CHECKED' and final['revision']==5 and len(final['history'])==5 and not final['case_goal_completed'];screenshot('owner-four-steps-checked.png')
    switch(specialists['prep-specialist-fixture-a']);prep_select(goal);click('#plan-prepare');reviewer=wait('planView',lambda x:isinstance(x,dict));assert reviewer['source_snapshots'] is None and reviewer['goal'] is None and all(x['source_sha256'] is None and not x['can_check'] for x in reviewer['steps']);screenshot('reviewer-minimal-read-only.png')
    switch(sessions['fixture-a']);receipt_select(goal);click('#plan-from-receipt');wait('planView',lambda x:isinstance(x,dict))
    with owner.connect() as c:
        owner.lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    try:
        click('#plan-refresh');invalid=wait('planView',lambda x:isinstance(x,dict) and x['steps'][1]['state']=='NEEDS_RECHECK');assert invalid['steps'][0]['state']=='CURRENT';screenshot('owner-observed-revocation.png')
    finally:
        with owner.connect() as c:
            owner.lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE synthetic_resource_grants SET active=true WHERE principal_id='fixture-a' AND capability='HOLD'")
    click('#plan-refresh');restored=wait('planView',lambda x:isinstance(x,dict) and x['steps'][1]['can_check']);assert restored['steps'][1]['state']=='NEEDS_RECHECK'
    for step in ('P2','P3','P4'):final=plan_check(step)
    assert final['revision']==8 and final['state']=='LOCAL_RECORDS_CHECKED' and len(final['history'])==8
    metrics=[]
    for width in (320,390):
        browser('set','viewport',str(width),'844');browser('snapshot','-i');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['scroll']<=m['width'];metrics.append(m);screenshot('plan-'+str(width)+'.png')
    browser('set','viewport','1200','900');browser('reload');browser('snapshot','-i');switch(sessions['fixture-a']);click('[data-tab=collaboration]');receipt_select(goal);click('#plan-from-receipt');reloaded=wait('planView',lambda x:isinstance(x,dict));assert reloaded['revision']==8 and len(reloaded['history'])==8;screenshot('owner-rechecked-reload.png')
    with owner.connect() as c:
        assert c.execute('SELECT state FROM service_receipt_steps WHERE id=%s',(uuid.UUID(accepted['receipt_step_id']),)).fetchone()['state']=='LOCAL_ACKNOWLEDGED'
        assert c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=%s',(uuid.UUID(combination),)).fetchone()['state']=='CONFIRMED'
        assert c.execute('SELECT state FROM service_dispatch_offers WHERE id=%s',(uuid.UUID(accepted['current_offer']['id']),)).fetchone()['state']=='ACCEPTED'
        assert c.execute('SELECT state FROM cases WHERE id=%s',(uuid.UUID(parent['case_id']),)).fetchone()['state']=='NEEDS_INPUT'
    switch(sessions['fixture-b']);click('#receipt-list');wait("document.querySelector('#receipt-items').textContent",lambda x:bool(x));assert goal not in value("document.querySelector('#receipt-items').textContent") and value('planView') is None
    assert not browser('errors')
    report=dict(scope='SYNTHETIC_FIXED_FOUR_STEP_TEMPLATE_ONLY',environment='Linux Chromium/local API/worker/PostgreSQL',preparation_id=parent['id'],case_id=parent['case_id'],three_roles_real_UI=True,resources_created_and_bound_via_UI=True,fixture_owner_assignment_outside_UI=True,missing_assignment_initially_BLOCKED=True,application_creates_no_grants=True,plan_revision=8,events=8,case_state='NEEDS_INPUT',case_goal_completed=False,explicit_revalidation_after_observed_revocation=True,responsibility_resources_receipt_preserved=True,counterparties_minimal_read_only=True,cross_enterprise_isolated=True,reload_persistent=True,narrow_viewports=metrics,screenshots_directory=str(args.screenshots),model_calls=0,real_budget=0,F1='UNACCEPTED',F2='NOT_PASSED',R4='DISABLED',native_Windows='NOT_RUN',whole_AT_EX='NOT_RUN')
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
finally:browser('close')
