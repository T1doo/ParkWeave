"""Real local synthetic resource UI; no formal/external booking or model calls."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import time
import uuid
from parkweave.process_env import minimal_environment

root=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--report',required=True,type=Path);p.add_argument('--screenshots-dir',type=Path);args=p.parse_args()
if os.name=='nt':raise RuntimeError('NOT_RUN: Linux browser harness is not Windows verification')
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
candidates=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2']
if not candidates:raise RuntimeError('cached approved agent-browser0.38.2 required; no install')
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','parkweave-resource-combinations','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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

shots=[]
def capture(name,width=1200,focus=None):
    if not args.screenshots_dir:return
    args.screenshots_dir.mkdir(parents=True,exist_ok=True)
    browser('set','viewport',str(width),'900' if width>600 else '844')
    if focus:browser('eval','document.querySelector('+json.dumps(focus)+').scrollIntoView({block:"center"});undefined')
    else:browser('eval','scrollTo(0,0);undefined')
    browser('snapshot','-i')
    path=args.screenshots_dir/(name+'.png');browser('screenshot',str(path))
    shots.append(str(path.relative_to(root)))


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

def catalog():
    browser('click','[data-tab=resource]');browser('snapshot','-i');browser('click','#resource-catalog');browser('snapshot','-i')
    wait("document.querySelector('#resource-form').hidden",lambda x:x is False)

def fill_window(start,end,qty,ttl,purpose):
    # Cached agent-browser fill clears native datetime-local controls (recorded).
    # Set native control values and dispatch real input events; picker gestures are NOT_RUN.
    browser('eval','--stdin',stdin="for(const [id,value] of "+json.dumps([['resource-start',start],['resource-end',end]])+" ){const el=document.getElementById(id);el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));}undefined")
    assert value("document.querySelector('#resource-start').value")==start and value("document.querySelector('#resource-end').value")==end
    browser('fill','#resource-quantity',str(qty));browser('fill','#resource-ttl',str(ttl));browser('fill','#resource-purpose',purpose)

def check_available(expected):
    browser('click','#resource-preview');browser('snapshot','-i')
    try:p=wait('resourcePreview',lambda x:isinstance(x,dict))
    except AssertionError:
        detail=value("({error:document.querySelector('#resource-error').textContent,window:resourceWindow(),draft:resourceDraft(),generation:resourceGeneration})")
        (root/'.runtime/eng018-browser-failure-state.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2)+'\n')
        raise
    assert p['view']['available'] is expected
    assert value("document.querySelector('#resource-hold').disabled") is not expected
    return p

def create_hold():
    browser('click','#resource-hold');browser('snapshot','-i')
    wait("document.querySelector('#resource-current').textContent",lambda x:'短期占位有效' in x)
    return value("document.querySelector('#resource-current article').dataset.holdId")

def mine(id):
    browser('click','#resource-mine');browser('snapshot','-i')
    return wait("document.querySelector('#resource-hold-items').textContent",lambda x:bool(x))

try:
    browser('open','http://127.0.0.1:8765');browser('snapshot','-i')
    sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());a=sessions['fixture-a'];b=sessions['fixture-b']
    switch(a);catalog();ids=value("Array.from(document.querySelector('#resource-select').options).map(o=>o.value)");assert len(ids)==2
    start=value("document.querySelector('#resource-start').value");end=value("document.querySelector('#resource-end').value")
    def create_pair(ttl=120):
        hs=[]
        for n,id in enumerate(ids):
            browser('select','#resource-select',id);fill_window(start,end,1,ttl if n==1 else 120,'SYNTHETIC · '+('协作空间' if n==0 else '研讨设备')+' '+uuid.uuid4().hex[:6]);check_available(True);hs.append(create_hold())
        return hs
    def select_pair(hs):
        mine(None)
        for id in hs:browser('click','[data-combination-hold="'+id+'"]');browser('snapshot','-i')
        assert value("document.querySelector('#combination-confirm').disabled") is False
    hs=create_pair();select_pair(hs);browser('click','#combination-confirm');browser('snapshot','-i')
    wait("document.querySelector('#combination-items').textContent",lambda x:'两资源均本地合成确认' in x)
    id=value("document.querySelector('#combination-items article').dataset.combinationId")
    original=value("resourceCall('/api/resource-combinations/'+"+json.dumps(id)+")")
    assert original['combination']['state']=='CONFIRMED' and all(h['state']=='CONFIRMED' for h in original['combination']['members'])
    assert original['reservation']=='NOT_CONFIRMED' and original['external_acceptance']=='NOT_SUBMITTED'
    assert value("document.querySelector('#combination-confirm').disabled") is True
    before_repeat=len(value("resourceCall('/api/resource-combinations')")['items'])
    browser('eval',"document.querySelector('#combination-confirm').click();undefined")
    assert len(value("resourceCall('/api/resource-combinations')")['items'])==before_repeat
    capture('combination-confirmed-desktop',focus='#combination-items');capture('combination-confirmed-320',320,'#combination-items');capture('combination-confirmed-390',390,'#combination-items');browser('set','viewport','1200','900')
    switch(b);catalog();fill_window(start,end,2,120,'SYNTHETIC · 另一企业容量检查');blocked=check_available(False)
    assert id not in json.dumps(blocked) and all(h not in json.dumps(blocked) for h in hs)
    browser('click','#combination-mine');browser('snapshot','-i');wait("document.querySelector('#combination-items').textContent",lambda x:'没有可读' in x)
    switch(a);catalog();browser('click','#combination-mine');browser('snapshot','-i')
    wait("document.querySelector('#combination-items [data-combination-id="+json.dumps(id)+"]').textContent",lambda x:'两资源均' in x)
    browser('click','[data-combination-cancel="'+id+'"]');browser('snapshot','-i');wait("document.querySelector('#combination-feedback').textContent",lambda x:'已整组取消' in x)
    cancelled=value("resourceCall('/api/resource-combinations/'+"+json.dumps(id)+")")
    assert cancelled['combination']['state']=='CANCELLED' and all(h['state']=='RELEASED' for h in cancelled['combination']['members'])
    capture('combination-cancelled',focus='#combination-items')
    for resource in ids:
        browser('select','#resource-select',resource);fill_window(start,end,2,120,'SYNTHETIC · 整组容量恢复');check_available(True)
    hs_exp=create_pair(ttl=5);select_pair(hs_exp)
    wait("resourceCall('/api/resource-holds/'+"+json.dumps(hs_exp[1])+")",lambda x:x['hold']['state']=='EXPIRED',timeout=15)
    browser('click','#combination-confirm');browser('snapshot','-i');wait("document.querySelector('#resource-error').textContent",lambda x:'不再可组合' in x or '已过期' in x)
    current=[value("resourceCall('/api/resource-holds/'+"+json.dumps(h)+")")['hold']['state'] for h in hs_exp]
    assert current==['HELD','EXPIRED']
    capture('combination-expired-failure',focus='#resource-error')
    browser('click','#resource-hold-items article[data-hold-id="'+hs_exp[0]+'"] [data-resource-action=release]');browser('snapshot','-i');wait("resourceCall('/api/resource-holds/'+"+json.dumps(hs_exp[0])+")",lambda x:x['hold']['state']=='RELEASED')
    browser('eval',"document.querySelector('[data-tab=service]').click();document.querySelector('[data-tab=resource]').click();undefined");browser('snapshot','-i')
    assert value('combinationSelection.size')==0 and value("document.querySelector('#combination-items').textContent")==''
    narrow=[]
    for width in (320,390):
        browser('set','viewport',str(width),'844');browser('snapshot','-i');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['scroll']<=m['width'];narrow.append(m)
    errors=browser('errors');assert not errors,errors
    report={'scope':'LOCAL_SYNTHETIC_TWO_RESOURCE_COMBINATION_ONLY','actual_PG_API_UI':True,'two_enterprises':True,
      'both_confirm_or_no_confirm':True,'whole_cancel_releases_both':True,'expiry_failure_keeps_original_hold_states':current,
      'other_enterprise_group_and_hold_ids_hidden':True,'disabled_repeat_click':True,'return_clears_selection_and_group':True,
      'screenshots':shots,'narrow_viewports':narrow,'browser_errors':0,'native_datetime_picker_gestures':'NOT_RUN; native values and input events',
      'reservation':'NOT_CONFIRMED','external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE',
      'LIVE':0,'budget':0,'Win11':'NOT_RUN','F1':'UNACCEPTED','F2':'NOT_PASSED','R4':'DISABLED','whole_AT_EX':'NOT_RUN'}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
finally:browser('close')
