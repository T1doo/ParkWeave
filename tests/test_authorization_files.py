"""ENG-005 fixed engineering subset: real HTTP, CLI worker and isolated PG."""
import hashlib
import os
from pathlib import Path
import secrets
import uuid
import pytest
import psycopg
from parkweave.store import Denied, Store
from test_worker_gateway import runtime,auth,worker,enqueue


def counts(owner):
    with owner.connect() as c:
        return {table:c.execute('SELECT count(*) n FROM '+table).fetchone()['n']
                for table in ('runs','operations','cases','fixture_effects','file_resources')}


def add_role(owner,tokens,role,org='org-a',park='park-a'):
    from parkweave.store import digest
    user='synthetic-'+role;tokens[user]=secrets.token_urlsafe(32)
    with owner.connect() as c:
        c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',(user,digest(tokens[user]),park,org,role))
        c.execute("INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,'READ',%s,%s)",(user,park,org))
    return user


@pytest.mark.parametrize('role',['park_specialist','resource_admin','service_executor'])
def test_roles_assigned_status_only_no_self_elevation(runtime,role):
    api,owner,tokens,env=runtime;run=enqueue(runtime,'case.create');worker(runtime)
    user=add_role(owner,tokens,role);before=counts(owner)
    assert api.get('/api/runs/'+run,headers=auth(tokens,user)).status_code==403
    owner.assign_status(user,run)
    r=api.get('/api/runs/'+run,headers=auth(tokens,user))
    assert r.status_code==200 and set(r.json())=={'run_id','state','revision','visibility'}
    assert r.json()['visibility']=='ASSIGNED_STATUS_ONLY'
    for intent in ('pause','cancel','resume','reconcile'):
        assert api.post('/api/runs/'+run+'/'+intent,headers=auth(tokens,user)).status_code==403
    assert api.post('/api/runs',headers=auth(tokens,user),json={'goal':'x'}).status_code==403
    assert api.post('/api/runs',headers=auth(tokens,user),json={'goal':'x','role':'enterprise_operator'}).status_code==422
    assert api.get('/api/facts',params={'fields':'region'},headers=auth(tokens,user)).status_code==403
    owner.assign_status(user,run,active=False)
    assert api.get('/api/runs/'+run,headers=auth(tokens,user)).status_code==403
    assert counts(owner)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c'])
def test_cross_scope_even_with_misconfigured_assignment_zero_effect(runtime,user):
    api,owner,tokens,env=runtime;run=enqueue(runtime,'case.create');before=counts(owner)
    # Deliberately malformed owner configuration does not widen the intersection.
    with owner.connect() as c:
        c.execute('INSERT INTO run_assignments VALUES(%s,%s,%s,%s,true)',(user,run,'park-a','org-a'))
    assert api.get('/api/runs/'+run,headers=auth(tokens,user)).status_code==403
    assert api.post('/api/runs/'+run+'/cancel',headers=auth(tokens,user)).status_code==403
    assert counts(owner)==before
    worker(runtime)
    assert counts(owner)['cases']==1


@pytest.mark.parametrize('action',['case.create','facts.assess','fault.record'])
def test_queued_execution_rechecks_current_capability(runtime,action):
    api,owner,tokens,env=runtime
    body={'goal':'合成撤权队列','action':action}
    if action=='facts.assess':body['fact_fields']=['region']
    r=api.post('/api/runs',headers=auth(tokens,key='fixedqueue'),json=body)
    assert r.status_code==202;run=r.json()['run_id']
    owner.revoke_capability('fixture-a','EXECUTE');owner.seed(tokens)
    worker(runtime)
    with owner.connect() as c:
        assert c.execute('SELECT state FROM operations WHERE run_id=%s',(run,)).fetchone()['state']=='FAILED_SAFE'
        assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==0
        assert c.execute('SELECT count(*) n FROM fixture_effects').fetchone()['n']==0
    assert api.post('/api/runs',headers=auth(tokens,key='fixedqueue'),json=body).status_code==403


