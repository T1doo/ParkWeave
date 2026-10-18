"""One authorized 77-node run in the previously prepared exact 0ec816f mirror."""
import hashlib,json,os,pathlib,shlex,shutil,subprocess,sys,time,xml.etree.ElementTree as E

ROOT=pathlib.Path('/workspace/ParkWeave')
R=ROOT/'.runtime/dispatch-accept-recovery-20261018'
DEST=R/'independent'
SHA='0ec816ff566ad4b9966229f5eb82123f5b984693'
def digest(data):return hashlib.sha256(data).hexdigest()
def dump(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def manifest_at(base,expected):
 return {p:digest((base/p).read_bytes()) if (base/p).is_file() else None for p in expected}
def head():return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()

loc=json.loads((DEST/'current-run.json').read_text());assert loc['source_sha']==SHA and head()==SHA
run=pathlib.Path(loc['run']);mirror=pathlib.Path(loc['mirror']);outer=pathlib.Path(loc['outer'])
assert not (run/'invocation.json').exists(), 'No automatic or accidental repeat execution'
expected=json.loads((R/'final-focused-A-inputs.json').read_text())
assert expected==json.loads((R/'final-focused-B-inputs.json').read_text()) and len(expected)==745
pre=dict(source_sha=SHA,src_tree=subprocess.check_output(['git','rev-parse','HEAD:src'],cwd=ROOT,text=True).strip(),
 input_count=len(expected),expected=expected,shared_actual=manifest_at(ROOT,expected),mirror_actual=manifest_at(mirror,expected))
assert pre['expected']==pre['shared_actual']==pre['mirror_actual']
assert pre['src_tree']=='e0f8443127b49b5feb9e1b880e8998ca67b5c404'
dump(run/'execution-pre-source.json',pre)
planned=json.loads((run/'planned-selectors.json').read_text());selectors=planned['selectors']
parent_nodes=[];parent_inputs={}
for label in ('final-focused-A','final-focused-B'):
 p=R/(label+'.xml');parent_inputs[str(p)]=digest(p.read_bytes());tree=E.parse(p)
 assert not tree.findall('.//failure') and not tree.findall('.//error') and not tree.findall('.//skipped')
 for case in tree.findall('.//testcase'):
  parent_nodes.append(case.get('classname').replace('.','/')+'.py::'+case.get('name'))
assert len(parent_nodes)==len(set(parent_nodes))==161
nodes=[];counts=[]
for selector in selectors:
 selected=[n for n in parent_nodes if n==selector or ('::' not in selector and n.startswith(selector+'::'))]
 nodes.extend(selected);counts.append(len(selected))
assert counts==[31,31,5,9,1] and len(nodes)==len(set(nodes))==77
dump(run/'expected-nodes.json',nodes)
dump(run/'parent-overlap-inputs.json',dict(source_sha=SHA,accepted_summary=json.loads((R/'accepted-tests.json').read_text()),
 focused_node_count=161,focused_nodes=parent_nodes,parent_xml_sha256=parent_inputs,expected_group_counts=counts,
 expected_nodes=nodes,all77_overlap=True,additional_unique_tests=0))
observer=outer/'observer';observer.mkdir(exist_ok=True)
plugin=DEST/'accept_evidence_observer.py';shutil.copyfile(plugin,observer/plugin.name);shutil.copyfile(plugin,run/(plugin.name+'.txt'))
env={name:os.environ[name] for name in ('PATH','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','TMPDIR','LANG','LC_ALL','TZ') if name in os.environ}
env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join(map(str,[observer,mirror/'src',mirror/'tests',mirror])),INDEPENDENT_ACCEPT_EVIDENCE=str(run))
argv=[str(ROOT/'.venv/bin/python'),'-B','-m','pytest','-q','-v','-p','no:cacheprovider','-p','accept_evidence_observer',
 '--rootdir='+str(mirror),'--basetemp='+str(outer/'pytest'),'--junitxml='+str(run/'independent.xml'),*selectors]
started=time.time()
inv=dict(source_sha=SHA,src_tree=pre['src_tree'],cwd=str(mirror),argv=argv,env=env,started=started,
 expected_node_count=77,execution_count=1,retry_policy='No automatic retry; original assertions/timeouts unchanged',
 observer_scope='Record collected nodes, original phase results and loaded pytest module origins; copy original existing non-PG artifacts after teardown. No product/test patches, added business requests, screenshots or timeout changes.')
dump(run/'invocation.json',inv);(run/'command.txt').write_text('cd '+shlex.quote(str(mirror))+'\n'+shlex.join(argv)+'\n')
print(json.dumps(dict(status='STARTING',source_sha=SHA,run=str(run),mirror=str(mirror),expected_node_count=77)),flush=True)
with (run/'stdout.txt').open('w') as stdout,(run/'stderr.txt').open('w') as stderr:
 process=subprocess.Popen(argv,cwd=mirror,env=env,stdout=stdout,stderr=stderr)
 dump(run/'owned-process.json',dict(pid=process.pid,argv=argv,cwd=str(mirror)))
 exit_code=process.wait()
post=dict(source_sha=head(),src_tree=subprocess.check_output(['git','rev-parse','HEAD:src'],cwd=ROOT,text=True).strip(),
 shared_actual=manifest_at(ROOT,expected),mirror_actual=manifest_at(mirror,expected))
dump(run/'execution-post-source.json',post)
drifts={key:[p for p,h in expected.items() if post[key+'_actual'].get(p)!=h] for key in ('shared','mirror')}
result=dict(source_sha=SHA,src_tree=pre['src_tree'],exit_code=exit_code,elapsed_seconds=time.time()-started,
 expected_node_count=77,shared_input_count=745,mirror_input_count=745,shared_drift=drifts['shared'],mirror_drift=drifts['mirror'],
 head_unchanged=post['source_sha']==SHA,src_tree_unchanged=post['src_tree']==pre['src_tree'],run=str(run),outer=str(outer))
dump(run/'run-result.json',result);print(json.dumps(result),flush=True)
sys.exit(exit_code)
