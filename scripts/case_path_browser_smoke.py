"""Actual product Case path read-only browser checks; caller-owned local fixture.

Context is caller-provided via stdin, never logged or written to artifacts. No
assignment/grant setup, Mock approval, model call or product write command.
"""
from pathlib import Path
import argparse,json,os,subprocess,sys,time
from parkweave.process_env import minimal_environment
p=argparse.ArgumentParser();p.add_argument('--base-port',type=int,default=8774);p.add_argument('--report',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True);a=p.parse_args();context=json.load(sys.stdin);root=Path.cwd();assert 1024<=a.base_port<=65535
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
cached=[x for x in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(x.read_text()).get('version')=='0.38.2'];assert cached
cmd=['node',str(sorted(cached)[0].parent/'bin/agent-browser.js'),'--session','pw-product-case-path','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
def browser(*args,stdin=None):
    r=subprocess.run(cmd+list(args),input=stdin,capture_output=True,text=True,env=env,timeout=30)
    if r.returncode:raise RuntimeError('cached local product browser operation failed')
    return r.stdout.strip()
def value(expr):
    r=json.loads(browser('eval','(async()=>JSON.stringify(await ('+expr+')))()'));return json.loads(r) if isinstance(r,str) else r
def wait(expr,pred,timeout=20):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        x=value(expr)
        if pred(x):return x
        time.sleep(.1)
    raise AssertionError('product Case path browser timeout '+expr)
def click(selector):
    value("(()=>{window.pathClicks=0;const b=document.querySelector("+json.dumps(selector)+");b.addEventListener('click',()=>pathClicks++,{once:true});b.scrollIntoView({block:'center'});return true;})()")
    browser('snapshot','-i');browser('click',selector);browser('snapshot','-i');assert value('pathClicks')==1

def plan(id):value('(async()=>{await loadPlan('+json.dumps(id)+');return true;})()');wait('planView',lambda x:isinstance(x,dict))
def read_path():click('#case-path-read');return wait('casePathView',lambda x:isinstance(x,dict))
def main():
    a.screenshots.mkdir(parents=True,exist_ok=False);browser('open',f'http://127.0.0.1:{a.base_port}/');browser('eval','--stdin',stdin="document.querySelector('#token').value="+json.dumps(context['token'])+";document.querySelector('#token').dispatchEvent(new Event('input'));undefined")
    plan(context['assigned']);x=read_path();assert x['existing_run_access']['candidate_available'] and x['dispatch']['offer_state']=='ACCEPTED' and x['receipt']['state']=='LOCAL_ACKNOWLEDGED'
    assert x['case_id']==context['case_id'] and not x['case_goal_completed'];metrics=[]
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['width']==m['scroll'];metrics.append(m);value("(()=>{document.querySelector('#case-path-result').scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(a.screenshots.resolve()/('same-case-'+str(width)+'.png')))
    click('#plan-refresh');wait('planView',lambda x:isinstance(x,dict));assert value('casePathView') is None;assert read_path()['case_id']==context['case_id']
    # A delayed success from a different Case may not return old IDs or state.
    value("(()=>{window.pathFetch=fetch;window.releasePath=null;window.fetch=async(p,o)=>{const r=await pathFetch(p,o);if(String(p).endsWith('/case-path'))await new Promise(resolve=>releasePath=resolve);return r;};return true;})()")
    click('#case-path-read');wait('typeof releasePath',lambda x:x=='function');plan(context['unassigned']);value("(()=>{window.fetch=pathFetch;releasePath();return true;})()");browser('snapshot','-i');assert value('casePathView') is None and value("document.querySelector('#case-path-result').textContent")==''
    z=read_path();assert z['existing_run_access']['state']=='BLOCKED_NO_EXISTING_ASSIGNMENT' and z['case_id']!=context['case_id'];assert '保持阻塞' in value("document.querySelector('#case-path-result').textContent");browser('screenshot',str(a.screenshots.resolve()/'new-run-blocked.png'))
    # Visible transient failure clears the old projection and permits retry.
    value("(()=>{window.pathFetch=fetch;window.fetch=(p,o)=>String(p).endsWith('/case-path')?Promise.reject(Error('SYNTHETIC_READ_FAILURE')):pathFetch(p,o);return true;})()")
    click('#case-path-read');wait("document.querySelector('#case-path-error').textContent",lambda s:'SYNTHETIC_READ_FAILURE' in s);assert value('casePathView') is None;value("(()=>{window.fetch=pathFetch;return true;})()");read_path()
    # An observed 403 clears the entire private plan, not only the new card.
    value("(()=>{window.pathFetch=fetch;window.fetch=(p,o)=>String(p).endsWith('/case-path')?Promise.resolve(new Response(JSON.stringify({detail:'SYNTHETIC_DENIED'}),{status:403,headers:{'Content-Type':'application/json'}})):pathFetch(p,o);return true;})()")
    click('#case-path-read');wait('planView',lambda x:x is None);assert value('casePathView') is None and value("document.querySelector('#request-original').textContent")=='';value("(()=>{window.fetch=pathFetch;return true;})()");plan(context['assigned']);read_path()
    # Identity change invalidates a response already in flight.
    value("(()=>{window.pathFetch=fetch;window.releasePath=null;window.fetch=async(p,o)=>{const r=await pathFetch(p,o);if(String(p).endsWith('/case-path'))await new Promise(resolve=>releasePath=resolve);return r;};return true;})()")
    click('#case-path-read');wait('typeof releasePath',lambda x:x=='function');browser('eval',"document.querySelector('#token').value='';document.querySelector('#token').dispatchEvent(new Event('input'));undefined");value("(()=>{window.fetch=pathFetch;releasePath();return true;})()");browser('snapshot','-i');assert value('casePathView') is None and value("document.querySelector('#case-path-result').textContent")==''
    assert not browser('errors');a.report.write_text(json.dumps({'same_case_id':context['case_id'],'same_case_current_record_navigation':True,'existing_assigned_chain_visible':True,'stored_records_not_acceptance_checks':True,'new_run_blocked':True,'repeat_read_and_plan_refresh':True,'late_other_case_hidden':True,'transient_failure_clears_old_projection':True,'observed_denial_clears_private_plan':True,'late_identity_reply_hidden':True,'viewport_checks':metrics,'commands_sent':0,'new_authority_created':False,'model_calls':0,'budget':0},indent=2)+'\n')
try:main()
finally:browser('close')
