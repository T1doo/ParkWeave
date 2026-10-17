from pathlib import Path
import datetime,json,os,subprocess,sys,time
root=Path('/workspace/ParkWeave');os.chdir(root)
name=sys.argv[1];modules=sys.argv[2:]
private=root/'.runtime/material-version-compare';private.mkdir(exist_ok=True)
argv=['.venv/bin/python','-m','pytest',*modules,'-q',f'--basetemp=/tmp/parkweave-material-version-{name}',f'--junitxml={private.relative_to(root)}/{name}.xml']
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
meta={'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'argv':argv,'diagnostic_instrumentation':False,'started_at':now()}
meta['uncommitted_source_diff_sha256']=__import__('hashlib').sha256(subprocess.check_output(['git','diff','--','src','tests','scripts','pyproject.toml'])).hexdigest()
mp=private/(name+'-invocation.json')
with (private/(name+'.log')).open('xb') as log:
 env=dict(os.environ,CASE_GOAL_RESULTS_EVIDENCE=str(private/name/'original-goals-browser'),OVERVIEW_EVIDENCE_DIRECTORY=str(private/name/'original-overview'),OVERVIEW_DENIED_EVIDENCE=str(private/name/'original-overview-denied'));meta['artifact_environment']={k:env[k] for k in ('CASE_GOAL_RESULTS_EVIDENCE','OVERVIEW_EVIDENCE_DIRECTORY','OVERVIEW_DENIED_EVIDENCE')};proc=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,env=env);meta['pytest_pid']=proc.pid;mp.write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta),flush=True)
 meta['exit_code']=proc.wait();meta['completed_at']=now();mp.write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps({'name':name,'exit_code':meta['exit_code']}),flush=True)
sys.exit(meta['exit_code'])
