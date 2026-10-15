"""Append current delivery status ahead of byte-exact repository history."""
from pathlib import Path
import json,hashlib
root=Path.cwd();o=root/'.runtime/multifield-source-root';freeze=json.loads((o/'freeze.json').read_text());reg=json.loads((o/'final-regression-verification.json').read_text());assert reg['status']=='PASS'
section=(o/'history-prefix-final.md').read_bytes();assert section.startswith('## 2026-10-15'.encode())
paths=['docs/Plan.md','docs/F2/Plan.md','docs/F2/Log.md','docs/DeliveryCriticalPath-20261010.md'];records=[]
for name in paths:
 p=root/name;original=p.read_bytes();assert hashlib.sha256(original).hexdigest()==freeze['all_tracked_sha256'][name]
 prefix=section.replace(b'F2/MultifieldSourceConflict-20261015.md',b'MultifieldSourceConflict-20261015.md') if name.startswith('docs/F2/') else section
 p.write_bytes(prefix+b'\n'+original);assert p.read_bytes().endswith(original)
 records.append(dict(path=name,original_sha256=hashlib.sha256(original).hexdigest(),old_bytes=len(original),new_bytes=p.stat().st_size,original_exact_suffix=True))
delivery=root/'.runtime/multifield-source-delivery';delivery.mkdir(exist_ok=True)
(delivery/'history-prefix-receipt.json').write_text(json.dumps(records,indent=2)+'\n')
print('four history files prefixed; original bytes exact suffix')
