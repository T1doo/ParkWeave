import json
from uuid import uuid4
import pytest
from conftest import pg,fixture
from test_service_plan_recovery_browser import goal_page, link_fixture, receipt_fixture, preparation_fixture, prep, open_case, lost, wait_recovered, open_again, recover, snapshot, setup, adopt, adopt_body, read, command, save, GOALS
from test_preparation import headers

@pytest.mark.parametrize('hot_path',['button','programmatic_write_guard'])
def test_hot_expired_handle_must_not_use_original_key(goal_page,hot_path):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p);h,stored,_=lost(page,f,p,'BEGIN');before=snapshot(f);requests=[];page.on('request',lambda r:requests.append((r.method,r.headers.get('idempotency-key'))));page.evaluate('(expires)=>{Date.now=()=>expires+1}',h['expires'])
 if hot_path=='button':page.locator('#service-plan-retry').click()
 else:page.evaluate('()=>servicePlanWrite("BEGIN").catch(servicePlanError)')
 page.wait_for_timeout(250);observation=dict(original_key_gets=sum(m=='GET' and k==h['key'] for m,k in requests),posts=sum(m=='POST' for m,k in requests),observed=bool(page.evaluate('servicePlanRecoveryHandle?.observed')),storage_retained=page.evaluate('JSON.stringify({...localStorage})')==stored,business_unchanged=snapshot(f)==before,handle_expired=True,page_errors=len(errors))
 from pathlib import Path
 out=Path('/workspace/ParkWeave/.runtime/independent-service-plan-cold-recovery-final-review');(out/('hot-expiry-'+hot_path+'.json')).write_text(json.dumps(observation,indent=2)+'\n');assert observation['business_unchanged'] and observation['posts']==0 and not errors
 assert observation['original_key_gets']==0, 'Expired hot handle was still used for original-key recovery GET'

def test_original_delayed_request_can_commit_after_not_observed_without_ui_replay(goal_page):
 f,page,errors=goal_page;p=prep(f,'ADOPT');open_case(page,f,p);captured=[];path='/api/preparations/'+p['preparation_id']+'/service-case-plan'
 def delay(route):
  if route.request.method!='POST':route.continue_();return
  captured.append(dict(key=route.request.headers['idempotency-key'],body=route.request.post_data_json));route.abort('failed')
 page.route('**'+path,delay);page.locator('#service-plan-reason').fill('SYNTHETIC INDEPENDENT_PRIVATE_DELAYED');page.locator('#service-plan-adopt').click();page.wait_for_function('()=>servicePlanPending?.stage==="UNCERTAIN"');stored=page.evaluate('JSON.stringify({...localStorage})');before=snapshot(f);page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));open_again(page,f,p);assert '未观察到' in page.locator('#service-plan-feedback').inner_text() and set(requests)=={'GET'} and snapshot(f)==before
 original=captured[0];r=page.request.post(page.url.rstrip('/')+path,headers=headers(f[2],key=original['key']),data=original['body']);assert r.status==201;after=snapshot(f);requests.clear();page.locator('#service-plan-retry').click();wait_recovered(page);assert set(requests)=={'GET'} and page.evaluate('servicePlanView.events.at(-1).id')==r.json()['command_receipt']['id'] and page.evaluate('JSON.stringify({...localStorage})')==stored and snapshot(f)==after and not errors

def test_revoked_cold_unknown_and_delayed_original_cannot_commit(goal_page):
 f,page,errors=goal_page;p=prep(f,'ADOPT');open_case(page,f,p);captured=[];path='/api/preparations/'+p['preparation_id']+'/service-case-plan'
 def delay(route):
  if route.request.method!='POST':route.continue_();return
  captured.append(dict(key=route.request.headers['idempotency-key'],body=route.request.post_data_json));route.abort('failed')
 page.route('**'+path,delay);page.locator('#service-plan-reason').fill('SYNTHETIC INDEPENDENT_PRIVATE_REVOKED');page.locator('#service-plan-adopt').click();page.wait_for_function('()=>servicePlanPending?.stage==="UNCERTAIN"');stored=page.evaluate('JSON.stringify({...localStorage})')
 with f[1].connect() as c:f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
 before=snapshot(f);page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('input');page.evaluate('(id)=>loadServiceCasePlan(id).catch(servicePlanError)',p['preparation_id']);page.wait_for_function('()=>servicePlanView===null&&document.getElementById("page-feedback").textContent.includes("访问权已失效")');assert set(requests)=={'GET'} and page.locator('#service-plan-reason').input_value()=='' and page.evaluate('JSON.stringify({...localStorage})')==stored and snapshot(f)==before
 original=captured[0];r=page.request.post(page.url.rstrip('/')+path,headers=headers(f[2],key=original['key']),data=original['body']);assert r.status==403 and snapshot(f)==before and not errors

def test_second_adopt_historical_receipt_binds_previous_generation(link_fixture):
 f=link_fixture;p=setup(f,GOALS[0]);first=adopt(f,p).json();key=str(uuid4());assert save(f,p,goals=[GOALS[0],GOALS[1]]).status_code==200;body=adopt_body(f,{**p,'revision':read(f,p).json()['preparation_revision']});body['expected_plan_revision']=first['revision'];second=adopt(f,p,body,key).json();assert save(f,{**p,'revision':read(f,p).json()['preparation_revision']},goals=[GOALS[0],GOALS[1],GOALS[2]]).status_code==200;body=adopt_body(f,{**p,'revision':read(f,p).json()['preparation_revision']});body['expected_plan_revision']=second['revision'];third=adopt(f,p,body);assert third.status_code==201;before=snapshot(f);x=recover(f,p,key).json();assert x['status']=='COMMITTED' and x['event']['plan_id']==second['plan_id'] and x['event']['previous_plan_id']==first['plan_id'] and x['event']['expected_revision']==first['revision'] and not x['event']['current_plan'] and x['current']['plan_id']==third.json()['plan_id'] and snapshot(f)==before

@pytest.mark.parametrize('key',['','a'*101,'contains space','x.y'])
def test_invalid_recovery_header_denied_without_business_observation(link_fixture,key):
 f=link_fixture;p=setup(f,GOALS[0]);assert adopt(f,p).status_code==201;before=snapshot(f)
 if key=='中文':
  from parkweave import service_case_steps as plans
  # HTTP transports reject non-ASCII header before API; API route validator is checked for ASCII shapes.
  pytest.skip('HTTP client refuses non-ASCII headers before request dispatch')
 r=f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan/command-recovery',headers={**headers(f[2]),'Idempotency-Key':key});assert r.status_code==422 and snapshot(f)==before
