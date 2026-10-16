import ast,json,hashlib
from pathlib import Path
root=Path.cwd();base=root/'src/parkweave';targets={'service_dispatches':{'Offer','Command','Reassign'},'executor_receipts':{'Create','Command'},'case_lifecycle':{'Command'},'isolated_local_execution':{'ExecuteLocal'}};rows=[]
for path in sorted(base.glob('*.py')):
 text=path.read_text();tree=ast.parse(text);aliases={};direct={}
 for n in ast.walk(tree):
  if isinstance(n,ast.ImportFrom):
   if not n.module:
    for a in n.names:
     if a.name in targets:aliases[a.asname or a.name]=a.name
   elif n.module.split('.')[-1] in targets:
    module=n.module.split('.')[-1]
    for a in n.names:
     if a.name in targets[module]:direct[a.asname or a.name]=(module,a.name)
  elif isinstance(n,ast.Import):
   for a in n.names:
    if a.name.split('.')[-1] in targets:aliases[a.asname or a.name]=a.name.split('.')[-1]
 parents={c:n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
 for n in ast.walk(tree):
  if not isinstance(n,ast.Call):continue
  f=n.func;target=None
  if isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name) and f.value.id in aliases and f.attr in targets[aliases[f.value.id]]:target=(aliases[f.value.id],f.attr)
  if isinstance(f,ast.Name) and f.id in direct:target=direct[f.id]
  if target is None:continue
  scope=n
  while scope in parents and not isinstance(scope,(ast.FunctionDef,ast.AsyncFunctionDef)):scope=parents[scope]
  dumps=[dict(line=x.lineno,text=ast.get_source_segment(text,x)) for x in ast.walk(scope) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='model_dump']
  rows.append(dict(path=str(path.relative_to(root)),line=n.lineno,target='.'.join(target),constructor=ast.get_source_segment(text,n),function=getattr(scope,'name','module'),model_dumps_in_same_function=dumps))
out=Path('.runtime/frontier-review/cross-module-dto-sweep-v1/inventory.json');out.write_text(json.dumps(dict(status='STATIC_ONLY',files_scanned=len(list(base.glob('*.py'))),constructor_sites=rows),indent=2)+'\n');print(json.dumps(dict(files=len(list(base.glob('*.py'))),sites=len(rows),sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
