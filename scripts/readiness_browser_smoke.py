"""Source-bound readiness on a real new Case with existing enterprise and assigned reviewer authority.
Requires an already running local synthetic fixture and existing assignments.
No seed, grant mutation, external network or model call. Creates one synthetic Case; never establishes Run access.
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
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','pw-readiness','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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

def open_parent(parent):
    click('[data-tab=collaboration]');preparation_select(parent);click('#plan-prepare');return wait('planView',lambda x:isinstance(x,dict))
def submit_request(expected_revision):
    click('#request-save');return wait('planView',lambda x:isinstance(x,dict) and x['preparation_revision']>expected_revision)
def material(slot,text):
    browser('select','#prep-slot',slot);browser('fill','#prep-text',text);browser('fill','#prep-source-label','SYNTHETIC user document v1')
    rev=value('preparationView.preparation.revision');click('#prep-evidence button');wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>rev);wait('readinessView',lambda x:isinstance(x,dict) and x['preparation_revision']>rev)
def decision(button,reason):
    browser('fill','#prep-reason',reason);rev=value('preparationView.preparation.revision');click(button);wait('readinessView',lambda x:isinstance(x,dict) and x['preparation_revision']>rev)
def assess_current(truth):
    old=len(value('readinessView.history'));click('#readiness-assess');return wait('readinessView',lambda x:isinstance(x,dict) and len(x['history'])>old and x['current_truth']==truth)
def capture(name):
    value("(()=>{document.querySelector('#readiness-panel').scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/name))
def main():
    before=permissions_digest();sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());specialists=json.loads((root/'.runtime/preparation-sessions.json').read_text());executors=json.loads((root/'.runtime/receipt-sessions.json').read_text())
    browser('open','http://127.0.0.1:8765');switch(sessions['fixture-a']);click('[data-tab=service]');click('#prep-catalog');wait('prepCatalog',lambda x:isinstance(x,dict))
    goal='SYNTHETIC ENG086 source readiness '+uuid.uuid4().hex[:8];browser('fill','#prep-goal',goal);click('#prep-create button');parent=wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['goal']==goal)['preparation'];wait('readinessView',lambda x:isinstance(x,dict))
    assert value('readinessView.current_truth')=='UNKNOWN';x=assess_current('UNKNOWN');assert x['current_inputs']['missing_slots']==['need_summary','material_outline']
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];viewport_checks.append(metric);capture('missing-unknown-'+str(width)+'.png')
    browser('set','viewport','1200','900');switch(specialists['prep-specialist-fixture-a']);click('[data-tab=collaboration]');preparation_select(parent);wait('readinessView',lambda x:isinstance(x,dict));decision('#prep-correction','SYNTHETIC 两项材料必须补正');assert value('readinessView.state')=='STALE';x=assess_current('FALSE');capture('specialist-correction-false.png')
    switch(sessions['fixture-a']);preparation_select(parent);wait('readinessView',lambda x:isinstance(x,dict));assert value('readinessView.current_truth')=='FALSE';material('need_summary','SYNTHETIC 用户明确提交的诉求摘要');material('material_outline','SYNTHETIC 文档目录摘录');assert value('readinessView.current_truth')=='UNKNOWN';x=assess_current('UNKNOWN')
    switch(specialists['prep-specialist-fixture-a']);preparation_select(parent);wait('readinessView',lambda x:isinstance(x,dict));decision('#prep-review','SYNTHETIC 仅核对当前本地资料包');x=assess_current('TRUE');assert x['latest']['result']['qualification_truth']=='UNKNOWN' and not x['business_publication'];assert '适用当前资料' in value("document.querySelector('#readiness-sources').textContent");capture('specialist-local-material-true.png')
    switch(sessions['fixture-a']);preparation_select(parent);wait('readinessView',lambda x:isinstance(x,dict));assert value('readinessView.current_truth')=='TRUE';material('need_summary','SYNTHETIC 修改后的诉求摘要');assert value('readinessView.state')=='STALE' and value('readinessView.latest.result.local_preparation_truth')=='TRUE' and value('readinessView.current_truth')=='UNKNOWN'
    assert '历史记录，当前不可沿用' in value("document.querySelector('#readiness-sources').textContent") and '等待获派专员人工核对' in value("document.querySelector('#readiness-sources').textContent")
    for width in (390,320):
        browser('set','viewport',str(width),'844');metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];viewport_checks.append(metric);capture('changed-old-true-stale-'+str(width)+'.png')
    browser('reload');switch(sessions['fixture-a']);click('[data-tab=collaboration]');preparation_select(parent);wait('readinessView',lambda x:isinstance(x,dict));assert value('readinessView.state')=='STALE' and len(value('readinessView.history'))==4;x=assess_current('UNKNOWN')
    # Commit once, lose the reply, then reuse the same key through the real UI.
    material('material_outline','SYNTHETIC 更新目录');old=len(value('readinessView.history'))
    value("(()=>{window.readinessFetch=window.fetch;window.dropReadiness=true;window.fetch=async(p,o)=>{const r=await readinessFetch(p,o);if(String(p).endsWith('/readiness')&&o.method==='POST'&&dropReadiness){dropReadiness=false;throw Error('SYNTHETIC_LOST_READINESS_REPLY');}return r;};return true;})()")
    click('#readiness-assess');wait("document.querySelector('#readiness-error').textContent",lambda x:'SYNTHETIC_LOST_READINESS_REPLY' in x);click('#readiness-assess');x=wait('readinessView',lambda x:isinstance(x,dict) and len(x['history'])==old+1);value("(()=>{window.fetch=readinessFetch;return true;})()")
    # A genuine committed late assessment cannot repopulate another identity's UI.
    material('need_summary','SYNTHETIC 再次修订');value("(()=>{window.lateReadinessFetch=window.fetch;window.releaseReadiness=null;window.fetch=async(p,o)=>{const r=await lateReadinessFetch(p,o);if(String(p).endsWith('/readiness')&&o.method==='POST')await new Promise(resolve=>releaseReadiness=resolve);return r;};return true;})()")
    click('#readiness-assess');wait('typeof releaseReadiness',lambda x:x=='function');switch(executors['receipt-executor-fixture-a']);value("(()=>{window.fetch=lateReadinessFetch;releaseReadiness();return true;})()");browser('snapshot','-i');assert value('readinessView') is None and value("document.querySelector('#readiness-sources').textContent")==''
    switch(sessions['fixture-a']);preparation_select(parent);x=wait('readinessView',lambda x:isinstance(x,dict));assert len(x['history'])==7 and x['current_truth']=='UNKNOWN'
    browser('reload');switch(specialists['prep-specialist-fixture-a']);click('[data-tab=collaboration]');preparation_select(parent);x=wait('readinessView',lambda x:isinstance(x,dict));assert len(x['history'])==7 and x['current_truth']=='UNKNOWN';capture('reload-shared-history.png')
    with owner.connect() as c:
        state=c.execute('SELECT state FROM cases WHERE id=%s',(parent['case_id'],)).fetchone()['state'];assert state=='NEEDS_INPUT'
        assert not c.execute('SELECT 1 FROM run_assignments WHERE run_id=%s',(parent['run_id'],)).fetchone()
    assert before==permissions_digest() and not browser('errors')
    report={'scope':'REAL_CASE_SOURCE_BOUND_MATERIAL_READINESS','case_id':str(parent['case_id']),'preparation_id':str(parent['id']),'history_count':len(x['history']),'current_truth':x['current_truth'],'case_state':state,'case_goal_completed':False,'missing_materials_unknown':True,'current_manual_correction_false':True,'local_manual_review_true_qualification_unknown':True,'material_change_stales_old_true':True,'reload_restores_history_and_staleness':True,'enterprise_assigned_specialist_share_sources':True,'lost_response_replay_exactly_one_assessment':True,'late_committed_response_after_identity_switch_hidden':True,'permissions_digest_before':before,'permissions_digest_after':permissions_digest(),'new_run_assignments':False,'viewport_checks':viewport_checks,'model_calls':0,'budget':0}
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
try:main()
finally:browser('close')
