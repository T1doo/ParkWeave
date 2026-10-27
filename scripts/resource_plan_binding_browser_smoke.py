"""Real product registered planning UI; local synthetic context supplied via stdin."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time
from parkweave.process_env import minimal_environment
p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True);p.add_argument('--base-port',type=int,default=8775);a=p.parse_args();context=json.load(sys.stdin);root=Path.cwd()
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
cached=[x for x in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(x.read_text()).get('version')=='0.38.2'];assert cached
cmd=['node',str(sorted(cached)[0].parent/'bin/agent-browser.js'),'--session','pw-resource-binding','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
def browser(*args,stdin=None):
    r=subprocess.run(cmd+list(args),input=stdin,capture_output=True,text=True,env=env,timeout=30)
    if r.returncode:raise RuntimeError('cached local resource binding browser failed')
    return r.stdout.strip()
def value(expr):
    r=json.loads(browser('eval','(async()=>JSON.stringify(await ('+expr+')))()'));return json.loads(r) if isinstance(r,str) else r
def wait(expr,pred,timeout=20):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        x=value(expr)
        if pred(x):return x
        time.sleep(.1)
    raise AssertionError('resource binding browser timeout '+expr)
def click(selector):
    value("(()=>{window.bindingClicks=0;const b=document.querySelector("+json.dumps(selector)+");b.addEventListener('click',()=>bindingClicks++,{once:true});b.scrollIntoView({block:'center'});return true;})()")
    browser('snapshot','-i');browser('click',selector);browser('snapshot','-i');assert value('bindingClicks')==1
def choose(label):
    selector=value("'#bounded-goal-choices button:nth-child('+(Array.from(document.querySelectorAll('#bounded-goal-choices button')).findIndex(b=>b.textContent==="+json.dumps(label)+")+1)+')'");click(selector)
def plan(id):value('(async()=>{await loadPlan('+json.dumps(id)+');return true;})()');wait('planView',lambda x:isinstance(x,dict))
def save_request():
    rev=value('planView.preparation_revision');click('#request-save');return wait('planView',lambda x:isinstance(x,dict) and x['preparation_revision']>rev)
def read_preview():click('#bounded-planning-read');return wait('boundedView',lambda x:isinstance(x,dict))
def binding():
    click('#resource-binding-read');return wait('resourceBindingView',lambda x:isinstance(x,dict))
def main():
    a.screenshots.mkdir(parents=True,exist_ok=False);browser('open',f'http://127.0.0.1:{a.base_port}/');browser('eval','--stdin',stdin="document.querySelector('#token').value="+json.dumps(context['token'])+";document.querySelector('#token').dispatchEvent(new Event('input'));undefined");plan(context['preparation_id'])
    first=binding();assert all(first['checkpoints'][s]['state']=='CURRENT' for s in ('P1','P2'));assert first['approval']=='NOT_IMPLEMENTED' and not first['execution_enabled']
    value("(()=>{document.querySelector('#resource-binding-choice').value="+json.dumps(context['alternative_combination_id'])+";document.querySelector('#resource-binding-choice').dispatchEvent(new Event('change'));return true;})()");assert value('resourceBindingView') is None;alternative=binding();assert alternative['candidate']['explicit_association_required'] and alternative['candidate']['old_occupancy_released'] is False
    click('#plan-materials');wait('preparationView',lambda x:isinstance(x,dict));click('#case-resource-load');wait('caseResourceView',lambda x:isinstance(x,dict));value("(()=>{document.querySelector('#case-resource-choice').value="+json.dumps(context['alternative_combination_id'])+";document.querySelector('#case-resource-reason').value='合成：明确选择替代组合并保留旧预约';return true;})()");click('#case-resource-form button');wait('caseResourceView.link_revision',lambda x:x==2);plan(context['preparation_id']);changed=binding();assert changed['checkpoints']['P2']['state']=='NEEDS_RECHECK' and len(changed['history'])==2 and changed['checkpoints']['P2']['changes']
    value("(()=>{document.querySelector('#resource').hidden=false;return true;})()");click('#combination-mine');wait("document.querySelectorAll('[data-combination-cancel]').length",lambda x:x>=2);click('[data-combination-cancel="'+context['alternative_combination_id']+'"]');wait('document.querySelector('+json.dumps('[data-combination-id="'+context['alternative_combination_id']+'"]')+').dataset.state',lambda x:x=='CANCELLED');plan(context['preparation_id']);withdrawn=binding();assert 'RESOURCE_CANCELLED' in withdrawn['checkpoints']['P2']['issues']
    value("(()=>{document.querySelector('#plan-required-goals').value='需要外部正式受理';document.querySelector('#plan-required-goals').dispatchEvent(new Event('input'));return true;})()");assert value('resourceBindingView') is None;save_request();changed_goal=binding();assert changed_goal['checkpoints']['P1']['state']=='NEEDS_RECHECK' and changed_goal['checkpoints']['P1']['changes'];assert not changed_goal['execution_enabled']
    click('#plan-refresh');wait('planView',lambda x:isinstance(x,dict));assert value('resourceBindingView') is None;restored=binding();assert len(restored['history'])==2 and 'RESOURCE_CANCELLED' in restored['checkpoints']['P2']['issues']
    metrics=[]
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['width']==m['scroll'];metrics.append(m);value("(()=>{document.querySelector('#resource-binding-result').scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(a.screenshots.resolve()/('binding-'+str(width)+'.png')))
    value("(()=>{window.bindingFetch=fetch;window.releaseBinding=null;window.fetch=async(p,o)=>{const r=await bindingFetch(p,o);if(String(p).includes('/resource-plan-binding'))await new Promise(resolve=>releaseBinding=resolve);return r;};return true;})()");click('#resource-binding-read');wait('typeof releaseBinding',lambda x:x=='function');plan(context['second_preparation_id']);value("(()=>{window.fetch=bindingFetch;releaseBinding();return true;})()");browser('snapshot','-i');assert value('resourceBindingView') is None
    plan(context['preparation_id']);binding();value("(()=>{window.bindingFetch=fetch;window.fetch=(p,o)=>String(p).includes('/resource-plan-binding')?Promise.resolve(new Response(JSON.stringify({detail:'SYNTHETIC_DENIED'}),{status:403})):bindingFetch(p,o);return true;})()");click('#resource-binding-read');wait('planView',lambda x:x is None);assert value('resourceBindingView') is None;value("(()=>{window.fetch=bindingFetch;return true;})()");plan(context['preparation_id']);binding();value("(()=>{window.bindingFetch=fetch;window.releaseBinding=null;window.fetch=async(p,o)=>{const r=await bindingFetch(p,o);if(String(p).includes('/resource-plan-binding'))await new Promise(resolve=>releaseBinding=resolve);return r;};return true;})()");click('#resource-binding-read');wait('typeof releaseBinding',lambda x:x=='function');browser('eval',"document.querySelector('#token').value='';document.querySelector('#token').dispatchEvent(new Event('input'));undefined");value("(()=>{window.fetch=bindingFetch;releaseBinding();return true;})()");browser('snapshot','-i');assert value('resourceBindingView') is None and value("document.querySelector('#resource-binding-result').textContent")=='';assert not browser('errors')
    a.report.write_text(json.dumps({'case_id':context['case_id'],'current_engineering_checkpoints_read':True,'alternative_comparison_no_release':True,'explicit_substitution_invalidates_old_checkpoint':True,'withdrawal_invalidates_current_binding':True,'changed_goal_invalidates_old_checkpoint':True,'refresh_restores_impacts_not_approval':True,'late_other_case_hidden':True,'observed_403_clears_private_plan':True,'late_identity_reply_hidden':True,'viewport_checks':metrics,'execution_enabled':False,'new_authority_created':False,'model_calls':0,'budget':0},ensure_ascii=False,indent=2)+'\n')
try:main()
finally:browser('close')
