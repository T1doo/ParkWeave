from pathlib import Path
import subprocess,shutil,json,hashlib,zipfile,time
r=Path('.runtime/preview-rules-change-review-20261014');stage=r/'wheel5e339-stage';stage.mkdir()
shutil.copytree('src',stage/'src',ignore=shutil.ignore_patterns('__pycache__'));shutil.copyfile('pyproject.toml',stage/'pyproject.toml')
start=time.monotonic()
with (r/'wheel5e339.log').open('w') as out:p=subprocess.run(['/workspace/ParkWeave/.venv/bin/python','-c',"from setuptools.build_meta import build_wheel; build_wheel('dist')"],cwd=stage,stdout=out,stderr=subprocess.STDOUT)
(r/'wheel5e339.exit').write_text(str(p.returncode)+'\n');assert p.returncode==0
w=next((stage/'dist').glob('*.whl'));z=zipfile.ZipFile(w)
expected={str(p.relative_to('src')):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('src/parkweave').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
actual={name:hashlib.sha256(z.read(name)).hexdigest() for name in z.namelist() if name.startswith('parkweave/') and not name.endswith('/')};assert expected==actual
extract=stage/'extracted';z.extractall(extract)
script="""from pathlib import Path
import sys,json
sys.path.insert(0,str(Path('extracted').resolve()))
from parkweave import api,store,synthetic_rule_readiness,resource_change_proposals
from fastapi.testclient import TestClient
class NoConnect(store.Store):
 def connect(self):raise AssertionError('default-disabled wheel smoke attempted business connection')
with TestClient(api.create_app(NoConnect('not-used'))) as c:
 assert c.get('/').status_code==200
 assert c.get('/api/preparations/00000000-0000-0000-0000-000000000001/synthetic-rule-readiness',params=dict(binding_id='unused',as_of='2026-10-14T00:00:00+00:00')).status_code==403
paths={m.__name__:m.__file__ for m in (api,store,synthetic_rule_readiness,resource_change_proposals)}
assert all(Path(v).is_relative_to(Path('extracted').resolve()) for v in paths.values())
print(json.dumps(dict(root_get=200,default_simulation_get=403,loaded=paths)))
"""
with (r/'wheel5e339-runtime.log').open('w') as out:q=subprocess.run(['/workspace/ParkWeave/.venv/bin/python','-c',script],cwd=stage,stdout=out,stderr=subprocess.STDOUT)
(r/'wheel5e339-runtime.exit').write_text(str(q.returncode)+'\n');assert q.returncode==0
result={'source_sha':'5e339a247e33d1a4b6cb4c106e54af1ea22b5439','all_src_files':len(expected),'missing':[],'extra':[],'changed':[],'wheel_sha256':hashlib.sha256(w.read_bytes()).hexdigest(),'build_exit':p.returncode,'runtime_exit':q.returncode,'seconds':time.monotonic()-start}
(r/'wheel5e339.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
