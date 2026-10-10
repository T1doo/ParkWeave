"""Independent exact-SHA real HTTP/PG probes; no frozen source edits."""
from pathlib import Path
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json,time,httpx,pytest
from psycopg.types.json import Jsonb
from conftest import pg,fixture
from test_case_goal_results_browser import goal_page,open_case,read_page,wait_held,settle
from test_case_goal_results import link_fixture,receipt_fixture,preparation_fixture,start,complete,snapshot,verified,GOALS,save
from test_case_lifecycle import read as local_read,act as local_act
from test_preparation import headers,read as prep_read,command as prep_act,add
from test_service_case_steps import adopt
OUT=Path('/workspace/ParkWeave/.runtime/independent-case-goal-results-final-review/probes')

def httpget(page,f,p,user='fixture-a'):
 return page.request.get(page.url.rstrip('/')+'/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2],user))

@pytest.mark.parametrize('damage',['review-payload-typed-revision','confirm-case','missing-local-event','receipt-first-version-gap','accept-payload-executor','review-grant-revoked'])
def test_partial_current_proof_damage_real_http(goal_page,damage):
 f,page,_=goal_page;p,g,d,s=complete(f,local=True);before=snapshot(f);good=httpget(page,f,p);assert good.ok and good.json()['state']=='LOCAL_OUTPUTS_VERIFIED' and snapshot(f)==before
 with f[1].connect() as c:
  if damage=='review-payload-typed-revision':c.execute("UPDATE preparation_events SET payload=jsonb_set(payload,'{revision}','true'::jsonb) WHERE preparation_id=%s AND action='REVIEW'",(p['preparation_id'],))
  elif damage=='confirm-case':c.execute("UPDATE preparation_events SET payload=jsonb_set(payload,'{case_id}',to_jsonb(%s::text)) WHERE preparation_id=%s AND action='CONFIRM'",('00000000-0000-0000-0000-000000000000',p['preparation_id']))
  elif damage=='missing-local-event':c.execute("DELETE FROM case_local_events WHERE preparation_id=%s AND action='REVALIDATE'",(p['preparation_id'],))
  elif damage=='receipt-first-version-gap':c.execute("DELETE FROM service_step_receipts WHERE step_id=%s AND version=1",(s['step']['id'],))
  elif damage=='accept-payload-executor':c.execute("UPDATE service_dispatch_events SET payload=jsonb_set(payload,'{executor_id}',to_jsonb(%s::text)) WHERE dispatch_id=%s AND action='ACCEPT'",('executor-b',d['dispatch_id']))
  else:
   f[1].lock_principal(c,'prep-specialist-fixture-a',exclusive=True)
   c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a' AND capability='REVIEW_ASSIGNED'")
 before=snapshot(f);r=httpget(page,f,p);assert r.ok;result=r.json();assert result['state']=='UNVERIFIED' and snapshot(f)==before
 assert result['results'][-1]['actual_output'] is None and result['results'][-1]['state']!='LOCAL_OUTPUT_VERIFIED'
 assert 'PRIVATE_GOAL_RECEIPT' not in json.dumps(result) and not result['case_goal_completed']

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_real_http_no_other_role_or_tenant_business_visibility(goal_page,user):
 f,page,_=goal_page;p,g,d,s=complete(f);before=snapshot(f);r=httpget(page,f,p,user);assert r.status==403 and snapshot(f)==before
 assert all(v not in r.text() for v in (p['case_id'],g['id'],s['current_receipt']['id'],'PRIVATE_GOAL_RECEIPT'))

def test_real_http_material_replacement_and_request_rebind_history(goal_page):
 f,page,_=goal_page;p=start(f);verified(f,p,'P1');old=httpget(page,f,p).json();proof=old['results'][0]['historical_verification']['id']
 current=prep_read(f,p).json()['preparation'];current={**current,'preparation_id':p['preparation_id']};p=prep_act(f,current,'REOPEN',reason='SYNTHETIC independent replaced material').json();p=add(f,p,text='SYNTHETIC independent new material').json()
 before=snapshot(f);changed=httpget(page,f,p).json();assert changed['state']=='UNVERIFIED' and changed['results'][0]['historical_verification']['id']==proof and changed['results'][0]['actual_output'] is None and snapshot(f)==before
 p=save(f,p,text='SYNTHETIC explicit independent request revision',goals=[GOALS[0],'SYNTHETIC unsupported original retained']).json();before=snapshot(f);x=httpget(page,f,p).json();assert x['adopted_goals']==[GOALS[0]] and [r['state'] for r in x['results']]==['NEEDS_NEW_PLAN','UNSUPPORTED'] and snapshot(f)==before


def test_real_http_last_source_lock_expiry_never_reuses_early_clock(goal_page):
 f,page,_=goal_page;p,g,d,s=complete(f,local=True)
 with f[1].connect() as c:c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '1 minute',ends_at=clock_timestamp()+interval '2 seconds' WHERE id IN (SELECT hold_id FROM synthetic_resource_combination_members WHERE combination_id=%s)",(g['id'],))
 for a in ('P2','P3','P4'):verified(f,p,a)
 assert local_act(f,p,local_read(f,p).json(),'REVALIDATE').status_code==200;verified(f,p,'P5');assert httpget(page,f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED';before=snapshot(f)
 endpoint=page.url.rstrip('/')+'/api/preparations/'+p['preparation_id']+'/goal-results'
 with httpx.Client(timeout=6) as http, f[1].connect() as block,ThreadPoolExecutor(1) as pool:
  block.execute('SELECT preparation_id FROM case_local_lifecycles WHERE preparation_id=%s FOR UPDATE',(p['preparation_id'],));pending=pool.submit(http.get,endpoint,headers=headers(f[2]));deadline=time.monotonic()+1.2;waiting=False
  while time.monotonic()<deadline:
   block.execute('SELECT pg_stat_clear_snapshot()');waiting=block.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query ILIKE '%%FROM case_local_lifecycles%%') AS waiting").fetchone()['waiting']
   if waiting:break
   time.sleep(.01)
  assert waiting,'real HTTP GET never reached held last source row'
  block.execute("SELECT pg_sleep(greatest(0,extract(epoch from(max(ends_at)-clock_timestamp())))+.03) FROM synthetic_resource_holds WHERE id IN (SELECT hold_id FROM synthetic_resource_combination_members WHERE combination_id=%s)",(g['id'],));block.commit();r=pending.result(5)
 assert r.status_code==200;result=r.json();assert result['state']=='UNVERIFIED' and result['results'][1]['actual_output'] is None and 'RESOURCE_WINDOW_ENDED' in result['results'][1]['issues'] and snapshot(f)==before
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'real-http-last-lock-expiry.json').write_text(json.dumps(dict(real_http=True,actual_pg_last_source_row_lock=True,pg_stat_snapshot_explicitly_refreshed=True,actual_database_clock_expiry=True,output_suppressed=True,business_snapshot_unchanged=True),indent=2)+'\n')

