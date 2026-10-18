from pathlib import Path
import hashlib,json,os,sys
import pytest
record=Path(os.environ['PW_REVIEW_EVIDENCE']);mirror=Path.cwd().resolve()
expected=set(json.loads((record/'expected-4-nodes.json').read_text()))
class Evidence:
    def __init__(self):self.collected=[];self.reports=[]
    def pytest_collection_finish(self,session):
        self.collected=[item.nodeid for item in session.items]
        (record/'actual-collected-nodeids.json').write_text(json.dumps(self.collected,indent=2)+'\n')
        assert len(self.collected)==4 and set(self.collected)==expected,'independent collection differs from authorized 4'
    def pytest_runtest_logreport(self,report):
        self.reports.append(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration))
    def pytest_sessionfinish(self,session,exitstatus):
        origins={}
        for name,module in sorted(sys.modules.items()):
            if name=='parkweave' or name.startswith('parkweave.'):
                path=getattr(module,'__file__',None)
                if path:
                    target=Path(path).resolve()
                    origins[name]=dict(file=str(target),inside_mirror_src=target.is_relative_to(mirror/'src'),sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        (record/'actual-pytest-module-origins.json').write_text(json.dumps(origins,indent=2)+'\n')
        (record/'actual-phase-reports.json').write_text(json.dumps(self.reports,indent=2)+'\n')
        (record/'observer-settlement.json').write_text(json.dumps(dict(pytest_exitstatus=int(exitstatus),process_id=os.getpid(),collected=len(self.collected),parkweave_modules=len(origins),all_origins_mirror_src=all(x['inside_mirror_src'] for x in origins.values()),resident_observer=False,scope='in-process pytest observation only; child API/Node/worker not additionally origin-instrumented'),indent=2)+'\n')
raise SystemExit(int(pytest.main(sys.argv[1:],plugins=[Evidence()])))
