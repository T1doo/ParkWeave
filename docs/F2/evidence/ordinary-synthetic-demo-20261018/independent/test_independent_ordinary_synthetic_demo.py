"""Three contract-first probes, only freshly launcher-owned SYNTHETIC state."""
from pathlib import Path
from hashlib import sha256
import fcntl,json,os,shutil,subprocess,sys,tempfile
import pytest
from scripts import ordinary_synthetic_demo as demo
from parkweave.store import Store,Denied
from parkweave.process_env import minimal_environment
from test_ordinary_synthetic_demo import demo_state,port,ROOT


def evidence(name,value):
    directory=Path(os.environ['PARKWEAVE_INDEPENDENT_DEMO_EVIDENCE']);directory.mkdir(parents=True,exist_ok=True)
    (directory/(name+'.json')).write_text(json.dumps(value,indent=2,sort_keys=True,default=str)+'\n')


def test_gitless_binding_includes_lifecycle_helpers_and_private_sessions(demo_state,tmp_path):
    state,marker,tokens=demo_state
    assert not (ROOT/'.git').exists()
    assert state.stat().st_mode&0o077==0
    for name in ('state.json','sessions.json','creation-observation.json','entry.lock'):
        assert (state/name).is_file() and (state/name).stat().st_mode&0o077==0
    source=demo.source_binding();assert source==marker['source']
    assert {'scripts/ordinary_synthetic_demo.py','scripts/material_only_demo.py','scripts/linux_fixture_server.py'}<=set(source['files'])
    assert marker['sessions_sha256']==sha256((state/'sessions.json').read_bytes()).hexdigest()
    setup_output=(tmp_path/'setup.stdout').read_text()+(tmp_path/'setup.stderr').read_text()
    assert all(value not in setup_output for value in tokens.values()) and 'dbname=' not in setup_output and 'PARKWEAVE_DSN' not in setup_output
    copy=tmp_path/'gitless-source-copy';copy.mkdir();shutil.copytree(ROOT/'src',copy/'src',ignore=shutil.ignore_patterns('__pycache__'))
    (copy/'scripts').mkdir()
    for name in ('ordinary_synthetic_demo.py','material_only_demo.py','linux_fixture_server.py'):shutil.copyfile(ROOT/'scripts'/name,copy/'scripts'/name)
    (copy/'docs').mkdir();(copy/'docs/unrelated.md').write_text('SYNTHETIC independent documentation difference\n')
    env=minimal_environment(os.environ,PYTHONPATH=str(copy/'src')+os.pathsep+str(copy),PYTHONDONTWRITEBYTECODE='1')
    diagnostic="""import json
from pathlib import Path
from scripts import ordinary_synthetic_demo as d
from parkweave import store
binding=d.source_binding()
print(json.dumps(dict(source_sha256=binding['sha256'],files=len(binding['files']),origins={name:dict(path=str(Path(module.__file__).resolve())) for name,module in [('demo',d),('lifecycle',d.lifecycle),('store',store)]})))
"""
    result=subprocess.run([sys.executable,'-B','-c',diagnostic],cwd=copy,env=env,text=True,capture_output=True,timeout=15)
    assert result.returncode==0,result.stderr
    observed=json.loads(result.stdout);assert observed['source_sha256']==source['sha256']
    assert all(Path(row['path']).is_relative_to(copy) for row in observed['origins'].values())
    helper=copy/'scripts/material_only_demo.py';original=helper.read_bytes();helper.write_bytes(original+b'\n# SYNTHETIC independent source-binding negative.\n')
    guarded="""import json,sys
from scripts import ordinary_synthetic_demo as d
from parkweave.store import Denied
def forbidden(*args,**kwargs):raise AssertionError('postgres must not start after source drift')
d.lifecycle.postgres=forbidden
try:d.serve(sys.argv[1],int(sys.argv[2]))
except Denied:print(json.dumps(dict(denied=True,postgres_started=False)))
else:raise AssertionError('changed lifecycle source was accepted')
"""
    before=(state/'state.json').read_bytes()
    denied=subprocess.run([sys.executable,'-B','-c',guarded,str(state),str(port())],cwd=copy,env=env,text=True,capture_output=True,timeout=15)
    assert denied.returncode==0,denied.stderr
    assert json.loads(denied.stdout)==dict(denied=True,postgres_started=False)
    assert (state/'state.json').read_bytes()==before and not (state/'data/postmaster.pid').exists()
    # This controlled file-mode fault is not repaired by the server.
    os.chmod(state/'sessions.json',0o644)
    with pytest.raises(Denied):demo.serve(state,port())
    assert (state/'sessions.json').stat().st_mode&0o077 and (state/'state.json').read_bytes()==before
    evidence('gitless-source-and-sessions',dict(git_present=False,original_binding=source['sha256'],copy_binding=observed['source_sha256'],private_copy_origins=observed['origins'],copied_helper_original_sha256=sha256(original).hexdigest(),copied_helper_changed_sha256=sha256(helper.read_bytes()).hexdigest(),source_change_denied_before_postgres=True,sessions_nonprivate_denied_without_repair=True,initial_sessions_hash_bound=True,stdout_contains_no_tokens_or_dsn=True,frozen_source_unchanged=True))


