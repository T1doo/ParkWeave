"""Private harness entry: installed package only, no source/PYTHONPATH fallback."""
from hashlib import sha256
from contextlib import contextmanager
import json,os,signal,subprocess,sys,time
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))  # Trusted copied harness only; contains no parkweave.
MANIFEST=json.loads((HERE/'manifest.json').read_text())
VERIFYING=False
OPENED=set()
def audit(event,args):
    if event=='open' and not VERIFYING and args and isinstance(args[0],(str,bytes)):
        path=Path(os.fsdecode(args[0])).absolute()
        package=Path(MANIFEST['purelib'])/'parkweave'
        if path.is_relative_to(package) and path.suffix in ('.sql','.html','.json'):
            OPENED.add(path.relative_to(package).as_posix());assert len(OPENED)<=256
sys.addaudithook(audit)


def _attest(role,stage):
    import parkweave,parkweave.store,parkweave.api,parkweave.local_resource_approval
    expected=MANIFEST
    assert sys.flags.isolated and sys.prefix==expected['prefix'] and 'PYTHONPATH' not in os.environ
    assert not (HERE/'parkweave').exists() and not list((HERE/'src').iterdir())
    assert all(str(Path(p).resolve()) not in expected['forbidden_roots'] for p in sys.path if p)
    pure=Path(expected['purelib']);package=pure/'parkweave'
    assert sha256(Path(__file__).read_bytes()).hexdigest()==expected['entrypoint_sha256']
    for name,digest in expected['harness_scripts'].items():
        assert sha256((HERE/'scripts'/name).read_bytes()).hexdigest()==digest
    assert not list(pure.glob('*.pth')) and not list(pure.glob('*.egg-link'))
    assert Path(parkweave.__file__).resolve()==package/'__init__.py'
    for name,digest in expected['package_files'].items():
        path=pure/name
        assert path.is_file() and not path.is_symlink() and path.resolve()==path
        assert sha256(path.read_bytes()).hexdigest()==digest
    actual={p.relative_to(pure).as_posix() for p in package.rglob('*') if p.is_file()}
    assert actual==set(expected['package_files'])
    loaded={}
    for name,module in sys.modules.copy().items():
        if name=='parkweave' or name.startswith('parkweave.'):
            path=Path(module.__file__).resolve();assert path.is_relative_to(package)
            loaded[name]=path.relative_to(pure).as_posix()
    result=dict(role=role,stage=stage,pid=os.getpid(),executable=sys.executable,prefix=sys.prefix,isolated=True,
        PYTHONPATH=False,cwd=str(Path.cwd()),package_root=str(package),wheel_sha256=expected['wheel_sha256'],
        verified_package_files=len(actual),actual_opened_package_resources=sorted(OPENED),package_manifest_sha256=sha256(json.dumps(expected['package_files'],sort_keys=True).encode()).hexdigest(),loaded_modules=loaded)
    path=HERE/(role+'-attestation.json');items=json.loads(path.read_text()) if path.exists() else []
    items.append(result);path.write_text(json.dumps(items,indent=2)+'\n')


def attest(role,stage):
    global VERIFYING
    VERIFYING=True
    try:_attest(role,stage)
    finally:VERIFYING=False


def setup():
    from scripts import ordinary_synthetic_demo as demo
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    observation=dict(children=[],creation={},cleanup_errors=[]);primary=None
    original=demo.lifecycle.postgres
    @contextmanager
    def observed(state):
        observation['state_dir']=str(state)
        with original(state,observation=observation) as pg:yield pg
    demo.lifecycle.postgres=observed
    try:
        attest('setup','BEFORE_SCHEMA')
        state=demo.setup(with_local_catalog=True,with_local_resource_approval=True)
        attest('setup','AFTER_SCHEMA')
        print(json.dumps(dict(state_dir=str(state),local_demo_config=str(state/'local-demo/config.json'))),flush=True)
    except BaseException as error:
        primary=error;observation['primary_error']=dict(error_type=type(error).__name__,errno=getattr(error,'errno',None));raise
    finally:
        demo.lifecycle.postgres=original
        try:
            state=demo._last_owned_state
            observation['state_dir']=str(state) if state is not None else None
            observation['postgres_marker_absent']=state is not None and not (state/'data/postmaster.pid').exists()
            (HERE/'setup-owned-processes.json').write_text(json.dumps(observation,indent=2)+'\n')
        except BaseException as cleanup:
            if primary is not None:raise BaseExceptionGroup('Installed setup primary and evidence errors',[primary,cleanup]) from None
            raise


