"""Real product registered planning UI; local synthetic context supplied via stdin."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time
from parkweave.process_env import minimal_environment
p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True);p.add_argument('--base-port',type=int,default=8775);a=p.parse_args();context=json.load(sys.stdin);root=Path.cwd()
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
cached=[x for x in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(x.read_text()).get('version')=='0.38.2'];assert cached
cmd=['node',str(sorted(cached)[0].parent/'bin/agent-browser.js'),'--session','pw-bounded-planning','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
def browser(*args,stdin=None):
    r=subprocess.run(cmd+list(args),input=stdin,capture_output=True,text=True,env=env,timeout=30)
    if r.returncode:raise RuntimeError('cached local planning browser failed')
    return r.stdout.strip()
def value(expr):
    r=json.loads(browser('eval','(async()=>JSON.stringify(await ('+expr+')))()'));return json.loads(r) if isinstance(r,str) else r
def wait(expr,pred,timeout=20):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        x=value(expr)
        if pred(x):return x
        time.sleep(.1)
    raise AssertionError('planning browser timeout '+expr)
def click(selector):
    value("(()=>{window.planningClicks=0;const b=document.querySelector("+json.dumps(selector)+");b.addEventListener('click',()=>planningClicks++,{once:true});b.scrollIntoView({block:'center'});return true;})()")
    browser('snapshot','-i');browser('click',selector);browser('snapshot','-i');assert value('planningClicks')==1
def choose(label):
    selector=value("'#bounded-goal-choices button:nth-child('+(Array.from(document.querySelectorAll('#bounded-goal-choices button')).findIndex(b=>b.textContent==="+json.dumps(label)+")+1)+')'");click(selector)
def plan(id):value('(async()=>{await loadPlan('+json.dumps(id)+');return true;})()');wait('planView',lambda x:isinstance(x,dict))
def save_request():
    rev=value('planView.preparation_revision');click('#request-save');return wait('planView',lambda x:isinstance(x,dict) and x['preparation_revision']>rev)
def read_preview():click('#bounded-planning-read');return wait('boundedView',lambda x:isinstance(x,dict))
def main():
    a.screenshots.mkdir(parents=True,exist_ok=False);browser('open',f'http://127.0.0.1:{a.base_port}/');browser('eval','--stdin',stdin="document.querySelector('#token').value="+json.dumps(context['token'])+";document.querySelector('#token').dispatchEvent(new Event('input'));undefined");plan(context['preparation_id'])
    choose('本地材料准备');save_request();x=read_preview();assert len(x['current']['steps'])==1 and x['current']['state']=='COVERED_PREVIEW_ONLY';click('#bounded-planning-save');wait('boundedView.history.length',lambda x:x==1)
    click('#plan-refresh');wait('planView',lambda x:isinstance(x,dict));assert value('boundedView') is None;assert len(read_preview()['history'])==1
    choose('本地记录重验');value("(()=>{document.querySelector('#plan-required-goals').value+='\\n外部正式受理';document.querySelector('#plan-required-goals').dispatchEvent(new Event('input'));return true;})()");assert value('boundedView') is None;save_request();x=read_preview();assert len(x['current']['steps'])==5 and x['current']['state']=='PARTIAL' and x['history'][0]['state']=='STALE';assert x['current']['goal_coverage'][-1]['goal']=='外部正式受理';click('#bounded-planning-save');wait('boundedView.history.length',lambda x:x==2)
    metrics=[]
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['width']==m['scroll'];metrics.append(m);value("(()=>{document.querySelector('#bounded-planning-result').scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(a.screenshots.resolve()/('planning-'+str(width)+'.png')))
    # A saved request is not automatically enabled as an execution graph.
    assert not value('boundedView.current.execution_enabled') and value("document.querySelector('#plan-create').hidden")
    value("(()=>{window.planningFetch=fetch;window.releasePlanning=null;window.fetch=async(p,o)=>{const r=await planningFetch(p,o);if(String(p).endsWith('/planning-preview'))await new Promise(resolve=>releasePlanning=resolve);return r;};return true;})()")
    click('#bounded-planning-read');wait('typeof releasePlanning',lambda x:x=='function');plan(context['second_preparation_id']);value("(()=>{window.fetch=planningFetch;releasePlanning();return true;})()");browser('snapshot','-i');assert value('boundedView') is None and value("document.querySelector('#bounded-planning-result').textContent")==''
    plan(context['preparation_id']);read_preview();value("(()=>{window.planningFetch=fetch;window.fetch=(p,o)=>String(p).endsWith('/planning-preview')?Promise.resolve(new Response(JSON.stringify({detail:'SYNTHETIC_DENIED'}),{status:403})):planningFetch(p,o);return true;})()");click('#bounded-planning-read');wait('planView',lambda x:x is None);assert value('boundedView') is None;value("(()=>{window.fetch=planningFetch;return true;})()");plan(context['preparation_id']);read_preview()
    value("(()=>{window.planningFetch=fetch;window.releasePlanning=null;window.fetch=async(p,o)=>{const r=await planningFetch(p,o);if(String(p).endsWith('/planning-preview'))await new Promise(resolve=>releasePlanning=resolve);return r;};return true;})()");click('#bounded-planning-read');wait('typeof releasePlanning',lambda x:x=='function');browser('eval',"document.querySelector('#token').value='';document.querySelector('#token').dispatchEvent(new Event('input'));undefined");value("(()=>{window.fetch=planningFetch;releasePlanning();return true;})()");browser('snapshot','-i');assert value('boundedView') is None and value("document.querySelector('#bounded-planning-result').textContent")==''
    assert not browser('errors');a.report.write_text(json.dumps({'case_id':context['case_id'],'one_step_goal_compiled':True,'five_step_closed_dependencies':True,'unsupported_required_goal_preserved':True,'capture_refresh_history_restored':True,'old_source_history_stale':True,'goal_draft_clears_preview':True,'late_other_case_hidden':True,'observed_403_clears_private_plan':True,'late_identity_reply_hidden':True,'execution_enabled':False,'new_authority_created':False,'viewport_checks':metrics,'model_calls':0,'budget':0},ensure_ascii=False,indent=2)+'\n')
try:main()
finally:browser('close')