@pytest.mark.parametrize('denied',[False,True])
def test_real_http_late_prior_case_result_preserves_new_case_and_draft(goal_page,denied):
 f,page,_=goal_page;p=start(f);verified(f,p,'P1');open_case(page,f,p);held=[]
 def delay(route):held.append((route,route.fetch()))
 page.route('**/api/preparations/'+p['preparation_id']+'/goal-results',delay);page.locator('#goal-results-read').click();wait_held(page,held)
 newer=start(f);open_case(page,f,newer);page.locator('#service-plan-reason').fill('SYNTHETIC independent new Case draft');page.locator('#goal-results-status').evaluate('(e)=>e.textContent="SYNTHETIC independent new view"');before=snapshot(f)
 if denied:held[0][0].fulfill(status=403,json={'detail':'SYNTHETIC old denial'})
 else:held[0][0].fulfill(response=held[0][1])
 page.wait_for_timeout(150);assert page.evaluate('goalResultView') is None and page.locator('#goal-results-status').inner_text()=='SYNTHETIC independent new view' and page.locator('#service-plan-reason').input_value()=='SYNTHETIC independent new Case draft' and snapshot(f)==before
 OUT.mkdir(parents=True,exist_ok=True);page.set_viewport_size({'width':320,'height':1000});page.locator('#goal-results-panel').scroll_into_view_if_needed();page.screenshot(path=str(OUT/('late-'+str(denied)+'.png')))

