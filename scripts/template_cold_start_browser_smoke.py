"""Native isolated template publication and fresh enterprise Case consumption."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time,uuid
from parkweave.process_env import minimal_environment
p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True);p.add_argument('--base-port',type=int,default=8781);a=p.parse_args();context=json.load(sys.stdin);root=Path.cwd()
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
cached=[x for x in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(x.read_text()).get('version')=='0.38.2'];assert cached
sessions=['pw-tc-'+uuid.uuid4().hex[:10],'pw-tc-'+uuid.uuid4().hex[:10]];active_session=sessions[0]
def browser(*args,stdin=None):
 cmd=['node',str(sorted(cached)[0].parent/'bin/agent-browser.js'),'--session',active_session,'--executable-path','/usr/bin/chromium','--args','--no-sandbox']
 r=subprocess.run(cmd+list(args),input=stdin,capture_output=True,text=True,env=env,timeout=30)
 if r.returncode:raise RuntimeError('cached isolated template browser failed: '+r.stderr[:300])
 return r.stdout.strip()
def value(expr):
 r=json.loads(browser('eval','(async()=>JSON.stringify(await ('+expr+')))()'));return json.loads(r) if isinstance(r,str) else r
def wait(expr,pred,timeout=25):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  x=value(expr)
  if pred(x):return x
  time.sleep(.1)
 raise AssertionError('template browser timeout '+expr)
def click(selector):
 value('(()=>{window.nativeClicks=0;const b=document.querySelector('+json.dumps(selector)+');b.addEventListener("click",()=>nativeClicks++,{once:true});b.scrollIntoView({block:"center"});return true;})()');browser('snapshot','-i');browser('click',selector);browser('snapshot','-i');assert value('nativeClicks')==1,'native button did not receive click: '+selector
def token(selector,role):
 browser('eval','--stdin',stdin='document.querySelector('+json.dumps(selector)+').value='+json.dumps(context['tokens'][role])+';document.querySelector('+json.dumps(selector)+").dispatchEvent(new Event('input'));undefined")
def track_writes():
 value("(()=>{window.originalFetch=fetch;window.writeRequests=[];window.fetch=(p,o)=>{if(o?.method&&o.method!=='GET')writeRequests.push({path:String(p),action:JSON.parse(o.body||'{}').action||'CREATE'});return originalFetch(p,o);};return true;})()")
def capture(name,selector):
 value('(()=>{document.querySelector('+json.dumps(selector)+').scrollIntoView({block:"start"});return true;})()');browser('snapshot','-i');browser('screenshot',str(a.screenshots.resolve()/name))
def product_ready():
 wait('materialCorrectionsView',lambda x:isinstance(x,dict) and x['preparation_id']==value('preparationView.preparation.id') and x['preparation_revision']==value('preparationView.preparation.revision'));return value('preparationView')
def product_select(goal):
 click('[data-tab=collaboration]');click('#prep-list');wait("document.querySelector('#prep-items').textContent",lambda x:goal in x);selector=value("'#prep-items button:nth-child('+(Array.from(document.querySelectorAll('#prep-items button')).findIndex(b=>b.textContent.startsWith("+json.dumps(goal)+"))+1)+')'");click(selector);wait('preparationView',lambda x:isinstance(x,dict));return product_ready()
def product_add(slot,text):
 revision=value('preparationView.preparation.revision');browser('select','#prep-slot',slot);browser('fill','#prep-text',text);browser('fill','#prep-source-label','SYNTHETIC new enterprise current material source');click('#prep-evidence button');wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>revision);return product_ready()
def product_decide(selector,reason):
 revision=value('preparationView.preparation.revision');browser('fill','#prep-reason',reason);click(selector);wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>revision);return product_ready()
def template_actor(role):
 browser('select','#template-actor',context['actors'][role]);click('#template-refresh');return wait('view',lambda x:isinstance(x,dict))
def template_action(action):
 revision=value('view.revision');browser('fill','#template-reason','SYNTHETIC explicit isolated '+action);click('[data-template-action="'+action+'"]');return wait('view',lambda x:isinstance(x,dict) and x['revision']>revision)
def template_page(owner=None):
 browser('open',f'http://127.0.0.1:{a.base_port}/template');browser('snapshot','-i');wait('status',lambda x:isinstance(x,dict) and x['enabled_for_isolated_tests']);track_writes()
 if owner:token('#consumer-token',owner)
def consumer_fields(name):
 click('#consumer-catalog');wait('catalog',lambda x:isinstance(x,dict));assert len(value('catalog.templates'))==1;browser('select','#consumer-reviewer',context['reviewer_ids']['b' if name=='b1' else 'a']);browser('fill','#consumer-goal',goals[name]);browser('fill','#consumer-need-summary','SYNTHETIC entirely new '+name+' enterprise request');browser('fill','#consumer-need-source','SYNTHETIC '+name+' independent request source');browser('fill','#consumer-material-outline','SYNTHETIC entirely new '+name+' enterprise material list');browser('fill','#consumer-outline-source','SYNTHETIC '+name+' independent material source')
def consumer_create(lost=False):
 if lost:value("(()=>{window.savedCommitFetch=fetch;window.consumerAttempts=[];window.dropConsumerReply=true;window.fetch=async(p,o)=>{if(String(p)==='/api/template-consumer/instances'&&o?.method==='POST'){consumerAttempts.push({key:o.headers['Idempotency-Key'],body:o.body});if(dropConsumerReply){dropConsumerReply=false;const r=await savedCommitFetch(p,o);if(!r.ok)return r;await r.text();throw Error('SYNTHETIC_COMMITTED_REPLY_LOST');}}return savedCommitFetch(p,o);};return true;})()")
 click('#consumer-create')
 if lost:
  wait("document.querySelector('#consumer-retry').hidden",lambda x:x is False);assert value('cp.state')=='UNKNOWN' and value("document.querySelector('#consumer-create').disabled");click('#consumer-retry');wait('instance',lambda x:isinstance(x,dict));assert value('consumerAttempts.length')==2 and value('consumerAttempts[0].key===consumerAttempts[1].key&&consumerAttempts[0].body===consumerAttempts[1].body');value('(()=>{window.fetch=savedCommitFetch;return true;})()')
 else:wait('instance',lambda x:isinstance(x,dict))
 for _ in range(20):
  if value('instance.state')=='PLAN_ADOPTED':return value('instance')
  click('#consumer-resume');wait('cp',lambda x:x is None);time.sleep(.1)
 raise AssertionError('actual worker/consumer did not reach PLAN_ADOPTED')
def product_flow(name,record):
 browser('open',f'http://127.0.0.1:{a.base_port}/');browser('snapshot','-i');track_writes();token('#token','specialist_b' if name=='b1' else 'specialist_a');row=product_select(goals[name]);assert row['preparation']['id']==record['preparation_id'] and len(row['current_materials'])==2;product_decide('#prep-review','SYNTHETIC manual review of this new enterprise current materials only');token('#token','owner_b' if name=='b1' else 'owner_a');product_select(goals[name]);product_decide('#prep-confirm','SYNTHETIC owner confirms this current new material packet');click('#service-plan-prepare');plan=wait('servicePlanView',lambda x:isinstance(x,dict));assert plan['plan_id']==record['plan_id'] and len(plan['steps'])==1 and plan['steps'][0]['adapter_id']=='P1';step=plan['steps'][0];browser('fill','#service-plan-reason','SYNTHETIC explicitly verify newly reviewed sources in this Case');click('[data-service-step="'+step['id']+'"][data-service-action="VERIFY"]');verified=wait('servicePlanView',lambda x:isinstance(x,dict) and x['state']=='VERIFIED');assert not verified['case_goal_completed'];return verified,value('writeRequests')
goals={}
def main():
 global active_session,goals
 a.screenshots.mkdir(parents=True,exist_ok=False);template_page();browser('fill','#template-park',context['park_id']);browser('fill','#template-id',context['template_id']);template_actor('author');browser('fill','#template-name','SYNTHETIC registered template for entirely new enterprises');browser('fill','#template-source-revision','1');browser('fill','#template-source-statement','SYNTHETIC neutral specification; each enterprise supplies its own new current materials');template_action('SAVE_DRAFT');template_action('SUBMIT');template_actor('reviewer');template_action('REVIEW');template_actor('publisher');published=template_action('CANDIDATE_PUBLISH');assert published['candidate_available'] and not published['business_publication'] and not published['deployment_enabled'];assert len(published['releases'])==1;release=published['releases'][0];release_id=release['release_id'];release_sha=release['release_sha256'];governance_writes=value('writeRequests');metrics=[]
 for width in (1200,390,320):
  browser('set','viewport',str(width),'900' if width==1200 else '844');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['scroll']<=m['width'];metrics.append({'stage':'isolated-candidate-published',**m});capture('template-candidate-'+str(width)+'.png','#banner')
 browser('set','viewport','1200','900');suffix=uuid.uuid4().hex[:8];goals={n:'SYNTHETIC ENG098 fresh '+n+' '+suffix for n in ('a1','b1','a2')};records={};product_writes={};consumer_writes={};verified_steps={}
 token('#consumer-token','owner_a');consumer_fields('a1');records['a1']=consumer_create(lost=True);consumer_writes['a1']=value('writeRequests')[len(governance_writes):];verified,product_writes['a1']=product_flow('a1',records['a1']);verified_steps['a1']=verified['steps'][0]['id']
 active_session=sessions[1];template_page('owner_b');assert value("document.querySelector('#consumer-goal').value")=='' and value('instance') is None;consumer_fields('b1');records['b1']=consumer_create();consumer_writes['b1']=value('writeRequests');verified,product_writes['b1']=product_flow('b1',records['b1']);verified_steps['b1']=verified['steps'][0]['id']
 active_session=sessions[0];template_page('owner_a');consumer_fields('a2');records['a2']=consumer_create();consumer_writes['a2']=value('writeRequests');verified,product_writes['a2']=product_flow('a2',records['a2']);verified_steps['a2']=verified['steps'][0]['id'];assert len({r['case_id'] for r in records.values()})==3 and len({r['run_id'] for r in records.values()})==3 and len(set(verified_steps.values()))==3
 browser('reload');browser('snapshot','-i');token('#token','owner_a');product_select(goals['a1']);click('#service-plan-prepare');wait('servicePlanView',lambda x:isinstance(x,dict));assert value('servicePlanView.state')=='VERIFIED' and value('servicePlanView.steps[0].id')==verified_steps['a1']
 for width in (1200,390,320):
  browser('set','viewport',str(width),'900' if width==1200 else '844');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['scroll']<=m['width'];metrics.append({'stage':'new-enterprise-P1-verified',**m});capture('template-new-case-P1-'+str(width)+'.png','#service-plan-steps')
 browser('set','viewport','1200','900');template_page('owner_a');browser('fill','#consumer-instance-id',records['a1']['instance_id']);click('#consumer-read');old=wait('instance',lambda x:isinstance(x,dict));binding=old['binding'];assert old['release_available'];consumer_fields('a2');browser('fill','#consumer-goal','SYNTHETIC withdrawn stale attempt must not create fourth Case')
 # Keep a genuine stale enterprise catalog in the first session while the second withdraws.
 active_session=sessions[1];template_page();browser('fill','#template-park',context['park_id']);browser('fill','#template-id',context['template_id']);template_actor('publisher');withdrawn=template_action('WITHDRAW');assert not withdrawn['candidate_available'];withdraw_writes=value('writeRequests');assert not browser('errors');active_session=sessions[0];click('#consumer-create');wait("document.querySelector('#consumer-error').textContent",lambda x:bool(x));assert value('instance') is None and value("document.querySelector('#consumer-result').textContent")=='';click('#consumer-catalog');wait('catalog.templates.length',lambda x:x==0);assert value("document.querySelector('#consumer-create').disabled");browser('fill','#consumer-instance-id',records['a1']['instance_id']);click('#consumer-read');after=wait('instance',lambda x:isinstance(x,dict) and x['release_available'] is False);assert after['binding']==binding and after['case_id']==records['a1']['case_id'] and after['preparation_id']==records['a1']['preparation_id'];withdrawal_writes=value('writeRequests')
 for width in (1200,390,320):
  browser('set','viewport',str(width),'900' if width==1200 else '844');m=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert m['scroll']<=m['width'];metrics.append({'stage':'withdrawn-history-new-creation-disabled',**m});capture('template-withdrawn-history-'+str(width)+'.png','#consumer-status')
 browser('set','viewport','1200','900');token('#consumer-token','owner_b');foreign=value('(async()=>{const r=await fetch("/api/template-consumer/instances/'+records['a1']['instance_id']+'",{headers:{Authorization:"Bearer "+document.querySelector("#consumer-token").value}});return r.status;})()');assert foreign==403
 # A delayed genuine B history response cannot restore private data after A replaces the token.
 browser('fill','#consumer-instance-id',records['b1']['instance_id']);value("(()=>{window.savedReadFetch=fetch;window.releaseInstanceRead=null;window.fetch=async(p,o)=>{const r=await savedReadFetch(p,o);if(String(p).endsWith('/"+records['b1']['instance_id']+"'))await new Promise(resolve=>releaseInstanceRead=resolve);return r;};return true;})()");click('#consumer-read');wait('typeof releaseInstanceRead',lambda x:x=='function');token('#consumer-token','owner_a');value('(()=>{window.fetch=savedReadFetch;releaseInstanceRead();return true;})()');browser('snapshot','-i');assert value('instance') is None and value("document.querySelector('#consumer-result').textContent")=='';assert not browser('errors')
 a.report.write_text(json.dumps({'scope':'ISOLATED_TEMPLATE_GOVERNANCE_AND_FRESH_ENTERPRISE_PRODUCT_FLOW','release_id':release_id,'release_sha256':release_sha,'cold_enterprise_sessions':2,'candidate_role_flow':['SAVE_DRAFT','SUBMIT','REVIEW','CANDIDATE_PUBLISH','WITHDRAW'],'instances':{k:{j:r[j] for j in ('instance_id','case_id','run_id','preparation_id','plan_id','binding')} for k,r in records.items()},'stable_P1_steps':verified_steps,'governance_posts':governance_writes,'consumer_posts':consumer_writes,'product_posts':product_writes,'withdraw_posts':withdraw_writes,'stale_consumer_posts':withdrawal_writes,'lost_committed_consumer_reply_same_body_key_recovered':True,'fresh_materials_each_enterprise':True,'new_enterprise_manual_review_confirm_real_P1_verify':True,'same_enterprise_second_case_fresh':True,'cross_org_instance_status':foreign,'late_identity_read_ignored':True,'withdrawal_stale_attempt_rejected_no_fourth_case':True,'withdrawn_catalog_disables_creation':True,'old_instance_binding_retained':True,'reload_P1_id_and_verified_state_persisted':True,'viewport_checks':metrics,'formal_business_publication':False,'qualification_confirmed':False,'case_goal_completed':False,'new_authority_created':False,'run_assignments_created':False,'model_calls':0,'budget':0},ensure_ascii=False,indent=2)+'\n')
try:main()
except Exception:
 try:
  safe=value("({url:location.pathname,feedback:document.querySelector('#page-feedback')?.textContent||'',preparation_error:document.querySelector('#prep-error')?.textContent||'',write_count:typeof writeRequests==='undefined'?0:writeRequests.length})");safe['browser_errors']=browser('errors');a.report.with_name('browser-failure.json').write_text(json.dumps(safe,indent=2)+'\n')
 except Exception:pass
 raise
finally:
 for active_session in sessions:
  try:browser('close')
  except RuntimeError:pass
