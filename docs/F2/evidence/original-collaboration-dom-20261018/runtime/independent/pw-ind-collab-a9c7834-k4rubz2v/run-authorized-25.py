from pathlib import Path
import hashlib,json,os,shutil,subprocess,time,xml.etree.ElementTree as ET
r=Path(__file__).resolve().parent
p=json.loads((r/'preparation.json').read_text());repo=Path(p['repository']);mirror=Path(p['mirror']);outer=Path(p['outer'])
assert (r/'START-authorized.json').exists(),'Do not start until parent explicitly authorizes START'
assert not (r/'run-result.json').exists() and not (r/'owned-process.json').exists(),'one pytest execution only'
expected=json.loads((r/'expected-inputs.json').read_text());nodes=json.loads((r/'expected-25-nodes.json').read_text())
def snapshot(root):return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in expected}
def drift(actual):return [name for name in expected if actual[name]!=expected[name]]
shared_pre=snapshot(repo);mirror_pre=snapshot(mirror)
assert not drift(shared_pre) and not drift(mirror_pre)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==p['source_sha']
contract_pre={str(root):{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in p['contracts']} for root in (repo,mirror)}
assert all(x==p['contracts'] for x in contract_pre.values())
(r/'shared-run-PRE-inputs.json').write_text(json.dumps(shared_pre,indent=2)+'\n');(r/'mirror-run-PRE-inputs.json').write_text(json.dumps(mirror_pre,indent=2)+'\n')
osnames={'PATH','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','TMPDIR','LANG','LC_ALL','TZ'}
env={name:os.environ[name] for name in osnames if name in os.environ}
env.update(PYTHONPATH=os.pathsep.join(str(mirror/name) for name in ('src','tests','.')),PYTHONDONTWRITEBYTECODE='1',PW_REVIEW_EVIDENCE=str(r),FRONTIER_ARTIFACT_ROOT=str(outer/'pytest/frontier-artifacts'))
args=['-q','-p','no:cacheprovider','--owned-connection-diagnostics='+str(r/'owned-connection-diagnostics'),'--rootdir='+str(mirror),'--basetemp='+str(outer/'pytest'),'--junitxml='+str(r/'independent.xml'),*nodes]
argv=[str(repo/'.venv/bin/python'),'-B',str(r/'pytest-observer.py'),*args]
inv=dict(source_sha=p['source_sha'],source_tree=p['source_tree'],tests_tree=p['tests_tree'],argv=argv,pytest_args=args,cwd=str(mirror),environment=env,started_utc_epoch=time.time(),automatic_retries=0,authorized_expected=25,basetemp=str(outer/'pytest'),origin_scope='pytest sys.modules actual files only; child API/Node/worker not additionally origin-instrumented')
(r/'invocation.json').write_text(json.dumps(inv,indent=2)+'\n');start=time.monotonic()
with (r/'stdout.txt').open('w') as stdout,(r/'stderr.txt').open('w') as stderr:
    child=subprocess.Popen(argv,cwd=mirror,env=env,stdout=stdout,stderr=stderr)
    (r/'owned-process.json').write_text(json.dumps(dict(pid=child.pid,argv=argv,cwd=str(mirror),start_epoch=time.time(),ownership='created by this runner; no unknown processes signalled'),indent=2)+'\n')
    exit_code=child.wait()
elapsed=time.monotonic()-start
shared_post=snapshot(repo);mirror_post=snapshot(mirror)
(r/'shared-run-POST-inputs.json').write_text(json.dumps(shared_post,indent=2)+'\n');(r/'mirror-run-POST-inputs.json').write_text(json.dumps(mirror_post,indent=2)+'\n')
contract_post={str(root):{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in p['contracts']} for root in (repo,mirror)}
artifacts=[];excluded=[]
def archive(base,prefix):
    if not base.exists():return
    for path in sorted(base.rglob('*')):
        if not path.is_file() or path.is_symlink():continue
        rel=path.relative_to(base)
        if any(part.startswith('parkweave-pg') or part=='data' for part in rel.parts):continue
        if path.name=='host.fixture-private' or path.name.endswith('.private.json') or 'token' in path.name.lower():
            excluded.append(dict(path=str(prefix/rel),reason='private bootstrap/token artifact; not read or copied'));continue
        if path.suffix not in {'.json','.jsonl','.log','.png','.txt','.xml'}:continue
        dest=r/'case-artifacts'/prefix/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
        artifacts.append(dict(path=str(dest.relative_to(r)),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),bytes=dest.stat().st_size))
archive(outer/'pytest',Path('pytest'))
for name in p['legacy_output_directories']:archive(mirror/'.runtime'/name,Path('mirror-runtime')/name)
(r/'case-artifact-manifest.json').write_text(json.dumps(dict(files=artifacts,excluded=excluded,pg_data_copied=False,private_bootstrap_copied=False,private_json_or_token_files_copied=False),indent=2)+'\n')
result=dict(source_sha=p['source_sha'],source_tree=p['source_tree'],tests_tree=p['tests_tree'],exit_code=exit_code,elapsed_seconds=elapsed,input_count=len(expected),shared_pre_drift=drift(shared_pre),mirror_pre_drift=drift(mirror_pre),shared_post_drift=drift(shared_post),mirror_post_drift=drift(mirror_post),contract_pre=contract_pre,contract_post=contract_post,head_post=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),owned_pytest_process_exited=child.poll() is not None,child_process_exit_code=child.returncode,automatic_retries=0,artifact_count=len(artifacts),evidence=str(r))
if (r/'independent.xml').exists():
    tree=ET.parse(r/'independent.xml');cases=tree.findall('.//testcase')
    result.update(testcases=len(cases),unique=len({(c.get('classname'),c.get('name')) for c in cases}),failures=len(tree.findall('.//failure')),errors=len(tree.findall('.//error')),skipped=len(tree.findall('.//skipped')))
    result['passed']=sum(not any(c.find(name) is not None for name in ('failure','error','skipped')) for c in cases)
(r/'run-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
raise SystemExit(exit_code)
