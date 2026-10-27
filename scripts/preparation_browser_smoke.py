"""Linux Chromium, actual local API/worker/PG, synthetic manual preparation only."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import time
import uuid
from parkweave.process_env import minimal_environment

root=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--report',required=True,type=Path);p.add_argument('--screenshots',type=Path);args=p.parse_args()
shots=args.screenshots or root/'.runtime'/('preparation-ui-'+uuid.uuid4().hex[:8]);shots.mkdir(parents=True,exist_ok=True)
if os.name=='nt':raise RuntimeError('NOT_RUN: Linux browser harness is not Windows verification')
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
candidates=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2']
if not candidates:raise RuntimeError('cached approved agent-browser0.38.2 required; no install')
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','parkweave-f2','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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

try:
    browser('open','http://127.0.0.1:8765');browser('snapshot','-i')
    browser('screenshot',str(shots/'f2-before.png'))
    enterprise=json.loads((root/'.runtime/synthetic-sessions.json').read_text())['fixture-a']
    specialist=json.loads((root/'.runtime/preparation-sessions.json').read_text())['prep-specialist-fixture-a']
    goal='SYNTHETIC browser material preparation '+uuid.uuid4().hex[:8]
    switch(enterprise);browser('click','#prep-catalog');browser('snapshot','-i');wait('prepCatalog',lambda x:isinstance(x,dict))
    browser('fill','#prep-goal',goal);browser('find','role','button','click','--name','开始资料准备');browser('snapshot','-i')
    initial=wait('preparationView',lambda x:isinstance(x,dict));id=initial['preparation']['id'];run=initial['preparation']['run_id']
    assert initial['preparation']['state']=='IN_PREPARATION' and initial['qualification']=='NOT_EVALUATED'
    material('need_summary','SYNTHETIC 企业希望整理诉求和材料','SYNTHETIC 用户提交摘录 v1')
    browser('click','[data-tab=collaboration]');browser('snapshot','-i');switch(specialist);list_select(goal)
    before=act('#prep-correction','SYNTHETIC 请补材料目录');assert before['preparation']['state']=='CHANGES_REQUESTED'
    switch(enterprise);list_select(goal)
    material('material_outline','SYNTHETIC 联系清单、事项概要；无资格声明','SYNTHETIC 测试材料目录 v1')
    switch(specialist);list_select(goal)
    reviewed=act('#prep-review','SYNTHETIC 专员仅核对当前资料包');assert reviewed['preparation']['state']=='REVIEWED'
    assert all(x['authenticity']=='UNVERIFIED' for x in reviewed['current_materials'])
    assert value("document.querySelector('#prep-materials').textContent").find('DOCUMENT_EXCERPT')>=0
    switch(enterprise);list_select(goal)
    confirmed=act('#prep-confirm','SYNTHETIC 企业确认本地资料准备');assert confirmed['preparation']['state']=='LOCAL_CONFIRMED'
    browser('screenshot',str(shots/'f2-confirmed.png'))
    browser('reload');browser('snapshot','-i');switch(enterprise);browser('click','[data-tab=collaboration]');browser('snapshot','-i');list_select(goal)
    assert value('preparationView.preparation.state')=='LOCAL_CONFIRMED'
    reopened=act('#prep-reopen','SYNTHETIC 新材料需要重新核对');assert reopened['preparation']['state']=='IN_PREPARATION'
    material('need_summary','<script>globalThis.PARKWEAVE_BAD=true</script> SYNTHETIC revised','SYNTHETIC 用户提交摘录 v2')
    assert value('Boolean(globalThis.PARKWEAVE_BAD||document.querySelector("#prep-materials script"))') is False
    assert value('preparationView.material_history.length')==3
    latest=value('preparationView');assert latest['preparation']['review_sha256'] is None and latest['external_acceptance']=='NOT_SUBMITTED' and latest['offline_fulfillment']=='NO_EVIDENCE'
    # Enterprise tries confirming stale/nonreviewed material: UI must display failure.
    browser('fill','#prep-reason','SYNTHETIC invalid confirmation');browser('click','#prep-confirm');browser('snapshot','-i')
    wait("document.querySelector('#prep-error').textContent",lambda x:bool(x))
    assert value('preparationView.preparation.state')=='IN_PREPARATION'
    narrow=[]
    for width in (320,390):
        browser('set','viewport',str(width),'844');browser('snapshot','-i')
        metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];narrow.append(metric)
    browser('set','viewport','1200','900');browser('screenshot',str(shots/'f2-final.png'))
    errors=browser('errors');assert not errors,errors
    report={'scope':'F2_PARALLEL_SYNTHETIC_ENGINEERING_ONLY','environment':'Linux Chromium/local API/independent worker/PG16.2 Python3.12.14','preparation_id':id,'run_id':run,'case_id':initial['preparation']['case_id'],'material_versions':3,'review_snapshot_sha256':reviewed['snapshot_sha256'],'confirmed_then_reopened':True,'history_retained':True,'reload_reads_persistent_state':True,'source_and_unverified_visible':True,'two_roles_via_real_UI':True,'stale_confirmation_rejected':True,'script_text_only':True,'identity_change_clears_material_UI':True,'narrow_viewports':narrow,'browser_errors':0,'screenshots_directory':str(shots),'model_calls':0,'real_budget':0,'native_Windows':'NOT_RUN','whole_AT_EX':'NOT_RUN','F1':'IN_PROGRESS','production_R4':'DISABLED','F2_admission':'NOT_PASSED'}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
finally:browser('close')
