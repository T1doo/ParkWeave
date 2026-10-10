"""Separate business oracles; same original fixtures, actual loopback HTTP."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import hashlib,json,sqlite3
import pytest
from conftest import pg,fixture
from test_preparation import preparation_fixture,create,headers
from test_isolated_execution_preview import setup,body,execute,read,snapshot
from test_request_intents import save
from test_new_enterprise_local_chain import actual_http
from parkweave.api import create_app
from parkweave import preparation as prep,isolated_execution_preview as ep

PRIVATE_EVIDENCE=Path('/workspace/ParkWeave/.runtime/independent-isolated-execution-preview-v2-review')
def hash_json(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def evidence(name,x):(PRIVATE_EVIDENCE/(name+'-safe.json')).write_text(json.dumps(x,indent=2)+'\n')
@pytest.fixture
def actual(preparation_fixture):
 f=preparation_fixture
 with actual_http(create_app(f[0])) as (client,requests):yield f[:3]+(client,)
def update_document(engine,x):
 x['sha256']=hash_json({k:v for k,v in x.items() if k!='sha256'})
 with sqlite3.connect(engine.path) as db:
  triggers=db.execute("SELECT sql FROM sqlite_master WHERE name='immutable_update'").fetchone()[0]
  db.execute('DROP TRIGGER immutable_update');db.execute('UPDATE previews SET document=?',(prep.canonical(x),));db.execute(triggers);db.commit()

@pytest.mark.parametrize('damage',['slot_bool','slot_float','not_previewed','execution_contract'])
def test_typed_independent_anchor(actual,tmp_path,damage):
 f=actual;p,e=setup(f,tmp_path,goals=['LOCAL_CASE_RECORD_RECHECK','SYNTHETIC mandatory unsupported final target']);b=body(f,p);key=uuid4().hex;r=execute(f,p,b,key);assert r.status_code==201;x=r.json()['result']
 if damage.startswith('slot_'):x['binding']['slots'][0]['version']=True if damage=='slot_bool' else 1.0
 elif damage=='not_previewed':assert x['not_previewed']==['P2','P3','P4','P5'];x['not_previewed']=[]
 else:x['execution_contract_sha256']='0'*64
 with sqlite3.connect(e.path) as db:proof_before=db.execute('SELECT proof FROM previews').fetchone()[0]
 update_document(e,x);before=snapshot(f);bytes_before=e.path.read_bytes()
 codes=[read(f,p).status_code,read(f,p,key).status_code,execute(f,p,b,key).status_code]
 with sqlite3.connect(e.path) as db:proof_unchanged=proof_before==db.execute('SELECT proof FROM previews').fetchone()[0]
 evidence('typed-'+damage,dict(codes=codes,expected=[409]*3,proof_unchanged=proof_unchanged,formal_values_unchanged=snapshot(f)==before,sqlite_bytes_unchanged=e.path.read_bytes()==bytes_before,actual_http=True))
 assert codes==[409]*3 and proof_unchanged and snapshot(f)==before and e.path.read_bytes()==bytes_before

@pytest.mark.parametrize('column',['document','proof'])
@pytest.mark.parametrize('encoding',['ascii','multibyte'])
def test_foreign_case_global_byte_bound(actual,tmp_path,column,encoding):
 f=actual;p,e=setup(f,tmp_path);b=body(f,p);assert execute(f,p,b).status_code==201
 other,_,_=create(f,user='fixture-b');payload='x'*65537 if encoding=='ascii' else '\u4e2d'*22000
 with sqlite3.connect(e.path) as db:
  fields=dict(owner='fixture-b',preparation=other['preparation_id'],request_key=uuid4().hex,fingerprint='0'*64,document='{}',proof='{}');fields[column]=payload
  db.execute('INSERT INTO previews VALUES(?,?,?,?,?,?)',tuple(fields.values()));db.commit()
 before=snapshot(f);before_bytes=e.path.read_bytes();codes=[read(f,p).status_code,execute(f,p,b).status_code]
 evidence('global-byte-'+column+'-'+encoding,dict(codes=codes,expected=[403]*2,foreign_actor_and_case=True,payload_characters=len(payload),payload_bytes=len(payload.encode()),formal_values_unchanged=snapshot(f)==before,sqlite_bytes_unchanged=e.path.read_bytes()==before_bytes,actual_http=True))
 assert codes==[403]*2 and snapshot(f)==before and e.path.read_bytes()==before_bytes

@pytest.mark.parametrize('damage',['extra','db_oid'])
def test_meta_identity_each_open(actual,tmp_path,damage):
 f=actual;p,e=setup(f,tmp_path);b=body(f,p);assert execute(f,p,b).status_code==201
 with sqlite3.connect(e.path) as db:
  meta=json.loads(db.execute('SELECT value FROM meta').fetchone()[0])
  if damage=='extra':meta['unrecognized']=True
  else:meta['database']['oid']='0'
  db.execute('UPDATE meta SET value=?',(prep.canonical(meta),));db.commit()
 before=snapshot(f);data=e.path.read_bytes();codes=[read(f,p).status_code,execute(f,p,b).status_code]
 evidence('meta-'+damage,dict(codes=codes,expected=[403]*2,formal_values_unchanged=snapshot(f)==before,sqlite_bytes_unchanged=e.path.read_bytes()==data,actual_http=True))
 assert codes==[403]*2 and snapshot(f)==before and e.path.read_bytes()==data

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_current_original_actor_and_scope(actual,tmp_path,user):
 f=actual;p,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;assert execute(f,p,b,key).status_code==201
 before=snapshot(f);data=e.path.read_bytes();rs=[read(f,p,key,user=user),execute(f,p,b,key,user=user)]
 assert [r.status_code for r in rs]==[403,403] and all('PRIVATE_PREVIEW' not in r.text for r in rs)
 assert snapshot(f)==before and e.path.read_bytes()==data
 evidence('scope-'+user,dict(statuses=[403]*2,private_text_absent=True,formal_values_unchanged=True,sqlite_bytes_unchanged=True,actual_http=True))

def test_real_created_service_v2_is_readonly_not_v1_conversion(actual,tmp_path):
 f=actual
 with f[1].connect() as c:c.execute("INSERT INTO preparation_catalog(park_id,service_id,version,name,source,namespace,qualification) SELECT park_id,service_id,2,name,source,namespace,qualification FROM preparation_catalog WHERE version=1")
 run=f[3].post('/api/runs',headers=headers(f[2],key=uuid4().hex),json={'goal':'SYNTHETIC actual version2 preview boundary'}).json()['run_id'];f[0].finish(f[0].claim('synthetic-independent-service2'))
 data=dict(run_id=run,service_id=prep.SERVICE,service_version=2,reviewer_id='prep-specialist-fixture-a');key=uuid4().hex
 response=f[3].post('/api/preparations',headers=headers(f[2],key=key),json=data);assert response.status_code==201;p=response.json()
 p={**p,'revision':save(f,p,goals=['LOCAL_MATERIAL_PREPARATION']).json()['revision']}
 e=ep.IsolatedExecutionPreview(f[0],(tmp_path/'service-v2-preview').resolve(),enabled_for_synthetic_preview=True);e.attach_store(f[0])
 before=snapshot(f);view=read(f,p);b=body(f,p);r=execute(f,p,b)
 with sqlite3.connect(e.path) as db:count=db.execute('SELECT count(*) FROM previews').fetchone()[0]
 assert view.status_code==200 and view.json()['execution_available'] is False and r.status_code==409 and count==0 and snapshot(f)==before
 evidence('real-created-service2',dict(actual_original_create_version=2,available=False,post=409,rows=0,formal_values_unchanged=True,actual_http=True))

def test_complete_goals_original_artifact_and_explicit_request_change_history(actual,tmp_path,monkeypatch):
 f=actual;goals=['LOCAL_CASE_RECORD_RECHECK','SYNTHETIC mandatory unsupported target'];p,e=setup(f,tmp_path,goals=goals);b=body(f,p);key=uuid4().hex;before=snapshot(f);calls=[];original=prep.command
 def observe(store,token,id,key,data):
  c=store.connection.connection
  rows=c.execute("SELECT relname FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'").fetchall();assert {r['relname'] for r in rows}==set(ep.TABLES)
  assert c.execute('SELECT count(*) n FROM principals').fetchone()['n']==2
  calls.append(data.action);return original(store,token,id,key,data)
 monkeypatch.setattr(prep,'command',observe);first=execute(f,p,b,key);assert first.status_code==201;x=first.json()['result'];a=x['artifact']
 independent_snapshot=hash_json(dict(preparation_id=a['preparation_id'],service_id=prep.SERVICE,service_version=1,materials=a['materials']))
 assert a['snapshot_sha256']==independent_snapshot and a['review_sha256']==independent_snapshot and calls==['ADD_EVIDENCE']*2+['REVIEW','CONFIRM']
 assert x['required_goals']==goals and x['not_previewed']==['P2','P3','P4','P5'] and x['coverage_state']=='PARTIAL_PREVIEW' and snapshot(f)==before
 updated=save(f,p,goals=['LOCAL_MATERIAL_PREPARATION','SYNTHETIC different required target']).json();p={**p,'revision':updated['revision']};before=snapshot(f);bytes_before=e.path.read_bytes()
 restored=read(f,p,key);replay=execute(f,p,b,key)
 assert restored.status_code==200 and restored.json()['result']==x and restored.json()['history'][0]['source_state']=='STALE' and replay.status_code==201 and replay.json()['result']==x
 assert snapshot(f)==before and e.path.read_bytes()==bytes_before and calls==['ADD_EVIDENCE']*2+['REVIEW','CONFIRM']
 evidence('complete-goals-and-history',dict(actual_temp_tables=8,actual_original_commands=calls,full_goal_count=2,unsupported_goal_retained=True,not_previewed=['P2','P3','P4','P5'],independent_snapshot_hash=independent_snapshot,source_change_preserves_original_document=True,source_state='STALE',historical_replay_no_execution=True,formal_values_unchanged=True,actual_http=True))

def test_interrupt_after_confirm_never_durably_succeeds(actual,tmp_path,monkeypatch):
 f=actual;p,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;before=snapshot(f);calls=[];connections=[];command=prep.command
 def interrupt(store,token,id,key,data):
  result=command(store,token,id,key,data);calls.append(data.action);connections.append(store.connection.connection)
  if data.action=='CONFIRM':raise ep.Unavailable('SYNTHETIC after confirmed temp artifact before persistent result')
  return result
 monkeypatch.setattr(prep,'command',interrupt);r=execute(f,p,b,key);assert r.status_code==503
 assert calls==['ADD_EVIDENCE']*2+['REVIEW','CONFIRM'] and all(c.closed for c in connections)
 recovery=read(f,p,key);assert recovery.status_code==200 and recovery.json()['status']=='NOT_OBSERVED' and recovery.json()['history']==[] and snapshot(f)==before
 evidence('after-confirm-interruption',dict(post=503,recovery='NOT_OBSERVED',actual_commands=4,all_temp_connections_closed=True,preview_rows=0,formal_values_unchanged=True,actual_http=True))
