from pathlib import Path
import sys,os,json,hashlib,time,atexit
base=Path(__file__).resolve().parent;mirror=base/'mirror';os.chdir(mirror)
sys.path[:0]=[str(mirror/'src'),str(mirror/'tests'),str(mirror)]
import pytest,pgserver
reports=[];fixtures=[];collected=[];servers=[];token_values=set()
original_server=pgserver.get_server

def own_server(*args,**kwargs):
    server=original_server(*args,**kwargs);data=Path(args[0] if args else kwargs['data_dir']).resolve();pidfile=data/'postmaster.pid'
    row=dict(data=str(data),pid=int(pidfile.read_text().splitlines()[0]) if pidfile.exists() else None)
    servers.append(row);return server
pgserver.get_server=own_server

def save_before_cleanup():
    for row in servers:
        path=Path('/proc')/str(row['pid'])/'stat'
        row['state_before_process_exit']=path.read_text().rsplit(')',1)[1].strip().split()[0] if path.exists() else 'EXITED'
        row['data_exists_before_process_exit']=Path(row['data']).exists()
    (base/'owned-pg-before-exit.json').write_text(json.dumps(servers,sort_keys=True,indent=2)+'\n')

class Observer:
    def pytest_collection_modifyitems(self,items):
        collected.extend(dict(nodeid=i.nodeid,path=str(i.path),name=i.name) for i in items)
    @pytest.hookimpl(hookwrapper=True)
    def pytest_fixture_setup(self,fixturedef,request):
        fixtures.append(fixturedef.argname);outcome=yield
        if outcome.excinfo is None:
            value=outcome.get_result()
            if fixturedef.argname in {'fixture','link_fixture','http_f'} and isinstance(value,tuple) and len(value)>2 and isinstance(value[2],dict):
                token_values.update(v for v in value[2].values() if isinstance(v,str))
    def pytest_runtest_logreport(self,report):
        reports.append(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration))

args=['-q','-c',str(mirror/'pyproject.toml'),'--rootdir='+str(mirror),'-p','no:cacheprovider','tests/test_independent_resource_members.py','tests/test_resource_query_graph.py','tests/test_resource_query_members_api.py','--basetemp='+os.environ['PARKWEAVE_INDEPENDENT_BASETEMP'],'--junitxml='+str(base/'results.xml')]
start=time.perf_counter();code=pytest.main(args,plugins=[Observer()]);elapsed=time.perf_counter()-start
atexit.register(save_before_cleanup)
private=base/'fixture-token-values.private.json';fd=os.open(private,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:json.dump(sorted(token_values),f)
before=json.loads((base/'input-before.json').read_text());shared_before=json.loads((base/'shared-input-before.json').read_text())
post={k:hashlib.sha256((mirror/k).read_bytes()).hexdigest() for k in before};shared={k:hashlib.sha256((Path('/workspace/ParkWeave')/k).read_bytes()).hexdigest() for k in before}
(base/'input-after.json').write_text(json.dumps(post,sort_keys=True,indent=2)+'\n');(base/'shared-input-after.json').write_text(json.dumps(shared,sort_keys=True,indent=2)+'\n')
modules=[]
for name,module in sorted(sys.modules.items()):
    file=getattr(module,'__file__',None)
    if file and (name=='parkweave' or name.startswith('parkweave.') or name.startswith('test_') or name=='owned_connection_diagnostics'):
        p=Path(file).resolve();rel=str(p.relative_to(mirror)) if p.is_relative_to(mirror) else None
        modules.append(dict(name=name,file=str(p),relative=rel,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),within_mirror=rel is not None,matches_frozen=rel is not None and before.get(rel)==hashlib.sha256(p.read_bytes()).hexdigest(),independent_oracle_file=p==mirror/'tests/test_independent_resource_members.py'))
(base/'module-origins.json').write_text(json.dumps(modules,sort_keys=True,indent=2)+'\n')
result=dict(source_sha='09ea99212b8ddcc70797ec7ac2bfc1909d574a18',exit_code=int(code),pytest_args=args,pytest_main_seconds=elapsed,reports=reports,collected=collected,fixtures=sorted(set(fixtures)),selected_inputs=len(before),mirror_drift=[k for k in before if before[k]!=post[k]],shared_drift=[k for k in shared_before if shared_before[k]!=shared[k]],shared_post_mismatch=[k for k in before if before[k]!=shared[k]],owned_pg=servers,private_fixture_token_values_captured=len(token_values))
(base/'result.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');raise SystemExit(int(code))
