from pathlib import Path
import hashlib,json,subprocess,time,sys,os,xml.etree.ElementTree as ET
root=Path.cwd();base=root/'.runtime/source-adoption';modules=json.loads((base/'root-modules.json').read_text())
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain','--','src','tests','scripts','pyproject.toml']), 'source tree must be committed'
def manifest():
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for d in ['src','tests','scripts'] for p in sorted(Path(d).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}|{'pyproject.toml':hashlib.sha256(Path('pyproject.toml').read_bytes()).hexdigest()}
before=manifest();(base/'frozen-before.json').write_text(json.dumps(before,indent=2)+'\n')
args=[sys.executable,'-m','pytest',*modules,'-q','--junitxml='+str(base/'root-final.xml')]
start=time.monotonic()
with (base/'root-final.log').open('w') as log:code=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT).returncode
after=manifest();(base/'frozen-after.json').write_text(json.dumps(after,indent=2)+'\n')
xml=ET.parse(base/'root-final.xml').getroot();cases=list(xml.iter('testcase'));counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0)
for case in cases:
 key='ERROR' if case.find('error') is not None else 'FAIL' if case.find('failure') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS';counts[key]+=1
record=dict(source_sha=source,argv=args,exit_code=code,elapsed_seconds=time.monotonic()-start,files=len(before),source_drift=[p for p in set(before)|set(after) if before.get(p)!=after.get(p)],counts=counts,modules=modules,testcase_keys=[dict(classname=c.get('classname'),name=c.get('name')) for c in cases])
(base/'root-final.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k not in ('argv','modules','testcase_keys')}));print((base/'root-final.log').read_text()[-4000:]);sys.exit(code)
