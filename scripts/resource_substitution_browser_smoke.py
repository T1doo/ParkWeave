"""Real product registered planning UI; local synthetic context supplied via stdin."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time
from parkweave.process_env import minimal_environment
p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True);p.add_argument('--base-port',type=int,default=8775);a=p.parse_args();context=json.load(sys.stdin);root=Path.cwd()
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
cached=[x for x in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(x.read_text()).get('version')=='0.38.2'];assert cached
cmd=['node',str(sorted(cached)[0].parent/'bin/agent-browser.js'),'--session','pw-resource-substitution','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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
def choose_candidate(id):
    value("(()=>{document.querySelector('#resource-binding-choice').value="+json.dumps(id)+";document.querySelector('#resource-binding-choice').dispatchEvent(new Event('change'));return true;})()");return binding()
def cancel_group(id):
    value("(()=>{document.querySelector('#resource').hidden=false;return true;})()");click('#combination-mine');wait("document.querySelectorAll('[data-combination-cancel]').length",lambda x:x>=1);click('[data-combination-cancel="'+id+'"]');wait('document.querySelector('+json.dumps('[data-combination-id="'+id+'"]')+').dataset.state',lambda x:x=='CANCELLED')
def main():
    a.screenshots.mkdir(parents=True,exist_ok=False);browser('open',f'http://127.0.0.1:{a.base_port}/');browser('eval','--stdin',stdin="document.querySelector('#token').value="+json.dumps(context['token'])+";document.querySelector('#token').dispatchEvent(new Event('input'));undefined");plan(context['preparation_id']);binding();old=choose_candidate(context['alternative_combination_id']);assert old['candidate']['comparison']['can_confirm'];cancel_group(context['alternative_combination_id'])
    value("(()=>{document.querySelector('#resource-binding-confirm-reason').value='合成：提交前候选已整组撤回';return true;})()");click('#resource-binding-confirm');wait("document.querySelector('#resource-binding-confirm-status').textContent",lambda x:'不能确认' in x);assert value('resourceBindingView') is None
    click('#plan-refresh');wait('planView',lambda x:isinstance(x,dict));first=binding();assert len(first['history'])==1;current=choose_candidate(context['final_combination_id']);assert current['candidate']['comparison']['can_confirm'];proof=current['candidate']['comparison']['sha256'];value("(()=>{document.querySelector('#resource-binding-confirm-reason').value='合成：明确选择当前替代，旧预约保留';window.bindingFetch=fetch;window.confirmKeys=[];window.failBindingReplyOnce=true;window.releaseConfirm=null;window.fetch=async(p,o)=>{if(String(p).endsWith('/resource-plan-binding/confirm')){confirmKeys.push(o.headers['Idempotency-Key']);if(failBindingReplyOnce){failBindingReplyOnce=false;await new Promise(resolve=>releaseConfirm=resolve);const r=await bindingFetch(p,o);await r.text();throw Error('SYNTHETIC_LOST_REPLY');}}return bindingFetch(p,o);};return true;})()");click('#resource-binding-confirm');wait('typeof releaseConfirm',lambda x:x=='function');assert value("document.querySelector('#resource-binding-choice').disabled") and value("document.querySelector('#resource-binding-read').disabled") and value("document.querySelector('#request-save').disabled")
    # Even a programmatic event cannot replace the in-flight retry identity.
    key=value('resourceBindingPending.key');value("(()=>{document.querySelector('#resource-binding-choice').value="+json.dumps(context['original_combination_id'])+";document.querySelector('#resource-binding-choice').dispatchEvent(new Event('change'));document.querySelector('#resource-binding-confirm-form').dispatchEvent(new Event('submit',{cancelable:true}));return true;})()");assert value('resourceBindingPending.key')==key and value('confirmKeys.length')==1;value("(()=>{releaseConfirm();return true;})()");wait('resourceBindingPending.stage',lambda x:x=='UNCERTAIN');assert value("document.querySelector('#resource-binding-confirm-reason').disabled")
    click('#resource-binding-confirm');wait("document.querySelector('#resource-binding-confirm-status').textContent",lambda x:'已记录' in x);assert value('confirmKeys.length')==2 and value('confirmKeys[0]===confirmKeys[1]');value("(()=>{window.fetch=bindingFetch;return true;})()");saved=value('resourceBindingView');assert len(saved['history'])==2 and len(saved['impact_history'])==1 and saved['impact_history'][0]['document']['comparison_sha256']==proof;assert saved['impact_history'][0]['document']['old_occupancy_released'] is False
    cancel_group(context['final_combination_id']);plan(context['preparation_id']);withdrawn=binding();assert 'RESOURCE_CANCELLED' in withdrawn['checkpoints']['P2']['issues'];assert withdrawn['impact_history'][0]['document']['comparison_sha256']==proof
    value("(()=>{document.querySelector('#plan-required-goals').value='需要外部正式受理';document.querySelector('#plan-required-goals').dispatchEvent(new Event('input'));return true;})()");assert value('resourceBindingView') is None;save_request();changed=binding();assert changed['checkpoints']['P1']['state']=='NEEDS_RECHECK';click('#plan-refresh');wait('planView',lambda x:isinstance(x,dict));assert value('resourceBindingView') is None;restored=binding();assert len(restored['impact_history'])==1 and restored['impact_history'][0]['document']['comparison_sha256']==proof
    metrics=[]
    for width in (1200,390,320):
        browser('set','viewport',str(width),'900' if width==1200 else '844');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['width']==m['scroll'];metrics.append(m);value("(()=>{document.querySelector('#resource-binding-result').scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(a.screenshots.resolve()/('substitution-'+str(width)+'.png')))
    browser('set','viewport','1200','900');value("(()=>{document.querySelector('.binding-impact').scrollIntoView({block:'start'});return true;})()");browser('snapshot','-i');browser('screenshot',str(a.screenshots.resolve()/'substitution-impact-1200.png'))
    value("(()=>{window.bindingFetch=fetch;window.releaseBinding=null;window.fetch=async(p,o)=>{const r=await bindingFetch(p,o);if(String(p).includes('/resource-plan-binding'))await new Promise(resolve=>releaseBinding=resolve);return r;};return true;})()");click('#resource-binding-read');wait('typeof releaseBinding',lambda x:x=='function');plan(context['second_preparation_id']);value("(()=>{window.fetch=bindingFetch;releaseBinding();return true;})()");browser('snapshot','-i');assert value('resourceBindingView') is None
    plan(context['preparation_id']);binding();value("(()=>{window.bindingFetch=fetch;window.fetch=(p,o)=>String(p).includes('/resource-plan-binding')?Promise.resolve(new Response(JSON.stringify({detail:'SYNTHETIC_DENIED'}),{status:403})):bindingFetch(p,o);return true;})()");click('#resource-binding-read');wait('planView',lambda x:x is None);assert value('resourceBindingView') is None;value("(()=>{window.fetch=bindingFetch;return true;})()");plan(context['preparation_id']);binding()
    value("(()=>{window.bindingFetch=fetch;window.releaseBinding=null;window.fetch=async(p,o)=>{const r=await bindingFetch(p,o);if(String(p).includes('/resource-plan-binding'))await new Promise(resolve=>releaseBinding=resolve);return r;};return true;})()");click('#resource-binding-read');wait('typeof releaseBinding',lambda x:x=='function');browser('eval',"document.querySelector('#token').value='';document.querySelector('#token').dispatchEvent(new Event('input'));undefined");value("(()=>{window.fetch=bindingFetch;releaseBinding();return true;})()");browser('snapshot','-i');assert value('resourceBindingView') is None;assert not browser('errors')
    a.report.write_text(json.dumps({'case_id':context['case_id'],'cancelled_preview_confirm_rejected':True,'inflight_selection_and_duplicate_submit_guarded':True,'lost_committed_reply_same_key_recovered':True,'only_one_immutable_impact_record':True,'original_occupancy_preserved':True,'withdrawal_invalidates_cached_current_state':True,'changed_goal_invalidates_cached_current_state':True,'refresh_restores_immutable_history_not_approval':True,'late_other_case_hidden':True,'observed_403_clears_private_plan':True,'late_identity_reply_hidden':True,'viewport_checks':metrics,'execution_enabled':False,'new_authority_created':False,'model_calls':0,'budget':0},ensure_ascii=False,indent=2)+'\n')
try:main()
finally:browser('close')
