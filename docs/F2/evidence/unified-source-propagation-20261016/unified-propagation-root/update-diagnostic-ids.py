from pathlib import Path
import ast,json
ids=set()
for path in Path('tests').glob('test_*.py'):
 for node in ast.parse(path.read_text(encoding='utf-8')).body:
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):ids.add(str(path)+'::'+node.name)
  elif isinstance(node,ast.ClassDef) and node.name[0].isalpha() and node.name.isascii():
   for method in node.body:
    if isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)) and method.name.startswith('test_'):ids.add(str(path)+'::'+node.name+'::'+method.name)
assert len(ids)<=3000
Path('scripts/windows_ci/diagnostic-test-ids.json').write_text(json.dumps(dict(schema=1,test_ids=sorted(ids)),indent=2)+'\n')
print(len(ids),'diagnostic IDs; original 3000 ceiling unchanged')
