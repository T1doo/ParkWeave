"""Historical Case template eligibility: existing records stay unchanged.
Requires an already running local synthetic fixture and existing assignments.
No seed, grant mutation, business command, external network or model call.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,time,uuid
from parkweave.process_env import minimal_environment
from parkweave.store import Store
root=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--case-id',required=True,type=uuid.UUID);p.add_argument('--second-case-id',required=True,type=uuid.UUID);p.add_argument('--report',required=True,type=Path);p.add_argument('--screenshots',required=True,type=Path);p.add_argument('--expect-before',action='store_true');args=p.parse_args()
if os.name=='nt':raise RuntimeError('NOT_RUN: Linux harness is not native Windows evidence')
owner=Store(os.environ['PARKWEAVE_CASE_FIXTURE_OWNER_DSN'])
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
candidates=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2'];assert candidates
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','pw-template-entry','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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
def screenshot(name):
    value("(()=>{const panel=document.querySelector('#plan-detail:not([hidden])')||document.querySelector('#local-case-detail:not([hidden])')||document.querySelector('#prep-detail:not([hidden])')||document.querySelector('#receipt-detail:not([hidden])');if(panel)panel.scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/name))



def state_digest():
    tables=('run_assignments','capability_grants','preparation_grants','synthetic_resource_grants','preparations','preparation_evidence','preparation_events','service_receipt_steps','service_step_receipts','service_receipt_events','synthetic_resource_holds','synthetic_resource_combinations','case_resource_links','resource_case_claims','case_local_lifecycles','case_local_events')
    with owner.connect() as c:
        rows={t:sorted(json.dumps(dict(r),sort_keys=True,default=str) for r in c.execute('SELECT * FROM '+t).fetchall()) for t in tables}
    return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()

def plan_versions():
    with owner.connect() as c:
        rows=[dict(r) for r in c.execute('SELECT preparation_id,id,revision,checked,invalidated_from,invalidated_at FROM controlled_plans ORDER BY preparation_id').fetchall()]
        events=[dict(r) for r in c.execute('SELECT * FROM controlled_plan_events ORDER BY id').fetchall()]
    stable=[{k:v for k,v in row.items() if k not in ('invalidated_from','invalidated_at')} for row in rows]
    digest=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()
    observations=[{'preparation_id':str(r['preparation_id']),'invalidated_from':r['invalidated_from'],'invalidated_at':str(r['invalidated_at']) if r['invalidated_at'] else None} for r in rows]
    return {'version_checked_digest':digest(stable),'events_digest':digest(events),'observations':observations}

def dispatch_select(goal):
    click('#dispatch-list');wait("document.querySelector('#dispatch-items').textContent",lambda x:goal in x)
    name=value("Array.from(document.querySelectorAll('#dispatch-items button')).find(x=>x.textContent==="+json.dumps(goal)+").textContent")
    browser('find','role','button','click','--name',name);browser('snapshot','-i');return wait('dispatchView',lambda x:isinstance(x,dict))

def receipt_plan(goal):
    receipt_select(goal);click('#plan-from-receipt');return wait('planView',lambda x:isinstance(x,dict))

def preparation_select(parent):
    click('#prep-list');wait("document.querySelector('#prep-items').textContent",lambda x:parent['goal'] in x)
    name=value("Array.from(document.querySelectorAll('#prep-items button')).find(x=>x.textContent.startsWith("+json.dumps(parent['goal'])+")).textContent")
    browser('find','role','button','click','--name',name);browser('snapshot','-i');return wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['id']==str(parent['id']))

def materials(expected,parent):
    click('#plan-materials');detail=wait('preparationView',lambda x:isinstance(x,dict))
    assert detail['preparation']['id']==str(parent['id']) and detail['preparation']['case_id']==str(parent['case_id'])
    assert detail['preparation']['revision']==parent['revision'] and value('prepRole')==expected
    enterprise=expected=='enterprise_operator'
    for selector in ('#prep-evidence','#prep-confirm','#prep-reopen','#case-resource-load'):
        assert value('document.querySelector('+json.dumps(selector)+').hidden')==(not enterprise)
    for selector in ('#prep-review','#prep-correction'):
        assert value('document.querySelector('+json.dumps(selector)+').hidden')==enterprise
    return detail

def hold_plan():
    value("(()=>{window.priorFetch=window.fetch;window.releasePlan=null;window.fetch=async(p,o)=>{const r=await window.priorFetch(p,o);if(String(p).endsWith('/controlled-plan'))await new Promise(resolve=>window.releasePlan=resolve);return r;};return true;})()")

def release_plan():
    value("(()=>{window.fetch=window.priorFetch;window.releasePlan();return true;})()");browser('snapshot','-i')


def main():
    before=state_digest();plan_before=plan_versions()
    with owner.connect() as c:
        parents=[c.execute('SELECT id,run_id,case_id,goal,revision FROM preparations WHERE case_id=%s',(case,)).fetchone() for case in (args.case_id,args.second_case_id)]
        parent=parents[0]
        existing=[bool(c.execute('SELECT 1 FROM '+table+' WHERE preparation_id=%s',(parent['id'],)).fetchone()) for table in ('case_resource_links','service_dispatches','service_receipt_steps')]
    assert all(parents) and all(existing)
    sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());executors=json.loads((root/'.runtime/receipt-sessions.json').read_text());specialists=json.loads((root/'.runtime/preparation-sessions.json').read_text())
    browser('open','http://127.0.0.1:8765');browser('snapshot','-i');switch(sessions['fixture-a']);click('[data-tab=collaboration]')
    value("(()=>{window.sourceFetch=window.fetch;window.writeRequests=0;window.fetch=(p,o)=>{if(o?.method&&o.method!=='GET')window.writeRequests++;return window.sourceFetch(p,o);};return true;})()")
    first=receipt_plan(parent['goal']);assert first['state']=='NOT_STARTED' and first['plan_id'] is None
    if args.expect_before:
        assert first['can_create'] and not value("document.querySelector('#plan-create').hidden")
        screenshot('before-historical-case-template-enabled.png')
        args.report.write_text(json.dumps({'scope':'REAL_HISTORICAL_CASE_BEFORE_TEMPLATE_ELIGIBILITY_FIX','can_create':first['can_create'],'existing_resource_dispatch_receipt':existing,'plan_id':first['plan_id'],'business_write_requests':value('writeRequests'),'business_and_grants_unchanged':state_digest()==before},ensure_ascii=False,indent=2)+'\n');return
    assert first['creation_blockers']==['EXISTING_CASE_RESOURCE_LINK','EXISTING_DISPATCH_RECORD','EXISTING_RECEIPT_RECORD'] and not first['can_create']
    assert value("document.querySelector('#plan-create').hidden")
    text=value("document.querySelector('#plan-next-action').textContent")
    assert all(t in text for t in ('已有资源关联','已有内部分派','已有回执','继续此Case','不会补启用')) and '新事项入口' not in value("document.querySelector('#plan-summary').textContent")
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');browser('snapshot','-i');metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];viewport_checks.append(metric);screenshot('historical-template-blocked-'+str(width)+'.png')
    browser('set','viewport','1200','900');materials('enterprise_operator',parent)
    click('#case-resource-load');wait('caseResourceView',lambda x:isinstance(x,dict));assert value('preparationId')==str(parent['id'])
    receipt_plan(parent['goal']);click('#plan-back');assert value('planView') is None;click('#plan-from-receipt');wait('planView',lambda x:isinstance(x,dict));assert not value('planView.can_create')
    switch(specialists['prep-specialist-fixture-a']);dispatch_select(parent['goal']);click('#plan-from-dispatch');specialist=wait('planView',lambda x:isinstance(x,dict));assert specialist['creation_blockers'] is None and not specialist['can_create'];assert '已有资源关联' not in value("document.querySelector('#plan-next-action').textContent");screenshot('specialist-template-minimal.png')
    switch(executors['receipt-executor-fixture-a']);executor=receipt_plan(parent['goal']);assert executor['creation_blockers'] is None and not executor['can_create'] and value("document.querySelector('#plan-materials').hidden");screenshot('executor-template-minimal.png')
    switch(sessions['fixture-a']);receipt_plan(parent['goal']);hold_plan();click('#plan-refresh');wait('typeof releasePlan',lambda x:x=='function');switch(specialists['prep-specialist-fixture-a']);value("(()=>{window.fetch=window.priorFetch;return true;})()");dispatch_select(parent['goal']);click('#plan-from-dispatch');wait('planView',lambda x:isinstance(x,dict));release_plan();assert value('planView.role')=='park_specialist' and value('planView.creation_blockers') is None
    switch(sessions['fixture-a']);receipt_plan(parent['goal']);hold_plan();click('#plan-refresh');wait('typeof releasePlan',lambda x:x=='function');value("(()=>{window.fetch=window.priorFetch;return true;})()");preparation_select(parents[1]);click('#plan-prepare');second=wait('planView',lambda x:isinstance(x,dict));release_plan();assert value('planView.preparation_id')==str(parents[1]['id']) and second['plan_id'] is not None
    assert second['revision']==8 and len(second['history'])==8;screenshot('existing-plan-keeps-history.png')
    plan_after=plan_versions();assert plan_before==plan_after and state_digest()==before and value('writeRequests')==0 and not browser('errors')
    report={'scope':'REAL_EXISTING_CASE_TEMPLATE_ELIGIBILITY_UI_ONLY','case_id':str(args.case_id),'second_case_id':str(args.second_case_id),'historical_enterprise_creation_blockers':first['creation_blockers'],'historical_case_cannot_create':not first['can_create'],'existing_resource_entry_still_same_case':True,'three_real_roles':True,'nonowner_no_private_creation_reasons':True,'collapse_and_reenter_keeps_blocked':True,'late_real_identity_does_not_reveal_blockers':True,'late_real_other_case_preserves_existing_plan':True,'existing_plan_revision_and_history_preserved':True,'business_write_requests':0,'business_and_grants_digest_before':before,'business_and_grants_digest_after':state_digest(),'controlled_plan_before':plan_before,'controlled_plan_after':plan_after,'viewport_checks':viewport_checks,'fresh_case_creation_UI_not_exercised':True,'model_calls':0,'budget':0}
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
try:main()
finally:browser('close')
