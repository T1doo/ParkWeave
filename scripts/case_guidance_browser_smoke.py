"""Read-only existing Case guidance: real roles, blockers, navigation and stale reads.
Requires an already running local synthetic fixture and existing assignments.
No seed, grant mutation, business command, external network or model call.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,time,uuid
from parkweave.process_env import minimal_environment
from parkweave.store import Store
root=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--case-id',required=True,type=uuid.UUID);p.add_argument('--second-case-id',required=True,type=uuid.UUID);p.add_argument('--report',required=True,type=Path);p.add_argument('--screenshots',required=True,type=Path);args=p.parse_args()
if os.name=='nt':raise RuntimeError('NOT_RUN: Linux harness is not native Windows evidence')
owner=Store(os.environ['PARKWEAVE_CASE_FIXTURE_OWNER_DSN'])
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
candidates=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2'];assert candidates
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','parkweave-guidance-local','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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
    value("(()=>{const panel=document.querySelector('#local-case-detail:not([hidden])')||document.querySelector('#receipt-detail:not([hidden])');if(panel)panel.scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/name))



def select_preparation(parent):
    click('#prep-list');wait("document.querySelector('#prep-items').textContent",lambda x:parent['goal'] in x)
    name=value("Array.from(document.querySelectorAll('#prep-items button')).find(x=>x.textContent.startsWith("+json.dumps(parent['goal'])+")).textContent")
    browser('find','role','button','click','--name',name);browser('snapshot','-i')
    wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['id']==str(parent['id']))
    click('#local-case-prepare');return wait('localCaseView',lambda x:isinstance(x,dict) and x['case_id']==str(parent['case_id']))

def guidance():return value("document.querySelector('#local-case-checks').textContent")
def available_matches(local):
    for button,key in [('validate','can_revalidate'),('close','can_close_local_record'),('reopen','can_reopen')]:
        assert value("document.querySelector('#local-case-"+button+"').disabled")==(not local[key])

def state_digest():
    tables=('run_assignments','capability_grants','preparation_grants','synthetic_resource_grants','preparations','preparation_evidence','preparation_events','service_receipt_steps','service_step_receipts','service_receipt_events','synthetic_resource_holds','synthetic_resource_combinations','case_resource_links','resource_case_claims','case_local_lifecycles','case_local_events')
    with owner.connect() as c:
        rows={t:sorted(json.dumps(dict(r),sort_keys=True,default=str) for r in c.execute('SELECT * FROM '+t).fetchall()) for t in tables}
    return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()

try:
    before=state_digest()
    with owner.connect() as c:
        parents=[c.execute('SELECT id,run_id,case_id,goal FROM preparations WHERE case_id=%s',(case,)).fetchone() for case in (args.case_id,args.second_case_id)]
    assert all(parents)
    sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());executors=json.loads((root/'.runtime/receipt-sessions.json').read_text());specialists=json.loads((root/'.runtime/preparation-sessions.json').read_text())
    browser('open','http://127.0.0.1:8765');browser('snapshot','-i');switch(sessions['fixture-a']);click('[data-tab=collaboration]')
    value("(()=>{window.sourceFetch=window.fetch;window.writeRequests=0;window.fetch=(p,o)=>{if(o?.method&&o.method!=='GET')window.writeRequests++;return window.sourceFetch(p,o);};return true;})()")
    first=select_preparation(parents[0]);assert first['role']=='enterprise_operator'
    assert 'RESOURCE_WINDOW_ENDED' in first['checks']['RESOURCE_RECHECK']
    assert '原资源时段已结束' in guidance() and '企业经办人' in guidance() and '历史本地关闭记录保留' in guidance()
    assert 'RESOURCE_WINDOW_ENDED' not in guidance();available_matches(first)
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');browser('snapshot','-i')
        metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];viewport_checks.append(metric)
        screenshot('enterprise-guidance-'+str(width)+'.png')
        value("(()=>{document.querySelector('#local-case-checks article:last-of-type').scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(args.screenshots.resolve()/('enterprise-blocker-'+str(width)+'.png')))
    browser('set','viewport','1200','900')
    browser('find','role','button','click','--name','打开此Case的资料与资源关联入口');browser('snapshot','-i')
    wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['id']==str(parents[0]['id']))
    assert value('prepRole')=='enterprise_operator' and not value("document.querySelector('#case-resource-load').hidden")
    screenshot('enterprise-same-case-materials.png')
    click('#case-resource-load');wait('caseResourceView',lambda x:isinstance(x,dict));assert value('preparationId')==str(parents[0]['id'])
    click('#local-case-prepare');wait('localCaseView',lambda x:isinstance(x,dict))
    # An actual API read held until the other existing Case is fully rendered.
    value("(()=>{window.beforeHold=window.fetch;window.releaseCase=null;window.fetch=async(p,o)=>{const r=await window.beforeHold(p,o);if(String(p).endsWith('/local-case')&&String(p).includes("+json.dumps(str(parents[0]['id']))+")){await new Promise(resolve=>window.releaseCase=resolve);}return r;};return true;})()")
    click('#local-case-refresh');wait('typeof releaseCase',lambda x:x=='function')
    value("(()=>{window.fetch=window.beforeHold;return true;})()")
    second=select_preparation(parents[1]);value("(()=>{window.releaseCase();return true;})()");browser('snapshot','-i')
    assert value('localCaseView.case_id')==str(args.second_case_id) and parents[1]['goal'] in value("document.querySelector('#local-case-summary').textContent")
    assert second['case_state']=='NEEDS_INPUT' and '待补材料' in value("document.querySelector('#local-case-boundary').textContent")
    available_matches(second);screenshot('enterprise-second-case.png')
    # Hold another genuine read while the identity changes; no old private card survives.
    first=select_preparation(parents[0])
    value("(()=>{window.beforeHold=window.fetch;window.releaseCase=null;window.fetch=async(p,o)=>{const r=await window.beforeHold(p,o);if(String(p).endsWith('/local-case'))await new Promise(resolve=>window.releaseCase=resolve);return r;};return true;})()")
    click('#local-case-refresh');wait('typeof releaseCase',lambda x:x=='function');switch(executors['receipt-executor-fixture-a'])
    value("(()=>{window.fetch=window.beforeHold;window.releaseCase();return true;})()");browser('snapshot','-i')
    assert value('localCaseView') is None and guidance()==''
    receipt_select(parents[0]['goal']);click('#local-case-receipt');executor=wait('localCaseView',lambda x:isinstance(x,dict))
    assert executor['role']=='service_executor' and executor['checks'] is None
    assert '仅供企业经办人查看' in guidance() and '原资源时段已结束' not in guidance()
    assert '当前接单与回执' in guidance() and '人工核对当前材料' not in guidance()
    assert value("document.querySelector('#local-case-decision').hidden") and value("document.querySelectorAll('#local-case-checks button').length")==0
    available_matches(executor);screenshot('executor-minimal-guidance.png')
    switch(specialists['prep-specialist-fixture-a']);specialist=select_preparation(parents[0])
    assert specialist['role']=='park_specialist' and specialist['checks'] is None
    assert '仅供企业经办人查看' in guidance() and '原资源时段已结束' not in guidance()
    assert '人工核对当前材料' in guidance() and '接单与回执' not in guidance()
    available_matches(specialist);screenshot('specialist-minimal-guidance.png')
    browser('find','role','button','click','--name','打开此Case的获派资料入口');browser('snapshot','-i')
    wait('preparationView',lambda x:isinstance(x,dict));assert value('preparationId')==str(parents[0]['id']) and value('prepRole')=='park_specialist'
    assert value("document.querySelector('#case-resource-load').hidden") and value("document.querySelector('#prep-evidence').hidden")
    # Fixed safe fallbacks are projections only, not real permission-revocation evidence.
    switch(sessions['fixture-a']);current=select_preparation(parents[0]);real_text=guidance()
    value("(()=>{renderLocalCaseGuidance({...localCaseView,checks:{MATERIAL_REVIEW:['PRIVATE_FUTURE_CODE']}});return true;})()")
    assert 'PRIVATE_FUTURE_CODE' not in guidance() and '当前条件未满足' in guidance()
    value("(()=>{renderLocalCaseGuidance({...localCaseView,checks:null});return true;})()")
    assert '没有详细检查结果' in guidance()
    value("(()=>{renderLocalCaseGuidance(localCaseView);return true;})()");assert guidance()==real_text
    assert value('writeRequests')==0 and state_digest()==before and not browser('errors')
    assert not current['case_goal_completed'] and current['offline_fulfillment']=='NO_EVIDENCE'
    report={'scope':'EXISTING_SYNTHETIC_CASE_GUIDANCE_READ_ONLY','case_id':str(args.case_id),'second_case_id':str(args.second_case_id),'three_real_roles':True,'real_blockers':current['checks'],'current_buttons_match_can_flags':True,'same_case_materials_and_resource_entry':True,'specialist_materials_entry_role_correct':True,'executor_no_private_details_or_entry':True,'late_real_read_other_case_preserved':True,'late_real_read_identity_private_guidance_cleared':True,'unknown_reason_and_missing_checks_safe_projection_only':True,'business_write_requests':0,'business_and_grants_digest_before':before,'business_and_grants_digest_after':state_digest(),'viewport_checks':viewport_checks,'case_goal_completed':current['case_goal_completed'],'case_state':current['case_state'],'local_record_revision':current['revision'],'local_record_cycle':current['cycle'],'models':0,'budget':0}
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
finally:browser('close')
