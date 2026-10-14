from pathlib import Path
import subprocess,json,hashlib,time,sys
r=Path('.runtime/preview-rules-change-review-20261014');label='final1953-frozen-related'
source=json.loads((r/'final-source.json').read_text());files=list(source['files'])
def manifest():return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files}
before=manifest();assert before==source['files'];(r/(label+'.before.json')).write_text(json.dumps(before,indent=2)+'\n')
modules=json.loads((r/'final-modules.json').read_text())
code='''import pytest,sys,json\nfrom pathlib import Path\nclass Loaded:\n def pytest_sessionfinish(self,session,exitstatus):\n  root=Path.cwd().resolve(); paths={name:str(Path(module.__file__).resolve()) for name,module in sys.modules.items() if name.startswith('parkweave') and getattr(module,'__file__',None)}\n  wrong={name:path for name,path in paths.items() if not Path(path).is_relative_to(root/'src'/'parkweave')}\n  Path('.runtime/preview-rules-change-review-20261014/final-loaded.json').write_text(json.dumps(dict(paths=paths,wrong=wrong),indent=2)+'\\n')\n  if wrong: session.exitstatus=1\nsys.exit(pytest.main('''+repr(modules+['-q','--junitxml='+str(r/(label+'.xml'))])+''',plugins=[Loaded()]))'''
start=time.monotonic()
with (r/(label+'.log')).open('w') as out:result=subprocess.run([sys.executable,'-c',code],stdout=out,stderr=subprocess.STDOUT)
(r/(label+'.exit')).write_text(str(result.returncode)+'\n');after=manifest();(r/(label+'.after.json')).write_text(json.dumps(after,indent=2)+'\n')
summary={'source_sha':source['source_sha'],'exit':result.returncode,'seconds':time.monotonic()-start,'files':len(files),'drift':[p for p in before if before[p]!=after[p]],'modules':modules}
(r/(label+'.window.json')).write_text(json.dumps(summary,indent=2)+'\n');print(summary)
