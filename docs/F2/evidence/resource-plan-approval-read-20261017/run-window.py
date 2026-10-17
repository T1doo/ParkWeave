from pathlib import Path
import datetime,json,os,subprocess,sys,time
root=Path('/workspace/ParkWeave');os.chdir(root)
name=sys.argv[1];modules=sys.argv[2:]
private=root/'.runtime/resource-plan-approval-read';private.mkdir(exist_ok=True)
argv=['.venv/bin/python','-m','pytest',*modules,'-q',f'--basetemp=/tmp/parkweave-resource-approval-{name}',f'--junitxml={private.relative_to(root)}/{name}.xml']
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
meta={'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'argv':argv,'diagnostic_instrumentation':False,'started_at':now()}
meta['uncommitted_source_diff_sha256']=__import__('hashlib').sha256(subprocess.check_output(['git','diff','--','src','tests','scripts','pyproject.toml'])).hexdigest()
mp=private/(name+'-invocation.json')
with (private/(name+'.log')).open('xb') as log:
 proc=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT);meta['pytest_pid']=proc.pid;mp.write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta),flush=True)
 meta['exit_code']=proc.wait();meta['completed_at']=now();mp.write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps({'name':name,'exit_code':meta['exit_code']}),flush=True)
sys.exit(meta['exit_code'])
