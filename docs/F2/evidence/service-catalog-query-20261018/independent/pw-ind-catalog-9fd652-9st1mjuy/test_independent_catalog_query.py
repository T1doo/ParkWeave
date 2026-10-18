"""Independent frozen literal and actual synthetic PG/HTTP counterexamples."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4,UUID
import hashlib,json,os,queue,subprocess,threading
import pytest
from psycopg.types.json import Jsonb
from parkweave import registered_dependencies as deps,typed_source_impact as typed,service_catalog_dependencies as query,preparation as prep
from parkweave.store import Store,Conflict
from parkweave.api import create_app
from test_registered_local_revision import http_f,link_fixture,receipt_fixture,preparation_fixture,patch,patch_body,expected_impact
from test_service_case_steps import setup,GOALS,adopt,verified,command,read,business
from test_service_plan_manual_lock import stored
from test_service_plan_recovery import recover
from test_case_goal_results import complete,get
from test_service_catalog_query_api import add_version,verify_all
from test_typed_dependency_opportunity_preview import database_state
from test_source_change_adoption import changed,preview
from test_preparation import headers
from test_new_enterprise_local_chain import actual_http
OUT=Path(os.environ['PARKWEAVE_INDEPENDENT_REVIEW'])
def emit(name,value): (OUT/(name+'.json')).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
def h(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def collected(rows):
 class C:
  def execute(self,sql,args):
   assert args==('park-a','service-a') and 'ORDER BY version LIMIT 33' in sql
   assert 'SELECT *' not in sql and sql.startswith('SELECT r.park_id,r.service_id,r.version,r.name,r.source,r.namespace,r.qualification,')
   assert "to_jsonb(r)->'candidate_catalog_revisions' AS candidate_catalog_revisions" in sql and "to_jsonb(r)->'candidate_catalog_head' AS candidate_catalog_head" in sql
   return self
  def fetchall(self):return deepcopy(rows)
 return query.collection(C(),{'park_id':'park-a','service_id':'service-a'})
def row(n):return dict(park_id='park-a',service_id='service-a',version=n,name='SYNTHETIC '+str(n),source={'kind':'SYNTHETIC','revision':str(n)},namespace='SYNTHETIC',qualification='NOT_EVALUATED')
def vals(stamp):return dict(resources={'known':True,'count':0,'sha256':'a'*64},existing_access={'known':True,'count':0,'sha256':'b'*64},service_catalog=stamp)

def test_independent_literal_fork_filter_bound_and_frozen_old_graph():
 parent={k:str(uuid4()) for k in ('id','case_id','run_id')};parent.update(owner_id='owner',park_id='park-a',org_id='org-a',service_id='service-a',namespace='SYNTHETIC')
 steps=[dict(id=str(uuid4()),adapter_id=a,depends_on=d) for a,d in [('P1',[]),('P2',['P1']),('P3',['P1']),('P4',['P2','P3']),('P5',[])]]
 plan={'id':str(uuid4()),'steps':steps};a=collected([row(1)]);b=collected([row(1),row(2)])
 literal=[dict(service_id='service-a',version=1,name='SYNTHETIC 1',source_sha256=h(row(1)['source']),publication_head=None)]
 assert a=={'known':True,'count':1,'sha256':h(literal)}
 old=deps.manifest(steps,vals(a));new=deps.manifest(steps,vals(b))
 assert deps.impact_between(steps,old,new)==({'P1','P2','P3','P4'},False)
 assert deps.impact_between(steps,old,old)==(set(),False)
 exactly=collected([row(n) for n in range(1,33)]);assert exactly['known'] and exactly['count']==32
 rows=[row(n) for n in range(1,34)];rows[-1]['namespace']='REAL'
 overflow=collected(rows);assert overflow['known'] is False and overflow['count']==33
 for bad in [dict(known=True,count=33,sha256='a'*64),dict(known=True,count=True,sha256='a'*64),dict(known=True,count=1,sha256='A'*64)]:
  v=deps.manifest(steps,vals(bad))
  with pytest.raises(Conflict):deps.validate(v)
 v1vals=vals(a);v1vals.pop('service_catalog');v1=deps.manifest(steps,v1vals)
 old_deps={'__name__':'parkweave._ind_baseline_deps','__package__':'parkweave'}
 exec(compile((OUT/'baseline-registered_dependencies.py').read_text(),'baseline-registered_dependencies.py','exec'),old_deps)
 assert v1==old_deps['manifest'](steps,v1vals)
 sources={a:{'preparation_revision':1,'preparation_sha256':'a'*64} for a in ['P1','P2','P3','P4']};sources['P5']={'sources':{'preparation_revision':1,'preparation_sha256':'a'*64},'local_lifecycle':None}
 after=deepcopy(sources);after['P2']['resource_collection']={'known':True,'count':2,'sha256':'c'*64}
 frozen={'__name__':'parkweave._ind_baseline_typed','__package__':'parkweave'}
 exec(compile((OUT/'baseline-typed_source_impact.py').read_text(),'baseline-typed_source_impact.py','exec'),frozen)
 assert typed.build_v1(parent,plan,sources,after,v1,v1)==frozen['build_v1'](parent,plan,sources,after,v1,v1)
 emit('independent-literal',dict(affected=['P1','P2','P3','P4'],preserved=['P5'],exact32=exactly,filtered33=overflow,old_v1_manifest_equal=True,old_graph_equal=True))

def test_independent_actual_excluded_rows_overflow_and_bad_head_readonly(http_f):
 f=http_f;p=setup(f,GOALS[0]);assert adopt(f,p).status_code==201;verified(f,p,'P1');old=stored(f,p)
 add_version(f)
 with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}','\"EXCLUDED_TEST_SOURCE\"'::jsonb) WHERE park_id='park-a' AND service_id=%s AND version=2",(prep.SERVICE,))
 before=database_state(f);r=recover(f,p);assert r.status_code==200,r.text
 assert r.json()['current']['state']=='VERIFIED' and stored(f,p)==old and database_state(f)==before
 with f[1].connect() as c:
  for n in range(3,34):c.execute('INSERT INTO preparation_catalog(park_id,service_id,version,name,source,namespace,qualification) SELECT park_id,service_id,%s,name,source,namespace,qualification FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=2',(n,'park-a',prep.SERVICE))
 with f[0].connect() as c:
  parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone();s=query.collection(c,parent)
 assert s['known'] is False and s['count']==33
 before=database_state(f);r=recover(f,p);assert r.status_code==200,r.text
 assert r.json()['current']['change_impact']['unknown_scope']=='THIS_CASE' and not r.json()['current']['can_adopt'] and database_state(f)==before
 with f[1].connect() as c:
  c.execute('DELETE FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version>2',('park-a',prep.SERVICE))
  c.execute("ALTER TABLE preparation_catalog ADD COLUMN IF NOT EXISTS candidate_catalog_head jsonb")
  c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}','\"SYNTHETIC\"'::jsonb),candidate_catalog_head=%s WHERE park_id='park-a' AND service_id=%s AND version=2",(Jsonb({'state':'WITHDRAWN'}),prep.SERVICE))
 before=database_state(f);assert recover(f,p).status_code==409 and database_state(f)==before
 emit('independent-readonly-bound',dict(excluded_row_preserves=True,filtered33_unknown=True,readonly_snapshot_preserved=True,bad_original_head_rejected=True))

def test_independent_v1_unified_history_migrates_without_recompiling_old_bytes(http_f,monkeypatch):
 f=http_f;original=deps.collections
 def legacy(*a):v=original(*a);v.pop('service_catalog');return v
 with monkeypatch.context() as m:
  m.setattr(deps,'collections',legacy);p,*_=complete(f,local=True);card=changed(f,p)
  r=f[3].get('/api/preparations/'+p['preparation_id']+'/opportunities/'+card['id']+'/plan-revision?dependency_scope=BOUNDED_MULTI_SOURCE_V1',headers=headers(f[2]));assert r.status_code==200,r.text
  v=r.json();assert v['can_adopt'];assert adopt(f,p,v['adoption']).status_code==201
  for a in ['P2','P3','P4','P5']:verified(f,p,a)
  old=stored(f,p);event=next(e for e in reversed(old['events']) if e['action']=='ADOPT');saved=deepcopy(event['local_revision']['source_change'])
  assert saved['version']==4 and saved['dependency_propagation']['schema']==2
 before=database_state(f);r=recover(f,p);assert r.status_code==200,r.text
 assert r.json()['current']['change_impact']['unknown_scope']=='THIS_CASE' and database_state(f)==before
 assert patch(f,p).status_code==201;now=stored(f,p);assert now['events'][:-1]==old['events'] and now['id']==old['id'] and [s['id'] for s in now['steps']]==[s['id'] for s in old['steps']]
 assert next(e for e in reversed(now['events'][:-1]) if e['action']=='ADOPT')['local_revision']['source_change']==saved
 verify_all(f,p);assert get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED'
 emit('independent-v1-unified',dict(old_graph_sha=saved['dependency_propagation']['sha256'],old_event_sha=h(old['events']),old_prefix_unchanged=True,explicit_migration=True,all_five_reverified=True))

def test_independent_catalog_aba_opportunity_proof_and_cold_revoked_key(http_f):
 f=http_f;p,*_=complete(f,local=True);add_version(f);card=changed(f,p);v=preview(f,p,card).json();assert v['can_adopt']
 with f[1].connect() as c:old=c.execute('SELECT name FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=2',('park-a',prep.SERVICE)).fetchone()['name']
 with f[1].connect() as c:c.execute('UPDATE preparation_catalog SET name=name||%s WHERE park_id=%s AND service_id=%s AND version=2',(' ABA','park-a',prep.SERVICE))
 with f[1].connect() as c:c.execute('UPDATE preparation_catalog SET name=%s WHERE park_id=%s AND service_id=%s AND version=2',(old,'park-a',prep.SERVICE))
 before=database_state(f);assert adopt(f,p,v['adoption']).status_code==409 and database_state(f)==before
 fresh=preview(f,p,card).json();assert fresh['can_adopt'] and fresh['preview_sha256']!=v['preview_sha256'];key=uuid4().hex;r=adopt(f,p,fresh['adoption'],key);assert r.status_code==201,r.text
 before=database_state(f)
 with actual_http(create_app(Store(f[0].dsn))) as (client,traffic):
  cold=(*f[:3],client);recovered=recover(cold,p,key);assert recovered.status_code==200,recovered.text;assert recovered.json()['status']=='COMMITTED' and recovered.json()['current']['state']!='VERIFIED'
  assert database_state(f)==before and all(t['method']=='GET' for t in traffic)
  for table,cap in [('preparation_grants','PREPARE'),('capability_grants','READ')]:
   with f[1].connect() as c:c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',cap))
   state=database_state(f);assert recover(cold,p,key).status_code==403 and database_state(f)==state
   with f[1].connect() as c:c.execute('UPDATE '+table+' SET active=true WHERE principal_id=%s AND capability=%s',('fixture-a',cap))
  state=database_state(f);assert recover(cold,p,key,'fixture-b').status_code==403 and database_state(f)==state
 emit('independent-catalog-aba',dict(old_preview_rejected=True,fresh_preview_sha=fresh['preview_sha256'],cold_get_only=True,read_prepare_before_exact_key=True,cross_subject_denied=True))

def test_independent_full_html_p1_only_label_original_adopt_verify(http_f):
 f=http_f;p=setup(f,GOALS[0]);assert adopt(f,p).status_code==201;verified(f,p,'P1');old=stored(f,p);unchanged=business(f);lines=[];messages=queue.Queue()
 errpath=OUT/'independent-html.stderr.log'
 with errpath.open('w') as err:
  proc=subprocess.Popen(['node','tests/independent_catalog_query_full_html.js'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
  def consume():
   for line in proc.stdout:messages.put(line)
   messages.put(None)
  threading.Thread(target=consume,daemon=True).start();proc.stdin.write(json.dumps(dict(base=str(f[3].base_url).rstrip('/'),token=f[2]['fixture-a'],A={k:p[k] for k in ['preparation_id','case_id','run_id']}))+'\n');proc.stdin.flush()
  try:
   while True:
    line=messages.get(timeout=60)
    if line is None:break
    lines.append(line);item=json.loads(line)
    if item.get('control')=='insert_catalog_version':add_version(f);proc.stdin.write('{}\n');proc.stdin.flush()
    elif item.get('control')=='assert_final':
     now=stored(f,p);assert now['events'][:len(old['events'])]==old['events'] and now['revision']==old['revision']+2 and now['id']==old['id'] and business(f)==unchanged
     proc.stdin.write('{}\n');proc.stdin.flush()
   code=proc.wait(timeout=5)
  finally:
   if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
   (OUT/'independent-html.stdout.jsonl').write_text(''.join(lines))
 assert code==0,errpath.read_text()
 result=json.loads(lines[-1]);assert result['checks']>=9 and sum(c['method']=='POST' for c in result['calls'])==2
