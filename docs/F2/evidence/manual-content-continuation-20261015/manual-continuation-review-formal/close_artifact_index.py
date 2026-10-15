"""Close this review window without exporting or changing raw evidence."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

ROOT = Path('/workspace/ParkWeave')
OUT = ROOT / '.runtime/manual-continuation-review-formal'
excluded = {'final-artifact-index.json', 'artifact-close.log'}
public_candidates = []
private_files = []
for path in sorted(OUT.rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts or 'pytest-cache' in path.parts:
        continue
    rel = str(path.relative_to(OUT))
    if rel in excluded:
        continue
    raw = path.read_bytes()
    item = dict(path=str(path.relative_to(ROOT)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    if path.name.endswith('.private.json'):
        item['publish'] = False
        private_files.append(item)
    else:
        public_candidates.append(item)
record = dict(status='REVIEW_WINDOW_CLOSED_PRIMARY_ARCHIVE_NOT_YET_GENERATED',
    source_sha='ef16f7c380a3d25a55bf42b208d3e579fcb0e068', utc=datetime.now(timezone.utc).isoformat(),
    source_writes=False, Git_writes=False, formal_test_processes_complete=True,
    raw_files=public_candidates, private_registry_files=private_files,
    files_are_raw_not_privacy_sanitized_exports=True,
    public_copy_requires_independent_primary_export_redaction_and_residual_gate=True,
    index_self_excluded=True, index_tool_stdout_excluded=True,
    archive_independent_reconstruction='NOT_RUN_AWAIT_EXPLICIT_ARCHIVE_GENERATED_SIGNAL',
    frozen_scope='14 complete modules404PASS; supplemental10pytestPASS(8 actual API/PG seams-locks-budgets and2 success-receipt/in-memory48check fixtures);4 synthetic extracted-function VM checks.')
(OUT / 'final-artifact-index.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(status=record['status'], indexed_raw_files=len(public_candidates),
    private_registry_files=len(private_files), private_values_printed=False)))
