"""Native registered Case-step UI on an isolated synthetic API; credentials on stdin."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time
from parkweave.process_env import minimal_environment
p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True);p.add_argument('--base-port',type=int,default=8779);a=p.parse_args();context=json.load(sys.stdin);root=Path.cwd()
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
cached=[x for x in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(x.read_text()).get('version')=='0.38.2'];assert cached
cmd=['node',str(sorted(cached)[0].parent/'bin/agent-browser.js'),'--session','pw-service-case-steps','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
def browser(*args,stdin=None):
 r=subprocess.run(cmd+list(args),input=stdin,capture_output=True,text=True,env=env,timeout=30)
 if r.returncode:raise RuntimeError('cached local Case-step browser failed: '+r.stderr[:300])
 return r.stdout.strip()
def value(expr):
 r=json.loads(browser('eval','(async()=>JSON.stringify(await ('+expr+')))()'));return json.loads(r) if isinstance(r,str) else r
def wait(expr,pred,timeout=20):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  x=value(expr)
  if pred(x):return x
  time.sleep(.1)
 raise AssertionError('Case-step browser timeout '+expr)
def click(selector):
 value('(()=>{document.querySelector('+json.dumps(selector)+').scrollIntoView({block:"center"});return true;})()');browser('snapshot','-i');browser('click',selector);browser('snapshot','-i')
def switch(role):
 browser('eval','--stdin',stdin="document.querySelector('#token').value="+json.dumps(context['tokens'][role])+";document.querySelector('#token').dispatchEvent(new Event('input'));undefined")
 assert value('receiptView') is None and value('dispatchView') is None
def track_writes():
 value("(()=>{window.originalFetch=fetch;window.writeRequests=[];window.fetch=(p,o)=>{if(o?.method&&o.method!=='GET')writeRequests.push({path:String(p),action:JSON.parse(o.body||'{}').action||'BUSINESS_WRITE'});return originalFetch(p,o);};return true;})()")
def preparation(goal=None):
 goal=goal or context['goal'];click('#prep-list');wait("document.querySelector('#prep-items').textContent",lambda x:goal in x)
 selector=value("'#prep-items button:nth-child('+(Array.from(document.querySelectorAll('#prep-items button')).findIndex(b=>b.textContent.startsWith("+json.dumps(goal)+"))+1)+')'");click(selector);return wait('preparationView',lambda x:isinstance(x,dict))
def preparation_plan(goal=None):preparation(goal);click('#service-plan-prepare');return wait('servicePlanView',lambda x:isinstance(x,dict))
def dispatch_plan():
 click('#dispatch-list');wait("document.querySelector('#dispatch-items').textContent",lambda x:context['goal'] in x)
 selector=value("'#dispatch-items button:nth-child('+(Array.from(document.querySelectorAll('#dispatch-items button')).findIndex(b=>b.textContent==="+json.dumps(context['goal'])+")+1)+')'");click(selector);wait('dispatchView',lambda x:isinstance(x,dict));click('#service-plan-from-dispatch');return wait('servicePlanView',lambda x:isinstance(x,dict))
def open_business(name,view):
 before=value('writeRequests.length');click('[data-service-open="'+name+'"]');row=wait(view,lambda x:isinstance(x,dict));assert value('writeRequests.length')==before
 if view=='dispatchView':assert row['preparation_id']==context['preparation_id']
 if view=='receiptView':assert row['step']['preparation_id']==context['preparation_id'] and row['step']['case_id']==context['case_id'] and row['step']['run_id']==context['run_id']
 return row
def step(adapter):return value('servicePlanView.steps.find(s=>s.adapter_id==='+json.dumps(adapter)+')')
def act(adapter,action):
 s=step(adapter);revision=value('servicePlanView.revision');browser('fill','#service-plan-reason','SYNTHETIC explicit '+adapter+' '+action);click('[data-service-step="'+s['id']+'"][data-service-action="'+action+'"]');return wait('servicePlanView',lambda x:isinstance(x,dict) and x['revision']>revision)
def committed_unknown_verify(adapter):
 s=step(adapter);revision=value('servicePlanView.revision');browser('fill','#service-plan-reason','SYNTHETIC explicit '+adapter+' VERIFY with same-key receipt recovery')
 value("(()=>{window.savedCommitFetch=fetch;window.verifyAttempts=[];window.dropVerifiedReply=true;window.fetch=async(p,o)=>{if(String(p).endsWith('/service-case-plan/commands')&&JSON.parse(o?.body||'{}').action==='VERIFY'){verifyAttempts.push({key:o.headers['Idempotency-Key'],body:o.body});if(dropVerifiedReply){dropVerifiedReply=false;const r=await savedCommitFetch(p,o);if(!r.ok)return r;await r.text();throw Error('SYNTHETIC_COMMITTED_REPLY_LOST');}}return savedCommitFetch(p,o);};return true;})()")
 click('[data-service-step="'+s['id']+'"][data-service-action="VERIFY"]');wait("document.querySelector('#service-plan-retry').hidden",lambda x:x is False);assert value('verifyAttempts.length')==1 and value('servicePlanPending') is not None;click('#service-plan-retry');wait('servicePlanRecoveryHandle?.observed&&!servicePlanRecoveryChecking',lambda x:x is True);row=wait('servicePlanView',lambda x:isinstance(x,dict) and x['revision']>revision);assert value('verifyAttempts.length')==1 and row['read_only'];click('#service-plan-release');row=wait('servicePlanView',lambda x:isinstance(x,dict) and not x.get('read_only'));assert value('verifyAttempts.length')==1;value('(()=>{window.fetch=savedCommitFetch;return true;})()');return row
def decision(selector,state):
 before=value('dispatchView.revision');browser('fill','#dispatch-decision-reason','SYNTHETIC explicit '+state);click(selector);return wait('dispatchView',lambda x:isinstance(x,dict) and x['revision']>before and x['current_offer']['state']==state)
def offer():
 before=value('dispatchView.revision');browser('select','#dispatch-executor','executor-a');browser('fill','#dispatch-offer-reason','SYNTHETIC explicit local responsibility offer');click('#dispatch-offer-button');return wait('dispatchView',lambda x:isinstance(x,dict) and x['revision']>before and x['current_offer']['state']=='OFFERED')
def submit(version):
 before=value('receiptView.step.revision');browser('fill','#receipt-text','SYNTHETIC corrected local work receipt v'+str(version));browser('fill','#receipt-source','SYNTHETIC work record v'+str(version));click('#receipt-submit-button');return wait('receiptView',lambda x:isinstance(x,dict) and x['step']['revision']>before and x['step']['state']=='RECEIPT_RECORDED')
def receipt_decision(selector,state):
 before=value('receiptView.step.revision');browser('fill','#receipt-reason','SYNTHETIC enterprise current receipt '+state);click(selector);return wait('receiptView',lambda x:isinstance(x,dict) and x['step']['revision']>before and x['step']['state']==state)
def capture(name,panel):
 value('(()=>{document.querySelector('+json.dumps(panel)+').scrollIntoView({block:"start"});return true;})()');browser('snapshot','-i');browser('screenshot',str(a.screenshots.resolve()/name))
def main():
 a.screenshots.mkdir(parents=True,exist_ok=False);browser('open',f'http://127.0.0.1:{a.base_port}/');browser('snapshot','-i');switch('owner');click('[data-tab=collaboration]');track_writes();initial=preparation_plan();assert initial['state']=='NOT_ADOPTED' and initial['can_adopt'];browser('fill','#service-plan-reason','SYNTHETIC adopt only explicitly saved registered coordination goal');click('#service-plan-adopt');adopted=wait('servicePlanView',lambda x:isinstance(x,dict) and x.get('plan_id'));assert [s['adapter_id'] for s in adopted['steps']]==['P1','P2','P3','P4'];ids={s['adapter_id']:s['id'] for s in adopted['steps']};plan_id=adopted['plan_id'];committed_unknown_verify('P1');assert step('P1')['state']=='VERIFIED'
 open_business('resources','preparationView');click('#case-resource-load');wait('caseResourceView',lambda x:isinstance(x,dict));browser('select','#case-resource-choice',context['combination_id']);browser('fill','#case-resource-reason','SYNTHETIC explicitly associate current confirmed resource combination');click('#case-resource-form button');wait('caseResourceView',lambda x:isinstance(x,dict) and x['link_revision']==1);click('#service-plan-prepare');wait('servicePlanView',lambda x:isinstance(x,dict));act('P2','VERIFY');assert step('P2')['state']=='VERIFIED'
 switch('specialist');preparation_plan();open_business('dispatch','dispatchView');offer();switch('executor');dispatch_plan();open_business('dispatch','dispatchView');decision('#dispatch-decline','DECLINED');click('#service-plan-from-dispatch');wait('servicePlanView',lambda x:isinstance(x,dict));act('P3','BEGIN');blocked=act('P3','REPORT_FAILURE');assert step('P3')['state']=='REPORTED_BLOCKED' and step('P3')['actual_business_state']=='DECLINED'
 switch('owner');preparation_plan();metrics=[]
 for width in (1200,390,320):
  browser('set','viewport',str(width),'900' if width==1200 else '844');metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];metrics.append({'stage':'reported-failure',**metric});capture('service-failure-'+str(width)+'.png','[data-service-adapter="P3"]');capture('service-failure-history-'+str(width)+'.png','#service-plan-history')
 browser('set','viewport','1200','900');switch('executor');dispatch_plan();retried=act('P3','RETRY');assert step('P3')['state']=='PENDING' and step('P3')['actual_business_state']=='DECLINED';open_business('dispatch','dispatchView');assert value('dispatchView.current_offer.state')=='DECLINED' and value('dispatchView.receipt_step_id') is None
 switch('specialist');preparation_plan();open_business('dispatch','dispatchView');offer();switch('executor');dispatch_plan();open_business('dispatch','dispatchView');accepted=decision('#dispatch-accept','ACCEPTED');receipt_id=accepted['receipt_step_id'];assert receipt_id
 switch('owner');preparation_plan();act('P3','VERIFY');assert step('P3')['state']=='VERIFIED';switch('executor');dispatch_plan();open_business('receipt','receiptView');first=submit(1);assert first['current_receipt']['version']==1
 switch('owner');preparation_plan();open_business('receipt','receiptView');corrected=receipt_decision('#receipt-correct','CHANGES_REQUESTED');assert corrected['current_receipt']['version']==1;switch('executor');dispatch_plan();open_business('receipt','receiptView');second=submit(2);assert second['current_receipt']['version']==2;switch('owner');preparation_plan();open_business('receipt','receiptView');receipt_decision('#receipt-ack','LOCAL_ACKNOWLEDGED');click('#service-plan-from-receipt');wait('servicePlanView',lambda x:isinstance(x,dict));final=act('P4','VERIFY');assert final['state']=='VERIFIED' and all(s['state']=='VERIFIED' for s in final['steps']);assert {s['adapter_id']:s['id'] for s in final['steps']}==ids and final['plan_id']==plan_id and not final['case_goal_completed'];writes=value('writeRequests');assert len(writes)==17;revision=final['revision']
 click('#service-plan-read');wait('servicePlanView',lambda x:isinstance(x,dict));assert value('servicePlanView.revision')==revision and value('writeRequests.length')==len(writes)
 browser('reload');browser('snapshot','-i');track_writes();switch('owner');click('[data-tab=collaboration]');reloaded=preparation_plan();assert reloaded['state']=='VERIFIED' and reloaded['revision']==revision and {s['adapter_id']:s['id'] for s in reloaded['steps']}==ids
 for width in (1200,390,320):
  browser('set','viewport',str(width),'900' if width==1200 else '844');metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];metrics.append({'stage':'all-verified',**metric});capture('service-verified-'+str(width)+'.png','#service-plan-steps');capture('service-verified-history-'+str(width)+'.png','#service-plan-history')
 browser('set','viewport','1200','900')
 # Delay only a genuine completed server GET; do not fabricate success data.
 value(r"(()=>{window.savedFetch=fetch;window.releaseServiceRead=null;window.fetch=async(p,o)=>{const r=await savedFetch(p,o);if(String(p).endsWith('/service-case-plan')&&(!o?.method||o.method==='GET'))await new Promise(resolve=>releaseServiceRead=resolve);return r;};return true;})()");click('#service-plan-read');wait('typeof releaseServiceRead',lambda x:x=='function');value('(()=>{window.fetch=savedFetch;return true;})()');preparation_plan(context['second_goal']);value('(()=>{releaseServiceRead();return true;})()');browser('snapshot','-i');assert value('servicePlanView.preparation_id')==context['second_preparation_id']
 preparation_plan();value(r"(()=>{window.savedFetch=fetch;window.releaseServiceRead=null;window.fetch=async(p,o)=>{const r=await savedFetch(p,o);if(String(p).endsWith('/service-case-plan')&&(!o?.method||o.method==='GET'))await new Promise(resolve=>releaseServiceRead=resolve);return r;};return true;})()");click('#service-plan-read');wait('typeof releaseServiceRead',lambda x:x=='function');switch('unassigned');value('(()=>{window.fetch=savedFetch;releaseServiceRead();return true;})()');browser('snapshot','-i');assert value('servicePlanView') is None
 negatives=[]
 for role in ('unassigned','revoked'):
  switch(role);status=value('(async()=>{const r=await fetch("/api/preparations/'+context['preparation_id']+'/service-case-plan",{headers:{Authorization:"Bearer "+document.querySelector("#token").value}});return r.status;})()');assert status==403;negatives.append({'role':role,'status':status})
 switch('owner');last=preparation_plan();assert last['state']=='VERIFIED' and value('writeRequests.length')==0 and not browser('errors')
 a.report.write_text(json.dumps({'scope':'SYNTHETIC_REGISTERED_CASE_STEPS_NATIVE_UI','case_id':context['case_id'],'run_id':context['run_id'],'preparation_id':context['preparation_id'],'plan_id':plan_id,'stable_steps':ids,'receipt_step_id':receipt_id,'plan_revision':revision,'business_posts':writes,'navigation_business_posts':0,'registered_four_step_adoption':True,'committed_unknown_verify_original_key_get_only_no_post_replay':True,'decline_then_reported_failure_retry_preserves_business_state':True,'specialist_reoffer_executor_accept':True,'receipt_correction_two_versions_acknowledged':True,'all_four_verified_after_reload':True,'stable_ids_after_reload':True,'late_case_reply_ignored':True,'late_token_reply_ignored':True,'negative_reads':negatives,'viewport_checks':metrics,'fixed_plan_created':False,'case_goal_completed':False,'external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE','model_calls':0,'budget':0},ensure_ascii=False,indent=2)+'\n')
try:main()
finally:browser('close')
