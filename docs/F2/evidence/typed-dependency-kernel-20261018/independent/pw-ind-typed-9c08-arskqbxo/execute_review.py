from pathlib import Path
import os,sys,json,hashlib,time,subprocess
base=Path(__file__).resolve().parent;mirror=base/'mirror';os.chdir(mirror)
sys.path[:0]=[str(mirror/'src'),str(mirror/'tests'),str(mirror)]
import pytest
reports=[];fixtures=[];module_records=[]
class Observer:
    def pytest_fixture_setup(self,fixturedef,request):
        fixtures.append(fixturedef.argname)
        if fixturedef.argname in {'pg','fixture','link_fixture','typed_http','http_f','receipt_fixture','preparation_fixture'}:
            pytest.fail('independent pure-computation review refuses database/HTTP fixture')
    def pytest_runtest_logreport(self,report):
        reports.append(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration))
start=time.perf_counter()
args=['-q','-p','no:cacheprovider','--junitxml='+str(base/'independent.xml'),str(base/'test_independent_literal_graph.py')]
code=pytest.main(args,plugins=[Observer()]);elapsed=time.perf_counter()-start
before=json.loads((base/'input-before.json').read_text())
post={k:hashlib.sha256((mirror/k).read_bytes()).hexdigest() if (mirror/k).is_file() else None for k in before}
shared={k:hashlib.sha256((Path('/workspace/ParkWeave')/k).read_bytes()).hexdigest() if (Path('/workspace/ParkWeave')/k).is_file() else None for k in before}
(base/'input-after.json').write_text(json.dumps(post,sort_keys=True,indent=2)+'\n')
(base/'shared-input-after.json').write_text(json.dumps(shared,sort_keys=True,indent=2)+'\n')
for name,module in sorted(sys.modules.items()):
    f=getattr(module,'__file__',None)
    if f:
        path=Path(f).resolve()
        try:rel=str(path.relative_to(mirror))
        except ValueError:continue
        if path.is_file():module_records.append(dict(name=name,file=str(path),relative=rel,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),matches_frozen=before.get(rel)==hashlib.sha256(path.read_bytes()).hexdigest()))
(base/'module-origins.json').write_text(json.dumps(module_records,sort_keys=True,indent=2)+'\n')
summary=dict(exit_code=int(code),source_sha='9c08f07677c7c29e20d322fa1b55f97af2c41e0e',pytest_args=args,pytest_seconds=elapsed,reports=reports,fixtures=sorted(set(fixtures)),selected_inputs=len(before),mirror_drift=[k for k in before if before[k]!=post[k]],shared_drift=[k for k in before if before[k]!=shared[k]],oracle_sha256=hashlib.sha256((base/'test_independent_literal_graph.py').read_bytes()).hexdigest(),local_modules=len(module_records))
(base/'result.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
raise SystemExit(int(code))
