"""Original entire HTML/nativefetch to actual local HTTP ASGI and owned PostgreSQL.

Python prepares a birth-tracked V4 predecessor with only P1/P2 verified. Page performs precise new Approval, resource
transaction, P2-P5 VERIFY and original goal/worklist reads. No browser claim.
"""
from copy import deepcopy
import json,hashlib,os,queue,subprocess,threading
from pathlib import Path
from uuid import uuid4
import pytest
from parkweave.api import create_app
from parkweave import case_resource_delivery
from test_new_enterprise_local_chain import actual_http
from frontier_fixture_support import frontier_case,capability_resource_catalog,capability_catalog,preparation_fixture,receipt_fixture
from test_service_case_steps import verified
from test_service_plan_manual_lock import stored
from test_resource_bundles import bundle,states
from test_case_resource_delivery import effects,recover
from test_service_plan_approval import enable,ledger
from test_case_lifecycle import read as localread,act as localact
from test_case_cancellation import snapshot
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.runtime/frontier-real-html'

@pytest.fixture(autouse=True)
def route_helper_artifacts(request,monkeypatch):
 import sys
 destination=request.module.OUT
 for name,module in list(sys.modules.items()):
  if name.startswith('test_') and module is not request.module:
   v=getattr(module,'OUT',None)
   if isinstance(v,Path) and (str(v).startswith('.runtime/') or '.runtime' in v.parts):monkeypatch.setattr(module,'OUT',destination/'helpers'/name)

