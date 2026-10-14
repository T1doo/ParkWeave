from conftest import pg,fixture
from test_preparation import preparation_fixture,headers,add
from test_service_plan_candidates import setup,GOAL,generate,preview,adoption,adopt,path
from test_plan_preview import digest
from test_request_intents import save
from test_isolated_run_access import permission_snapshot
from parkweave import controlled_plans as cp
from psycopg.types.json import Jsonb
from pathlib import Path
from uuid import uuid4
from copy import deepcopy
import pytest,json,subprocess,selectors


def recover(f,p,key):return f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan/command-recovery',headers=headers(f[2],key=key))

def replace_plain(f,p):
 assert save(f,p,text='SYNTHETIC independent actual revised request',goals=[GOAL,'UNSUPPORTED_NEW_INDEPENDENT']).status_code==200
 x=f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2])).json();d=dict(expected_preparation_revision=x['preparation_revision'],expected_request_revision=x['request_revision'],expected_plan_revision=x['revision'],expected_source_sha256=x['current_preview']['source_sha256'],required_goals=x['current_preview']['required_goals'],reason='SYNTHETIC independent actual plain replacement',partial_adoption=True)
 r=f[3].post('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2],key='ind-plain-replacement'),json=d);assert r.status_code==201,r.text;return r.json()


def test_history_candidate_original_cache_and_get_fail_together_after_proof_corruption(preparation_fixture):
 f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();d=adoption(f,p,v);r=adopt(f,p,v,'ind-original-adopt',d);assert r.status_code==201;rplan=r.json()['plan_id'];replace_plain(f,p);before=digest(f)
 assert recover(f,p,'ind-original-adopt').json()['event']['plan_id']==rplan;assert adopt(f,p,v,'ind-original-adopt',d).status_code==201;assert digest(f)==before
 with f[1].connect() as c:c.execute("UPDATE preparations SET planning_previews='[]'::jsonb WHERE id=%s",(p['preparation_id'],))
 before=digest(f);assert recover(f,p,'ind-original-adopt').status_code==409;assert adopt(f,p,v,'ind-original-adopt',d).status_code==409;assert digest(f)==before


def test_double_delete_cannot_turn_consumed_candidate_into_ordinary_legacy_plan(preparation_fixture):
 f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();d=adoption(f,p,v);assert adopt(f,p,v,'ind-double-proof',d).status_code==201
 with f[1].connect() as c:c.execute("UPDATE preparations SET service_case_plan=service_case_plan-'candidate_consumption'-'adoption_request' WHERE id=%s",(p['preparation_id'],))
 before=digest(f);assert f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2])).status_code==409;assert recover(f,p,'ind-double-proof').status_code==409;assert adopt(f,p,v,'ind-double-proof',d).status_code==409;assert digest(f)==before

@pytest.mark.parametrize('bad',['boolean_version','extra_action','omitted_goal'])
def test_untrusted_original_snapshot_and_recomputed_hash_do_not_override_current_compiler(preparation_fixture,bad):
 from parkweave.service_plan_candidates import document
 f=preparation_fixture;p=setup(f,[GOAL,'UNSUPPORTED_PRIVATE_TARGET']);v=generate(f,p).json()
 with f[1].connect() as c:
  h=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews'];doc=h[0]['document']
  if bad=='boolean_version':doc['steps'][0]['adapter_revision']=True
  elif bad=='extra_action':doc['steps'][0]['actions'].append({'method':'POST','path':'/api/unauthorized','role':'enterprise_operator','commands':['NEW_AUTHORITY']})
  else:doc['required_goals'].pop();doc['goal_coverage'].pop()
  h[0]['candidate']=document(doc);h[0]['candidate_sha256']=cp._hash(h[0]['candidate']);c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(h),p['preparation_id']))
 before=digest(f);r=preview(f,p,v['candidate_id']);assert r.status_code==200,r.text;assert r.json()['state']=='REJECTED' and not r.json()['can_adopt'] and not r.json()['can_adopt_partial'];assert adopt(f,p,r.json()).status_code==409;assert digest(f)==before


