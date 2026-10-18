from pathlib import Path
import ast,hashlib,json,subprocess,threading
root=Path('/workspace/ParkWeave');raw=root/'.runtime/service-catalog-query-20261018';base='fd181ab1564d5b8b4a2feb44d9d93da8d9df08f8'
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(name,v):(raw/name).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def original(p):return subprocess.check_output(['git','show',base+':'+p],cwd=root)
protected=['src/parkweave/'+p+'.py' for p in ['dependency_graph','unified_dependency_propagation','service_case_steps','source_change_adoption','formal_preparation_entry','native_run_access','resource_plan_approval_read','resource_approval_host_read','ordinary_runtime_read','ordinary_runtime_write','api']]+['docs/验收规格.json','docs/F1/ATBindings.json']
checks={p:dict(base_sha256=sha(original(p)),current_sha256=sha((root/p).read_bytes()),equal=original(p)==(root/p).read_bytes()) for p in protected}
p='src/parkweave/registered_dependencies.py'
def functions(b):
 text=b.decode();return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
old,new=functions(original(p)),functions((root/p).read_bytes())
for name in ['closure','impact_between','plan_proof','inspect']:
 checks[p+'::'+name]=dict(base_sha256=sha(old[name].encode()),current_sha256=sha(new[name].encode()),equal=old[name]==new[name])
assert all(c['equal'] for c in checks.values());save('protected-originals.json',dict(base_sha=base,checks=checks))
entries=[l.split('\t',1) for l in subprocess.check_output(['git','ls-tree','-r',base,'docs/F2/evidence'],cwd=root,text=True).splitlines()]
reader=subprocess.Popen(['git','cat-file','--batch'],cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
def feed():reader.stdin.write(('\n'.join(e.split()[2] for e,p in entries)+'\n').encode());reader.stdin.close()
feeder=threading.Thread(target=feed);feeder.start();inherited={}
for entry,path in entries:
 oid,kind,length=reader.stdout.readline().split();remaining=int(length);digest=hashlib.sha256()
 while remaining:
  chunk=reader.stdout.read(min(remaining,1024*1024));assert chunk;digest.update(chunk);remaining-=len(chunk)
 assert reader.stdout.read(1)==b'\n'
 with (root/path).open('rb') as current:actual=hashlib.file_digest(current,'sha256').hexdigest()
 assert oid.decode()==entry.split()[2] and kind==b'blob' and digest.hexdigest()==actual
 inherited[path]=actual
feeder.join();assert reader.wait()==0;save('inherited-evidence-before.json',dict(base_sha=base,count=len(inherited),sha256=inherited))
print(json.dumps(dict(protected_checks=len(checks),all_equal=True,inherited_evidence=len(inherited))))