def test_current_actual_403_clears_private_views_despite_committed_lost_objection(goal_page):
 f,page,errors=goal_page;p=start(f);verified(f,p,'P1');open_case(page,f,p);read_page(page)
 page.evaluate("async()=>{await servicePlanOpen('materials')}");page.wait_for_function('()=>objectionView!==null&&preparationView!==null');assert page.locator('#goal-results-panel').is_visible()
 def lose(route):
  response=route.fetch();assert response.status==200;route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/material-objections',lambda r:lose(r) if r.request.method=='POST' else r.continue_())
 held=[];page.route('**/api/preparations/'+p['preparation_id']+'/goal-results',lambda route:held.append(route));page.locator('#goal-results-read').click();wait_held(page,held)
 page.locator('#objection-reason').fill('SYNTHETIC PRIVATE_REVIEW_OBJECTION_UNCERTAIN');page.locator('#objection-raise').click();page.wait_for_function('()=>objectionPending&&!objectionBusy')
 stored=page.evaluate('JSON.stringify({...localStorage})');assert 'PRIVATE_REVIEW_OBJECTION' not in stored and f[2]['fixture-a'] not in stored
 with f[1].connect() as c:
  f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
 before=snapshot(f);actual=httpget(page,f,p);assert actual.status==403
 response=held[0].fetch();assert response.status==403;held[0].fulfill(response=response);page.wait_for_timeout(300)
 observed=page.evaluate("()=>({goal_view_present:goalResultView!==null,plan_view_present:servicePlanView!==null,preparation_view_present:preparationView!==null,objection_view_present:objectionView!==null,pending_present:objectionPending!==null,private_draft_present:document.getElementById('objection-reason').value.includes('PRIVATE_REVIEW_OBJECTION'),prep_hidden:document.getElementById('prep-detail').hidden,result_hidden:document.getElementById('goal-results-panel').hidden,feedback:document.getElementById('page-feedback').textContent})")
 observed.update(actual_http_status=actual.status,opaque_handle_preserved=page.evaluate('JSON.stringify({...localStorage})')==stored,page_errors=list(errors),business_snapshot_unchanged=snapshot(f)==before,exact_sha='984cbe95acdc51f42e4b67d9a6c06c780c44350b')
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'current-403-pending-objection-observation.json').write_text(json.dumps(observed,ensure_ascii=False,indent=2)+'\n');page.screenshot(path=str(OUT/'current-403-pending-objection.png'))
 assert observed['business_snapshot_unchanged'] and observed['opaque_handle_preserved']
 assert observed['prep_hidden'] and observed['result_hidden'] and not observed['preparation_view_present'] and not observed['objection_view_present'] and not observed['private_draft_present'] and not errors

@pytest.mark.parametrize('kind',['material','objection'])
@pytest.mark.parametrize('status',[200,403])
def test_independent_interleaving_keeps_exact_opaque_handle_and_get_recovery(goal_page,kind,status):
 f,page,errors=goal_page;p=start(f);verified(f,p,'P1');open_case(page,f,p);page.evaluate("async()=>{await servicePlanOpen('materials')}");page.wait_for_function('()=>objectionView!==null&&preparationView!==null');held=[];committed=[]
 def pause(route):held.append((route,route.fetch() if status==200 else None))
 page.route('**/api/preparations/'+p['preparation_id']+'/goal-results',pause);page.locator('#goal-results-read').click();wait_held(page,held)
 def lose(route):
  if route.request.method!='POST':route.continue_();return
  response=route.fetch();assert response.status==200;committed.append(response.json());route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+('/commands' if kind=='material' else '/material-objections'),lose)
 marker='SYNTHETIC PRIVATE_INDEPENDENT_'+kind
 if kind=='material':
  page.locator('#prep-slot').select_option('need_summary');page.locator('#prep-text').fill(marker);page.locator('#prep-source-label').fill('SYNTHETIC independent latest source');page.locator('#prep-evidence button').click();page.wait_for_function('()=>prepCommandPending?.state==="UNKNOWN"')
 else:
  page.locator('#objection-reason').fill(marker);page.locator('#objection-raise').click();page.wait_for_function('()=>objectionPending!==null&&!objectionBusy')
 assert len(committed)==1;stored=page.evaluate('JSON.stringify({...localStorage})');handles=json.loads(stored);assert len(handles)==1 and marker not in stored and f[2]['fixture-a'] not in stored
 handle=json.loads(next(iter(handles.values())))
 if status==403:
  with f[1].connect() as c:
   f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
 before=snapshot(f);route,response=held[0]
 if status==403:response=route.fetch()
 assert response.status==status
 if status==200:assert response.json()['state']=='LOCAL_OUTPUTS_VERIFIED'
 route.fulfill(response=response);page.wait_for_timeout(200)
 assert snapshot(f)==before and not errors and page.evaluate('goalResultView') is None and page.evaluate('JSON.stringify({...localStorage})')==stored
 if status==403:
  assert page.evaluate('preparationView===null&&objectionView===null&&prepCommandPending===null&&objectionPending===null&&servicePlanView===null') and page.locator('#prep-detail').is_hidden() and page.locator('#goal-results-panel').is_hidden()
  assert page.locator('#prep-text').input_value()=='' and page.locator('#objection-reason').input_value()==''
  with f[1].connect() as c:
   f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE capability_grants SET active=true,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
 else:
  assert page.locator('#goal-results-items').inner_text()=='' and '保持未核验' in page.locator('#goal-results-error').inner_text()
  if kind=='material':assert page.evaluate('prepCommandPending?.state==="UNKNOWN"') and page.locator('#prep-text').input_value()==marker
  else:assert page.evaluate('objectionPending!==null') and page.locator('#objection-reason').input_value()==marker
 before=snapshot(f);url=page.url.rstrip('/')+'/api/preparations/'+p['preparation_id']
 r=page.request.get(url+('/command-recovery' if kind=='material' else '/material-objections/recovery/'+handle['key']),headers=headers(f[2],key=handle['key'] if kind=='material' else None));assert r.status==200;v=r.json();assert v['status']=='COMMITTED' and v['historical_only'] and not v['automatically_replayed'];assert snapshot(f)==before
 if kind=='material':assert v['event']['revision']==committed[0]['revision'] and v['event']['action']=='ADD_EVIDENCE'
 else:assert v['event']['objection']['id']==committed[0]['objection']['id']
 OUT.mkdir(parents=True,exist_ok=True);(OUT/f'interleaved-{kind}-{status}.json').write_text(json.dumps(dict(real_http=True,real_original_write_committed_once=True,response_lost=True,read_status=status,old_200_was_verified=status==200,never_displayed_verified=True,exact_opaque_handle_unchanged=True,no_unhandled_pageerror=True,read_only_historical_recovery_committed=True,business_snapshot_unchanged=True,exact_sha='984cbe95acdc51f42e4b67d9a6c06c780c44350b'),indent=2)+'\n')


