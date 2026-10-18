from pathlib import Path
import os,sys,json,subprocess,hashlib,time,tempfile,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');r=root/'.runtime/receipt-submit-recovery-20261018';os.chdir(root);label=sys.argv[1];extra=sys.argv[2:]
def paths():return sorted(set(subprocess.check_output(['git','ls-files','src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md','docs/F2/ReceiptSubmitRecovery-20261018.md'],text=True).splitlines()+subprocess.check_output(['git','ls-files','--others','--exclude-standard','src','tests','scripts'],text=True).splitlines()))
def manifest():return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths()}
before=manifest();(r/(label+'-inputs.json')).write_text(json.dumps(before,indent=2)+'\n');base=Path(tempfile.mkdtemp(prefix='pw-receipt-submit-'+label+'-'))/'pytest'
sys.path.insert(0,str(root/'src'));from parkweave.process_env import minimal_environment
env=minimal_environment(os.environ,PYTHONPATH=os.pathsep.join(str(root/p) for p in ['tests','src','.']),PYTHONDONTWRITEBYTECODE='1',FRONTIER_ARTIFACT_ROOT=str(base/'frontier-artifacts'),FRONTIER_ORACLE_ARTIFACT_ROOT=str(base/'frontier-oracle-artifacts'),FRONTIER_TEST_SOURCE_ROOT=str(root/'src/parkweave'),FRONTIER_TEST_SOURCE_MANIFEST=str(r/'frozen-inputs.json'))
argv=[str(root/'.venv/bin/python'),'-B','-m','pytest','-q','-p','no:cacheprovider','--rootdir='+str(root),'--basetemp='+str(base),'--junitxml='+str(r/(label+'.xml'))]+extra
inv=dict(argv=argv,cwd=str(root),basetemp=str(base),source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),started=time.time(),source_status=subprocess.check_output(['git','status','--porcelain'],text=True));(r/(label+'-invocation.json')).write_text(json.dumps(inv,indent=2)+'\n')
with (r/(label+'.log')).open('w') as log:p=subprocess.run(argv,env=env,stdout=log,stderr=subprocess.STDOUT)
after=manifest();drift=[x for x in before.keys()|after.keys() if before.get(x)!=after.get(x)];result=dict(source_sha=inv['source_sha'],exit_code=p.returncode,elapsed_seconds=time.time()-inv['started'],input_count=len(before),input_drift=drift)
if (r/(label+'.xml')).exists():
 tree=E.parse(r/(label+'.xml'));cases=tree.findall('.//testcase');result.update(testcases=len(cases),unique=len({(c.get('classname'),c.get('name')) for c in cases}),failures=len(tree.findall('.//failure')),errors=len(tree.findall('.//error')),skipped=len(tree.findall('.//skipped')))
(r/(label+'-result.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));sys.exit(p.returncode)
