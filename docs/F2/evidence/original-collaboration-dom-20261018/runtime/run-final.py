from pathlib import Path
import hashlib,json,os,subprocess,time,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');r=root/'.runtime/original-collaboration-dom-20261018';freeze=json.loads((r/'freeze.json').read_text());mirror=Path(freeze['mirror']);outer=Path(freeze['outer']);expected=json.loads((r/'frozen-inputs.json').read_text())
assert not (r/'final-result.json').exists() and not (r/'final-owned-process.json').exists(),'one execution only'
def snapshot(base):return {name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in expected}
def drift(actual):return [name for name in expected if actual[name]!=expected[name]]
pre={str(base):snapshot(base) for base in (root,mirror)}
assert all(not drift(values) for values in pre.values())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==freeze['source_sha']
(r/'final-PRE-inputs.json').write_text(json.dumps(pre,indent=2)+'\n')
osnames={'PATH','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','TMPDIR','LANG','LC_ALL','TZ'}
env={name:os.environ[name] for name in osnames if name in os.environ}
env.update(PYTHONPATH=os.pathsep.join(str(mirror/name) for name in ('tests','src','.')),PYTHONDONTWRITEBYTECODE='1',PW_COLLABORATION_EVIDENCE=str(r))
args=['-q','-p','no:cacheprovider','--rootdir='+str(mirror),'--basetemp='+str(outer/'pytest'),'--junitxml='+str(r/'final.xml'),'--owned-connection-diagnostics='+str(r/'final-connections'),*['tests/'+name+'.py' for name in freeze['modules']]]
argv=[str(root/'.venv/bin/python'),'-B',str(r/'final-observer.py'),*args]
inv=dict(source_sha=freeze['source_sha'],source_tree=freeze['source_tree'],tests_tree=freeze['tests_tree'],argv=argv,cwd=str(mirror),basetemp=str(outer/'pytest'),started=time.time(),automatic_retries=0,environment=env)
(r/'final-invocation.json').write_text(json.dumps(inv,indent=2)+'\n');start=time.monotonic()
with (r/'final.log').open('w') as log:
    child=subprocess.Popen(argv,cwd=mirror,env=env,stdout=log,stderr=subprocess.STDOUT)
    (r/'final-owned-process.json').write_text(json.dumps(dict(pid=child.pid,argv=argv,cwd=str(mirror),ownership='created by this runner'),indent=2)+'\n')
    code=child.wait()
post={str(base):snapshot(base) for base in (root,mirror)};(r/'final-POST-inputs.json').write_text(json.dumps(post,indent=2)+'\n')
result=dict(source_sha=freeze['source_sha'],source_tree=freeze['source_tree'],tests_tree=freeze['tests_tree'],exit_code=code,elapsed_seconds=time.monotonic()-start,input_count=len(expected),PRE_drift={name:drift(values) for name,values in pre.items()},POST_drift={name:drift(values) for name,values in post.items()},automatic_retries=0,owned_pytest_exit_code=child.returncode)
if (r/'final.xml').exists():
    tree=E.parse(r/'final.xml');cases=tree.findall('.//testcase');result.update(testcases=len(cases),unique=len({(c.get('classname'),c.get('name')) for c in cases}),passed=sum(not any(c.find(tag) is not None for tag in ('failure','error','skipped')) for c in cases),failures=len(tree.findall('.//failure')),errors=len(tree.findall('.//error')),skipped=len(tree.findall('.//skipped')))
(r/'final-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(code)
