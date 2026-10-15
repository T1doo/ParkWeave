from pathlib import Path
import subprocess,json,os,time,hashlib,xml.etree.ElementTree as ET
r=Path('/workspace/ParkWeave');base=Path(__file__).resolve().parent;o=base/'triage-fact-bundle-v1';o.mkdir(exist_ok=False);(o/'legacy').mkdir()
sha='f686adafe3cec9b2820c10fada51ef2f57a559a6';node='tests/test_case_fact_bundle.py::test_timed_source_expiration_during_actual_post_update_wait_rolls_back_lock'
f=json.loads((r/'.runtime/note-template-carry-root/freeze-v3.json').read_text());assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()==sha
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=r)
def hashes():return {p:hashlib.sha256((r/p).read_bytes()).hexdigest() for p in f['all_tracked_sha256']}
before=hashes();assert before==f['all_tracked_sha256'];(o/'before.json').write_text(json.dumps(before,indent=2)+'\n')
env={**os.environ,'PYTHONPATH':os.pathsep.join([str(base),str(r/'tests'),str(r)]),'TYPED_COLLECTION':str(o/'collection.json'),'TYPED_PRIVATE':str(o/'redaction.private.json'),'LEGACY_ARTIFACT_DESTINATION':str(o/'legacy'),'AT_BATCH_ARTIFACT_ROOT':str(o/'artifacts'),'AT_BATCH_WINDOW':'triage','PYTHONDONTWRITEBYTECODE':'1','XDG_CACHE_HOME':str(r/'.runtime/xdg-cache')}
args=[str(r/'.venv/bin/python'),'-m','pytest',node,'-vv','--tb=short','-p','shared_capture','-p','legacy_artifact_capture','-o','cache_dir=/tmp/note-carry-fact-triage-cache-v1','--basetemp=/tmp/note-carry-fact-triage-pg-v1','--junitxml='+str(o/'result.xml')]
t=time.monotonic()
with (o/'result.log').open('x') as log:code=subprocess.run(args,cwd=r,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
after=hashes();(o/'after.json').write_text(json.dumps(after,indent=2)+'\n');cs=list(ET.parse(o/'result.xml').iter('testcase'));counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0)
for c in cs:counts['ERROR' if c.find('error')is not None else 'FAIL' if c.find('failure')is not None else 'SKIP' if c.find('skipped')is not None else 'PASS']+=1
record=dict(source_sha=sha,node=node,exit_code=code,elapsed_seconds=time.monotonic()-t,counts=counts,all_tracked_drift=[p for p in before if before[p]!=after[p]],source_paths=len(f['source_paths']),all_tracked_paths=len(before),original_assertions_and_test_unchanged=True,independent_owned_PostgreSQL=True,not_substitute_for_complete_window=True)
(o/'result.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));raise SystemExit(code)
