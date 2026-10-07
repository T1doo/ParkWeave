"""Native plan handoff UI against an owned synthetic fixture; tokens arrive on stdin."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time
from parkweave.process_env import minimal_environment
p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True);p.add_argument('--base-port',type=int,default=8778);a=p.parse_args();context=json.load(sys.stdin);root=Path.cwd()
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
cached=[x for x in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(x.read_text()).get('version')=='0.38.2'];assert cached
cmd=['node',str(sorted(cached)[0].parent/'bin/agent-browser.js'),'--session','pw-plan-handoff','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
def browser(*args,stdin=None):
 r=subprocess.run(cmd+list(args),input=stdin,capture_output=True,text=True,env=env,timeout=30)
 if r.returncode:raise RuntimeError('cached local handoff browser failed: '+r.stderr[:300])
 return r.stdout.strip()
def value(expr):
 r=json.loads(browser('eval','(async()=>JSON.stringify(await ('+expr+')))()'));return json.loads(r) if isinstance(r,str) else r
def wait(expr,pred,timeout=20):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  x=value(expr)
  if pred(x):return x
  time.sleep(.1)
 raise AssertionError('handoff browser timeout '+expr)
def click(selector):
 value('(()=>{document.querySelector('+json.dumps(selector)+').scrollIntoView({block:"center"});return true;})()');browser('snapshot','-i');browser('click',selector);browser('snapshot','-i')
def switch(role):
 browser('eval','--stdin',stdin="document.querySelector('#token').value="+json.dumps(context['tokens'][role])+";document.querySelector('#token').dispatchEvent(new Event('input'));undefined")
 assert value('planView') is None and value('receiptView') is None and value('dispatchView') is None
def track_writes():
 value("(()=>{window.originalFetch=fetch;window.writeRequests=[];window.fetch=(p,o)=>{if(o?.method&&o.method!=='GET')writeRequests.push({path:String(p),action:JSON.parse(o.body||'{}').action||'OFFER'});return originalFetch(p,o);};return true;})()")
def prep_plan(goal=None):
 goal=goal or context['goal'];click('#prep-list');wait("document.querySelector('#prep-items').textContent",lambda x:goal in x)
 selector=value("'#prep-items button:nth-child('+(Array.from(document.querySelectorAll('#prep-items button')).findIndex(b=>b.textContent.startsWith("+json.dumps(goal)+"))+1)+')'");click(selector);wait('preparationView',lambda x:isinstance(x,dict));click('#plan-prepare');return wait('planView',lambda x:isinstance(x,dict))
def dispatch_plan():
 click('#dispatch-list');wait("document.querySelector('#dispatch-items').textContent",lambda x:context['goal'] in x)
 selector=value("'#dispatch-items button:nth-child('+(Array.from(document.querySelectorAll('#dispatch-items button')).findIndex(b=>b.textContent==="+json.dumps(context['goal'])+")+1)+')'");click(selector);wait('dispatchView',lambda x:isinstance(x,dict));click('#plan-from-dispatch');return wait('planView',lambda x:isinstance(x,dict))
def navigation(selector,view):
 before=value('writeRequests.length');click(selector);row=wait(view,lambda x:isinstance(x,dict));assert value('writeRequests.length')==before
 if view=='dispatchView':assert row['preparation_id']==context['preparation_id']
 if view=='receiptView':assert row['step']['id']==context['receipt_step_id'] and row['step']['preparation_id']==context['preparation_id'] and row['step']['case_id']==context['case_id'] and row['step']['run_id']==context['run_id']
 return row
def check(step):
 rev=value('planView.revision');browser('fill','#plan-reason','SYNTHETIC explicit current '+step+' check');click('#plan-'+step);return wait('planView',lambda x:isinstance(x,dict) and x['revision']>rev)
def hold_receipt():
 value(r"(()=>{window.savedFetch=fetch;window.releaseReceipt=null;window.fetch=async(p,o)=>{const r=await savedFetch(p,o);if(/\/api\/executor-receipts\/[^/]+$/.test(String(p)))await new Promise(resolve=>releaseReceipt=resolve);return r;};return true;})()")
def release():value('(()=>{window.fetch=savedFetch;releaseReceipt();return true;})()');browser('snapshot','-i')
def screenshot(name,panel):
 value('(()=>{document.querySelector('+json.dumps(panel)+').scrollIntoView({block:"start"});return true;})()');browser('snapshot','-i');browser('screenshot',str(a.screenshots.resolve()/name))
def main():
 a.screenshots.mkdir(parents=True,exist_ok=False);browser('open',f'http://127.0.0.1:{a.base_port}/');browser('snapshot','-i');switch('owner');click('[data-tab=collaboration]')
 track_writes()
 row=prep_plan();assert row['next_step']=='P3';assert not value("document.querySelector('#plan-receipt').hidden");click('#plan-receipt');wait("document.querySelector('#plan-error').textContent",lambda x:bool(x));assert value('receiptView') is None and value('writeRequests.length')==0 and value('planView.preparation_id')==context['preparation_id']
 navigation('#plan-handoff','dispatchView');assert value('dispatchView.revision')==0 and value('writeRequests.length')==0
 switch('specialist');prep_plan();assert value("document.querySelector('#plan-receipt').hidden");navigation('#plan-handoff','dispatchView');browser('select','#dispatch-executor','executor-a');browser('fill','#dispatch-offer-reason','SYNTHETIC explicit local responsibility offer');click('#dispatch-offer-button');offered=wait('dispatchView',lambda x:isinstance(x,dict) and x['revision']==1);assert offered['current_offer']['state']=='OFFERED'
 switch('executor');row=dispatch_plan();navigation('#plan-handoff','dispatchView');browser('fill','#dispatch-decision-reason','SYNTHETIC executor accepts only this assigned task');click('#dispatch-accept');accepted=wait('dispatchView',lambda x:isinstance(x,dict) and x['revision']==2);assert accepted['current_offer']['state']=='ACCEPTED';context['receipt_step_id']=accepted['receipt_step_id'];assert context['receipt_step_id']
 click('#plan-from-dispatch');wait('planView',lambda x:isinstance(x,dict));assert not value("document.querySelector('#plan-receipt').hidden");navigation('#plan-receipt','receiptView');assert value('receiptView.step.state')=='AWAITING_RECEIPT'
 switch('owner');row=prep_plan();assert row['next_step']=='P3';row=check('P3');assert row['next_step']=='P4'
 metrics=[]
 for width in (1200,390,320):
  browser('set','viewport',str(width),'900' if width==1200 else '844');metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];metrics.append({'stage':'plan-handoff',**metric});screenshot('plan-handoff-'+str(width)+'.png','#plan-handoff');navigation('#plan-receipt','receiptView');screenshot('receipt-empty-'+str(width)+'.png','#receipt-detail');click('#plan-from-receipt');wait('planView',lambda x:isinstance(x,dict))
 browser('set','viewport','1200','900');switch('executor');dispatch_plan();navigation('#plan-receipt','receiptView');browser('fill','#receipt-text','SYNTHETIC local receipt, no external fulfillment evidence');browser('fill','#receipt-source','SYNTHETIC work record v1');click('#receipt-submit-button');submitted=wait('receiptView',lambda x:isinstance(x,dict) and x['step']['state']=='RECEIPT_RECORDED');assert submitted['current_receipt']['actor_id']=='executor-a'
 switch('owner');prep_plan();navigation('#plan-receipt','receiptView');browser('fill','#receipt-reason','SYNTHETIC enterprise checks current local receipt only');click('#receipt-ack');wait('receiptView',lambda x:isinstance(x,dict) and x['step']['state']=='LOCAL_ACKNOWLEDGED');click('#plan-from-receipt');wait('planView',lambda x:isinstance(x,dict));final=check('P4');assert final['state']=='LOCAL_RECORDS_CHECKED' and final['revision']==5;assert not final['case_goal_completed'] and not final['full_original_goal_verified']
 writes=value('writeRequests');assert [x['action'] for x in writes]==['OFFER','ACCEPT','CHECK_STEP','SUBMIT','ACKNOWLEDGE','CHECK_STEP'];click('#plan-refresh');wait('planView',lambda x:isinstance(x,dict));assert value('planView.revision')==5 and value('writeRequests.length')==6
 browser('reload');browser('snapshot','-i');track_writes();switch('owner');click('[data-tab=collaboration]');reloaded=prep_plan();assert reloaded['revision']==5 and reloaded['state']=='LOCAL_RECORDS_CHECKED';navigation('#plan-receipt','receiptView');assert value('receiptView.step.state')=='LOCAL_ACKNOWLEDGED';click('#plan-from-receipt');wait('planView',lambda x:isinstance(x,dict))
 # Delay a genuine authorized receipt GET across a different Case selection.
 hold_receipt();click('#plan-receipt');wait('typeof releaseReceipt',lambda x:x=='function');value('(()=>{window.fetch=savedFetch;return true;})()');prep_plan(context['second_goal']);release();assert value('planView.preparation_id')==context['second_preparation_id'] and value('receiptView') is None
 prep_plan();hold_receipt();click('#plan-receipt');wait('typeof releaseReceipt',lambda x:x=='function');switch('unassigned');release();assert value('planView') is None and value('receiptView') is None
 denied=[]
 for role in ('unassigned','revoked'):
  switch(role);status=value('(async()=>{const r=await fetch("/api/preparations/'+context['preparation_id']+'/controlled-plan",{headers:{Authorization:"Bearer "+document.querySelector("#token").value}});return r.status;})()');assert status==403;denied.append({'role':role,'status':status});assert value('planView') is None and value('receiptView') is None
 switch('specialist');prep_plan();assert value("document.querySelector('#plan-receipt').hidden");navigation('#plan-handoff','dispatchView');assert value("document.querySelector('#dispatch-receipt').hidden")
 switch('owner');prep_plan();navigation('#plan-receipt','receiptView');assert value('receiptView.offline_fulfillment')=='NO_EVIDENCE' and value('receiptView.external_acceptance')=='NOT_SUBMITTED';screenshot('receipt-acknowledged-1200.png','#receipt-detail');assert value('writeRequests.length')==0 and not browser('errors')
 a.report.write_text(json.dumps({'scope':'SYNTHETIC_INTERNAL_PLAN_HANDOFF_ONLY','case_id':context['case_id'],'run_id':context['run_id'],'preparation_id':context['preparation_id'],'receipt_step_id':context['receipt_step_id'],'native_role_flow':['OFFER','ACCEPT','P3_CHECK','SUBMIT','ACKNOWLEDGE','P4_CHECK'],'business_posts':writes,'navigation_business_posts':0,'same_case_preparation_run_receipt_bound':True,'refresh_and_reload_persisted':True,'specialist_receipt_route_hidden':True,'late_case_reply_ignored':True,'late_identity_reply_ignored':True,'negative_reads':denied,'viewport_checks':metrics,'plan_revision':5,'case_goal_completed':False,'full_original_goal_verified':False,'offline_fulfillment':'NO_EVIDENCE','external_acceptance':'NOT_SUBMITTED','model_calls':0,'budget':0},ensure_ascii=False,indent=2)+'\n')
try:main()
finally:browser('close')