def test_outbox_revoked_before_consume_suppressed_after_delivery_retracted(runtime):
    api,owner,tokens,env=runtime;run=enqueue(runtime,'case.create')
    owner.revoke_capability('fixture-a','READ');worker(runtime)
    with owner.connect() as c:
        rows=c.execute('SELECT * FROM deliveries WHERE run_id=%s',(run,)).fetchall()
        assert len(rows)==2 and all(r['state']=='SUPPRESSED' and r['payload']=={} for r in rows)
        assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==1
    for row in rows:
        assert api.get('/api/messages/'+str(row['event_id']),headers=auth(tokens)).status_code==403
    # A distinct authorized identity demonstrates cached delivered output withdrawal.
    run2=api.post('/api/runs',headers=auth(tokens,'fixture-b'),json={'goal':'合成消息'}).json()['run_id']
    worker(runtime)
    with owner.connect() as c:
        rows2=c.execute("SELECT * FROM deliveries WHERE run_id=%s AND state='READY'",(run2,)).fetchall()
    assert len(rows2)==2
    event=str(rows2[0]['event_id'])
    assert api.get('/api/messages/'+event,headers=auth(tokens,'fixture-b')).status_code==200
    assert api.get('/api/messages/'+event,headers=auth(tokens)).status_code==403
    owner.revoke_capability('fixture-b','READ')
    assert api.get('/api/messages/'+event,headers=auth(tokens,'fixture-b')).status_code==403
    worker(runtime);worker(runtime)
    with owner.connect() as c:
        assert all(r['state']=='RETRACTED' and r['payload']=={} for r in c.execute('SELECT * FROM deliveries WHERE run_id=%s',(run2,)))
        assert c.execute('SELECT count(*) n FROM deliveries').fetchone()['n']==4


def test_outbox_field_grant_revoked_before_consume(runtime):
    api,owner,tokens,env=runtime
    r=api.post('/api/runs',headers=auth(tokens),json={'goal':'合成证据','action':'facts.assess','fact_fields':['region']})
    run=r.json()['run_id'];owner.revoke_field('fixture-a','region','READ');worker(runtime)
    with owner.connect() as c:
        assert all(r['state']=='SUPPRESSED' for r in c.execute('SELECT * FROM deliveries WHERE run_id=%s',(run,)))
    assert api.get('/api/runs/'+run,headers=auth(tokens)).status_code==403


def test_outbox_ack_fault_rolls_back_delivery_monotonic_replay(fixture):
    store,owner,tokens,client=fixture
    run=store.submit(tokens['fixture-a'],'delivery',__import__('parkweave.domain',fromlist=['Intake']).Intake(goal='合成'))
    store.finish(store.claim('fixture'))
    with pytest.raises(RuntimeError):store.consume(fail_before_ack=True)
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM deliveries').fetchone()['n']==0
        assert c.execute('SELECT count(*) n FROM run_projection').fetchone()['n']==0
    while store.consume():pass
    with owner.connect() as c:
        assert c.execute('SELECT revision,payload FROM run_projection').fetchone()['payload']['state']=='SUCCEEDED'
        assert c.execute('SELECT count(*) n FROM deliveries').fetchone()['n']==2
        c.execute('UPDATE outbox SET consumed_at=NULL')
    while store.consume():pass
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM deliveries').fetchone()['n']==2
        assert c.execute('SELECT revision FROM run_projection').fetchone()['revision']==2


@pytest.fixture
def file_runtime(runtime,tmp_path):
    if os.name=='nt':pytest.skip('NOT_RUN: native file backend remains disabled')
    # Restart actual API with explicit private synthetic file root, no credential lookup.
    api,owner,tokens,env=runtime
    root=tmp_path/'private';root.mkdir(mode=0o700)
    owner.file_root=root
    run=enqueue(runtime,'case.create')
    fid=owner.register_synthetic_file('fixture-a',run,b'<script>globalThis.PARKWEAVE_BAD=true</script>\nSYNTHETIC ONLY')
    import socket,subprocess,sys,time,httpx
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port)],
                          env=dict(env,PARKWEAVE_FILE_ROOT=str(root)),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}') as file_api:
            for _ in range(100):
                try:
                    if file_api.get('/health').status_code==200:break
                except httpx.TransportError:pass
                time.sleep(.03)
            else:raise AssertionError('file API startup timeout')
            yield file_api,owner,tokens,env,root,run,fid
    finally:proc.terminate();proc.wait(timeout=10)


