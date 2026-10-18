from pathlib import Path
import ast,hashlib,json,subprocess,threading,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave'); raw=root/'.runtime/resource-query-members-20261018'
base='f522b6bfb4080d1fc557f1695dd6c909a61bda80'; frozen='09ea99212b8ddcc70797ec7ac2bfc1909d574a18'
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(name,value):
 (raw/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def original(path):return subprocess.check_output(['git','show',base+':'+path],cwd=root)
protected=['src/parkweave/'+p+'.py' for p in ['dependency_graph','registered_dependencies','typed_source_impact','unified_dependency_propagation','service_case_steps']]+['docs/验收规格.json','docs/F1/ATBindings.json']
proof={p:dict(base_sha256=sha(original(p)),current_sha256=sha((root/p).read_bytes()),equal=original(p)==(root/p).read_bytes()) for p in protected}
path='src/parkweave/source_change_adoption.py'
def functions(b):
 text=b.decode();return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
old,new=functions(original(path)),functions((root/path).read_bytes())
for name in ['build','validate_history','typed_dependency_preview']:
 proof[path+'::'+name]=dict(base_sha256=sha(old[name].encode()),current_sha256=sha(new[name].encode()),equal=old[name]==new[name])
assert all(v['equal'] for v in proof.values());save('protected-originals.json',dict(base_sha=base,frozen_sha=frozen,checks=proof))
f=raw/'frozen-09ea9921'; result=json.loads((f/'result.json').read_text());collection=json.loads((f/'collection.json').read_text());calls=[json.loads(l) for l in (f/'calls.jsonl').read_text().splitlines()]; xml=ET.parse(f/'results.xml');cases=xml.findall('.//testcase');origins=json.loads((f/'module-origins.json').read_text());pre=json.loads((f/'shared-before.json').read_text());mirror=Path(result['mirror'])
assert len(collection)==len(set(collection))==16
assert len(cases)==16 and not xml.findall('.//failure') and not xml.findall('.//error') and not xml.findall('.//skipped')
for phase in ['setup','call','teardown']:
 rows=[r for r in calls if r['when']==phase];assert len(rows)==16 and {r['nodeid'] for r in rows}==set(collection) and all(r['outcome']=='passed' for r in rows)
origin_checks={name:dict(within_mirror=v['within_mirror'],matches_input=pre.get(str(Path(v['path']).relative_to(mirror)))==v['sha256']) for name,v in origins.items()}
assert all(v['within_mirror'] and v['matches_input'] for v in origin_checks.values())
save('module-source-validation.json',dict(frozen_sha=frozen,count=len(origins),checks=origin_checks))
save('counting-verification.json',dict(frozen_sha=frozen,unique_collection=16,setup_passed=16,call_passed=16,teardown_passed=16,junit_passed=16,failures=0,errors=0,skipped=0,selected_inputs=len(pre),shared_and_mirror_pre_post_equal=all(json.loads((f/p).read_text())==pre for p in ['shared-after.json','mirror-before.json','mirror-after.json']),module_origins=len(origins),all_origins_match_mirror_input=True,old_matrices_rerun=False,browser_requested=False,collection=collection))
entries=[line.split('\t',1) for line in subprocess.check_output(['git','ls-tree','-r',base,'docs/F2/evidence'],cwd=root,text=True).splitlines()]
objects=[entry.split()[2] for entry,path in entries]
reader=subprocess.Popen(['git','cat-file','--batch'],cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
def feed():
 reader.stdin.write(('\n'.join(objects)+'\n').encode());reader.stdin.close()
feeder=threading.Thread(target=feed);feeder.start();inherited={}
for entry,path in entries:
 oid,kind,length=reader.stdout.readline().split();length=int(length);digest=hashlib.sha256();remaining=length
 while remaining:
  chunk=reader.stdout.read(min(remaining,1024*1024));assert chunk;digest.update(chunk);remaining-=len(chunk)
 assert reader.stdout.read(1)==b'\n'
 with (root/path).open('rb') as current:current_digest=hashlib.file_digest(current,'sha256').hexdigest()
 assert oid.decode()==entry.split()[2] and kind==b'blob' and digest.hexdigest()==current_digest
 inherited[path]=current_digest
feeder.join();assert reader.wait()==0;save('inherited-evidence-before.json',dict(base_sha=base,count=len(inherited),sha256=inherited))
print(json.dumps(dict(protected_checks=len(proof),all_equal=True,passed=len(collection),module_origins=len(origins),inherited_evidence=len(inherited))))
