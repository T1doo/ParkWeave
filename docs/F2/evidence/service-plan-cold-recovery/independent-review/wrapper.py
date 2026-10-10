import sys,json,time
from pathlib import Path
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/independent-service-plan-cold-recovery-complete-review';sys.path.insert(0,str(ROOT/'tests'));sys.path.insert(0,str(ROOT));import pytest
class Progress:
 def __init__(self):self.records=[];self.start=time.monotonic()
 def pytest_collection_finish(self,session):
  for item in session.items:
   m=item.module
   if hasattr(m,'OUT') and isinstance(m.OUT,Path):m.OUT=OUT/'browser'/m.__name__
 def pytest_runtest_logreport(self,report):
  r=report
  if r.when=='call' or r.failed or r.skipped:
   self.records.append(dict(nodeid=r.nodeid,when=r.when,outcome=r.outcome,duration=r.duration));(OUT/(sys.argv[1]+'-progress.json')).write_text(json.dumps(dict(elapsed=time.monotonic()-self.start,records=self.records),indent=2)+'\n')
raise SystemExit(pytest.main(sys.argv[2:],plugins=[Progress()]))