def test_logical_file_actual_http_attachment_scope_and_revoked_cache(file_runtime):
    api,owner,tokens,env,root,run,fid=file_runtime
    r=api.get('/api/files/'+fid,headers=auth(tokens))
    assert r.status_code==200 and r.headers['content-type'].startswith('text/plain')
    assert r.headers['content-disposition'].startswith('attachment;')
    assert "sandbox" in r.headers['content-security-policy'] and r.headers['cache-control']=='no-store'
    assert b'<script>' in r.content and str(root).encode() not in r.content
    before=counts(owner)
    for user in ('fixture-b','fixture-c'):
        assert api.get('/api/files/'+fid,headers=auth(tokens,user)).status_code==403
    user=add_role(owner,tokens,'service_executor');owner.assign_status(user,run)
    assert api.get('/api/files/'+fid,headers=auth(tokens,user)).status_code==403
    assert counts(owner)==before
    owner.revoke_capability('fixture-a','FILE_READ');owner.seed({k:v for k,v in tokens.items() if k.startswith('fixture-')})
    assert api.get('/api/files/'+fid,headers=auth(tokens)).status_code==403
    worker((api,owner,tokens,env))
    assert counts(owner)['file_resources']==1


@pytest.mark.parametrize('bad',['..%5Csecret','C:%5CWindows%5Cwin.ini','%5C%5Cserver%5Cshare','file.txt:secret','..%2Fsecret'])
def test_windows_and_traversal_strings_are_not_file_ids(file_runtime,bad):
    api,owner,tokens,env,root,run,fid=file_runtime;before=counts(owner)
    r=api.get('/api/files/'+bad,headers=auth(tokens))
    assert r.status_code in (422,404) and 'SYNTHETIC ONLY' not in r.text
    assert counts(owner)==before


@pytest.mark.parametrize('attack',['content','symlink','hardlink','directory','root_symlink'])
def test_file_integrity_and_descriptor_boundary(file_runtime,attack):
    api,owner,tokens,env,root,run,fid=file_runtime
    path=root/'files'/(fid+'.txt')
    outside=root.parent/'outside.txt';outside.write_text('HOST_SENTINEL_NEVER_RETURN')
    if attack=='content':path.write_text('HOST_SENTINEL_NEVER_RETURN')
    elif attack=='root_symlink':
        moved=root.with_name('moved');root.rename(moved);root.symlink_to(moved,target_is_directory=True)
    else:
        path.unlink()
        if attack=='symlink':path.symlink_to(outside)
        elif attack=='hardlink':os.link(outside,path)
        elif attack=='directory':path.mkdir()
    r=api.get('/api/files/'+fid,headers=auth(tokens))
    assert r.status_code==403 and 'HOST_SENTINEL' not in r.text and str(root) not in r.text


def test_application_cannot_self_grant_or_register_resource(fixture):
    store,owner,tokens,client=fixture
    for sql in ["UPDATE capability_grants SET active=true","INSERT INTO run_assignments SELECT 'fixture-a',id,'park-a','org-a',true FROM runs",
                "UPDATE file_resources SET sha256='x'"]:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with store.connect() as c:c.execute(sql)


@pytest.mark.skipif(os.name!='nt',reason='NOT_RUN: native Windows reparse points, ADS, ACL and clean lifecycle require Windows11 x64')
def test_native_windows_file_backend_gate():
    pytest.skip('NOT_RUN: descriptor backend intentionally disabled until native Windows backend is verified')


