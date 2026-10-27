"""New Case preview and explicit adoption using existing enterprise authority.
Requires an already running local synthetic fixture and existing assignments.
No seed, grant mutation, external network or model call. Creates one synthetic Case and adopts its fixed plan explicitly.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,time,uuid
from parkweave.process_env import minimal_environment
from parkweave.store import Store
root=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--report',required=True,type=Path);p.add_argument('--screenshots',required=True,type=Path);args=p.parse_args()
if os.name=='nt':raise RuntimeError('NOT_RUN: Linux harness is not native Windows evidence')
owner=Store(os.environ['PARKWEAVE_CASE_FIXTURE_OWNER_DSN'])
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
candidates=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2'];assert candidates
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','pw-plan-preview','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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



def preparation_select(parent):
    click('#prep-list');wait("document.querySelector('#prep-items').textContent",lambda x:parent['goal'] in x)
    name=value("Array.from(document.querySelectorAll('#prep-items button')).find(x=>x.textContent.startsWith("+json.dumps(parent['goal'])+")).textContent")
    browser('find','role','button','click','--name',name);browser('snapshot','-i');return wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['id']==str(parent['id']))





def permissions_digest():
    with owner.connect() as c:
        data={t:sorted(json.dumps(dict(r),sort_keys=True,default=str) for r in c.execute('SELECT * FROM '+t)) for t in ('run_assignments','capability_grants','preparation_grants','synthetic_resource_grants')}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

def main():
    grants_before=permissions_digest()
    sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());specialists=json.loads((root/'.runtime/preparation-sessions.json').read_text())
    browser('open','http://127.0.0.1:8765');switch(sessions['fixture-a'])
    click('[data-tab=service]');click('#prep-catalog');wait('prepCatalog',lambda x:isinstance(x,dict))
    goal='SYNTHETIC ENG084 新输入方案预览 '+uuid.uuid4().hex[:8]
    browser('fill','#prep-goal',goal);click('#prep-create button');detail=wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['goal']==goal)
    parent=detail['preparation'];assert parent['revision']==1 and parent['state']=='IN_PREPARATION'
    click('[data-tab=collaboration]');preparation_select(parent);click('#plan-prepare');wait('planView',lambda x:isinstance(x,dict))
    assert value("document.querySelector('#plan-create').hidden") and value('planPreview') is None
    guard=value("(async()=>{try{await planWrite(null);return 'UNEXPECTED';}catch(e){return e.message;}})()");assert '请先预览' in guard
    before=state_digest();versions=plan_versions()
    click('#request-local-goal');browser('fill','#plan-required-goals','需要外部机构受理回执');revision=value('planView.preparation_revision');click('#request-save');wait('planView',lambda x:isinstance(x,dict) and x['preparation_revision']>revision);before=state_digest();versions=plan_versions();click('#plan-preview-button');x=wait('planPreview',lambda x:isinstance(x,dict))
    assert x['state']=='PARTIAL' and x['unsupported_goals']==['需要外部机构受理回执'] and not x['can_adopt']
    assert value("document.querySelector('#plan-create').hidden") and '需要外部机构受理回执' in value("document.querySelector('#plan-preview-result').textContent")
    assert state_digest()==before and plan_versions()==versions
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');browser('snapshot','-i');metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];viewport_checks.append(metric);screenshot('uncovered-goal-preview-'+str(width)+'.png')
    browser('set','viewport','1200','900');browser('fill','#plan-required-goals','');assert value('planPreview') is None
    revision=value('planView.preparation_revision');click('#request-save');wait('planView',lambda x:isinstance(x,dict) and x['preparation_revision']>revision);before=state_digest();versions=plan_versions();click('#plan-preview-button');x=wait('planPreview',lambda x:isinstance(x,dict));assert x['can_adopt'] and not x['unsupported_goals']
    assert 'EXISTING_RUN_ASSIGNMENT_REQUIRED' in x['steps'][2]['issues'] and not x['executed'] and not x['persisted']
    assert all(k in value("document.querySelector('#plan-preview-result').textContent") for k in ('责任：','前置：','产出：','验收：','没有已有合法Run访问'))
    assert state_digest()==before and plan_versions()==versions;screenshot('supported-preview-with-blocked-acceptance.png')
    for index,name in ((0,'preview-material-step.png'),(2,'preview-blocked-run-step.png')):
        value("(()=>{document.querySelectorAll('#plan-preview-result article')["+str(index)+"].scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/name))
    # An actual delayed preview cannot reappear after an actual identity switch.
    value("(()=>{window.previewFetch=window.fetch;window.releasePreview=null;window.fetch=async(p,o)=>{const r=await window.previewFetch(p,o);if(String(p).endsWith('/controlled-plan/preview'))await new Promise(resolve=>window.releasePreview=resolve);return r;};return true;})()")
    click('#plan-preview-button');wait('typeof releasePreview',lambda x:x=='function');switch(specialists['prep-specialist-fixture-a'])
    value("(()=>{window.fetch=window.previewFetch;window.releasePreview();return true;})()");browser('snapshot','-i');assert value('planPreview') is None and value("document.querySelector('#plan-preview-result').textContent")==''
    switch(sessions['fixture-a']);preparation_select(parent);click('#plan-prepare');wait('planView',lambda x:isinstance(x,dict));click('#plan-preview-button');wait('planPreview',lambda x:isinstance(x,dict));click('#plan-create')
    plan=wait('planView',lambda x:isinstance(x,dict) and x.get('plan_id'))
    assert plan['preparation_id']==str(parent['id']) and plan['revision']==1 and len(plan['history'])==1
    assert not plan['case_goal_completed'] and plan['state']!='LOCAL_RECORDS_CHECKED'
    assert 'EXISTING_RUN_ASSIGNMENT_REQUIRED' in next(s for s in plan['steps'] if s['id']=='P3')['issues']
    click('#plan-refresh');fresh=wait('planView',lambda x:isinstance(x,dict));assert fresh['plan_id']==plan['plan_id'] and fresh['revision']==1
    screenshot('adopted-plan-incomplete.png')
    assert permissions_digest()==grants_before and not browser('errors')
    with owner.connect() as c:
        assert not c.execute('SELECT 1 FROM run_assignments WHERE run_id=%s',(parent['run_id'],)).fetchone()
        state=c.execute('SELECT state FROM cases WHERE id=%s',(parent['case_id'],)).fetchone()['state']
    assert state=='NEEDS_INPUT'
    report={'scope':'REAL_NEW_SYNTHETIC_CASE_PREVIEW_AND_EXPLICIT_ADOPTION','case_id':str(parent['case_id']),'preparation_id':str(parent['id']),'plan_id':plan['plan_id'],'new_case_materials_empty':True,'unsupported_required_goal_preserved':True,'preview_no_business_or_plan_mutation':True,'current_inputs_responsibility_outputs_acceptance_visible':True,'late_real_identity_preview_discarded':True,'explicit_adoption_revision':plan['revision'],'refresh_same_plan':True,'case_state':state,'case_goal_completed':False,'p3_existing_run_access_missing':True,'permissions_digest_before':grants_before,'permissions_digest_after':permissions_digest(),'new_assignments':False,'viewport_checks':viewport_checks,'model_calls':0,'budget':0}
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
try:main()
finally:browser('close')
