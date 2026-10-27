"""Owned PG + real ordinary processes; no CaseStep fixture issuer or installer."""
from contextlib import contextmanager
from pathlib import Path
import json,os,socket,subprocess,sys,time
import httpx
from parkweave.process_env import minimal_environment
from scripts.linux_fixture_server import stop_children

ROOT=Path(__file__).resolve().parents[1]
MODE='CURRENT_PREPARATION'

def environment(f):
    return minimal_environment(os.environ,PYTHONPATH=str(ROOT/'src'),PARKWEAVE_DSN=f[0].dsn,
        PARKWEAVE_MODE='LOCAL',PARKWEAVE_CASE_STEP_MODE=MODE,PYTHONDONTWRITEBYTECODE='1')

def worker_once(f,directory):
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'worker.stdout').open('w') as out,(directory/'worker.stderr').open('w') as err:
        result=subprocess.run([sys.executable,'-B','-m','parkweave.worker','--once'],cwd=ROOT,
            env=environment(f),stdout=out,stderr=err,timeout=30)
    (directory/'worker-result.json').write_text(json.dumps(dict(exit_code=result.returncode,ordinary_worker=True))+'\n')
    assert result.returncode==0,(directory/'worker.stderr').read_text()

@contextmanager
def ordinary_api(f,directory,port=None):
    directory.mkdir(parents=True,exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',port or 0));port=sock.getsockname()[1]
    with (directory/'api.log').open('w') as log:
        child=subprocess.Popen([sys.executable,'-B','-m','uvicorn','parkweave.api:configured_app',
            '--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log'],
            cwd=ROOT,env=environment(f),stdout=log,stderr=subprocess.STDOUT)
        observations=[]
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=15) as api:
                for _ in range(150):
                    assert child.poll() is None,'ordinary API exited; see api.log'
                    try:
                        r=api.get('/health');pid=r.json().get('process_id')
                        if r.status_code==200 and pid==child.pid:break
                    except httpx.TransportError:pass
                    time.sleep(.1)
                else:raise AssertionError('owned ordinary API startup exceeded 15 seconds')
                observations.append(dict(api_pid=child.pid,health_pid=pid,ordinary_factory=True,port=port))
                yield api
        finally:
            stop_children([child]);observations.append(dict(owned_child_exit=child.poll()))
            (directory/'process.json').write_text(json.dumps(observations,indent=2)+'\n')
