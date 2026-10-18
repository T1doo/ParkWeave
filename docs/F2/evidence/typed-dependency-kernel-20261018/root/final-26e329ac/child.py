import sys,json,hashlib
from pathlib import Path
import pytest
args=sys.argv[1:]
class Record:
 def pytest_collection_finish(self,session):
  self.nodes=[i.nodeid for i in session.items]
  Path('collection.json').write_text(json.dumps(self.nodes,indent=2)+'\n')
p=Record();code=pytest.main(args,plugins=[p])
origins={}
for name,m in tuple(sys.modules.items()):
 f=getattr(m,'__file__',None)
 if f and (name.startswith('parkweave') or name.startswith('test_dependency_graph')):
  path=Path(f).resolve()
  if path.is_file():origins[name]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
Path('module-origins.json').write_text(json.dumps(origins,indent=2)+'\n')
raise SystemExit(code)
