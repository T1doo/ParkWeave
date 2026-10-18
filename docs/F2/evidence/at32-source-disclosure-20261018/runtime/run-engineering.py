from pathlib import Path
import datetime,hashlib,json,os,platform,subprocess,sys,time
R=Path.cwd();D=R/'.runtime/at32-source-disclosure-20261018';SOURCE='d74c7b4e22c648e125b5aa135d2506e94242f76e'
def git(*a):return subprocess.check_output(['git',*a],cwd=R,text=True).strip()
assert git('rev-parse','HEAD')==SOURCE and not git('status','--porcelain')
sys.path.insert(0,str(R/'src'));from parkweave.process_env import minimal_environment
env=minimal_environment(os.environ); runs=[]
commands=[('selector',[sys.executable,'scripts/run_acceptance.py','--ids','AT-32','--source-head',SOURCE,'--report',str(D/'engineering-at32.json')]),('guards',[sys.executable,'-m','pytest','-q','--junitxml',str(D/'guards.xml'),'tests/test_acceptance_runner.py::test_fixed_bindings_complete_unique_and_safe','tests/test_acceptance_runner.py::test_whole_acceptance_never_passes_and_missing_tests_are_incomplete'])]
for name,argv in commands:
 start=time.monotonic();stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with (D/(name+'.stdout')).open('w') as out,(D/(name+'.stderr')).open('w') as err:
  try:p=subprocess.run(argv,cwd=R,env=env,stdout=out,stderr=err,timeout=120);code=p.returncode;state='COMPLETED'
  except subprocess.TimeoutExpired:code=None;state='TIMEOUT'
 runs.append(dict(name=name,argv=argv,source_sha=SOURCE,started_utc=stamp,elapsed_seconds=time.monotonic()-start,exit_code=code,state=state,automatic_retries=0))
 if code!=0:break
if (D/'engineering-at32.json').exists():
 v=json.loads((D/'engineering-at32.json').read_text())
 for key,name in [('private_junit','selector.xml'),('private_log','selector-pytest.log')]:
  if key in v:(D/name).write_bytes((R/v[key]).read_bytes())
assert git('rev-parse','HEAD')==SOURCE and not git('status','--porcelain')
v=dict(schema='parkweave-at32-engineering-invocations/1',source_sha=SOURCE,python=sys.version,platform=platform.platform(),runs=runs,product_runs=0,db_connections=0,real_model_calls=0,native_windows='NOT_RUN',full_regression=False)
(D/'engineering-invocations.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'runs':runs},ensure_ascii=False));raise SystemExit(0 if len(runs)==2 and all(r['exit_code']==0 for r in runs) else 1)
