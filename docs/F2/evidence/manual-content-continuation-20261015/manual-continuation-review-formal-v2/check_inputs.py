"""Independent provenance of the new freeze, test-only repair and old raw evidence."""
from datetime import datetime, timezone
from pathlib import Path
import ast
import hashlib
import json
import subprocess

ROOT = Path('/workspace/ParkWeave')
OUT = Path(__file__).resolve().parent
settings = json.loads((OUT / 'execution-config.json').read_text())
SHA = settings['source_sha']
assert settings['status'] == 'READY_FROZEN_SHA'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


assert git('rev-parse', 'HEAD').decode().strip() == SHA
assert not git('status', '--porcelain', '--untracked-files=no')
changed = git('diff', '--name-only', settings['old_execution_sha'], SHA).decode().splitlines()
assert changed == ['tests/manual_content_continuation_real_html.js', 'tests/test_manual_content_continuation_independent.py']
freeze = json.loads((ROOT / settings['freeze_path']).read_text())
assert len(freeze['source_paths']) == 608 and len(freeze['all_tracked_sha256']) == 13252
product_paths = git('ls-files', '-z', '--', 'src', 'scripts', 'pyproject.toml').decode().split('\0')
product_paths = [p for p in product_paths if p]
for path in product_paths:
    data = (ROOT / path).read_bytes()
    assert data == git('show', settings['old_execution_sha'] + ':' + path)
    assert hashlib.sha256(data).hexdigest() == freeze['source_paths'][path]
prior = json.loads((ROOT / '.runtime/manual-continuation-review-formal/prior1048-originals-before.json').read_text())
records = {}
for path, expected in prior['records'].items():
    data = (ROOT / path).read_bytes()
    actual = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    assert actual == expected, path
    records[path] = actual
assert len(records) == 1048
(OUT / 'prior1048-originals-before.json').write_text(json.dumps(dict(status='MATCH_ALL_OLD_ARCHIVE_RAW_IDENTITIES',
    source_sha=SHA, utc=datetime.now(timezone.utc).isoformat(), records=records,
    previous_scores_reused=False), indent=2) + '\n')
plugin = OUT / 'legacy_artifact_capture.py'
assert plugin.read_bytes() == (OUT / 'preparation/legacy_artifact_capture-initial.py').read_bytes()
roots = json.loads((ROOT / '.runtime/manual-continuation-final/artifact-legacy-roots.json').read_text())
assert roots == json.loads((OUT / 'preparation/artifact-legacy-roots.json').read_text()) and len(roots) == 16
record = dict(status='PASS_INPUT_SCOPE_AND_TEST_ONLY_REPAIR_REVIEW', source_sha=SHA,
    previous_execution_sha=settings['old_execution_sha'], source_paths=608, all_tracked_paths=13252,
    actual_changed_files=changed, product_src_scripts_pyproject_paths=len(product_paths),
    all_product_bytes_equal_previous_execution=True, previous_scores_reused=False,
    fixture_repair_review=[
        'Source ABA: real two committed PG transactions; complete original row restored and xmin changed. Intermediate UNKNOWN need not expose source text.',
        'Plan ABA: real owned-PG whole-plan fault injection, complete JSON and PG text restored with xmin changed; not an original business LOCK/UNLOCK or UIgeneration test.',
        'UNKNOWN: capture complete valid requests before source loss, then current UNKNOWN supplies no action templates and both original ADOPT requests409 with zero business writes.',
        'Full HTML UNKNOWN additionally disables both buttons and invoking both handlers sends no POST; nullable continuation is allowed only in that refused state.'
    ], legacy_plugin_sha256=hashlib.sha256(plugin.read_bytes()).hexdigest(),
    same_16_test_artifact_roots=True, artifact_destination_precreated_each_window=True,
    only_artifact_Path_open_mkdir_changed=True, product_PG_HTTP_auth_assert_driver_bypass=False,
    old_1048_raw_unchanged_at_new_start=True)
(OUT / 'input-scope-and-test-repair-review.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k:v for k,v in record.items() if k not in {'fixture_repair_review'}}))
