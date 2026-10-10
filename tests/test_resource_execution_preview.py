"""Original P2 commands on real PG; public business and prior P1 artifacts unchanged."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from uuid import UUID,uuid4
import json,sqlite3
import pytest
from fastapi.testclient import TestClient
from parkweave import resource_execution_preview as rp, isolated_execution_preview as ep
from parkweave import resource_combinations as rc, resource_holds as rh, case_resources as cr, bounded_planning as planning
from parkweave.api import create_app
from parkweave.store import Store,Denied
from test_isolated_execution_preview import preparation_fixture,setup as p1_setup,snapshot,execute as p1_execute,add
from test_preparation import headers


def setup(f,tmp_path,slots=2,goals=None):
    rc.seed_synthetic(f[1])
    p,p1=p1_setup(f,tmp_path,slots,goals or ['LOCAL_CASE_RECORD_RECHECK','外部正式成果'])
    engine=rp.ResourceExecutionPreview(f[0],(tmp_path/('resource-preview-'+uuid4().hex)).resolve(),enabled_for_synthetic_preview=True)
    engine.attach_store(f[0]);return p,p1,engine


def read(f,p,key=None,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/resource-execution-preview'+('/recovery/'+key if key else ''),headers=headers(f[2],user))


def body(f,p):
    x=read(f,p).json();return dict(expected_preparation_revision=x['preparation_revision'],expected_request_revision=x['request_revision'],expected_source_sha256=x['current_source_sha256'])


def execute(f,p,b=None,key=None,user='fixture-a'):
    return f[3].post('/api/preparations/'+p['preparation_id']+'/resource-execution-preview',headers=headers(f[2],user,key or uuid4().hex),json=b or body(f,p))


def test_original_resource_commands_real_shadows_and_formal_values_and_p1_bytes_unchanged(preparation_fixture,tmp_path,monkeypatch):
    f=preparation_fixture;p,p1,e=setup(f,tmp_path);assert p1_execute(f,p).status_code==201;old=p1.path.read_bytes();before=snapshot(f);calls=[];connections=[]
    for module,name in ((rh,'preview'),(rh,'create'),(rc,'confirm'),(cr,'bind')):
        original=getattr(module,name)
        def observed(store,*args,_name=name,_original=original,**kwargs):
            c=store.connection._raw;connections.append(c)
            names={r['relname'] for r in c.execute("SELECT relname FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'")}
            assert names==set(rp.TABLES);assert c.execute('SHOW search_path').fetchone()['search_path']=='pg_temp'
            calls.append(_name);return _original(store,*args,**kwargs)
        monkeypatch.setattr(module,name,observed)
    r=execute(f,p);assert r.status_code==201,r.text;x=r.json()['result'];a=x['artifact']
    assert calls==['preview','create','preview','create','confirm','bind'] and all(c.closed for c in connections)
    assert x['state']=='SUCCEEDED' and a['p2_state']=='LOCAL_ASSOCIATION_PREVIEWED' and a['p1']['state']=='LOCAL_CONFIRMED'
    assert len(a['holds'])==len(a['receipts'])==2 and all(h['state']=='CONFIRMED' for h in a['holds'])
    assert all(UUID(h['resource_id']) not in rp.RESOURCES for h in a['holds'])
    assert len(a['links'])==len(a['claims'])==len(a['combination_receipts'])==1
    assert a['links'][0]['case_id']==a['p1']['case_id']!=p['case_id'] and a['links'][0]['preparation_sha256']==a['p1']['snapshot_sha256']
    assert x['required_goals']==['LOCAL_CASE_RECORD_RECHECK','外部正式成果'] and x['not_previewed']==['P3','P4','P5'] and x['goal_coverage'][1]['status']=='UNSUPPORTED'
    assert all(v['occupied_peak']==0 for v in a['prechecks']) and r.json()['source_atomicity'] is False
    assert snapshot(f)==before and p1.path.read_bytes()==old
    fresh=rp.ResourceExecutionPreview(f[0],e.root,enabled_for_synthetic_preview=True);fresh.attach_store(f[0]);assert read(f,p).json()['history'][0]['document']==x and snapshot(f)==before
    with pytest.raises(Denied):ep.IsolatedExecutionPreview(f[0],e.root,enabled_for_synthetic_preview=True)
    assert e.path.stat().st_mode & 0o777==0o600


@pytest.mark.parametrize('bad',['disabled','window','p1'])
def test_actual_domain_failure_explicit_repair_keeps_history(preparation_fixture,tmp_path,bad):
    f=preparation_fixture;p,_,e=setup(f,tmp_path,slots=1 if bad=='p1' else 2)
    if bad!='p1':
        with f[1].connect() as c:
            sql="enabled=false" if bad=='disabled' else "open_until=clock_timestamp()+interval '30 minutes'"
            c.execute('UPDATE synthetic_resources SET '+sql+' WHERE id=%s',(rc.SECOND_RESOURCE_ID,))
    before=snapshot(f);key=uuid4().hex;r=execute(f,p,key=key);assert r.status_code==201,r.text;old=r.json()['result']
    assert old['state']=='FAILED' and snapshot(f)==before
    assert old['artifact']['p2_state']==('NOT_EXECUTED' if bad=='p1' else 'FAILED')
    if bad=='p1':assert 'P2' in old['not_previewed']
    if bad=='p1':p=add(f,p,'material_outline','SYNTHETIC repaired').json()
    else:
        with f[1].connect() as c:
            c.execute("UPDATE synthetic_resources SET revision=revision+1,enabled=true,open_until=clock_timestamp()+interval '30 days',source=jsonb_set(source,'{revision}','\"2\"') WHERE id=%s",(rc.SECOND_RESOURCE_ID,))
    before=snapshot(f);assert read(f,p,key).json()['result']==old
    assert execute(f,p).json()['result']['state']=='SUCCEEDED' and snapshot(f)==before
    assert read(f,p).json()['history'][0]['source_state']=='STALE'


def test_same_key_concurrent_and_cold_get_only_and_cas(preparation_fixture,tmp_path):
    f=preparation_fixture;p,_,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;before=snapshot(f)
    def call(_):return e.execute(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),key,ep.Execute(**b))
    with ThreadPoolExecutor(2) as pool:out=list(pool.map(call,range(2)))
    assert out[0]['result']==out[1]['result'] and len(read(f,p).json()['history'])==1 and snapshot(f)==before
    s=Store(f[0].dsn);rp.ResourceExecutionPreview(s,e.root,enabled_for_synthetic_preview=True).attach_store(s)
    with TestClient(create_app(s)) as client:
        r=client.get('/api/preparations/'+p['preparation_id']+'/resource-execution-preview/recovery/'+key,headers=headers(f[2]));assert r.json()['result']==out[0]['result'] and r.json()['automatically_replayed'] is False
    assert execute(f,p,{**b,'expected_request_revision':b['expected_request_revision']+1},key).status_code==409
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET revision=revision+1 WHERE id=%s',(rh.RESOURCE_ID,))
    before=snapshot(f);assert execute(f,p,b).status_code==409 and read(f,p,key).json()['history'][0]['source_state']=='STALE' and snapshot(f)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_other_owner_enterprise_role_denied_no_private_artifact(preparation_fixture,tmp_path,user):
    f=preparation_fixture;p,_,e=setup(f,tmp_path);b=body(f,p);before=snapshot(f)
    assert execute(f,p,b,user=user).status_code==read(f,p,user=user).status_code==403 and snapshot(f)==before
    with sqlite3.connect(e.path) as c:assert c.execute('SELECT count(*) FROM previews').fetchone()[0]==0


@pytest.mark.parametrize('cap',['READ','EXECUTE','PREPARE','RESOURCE_READ','HOLD'])
def test_current_revocation_precedes_old_replay_and_recovery(preparation_fixture,tmp_path,cap):
    f=preparation_fixture;p,_,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;assert execute(f,p,b,key).status_code==201
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        if cap in ('RESOURCE_READ','HOLD'):c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND resource_id=%s AND capability=%s",(rh.RESOURCE_ID,'READ' if cap=='RESOURCE_READ' else cap))
        else:c.execute('UPDATE '+('preparation_grants' if cap=='PREPARE' else 'capability_grants')+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap,))
    before=snapshot(f);old=e.path.read_bytes();assert execute(f,p,b,key).status_code==read(f,p,key).status_code==403 and snapshot(f)==before and e.path.read_bytes()==old


def test_registered_drift_extra_inputs_default_disabled_and_formal_uuid_consumption(preparation_fixture,tmp_path,monkeypatch):
    f=preparation_fixture;p,_,e=setup(f,tmp_path);b=body(f,p);x=execute(f,p,b).json()['result'];before=snapshot(f)
    for extra in ({'sql':'UPDATE cases'},{'resource_id':str(rh.RESOURCE_ID)},{'role':'enterprise_operator'}):assert execute(f,p,{**b,**extra}).status_code==422
    with TestClient(create_app(Store(f[0].dsn))) as client:assert client.get('/api/preparations/'+p['preparation_id']+'/resource-execution-preview',headers=headers(f[2])).status_code==403
    monkeypatch.setitem(planning.ACTIONS,'P2',[{**rp.P2_ACTIONS[0],'commands':['UNREGISTERED']}])
    assert read(f,p).json()['execution_available'] is False and execute(f,p).status_code==409
    a=x['artifact'];r=f[3].post('/api/resource-combinations/'+a['combination']['id']+'/cancel',headers=headers(f[2],key=uuid4().hex),json={});assert r.status_code==403
    assert snapshot(f)==before


def test_temp_write_fault_then_sqlite_commit_fault_recovery_and_closed_sql(preparation_fixture,tmp_path,monkeypatch):
    f=preparation_fixture;p,_,e=setup(f,tmp_path);b=body(f,p);before=snapshot(f);key=uuid4().hex;original=rc.confirm;connections=[]
    def failure(store,*args,**kwargs):
        result=original(store,*args,**kwargs);connections.append(store.connection._raw)
        for q in ("UPDATE public.cases SET state='NEEDS_INPUT'",'SET search_path TO public','SELECT pg_advisory_unlock_all()','SELECT set_config(%s,%s,true)','CREATE TABLE arbitrary(id int)'):
            with pytest.raises(Denied):store.connection.execute(q)
        raise ep.Unavailable('SYNTHETIC fault after actual isolated combination')
    monkeypatch.setattr(rc,'confirm',failure);assert execute(f,p,b,key).status_code==503 and all(c.closed for c in connections)
    assert read(f,p,key).json()['status']=='NOT_OBSERVED' and snapshot(f)==before
    monkeypatch.setattr(rc,'confirm',original);database=e._database
    class FailCommit:
        def __init__(self,db):self.db=db
        def execute(self,*args):return self.db.execute(*args)
        def commit(self):raise ep.Unavailable('SYNTHETIC SQLite commit fault')
    @contextmanager
    def failed():
        with database() as db:yield FailCommit(db)
    monkeypatch.setattr(e,'_database',failed);assert execute(f,p,b,key).status_code==503
    monkeypatch.setattr(e,'_database',database);assert read(f,p,key).json()['status']=='NOT_OBSERVED' and snapshot(f)==before
    assert execute(f,p,b,key).status_code==201 and snapshot(f)==before


def test_document_rehash_cannot_change_artifact_or_complete_goals(preparation_fixture,tmp_path):
    f=preparation_fixture;p,_,e=setup(f,tmp_path);x=execute(f,p).json()['result'];before=snapshot(f)
    with sqlite3.connect(e.path) as db:
        row=dict(zip([d[0] for d in db.execute('SELECT * FROM previews').description],db.execute('SELECT * FROM previews').fetchone()))
    for change in ('artifact','goals','state'):
        doc=json.loads(row['document'])
        if change=='artifact':doc['artifact']['holds']=[]
        elif change=='goals':doc['required_goals']=[]
        else:doc['state']='FAILED'
        doc['sha256']=ep._sha({k:v for k,v in doc.items() if k!='sha256'})
        with pytest.raises(Exception,match='proof unavailable'):e._document({**row,'document':json.dumps(doc)})
    assert snapshot(f)==before and read(f,p).json()['history'][0]['document']==x


def test_after_commit_response_failure_get_restores_exact_original_artifact(preparation_fixture,tmp_path,monkeypatch):
    f=preparation_fixture;p,_,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;before=snapshot(f);original=e._comparison;calls=[]
    def comparison(*args):
        calls.append(True)
        if len(calls)==2:raise ep.Unavailable('SYNTHETIC lost response after SQLite commit')
        return original(*args)
    monkeypatch.setattr(e,'_comparison',comparison);assert execute(f,p,b,key).status_code==503 and len(calls)==2
    with sqlite3.connect(e.path) as db:assert db.execute('SELECT count(*) FROM previews').fetchone()[0]==1
    recovered=read(f,p,key).json();assert recovered['status']=='COMMITTED' and recovered['result']['state']=='SUCCEEDED' and recovered['automatically_replayed'] is False
    assert snapshot(f)==before


def test_resource_source_change_during_execution_does_not_commit_old_binding(preparation_fixture,tmp_path,monkeypatch):
    f=preparation_fixture;p,_,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;original=e._execute;changed=[]
    def execute_then_change(*args):
        result=original(*args)
        with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET revision=revision+1 WHERE id=%s',(rh.RESOURCE_ID,))
        changed.append(snapshot(f));return result
    monkeypatch.setattr(e,'_execute',execute_then_change);assert execute(f,p,b,key).status_code==409
    assert read(f,p,key).json()['status']=='NOT_OBSERVED' and snapshot(f)==changed[0]
