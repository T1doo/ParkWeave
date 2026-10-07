"""Fresh native Cases and per-slot corrections on an owned synthetic API."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time,uuid,hashlib
from parkweave.process_env import minimal_environment
p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True);p.add_argument('--base-port',type=int,default=8780);a=p.parse_args();context=json.load(sys.stdin);root=Path.cwd()
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
cached=[x for x in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(x.read_text()).get('version')=='0.38.2'];assert cached
sessions=['pw-mc-'+uuid.uuid4().hex[:10],'pw-mc-'+uuid.uuid4().hex[:10]];active_session=sessions[0]
def browser(*args,stdin=None):
 cmd=['node',str(sorted(cached)[0].parent/'bin/agent-browser.js'),'--session',active_session,'--executable-path','/usr/bin/chromium','--args','--no-sandbox']
 r=subprocess.run(cmd+list(args),input=stdin,capture_output=True,text=True,env=env,timeout=30)
 if r.returncode:raise RuntimeError('cached local material-correction browser failed: '+r.stderr[:300])
 return r.stdout.strip()
def value(expr):
 r=json.loads(browser('eval','(async()=>JSON.stringify(await ('+expr+')))()'));return json.loads(r) if isinstance(r,str) else r
def wait(expr,pred,timeout=20):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  x=value(expr)
  if pred(x):return x
  time.sleep(.1)
 raise AssertionError('material-correction browser timeout '+expr)
def click(selector):
 value('(()=>{window.nativeClicks=0;const b=document.querySelector('+json.dumps(selector)+');b.addEventListener("click",()=>nativeClicks++,{once:true});b.scrollIntoView({block:"center"});return true;})()');browser('snapshot','-i');browser('click',selector);browser('snapshot','-i');assert value('nativeClicks')==1,'native button did not receive click: '+selector
def switch(role):
 browser('eval','--stdin',stdin="document.querySelector('#token').value="+json.dumps(context['tokens'][role])+";document.querySelector('#token').dispatchEvent(new Event('input'));undefined");assert value('preparationView') is None
def track_writes():
 value("(()=>{window.originalFetch=fetch;window.writeRequests=[];window.fetch=(p,o)=>{if(o?.method&&o.method!=='GET')writeRequests.push({path:String(p),action:JSON.parse(o.body||'{}').action||'CREATE'});return originalFetch(p,o);};return true;})()")
def ready():
 wait('materialCorrectionsView',lambda x:isinstance(x,dict) and x['preparation_id']==value('preparationView.preparation.id') and x['preparation_revision']==value('preparationView.preparation.revision'));return value('preparationView')
def select(goal):
 click('[data-tab=collaboration]');click('#prep-list');wait("document.querySelector('#prep-items').textContent",lambda x:goal in x);selector=value("'#prep-items button:nth-child('+(Array.from(document.querySelectorAll('#prep-items button')).findIndex(b=>b.textContent.startsWith("+json.dumps(goal)+"))+1)+')'");click(selector);wait('preparationView',lambda x:isinstance(x,dict));return ready()
def corrections():
 id=value('preparationView.preparation.id');return value('(async()=>{const r=await fetch("/api/preparations/'+id+'/material-corrections",{headers:{Authorization:"Bearer "+document.querySelector("#token").value}});if(!r.ok)throw Error("correction read denied");return await r.json();})()')
def create(goal):
 click('[data-tab=service]');click('#prep-catalog');wait('prepCatalog',lambda x:isinstance(x,dict));browser('fill','#prep-goal',goal);click('#prep-create button');wait('preparationView',lambda x:isinstance(x,dict));row=ready();assert row['preparation']['goal']==goal;return row['preparation']
def draft(slot,text):browser('select','#prep-slot',slot);browser('fill','#prep-text',text);browser('fill','#prep-source-label','SYNTHETIC independent new material source')
def add(slot,text):
 revision=value('preparationView.preparation.revision');draft(slot,text);click('#prep-evidence button');wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>revision);return ready()
def decision(selector,reason):
 revision=value('preparationView.preparation.revision');browser('fill','#prep-reason',reason);click(selector);wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>revision);return ready()
def ask_both():
 for slot in ('need_summary','material_outline'):browser('check','[data-correction-slot="'+slot+'"]')
 return decision('#prep-correction','SYNTHETIC need new versions of both named materials')
def lost_reply_add(slot,text):
 revision=value('preparationView.preparation.revision');draft(slot,text)
 value("(()=>{window.savedCommitFetch=fetch;window.addAttempts=[];window.dropAddReply=true;window.fetch=async(p,o)=>{if(String(p).endsWith('/commands')&&JSON.parse(o?.body||'{}').action==='ADD_EVIDENCE'){addAttempts.push({key:o.headers['Idempotency-Key'],body:o.body});if(dropAddReply){dropAddReply=false;const r=await savedCommitFetch(p,o);if(!r.ok)return r;await r.text();throw Error('SYNTHETIC_COMMITTED_REPLY_LOST');}}return savedCommitFetch(p,o);};return true;})()")
 click('#prep-evidence button');wait("document.querySelector('#prep-command-retry').hidden",lambda x:x is False);assert value('addAttempts.length')==1 and value('prepCommandPending.state')=='UNKNOWN';assert value("document.querySelector('#prep-evidence button').disabled");click('#prep-command-retry');wait('preparationView',lambda x:isinstance(x,dict) and x['preparation']['revision']>revision);row=ready();assert value('addAttempts.length')==2 and value('addAttempts[0].key===addAttempts[1].key&&addAttempts[0].body===addAttempts[1].body');value('(()=>{window.fetch=savedCommitFetch;return true;})()');return row
def capture(name,panel):
 assert 'undefined' not in value("document.querySelector('#material-corrections-panel').textContent");value('(()=>{document.querySelector('+json.dumps(panel)+').scrollIntoView({block:"start"});return true;})()');browser('snapshot','-i');browser('screenshot',str(a.screenshots.resolve()/name))
def main():
 global active_session
 a.screenshots.mkdir(parents=True,exist_ok=False);browser('open',f'http://127.0.0.1:{a.base_port}/');browser('snapshot','-i');switch('owner_a');click('[data-tab=collaboration]');track_writes();suffix=uuid.uuid4().hex[:8];goals={'a1':'SYNTHETIC ENG097 A first '+suffix,'b1':'SYNTHETIC ENG097 B fresh '+suffix,'a2':'SYNTHETIC ENG097 A independent '+suffix};parents={}
 for name,owner in [('a1','owner_a'),('b1','owner_b'),('a2','owner_a')]:
  switch(owner);parents[name]=create(goals[name]);add('need_summary','SYNTHETIC fresh '+name+' original request');add('material_outline','SYNTHETIC fresh '+name+' original materials');assert corrections()['items']==[]
 assert len({p['case_id'] for p in parents.values()})==3 and len({p['run_id'] for p in parents.values()})==3
 ids={};resolved={};metrics=[]
 for name,owner,specialist in [('a1','owner_a','specialist_a'),('b1','owner_b','specialist_b')]:
  switch(specialist);select(goals[name]);ask_both();asked=corrections();assert len(asked['items'])==2 and all(t['status']=='REQUESTED' and t['base_version']==1 and t['reason'] for t in asked['items']);ids[name]=[t['id'] for t in asked['items']]
  switch(owner);select(goals[name]);assert [t['id'] for t in corrections()['items']]==ids[name]
  if name=='a1':
   revision=value('preparationView.preparation.revision');writes=value('writeRequests.length');draft('need_summary','');click('#prep-evidence button');assert value('writeRequests.length')==writes and value('preparationView.preparation.revision')==revision
   draft('need_summary','   ');click('#prep-evidence button');wait("document.querySelector('#prep-error').textContent",lambda x:bool(x));click('#prep-refresh');wait('preparationView',lambda x:isinstance(x,dict));ready();assert value('preparationView.preparation.revision')==revision and all(t['status']=='REQUESTED' and t['current_version']==1 for t in corrections()['items']);lost_reply_add('need_summary','SYNTHETIC fresh a1 corrected request v2')
  else:add('need_summary','SYNTHETIC fresh b1 corrected request v2')
  partial=corrections();assert sorted(t['status'] for t in partial['items'])==['REQUESTED','SUBMITTED_FOR_REVIEW'];assert not partial['can_review'];add('material_outline','SYNTHETIC fresh '+name+' corrected materials v2');submitted=corrections();assert all(t['status']=='SUBMITTED_FOR_REVIEW' and t['current_version']==2 for t in submitted['items'])
  switch(specialist);select(goals[name]);decision('#prep-review','SYNTHETIC reviewed both new sources only');reviewed=corrections();assert all(t['status']=='RESOLVED' and t['current_review_valid'] and t['resolution'] for t in reviewed['items']);switch(owner);select(goals[name]);decision('#prep-confirm','SYNTHETIC owner confirms current reviewed material packet');resolved[name]=corrections();assert all(t['current_review_valid'] and t['id'] in ids[name] and len(t['submissions'])==1 for t in resolved[name]['items'])
 assert set(ids['a1']).isdisjoint(ids['b1'])
 switch('owner_a');select(goals['a2']);assert corrections()['items']==[]
 # A genuinely stale command races a second cold native browser, with no setup mutation.
 draft('need_summary','SYNTHETIC STALE_COMMAND_MUST_NOT_APPEND');value("(()=>{window.savedRaceFetch=fetch;window.releaseStaleCommand=null;window.staleWriteStatus=null;window.fetch=async(p,o)=>{if(String(p).endsWith('/commands')&&JSON.parse(o?.body||'{}').action==='ADD_EVIDENCE'){await new Promise(resolve=>releaseStaleCommand=resolve);const r=await savedRaceFetch(p,o);staleWriteStatus=r.status;return r;}return savedRaceFetch(p,o);};return true;})()");click('#prep-evidence button');wait('typeof releaseStaleCommand',lambda x:x=='function')
 active_session=sessions[1];browser('open',f'http://127.0.0.1:{a.base_port}/');browser('snapshot','-i');switch('owner_a');click('[data-tab=collaboration]');track_writes();select(goals['a2']);add('need_summary','SYNTHETIC independent a2 concurrent new source');secondary_writes=value('writeRequests');assert len(secondary_writes)==1;assert not browser('errors');active_session=sessions[0];value('(()=>{releaseStaleCommand();return true;})()');wait('staleWriteStatus',lambda x:x==409);wait("document.querySelector('#prep-error').textContent",lambda x:bool(x));value('(()=>{window.fetch=savedRaceFetch;return true;})()');click('#prep-refresh');wait('preparationView',lambda x:isinstance(x,dict));ready();assert corrections()['items']==[] and value('preparationView.current_materials.find(m=>m.slot==="need_summary").version')==2 and 'STALE_COMMAND_MUST_NOT_APPEND' not in value("document.querySelector('#prep-history').textContent")
 # Resolution is durable history after source changes; it cannot claim current review.
 select(goals['a1']);decision('#prep-reopen','SYNTHETIC reopen current packet for a new source');add('need_summary','SYNTHETIC a1 later source changes reviewed packet');first_writes=value('writeRequests');browser('reload');browser('snapshot','-i');switch('owner_a');click('[data-tab=collaboration]');track_writes();select(goals['a1']);stale=corrections();assert [t['id'] for t in stale['items']]==ids['a1'] and all(not t['current_review_valid'] for t in stale['items']);assert any(t['status']=='STALE_RESOLUTION' and t['source_status']=='HISTORICAL_SOURCE_CHANGED' for t in stale['items'])
 value("(()=>{document.querySelector('#material-corrections-history').closest('details').open=true;return true;})()")
 for width in (1200,390,320):
  browser('set','viewport',str(width),'900' if width==1200 else '844');metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];metrics.append({'stage':'changed-source-history',**metric});capture('material-correction-history-'+str(width)+'.png','#material-corrections-history')
 browser('set','viewport','1200','900');switch('owner_b');select(goals['b1']);current=corrections();assert all(t['current_review_valid'] for t in current['items']);assert value('preparationView.preparation.state')=='LOCAL_CONFIRMED';value("(()=>{document.querySelector('#material-corrections-history').closest('details').open=true;return true;})()")
 for width in (1200,390,320):
  browser('set','viewport',str(width),'900' if width==1200 else '844');metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];metrics.append({'stage':'current-resolution',**metric});capture('material-correction-resolved-'+str(width)+'.png','#material-corrections-history')
 browser('set','viewport','1200','900');status=value('(async()=>{const r=await fetch("/api/preparations/'+parents['a1']['id']+'/material-corrections",{headers:{Authorization:"Bearer "+document.querySelector("#token").value}});return r.status;})()');assert status==403
 switch('owner_a');select(goals['a1']);value("(()=>{window.savedReadFetch=fetch;window.releaseCorrectionRead=null;window.fetch=async(p,o)=>{const r=await savedReadFetch(p,o);if(String(p).endsWith('/material-corrections'))await new Promise(resolve=>releaseCorrectionRead=resolve);return r;};return true;})()");click('#prep-refresh');wait('typeof releaseCorrectionRead',lambda x:x=='function');value('(()=>{window.fetch=savedReadFetch;return true;})()');select(goals['a2']);value('(()=>{releaseCorrectionRead();return true;})()');browser('snapshot','-i');assert value('materialCorrectionsView.preparation_id')==parents['a2']['id'] and value('materialCorrectionsView.items.length')==0
 select(goals['a1']);value("(()=>{window.savedReadFetch=fetch;window.releaseCorrectionRead=null;window.fetch=async(p,o)=>{const r=await savedReadFetch(p,o);if(String(p).endsWith('/material-corrections'))await new Promise(resolve=>releaseCorrectionRead=resolve);return r;};return true;})()");click('#prep-refresh');wait('typeof releaseCorrectionRead',lambda x:x=='function');switch('owner_b');value('(()=>{window.fetch=savedReadFetch;releaseCorrectionRead();return true;})()');browser('snapshot','-i');assert value('materialCorrectionsView') is None and value('preparationView') is None;select(goals['b1']);assert all(t['current_review_valid'] for t in corrections()['items']);assert value('writeRequests.length')==0 and not browser('errors')
 a.report.write_text(json.dumps({'scope':'SYNTHETIC_FRESH_CASE_ITEM_MATERIAL_CORRECTIONS','cold_browser_sessions':2,'new_cases':parents,'stable_target_ids':ids,'independent_enterprise_materials':True,'same_enterprise_second_case_isolated':True,'two_named_slot_corrections_resolved_by_real_review':True,'incomplete_input_no_partial_write':True,'committed_add_unknown_reply_original_body_key_recovered':True,'stale_native_command_status':409,'stale_native_command_no_material_append':True,'cross_enterprise_correction_get':403,'late_case_read_ignored':True,'late_identity_read_cleared':True,'changed_source_resolution_historical_after_reload':True,'current_other_enterprise_resolution_preserved':True,'primary_browser_business_posts':first_writes,'secondary_browser_business_posts':secondary_writes,'navigation_business_posts':0,'viewport_checks':metrics,'authority_created':False,'run_assignments_created':False,'case_goal_completed':False,'external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE','models':0,'budget':0},ensure_ascii=False,indent=2)+'\n')
try:main()
except Exception:
 try:
  safe=value("({feedback:document.querySelector('#page-feedback').textContent,preparation_error:document.querySelector('#prep-error').textContent,correction_error:document.querySelector('#material-corrections-error').textContent,catalog_loaded:!!prepCatalog,write_count:typeof writeRequests==='undefined'?0:writeRequests.length})");safe['browser_errors']=browser('errors');a.report.with_name('browser-failure.json').write_text(json.dumps(safe,indent=2)+'\n')
 except Exception:pass
 raise
finally:
 for active_session in sessions:
  try:browser('close')
  except RuntimeError:pass
