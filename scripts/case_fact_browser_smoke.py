"""Native registered Case-step UI on an isolated synthetic API; credentials on stdin."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time,uuid
from parkweave.process_env import minimal_environment
p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True);p.add_argument('--base-port',type=int,default=8786);a=p.parse_args();context=json.load(sys.stdin);root=Path.cwd()
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
cached=[x for x in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(x.read_text()).get('version')=='0.38.2'];assert cached
cmd=['node',str(sorted(cached)[0].parent/'bin/agent-browser.js'),'--session','pw-fact-'+uuid.uuid4().hex[:10],'--executable-path','/usr/bin/chromium','--args','--no-sandbox']
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
 value('(()=>{const e=document.querySelector('+json.dumps(selector)+');if(!e||e.disabled||e.closest("[hidden]"))throw Error("native click unavailable");window.nativeClicks=0;e.addEventListener("click",()=>nativeClicks++,{once:true});e.scrollIntoView({block:"center"});return true;})()');browser('snapshot','-i');browser('click',selector);assert value('nativeClicks')==1;browser('snapshot','-i')
def switch(role):
 browser('eval','--stdin',stdin="document.querySelector('#token').value="+json.dumps(context['tokens'][role])+";document.querySelector('#token').dispatchEvent(new Event('input'));undefined")
 assert value('receiptView') is None and value('dispatchView') is None
def track_writes():
 value("(()=>{window.originalFetch=fetch;window.writeRequests=[];window.fetch=(p,o)=>{if(o?.method&&o.method!=='GET')writeRequests.push({path:String(p),action:JSON.parse(o.body||'{}').action||'BUSINESS_WRITE'});return originalFetch(p,o);};return true;})()")
def preparation(goal=None):
 goal=goal or context['goal'];click('[data-tab=collaboration]');click('#prep-list');wait("document.querySelector('#prep-items').textContent",lambda x:goal in x)
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
 click('[data-service-step="'+s['id']+'"][data-service-action="VERIFY"]');wait("document.querySelector('#service-plan-retry').hidden",lambda x:x is False);assert value('verifyAttempts.length')==1 and value('servicePlanPending') is not None;click('#service-plan-retry');row=wait('servicePlanView',lambda x:isinstance(x,dict) and x['revision']>revision);assert value('verifyAttempts.length')==2 and value('verifyAttempts[0].key===verifyAttempts[1].key&&verifyAttempts[0].body===verifyAttempts[1].body');value('(()=>{window.fetch=savedCommitFetch;return true;})()');return row
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
def prep_ready():
 wait('materialCorrectionsView',lambda x:isinstance(x,dict) and x['preparation_id']==value('preparationView.preparation.id') and x['preparation_revision']==value('preparationView.preparation.revision'));return value('preparationView')
def material(slot,version):
 before=value('preparationView.preparation.revision');browser('select','#prep-slot',slot);browser('fill','#prep-text','SYNTHETIC FACT_BROWSER independent '+slot+' material version '+str(version));browser('fill','#prep-source-label','SYNTHETIC FACT_BROWSER new source v'+str(version));click('#prep-evidence button');wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>before);return prep_ready()
def prep_decision(selector,reason):
 before=value('preparationView.preparation.revision');browser('fill','#prep-reason',reason);click(selector);wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>before);return prep_ready()
def local_decision(selector):
 before=value('localCaseView.revision');browser('fill','#local-case-reason','SYNTHETIC FACT_BROWSER explicit '+selector);click(selector);return wait('localCaseView',lambda x:isinstance(x,dict) and x['revision']>before)
def associate(revision):
 click('#case-resource-load');wait('caseResourceView',lambda x:isinstance(x,dict));browser('select','#case-resource-choice',context['combination_id']);browser('fill','#case-resource-reason','SYNTHETIC explicit current material resource binding v'+str(revision));click('#case-resource-form button');return wait('caseResourceView',lambda x:isinstance(x,dict) and x['link_revision']==revision)
def show_plan():
 click('#service-plan-prepare');return wait('servicePlanView',lambda x:isinstance(x,dict))
def viewport_capture(stage,panel,metrics):
 for width in (1200,390,320):
  browser('set','viewport',str(width),'900' if width==1200 else '844');metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];metrics.append({'stage':stage,**metric});capture(stage+'-'+str(width)+'.png',panel)
 browser('set','viewport','1200','900')
def committed_unknown_reoffer():
 before=value('dispatchView.revision');browser('select','#dispatch-executor','executor-a');browser('fill','#dispatch-offer-reason','SYNTHETIC original executor explicitly reconsider new materials')
 value("(()=>{window.savedReofferFetch=fetch;window.reofferAttempts=[];window.dropReofferReply=true;window.fetch=async(p,o)=>{if(String(p).endsWith('/dispatch')&&o?.method==='POST'){reofferAttempts.push({key:o.headers['Idempotency-Key'],body:o.body});if(dropReofferReply){dropReofferReply=false;const r=await savedReofferFetch(p,o);if(!r.ok)return r;await r.text();throw Error('SYNTHETIC_COMMITTED_REPLY_LOST');}}return savedReofferFetch(p,o);};return true;})()")
 click('#dispatch-offer-button');wait("document.querySelector('#dispatch-retry').hidden",lambda x:x is False);assert value('reofferAttempts.length')==1;click('#dispatch-retry');row=wait('dispatchView',lambda x:isinstance(x,dict) and x['revision']>before and x['current_offer']['state']=='OFFERED');assert value('reofferAttempts.length')==2 and value('reofferAttempts[0].key===reofferAttempts[1].key&&reofferAttempts[0].body===reofferAttempts[1].body');assert value('JSON.parse(reofferAttempts[0].body).recovery_receipt_step_id')==context['old_step_id'];value('(()=>{window.fetch=savedReofferFetch;return true;})()');return row

def fact_read():
 click('#case-fact-read');return wait('caseFactView',lambda x:isinstance(x,dict) and x['preparation_id']==context['preparation_id'])
def fact_declare():
 x=fact_read();assert x['state']=='NOT_DECLARED' and x['revision']==0
 assert all(value('document.querySelector(\'[data-fact-field="'+f+'"]\').value')=='' for f in context['selected_facts'])
 browser('check','#case-fact-declare-purpose');browser('fill','#case-fact-declare-reason','SYNTHETIC explicit Case purpose; no qualification or global source verdict');click('#case-fact-declare')
 wait('caseFactPending',lambda x:x is None);wait('preparationView.preparation.revision',lambda r:r>x['preparation_revision']);return fact_read()
def fact_confirm(unknown=False):
 x=fact_read();revision=x['revision'];assert value("document.querySelector('#case-fact-confirm').disabled")
 for field,assertion in context['selected_facts'].items():browser('select','[data-fact-field="'+field+'"]',assertion)
 assert value("document.querySelector('#case-fact-confirm').disabled")
 browser('check','#case-fact-purpose');browser('fill','#case-fact-confirm-reason','SYNTHETIC explicit three owner choices for this Case; competing source retained')
 if unknown:
  value("(()=>{window.savedFactFetch=fetch;window.factAttempts=[];window.dropFactReply=true;window.fetch=async(p,o)=>{if(String(p).endsWith('/fact-clarifications/confirm')&&o?.method==='POST'){factAttempts.push({key:o.headers['Idempotency-Key'],body:o.body});if(dropFactReply){dropFactReply=false;const r=await savedFactFetch(p,o);if(!r.ok)return r;await r.text();throw Error('SYNTHETIC_COMMITTED_REPLY_LOST');}}return savedFactFetch(p,o);};return true;})()")
 click('#case-fact-confirm')
 if unknown:
  wait('caseFactPending?.stage',lambda x:x=='UNKNOWN');assert value('factAttempts.length')==1
  original=value('caseFactPending.body');key=value('caseFactPending.key');click('#prep-refresh');wait('preparationView',lambda y:isinstance(y,dict) and y['preparation']['revision']>x['preparation_revision']);assert value('caseFactPending.body')==original and value('caseFactPending.key')==key
  click('#case-fact-retry');wait('caseFactPending',lambda y:y is None);assert value('factAttempts.length')==2 and value('factAttempts[0].key===factAttempts[1].key&&factAttempts[0].body===factAttempts[1].body');value('(()=>{window.fetch=savedFactFetch;return true;})()')
 else:wait('caseFactPending',lambda y:y is None)
 wait('preparationView.preparation.revision',lambda r:r>x['preparation_revision']);y=fact_read();assert y['revision']>revision and y['state']=='CURRENT' and y['satisfied'];assert len(y['history'][-1]['choices'])==3
 assert set(c['assertion_id'] for c in y['history'][-1]['choices'])==set(context['selected_facts'].values())
 region=next(q for q in y['necessary_questions'] if q['field']=='region');assert len(region['evidence'])>=2
 context.setdefault('confirmed_fact_versions',[]).append(y)
 return y

def source_conflict():
 from datetime import datetime,timedelta,timezone
 preparation();x=fact_read();before=x['history'];revision=x['preparation_revision']
 click('#case-fact-source-entry summary');browser('select','#case-fact-source-field','region')
 browser('fill','#case-fact-source-value','PRIVATE_NATIVE_NEW_COMPETING_REGION')
 browser('fill','#case-fact-source-ref','SYNTHETIC real native source '+uuid.uuid4().hex);browser('fill','#case-fact-source-version','2');browser('fill','#case-fact-source-excerpt','PRIVATE_NATIVE_NEW_COMPETING_REGION_EXCERPT')
 now=datetime.now(timezone.utc)
 browser('fill','#case-fact-source-from',(now-timedelta(hours=1)).isoformat());browser('fill','#case-fact-source-until',(now+timedelta(days=1)).isoformat());browser('check','#case-fact-source-purpose');click('#case-fact-source-save')
 wait('caseFactPending',lambda x:x is None);preparation();x=fact_read();assert x['state']=='STALE' and not x['satisfied'] and x['history']==before and x['preparation_revision']==revision
 region=next(q for q in x['necessary_questions'] if q['field']=='region');assert len(region['evidence'])==3 and any(e['value']=='PRIVATE_NATIVE_NEW_COMPETING_REGION' for e in region['evidence'])
 for field in context['selected_facts']:assert value('document.querySelector(\'[data-fact-field="'+field+'"]\').value')==''
 return x

def fact_late_guards():
 preparation();fact_read();original_history=value('caseFactView.history')
 value("(()=>{window.savedFactLateFetch=fetch;window.releaseFactRead=null;window.fetch=async(p,o)=>{const r=await savedFactLateFetch(p,o);if(String(p).endsWith('/fact-clarifications')&&(!o?.method||o.method==='GET'))await new Promise(resolve=>releaseFactRead=resolve);return r;};return true;})()")
 click('#case-fact-read');wait('typeof releaseFactRead',lambda x:x=='function');value('(()=>{window.fetch=savedFactLateFetch;return true;})()');preparation(context['second_goal']);click('#case-fact-read');wait('caseFactView',lambda x:isinstance(x,dict) and x['preparation_id']==context['second_preparation_id']);value('(()=>{releaseFactRead();return true;})()');browser('snapshot','-i');assert value('caseFactView.preparation_id')==context['second_preparation_id'] and value('caseFactView.history')==[]
 preparation();fact_read();assert value('caseFactView.history')==original_history
 value("(()=>{window.savedFactLateFetch=fetch;window.releaseFactRead=null;window.fetch=async(p,o)=>{const r=await savedFactLateFetch(p,o);if(String(p).endsWith('/fact-clarifications')&&(!o?.method||o.method==='GET'))await new Promise(resolve=>releaseFactRead=resolve);return r;};return true;})()")
 click('#case-fact-read');wait('typeof releaseFactRead',lambda x:x=='function');switch('specialist');value('(()=>{window.fetch=savedFactLateFetch;releaseFactRead();return true;})()');browser('snapshot','-i');assert value('caseFactView') is None and value("document.querySelector('#case-fact-fields').textContent")=='' and value("document.querySelector('#case-fact-history').textContent")==''
 denial=value('(async()=>{const r=await fetch("/api/preparations/'+context['preparation_id']+'/fact-clarifications",{headers:{Authorization:"Bearer "+document.querySelector("#token").value}});return {status:r.status,body:await r.text()};})()');assert denial['status']==403 and 'PRIVATE_' not in denial['body'];switch('foreign');denial=value('(async()=>{const r=await fetch("/api/preparations/'+context['preparation_id']+'/fact-clarifications",{headers:{Authorization:"Bearer "+document.querySelector("#token").value}});return {status:r.status,body:await r.text()};})()');assert denial['status']==403 and 'PRIVATE_' not in denial['body'];assert value('caseFactView') is None
 for field in ('value','ref','excerpt','from','until'):assert value('document.querySelector("#case-fact-source-'+field+'").value')==''
 switch('owner');return original_history

def main():
 a.screenshots.mkdir(parents=True,exist_ok=False);browser('open',f'http://127.0.0.1:{a.base_port}/');browser('snapshot','-i');switch('owner');track_writes();preparation();prep_ready()
 # Save the explicit five-node goal natively before material review or adoption.
 click('#plan-prepare');wait('planView',lambda x:isinstance(x,dict));browser('fill','#request-current','SYNTHETIC FACT_BROWSER local record recheck only; no external completion');browser('fill','#plan-required-goals','LOCAL_CASE_RECORD_RECHECK');click('#request-save');wait('planView.request_intent',lambda x:isinstance(x,dict) and x.get('required_goals')==['LOCAL_CASE_RECORD_RECHECK']);preparation();prep_ready();fact_declare();fact_confirm(unknown=True);material('need_summary',1);material('material_outline',1)
 switch('specialist');preparation();prep_ready();prep_decision('#prep-review','SYNTHETIC original two new materials manually reviewed');switch('owner');preparation();prep_ready();prep_decision('#prep-confirm','SYNTHETIC original local material package confirmed');initial=show_plan();assert initial['can_adopt'];browser('fill','#service-plan-reason','SYNTHETIC adopt explicit local five-node goal');click('#service-plan-adopt');plan=wait('servicePlanView',lambda x:isinstance(x,dict) and x.get('plan_id'));ids={s['adapter_id']:s['id'] for s in plan['steps']};assert list(ids)==['P1','P2','P3','P4','P5'];plan_id=plan['plan_id']
 act('P1','VERIFY');open_business('resources','preparationView');associate(1);show_plan();act('P2','VERIFY');switch('specialist');preparation_plan();open_business('dispatch','dispatchView');offer();switch('executor');dispatch_plan();open_business('dispatch','dispatchView');accepted=decision('#dispatch-accept','ACCEPTED');old_step=accepted['receipt_step_id'];context['old_step_id']=old_step;assert old_step
 # Original SUBMIT still refuses an accepted offer until P3 is actually verified.
 click('#service-plan-from-dispatch');wait('servicePlanView',lambda x:isinstance(x,dict));open_business('receipt','receiptView');before=value('receiptView.step.revision');browser('fill','#receipt-text','SYNTHETIC premature submission must not persist');browser('fill','#receipt-source','SYNTHETIC premature local record');click('#receipt-submit-button');wait("document.querySelector('#receipt-error').textContent",lambda x:bool(x));assert value('receiptView.step.revision')==before and value('receiptView.current_receipt') is None
 switch('owner');preparation_plan();act('P3','VERIFY');switch('executor');dispatch_plan();open_business('receipt','receiptView');first_receipt=submit(1);old_receipt=first_receipt['current_receipt'];switch('owner');preparation_plan();open_business('receipt','receiptView');receipt_decision('#receipt-ack','LOCAL_ACKNOWLEDGED');click('#service-plan-from-receipt');wait('servicePlanView',lambda x:isinstance(x,dict));act('P4','VERIFY');open_business('localcase','localCaseView');local_decision('#local-case-validate');preparation_plan();act('P5','VERIFY');open_business('localcase','localCaseView');first_close=local_decision('#local-case-close');assert first_close['case_state']=='WAITING_CONFIRMATION' and not first_close['case_goal_completed'];first_history=first_close['history'];preparation_plan();act('P5','VERIFY');metrics=[];preparation();fact_read();viewport_capture('facts-explicit-current','#case-fact-panel',metrics);preparation_plan();viewport_capture('recovery-original-five-verified','#service-plan-steps',metrics)
 # Real original fact append alone stales all five original source bindings.
 source_conflict();viewport_capture('facts-real-source-conflict-stale','#case-fact-panel',metrics);stale=show_plan();assert all(s['state']!='VERIFIED' for s in stale['steps']);preparation();fact_confirm();switch('specialist');preparation();prep_ready();prep_decision('#prep-review','SYNTHETIC manual review of current materials and new explicit fact purpose');switch('owner');preparation();prep_ready();prep_decision('#prep-confirm','SYNTHETIC independent local confirmation after explicit source choices');stale=show_plan();assert {s['adapter_id']:s['id'] for s in stale['steps']}==ids and stale['plan_id']==plan_id;assert all(s['state']!='VERIFIED' for s in stale['steps']);viewport_capture('recovery-materials-invalidated-five','#service-plan-steps',metrics);open_business('localcase','localCaseView');local_decision('#local-case-reopen');preparation_plan()
 act('P1','VERIFY');open_business('resources','preparationView');associate(2);show_plan();act('P2','VERIFY');switch('specialist');preparation_plan();open_business('dispatch','dispatchView');assert value('dispatchView.current_offer.state')=='ACCEPTED';assert value('dispatchView.can_reoffer') is True;reoffered=committed_unknown_reoffer();assert reoffered['receipt_step_id'] is None;assert reoffered['current_offer']['executor_id']=='executor-a'
 switch('executor');dispatch_plan();open_business('dispatch','dispatchView');newaccepted=decision('#dispatch-accept','ACCEPTED');new_step=newaccepted['receipt_step_id'];assert new_step and new_step!=old_step;switch('owner');preparation_plan();act('P3','VERIFY');switch('executor');dispatch_plan();open_business('receipt','receiptView');assert value('receiptView.current_receipt') is None and value('receiptView.step.id')==new_step;newreceipt=submit(2);assert newreceipt['current_receipt']['version']==1 and newreceipt['current_receipt']['id']!=old_receipt['id'];switch('owner');preparation_plan();open_business('receipt','receiptView');receipt_decision('#receipt-ack','LOCAL_ACKNOWLEDGED');click('#service-plan-from-receipt');wait('servicePlanView',lambda x:isinstance(x,dict));act('P4','VERIFY');open_business('localcase','localCaseView');local_decision('#local-case-validate');preparation_plan();act('P5','VERIFY');open_business('localcase','localCaseView');final_close=local_decision('#local-case-close');assert final_close['case_state']=='WAITING_CONFIRMATION' and final_close['cycle']==2;assert final_close['history'][:len(first_history)]==first_history
 final=preparation_plan();final=act('P5','VERIFY');assert all(s['state']=='VERIFIED' for s in final['steps']);assert {s['adapter_id']:s['id'] for s in final['steps']}==ids and final['plan_id']==plan_id;writes=value('writeRequests');revision=final['revision'];viewport_capture('recovery-current-five-verified','#service-plan-steps',metrics);viewport_capture('recovery-current-history','#service-plan-history',metrics)
 # Existing old receipt is readable as immutable history and must retain its
 # original material snapshot and acknowledged record after the new generation.
 old=value('(async()=>{const r=await fetch("/api/executor-receipts/'+old_step+'",{headers:{Authorization:"Bearer "+document.querySelector("#token").value}});if(!r.ok)throw Error("old history denied");return await r.json();})()');assert old['step']['id']==old_step and old['current_receipt']['id']==old_receipt['id'];assert old['step']['state']=='LOCAL_ACKNOWLEDGED';assert old['step']['preparation_revision']==first_receipt['step']['preparation_revision'] and old['step']['preparation_sha256']==first_receipt['step']['preparation_sha256'];assert newreceipt['step']['preparation_revision']>old['step']['preparation_revision'] and newreceipt['step']['preparation_sha256']==old['step']['preparation_sha256']
 first_fact,current_fact=context['confirmed_fact_versions'];assert current_fact['revision']>first_fact['revision'] and current_fact['decision_ref']!=first_fact['decision_ref'] and current_fact['decision_sha256']!=first_fact['decision_sha256'] and current_fact['source_sha256']!=first_fact['source_sha256'];assert current_fact['history'][:len(first_fact['history'])]==first_fact['history'];assert set(c['assertion_id'] for c in current_fact['history'][-1]['choices'])==set(context['selected_facts'].values())
 current_fact=value('(async()=>{const r=await fetch("/api/preparations/'+context['preparation_id']+'/fact-clarifications",{headers:{Authorization:"Bearer "+document.querySelector("#token").value}});if(!r.ok)throw Error("current fact history denied");return await r.json();})()');assert current_fact['state']=='CURRENT' and current_fact['satisfied'] and current_fact['preparation_revision']==newreceipt['step']['preparation_revision'];assert current_fact['history'][:len(first_fact['history'])]==first_fact['history'] and len(current_fact['history'][-1]['choices'])==3 and {c['field']:c['assertion_id'] for c in current_fact['history'][-1]['choices']}==context['selected_facts']
 old_index=value('(async()=>{const r=await fetch("/api/executor-receipts",{headers:{Authorization:"Bearer "+document.querySelector("#token").value}});return (await r.json()).items.findIndex(s=>s.id==="'+old_step+'");})()');assert old_index>=0;click('#receipt-list');wait("document.querySelectorAll('#receipt-items button').length",lambda x:x==2);click('#receipt-items button:nth-child('+str(old_index+1)+')');wait('receiptView',lambda x:isinstance(x,dict) and x['step']['id']==old_step);assert value("document.querySelector('#receipt-reopen').disabled") and value("document.querySelector('#receipt-ack').disabled");viewport_capture('recovery-old-receipt-read-only','#receipt-detail',metrics)
 browser('reload');browser('snapshot','-i');switch('owner');track_writes();reloaded=preparation_plan();assert reloaded['revision']==revision and reloaded['plan_id']==plan_id and {s['adapter_id']:s['id'] for s in reloaded['steps']}==ids;assert all(s['state']=='VERIFIED' for s in reloaded['steps']);open_business('dispatch','dispatchView');assert value('dispatchView.receipt_step_id')==new_step;assert value('writeRequests.length')==0
 fact_history=fact_late_guards();preparation_plan();value(r"(()=>{window.savedLateFetch=fetch;window.releaseLateRead=null;window.fetch=async(p,o)=>{const r=await savedLateFetch(p,o);if(String(p).endsWith('/service-case-plan')&&(!o?.method||o.method==='GET'))await new Promise(resolve=>releaseLateRead=resolve);return r;};return true;})()");click('#service-plan-read');wait('typeof releaseLateRead',lambda x:x=='function');value('(()=>{window.fetch=savedLateFetch;return true;})()');preparation_plan(context['second_goal']);value('(()=>{releaseLateRead();return true;})()');browser('snapshot','-i');assert value('servicePlanView.preparation_id')==context['second_preparation_id'];preparation_plan()
 value(r"(()=>{window.savedLateFetch=fetch;window.releaseLateRead=null;window.fetch=async(p,o)=>{const r=await savedLateFetch(p,o);if(String(p).endsWith('/service-case-plan')&&(!o?.method||o.method==='GET'))await new Promise(resolve=>releaseLateRead=resolve);return r;};return true;})()");click('#service-plan-read');wait('typeof releaseLateRead',lambda x:x=='function');switch('unassigned');value('(()=>{window.fetch=savedLateFetch;releaseLateRead();return true;})()');browser('snapshot','-i');assert value('servicePlanView') is None
 switch('unassigned');negative=value('(async()=>{const r=await fetch("/api/preparations/'+context['preparation_id']+'/dispatch",{headers:{Authorization:"Bearer "+document.querySelector("#token").value}});return r.status;})()');assert negative==403
 assert not browser('errors');a.report.write_text(json.dumps({'scope':'ISOLATED_SYNTHETIC_NATIVE_CASE_FACT_PURPOSE_AND_FIVE_STEP_RECOVERY','facts_explicit_three_choices':True,'facts_competitor_retained':True,'facts_committed_unknown_exact_retry_after_refresh':True,'facts_late_case_and_token_private_clear':True,'fact_purpose_history':fact_history,'initial_confirmed_fact_version':first_fact,'current_confirmed_fact_version':current_fact,'material_sha_preserved_without_material_changes':True,'actual_fact_source_change':'ORIGINAL_API_FACT_ASSERTION_VIA_NATIVE_UI_STALES_ALL_FIVE','facts_fresh_explicit_reconfirmation_and_manual_review':True,'preparation_id':context['preparation_id'],'case_id':context['case_id'],'run_id':context['run_id'],'case_precreated_before_browser':True,'initial_plan_id':plan_id,'stable_case_step_ids':ids,'old_receipt_step_id':old_step,'new_receipt_step_id':new_step,'old_receipt_id':old_receipt['id'],'new_receipt_id':newreceipt['current_receipt']['id'],'old_step_preparation_revision':old['step']['preparation_revision'],'new_step_preparation_revision':newreceipt['step']['preparation_revision'],'old_step_preparation_sha256':old['step']['preparation_sha256'],'new_step_preparation_sha256':newreceipt['step']['preparation_sha256'],'plan_revision':revision,'business_posts':writes,'cross_step_premature_submit_rejected':True,'materials_invalidated_all_five':True,'resource_native_rebind_revision':2,'same_executor_explicit_reoffer_new_acceptance':True,'committed_reoffer_reply_lost_original_body_key_recovered':True,'old_receipt_immutable_history_retained':True,'new_step_receipt_starts_fresh_version_one':True,'reload_stable_current_case_steps':True,'historical_receipt_native_controls_disabled':True,'late_case_read_ignored':True,'late_token_read_ignored':True,'local_case_cycle':2,'original_case_state':'WAITING_CONFIRMATION','unassigned_status':negative,'viewport_checks':metrics,'case_goal_completed':False,'formal_business_publication':False,'external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE','model_calls':0,'budget':0},ensure_ascii=False,indent=2)+'\n')
try:main()
finally:browser('close')