def test_action_grant_and_role_change_cannot_reuse_queued_identity(runtime):
    api,owner,tokens,env=runtime;run=enqueue(runtime,'case.create')
    with owner.connect() as c:
        owner.lock_principal(c,'fixture-a',exclusive=True)
        c.execute("UPDATE action_grants SET active=false WHERE principal_id='fixture-a' AND action='case.create'")
    owner.seed(tokens);worker(runtime)
    assert counts(owner)['cases']==0
    with owner.connect() as c:
        assert c.execute('SELECT state FROM operations WHERE run_id=%s',(run,)).fetchone()['state']=='FAILED_SAFE'
        owner.lock_principal(c,'fixture-a',exclusive=True)
        c.execute("UPDATE principals SET role='service_executor' WHERE id='fixture-a'")
    assert api.get('/api/runs/'+run,headers=auth(tokens)).status_code==403
    owner.assign_status('fixture-a',run)
    r=api.get('/api/runs/'+run,headers=auth(tokens))
    assert r.status_code==200 and r.json()['visibility']=='ASSIGNED_STATUS_ONLY'
    assert 'operation' not in r.json() and 'case' not in r.json()
    with owner.connect() as c:events=c.execute('SELECT event_id FROM deliveries WHERE run_id=%s',(run,)).fetchall()
    for event in events:
        assert api.get('/api/messages/'+str(event['event_id']),headers=auth(tokens)).status_code==403
    worker(runtime)
    with owner.connect() as c:
        assert all(row['state']=='RETRACTED' for row in c.execute('SELECT state FROM deliveries WHERE run_id=%s',(run,)))
    assert api.post('/api/runs',headers=auth(tokens),json={'goal':'x'}).status_code==403


def test_field_delivery_after_withdrawal_retracted(runtime):
    api,owner,tokens,env=runtime
    run=api.post('/api/runs',headers=auth(tokens),json={'goal':'合成','action':'facts.assess','fact_fields':['region']}).json()['run_id']
    worker(runtime)
    with owner.connect() as c:events=c.execute('SELECT event_id FROM deliveries WHERE run_id=%s',(run,)).fetchall()
    assert len(events)==2
    owner.revoke_field('fixture-a','region','READ')
    for event in events:
        assert api.get('/api/messages/'+str(event['event_id']),headers=auth(tokens)).status_code==403
    worker(runtime)
    with owner.connect() as c:
        assert all(r['state']=='RETRACTED' and r['payload']=={} for r in c.execute('SELECT state,payload FROM deliveries WHERE run_id=%s',(run,)))
        assert c.execute("SELECT count(*) n FROM authorization_audit WHERE outcome='RETRACTED'").fetchone()['n']==2


def test_denied_file_authorization_never_opens_backend(fixture,monkeypatch):
    store,owner,tokens,client=fixture
    import parkweave.files
    def forbidden(*args,**kwargs):raise AssertionError('denied request reached file backend')
    monkeypatch.setattr(parkweave.files,'read_text_resource',forbidden)
    assert client.get('/api/files/'+str(uuid.uuid4()),headers=auth(tokens,'fixture-b')).status_code==403
    owner.revoke_capability('fixture-a','FILE_READ')
    assert client.get('/api/files/'+str(uuid.uuid4()),headers=auth(tokens)).status_code==403
    with owner.connect() as c:
        rows=c.execute('SELECT category,outcome FROM authorization_audit').fetchall()
        assert len(rows)==2 and all(r=={'category':'API_AUTHORIZATION','outcome':'DENIED'} for r in rows)


def test_fixture_writer_cannot_follow_configured_root_symlink(fixture,tmp_path):
    if os.name=='nt':pytest.skip('NOT_RUN: native reparse writer backend not verified')
    store,owner,tokens,client=fixture
    outside=tmp_path/'outside';outside.mkdir()
    root=tmp_path/'private';root.symlink_to(outside,target_is_directory=True)
    owner.file_root=root
    from parkweave.domain import Intake
    run=store.submit(tokens['fixture-a'],'safe-root',Intake(goal='合成'))
    with pytest.raises(Denied):owner.register_synthetic_file('fixture-a',run,b'SYNTHETIC')
    assert list(outside.iterdir())==[]
    with owner.connect() as c:assert c.execute('SELECT count(*) n FROM file_resources').fetchone()['n']==0


