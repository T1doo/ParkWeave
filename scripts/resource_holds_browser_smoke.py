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
cmd=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','parkweave-resource-holds','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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
    sessions=json.loads((root/'.runtime/synthetic-sessions.json').read_text());a=sessions['fixture-a'];b=sessions['fixture-b'];capture('service-desktop');capture('service-mobile',390);browser('set','viewport','1200','900')
    suffix=uuid.uuid4().hex[:8];purposeA='<script>globalThis.RESOURCE_BAD=true</script> SYNTHETIC A '+suffix;purposeB='SYNTHETIC B '+suffix
    switch(a);catalog();start=value("document.querySelector('#resource-start').value");end=value("document.querySelector('#resource-end').value")
    fill_window(start,end,2,120,purposeA);precheck=check_available(True);idA=create_hold();capture('resource-held',focus='#resource-current')
    stateA=value("resourceCall('/api/resource-holds/'+"+json.dumps(idA)+")")
    assert value("document.querySelector('#resource-hold').disabled") is True
    browser('eval',"document.querySelector('#resource-hold').click();undefined")
    own=value("resourceCall('/api/resource-holds')")
    assert len([h for h in own['items'] if h['purpose']==purposeA])==1

    assert stateA['hold']['state']=='HELD' and stateA['reservation']=='NOT_CONFIRMED' and stateA['offline_fulfillment']=='NO_EVIDENCE'
    assert value('Boolean(globalThis.RESOURCE_BAD||document.querySelector("#resource-current script"))') is False
    browser('click','#resource-current [data-resource-action=confirm]');browser('snapshot','-i')
    wait("document.querySelector('#resource-current').textContent",lambda x:'本地合成确认' in x)
    confirmed=value("resourceCall('/api/resource-holds/'+"+json.dumps(idA)+")")
    assert confirmed['hold']['state']=='CONFIRMED' and confirmed['hold']['local_confirmation']=='CONFIRMED'
    assert confirmed['hold']['expires_at']==stateA['hold']['expires_at'] and confirmed['external_acceptance']=='NOT_SUBMITTED'
    assert value("document.querySelector('#resource-current [data-resource-action=confirm]')===null") is True
    capture('resource-confirmed-desktop',focus='#resource-current');capture('resource-confirmed-320',320,'#resource-current');capture('resource-confirmed-390',390,'#resource-current');browser('set','viewport','1200','900')

    switch(b);assert value("document.querySelector('#resource-current').textContent")=='';catalog();fill_window(start,end,1,120,purposeB)
    blocked=check_available(False);assert blocked['view']['occupied_peak']==2;capture('resource-capacity-warning',focus='#resource-preview-result')
    assert idA not in json.dumps(blocked) and purposeA not in json.dumps(blocked)
    text=mine(None);assert purposeA not in text
    switch(a);browser('click','[data-tab=resource]');browser('snapshot','-i');mine(idA)
    browser('click',f'#resource-hold-items article[data-hold-id="{idA}"] button');browser('snapshot','-i')
    wait("document.querySelector('#resource-hold-items article[data-hold-id=\""+idA+"\"]').textContent",lambda x:'占位已释放' in x)
    capture('resource-cancelled',focus='#resource-hold-items')
    switch(b);catalog();fill_window(start,end,2,5,purposeB);check_available(True);idB=create_hold()
    expired=wait("resourceCall('/api/resource-holds/'+"+json.dumps(idB)+")",lambda x:x['hold']['state']=='EXPIRED',timeout=15)
    assert expired['reservation']=='NOT_CONFIRMED'
    text=mine(idB);assert '占位已过期' in text and purposeA not in text
    mine(idB);browser('reload');browser('snapshot','-i');assert value("document.querySelector('#token').value")==''
    switch(b);browser('click','[data-tab=resource]');browser('snapshot','-i');text=mine(idB);assert '占位已过期' in text and purposeB in text
    catalog();fill_window(start,end,2,120,'SYNTHETIC expiry freed capacity');vacancy=check_available(True);assert vacancy['view']['occupied_peak']==0
    mine(idB);narrow=[]
    for width in (320,390):
        browser('set','viewport',str(width),'844');browser('snapshot','-i');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['scroll']<=m['width'];narrow.append(m)
    browser('set','viewport','1200','900');browser('screenshot',str(root/'.runtime'/(args.report.stem+'-resources.png')));capture('resource-expired',focus='#resource-hold-items')
    switch('SYNTHETIC-invalid-session');browser('click','#resource-catalog');browser('snapshot','-i')
    wait("document.querySelector('#resource-error').textContent",lambda x:'权限' in x)
    assert value("document.querySelector('#resource-hold-items').textContent")==''
    capture('resource-permission-error',focus='#page-feedback')
    switch(sessions['fixture-c']);catalog_empty=browser('click','#resource-catalog');browser('snapshot','-i');wait("document.querySelector('#resource-catalog-view').textContent",lambda x:'没有可读' in x);capture('resource-empty',focus='#resource-catalog-view')
    switch(a);catalog();fill_window(start,end,1,120,'SYNTHETIC · 团队协作时段');check_available(True);clean_id=create_hold()
    browser('click','#resource-current [data-resource-action=confirm]');browser('snapshot','-i');wait("document.querySelector('#resource-current').textContent",lambda x:'本地合成确认' in x)
    capture('resource-confirmed-readable',focus='#resource-current');capture('resource-confirmed-readable-mobile',390,'#resource-current')
    browser('click','#resource-current [data-resource-action=release]');browser('snapshot','-i');wait("document.querySelector('#resource-current').textContent",lambda x:'占位已释放' in x)

    browser('click','[data-tab=service]');browser('click','[data-tab=resource]');browser('snapshot','-i');assert value("document.querySelector('#resource-form').hidden") is True
    errors=browser('errors');assert not errors,errors
    report={'scope':'F2_PARALLEL_SYNTHETIC_SINGLE_RESOURCE_CONFIRM_ONLY','two_enterprises_real_UI':True,'hold_ids':[idA,idB],
      'preview_then_explicit_hold':True,'anonymous_capacity_conflict':True,'other_enterprise_ids_and_purpose_hidden':True,
      'owner_release':True,'disabled_repeat_hold_click_no_duplicate':True,'screenshots':shots,'return_navigation_clears_old_resource_form':True,'explicit_single_resource_local_confirm':True,'confirm_preserves_hold_deadline_history':True,'confirmed_capacity_blocks_other_enterprise':True,'local_cancel_frees_capacity':True,'TTL5_expired_by_actual_DB_clock_no_cleaner':True,'expiry_frees_capacity':True,
      'repeated_read_and_reload':True,'identity_change_and_invalid_session_clear_UI':True,'script_text_only':True,'narrow_viewports':narrow,
      'native_datetime_picker_gestures':'NOT_RUN; native values plus input events','browser_errors':0,'model_calls':0,'real_budget':0,'reservation':'NOT_CONFIRMED','external_acceptance':'NOT_SUBMITTED',
      'offline_fulfillment':'NO_EVIDENCE','native_Windows':'NOT_RUN','whole_AT_EX':'NOT_RUN','F1':'IN_PROGRESS','F2_admission':'NOT_PASSED','R4':'DISABLED'}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
finally:browser('close')
