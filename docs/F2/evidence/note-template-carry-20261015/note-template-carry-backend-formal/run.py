from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shutil,subprocess,sys,time,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/note-template-carry-backend-formal'
SHA=sys.argv[1];FREEZE=Path(sys.argv[2]);FINAL=ROOT/'.runtime/note-template-carry-final'
os.chdir(ROOT)
assert not (OUT/'launch.json').exists(),'new evidence window required; never overwrite a prior run'
freeze=json.loads(FREEZE.read_text());modules=json.loads((OUT/'modules.json').read_text())
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
def hashes(paths):return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
assert freeze['source_sha']==SHA and git('rev-parse','HEAD')==SHA
assert not git('status','--porcelain'),'entire frozen checkout must be clean'
tracked=[p for p in subprocess.check_output(['git','ls-files','-z'],text=True).split('\0') if p]
assert set(tracked)==set(freeze['all_tracked_sha256']) and set(freeze['source_paths'])<=set(tracked) and len(modules)==7
before_all=hashes(tracked);before_source={p:before_all[p] for p in freeze['source_paths']}
assert before_all==freeze['all_tracked_sha256'] and before_source==freeze['source_paths']
for name,values in [('all-tracked-before.json',before_all),('source-before.json',before_source)]:
 (OUT/name).write_text(json.dumps(values,indent=2)+'\n')
(OUT/'freeze-input.json').write_bytes(FREEZE.read_bytes())
for name in ['shared_capture.py','legacy_artifact_capture.py']:shutil.copyfile(FINAL/name,OUT/name)
(OUT/'artifact-legacy').mkdir()
args=[sys.executable,'-m','pytest','-q','-p','legacy_artifact_capture','-p','shared_capture','-p','formal_monitor','-o','cache_dir='+str(OUT/'pytest-cache'),*modules,'--basetemp=/tmp/parkweave-note-template-carry-formal-'+SHA[:8],'--junitxml='+str(OUT/'formal.xml')]
env=dict(os.environ,FORMAL_EVIDENCE_ROOT=str(OUT),LEGACY_ARTIFACT_DESTINATION=str(OUT/'artifact-legacy'),AT_BATCH_ARTIFACT_ROOT=str(OUT/'artifacts'),AT_BATCH_WINDOW='formal7',TYPED_COLLECTION=str(OUT/'collection.json'),TYPED_PRIVATE=str(OUT/'redaction.private.json'),XDG_CACHE_HOME=str(OUT/'xdg-cache'))
env['PYTHONPATH']=os.pathsep.join([str(OUT),str(ROOT/'src'),str(ROOT/'tests')])
started=datetime.now(timezone.utc).isoformat();start=time.monotonic()
launch=dict(source_sha=SHA,started_utc=started,argv=args,modules=modules,runner_pid=os.getpid(),source_count=len(before_source),tracked_count=len(before_all),capture_sha256=hashlib.sha256((OUT/'shared_capture.py').read_bytes()).hexdigest(),legacy_capture_sha256=hashlib.sha256((OUT/'legacy_artifact_capture.py').read_bytes()).hexdigest(),legacy_roots_sha256=hashlib.sha256((FINAL/'artifact-legacy-roots.json').read_bytes()).hexdigest(),artifact_root=env['AT_BATCH_ARTIFACT_ROOT'],legacy_artifact_root=env['LEGACY_ARTIFACT_DESTINATION'],freeze_input_sha256=hashlib.sha256((OUT/'freeze-input.json').read_bytes()).hexdigest())
(OUT/'launch.json').write_text(json.dumps(launch,indent=2)+'\n')
with (OUT/'formal.log').open('w') as stream:code=subprocess.run(args,stdout=stream,stderr=subprocess.STDOUT,env=env).returncode
finished=datetime.now(timezone.utc).isoformat();after_all=hashes(tracked);after_source={p:after_all[p] for p in before_source}
for name,values in [('all-tracked-after.json',after_all),('source-after.json',after_source)]:
 (OUT/name).write_text(json.dumps(values,indent=2)+'\n')
collection=json.loads((OUT/'collection.json').read_text());cases=list(ET.parse(OUT/'formal.xml').iter('testcase'));counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0);actual=[]
for c in cases:
 counts['ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS']+=1
 pieces=c.get('classname','').split('.');index=next((i for i,p in enumerate(pieces) if p.startswith('test_')),None)
 actual.append('UNMATCHED_JUNIT::'+c.get('name','') if index is None else 'tests/'+pieces[index]+'.py::'+'::'.join(pieces[index+1:]+[c.get('name')]))
source_drift=[p for p in before_source if before_source[p]!=after_source[p]];tracked_drift=[p for p in before_all if before_all[p]!=after_all[p]]
result=dict(source_sha=SHA,head_after=git('rev-parse','HEAD'),started_utc=started,finished_utc=finished,elapsed_seconds=time.monotonic()-start,exit_code=code,counts=counts,collected=len(collection),junit_cases=len(cases),collection_junit_exact_match=sorted(collection)==sorted(actual),unique_collection_nodes=len(collection)==len(set(collection)),unique_junit_nodes=len(actual)==len(set(actual)),source_count=len(before_source),tracked_count=len(before_all),source_drift=source_drift,tracked_drift=tracked_drift,tracked_list_after_unchanged=set(p for p in subprocess.check_output(['git','ls-files','-z'],text=True).split('\0') if p)==set(tracked),status_after=git('status','--porcelain'),modules=modules,argv=args)
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');(OUT/'junit-nodeids.json').write_text(json.dumps(actual,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False));sys.exit(code or int(bool(source_drift or tracked_drift or result['status_after']) or not result['tracked_list_after_unchanged'] or not result['collection_junit_exact_match'] or not result['unique_junit_nodes'] or result['head_after']!=SHA))
