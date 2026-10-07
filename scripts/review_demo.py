"""Single command review launcher: three owned localhost children, no credentials.

Default candidates disabled. --isolated-mock creates only two candidate SQLite
files in a dedicated local directory. Ctrl-C stops only this launcher's children.
"""
from pathlib import Path
import argparse,json,os,signal,socket,subprocess,sys,time,urllib.request,uuid
from parkweave.process_env import minimal_environment
from scripts.review_demo_factories import NAMESPACE

ROOT=Path(__file__).resolve().parents[1]
OBJECTS={'park_id':'park-a','org_id':'org-a','service_id':'candidate-intake','run_id':'mock-run-a','capability':'READ','max_seconds':28800}
def initialize_state(path):
    path=Path(path)
    if path.is_symlink():raise ValueError('symlink state directory refused')
    resolved=path.resolve()
    if not (resolved.is_relative_to(ROOT/'.runtime') or resolved.is_relative_to(Path('/tmp'))):raise ValueError('dedicated workspace runtime or tmp state directory required')
    marker={'namespace':NAMESPACE,'version':1,'objects':OBJECTS,'actual_permissions_enabled':False};file=resolved/'review-demo.json'
    if resolved.exists():
        if not file.is_file() or file.is_symlink() or json.loads(file.read_text())!=marker:raise ValueError('foreign existing directory refused without changes')
        if any(p.name not in {'review-demo.json','rules.candidate.sqlite3','access.run-access.candidate.sqlite3'} for p in resolved.iterdir()):raise ValueError('unknown state files refused')
    else:
        resolved.mkdir(parents=True);file.write_text(json.dumps(marker,indent=2)+'\n')
    return resolved

def reserve_report(path):
    if path is None:return None
    path=Path(path)
    if path.is_symlink():raise ValueError('symlink report refused')
    resolved=path.resolve()
    if not (resolved.is_relative_to(ROOT/'.runtime') or resolved.is_relative_to(Path('/tmp'))):raise ValueError('dedicated runtime or tmp report required')
    if resolved.exists():
        old=json.loads(resolved.read_text())
        if old.get('namespace')!=NAMESPACE or old.get('artifact_kind')!='OWNED_REVIEW_LAUNCH_REPORT':raise ValueError('foreign report refused without changes')
    else:
        with resolved.open('x') as f:json.dump({'namespace':NAMESPACE,'artifact_kind':'OWNED_REVIEW_LAUNCH_REPORT'},f)
    return resolved

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--isolated-mock',action='store_true');parser.add_argument('--state-dir',type=Path);parser.add_argument('--base-port',type=int,default=8770);parser.add_argument('--check-startup',action='store_true');parser.add_argument('--report',type=Path);a=parser.parse_args(argv)
    if not 1024<=a.base_port<=65533:parser.error('base port must be 1024..65533')
    if a.state_dir and not a.isolated_mock:parser.error('state directory requires explicit --isolated-mock')
    try:a.report=reserve_report(a.report)
    except (OSError,ValueError,AttributeError):parser.error('report destination refused; foreign files preserved')
    instance=uuid.uuid4().hex;runtime=ROOT/'.runtime'/('review-launch-'+instance[:12]);runtime.mkdir(parents=True)
    state=initialize_state(a.state_dir or runtime/'state') if a.isolated_mock else None
    status={'artifact_kind':'OWNED_REVIEW_LAUNCH_REPORT','instance_id':instance,'namespace':NAMESPACE,'url':f'http://127.0.0.1:{a.base_port}/','isolated_mock_enabled':a.isolated_mock,'state_dir':str(state) if state else None,'current_product_database_connected':False,'credentials_created':False,'actual_permissions_enabled':False,'actual_assignment_written':False,'ready':False,'owned_children':[]}
    overrides={'PYTHONPATH':str(ROOT/'src')+':'+str(ROOT),'PARKWEAVE_REVIEW_EVIDENCE_ROOT':str(ROOT),'PARKWEAVE_REVIEW_INSTANCE':instance,'PARKWEAVE_REVIEW_BASE_PORT':str(a.base_port)}
    if state:overrides.update(PARKWEAVE_REVIEW_STATE=str(state),PARKWEAVE_REVIEW_MODE=NAMESPACE)
    env=minimal_environment(os.environ,**overrides);children=[];logs=[]
    def report():
        if a.report:a.report.write_text(json.dumps(status,indent=2)+'\n')
    previous=signal.signal(signal.SIGTERM,lambda signum,frame:(_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        # A busy port is a blocker, never grounds to stop somebody else's process.
        for port in range(a.base_port,a.base_port+3):
            with socket.socket() as s:
                s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',port))
        for offset,kind in enumerate(('hub','rules','access')):
            log=(runtime/(kind+'.log')).open('w');logs.append(log)
            child=subprocess.Popen([sys.executable,'-m','uvicorn','scripts.review_demo_factories:'+kind+'_app','--factory','--host','127.0.0.1','--port',str(a.base_port+offset)],cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=True);children.append(child);status['owned_children'].append({'kind':kind,'pid':child.pid})
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if any(p.poll() is not None for p in children):raise RuntimeError('OWNED_CHILD_EXITED')
            ready=[]
            for offset,kind in enumerate(('hub','rules','access')):
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{a.base_port+offset}/__review_health',timeout=.3) as r:info=json.load(r)
                    ready.append(info=={'instance_id':instance,'kind':kind,'isolated_mock_enabled':a.isolated_mock})
                except (OSError,ValueError):ready.append(False)
            if all(ready):break
            time.sleep(.1)
        else:raise RuntimeError('LOCAL_READY_TIMEOUT')
        status['ready']=True;report();print(json.dumps(status),flush=True)
        if not a.check_startup:
            while True:
                if any(p.poll() is not None for p in children):raise RuntimeError('OWNED_CHILD_EXITED')
                time.sleep(.25)
    except KeyboardInterrupt:status['stopped']='OWNED_CHILDREN_ONLY'
    except Exception as e:status['failure']=str(e) if isinstance(e,RuntimeError) else type(e).__name__
    finally:
        for child in children:
            if child.poll() is None:child.terminate()
        status['cleanup']=[]
        for child in children:
            try:status['cleanup'].append(child.wait(timeout=5))
            except subprocess.TimeoutExpired:child.kill();status['cleanup'].append(child.wait(timeout=5))
        for log in logs:log.close()
        report();signal.signal(signal.SIGTERM,previous)
    return 1 if 'failure' in status else 0

if __name__=='__main__':raise SystemExit(main())