def test_lock_unknown_postmaster_and_material_prefix_are_never_adopted(demo_state,monkeypatch):
    state,marker,_=demo_state;before=(state/'state.json').read_bytes();attempts=[]
    def forbidden(*args,**kwargs):attempts.append(args);raise AssertionError('no process may start for rejected state')
    with monkeypatch.context() as patch:
        patch.setattr(demo.lifecycle.subprocess,'Popen',forbidden)
        inode=(state/'entry.lock').stat().st_ino
        with (state/'entry.lock').open('r+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with pytest.raises(BlockingIOError):demo.serve(state,port())
        assert (state/'entry.lock').stat().st_ino==inode
        unknown=state/'data/postmaster.pid';raw=b'2147483647\nSYNTHETIC_OWNED_TEST_UNKNOWN_MARKER\n'
        fd=os.open(unknown,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as file:file.write(raw)
        with pytest.raises(Denied):demo.serve(state,port())
        assert unknown.read_bytes()==raw
        old_prefix=Path(tempfile.mkdtemp(prefix=demo.lifecycle.PREFIX,dir='/tmp'))
        with pytest.raises(Denied):demo.serve(old_prefix,port())
        assert old_prefix.is_dir() and list(old_prefix.iterdir())==[]
    assert not attempts and (state/'state.json').read_bytes()==before
    evidence('unknown-state-not-adopted',dict(held_lock_denied=True,lock_inode_preserved=True,unknown_postmaster_marker_retained=True,unknown_marker_sha256=sha256(raw).hexdigest(),process_creation_attempts=0,old_material_prefix_stub=str(old_prefix),old_material_setup_executed=False,old_material_database_created=False,state_marker_unchanged=True))


def test_actual_app_role_membership_drift_refuses_serve_and_is_not_repaired(demo_state,monkeypatch):
    state,marker,_=demo_state;before=(state/'state.json').read_bytes();sessions=sha256((state/'sessions.json').read_bytes()).hexdigest()
    # Negative administration only inside this test's new owned cluster.
    with demo.lifecycle.postgres(state):
        with Store(demo.lifecycle.dsn(state)).connect() as c:
            assert demo.authority(c)==marker['authority']
            c.execute('GRANT pg_read_all_data TO parkweave_app')
    original=demo.subprocess.Popen;children=[];business_children=[]
    def observe(args,**kwargs):
        if 'uvicorn' in args or 'parkweave.worker' in args:
            business_children.append(args);raise AssertionError('API/worker must not start with role drift')
        child=original(args,**kwargs);children.append(child);return child
    with monkeypatch.context() as patch:
        patch.setattr(demo.subprocess,'Popen',observe)
        with pytest.raises(Denied):demo.serve(state,port())
    assert len(children)==1 and all(child.poll() is not None for child in children) and not business_children
    assert not (state/'data/postmaster.pid').exists()
    assert (state/'state.json').read_bytes()==before and sha256((state/'sessions.json').read_bytes()).hexdigest()==sessions
    with demo.lifecycle.postgres(state):
        with Store(demo.lifecycle.dsn(state)).connect() as c:
            c.execute('SET TRANSACTION READ ONLY')
            assert c.execute("SELECT pg_has_role('parkweave_app','pg_read_all_data','MEMBER') member").fetchone()['member'] is True
            with pytest.raises(Denied):demo.authority(c)
            assert not c.execute('SELECT 1 FROM runs').fetchone() and not c.execute('SELECT 1 FROM run_assignments').fetchone()
    evidence('sql-role-drift',dict(scope='FRESH_OWNED_SYNTHETIC_NEGATIVE_ONLY',membership='pg_read_all_data',serve_denied=True,api_worker_spawn_attempts=0,stopped_exact_owned_validation_postgres=[child.pid for child in children],membership_not_repaired=True,source_state_sessions_unchanged=True,business_records=0,run_assignments=0))
