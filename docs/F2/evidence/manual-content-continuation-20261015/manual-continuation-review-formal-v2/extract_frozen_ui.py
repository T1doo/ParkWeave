"""Read current frozen HTML; extract named original functions for a scoped VM check."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path('/workspace/ParkWeave')
OUT = Path(__file__).resolve().parent
settings = json.loads((OUT / 'execution-config.json').read_text())
SHA = settings['source_sha']
assert settings['status'] == 'READY_FROZEN_SHA'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == SHA
freeze = json.loads((ROOT / settings['freeze_path']).read_text())
raw = (ROOT / 'src/parkweave/web.html').read_bytes()
assert hashlib.sha256(raw).hexdigest() == freeze['source_paths']['src/parkweave/web.html']
text = raw.decode()
names = ['uuidHandle', 'boundedCaseHash', 'receiptHistoryCanonical', 'coldKeys',
         'coldCanonical', 'coldDigest', 'planSourceConflictSource', 'planSourceContinuationCheck',
         'planSourceConflictHandles', 'planSourceConflictCall', 'planSourceConflictRejected',
         'planSourceConflictWrite', 'planSourceConflictReceipt', 'planSourceExactNonemptyLine']
selected = []
hashes = {}
for name in names:
    start = re.search(r'^(?:async )?function ' + re.escape(name) + r'\(', text, re.M)
    assert start is not None
    line_end = text.index('\n', start.start())
    if name == 'planSourceConflictReceipt':
        line_end = text.index('\n}\n', start.start()) + 2
    function = text[start.start():line_end]
    selected.append(function)
    hashes[name] = hashlib.sha256(function.encode()).hexdigest()
(OUT / 'frozen-ui-functions.js').write_text('\n\n'.join(selected) + '\n')
(OUT / 'frozen-ui-source.json').write_text(json.dumps(dict(source_sha=SHA,
    web_sha256=hashlib.sha256(raw).hexdigest(), functions=hashes,
    scope='Actual newly frozen functions; synthetic DOM/context/transport only; no full HTML/API/PG/browser claims.',
    previous_score_reused=False), indent=2) + '\n')
print(json.dumps(dict(status='EXTRACTED_NOT_EXECUTED', source_sha=SHA, functions=len(names),
    web_sha256=hashlib.sha256(raw).hexdigest())))
