"""Existing Case plan navigation: real roles, Back, late reads and version binding.
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
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','pw-plan-nav','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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
    before=state_digest();versions_before=plan_versions()
    with owner.connect() as c:
        parents=[c.execute('SELECT id,run_id,case_id,goal,revision FROM preparations WHERE case_id=%s',(case,)).fetchone() for case in (args.case_id,args.second_case_id)]
    assert all(parents)
    sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());executors=json.loads((root/'.runtime/receipt-sessions.json').read_text());specialists=json.loads((root/'.runtime/preparation-sessions.json').read_text())
    browser('open','http://127.0.0.1:8765');browser('snapshot','-i');switch(sessions['fixture-a']);click('[data-tab=collaboration]')
    value("(()=>{window.sourceFetch=window.fetch;window.writeRequests=0;window.fetch=(p,o)=>{if(o?.method&&o.method!=='GET')window.writeRequests++;return window.sourceFetch(p,o);};return true;})()")
    first=receipt_plan(parents[0]['goal']);assert first['role']=='enterprise_operator' and value('prepRole') is None
    if args.expect_before:
        click('#plan-materials');wait('preparationView',lambda x:isinstance(x,dict));observed=value("({role:prepRole,enterpriseEvidenceHidden:document.querySelector('#prep-evidence').hidden,specialistReviewVisible:!document.querySelector('#prep-review').hidden,caseId:preparationView.preparation.case_id})")
        assert observed['role'] is None and observed['enterpriseEvidenceHidden'] and observed['specialistReviewVisible'] and observed['caseId']==str(args.case_id)
        screenshot('before-enterprise-wrong-controls.png')
        assert state_digest()==before and value('writeRequests')==0
        args.report.write_text(json.dumps({'scope':'REAL_EXISTING_CASE_BEFORE_FIX','observed':observed,'business_write_requests':0,'business_and_grants_unchanged':True},ensure_ascii=False,indent=2)+'\n');return
    materials('enterprise_operator',parents[0]);screenshot('enterprise-return-correct-materials.png')
    # Collapsing a plan entered from a receipt retains that receipt, then re-entering reads current API.
    first=receipt_plan(parents[0]['goal']);receipt_before=value('receiptView');click('#plan-back')
    assert value('planView') is None and value("document.querySelector('#plan-detail').hidden") and value('receiptView')==receipt_before
    click('#plan-from-receipt');wait('planView',lambda x:isinstance(x,dict));materials('enterprise_operator',parents[0])
    # A pending refresh is visibly cancellable; the late real response cannot reopen the collapsed plan.
    first=receipt_plan(parents[0]['goal']);hold_plan();click('#plan-refresh');wait('typeof releasePlan',lambda x:x=='function')
    assert not value("document.querySelector('#plan-detail').hidden") and value("document.querySelector('#plan-materials').hidden") and value('planView') is None
    screenshot('pending-plan-cancellable.png');click('#plan-back');release_plan()
    assert value('planView') is None and value("document.querySelector('#plan-detail').hidden")
    click('#plan-from-receipt');wait('planView',lambda x:isinstance(x,dict));materials('enterprise_operator',parents[0])
    # Cancel a pending genuine material read from the same workspace and reopen the current plan.
    first=receipt_plan(parents[0]['goal']);assert first['preparation_revision']==parents[0]['revision']
    value(r"(()=>{window.priorFetch=window.fetch;window.releaseMaterials=null;window.fetch=async(p,o)=>{const r=await window.priorFetch(p,o);if(/\/api\/preparations\/[^/]+$/.test(String(p)))await new Promise(resolve=>window.releaseMaterials=resolve);return r;};return true;})()")
    click('#plan-materials');wait('typeof releaseMaterials',lambda x:x=='function')
    assert not value("document.querySelector('#plan-material-loading').hidden") and value('preparationView') is None
    browser('set','viewport','320','844');value("(()=>{document.querySelector('#plan-material-loading').scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/'pending-materials-cancellable-320.png'))
    value("(()=>{window.fetch=window.priorFetch;return true;})()");click('#plan-material-cancel');wait('planView',lambda x:isinstance(x,dict));value("(()=>{window.releaseMaterials();return true;})()");browser('snapshot','-i')
    assert value('preparationView') is None and value('planView.preparation_id')==str(parents[0]['id']) and value("document.querySelector('#plan-material-loading').hidden")
    browser('set','viewport','1200','900');materials('enterprise_operator',parents[0])
    # Hold a material read across a genuine role switch, then enter the specialist's existing dispatch.
    first=receipt_plan(parents[0]['goal'])
    value(r"(()=>{window.priorFetch=window.fetch;window.releaseMaterials=null;window.fetch=async(p,o)=>{const r=await window.priorFetch(p,o);if(/\/api\/preparations\/[^/]+$/.test(String(p)))await new Promise(resolve=>window.releaseMaterials=resolve);return r;};return true;})()")
    click('#plan-materials');wait('typeof releaseMaterials',lambda x:x=='function');switch(specialists['prep-specialist-fixture-a'])
    value("(()=>{window.fetch=window.priorFetch;window.releaseMaterials();return true;})()");browser('snapshot','-i')
    assert value('preparationView') is None and value('prepRole') is None and not value("document.querySelector('#prep-materials').textContent")
    dispatch_select(parents[0]['goal']);click('#plan-from-dispatch');specialist=wait('planView',lambda x:isinstance(x,dict))
    assert specialist['role']=='park_specialist' and specialist.get('source_snapshots') is None
    materials('park_specialist',parents[0]);screenshot('specialist-return-correct-materials.png')
    browser('set','viewport','320','844');value("(()=>{document.querySelector('#prep-decision').scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/'specialist-correct-controls-320.png'));browser('set','viewport','1200','900')
    # Execution role has no material route and may return only to its actual assigned dispatch.
    switch(executors['receipt-executor-fixture-a']);executor=receipt_plan(parents[0]['goal'])
    assert executor['role']=='service_executor' and value("document.querySelector('#plan-materials').hidden")
    assert all(not step['can_check'] for step in executor.get('steps',[]));screenshot('executor-plan-no-materials.png')
    click('#plan-dispatch');dispatch=wait('dispatchView',lambda x:isinstance(x,dict));assert dispatch['role']=='service_executor' and dispatch['preparation_id']==str(parents[0]['id'])
    # Plan reads held across Case/identity changes preserve the new authorized selection.
    switch(sessions['fixture-a']);first=receipt_plan(parents[0]['goal']);hold_plan();click('#plan-refresh');wait('typeof releasePlan',lambda x:x=='function')
    value("(()=>{window.fetch=window.priorFetch;return true;})()");preparation_select(parents[1]);click('#plan-prepare');second=wait('planView',lambda x:isinstance(x,dict));release_plan()
    assert value('planView.preparation_id')==str(parents[1]['id']);materials('enterprise_operator',parents[1]);screenshot('second-case-return-correct-materials.png')
    # Local Case -> plan -> collapse restores this same Case by a fresh read, including during pending refresh.
    preparation_select(parents[0]);click('#local-case-prepare');local=wait('localCaseView',lambda x:isinstance(x,dict));click('#local-case-plan');wait('planView',lambda x:isinstance(x,dict))
    hold_plan();click('#plan-refresh');wait('typeof releasePlan',lambda x:x=='function');click('#plan-back');wait('localCaseView',lambda x:isinstance(x,dict));release_plan()
    assert value('localCaseView.case_id')==str(args.case_id) and value('planView') is None and not value("document.querySelector('#local-case-detail').hidden")
    assert value('localCaseView.revision')==local['revision'];screenshot('collapse-restores-current-local-case.png')
    # Switch identity during a plan read, then re-enter specialist plan; old result cannot replace it.
    first=receipt_plan(parents[0]['goal']);hold_plan();click('#plan-refresh');wait('typeof releasePlan',lambda x:x=='function');switch(specialists['prep-specialist-fixture-a'])
    value("(()=>{window.fetch=window.priorFetch;return true;})()");dispatch_select(parents[0]['goal']);click('#plan-from-dispatch');wait('planView',lambda x:isinstance(x,dict));release_plan()
    assert value('planView.role')=='park_specialist';materials('park_specialist',parents[0])
    # Workspace switch cancels a pending plan without restoring private rows or old actions.
    dispatch_select(parents[0]['goal']);click('#plan-from-dispatch');wait('planView',lambda x:isinstance(x,dict));hold_plan();click('#plan-refresh');wait('typeof releasePlan',lambda x:x=='function');click('[data-tab=resource]');release_plan()
    assert value('planView') is None and value('preparationView') is None and value("document.querySelector('#plan-detail').hidden")
    click('[data-tab=collaboration]');switch(sessions['fixture-a']);receipt_plan(parents[0]['goal']);materials('enterprise_operator',parents[0])
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');browser('snapshot','-i');metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];viewport_checks.append({'stage':'enterprise-materials',**metric});screenshot('enterprise-materials-'+str(width)+'.png')
        value("(()=>{document.querySelector('#prep-evidence').scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/('enterprise-controls-'+str(width)+'.png')))
        first=receipt_plan(parents[0]['goal']);metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];viewport_checks.append({'stage':'enterprise-plan',**metric});screenshot('enterprise-plan-'+str(width)+'.png');materials('enterprise_operator',parents[0])
    versions_after=plan_versions();assert versions_after['version_checked_digest']==versions_before['version_checked_digest'] and versions_after['events_digest']==versions_before['events_digest']
    assert state_digest()==before and value('writeRequests')==0 and not browser('errors')
    report={'scope':'REAL_EXISTING_CASE_PLAN_NAVIGATION_ONLY','case_id':str(args.case_id),'second_case_id':str(args.second_case_id),'three_real_roles':True,'enterprise_receipt_plan_materials_correct':True,'specialist_dispatch_plan_materials_correct':True,'executor_no_material_route':True,'collapse_receipt_preserved_and_reentered':True,'pending_plan_visible_and_cancellable':True,'late_real_plan_after_collapse_ignored':True,'late_real_material_read_identity_cleared':True,'same_workspace_material_cancel_returns_fresh_plan':True,'current_plan_preparation_revision_bound':True,'late_real_plan_other_case_preserved':True,'local_case_collapse_fresh_same_case':True,'late_real_plan_new_role_preserved':True,'workspace_switch_clears_pending_plan':True,'business_write_requests':0,'business_and_grants_digest_before':before,'business_and_grants_digest_after':state_digest(),'controlled_plan_before':versions_before,'controlled_plan_after':versions_after,'controlled_plan_revision_checked_and_events_unchanged':True,'viewport_checks':viewport_checks,'models':0,'budget':0}
    raw=json.loads(browser('eval','--stdin',stdin=Path(__file__).with_name('controlled_plan_race_oracle.js').read_text()))
    ordered=json.loads(raw) if isinstance(raw,str) else raw
    assert all(ordered['checks'].values()) and not browser('errors')
    ordered.update(scope='SYNTHETIC_RESPONSE_ORDER_ONLY',business_API_calls=0,backend_authorization_tested=False)
    args.report.with_name(args.report.stem+'-controlled-order.json').write_text(json.dumps(ordered,ensure_ascii=False,indent=2)+'\n')
    report['controlled_response_order_report']=str(args.report.with_name(args.report.stem+'-controlled-order.json'))
    report['controlled_response_order_checks']=len(ordered['checks'])
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
try:main()
finally:browser('close')
