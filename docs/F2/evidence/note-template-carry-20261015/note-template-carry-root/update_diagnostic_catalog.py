from pathlib import Path
import ast,json,hashlib
p=Path('scripts/windows_ci/diagnostic-test-ids.json');before=p.read_bytes();ids=set()
for path in Path('tests').glob('test_*.py'):
 for node in ast.parse(path.read_text(encoding='utf-8')).body:
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):ids.add(str(path)+'::'+node.name)
  elif isinstance(node,ast.ClassDef) and node.name[0].isalpha() and node.name.isascii():
   for method in node.body:
    if isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)) and method.name.startswith('test_'):ids.add(str(path)+'::'+node.name+'::'+method.name)
old=json.loads(before);p.write_text(json.dumps(dict(schema=1,test_ids=sorted(ids)),ensure_ascii=False,indent=2)+'\n');after=p.read_bytes()
report=dict(before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(after).hexdigest(),before_count=len(old['test_ids']),after_count=len(ids),added=sorted(ids-set(old['test_ids'])),removed=sorted(set(old['test_ids'])-ids),byte_size=len(after),windows_executed=False)
Path('.runtime/note-template-carry-root/catalog-update.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['added','removed']}))
