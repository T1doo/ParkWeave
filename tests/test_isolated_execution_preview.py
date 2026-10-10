"""Real registered PG commands; all public business bytes must stay unchanged."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID,uuid4
import hashlib,json,sqlite3
import pytest
from psycopg.errors import UndefinedTable
from parkweave import isolated_execution_preview as ep, preparation as prep
from parkweave.api import create_app
from parkweave.store import Store,Denied
from fastapi.testclient import TestClient
from test_preparation import preparation_fixture,create,headers,add
from test_request_intents import save
from test_bounded_planning import read as proposal


def snapshot(f):
    with f[1].connect() as c:
        names=[r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename!='authorization_audit' ORDER BY tablename")]
        return {name:sorted(json.dumps(dict(r),sort_keys=True,default=str) for r in c.execute('SELECT * FROM "'+name+'"')) for name in names}


def setup(f,tmp_path,slots=2,goals=None):
    p,_,_=create(f);p={**p,'revision':save(f,p,goals=goals or ['LOCAL_MATERIAL_PREPARATION']).json()['revision']}
    for slot in prep.SLOTS[:slots]:p=add(f,p,slot,'SYNTHETIC PRIVATE_PREVIEW '+slot).json()
    engine=ep.IsolatedExecutionPreview(f[0],(tmp_path/('preview-'+uuid4().hex)).resolve(),enabled_for_synthetic_preview=True);engine.attach_store(f[0]);return p,engine


def body(f,p):
    x=proposal(f,p).json()['current']
    with f[1].connect() as c:revision=c.execute('SELECT request_intent FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['request_intent']['revision']
    return dict(expected_preparation_revision=x['preparation_revision'],expected_request_revision=revision,expected_source_sha256=x['source_sha256'])


def execute(f,p,b=None,key=None,user='fixture-a'):
    return f[3].post('/api/preparations/'+p['preparation_id']+'/execution-preview',headers=headers(f[2],user,key or uuid4().hex),json=b or body(f,p))


def read(f,p,key=None,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/execution-preview'+('/recovery/'+key if key else ''),headers=headers(f[2],user))


def test_actual_registered_four_commands_separate_artifact_all_public_values_unchanged(preparation_fixture,tmp_path,monkeypatch):
    f=preparation_fixture;p,engine=setup(f,tmp_path);b=body(f,p);before=snapshot(f);calls=[];original=prep.command
    def observed(store,token,id,key,data):
        c=store.connection.connection
        rows=c.execute("SELECT relname FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r' ORDER BY relname").fetchall()
        assert {r['relname'] for r in rows}==set(ep.TABLES)
        calls.append(data.action);return original(store,token,id,key,data)
    monkeypatch.setattr(prep,'command',observed)
    r=execute(f,p,b);assert r.status_code==201,r.text;x=r.json()['result'];a=x['artifact']
    assert calls==['ADD_EVIDENCE','ADD_EVIDENCE','REVIEW','CONFIRM']
    assert x['state']=='SUCCEEDED' and a['state']=='LOCAL_CONFIRMED' and a['namespace']=='PREVIEW_EXECUTION'
    assert a['preparation_id']!=p['preparation_id'] and a['case_id']!=p['case_id'] and a['run_id']!=p['run_id']
    assert [e['action'] for e in a['events']]==calls and a['revision']==5 and a['review_sha256']==a['snapshot_sha256']
    assert snapshot(f)==before and x['formal_writes']==0 and not x['case_goal_completed'] and not x['new_grants']
    with f[1].connect() as c:
        for table in ['principals','capability_grants','preparation_grants']:assert not c.execute('SELECT 1 FROM '+table+" WHERE "+('id' if table=='principals' else 'principal_id')+" LIKE 'preview-%'").fetchone()
    reopened=ep.IsolatedExecutionPreview(f[0],engine.root,enabled_for_synthetic_preview=True);reopened.attach_store(f[0]);assert read(f,p).json()['history'][0]['document']==x
    assert engine.root.stat().st_mode & 0o777==0o700 and engine.path.stat().st_mode & 0o777==0o600


@pytest.mark.parametrize('slots',[0,1])
def test_missing_input_actual_review_failed_then_explicit_new_source_preserves_failed_history(preparation_fixture,tmp_path,slots):
    f=preparation_fixture;p,engine=setup(f,tmp_path,slots);before=snapshot(f);key=uuid4().hex;r=execute(f,p,key=key);assert r.status_code==201,r.text;x=r.json()['result']
    assert x['state']=='FAILED' and x['artifact']['state']=='IN_PREPARATION' and len(x['artifact']['events'])==slots and snapshot(f)==before
    for slot in prep.SLOTS[slots:]:p=add(f,p,slot,'SYNTHETIC actual corrected '+slot).json()
    before=snapshot(f);assert read(f,p,key).json()['result']==x
    r=execute(f,p);assert r.status_code==201 and r.json()['result']['state']=='SUCCEEDED' and snapshot(f)==before
    h=read(f,p).json()['history'];assert h[0]['document']==x and h[0]['source_state']=='STALE' and len(h)==2


def test_all_goals_kept_other_registered_steps_never_executed(preparation_fixture,tmp_path):
    f=preparation_fixture;goals=['LOCAL_CASE_RECORD_RECHECK','外部正式成果'];p,e=setup(f,tmp_path,goals=goals);before=snapshot(f);r=execute(f,p);assert r.status_code==201,r.text;x=r.json()['result']
    assert x['required_goals']==goals and x['not_previewed']==['P2','P3','P4','P5'] and x['coverage_state']=='PARTIAL_PREVIEW'
    assert x['goal_coverage'][1]['status']=='UNSUPPORTED' and snapshot(f)==before


def test_same_key_concurrency_lost_reply_read_only_new_store_and_body_mismatch(preparation_fixture,tmp_path):
    f=preparation_fixture;p,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;before=snapshot(f)
    def call(_):return e.execute(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),key,ep.Execute(**b))
    with ThreadPoolExecutor(2) as pool:r=list(pool.map(call,range(2)))
    assert r[0]['result']==r[1]['result'] and len(read(f,p).json()['history'])==1 and snapshot(f)==before
    recreated=Store(f[0].dsn);e.attach_store(recreated);x=e.read(recreated,f[2]['fixture-a'],UUID(p['preparation_id']),key);assert x['status']=='COMMITTED' and x['result']==r[0]['result'] and snapshot(f)==before
    assert execute(f,p,{**b,'expected_request_revision':b['expected_request_revision']+1},key).status_code==409
    assert read(f,p,uuid4().hex).json()['status']=='NOT_OBSERVED' and snapshot(f)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_other_actor_or_enterprise_denied_without_private_artifact(preparation_fixture,tmp_path,user):
    f=preparation_fixture;p,e=setup(f,tmp_path);b=body(f,p);before=snapshot(f)
    assert execute(f,p,b,user=user).status_code==403 and read(f,p,user=user).status_code==403 and snapshot(f)==before
    with sqlite3.connect(e.path) as c:assert c.execute('SELECT count(*) FROM previews').fetchone()[0]==0


@pytest.mark.parametrize('cap',['READ','EXECUTE','PREPARE'])
def test_revocation_precedes_replay_and_cold_recovery(preparation_fixture,tmp_path,cap):
    f=preparation_fixture;p,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;assert execute(f,p,b,key).status_code==201
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True);table='preparation_grants' if cap=='PREPARE' else 'capability_grants';c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap,))
    before=snapshot(f);assert execute(f,p,b,key).status_code==403 and read(f,p,key).status_code==403 and snapshot(f)==before


def test_changed_source_and_invalid_input_refused_default_dormant(preparation_fixture,tmp_path):
    f=preparation_fixture;p,e=setup(f,tmp_path);b=body(f,p);p=add(f,p,text='SYNTHETIC changed').json();before=snapshot(f)
    assert execute(f,p,b).status_code==409
    for extra in [{'sql':'UPDATE cases'},{'namespace':'public'},{'role':'park_specialist'}]:assert execute(f,p,{**body(f,p),**extra}).status_code==422
    with TestClient(create_app(Store(f[0].dsn))) as client:
        assert client.post('/api/preparations/'+p['preparation_id']+'/execution-preview',headers=headers(f[2],key=uuid4().hex),json=body(f,p)).status_code==403
    assert snapshot(f)==before


def test_interruption_after_actual_temp_writes_does_not_commit_or_touch_business_then_explicit_retry(preparation_fixture,tmp_path,monkeypatch):
    f=preparation_fixture;p,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;before=snapshot(f);original=prep.command;connections=[];calls=[]
    def interrupted(store,token,id,key,data):
        r=original(store,token,id,key,data);connections.append(store.connection.connection);calls.append(data.action)
        if data.action=='REVIEW':raise ep.Unavailable('SYNTHETIC injected interruption after actual writes')
        return r
    monkeypatch.setattr(prep,'command',interrupted);r=execute(f,p,b,key);assert r.status_code==503 and calls==['ADD_EVIDENCE','ADD_EVIDENCE','REVIEW']
    assert all(c.closed for c in connections) and snapshot(f)==before and read(f,p,key).json()['status']=='NOT_OBSERVED'
    with sqlite3.connect(e.path) as c:assert c.execute('SELECT count(*) FROM previews').fetchone()[0]==0
    monkeypatch.setattr(prep,'command',original);r=execute(f,p,b,key);assert r.status_code==201 and r.json()['result']['state']=='SUCCEEDED' and snapshot(f)==before


def test_preview_ids_not_accepted_by_formal_commands(preparation_fixture,tmp_path):
    f=preparation_fixture;p,e=setup(f,tmp_path);x=execute(f,p).json()['result'];before=snapshot(f);a=x['artifact']
    r=f[3].post('/api/preparations/'+a['preparation_id']+'/commands',headers=headers(f[2],key=uuid4().hex),json={'action':'CONFIRM','expected_revision':a['revision'],'reason':'SYNTHETIC cannot consume preview'});assert r.status_code==403 and snapshot(f)==before


def test_foreign_storage_symlink_and_other_database_rejected_without_repair(preparation_fixture,tmp_path):
    f=preparation_fixture;p,e=setup(f,tmp_path)
    other=tmp_path/'foreign';other.mkdir(mode=0o700);(other/'keep.txt').write_text('SYNTHETIC unchanged')
    with pytest.raises(Denied):ep.IsolatedExecutionPreview(f[0],other,enabled_for_synthetic_preview=True)
    symlink=tmp_path/'link';symlink.symlink_to(e.root,target_is_directory=True)
    with pytest.raises(Denied):ep.IsolatedExecutionPreview(f[0],symlink,enabled_for_synthetic_preview=True)
    with pytest.raises(Denied):ep.IsolatedExecutionPreview(f[0],e.root)
    assert (other/'keep.txt').read_text()=='SYNTHETIC unchanged'


def test_actual_sqlite_lock_unavailable_then_get_and_explicit_attempt_no_formal_write(preparation_fixture,tmp_path):
    f=preparation_fixture;p,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;before=snapshot(f)
    with sqlite3.connect(e.path) as held:
        held.execute('BEGIN EXCLUSIVE')
        r=execute(f,p,b,key);assert r.status_code==503 and snapshot(f)==before
        held.rollback()
    assert read(f,p,key).json()['status']=='NOT_OBSERVED' and snapshot(f)==before
    assert execute(f,p,b,key).status_code==201 and snapshot(f)==before


def test_failed_artifact_commit_rolls_back_actual_sqlite_insert_no_false_committed(preparation_fixture,tmp_path,monkeypatch):
    from contextlib import contextmanager
    f=preparation_fixture;p,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;before=snapshot(f);original=e._database;inserted=[]
    class FailCommit:
        def __init__(self,db):self.db=db
        def execute(self,q,params=()):
            r=self.db.execute(q,params)
            if q.startswith('INSERT INTO previews'):inserted.append(True)
            return r
        def commit(self):raise ep.Unavailable('SYNTHETIC lost storage commit')
    @contextmanager
    def unavailable():
        with original() as db:yield FailCommit(db)
    monkeypatch.setattr(e,'_database',unavailable);assert execute(f,p,b,key).status_code==503 and inserted==[True] and snapshot(f)==before
    monkeypatch.setattr(e,'_database',original);assert read(f,p,key).json()['status']=='NOT_OBSERVED' and snapshot(f)==before
    assert execute(f,p,b,key).status_code==201 and snapshot(f)==before


def test_closed_adapter_never_falls_back_to_business_schema_or_unknown_table(preparation_fixture,tmp_path,monkeypatch):
    f=preparation_fixture;p,e=setup(f,tmp_path);b=body(f,p);before=snapshot(f);original=prep.command;rejected=[]
    def probe(store,token,id,key,data):
        c=store.connection
        for query in ['UPDATE public.cases SET state=\'FULFILLED\'','INSERT INTO synthetic_resource_holds(id) VALUES(null)','CREATE TABLE arbitrary(id int)','SET search_path TO public','SELECT pg_catalog.pg_sleep(1)',"SELECT set_config('search_path','public',true)",'SELECT pg_advisory_unlock_all()']:
            with pytest.raises(Denied):c.execute(query)
            rejected.append(query.split()[0])
        with pytest.raises(UndefinedTable):c.connection.execute('SELECT 1 FROM cases')
        # A missing relation aborts PG, so deliberately do not run this unsafe
        # raw inspector in normal execution; outer rollback destroys shadows.
        raise ep.Unavailable('SYNTHETIC closed search_path proved missing formal cases')
    monkeypatch.setattr(prep,'command',probe);assert execute(f,p,b).status_code==503 and len(rejected)==7 and snapshot(f)==before
    monkeypatch.setattr(prep,'command',original);assert execute(f,p,b).status_code==201 and snapshot(f)==before


def test_case_limit_and_storage_mutation_or_extra_schema_rejected(preparation_fixture,tmp_path):
    f=preparation_fixture;p,e=setup(f,tmp_path);b=body(f,p);before=snapshot(f)
    for _ in range(16):assert execute(f,p,b).status_code==201
    assert execute(f,p,b).status_code==409 and len(read(f,p).json()['history'])==16 and snapshot(f)==before
    with sqlite3.connect(e.path) as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute("UPDATE previews SET fingerprint='damaged'")
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM previews')
        db.execute('CREATE TABLE foreign_object(value TEXT)');db.commit()
    before_bytes=e.path.read_bytes();assert read(f,p).status_code==403 and e.path.read_bytes()==before_bytes and snapshot(f)==before


def test_source_catalog_change_during_actual_execution_refuses_commit_preserves_new_source(preparation_fixture,tmp_path,monkeypatch):
    f=preparation_fixture;p,e=setup(f,tmp_path);b=body(f,p);original=e._execute;changed=[]
    def change(*args):
        artifact=original(*args)
        with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_build_object('kind','SYNTHETIC','id','preview-source-revision','revision','2')")
        changed.append(snapshot(f));return artifact
    monkeypatch.setattr(e,'_execute',change);assert execute(f,p,b).status_code==409 and snapshot(f)==changed[0]
    assert read(f,p).json()['history']==[]
    monkeypatch.setattr(e,'_execute',original);before=snapshot(f);assert execute(f,p).status_code==201 and snapshot(f)==before


@pytest.mark.parametrize('damage',['actor','fingerprint','private_case','duplicate_event','snapshot','role','source_body'])
def test_rehashed_storage_corruption_never_served_or_replayed(preparation_fixture,tmp_path,damage):
    f=preparation_fixture;p,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;r=execute(f,p,b,key);assert r.status_code==201;x=r.json()['result'];before=snapshot(f)
    if damage=='actor':x['artifact']['events'][0]['actor_id']='preview-owner-'+uuid4().hex
    elif damage=='fingerprint':x['artifact']['events'][0]['fingerprint']='0'*64
    elif damage=='private_case':x['artifact']['case_id']=p['case_id']
    elif damage=='duplicate_event':x['artifact']['events'][1]['id']=x['artifact']['events'][0]['id']
    elif damage=='snapshot':x['artifact']['events'][0]['payload']['snapshot_sha256']='0'*64
    elif damage=='role':x['artifact']['roles']='ACTUAL_REVIEWER'
    else:x['binding']['source_sha256']='0'*64
    x['sha256']=ep._sha({k:v for k,v in x.items() if k!='sha256'})
    with sqlite3.connect(e.path) as db:
        trigger=db.execute("SELECT sql FROM sqlite_master WHERE name='immutable_update'").fetchone()[0];db.execute('DROP TRIGGER immutable_update');db.execute('UPDATE previews SET document=?',(prep.canonical(x),));db.execute(trigger);db.commit()
    original=e.path.read_bytes();assert read(f,p).status_code==409 and read(f,p,key).status_code==409 and execute(f,p,b,key).status_code==409 and e.path.read_bytes()==original and snapshot(f)==before


def test_distinct_actual_pg_clusters_same_name_oid_socket_port_refuse_reopen(tmp_path):
    import pgserver,psycopg
    from psycopg.conninfo import make_conninfo
    servers=[];stores=[]
    try:
        for i in range(2):
            server=pgserver.get_server(tmp_path/('cluster-'+str(i)),cleanup_mode='stop');servers.append(server)
            with psycopg.connect(server.get_uri(),autocommit=True) as c:c.execute('CREATE DATABASE preview_identity_probe')
            stores.append(Store(make_conninfo(server.get_uri(),dbname='preview_identity_probe')))
        identities=[ep._identity(s) for s in stores]
        assert identities[0]['name']==identities[1]['name'] and identities[0]['oid']==identities[1]['oid'] and identities[0]['system_identifier']!=identities[1]['system_identifier']
        for s in stores:
            with s.connect() as c:assert c.execute('SELECT inet_server_port() port').fetchone()['port'] is None
        root=(tmp_path/'same-named-database-preview').resolve();e=ep.IsolatedExecutionPreview(stores[0],root,enabled_for_synthetic_preview=True);before=e.path.read_bytes()
        with pytest.raises(Denied):e.attach_store(stores[1])
        with pytest.raises(Denied):ep.IsolatedExecutionPreview(stores[1],root,enabled_for_synthetic_preview=True)
        assert e.path.read_bytes()==before
    finally:
        for server in reversed(servers):server.cleanup()
