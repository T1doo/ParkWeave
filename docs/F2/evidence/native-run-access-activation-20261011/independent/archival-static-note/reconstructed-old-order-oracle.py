"""Hash-matched reconstructed old validator metadata oracle only; no exporter import, DB, browser or public mutation."""
from pathlib import Path
import ast,json
base=Path(__file__).parent
source=(base/'reconstructed-old-validator-private.py.txt').read_text()
node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name=='ids')
namespace={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(base/'reconstructed-old-validator-private.py.txt'),'exec'),namespace)
original=json.loads(Path('.runtime/native-run-access-activation-20261011/delivery-lane-a-actual-collection.json').read_text())['collected'][0]
exported=json.loads(json.dumps(original,sort_keys=True))
print('scope: original validator metadata-only oracle, not a business testcase',flush=True)
print('original object keys:',list(original),flush=True)
print('exported object keys:',list(exported),flush=True)
print('object values are structurally identical:',original==exported,flush=True)
assert namespace['ids'](original)==namespace['ids'](exported), 'validator misclassifies JSON key reordering as protected identity mutation'