def test_original_generate_key_and_adopt_key_are_readonly_history_after_actual_material_add(preparation_fixture):
 f=preparation_fixture;p=setup(f,[GOAL]);source=f[3].get('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2])).json()['current'];gbody={'expected_preparation_revision':source['preparation_revision'],'expected_source_sha256':source['source_sha256']};v=generate(f,p,'ind-generate',gbody).json();d=adoption(f,p,v);first=adopt(f,p,v,'ind-adopt',d);assert first.status_code==201;add(f,p);before=digest(f)
 r=f[3].get(path(p)+'/recovery',headers=headers(f[2],key='ind-generate'));assert r.status_code==200 and r.json()['status']=='COMMITTED' and r.json()['items'][0]['state']=='STALE'
 assert recover(f,p,'ind-adopt').json()['status']=='COMMITTED';assert adopt(f,p,v,'ind-adopt',d).status_code==201;assert adopt(f,p,v,'ind-adopt',{**d,'reason':'SYNTHETIC different'}).status_code==409;assert digest(f)==before


def test_current_authority_denies_id_preview_original_recovery_and_cached_adoption(preparation_fixture):
 f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p,'ind-grant-generate').json();d=adoption(f,p,v);assert adopt(f,p,v,'ind-grant-adopt',d).status_code==201
 with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
 before=digest(f);assert preview(f,p,v['candidate_id']).status_code==403;assert f[3].get(path(p)+'/recovery',headers=headers(f[2],key='ind-grant-generate')).status_code==403;assert adopt(f,p,v,'ind-grant-adopt',d).status_code==403;assert digest(f)==before


def test_real_legacy_adoption_without_extensions_keeps_original_receipt_after_new_candidate_metadata(preparation_fixture):
 f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();d=adoption(f,p,v)
 for k in ('candidate_id','expected_candidate_sha256','expected_verification_sha256'):d.pop(k)
 assert adopt(f,p,v,'ind-original-legacy',d).status_code==201;before=digest(f);assert recover(f,p,'ind-original-legacy').json()['status']=='COMMITTED';assert adopt(f,p,v,'ind-original-legacy',d).status_code==201;assert digest(f)==before


def test_actual_owned_pg_parent_wait_material_implementation_wins_candidate_adoption(preparation_fixture):
 import time
 from concurrent.futures import ThreadPoolExecutor
 from parkweave.preparation import _insert_evidence
 f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();d=adoption(f,p,v);observed=False
 with ThreadPoolExecutor(1) as pool:
  with f[1].connect() as holder:
   parent=holder.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],)).fetchone();pid=holder.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'];future=pool.submit(adopt,f,p,v,'ind-pg-adopt',d);end=time.monotonic()+2
   with f[1].connect() as monitor:
    while time.monotonic()<end:
     monitor.execute('SELECT pg_stat_clear_snapshot()');observed=monitor.execute('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND %s=ANY(pg_blocking_pids(pid))) AS yes',(pid,)).fetchone()['yes']
     if observed:break
     time.sleep(.01)
   assert observed;actor=holder.execute("SELECT * FROM principals WHERE id='fixture-a'").fetchone();_insert_evidence(holder,actor,parent,'material_outline','SYNTHETIC independent actual material helper mutation','DOCUMENT_EXCERPT','SYNTHETIC changed during owned parent wait')
  result=future.result(timeout=5);assert result.status_code==409,result.text
 r=preview(f,p,v['candidate_id']);assert r.status_code==200 and r.json()['state']=='STALE';assert f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2])).json()['plan_id'] is None
 Path('.runtime/service-plan-candidates-20261014/independent/pg-wait.json').write_text(json.dumps({'actual_pg_parent_blocker_observed':observed,'response':409,'mutation':'original _insert_evidence implementation on held owned connection; not separate ADD_EVIDENCE HTTP','plan_adopted':False})+'\n')

