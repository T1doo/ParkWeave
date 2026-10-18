from pathlib import Path
import hashlib,json,os,sys
import pytest
r=Path(os.environ['PW_COLLABORATION_EVIDENCE']);mirror=Path.cwd().resolve();freeze=json.loads((r/'verified-freeze.json').read_text())
class Evidence:
    def __init__(self):self.nodes=[];self.phases=[]
    def pytest_collection_finish(self,session):
        self.nodes=[item.nodeid for item in session.items];(r/'verified-collected-nodeids.json').write_text(json.dumps(self.nodes,indent=2)+'\n');assert self.nodes==freeze['nodes']
    def pytest_runtest_logreport(self,report):self.phases.append(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration))
    def pytest_sessionfinish(self,session,exitstatus):
        origins={}
        for name,module in sorted(sys.modules.items()):
            if name=='parkweave' or name.startswith('parkweave.'):
                path=getattr(module,'__file__',None)
                if path:
                    target=Path(path).resolve();origins[name]=dict(file=str(target),inside_mirror_src=target.is_relative_to(mirror/'src'),sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        (r/'verified-module-origins.json').write_text(json.dumps(origins,indent=2)+'\n');(r/'verified-phase-reports.json').write_text(json.dumps(self.phases,indent=2)+'\n');(r/'verified-observer-settlement.json').write_text(json.dumps(dict(exitstatus=int(exitstatus),process_id=os.getpid(),nodes=len(self.nodes),modules=len(origins),all_origins_mirror_src=all(row['inside_mirror_src'] for row in origins.values()),scope='pytest only; ordinary child API not additionally origin-instrumented'),indent=2)+'\n')
raise SystemExit(int(pytest.main(sys.argv[1:],plugins=[Evidence()])))
