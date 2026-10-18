from pathlib import Path
import datetime,hashlib,io,json,os,subprocess,sys,tarfile,tempfile,time,xml.etree.ElementTree as ET
R=Path.cwd();D=R/'.runtime/at32-source-disclosure-20261018';S='d74c7b4e22c648e125b5aa135d2506e94242f76e'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==S
work=Path(tempfile.mkdtemp(prefix='pw-at32-static-',dir='/tmp'));mirror=work/'mirror';mirror.mkdir()
paths=['src','tests','scripts','pyproject.toml','docs/验收规格.json','docs/F1/ATBindings.json','docs/sources/V1']
blob=subprocess.check_output(['git','archive',S,'--',*paths]);tarfile.open(fileobj=io.BytesIO(blob)).extractall(mirror,filter='data')
records={}
for line in subprocess.check_output(['git','ls-tree','-rz',S,'--',*paths]).split(b'\0'):
 if line:
  meta,p=line.split(b'\t',1);oid=meta.split()[2].decode();name=p.decode();b=(mirror/name).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==oid
  records[name]={'git_blob':oid,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
(D/'static-mirror-inputs.json').write_text(json.dumps(dict(source_sha=S,archive_sha256=hashlib.sha256(blob).hexdigest(),mirror=str(mirror),files=records),indent=2)+'\n')
sys.path.insert(0,str(mirror/'src'));from parkweave.process_env import minimal_environment
env=minimal_environment(os.environ,PYTHONPATH=str(mirror/'src'))
argv=[sys.executable,'-m','pytest','-q','--basetemp',str(work/'pytest'),'--junitxml',str(D/'static-mirror.xml'),'tests/test_acceptance_runner.py'];start=time.monotonic();stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
with (D/'static-mirror.stdout').open('w') as out,(D/'static-mirror.stderr').open('w') as err:
 try:p=subprocess.run(argv,cwd=mirror,env=env,stdout=out,stderr=err,timeout=120);code=p.returncode;state='COMPLETED'
 except subprocess.TimeoutExpired:code=None;state='TIMEOUT'
drift=[]
for name,row in records.items():
 if hashlib.sha256((mirror/name).read_bytes()).hexdigest()!=row['sha256'] or hashlib.sha256((R/name).read_bytes()).hexdigest()!=row['sha256']:drift.append(name)
cases=list(ET.parse(D/'static-mirror.xml').getroot().iter('testcase')) if (D/'static-mirror.xml').exists() else []
result=dict(source_sha=S,started_utc=stamp,elapsed_seconds=time.monotonic()-start,state=state,exit_code=code,argv=argv,cwd=str(mirror),source_inputs=len(records),PREPOST_drift=drift,case_ids=[c.attrib for c in cases],passed=sum(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in cases),failures=sum(c.find('failure') is not None for c in cases),errors=sum(c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases),scope='Direct execution of 3 existing static tests on frozen Git archive. Not a successful run_acceptance/source_bytes invocation; original cap refusal remains.',automatic_retries=0,model_calls=0,db_connections=0,product_runs=0,native_windows='NOT_RUN',real_business='NOT_RUN')
(D/'static-mirror-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert code==0 and result['passed']==3 and not drift
