from pathlib import Path
import hashlib,json,os,sys
import pytest
D=Path(os.environ['PW_AT21_EVIDENCE']);label=os.environ['PW_AT21_WINDOW'];mirror=Path.cwd().resolve();freeze=json.loads((D/(label+'-freeze.json')).read_text())
class Evidence:
    def __init__(self):self.nodes=[];self.phases=[]
    def pytest_collection_finish(self,session):
        self.nodes=[i.nodeid for i in session.items];(D/(label+'-actual-nodeids.json')).write_text(json.dumps(self.nodes,indent=2)+'\n');assert self.nodes==freeze['nodes']
    def pytest_runtest_logreport(self,report):
        self.phases.append(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration));(D/(label+'-phases.json')).write_text(json.dumps(self.phases,indent=2)+'\n')
    def pytest_sessionfinish(self,session,exitstatus):
        origins={}
        for name,m in sorted(sys.modules.items()):
            if name=='parkweave' or name.startswith('parkweave.'):
                p=getattr(m,'__file__',None)
                if p:
                    p=Path(p).resolve();origins[name]=dict(path=str(p),inside_mirror_src=p.is_relative_to(mirror/'src'),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        (D/(label+'-module-origins.json')).write_text(json.dumps(origins,indent=2)+'\n');(D/(label+'-observer-settlement.json')).write_text(json.dumps(dict(pytest_exit=int(exitstatus),process_id=os.getpid(),actual_modules=len(origins),all_origins_mirror_src=all(x['inside_mirror_src'] for x in origins.values()),scope='pytest process only; Node executes original mirror HTML; no child Python business API'),indent=2)+'\n')
raise SystemExit(int(pytest.main(sys.argv[1:],plugins=[Evidence()])))
