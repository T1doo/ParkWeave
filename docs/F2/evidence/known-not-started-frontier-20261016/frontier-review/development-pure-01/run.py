from pathlib import Path
import os,sys,json,hashlib,subprocess,datetime,importlib
root=Path.cwd();out=root/'.runtime/frontier-review/development-pure-01'
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.path.insert(0,str(root/'src'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
 names=subprocess.check_output(['git','ls-files','-z'],text=True).split('\0')
 rows={n:sha(root/n) for n in names if n and (root/n).is_file()}
 modules={}
 for name in ('business_frontier','business_frontier_types','plan_replacement_compatibility','service_dispatches','executor_receipts','case_lifecycle'):
  m=importlib.import_module('parkweave.'+name);p=Path(m.__file__).resolve();modules[name]=dict(path=str(p),sha256=sha(p))
 return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),tracked=rows,imports=modules)
before=snapshot();(out/'before.json').write_text(json.dumps(before,indent=2)+'\n')
cmd=[sys.executable,'-B','-m','pytest','-p','no:cacheprovider','-q','--junitxml='+str(out/'junit.xml'),str(root/'.runtime/frontier-review/pure-candidate-v1/test_frontier_review_pure.py')]
env=dict(os.environ,PYTHONPATH=str(root/'src'),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
with (out/'raw.log').open('wb') as f:result=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
after=snapshot();(out/'after.json').write_text(json.dumps(after,indent=2)+'\n')
summary=dict(status='DEVELOPMENT_NOT_FROZEN',exit_code=result.returncode,command=cmd,source_changed=[k for k in before['tracked'] if before['tracked'][k]!=after['tracked'].get(k)],imports_equal=before['imports']==after['imports'],head_equal=before['head']==after['head'])
(out/'result.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary));print((out/'raw.log').read_text())