def test_material_opaque_handle_cold_page_still_recovers_original_committed_key(goal_page):
 f,page,errors=goal_page;p=start(f);open_case(page,f,p);page.evaluate("async()=>{await servicePlanOpen('materials')}");page.wait_for_function('()=>preparationView!==null')
 def lose(route):
  if route.request.method!='POST':route.continue_();return
  response=route.fetch();assert response.status==200;route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/commands',lose);page.locator('#prep-slot').select_option('material_outline');page.locator('#prep-text').fill('SYNTHETIC PRIVATE_COLD_RECOVERY');page.locator('#prep-source-label').fill('SYNTHETIC independent cold version');page.locator('#prep-evidence button').click();page.wait_for_function('()=>prepCommandPending?.state==="UNKNOWN"')
 stored=page.evaluate('JSON.stringify({...localStorage})');assert stored!='{}';key=json.loads(next(iter(json.loads(stored).values())))['key'];before=snapshot(f);methods=[];page.on('request',lambda r:methods.append(r.method));page.reload();page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('input');page.evaluate("async id=>{await loadPreparation(id,{role:'enterprise_operator'})}",p['preparation_id']);page.wait_for_function('()=>preparationView!==null')
 observed=dict(original_handle_retained=page.evaluate('JSON.stringify({...localStorage})')==stored,recovery_handle_present=page.evaluate('prepRecoveryHandle!==null'),current_material_version=page.evaluate("preparationView.current_materials.find(m=>m.slot==='material_outline').version"),read_only_requests=bool(methods) and set(methods)=={'GET'},business_snapshot_unchanged=snapshot(f)==before,page_errors=list(errors),exact_sha='984cbe95acdc51f42e4b67d9a6c06c780c44350b')
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'cold-material-handle-observation.json').write_text(json.dumps(observed,indent=2)+'\n')
 assert observed['read_only_requests'] and observed['business_snapshot_unchanged'] and not errors
 assert observed['original_handle_retained'] and observed['recovery_handle_present']


def lost_material(page,f,p):
 open_case(page,f,p);page.evaluate("async()=>{await servicePlanOpen('materials')}");page.wait_for_function('()=>preparationView!==null')
 def lose(route):
  if route.request.method!='POST':route.continue_();return
  response=route.fetch();assert response.status==200;route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/commands',lose);page.locator('#prep-slot').select_option('material_outline');page.locator('#prep-text').fill('SYNTHETIC PRIVATE_FINAL_RECOVERY_BODY');page.locator('#prep-source-label').fill('SYNTHETIC final actual source');page.locator('#prep-evidence button').click();page.wait_for_function('()=>prepCommandPending?.state==="UNKNOWN"')
 raw=page.evaluate('JSON.stringify({...localStorage})');assert 'PRIVATE_FINAL_RECOVERY_BODY' not in raw and f[2]['fixture-a'] not in raw;storage=json.loads(raw);name=next(iter(storage));handle=json.loads(storage[name]);assert set(handle)=={'v','id','key','revision','expires'}
 return raw,name,handle


