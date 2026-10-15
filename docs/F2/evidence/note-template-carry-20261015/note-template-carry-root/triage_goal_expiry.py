from pathlib import Path
import os,subprocess,json,hashlib,time,sys,xml.etree.ElementTree as E
r=Path.cwd();base=r/'.runtime/note-template-carry-root/goal-expiry-triage-v1';base.mkdir(exist_ok=False);f=json.loads((r/'.runtime/note-template-carry-root/freeze-v3.json').read_text());paths=f['all_tracked_sha256']
def manifest():return {p:hashlib.sha256((r/p).read_bytes()).hexdigest() for p in paths}
before=manifest();assert before==paths
(base/'all-tracked-before.json').write_text(json.dumps(before,indent=2)+'\n')
assert subprocess.check_output(['git','show','ed5d32b6bbcf261d802fe579a2daab16330a5879:tests/test_case_goal_results.py'])==(r/'tests/test_case_goal_results.py').read_bytes()
artifact=base/'legacy-artifacts';artifact.mkdir()
env=dict(os.environ,PYTHONPATH=str(r/'.runtime/note-template-carry-final')+os.pathsep+str(r),LEGACY_ARTIFACT_DESTINATION=str(artifact),AT_BATCH_ARTIFACT_ROOT=str(base/'artifacts'),AT_BATCH_WINDOW='triage',TYPED_COLLECTION=str(base/'collection.json'),TYPED_PRIVATE=str(base/'redaction.private.json'))
args=[sys.executable,'-m','pytest','-q','-p','shared_capture','-p','legacy_artifact_capture','tests/test_case_goal_results.py::test_resource_window_expiry_during_actual_last_source_row_lock_wait','--basetemp=/tmp/parkweave-note-carry-goal-expiry-triage-v1','--junitxml='+str(base/'result.xml')]
start=time.monotonic()
with (base/'result.log').open('x') as log:code=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
after=manifest();(base/'all-tracked-after.json').write_text(json.dumps(after,indent=2)+'\n');cases=list(E.parse(base/'result.xml').iter('testcase'));result=dict(source_sha=f['source_sha'],argv=args,exit_code=code,elapsed_seconds=time.monotonic()-start,source_and_all_tracked_unchanged=before==after==paths,collected=json.loads((base/'collection.json').read_text()),cases=[dict(name=c.get('name'),failed=c.find('failure') is not None,error=c.find('error') is not None,skipped=c.find('skipped') is not None) for c in cases],product_and_test_unchanged=True)
(base/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));sys.exit(code or int(before!=after))
