import sys,json,time
from pathlib import Path
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/independent-p3-dispatch-execution-preview-review';sys.path.insert(0,str(ROOT/'tests'));sys.path.insert(0,str(ROOT));import test_material_objections_browser as original_objection
original_objection.OUT=OUT/"browser"/"original-objections-private"
import pytest
class Progress:
 def __init__(self):
  self.records=[];self.start=time.monotonic();self.window=next(Path(a.split('=',1)[1]).name.removesuffix('-junit.xml') for a in sys.argv if a.startswith('--junitxml='));self.progress_path=OUT/(self.window+'-progress.json')
 def pytest_collection_finish(self,session):
  for item in session.items:
   m=item.module
   if m.__name__=='test_template_upgrade_browser':
    original_path=m.Path;m.Path=lambda value, _original=original_path: OUT/'browser'/self.window/'registered-upgrade' if str(value)=='.runtime/template-upgrade/browser' else _original(value)
   if hasattr(m,'OUT') and isinstance(m.OUT,Path):m.OUT=OUT/'browser'/self.window/m.__name__
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed or report.skipped:
   self.records.append(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration));self.progress_path.write_text(json.dumps(dict(elapsed=time.monotonic()-self.start,records=self.records),indent=2)+'\n')
raise SystemExit(pytest.main(sys.argv[1:],plugins=[Progress()]))