def test_actual_saved_handle_retry_preserves_deadline_and_expiry_has_no_authority(goal_page):
 f,page,errors=goal_page;p=start(f);raw,name,handle=lost_material(page,f,p);before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.wait_for_timeout(25)
 page.evaluate('()=>rememberPrepRecovery(prepCommandPending)');assert page.evaluate('JSON.stringify({...localStorage})')==raw and snapshot(f)==before and requests==[]
 observed=page.evaluate('''()=>{let blocked=false;try{rememberPrepRecovery({...prepCommandPending,body:{...prepCommandPending.body,expected_revision:prepCommandPending.body.expected_revision+1}})}catch(e){blocked=true}return blocked}''');assert observed and page.evaluate('JSON.stringify({...localStorage})')==raw
 page.evaluate('({name,handle})=>{localStorage.setItem(name,JSON.stringify({...handle,expires:Date.now()-1}));}',dict(name=name,handle=handle));assert page.evaluate('(id)=>readPrepRecovery(id)',p['preparation_id']) is None;assert page.evaluate('(name)=>localStorage.getItem(name)',name) is None
 before=snapshot(f);endpoint=page.url.rstrip('/')+'/api/preparations/'+p['preparation_id']+'/command-recovery';r=page.request.get(endpoint,headers=headers(f[2],key=handle['key']));assert r.status==200 and r.json()['status']=='COMMITTED' and r.json()['historical_only'] and not r.json()['automatically_replayed'] and snapshot(f)==before
 denied=page.request.get(endpoint,headers=headers(f[2],'fixture-b',handle['key']));assert denied.status==403 and 'PRIVATE_FINAL_RECOVERY_BODY' not in denied.text() and snapshot(f)==before
 # APIRequestContext traffic does not emit Page request events; independently
 # exercise the same actual read through browser fetch before asserting events.
 browser_read=page.evaluate('''async ({url,key})=>{const r=await fetch(url,{headers:{Authorization:'Bearer '+document.getElementById('token').value,'Idempotency-Key':key}});const x=await r.json();return {status:r.status,committed:x.status==='COMMITTED',historical:x.historical_only,noReplay:x.automatically_replayed===false}}''',dict(url=endpoint,key=handle['key']))
 assert browser_read==dict(status=200,committed=True,historical=True,noReplay=True) and requests and set(requests)=={'GET'} and snapshot(f)==before and not errors
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'actual-retry-expiry-no-authority.json').write_text(json.dumps(dict(actual_committed_original_write=True,same_key_revision_storage_bytes_unchanged=True,original_deadline_not_extended=True,wrong_revision_rejected=True,expired_client_handle_rejected=True,opaque_key_not_authority=True,original_owner_historical_get_committed=True,no_replay=True,read_only_snapshot_unchanged=True,exact_sha='984cbe95acdc51f42e4b67d9a6c06c780c44350b'),indent=2)+'\n')

@pytest.mark.parametrize('scope',['fixture-b','fixture-c','prep-specialist-fixture-a','revoked-read','other-owner-case'])
def test_actual_cold_saved_key_cannot_expand_recovery_scope(goal_page,scope):
 f,page,errors=goal_page;p=start(f);raw,name,handle=lost_material(page,f,p);page.reload();assert page.locator('#token').input_value()=='' and page.evaluate('prepCommandPending===null&&preparationView===null')
 other=None
 if scope=='other-owner-case':other=start(f)
 if scope=='revoked-read':
  with f[1].connect() as c:
   f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
 user=scope if scope in f[2] else 'fixture-a';page.locator('#token').fill(f[2][user]);page.locator('#token').dispatch_event('input');before=snapshot(f);target=other or p
 r=page.request.get(page.url.rstrip('/')+'/api/preparations/'+target['preparation_id']+'/command-recovery',headers=headers(f[2],user,handle['key']));assert r.status==(409 if other else 403);assert 'PRIVATE_FINAL_RECOVERY_BODY' not in r.text() and 'event' not in r.json();assert snapshot(f)==before and page.evaluate('JSON.stringify({...localStorage})')==raw and not errors
