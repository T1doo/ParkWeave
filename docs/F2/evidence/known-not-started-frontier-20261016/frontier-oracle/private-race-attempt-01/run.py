from pathlib import Path
import subprocess,os,json,datetime,hashlib
OUT=Path(__file__).resolve().parent;WORK=OUT/'project';env=os.environ.copy()
env.update(PYTHONPATH=str(WORK/'src')+os.pathsep+str(WORK/'tests')+os.pathsep+str(OUT),FRONTIER_TEST_SOURCE_ROOT=str(WORK/'src/parkweave'),FRONTIER_TEST_SOURCE_MANIFEST=str(WORK/'source-manifest.json'),FRONTIER_ORACLE_ARTIFACT_ROOT=str(OUT/'artifacts/oracle'),FRONTIER_ARTIFACT_ROOT=str(OUT/'artifacts/fixture'),FRONTIER_PRIVATE_WINDOW_ROOT=str(OUT))
args=['/workspace/ParkWeave/.venv/bin/python','-m','pytest','tests/test_frontier_p4_race.py','-q','-p','private_redaction','--tb=short','--junitxml='+str(OUT/'junit.xml')]
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
log=OUT/'pytest.log'
with log.open('w') as stream:
 log.chmod(0o600);result=subprocess.run(args,cwd=WORK,env=env,stdout=stream,stderr=subprocess.STDOUT)
manifest=json.loads((WORK/'source-manifest.json').read_text())['source_paths']
drift=[p for p,h in manifest.items() if not (WORK/p).exists() or hashlib.sha256((WORK/p).read_bytes()).hexdigest()!=h]
receipt={'status':'PRIVATE_DEVELOPMENT_RESULT_NOT_FORMAL','started_utc':start,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':result.returncode,'source_drift':drift,'selected_complete_modules':['tests/test_frontier_p4_race.py'],'redaction_plugin_sha256':hashlib.sha256((OUT/'private_redaction.py').read_bytes()).hexdigest(),'product_logic_patched':False}
(OUT/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