def test_positive_generate_and_adopt_mutate_only_their_original_target_columns(preparation_fixture):
 f=preparation_fixture;p=setup(f,[GOAL])
 def snapshot():
  with f[1].connect() as c:
   tables=[x['tablename'] for x in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename!='authorization_audit' ORDER BY tablename")];return {t:c.execute('SELECT * FROM "'+t+'" ORDER BY 1').fetchall() for t in tables}
 before=snapshot();v=generate(f,p,'ind-positive-generate').json();after=snapshot();expected=deepcopy(before)
 target=next(x for x in expected['preparations'] if str(x['id'])==p['preparation_id']);live=next(x for x in after['preparations'] if str(x['id'])==p['preparation_id']);target['planning_previews']=deepcopy(live['planning_previews']);assert expected==after
 before=after;r=adopt(f,p,v,'ind-positive-adopt');assert r.status_code==201,r.text;after=snapshot();expected=deepcopy(before);target=next(x for x in expected['preparations'] if str(x['id'])==p['preparation_id']);live=next(x for x in after['preparations'] if str(x['id'])==p['preparation_id']);target['service_case_plan']=deepcopy(live['service_case_plan']);assert expected==after
 with f[1].connect() as c:audit=c.execute('SELECT * FROM authorization_audit ORDER BY 1').fetchall()
 Path('.runtime/service-plan-candidates-20261014/independent/positive-full-snapshot.json').write_text(json.dumps({'public_tables_compared':list(after),'table_count':len(after),'generate_only_column':'preparations.planning_previews','adopt_only_column':'preparations.service_case_plan','other_columns_tables_unchanged':True,'authorization_audit_rows':len(audit),'audit_separate':True})+'\n')

@pytest.mark.parametrize('mode',['pending_adopt','cold_generate','cold_adopt','opaque_wrongname','source_change'])
def test_full_original_page_exact_candidate_unknown_recovery_and_stale_source(preparation_fixture,mode):
 f=preparation_fixture;p=setup(f,[GOAL]);permissions=permission_snapshot(f[1]);messages=[];summary=None;dropped=False
 proc=subprocess.Popen(['node','.runtime/service-plan-candidates-20261014/independent/candidate_actual_independent.js',p['preparation_id'],'fixture-a',mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
 try:
  while True:
   assert sel.select(timeout=15),'independent candidate page timeout';line=proc.stdout.readline()
   if not line:break
   msg=json.loads(line)
   if msg.get('change_source'):
    add(f,p);proc.stdin.write(b'{}\n');proc.stdin.flush();continue
   if 'result' in msg:summary=msg;break
   q=msg['request'];o=q['options'];method=o.get('method','GET');body=json.loads(o['body']) if o.get('body') else None;before=digest(f)
   r=f[3].request(method,q['path'],headers=headers(f[2],key=o['headers'].get('Idempotency-Key')),json=body);assert r.status_code in (200,201),r.text
   if method=='GET':assert digest(f)==before
   assert permission_snapshot(f[1])==permissions
   drop=not dropped and method=='POST' and ((mode in ('cold_generate','opaque_wrongname') and q['path'].endswith('/service-plan-candidates')) or (mode=='cold_adopt' and q['path'].endswith('/service-case-plan')));dropped=dropped or drop
   messages.append({'method':method,'path':q['path'],'status':r.status_code,'dropped_reply_after_real_commit':drop,'body':body});proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json(),'lost':drop})+'\n').encode());proc.stdin.flush()
  assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['result']=='PASS';assert sum(m['method']=='POST' and m['path'].endswith('/service-plan-candidates') for m in messages)==1
  assert summary['posts']==(1 if mode in ('opaque_wrongname','source_change') else 2)
  assert dropped==(mode in ('cold_generate','cold_adopt','opaque_wrongname'))
 finally:
  Path('.runtime/service-plan-candidates-20261014/independent/page-'+mode+'-chain.json').write_text(json.dumps({'summary':summary,'requests':messages,'lost_original_reply_after_commit':dropped},indent=2)+'\n');sel.close()
  if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
