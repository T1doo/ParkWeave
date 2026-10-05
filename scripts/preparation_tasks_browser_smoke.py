"""Personal task inbox: real local synthetic API/worker/PG, no model/provider."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import time
import uuid
from parkweave.process_env import minimal_environment

root=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--report',required=True,type=Path);args=p.parse_args()
if os.name=='nt':raise RuntimeError('NOT_RUN: Linux browser harness is not Windows verification')
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
candidates=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2']
if not candidates:raise RuntimeError('cached approved agent-browser0.38.2 required; no install')
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','parkweave-f2-tasks','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
def browser(*items,stdin=None):
    result=subprocess.run(cmd+list(items),input=stdin,capture_output=True,text=True,env=env,timeout=30)
    if result.returncode:raise RuntimeError('browser command failed: '+result.stderr)
    return result.stdout.strip()
def value(expression):
    data=json.loads(browser('eval','(async()=>JSON.stringify(await ('+expression+')))()'))
    return json.loads(data) if isinstance(data,str) else data

def wait(expression,predicate,timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        result=value(expression)
        if predicate(result):return result
        time.sleep(.1)
    raise AssertionError('SYNTHETIC browser readiness timeout: '+expression)

def switch(token):
    browser('eval','--stdin',stdin="document.querySelector('#token').value="+json.dumps(token)+";document.querySelector('#token').dispatchEvent(new Event('input'));undefined")
    assert value('preparationView') is None
    assert value("document.querySelector('#prep-history').textContent")==''
    browser('snapshot','-i')

def list_select(goal):
    browser('click','#prep-list');browser('snapshot','-i')
    wait("document.querySelector('#prep-items').textContent",lambda x:goal in x)
    # Semantic locator acts on the real listed button.
    browser('find','role','button','click','--name',goal+' · '+value("Array.from(document.querySelectorAll('#prep-items button')).find(x=>x.textContent.startsWith("+json.dumps(goal)+")).textContent.split(' · ')[1]"))
    browser('snapshot','-i');wait('preparationView',lambda x:isinstance(x,dict))

def act(button,reason):
    revision=value('preparationView.preparation.revision')
    browser('fill','#prep-reason',reason);browser('click',button);browser('snapshot','-i')
    return wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>revision)

def material(slot,text,label):
    revision=value('preparationView.preparation.revision')
    browser('select','#prep-slot',slot);browser('fill','#prep-text',text);browser('select','#prep-source-kind','DOCUMENT_EXCERPT');browser('fill','#prep-source-label',label)
    browser('find','role','button','click','--name','追加材料版本');browser('snapshot','-i')
    return wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>revision)

def task_list(goal,expected):
    browser('click','#prep-tasks');browser('snapshot','-i')
    wait("document.querySelector('#prep-task-items').textContent",lambda x:'待办' in x)
    text=value("document.querySelector('#prep-task-items').textContent")
    assert (goal in text)==expected,(goal,expected,text)
    return text

def open_task(goal):
    index=value("Array.from(document.querySelectorAll('#prep-task-items article')).findIndex(x=>x.textContent.includes("+json.dumps(goal)+"))+1")
    assert index>0
    browser('click',f'#prep-task-items article:nth-of-type({index}) button');browser('snapshot','-i')
    return wait('preparationView',lambda x:isinstance(x,dict))

def new_case(goal):
    browser('click','[data-tab=service]');browser('snapshot','-i')
    browser('click','#prep-catalog');browser('snapshot','-i');wait('prepCatalog',lambda x:isinstance(x,dict))
    browser('fill','#prep-goal',goal);browser('find','role','button','click','--name','开始资料准备');browser('snapshot','-i')
    return wait('preparationView',lambda x:isinstance(x,dict))

try:
    browser('open','http://127.0.0.1:8765');browser('snapshot','-i')
    enterprise=json.loads((root/'.runtime/synthetic-sessions.json').read_text())['fixture-a']
    specialist=json.loads((root/'.runtime/preparation-sessions.json').read_text())['prep-specialist-fixture-a']
    suffix=uuid.uuid4().hex[:8];goal='SYNTHETIC inbox A '+suffix;other='SYNTHETIC inbox B '+suffix
    switch(enterprise);a=new_case(goal);id=a['preparation']['id']
    material('need_summary','<script>globalThis.PARKWEAVE_TASK_BAD=true</script> SYNTHETIC PRIVATE MATERIAL','SYNTHETIC inbox source v1')
    b=new_case(other);assert b['current_materials']==[]
    browser('click','[data-tab=collaboration]');browser('snapshot','-i')
    initial=task_list(goal,True);assert other in initial and '待补材料：材料目录' in initial and 'PRIVATE MATERIAL' not in initial
    task_list(goal,True);assert open_task(goal)['preparation']['id']==id
    switch(specialist);task_list(goal,False);list_select(goal)
    act('#prep-correction','<script>globalThis.PARKWEAVE_TASK_BAD=true</script> SYNTHETIC 补目录')
    switch(enterprise);corrected=task_list(goal,True);assert '请回应专员补正' in corrected and 'SYNTHETIC 补目录' in corrected
    assert value('Boolean(globalThis.PARKWEAVE_TASK_BAD||document.querySelector("#prep-task-items script"))') is False
    open_task(goal);material('material_outline','SYNTHETIC two-role outline','SYNTHETIC outline v1')
    ready=task_list(goal,False);assert other in ready
    switch(specialist);assert '请人工核对资料包' in task_list(goal,True);open_task(goal)
    reviewed=act('#prep-review','SYNTHETIC 人工核对');assert reviewed['preparation']['state']=='REVIEWED'
    task_list(goal,False)
    switch(enterprise);assert '请确认本地资料准备' in task_list(goal,True);open_task(goal)
    confirmed=act('#prep-confirm','SYNTHETIC 本地资料确认');assert confirmed['preparation']['state']=='LOCAL_CONFIRMED'
    task_list(goal,False);browser('reload');browser('snapshot','-i');switch(enterprise)
    browser('click','[data-tab=collaboration]');browser('snapshot','-i');reloaded=task_list(goal,False);assert other in reloaded
    list_select(goal);reopened=act('#prep-reopen','SYNTHETIC 再核对');assert reopened['preparation']['state']=='IN_PREPARATION'
    history=len(reopened['history'])
    switch(specialist);task_list(goal,True);task_list(goal,True);state=open_task(goal)
    assert len(state['history'])==history and len(state['material_history'])==2
    assert state['qualification']=='NOT_EVALUATED' and state['external_acceptance']=='NOT_SUBMITTED' and state['offline_fulfillment']=='NO_EVIDENCE'
    narrow=[]
    for width in (320,390):
        browser('set','viewport',str(width),'844');browser('snapshot','-i')
        metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];narrow.append(metric)
    browser('set','viewport','1200','900');browser('screenshot',str(root/'.runtime/eng016-tasks.png'))
    switch('SYNTHETIC-invalid-session');browser('click','#prep-tasks');browser('snapshot','-i')
    wait("document.querySelector('#result').textContent",lambda x:'权限' in x)
    assert value("document.querySelector('#prep-task-items').textContent")==''
    switch(enterprise);task_list(other,True);list_select(goal)
    browser('fill','#prep-reason','SYNTHETIC invalid stale confirmation');browser('click','#prep-confirm');browser('snapshot','-i')
    wait("document.querySelector('#prep-error').textContent",lambda x:bool(x))
    assert value('preparationView.preparation.state')=='IN_PREPARATION'
    errors=browser('errors');assert not errors,errors
    report={'scope':'F2_PARALLEL_SYNTHETIC_PERSONAL_TASKS_ONLY','two_roles_real_UI':True,'two_case_ids':[id,b['preparation']['id']],
      'missing_materials_and_correction_visible':True,'material_bodies_not_in_task_list':True,'review_then_owner_confirm_then_disappear':True,
      'reopen_returns_reviewer_task':True,'reload_reads_persisted_tasks':True,'repeated_reads_leave_history_unchanged':True,
      'task_opens_current_detail':True,'invalid_identity_clears_tasks':True,'invalid_confirmation_rejected':True,'script_text_only':True,
      'narrow_viewports':narrow,'browser_errors':0,'model_calls':0,'real_budget':0,'native_Windows':'NOT_RUN','whole_AT_EX':'NOT_RUN','F1':'IN_PROGRESS','F2_admission':'NOT_PASSED','R4':'DISABLED'}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
finally:browser('close')