@pytest.mark.parametrize('mode',['positive','lost_ack','current_403','late_403'])
def test_original_entire_html_frontier_approval_and_recovery(frontier_case,tmp_path,mode):
 t=frontier_case;f,p=t['f'],t['p'];assert next(s for s in t['new']['steps'] if s['adapter_id']=='P1')['coordination_state']=='VERIFIED';hs,data=bundle(f)
 B=None
 if mode=='late_403':
  from test_executor_receipts import ready
  B=ready(f)
  # Original exact allowlist construction, without inventing authorization.
  from parkweave.service_plan_approval import IsolatedPlanApproval
  t['bridge']=IsolatedPlanApproval(f[1],f[1]._case_fact_fixture_receipt,preparation_ids=[p['preparation_id'],B['preparation_id']],enabled_for_isolated_tests=True,enabled_for_source_reapproval_tests=True,enabled_for_plan_replacement_tests=True,plan_replacement_preflight=t['checker'],enabled_for_known_not_started_tests=True,known_not_started_frontier=t['protocol']);t['bridge'].attach_store(f[0])
 assert Path(case_resource_delivery.__file__).resolve().is_relative_to((ROOT/'src').resolve())
 OUT.mkdir(parents=True,exist_ok=True);attempt=mode+'-'+uuid4().hex[:10];lines=[];state={};result=None;err='';process=None
 def before():state.update(plan=deepcopy(stored(f,p)),ledger=deepcopy(ledger(f,p)),old=snapshot(f))
 def after():
  assert effects(f)==[2,6,2,2,2] and states(f,hs)==['CONFIRMED']*3
  assert stored(f,p)==state['plan'],'resource commit never auto-verifies plan'
  assert ledger(f,p)['events'][:-1]==state['ledger']['events']
  with f[1].connect() as c:rows=c.execute('SELECT * FROM case_resource_links ORDER BY revision').fetchall()
  assert len(rows)==2 and str(rows[0]['id'])==t['oldreceipt']['link']['id'] and rows[0]['snapshot']==t['oldreceipt']['link']['snapshot']
 def dispatch():
  from test_service_dispatches import offer,command as dispatch_command
  from test_preparation import headers
  q=f[3].get('/api/service-dispatches/catalog?preparation_id='+p['preparation_id'],headers=headers(f[2],'prep-specialist-fixture-a'));assert q.status_code==200,q.text
  r=offer(f,p,expected_business_frontier=q.json()['business_frontier'])[0];assert r.status_code==201,r.text
  current=f[3].get('/api/service-dispatches/'+r.json()['dispatch_id'],headers=headers(f[2],'executor-a'));assert current.status_code==200,current.text
  accepted=dispatch_command(f,current.json(),'ACCEPT',expected_business_frontier=current.json()['business_frontier']);assert accepted.status_code==200,accepted.text
  state['dispatch']=accepted.json()
 def report():
  from test_executor_receipts import act as receipt
  from test_preparation import headers
  sr=f[3].get('/api/executor-receipts/'+state['dispatch']['receipt_step_id'],headers=headers(f[2],'executor-a'));assert sr.status_code==200,sr.text
  sr=receipt(f,sr.json(),'SUBMIT',expected_business_frontier=sr.json()['business_frontier']);assert sr.status_code==200,sr.text
  sr=f[3].get('/api/executor-receipts/'+state['dispatch']['receipt_step_id'],headers=headers(f[2]));assert sr.status_code==200,sr.text
  sr=receipt(f,sr.json(),'ACKNOWLEDGE',expected_business_frontier=sr.json()['business_frontier']);assert sr.status_code==200,sr.text
 def local():
  current=localread(f,p);assert current.status_code==200,current.text
  r=localact(f,p,current.json(),'REVALIDATE',expected_business_frontier=current.json()['business_frontier']);assert r.status_code==200,r.text
 def final():
  assert len(stored(f,p)['required_goals'])==6
  old=recover(f,p,t['oldreceipt']['delivery_binding']['request_key']);assert old.status_code==200,old.text
  assert old.json()['receipt']==t['oldreceipt']['receipt'] and old.json()['independent_check']['status']=='NEEDS_RECHECK'
 def revoke():
  with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
  state['denied']=snapshot(f)
 def denied():assert snapshot(f)==state['denied']
 def restore():
  denied()
  with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=true,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
 controls=dict(before_commit=before,after_commit=after,reoffer_accept=dispatch,new_report_ack=report,revalidate_local=local,final_evidence=final,revoke=revoke,assert_denied_read_no_write=denied,restore=restore)
 with actual_http(create_app(f[0])) as (client,requests):
  f=(*f[:3],client);t['f']=f;t['a']['f']=f
  config=dict(base=str(client.base_url).rstrip('/'),token=f[2]['fixture-a'],mode=mode,A=p,holds=[h['id'] for h in hs],old_plan_id=t['old']['id'],new_plan_id=t['new']['id'])
  if B:config['B']=B
  process=subprocess.Popen(['node','tests/frontier_real_html.js'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  incoming=queue.Queue()
  def consume():
   for line in process.stdout:incoming.put(line)
   incoming.put(None)
  reader=threading.Thread(target=consume,daemon=True);reader.start()
  try:
   process.stdin.write(json.dumps(config)+'\n');process.stdin.flush()
   while True:
    try:line=incoming.get(timeout=45)
    except queue.Empty:raise AssertionError('real replacement page no progress for 45 seconds')
    if line is None:break
    lines.append(line);message=json.loads(line)
    if 'trace' in message:continue
    if 'control' in message:
     response=controls[message['control']]();process.stdin.write(json.dumps(response or {})+'\n');process.stdin.flush()
    else:result=message;break
   code=process.wait(timeout=10);err=process.stderr.read();assert code==0,err
   assert result and result['scope']=='FULL_ORIGINAL_HTML_KNOWN_NOT_STARTED_FRONTIER_ACTUAL_HTTP_ASGI_OWNED_PG' and result['fake_dto'] is False
   (OUT/(attempt+'.result.json')).write_text(json.dumps(dict(result,backend_path=str(Path(case_resource_delivery.__file__).resolve()),backend_sha256=hashlib.sha256(Path(case_resource_delivery.__file__).read_bytes()).hexdigest(),python_http_requests=requests),sort_keys=True,indent=2)+'\n')
  finally:
   if process.poll() is None:process.terminate();process.wait(timeout=5)
   reader.join(timeout=5)
   while not incoming.empty():
    line=incoming.get_nowait()
    if line is not None:lines.append(line)
   (OUT/(attempt+'.stdout.jsonl')).write_text(''.join(lines));(OUT/(attempt+'.stderr.log')).write_text(err+process.stderr.read())