def api():
    import uvicorn
    from parkweave.api import configured_app
    app=configured_app();attest('api','BEFORE_SERVE')
    # Uvicorn restores and re-raises captured SIGTERM after its graceful shutdown.
    # Retain that shutdown, then allow our owned process to write final provenance.
    signal.signal(signal.SIGTERM,lambda *_:None)
    try:uvicorn.run(app,host='127.0.0.1',port=int(sys.argv[2]),access_log=False,log_level='warning')
    finally:attest('api','AFTER_SERVE')


def worker():
    from parkweave.worker import main
    role=sys.argv[2];sys.argv=['parkweave.worker','--once'];attest(role,'BEFORE_WORK')
    try:main()
    finally:attest(role,'AFTER_WORK')


def serve():
    from scripts import ordinary_synthetic_demo as demo
    from parkweave.process_env import minimal_environment
    import urllib.request
    state=Path(sys.argv[2]);port=int(sys.argv[3]);observation=dict(children=[],creation={},cleanup_errors=[])
    child=None;readiness_attempts=0;primary=None;cleanup=[]
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        with demo.locked(state),demo.lifecycle.postgres(state,observation=observation) as pg:
            env=minimal_environment(os.environ,PYTHONDONTWRITEBYTECODE='1',PARKWEAVE_DSN=demo.lifecycle.dsn(state,application=True),
                PARKWEAVE_MODE='LOCAL',PARKWEAVE_CASE_STEP_MODE='LOCAL_DEMO_CURRENT_PREPARATION',
                PARKWEAVE_SERVICE_PROFILE='LOCAL_SYNTHETIC_DEMO',PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG=demo.existing_local_demo_config(str(state/'local-demo/config.json')),
                PARKWEAVE_LOCAL_RESOURCE_APPROVAL_MODE='CURRENT_OWNER')
            assert 'PYTHONPATH' not in env
            (HERE/'application-env.json').write_text(json.dumps(env))  # Private only; contains owned local DSN.
            with (state/'logs/installed-api.log').open('a') as log:
                try:
                    child=subprocess.Popen([sys.executable,'-I','-B',str(HERE/'entry.py'),'api',str(port)],cwd=HERE,env=env,stdout=log,stderr=log)
                    observation['children'].append(dict(role='api',pid=child.pid,exit_code=None))
                    deadline=time.monotonic()+20
                    while time.monotonic()<deadline:
                        assert readiness_attempts<40,'installed API readiness request40 exhausted'
                        assert child.poll() is None,'installed API exited before readiness'
                        try:
                            readiness_attempts+=1
                            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=.3) as response:health=json.load(response)
                            if health['process_id']==child.pid:break
                        except OSError:pass
                        time.sleep(.1)
                    else:raise TimeoutError('installed API readiness exhausted20s')
                    print(json.dumps(dict(url=f'http://127.0.0.1:{port}',api_pid=child.pid,postgres_pid=pg.pid,state_dir=str(state),readiness_attempts=readiness_attempts)),flush=True)
                    while child.poll() is None:time.sleep(.1)
                    raise RuntimeError('installed API stopped unexpectedly')
                finally:
                    if child is not None:
                        try:demo.stop_children([child])
                        except BaseException as error:
                            cleanup.append(error);observation['cleanup_errors'].append(dict(stage='API_STOP',error_type=type(error).__name__,errno=getattr(error,'errno',None)))
                        observation['children'][-1]['exit_code']=child.poll()
    except KeyboardInterrupt:pass
    except BaseException as error:
        primary=error
        observation['primary_error']=dict(stage='SERVE',error_type=type(error).__name__,errno=getattr(error,'errno',None))
    finally:
        observation['readiness_attempts']=readiness_attempts
        observation['postgres_marker_absent']=not (state/'data/postmaster.pid').exists()
        (HERE/'owned-processes.json').write_text(json.dumps(observation,indent=2)+'\n')
    if not observation['postgres_marker_absent'] or any(x['exit_code'] is None for x in observation['children']):
        cleanup.append(RuntimeError('Owned process cleanup not confirmed'))
    if cleanup:raise BaseExceptionGroup('Installed service and cleanup errors',([primary] if primary is not None else [])+cleanup) from None
    if primary is not None:raise primary


if __name__=='__main__':
    {'setup':setup,'api':api,'worker':worker,'serve':serve}[sys.argv[1]]()
