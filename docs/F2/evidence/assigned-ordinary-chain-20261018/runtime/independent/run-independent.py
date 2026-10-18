"""One authorized, unmodified three-node run in an exact frozen mirror."""
import hashlib,io,json,os,pathlib,shlex,shutil,subprocess,sys,tarfile,tempfile,time

ROOT=pathlib.Path('/workspace/ParkWeave')
DEST=ROOT/'.runtime/assigned-demo-chain-20261018/independent'
SHA='d0045f14699857f8cd4ba254505abe9fa0fc982e'
EXPECTED=[
 'tests/test_assigned_demo_chain_browser.py::test_existing_assigned_run_original_ordinary_DOM_full_chain_and_restart[1200]',
 'tests/test_assigned_demo_chain_browser.py::test_existing_assigned_run_original_ordinary_DOM_full_chain_and_restart[320]',
 'tests/test_local_synthetic_demo.py::test_missing_run_assignment_stops_original_dispatch_without_creating_authority',
]

def dump(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def git(*args):
 return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def manifest_at(base,expected):
 return {p:hashlib.sha256((base/p).read_bytes()).hexdigest() if (base/p).is_file() else None for p in expected}

assert git('rev-parse','HEAD')==SHA
expected=json.loads((ROOT/'.runtime/assigned-demo-chain-20261018/final-inputs.json').read_text())
assert len(expected)==741
outer=pathlib.Path(tempfile.mkdtemp(prefix='pw-ind-assigned-d004-'))
mirror=outer/'mirror';mirror.mkdir()
raw=subprocess.check_output(['git','archive',SHA,'--','src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md'],cwd=ROOT)
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
 archive.extractall(mirror,filter='data')
run=DEST/outer.name;run.mkdir()
dump(DEST/'current-run.json',dict(source_sha=SHA,run=str(run),outer=str(outer),mirror=str(mirror)))
before=dict(source_sha=git('rev-parse','HEAD'),src_tree=git('rev-parse','HEAD:src'),expected=expected,
 shared_actual=manifest_at(ROOT,expected),mirror_actual=manifest_at(mirror,expected))
dump(run/'pre-source.json',before)
assert before['shared_actual']==expected and before['mirror_actual']==expected
dump(run/'expected-nodes.json',EXPECTED)
observer=outer/'observer';observer.mkdir()
plugin=DEST/'independent_artifact_observer.py'
shutil.copyfile(plugin,observer/plugin.name)
shutil.copyfile(plugin,run/(plugin.name+'.txt'))
env={name:os.environ[name] for name in ('PATH','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','TMPDIR','LANG','LC_ALL','TZ') if name in os.environ}
env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join(map(str,[observer,mirror/'src',mirror/'tests',mirror])),INDEPENDENT_ASSIGNED_EVIDENCE=str(run))
argv=[str(ROOT/'.venv/bin/python'),'-B','-m','pytest','-q','-v','-p','no:cacheprovider','-p','independent_artifact_observer',
 '--rootdir='+str(mirror),'--basetemp='+str(outer/'pytest'),'--junitxml='+str(run/'independent.xml'),
 'tests/test_assigned_demo_chain_browser.py',EXPECTED[-1]]
started=time.time()
inv=dict(source_sha=SHA,cwd=str(mirror),argv=argv,env=env,expected_node_count=3,execution_count=1,
 retry_policy='No automatic retry',started=started,mirror=str(mirror),outer=str(outer),
 observer_scope='Only record collected nodes, copy pre-existing proof/log/PNG artifacts after teardown, and record loaded module file origins. No product functions or test budgets/assertions altered.')
dump(run/'invocation.json',inv)
(run/'command.txt').write_text('cd '+shlex.quote(str(mirror))+'\n'+shlex.join(argv)+'\n')
print(json.dumps(dict(status='STARTING',source_sha=SHA,run=str(run),outer=str(outer),argv=argv)),flush=True)
with (run/'stdout.txt').open('w') as stdout,(run/'stderr.txt').open('w') as stderr:
 process=subprocess.Popen(argv,cwd=mirror,env=env,stdout=stdout,stderr=stderr)
 dump(run/'owned-process.json',dict(pid=process.pid,argv=argv,cwd=str(mirror),source_sha=SHA))
 exit_code=process.wait()
elapsed=time.time()-started
after=dict(source_sha=git('rev-parse','HEAD'),src_tree=git('rev-parse','HEAD:src'),
 shared_actual=manifest_at(ROOT,expected),mirror_actual=manifest_at(mirror,expected))
dump(run/'post-source.json',after)
drift={scope:[p for p,h in expected.items() if after[scope+'_actual'].get(p)!=h] for scope in ('shared','mirror')}
result=dict(source_sha=SHA,exit_code=exit_code,elapsed_seconds=elapsed,expected_node_count=3,
 shared_input_count=len(expected),mirror_input_count=len(expected),shared_drift=drift['shared'],mirror_drift=drift['mirror'],
 head_unchanged=after['source_sha']==SHA,src_tree_unchanged=before['src_tree']==after['src_tree'],run=str(run),outer=str(outer))
dump(run/'run-result.json',result)
print(json.dumps(result),flush=True)
sys.exit(exit_code)
