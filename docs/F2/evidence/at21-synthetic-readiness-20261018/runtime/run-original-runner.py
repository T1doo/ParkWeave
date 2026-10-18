from pathlib import Path
import json,os,subprocess,time
R=Path.cwd();D=R/'.runtime/at21-synthetic-readiness-20261018';freeze=json.loads((D/'frozen-freeze.json').read_text());S=freeze['source_sha'];assert not (D/'runner-invocation.json').exists();assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==S and not subprocess.check_output(['git','status','--porcelain'])
env={k:os.environ[k] for k in ['PATH','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','TMPDIR','LANG','LC_ALL','TZ'] if k in os.environ}
argv=[str(R/'.venv/bin/python'),'scripts/run_acceptance.py','--ids','AT-21','--source-head',S,'--report',str(D/'original-runner-report.json')];start=time.monotonic()
p=subprocess.run(argv,cwd=R,env=env,capture_output=True,text=True,timeout=120);(D/'original-runner.stdout').write_text(p.stdout);(D/'original-runner.stderr').write_text(p.stderr)
v=dict(source_sha=S,argv=argv,exit_code=p.returncode,elapsed_seconds=time.monotonic()-start,automatic_retries=0);(D/'runner-invocation.json').write_text(json.dumps(v,indent=2)+'\n')
report=json.loads((D/'original-runner-report.json').read_text());assert p.returncode==1 and report['observed_cases']==0 and report['acceptance_failure']['reason']=='GIT_BLOB_UNAVAILABLE';assert report['whole_AT_EX']=='NOT_RUN'
files=sorted((R/'tests').glob('test_*.py'));sizes=[p.stat().st_size for p in files];result=dict(**v,phase=report['acceptance_failure'],pytest_executed=0,whole_AT_EX='NOT_RUN',root_test_files=len(files),root_test_bytes=sum(sizes),unchanged_cap_bytes=4194304,repaired=False)
(D/'runner-refusal-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
