"""Complete-module development window with actual dirty-source snapshots."""
from pathlib import Path
import subprocess,sys,os,json,hashlib,time,datetime,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');os.chdir(root);name=sys.argv[1];modules=json.loads(Path(sys.argv[2]).read_text())
base=root/'.runtime/frontier-root/development'/name;assert not base.exists();base.mkdir(parents=True)
def git(*args):return subprocess.check_output(['git',*args],text=True)
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=sorted(set(p for p in git('ls-files','--cached','--others','--exclude-standard','-z','--','src','tests','scripts','pyproject.toml').split('\0') if p))
before={p:digest(p) for p in paths};tracked=[p for p in git('ls-files','-z').split('\0') if p];all_before={p:digest(p) for p in tracked}
changed=[p for p in git('ls-files','-m','-o','--exclude-standard','-z','--','src','tests','scripts','pyproject.toml').split('\0') if p]
for p in changed:
 target=base/'source-snapshot'/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(Path(p).read_bytes())
(base/'before.json').write_text(json.dumps(before,indent=2)+'\n');(base/'all-tracked-before.json').write_text(json.dumps(all_before,indent=2)+'\n')
runner=root/'.runtime/frontier-root/v1/runner';collection=base/'collection.json';artifact=base/'artifacts';artifact.mkdir()
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(runner)+os.pathsep+str(root)+os.pathsep+os.environ.get('PYTHONPATH',''),LEGACY_ARTIFACT_DESTINATION=str(base),AT_BATCH_ARTIFACT_ROOT=str(artifact),AT_BATCH_WINDOW=name,TYPED_CAPTURE_PLUGIN=str(runner/'shared_capture.py'),TYPED_COLLECTION=str(collection),TYPED_PRIVATE=str(base/'redaction.private.json'),PLAN_REPLACEMENT_TEST_SOURCE_ROOT=str(root/'src/parkweave'),FRONTIER_TEST_SOURCE_ROOT=str(root/'src/parkweave'),FRONTIER_ARTIFACT_ROOT=str(artifact/'frontier-fixture'),FRONTIER_ORACLE_ARTIFACT_ROOT=str(artifact/'frontier-oracle'),PARKWEAVE_T07_EVIDENCE_DIR=str(artifact/'t07-evidence'))
args=[sys.executable,'-m','pytest','-q','-p','shared_capture','-p','legacy_artifact_capture',*modules,'--basetemp=/tmp/parkweave-frontier-development-'+name,'--junitxml='+str(base/'junit.xml')]
start=time.monotonic();started=datetime.datetime.now(datetime.timezone.utc).isoformat()
with (base/'pytest.log').open('w') as output:code=subprocess.run(args,stdout=output,stderr=subprocess.STDOUT,env=env).returncode
after={p:digest(p) for p in paths};all_after={p:digest(p) for p in tracked};cases=list(ET.parse(base/'junit.xml').iter('testcase')) if (base/'junit.xml').exists() else [];counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0)
for case in cases:counts['ERROR' if case.find('error') is not None else 'FAIL' if case.find('failure') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS']+=1
def node(case):
 parts=case.get('classname','').split('.');pos=next((i for i,x in enumerate(parts) if x.startswith('test_')),None)
 return 'UNSUPPORTED::'+case.get('name','') if pos is None else 'tests/'+parts[pos]+'.py::'+'::'.join(parts[pos+1:]+[case.get('name')])
collected=json.loads(collection.read_text()) if collection.exists() else []
record={'scope':'UNCOMMITTED_DEVELOPMENT_COMPLETE_MODULES_NOT_FINAL_SCORES','base_head':git('rev-parse','HEAD').strip(),'started_utc':started,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-start,'modules':modules,'argv':args,'exit_code':code,'counts':counts,'collection_junit_exact_match':sorted(collected)==sorted(node(c) for c in cases),'unique_nodes':len(collected)==len(set(collected)),'source_drift':[p for p in paths if before[p]!=after[p]],'all_tracked_drift':[p for p in tracked if all_before[p]!=all_after[p]],'changed_source_snapshot_paths':changed,'source_before_sha256':before,'source_after_sha256':after,'all_tracked_paths':len(tracked),'collected_nodes':collected}
(base/'result.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k not in {'argv','source_before_sha256','source_after_sha256','collected_nodes','changed_source_snapshot_paths'}}));raise SystemExit(code or int(bool(record['source_drift'] or record['all_tracked_drift']) or not record['collection_junit_exact_match'] or not record['unique_nodes']))
