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
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','pw-request-save','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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
def main():
    grants_before=permissions_digest()
    sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());specialists=json.loads((root/'.runtime/preparation-sessions.json').read_text())
    browser('open','http://127.0.0.1:8765');switch(sessions['fixture-a']);click('[data-tab=service]');click('#prep-catalog');wait('prepCatalog',lambda x:isinstance(x,dict))
    goal='SYNTHETIC ENG085 原始诉求 '+uuid.uuid4().hex[:8];browser('fill','#prep-goal',goal);click('#prep-create button')
    parent=wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['goal']==goal)['preparation']
    x=open_parent(parent);assert not x['request_intent']['recorded'] and not value("document.querySelector('#request-local-goal').checked")
    assert '覆盖未知' in value("document.querySelector('#request-intent-status').textContent")
    # Explicit empty goals are persisted as UNKNOWN, never silently promoted.
    browser('fill','#request-current','SYNTHETIC 当前诉求用户修订');x=submit_request(x['preparation_revision']);assert x['request_intent']['coverage']['state']=='UNKNOWN'
    click('#plan-preview-button');preview=wait('planPreview',lambda x:isinstance(x,dict));assert preview['state']=='UNKNOWN' and not preview['can_adopt']
    click('#request-local-goal');browser('fill','#plan-required-goals','必须外部机构受理回执');assert value('planPreview') is None
    x=submit_request(x['preparation_revision']);assert x['request_intent']['coverage']['state']=='PARTIAL'
    before=state_digest();versions=plan_versions();click('#plan-preview-button');preview=wait('planPreview',lambda x:isinstance(x,dict))
    assert preview['state']=='PARTIAL' and not preview['can_adopt'] and preview['unsupported_goals']==['必须外部机构受理回执']
    assert state_digest()==before and plan_versions()==versions
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];viewport_checks.append(metric);screenshot('saved-partial-'+str(width)+'.png');value("(()=>{document.querySelector('#request-intent-status').scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/('saved-coverage-state-'+str(width)+'.png')))
    browser('set','viewport','1200','900');browser('reload');switch(sessions['fixture-a']);x=open_parent(parent)
    assert x['request_intent']['original_request']==goal and x['request_intent']['current_request']=='SYNTHETIC 当前诉求用户修订'
    assert value("document.querySelector('#plan-required-goals').value")=='必须外部机构受理回执' and x['request_intent']['coverage']['state']=='PARTIAL'
    # Specialist can see necessary coverage state, never the owner-only draft or history text.
    switch(specialists['prep-specialist-fixture-a']);specialist=open_parent(parent)
    assert specialist['request_intent'] is None and specialist['request_coverage_state']=='PARTIAL' and value("document.querySelector('#request-intent-form').hidden")
    assert '必须外部机构受理回执' not in value("document.querySelector('#plan-detail').textContent")
    switch(sessions['fixture-a']);x=open_parent(parent);browser('fill','#plan-required-goals','');x=submit_request(x['preparation_revision'])
    click('#plan-preview-button');preview=wait('planPreview',lambda x:isinstance(x,dict));assert preview['can_adopt']
    # Changing the request clears the valid preview and hides adoption until saved and re-previewed.
    browser('fill','#request-current','SYNTHETIC 再次修订的当前诉求');assert value('planPreview') is None and value("document.querySelector('#plan-create').hidden")
    click('#plan-preview-button');wait("document.querySelector('#plan-error').textContent",lambda x:'先保存' in x)
    x=submit_request(x['preparation_revision']);click('#plan-preview-button');wait('planPreview',lambda x:isinstance(x,dict) and x['can_adopt']);click('#plan-create')
    plan=wait('planView',lambda x:isinstance(x,dict) and x.get('plan_id'));assert plan['revision']==1 and not plan['case_goal_completed']
    # Keep the adopted plan/history; save a newly unmet goal and read true incomplete state.
    browser('fill','#plan-required-goals','新必需目标：真实线下履约');plan=submit_request(plan['preparation_revision'])
    assert plan['request_intent']['coverage']['state']=='PARTIAL' and plan['state']=='BLOCKED' and plan['revision']==1 and len(plan['history'])==1
    assert 'EXISTING_RUN_ASSIGNMENT_REQUIRED' in next(s for s in plan['steps'] if s['id']=='P3')['issues'];screenshot('adopted-plan-after-uncovered-goal.png')
    # Commit then lose its response; retry must reuse the original key and append exactly one event.
    with owner.connect() as c:events_before=c.execute("SELECT count(*) n FROM preparation_events WHERE preparation_id=%s AND action='UPDATE_REQUEST'",(parent['id'],)).fetchone()['n']
    browser('fill','#request-current','SYNTHETIC 丢响应后的已保存诉求')
    value("(()=>{window.savedRequestFetch=window.fetch;window.dropRequestReply=true;window.fetch=async(p,o)=>{const r=await window.savedRequestFetch(p,o);if(String(p).endsWith('/request-intent')&&window.dropRequestReply){window.dropRequestReply=false;throw Error('SYNTHETIC_LOST_REQUEST_RESPONSE');}return r;};return true;})()")
    click('#request-save');wait("document.querySelector('#plan-error').textContent",lambda x:'SYNTHETIC_LOST_REQUEST_RESPONSE' in x)
    x=submit_request(plan['preparation_revision']);value("(()=>{window.fetch=window.savedRequestFetch;return true;})()")
    with owner.connect() as c:assert c.execute("SELECT count(*) n FROM preparation_events WHERE preparation_id=%s AND action='UPDATE_REQUEST'",(parent['id'],)).fetchone()['n']==events_before+1
    # The save really commits, but a late response after switching identity cannot restore private UI.
    browser('fill','#request-current','SYNTHETIC 迟到已保存诉求')
    value("(()=>{window.delayedRequestFetch=window.fetch;window.releaseRequestReply=null;window.fetch=async(p,o)=>{const r=await window.delayedRequestFetch(p,o);if(String(p).endsWith('/request-intent'))await new Promise(resolve=>window.releaseRequestReply=resolve);return r;};return true;})()")
    click('#request-save');wait('typeof releaseRequestReply',lambda x:x=='function');switch(specialists['prep-specialist-fixture-a']);specialist=open_parent(parent)
    value("(()=>{window.fetch=window.delayedRequestFetch;window.releaseRequestReply();return true;})()");browser('snapshot','-i');assert value('planView.role')=='park_specialist' and value('planView.request_intent') is None and value("document.querySelector('#request-current').value")==''

    browser('reload');switch(sessions['fixture-a']);x=open_parent(parent)
    assert x['request_intent']['current_request']=='SYNTHETIC 迟到已保存诉求' and x['request_intent']['coverage']['state']=='PARTIAL' and x['revision']==1
    assert permissions_digest()==grants_before and not browser('errors')
    with owner.connect() as c:
        state=c.execute('SELECT goal,state FROM cases WHERE id=%s',(parent['case_id'],)).fetchone();assert state['goal']==goal and state['state']=='NEEDS_INPUT'
        assert not c.execute('SELECT 1 FROM run_assignments WHERE run_id=%s',(parent['run_id'],)).fetchone()
    report={'scope':'REAL_NEW_CASE_PERSISTENT_EXPLICIT_REQUEST_AND_GOAL_COVERAGE','case_id':str(parent['case_id']),'preparation_id':str(parent['id']),'plan_id':x['plan_id'],'request_revision':x['request_intent']['revision'],'plan_revision':x['revision'],'original_request_preserved':True,'empty_explicit_goals_stay_unknown':True,'unsupported_goal_saved_partial':True,'page_reload_restores_request_goals_coverage':True,'dirty_request_discards_preview_and_blocks_adoption':True,'specialist_private_intent_hidden':True,'changes_after_adoption_preserve_history':True,'lost_save_response_same_key_replay_one_event':True,'late_committed_save_after_identity_change_not_projected':True,'case_state':'NEEDS_INPUT','case_goal_completed':False,'p3_access_missing':True,'new_run_assignments':False,'permissions_digest_before':grants_before,'permissions_digest_after':permissions_digest(),'viewport_checks':viewport_checks,'model_calls':0,'budget':0}
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
try:main()
finally:browser('close')