def test_identity_scope_change_does_not_carry_old_grants(runtime):
    api,owner,tokens,env=runtime;run=enqueue(runtime,'case.create');before=counts(owner)
    with owner.connect() as c:
        owner.lock_principal(c,'fixture-a',exclusive=True)
        c.execute("UPDATE principals SET org_id='org-b' WHERE id='fixture-a'")
    assert api.post('/api/runs',headers=auth(tokens),json={'goal':'x'}).status_code==403
    assert api.get('/api/runs/'+run,headers=auth(tokens)).status_code==403
    assert counts(owner)==before
    worker(runtime)
    assert counts(owner)['cases']==0
    with owner.connect() as c:
        assert c.execute('SELECT state FROM operations WHERE run_id=%s',(run,)).fetchone()['state']=='FAILED_SAFE'



def test_additive_unreleased_grant_scope_migration_preserves_withdrawal(fixture):
    store,owner,tokens,client=fixture
    from parkweave.domain import Intake
    run=store.submit(tokens['fixture-a'],'prototype-history',Intake(goal='合成保留'))
    before=store.read(tokens['fixture-a'],run)
    owner.revoke_capability('fixture-a','EXECUTE')
    # Schema-only initial fixture for the unreleased earlier prototype, no Run state edits.
    with owner.connect() as c:
        c.execute('ALTER TABLE capability_grants DROP COLUMN park_id,DROP COLUMN org_id')
        c.execute('ALTER TABLE action_grants DROP COLUMN park_id,DROP COLUMN org_id')
        c.execute('DELETE FROM schema_version WHERE version>=5')
    owner.migrate();owner.migrate()
    assert store.read(tokens['fixture-a'],run)==before
    with owner.connect() as c:
        grant=c.execute("SELECT active,park_id,org_id FROM capability_grants WHERE principal_id='fixture-a' AND capability='EXECUTE'").fetchone()
        assert grant=={'active':False,'park_id':'park-a','org_id':'org-a'}
        assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']==6
    store.finish(store.claim('current-worker'))
    assert store.read(tokens['fixture-a'],run)['operation']['state']=='FAILED_SAFE'
    assert counts(owner)['cases']==0


@pytest.mark.parametrize('target,mode',[('root',0o777),('files',0o777),('files',0o755)])
def test_insecure_private_directories_rejected_without_repair(file_runtime,target,mode):
    api,owner,tokens,env,root,run,fid=file_runtime
    directory=root if target=='root' else root/'files'
    directory.chmod(mode);before=counts(owner)
    r=api.get('/api/files/'+fid,headers=auth(tokens))
    assert r.status_code==403 and b'SYNTHETIC ONLY' not in r.content
    with pytest.raises(Denied,match='unsafe private directory'):
        owner.register_synthetic_file('fixture-a',run,b'SYNTHETIC NEW')
    assert directory.stat().st_mode&0o777==mode and counts(owner)==before


def test_private_directory_wrong_owner_and_new_minimum_mode(tmp_path,monkeypatch):
    if os.name=='nt':pytest.skip('NOT_RUN: POSIX owner cannot prove Windows ACL')
    from parkweave.files import resource_directory,require_private_directory
    root=tmp_path/'private';root.mkdir(mode=0o700)
    with resource_directory(root,create=True):pass
    assert (root/'files').stat().st_mode&0o777==0o700
    with resource_directory(root) as fd:
        original=os.fstat
        from types import SimpleNamespace
        info=original(fd)
        monkeypatch.setattr(os,'fstat',lambda _:SimpleNamespace(st_mode=info.st_mode,st_uid=os.geteuid()+1))
        with pytest.raises(Denied,match='unsafe private directory'):require_private_directory(fd)
