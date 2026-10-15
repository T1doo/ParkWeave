from pathlib import Path
import hashlib,json,os,subprocess,sys,time,xml.etree.ElementTree as ET
from datetime import datetime,timezone
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/manual-continuation-backend-formal-v2';SHA='14bc83f241149bd03907bd088a35eb6df53ba0a2'
os.chdir(ROOT)
freeze=json.loads((ROOT/'.runtime/manual-continuation-root/freeze-v2.json').read_text());modules=json.loads((OUT/'modules.json').read_text())
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
def hash_paths(paths):return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
assert freeze['source_sha']==SHA and git('rev-parse','HEAD')==SHA
assert not git('status','--porcelain'), 'entire frozen checkout must be clean before start'
tracked=git('ls-files','-z').split('\0');tracked=[p for p in tracked if p]
assert set(tracked)==set(freeze['all_tracked_sha256'])
assert len(freeze['source_paths'])==608 and len(tracked)==13252 and len(modules)==7
before_all=hash_paths(tracked);before_source={p:before_all[p] for p in freeze['source_paths']}
assert before_all==freeze['all_tracked_sha256'] and before_source==freeze['source_paths']
(OUT/'all-tracked-before.json').write_text(json.dumps(before_all,indent=2)+'\n');(OUT/'source-before.json').write_text(json.dumps(before_source,indent=2)+'\n')
args=[sys.executable,'-m','pytest','-q','-p','legacy_artifact_capture','-p','shared_capture','-p','formal_monitor','-o','cache_dir='+str(OUT/'pytest-cache'),*modules,'--basetemp=/tmp/parkweave-manual-continuation-backend-formal-v2-14bc83f','--junitxml='+str(OUT/'formal.xml')]
env=dict(os.environ,FORMAL_EVIDENCE_ROOT=str(OUT),LEGACY_ARTIFACT_DESTINATION=str(OUT/'artifact-legacy'),AT_BATCH_ARTIFACT_ROOT=str(OUT/'artifacts'),AT_BATCH_WINDOW='formal7',TYPED_COLLECTION=str(OUT/'collection.json'),TYPED_PRIVATE=str(OUT/'redaction.private.json'),XDG_CACHE_HOME=str(OUT/'xdg-cache'))
env['PYTHONPATH']=os.pathsep.join([str(OUT),str(ROOT/'src'),str(ROOT/'tests')])
started=datetime.now(timezone.utc).isoformat();start=time.monotonic()
(OUT/'launch.json').write_text(json.dumps(dict(source_sha=SHA,started_utc=started,argv=args,modules=modules,runner_pid=os.getpid(),source_count=len(before_source),tracked_count=len(before_all),capture_sha256=hashlib.sha256((OUT/'shared_capture.py').read_bytes()).hexdigest(),artifact_root=env['AT_BATCH_ARTIFACT_ROOT'],legacy_artifact_root=env['LEGACY_ARTIFACT_DESTINATION'],legacy_capture_sha256=hashlib.sha256((OUT/'legacy_artifact_capture.py').read_bytes()).hexdigest(),legacy_roots_sha256=hashlib.sha256((ROOT/'.runtime/manual-continuation-final/artifact-legacy-roots.json').read_bytes()).hexdigest()),indent=2)+'\n')
with (OUT/'formal.log').open('w') as stream:code=subprocess.run(args,stdout=stream,stderr=subprocess.STDOUT,env=env).returncode
finished=datetime.now(timezone.utc).isoformat();after_all=hash_paths(tracked);after_source={p:after_all[p] for p in before_source}
(OUT/'all-tracked-after.json').write_text(json.dumps(after_all,indent=2)+'\n');(OUT/'source-after.json').write_text(json.dumps(after_source,indent=2)+'\n')
collection=json.loads((OUT/'collection.json').read_text());cases=list(ET.parse(OUT/'formal.xml').iter('testcase'));counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0);actual=[]
for c in cases:
    counts['ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS']+=1
    pieces=c.get('classname','').split('.');index=next((i for i,p in enumerate(pieces) if p.startswith('test_')),None)
    actual.append('UNMATCHED_JUNIT::'+c.get('name','') if index is None else 'tests/'+pieces[index]+'.py::'+'::'.join(pieces[index+1:]+[c.get('name')]))
source_drift=[p for p in before_source if before_source[p]!=after_source[p]];tracked_drift=[p for p in before_all if before_all[p]!=after_all[p]]
result=dict(source_sha=SHA,head_after=git('rev-parse','HEAD'),started_utc=started,finished_utc=finished,elapsed_seconds=time.monotonic()-start,exit_code=code,counts=counts,collected=len(collection),junit_cases=len(cases),collection_junit_exact_match=sorted(collection)==sorted(actual),unique_collection_nodes=len(collection)==len(set(collection)),unique_junit_nodes=len(actual)==len(set(actual)),source_count=len(before_source),tracked_count=len(before_all),source_drift=source_drift,tracked_drift=tracked_drift,tracked_list_after_unchanged=set(git('ls-files','-z').split('\0'))-set([''])==set(tracked),status_after=git('status','--porcelain'),modules=modules,argv=args)
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');(OUT/'junit-nodeids.json').write_text(json.dumps(actual,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False));sys.exit(code or int(bool(source_drift or tracked_drift) or not result['collection_junit_exact_match'] or not result['unique_junit_nodes'] or result['head_after']!=SHA))
