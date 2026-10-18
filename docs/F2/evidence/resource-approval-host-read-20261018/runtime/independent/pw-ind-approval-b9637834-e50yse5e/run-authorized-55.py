from pathlib import Path
import hashlib,json,os,shutil,subprocess,time,xml.etree.ElementTree as ET
repo=Path('/workspace/ParkWeave')
r=repo/'.runtime/resource-approval-host-read-20261018/independent/pw-ind-approval-b9637834-e50yse5e'
p=json.loads((r/'preparation.json').read_text());mirror=Path(p['mirror']);outer=Path(p['outer'])
expected=json.loads((r/'expected-inputs.json').read_text())
assert not (r/'run-result.json').exists() and not (r/'owned-process.json').exists(),'one execution only'
def snapshot(root):return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in expected}
def drift(actual):return [name for name in expected if actual[name]!=expected[name]]
shared_pre=snapshot(repo);mirror_pre=snapshot(mirror)
assert not drift(shared_pre) and not drift(mirror_pre)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==p['source_sha']
contract=p['feature_contract_path'];contract_pre={str(root):hashlib.sha256((root/contract).read_bytes()).hexdigest() for root in (repo,mirror)}
assert set(contract_pre.values())=={p['feature_contract_sha256']}
(r/'shared-run-PRE-inputs.json').write_text(json.dumps(shared_pre,indent=2)+'\n')
(r/'mirror-run-PRE-inputs.json').write_text(json.dumps(mirror_pre,indent=2)+'\n')
osnames={'PATH','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','TMPDIR','LANG','LC_ALL','TZ'}
env={name:os.environ[name] for name in osnames if name in os.environ}
env.update(PYTHONPATH=os.pathsep.join(str(mirror/name) for name in ('src','tests','.')),PYTHONDONTWRITEBYTECODE='1',PW_REVIEW_EVIDENCE=str(r))
args=['-q','-p','no:cacheprovider','--rootdir='+str(mirror),'--basetemp='+str(outer/'pytest'),'--junitxml='+str(r/'independent.xml'),'tests/test_resource_approval_host_read.py','tests/test_resource_approval_host_browser.py']
argv=[str(repo/'.venv/bin/python'),'-B',str(r/'pytest-observer.py'),*args]
inv=dict(source_sha=p['source_sha'],source_tree=p['source_tree'],argv=argv,pytest_args=args,cwd=str(mirror),environment=env,started_utc_epoch=time.time(),automatic_retries=0,authorized_expected=55,basetemp=str(outer/'pytest'),origin_scope='pytest sys.modules actual files only; child API/host not independently instrumented')
(r/'invocation.json').write_text(json.dumps(inv,indent=2)+'\n')
start=time.monotonic()
with (r/'stdout.txt').open('w') as stdout,(r/'stderr.txt').open('w') as stderr:
    child=subprocess.Popen(argv,cwd=mirror,env=env,stdout=stdout,stderr=stderr)
    (r/'owned-process.json').write_text(json.dumps(dict(pid=child.pid,argv=argv,cwd=str(mirror),start_epoch=time.time(),ownership='created by this runner; no unknown processes signalled'),indent=2)+'\n')
    exit_code=child.wait()
elapsed=time.monotonic()-start
shared_post=snapshot(repo);mirror_post=snapshot(mirror)
(r/'shared-run-POST-inputs.json').write_text(json.dumps(shared_post,indent=2)+'\n')
(r/'mirror-run-POST-inputs.json').write_text(json.dumps(mirror_post,indent=2)+'\n')
contract_post={str(root):hashlib.sha256((root/contract).read_bytes()).hexdigest() for root in (repo,mirror)}
artifacts=[];excluded=[]
base=outer/'pytest'
if base.exists():
    for path in sorted(base.rglob('*')):
        if not path.is_file() or path.is_symlink():continue
        rel=path.relative_to(base)
        if rel.parts[0].startswith('parkweave-pg') or 'data' in rel.parts:
            continue
        if path.name=='host.fixture-private':
            excluded.append(dict(path=str(rel),reason='private SYNTHETIC fixture key; excluded, not read'))
            continue
        if path.suffix not in {'.json','.jsonl','.log','.png','.txt'}:continue
        dest=r/'case-artifacts'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
        artifacts.append(dict(path=str(dest.relative_to(r)),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),bytes=dest.stat().st_size))
(r/'case-artifact-manifest.json').write_text(json.dumps(dict(files=artifacts,excluded=excluded,pg_data_copied=False,private_bootstrap_copied=False),indent=2)+'\n')
result=dict(source_sha=p['source_sha'],source_tree=p['source_tree'],exit_code=exit_code,elapsed_seconds=elapsed,input_count=749,shared_pre_drift=drift(shared_pre),mirror_pre_drift=drift(mirror_pre),shared_post_drift=drift(shared_post),mirror_post_drift=drift(mirror_post),contract_pre=contract_pre,contract_post=contract_post,head_post=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),owned_pytest_process_exited=child.poll() is not None,child_process_exit_code=child.returncode,automatic_retries=0,artifact_count=len(artifacts),evidence=str(r))
if (r/'independent.xml').exists():
    tree=ET.parse(r/'independent.xml');cases=tree.findall('.//testcase')
    result.update(testcases=len(cases),unique=len({(c.get('classname'),c.get('name')) for c in cases}),failures=len(tree.findall('.//failure')),errors=len(tree.findall('.//error')),skipped=len(tree.findall('.//skipped')))
    result['passed']=sum(not any(c.find(name) is not None for name in ('failure','error','skipped')) for c in cases)
(r/'run-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2),flush=True)
raise SystemExit(exit_code)
