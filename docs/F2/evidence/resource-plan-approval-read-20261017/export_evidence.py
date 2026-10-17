"""Closed-file evidence export. Preserve JSON keys and JUnit identities exactly.

Run only after final-v2 exits. No fixture credential/key files or PG data are read.
Private originals are retained. The output is a new directory, never an overwrite.
"""
from pathlib import Path
import collections
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path('/workspace/ParkWeave')
PRIVATE = ROOT / '.runtime/resource-plan-approval-read'
TARGET = ROOT / 'docs/F2/evidence/resource-plan-approval-read-20261017'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strict(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('non-JSON constant: ' + value)
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid)


def shape(value):
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [shape(item) for item in value]
    return type(value).__name__


try:
    strict(b'{"ordinary_key":1,"ordinary_key":2}')
except ValueError:
    pass
else:
    raise AssertionError('duplicate-key guard failed')

freeze = strict((PRIVATE / 'freeze-v2.json').read_bytes())
assert all(sha((ROOT / path).read_bytes()) == digest for path, digest in freeze['files'].items())
assert not TARGET.exists(), 'new archive only'
nodes = strict((PRIVATE / 'final-v2-nodes.json').read_bytes())
meta = strict((PRIVATE / 'final-v2-invocation.json').read_bytes())
assert meta['exit_code'] == 0 and meta['source_sha'] == freeze['source_sha']
assert meta['uncommitted_source_diff_sha256'] == sha(b'')
assert meta['diagnostic_instrumentation'] is False


def junit(path):
    root = ET.parse(path).getroot()
    cases = root.findall('.//testcase')
    ids = ['tests/' + item.get('classname').split('.')[-1] + '.py::' + item.get('name') for item in cases]
    counts = collections.Counter(ids)
    return dict(testcase_elements=len(cases), unique=len(counts), duplicate_testcase_ids=[key for key, count in counts.items() if count > 1],
                failure=len(root.findall('.//failure')), errors=len(root.findall('.//error')),
                skipped=len(root.findall('.//skipped')),
                seconds=sum(float(suite.get('time', '0')) for suite in root.findall('.//testsuite'))), ids


final, actual = junit(PRIVATE / 'final-v2.xml')
assert actual == nodes and final['unique'] == final['testcase_elements'] == 143
assert not any(final[key] for key in ('failure', 'errors', 'skipped', 'duplicate_testcase_ids'))
assert len(set(nodes)) == 143
windows = {}
for name in ('dev-v1', 'dev-v2', 'dev-v3', 'edge-v1', 'final-v1', 'fix-v1', 'fix-v2', 'final-v2'):
    windows[name] = junit(PRIVATE / (name + '.xml'))[0]
    windows[name]['not_added_to_final_unique_count'] = name != 'final-v2'
assert windows['final-v1']['unique'] == 141
assert windows['fix-v1']['failure'] == 1 and windows['fix-v2']['failure'] == 0

preserved = strict((PRIVATE / 'preservation-pre-delivery.json').read_bytes())
inherited = strict((PRIVATE / 'inherited-archive-blobs.json').read_bytes())
# Batch Git-object hashing in one process: inherited files must retain exact bytes.
for path, blob in inherited.items():
    data = (ROOT / path).read_bytes()
    assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == blob
for path in freeze['old_algorithms_unchanged']:
    assert subprocess.check_output(['git', 'show', freeze['base_sha'] + ':' + path], cwd=ROOT) == (ROOT / path).read_bytes()

names = [
    'preflight.json', 'process-observation.json', 'ancestry.json', 'remote-before.txt', 'remote-pre-delivery.txt',
    'preservation-pre-delivery.json', 'inherited-archive-blobs.json',
    'freeze.json', 'freeze-v2.json', 'failure-ledger.json',
    'final-collection.txt', 'final-v2-collection.txt', 'final-v2-nodes.json',
    'archive-field-correction.json', 'run-window.py', 'export_evidence.py', 'write_report.py', 'verify_delivery.py',
]
for window in windows:
    names.extend([window + '.log', window + '.xml'])
    invocation = window + '-invocation.json'
    if (PRIVATE / invocation).is_file():
        names.append(invocation)
sources = [(PRIVATE / name, name) for name in names]
# Only explicit ordinary API logs and screenshots, never PG storage, session files,
# bearer maps, fixture MACs/keys, protected host configs, or arbitrary temp JSON.
for window in windows:
    temp = Path('/tmp') / ('parkweave-resource-approval-' + window)
    if temp.exists():
        for file in sorted(temp.rglob('*')):
            if file.is_file() and not file.is_symlink() and (file.name == 'ordinary-api.log' or file.suffix == '.png'):
                sources.append((file, 'browser/' + window + '/' + str(file.relative_to(temp))))
assert all(path.is_file() for path, _ in sources)

token = re.compile(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
known = {'expected_service_id-SYNTHETIC-other-service',
         'held_connection_closed_before_sessionfinish', 'owned_pytest_and_writer_proc_entries_absent'}
for name in freeze['files']:
    try:
        known.update(token.findall((ROOT / name).read_text()))
    except UnicodeDecodeError:
        pass
for original, relative in sources:
    if original.suffix == '.xml':
        for item in ET.fromstring(original.read_bytes()).findall('.//testcase'):
            known.update(token.findall(item.get('classname', '')))
            known.update(token.findall(item.get('name', '')))
    if original.name.endswith('collection.txt'):
        for line in original.read_text().splitlines():
            if line.startswith('tests/') and '::' in line:
                known.update(token.findall(line))
for name in ('export_evidence.py', 'run-window.py', 'write_report.py', 'verify_delivery.py'):
    known.update(token.findall((PRIVATE / name).read_text()))

redactions = 0


def redact_text(value, *, failure_text=False):
    global redactions
    def replace(match):
        global redactions
        if match[0] in known:
            return match[0]
        redactions += 1
        return '[SYNTHETIC_SESSION_REDACTED]'
    result = token.sub(replace, value)
    if failure_text:
        # Pytest repr can abbreviate a bearer; remove the entire displayed value.
        def bearer(match):
            global redactions
            redactions += 1
            return match[1] + "'[SYNTHETIC_SESSION_REDACTED]'"
        result = re.sub(r"('(?:fixture-[abc]|prep-specialist-fixture-[abc]|unassigned)'\s*:\s*)'[^']*'", bearer, result)
    return result


def values_only(value):
    if isinstance(value, dict):
        # Keys are schema, never pass them through a token regex.
        return {key: values_only(item) for key, item in value.items()}
    if isinstance(value, list):
        return [values_only(item) for item in value]
    return redact_text(value) if isinstance(value, str) else value


def xml_identity(raw):
    root = ET.fromstring(raw)
    return [(item.tag, {key: value for key, value in item.attrib.items() if key != 'message'}) for item in root.iter()]


TARGET.mkdir(parents=True)
pairs = []
for original, relative in sources:
    raw = original.read_bytes()
    before = redactions
    suffix = original.suffix
    data = raw
    if suffix == '.json':
        parsed = strict(raw)
        cleaned = values_only(parsed)
        if cleaned != parsed:
            data = (json.dumps(cleaned, indent=2, ensure_ascii=False) + '\n').encode()
        assert shape(parsed) == shape(strict(data))
    elif suffix == '.jsonl':
        lines = []
        for line in raw.splitlines():
            parsed = strict(line)
            cleaned = values_only(parsed)
            out = json.dumps(cleaned, ensure_ascii=False).encode()
            assert shape(parsed) == shape(strict(out))
            lines.append(out)
        data = b'\n'.join(lines) + b'\n'
    elif suffix == '.xml':
        tree = ET.fromstring(raw)
        for item in tree.iter():
            if item.text:
                item.text = redact_text(item.text, failure_text=True)
            if item.tail:
                item.tail = redact_text(item.tail, failure_text=True)
            if 'message' in item.attrib:
                item.attrib['message'] = redact_text(item.attrib['message'], failure_text=True)
        if redactions != before:
            data = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
        assert xml_identity(raw) == xml_identity(data)
    elif suffix != '.png':
        data = redact_text(raw.decode(), failure_text=suffix == '.log').encode()
    out = TARGET / relative
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    if original.name.endswith('collection.txt'):
        node_lines = lambda b: [line for line in b.decode().splitlines() if line.startswith('tests/') and '::' in line]
        assert node_lines(raw) == node_lines(data)
    assert sha(original.read_bytes()) == sha(raw)
    pairs.append(dict(original=str(original.relative_to(ROOT)) if original.is_relative_to(ROOT) else str(original),
                      exported=str(out.relative_to(ROOT)), original_sha256=sha(raw), exported_sha256=sha(data),
                      original_bytes=len(raw), exported_bytes=len(data), redacted_occurrences=redactions-before,
                      json_keys_preserved=True if suffix in ('.json', '.jsonl') else None,
                      junit_identity_preserved=True if suffix == '.xml' else None))

for pair in pairs:
    path = ROOT / pair['exported']
    assert sha(path.read_bytes()) == pair['exported_sha256']
    if path.suffix == '.json':
        strict(path.read_bytes())

gate = dict(
    base_sha=freeze['base_sha'], source_sha=freeze['source_sha'],
    branch='dev/f3-resource-plan-approval-read-20261017',
    result='RELATED_CONTRACT_SLICE_PASSED_REAL_AUTHORITY_UNAVAILABLE',
    formal_modules=freeze['modules'], final=final, per_module_unique=dict(collections.Counter(n.split('::')[0] for n in nodes)),
    new_API_unique=50, new_browser_unique=6, new56_included_in143=True,
    windows=windows, window_counts_never_added=True, source_inputs=len(freeze['files']), source_drift=0,
    original_algorithms_unchanged=freeze['old_algorithms_unchanged'],
    inherited_archive_git_blobs_checked=len(inherited), inherited_archive_drift=0,
    public_pairs=len(pairs), redacted_occurrences=redactions, JSON_strict_duplicate_key_validation=True,
    JSON_string_values_only_redacted=True, JSON_schema_keys_preserved=True,
    JUnit_nodes_and_nonmessage_attributes_preserved=True, original_raw_files_retained=True,
    old_duplicate_key_archive_preserved_with_separate_correction=True,
    prior_diagnostic427_or_SIGINT_rerun=False, source_adapter='explicit trusted-host Python read/verify composition seam; no production backend or trust root supplied',
    synthetic_fixture='signed synthetic file with independent current-head fixture; contract proof only, no real approval/authority proof',
    actual_production_approval_source_or_adapter_provided=False,
    production_installation_verified=False, original_namespace_scope='SYNTHETIC_LOCAL_PREPARATION_ONLY',
    positive_restart_proof='factory rebuild and fresh browser with same existing synthetic file; not production process installation',
    negative_restart_proof='actual default uvicorn subprocess restart without provider remains unavailable',
    browser_long_validity='client clock only:20+5 days remains verified,6 more days displays expiry; database clock not advanced',
    all_approval_read_responses_execution_authorized=False,
    approval_write_or_activation_or_resource_execution_added=False,
    independent_review='new product slice pending independent parent review',
    runtime_missing_inputs=[
        'original preparation/catalog entry still accepts SYNTHETIC namespace/kind only; real-business entry is unsupported and requires later authorized implementation/acceptance',
        'existing legal session and current READ plus PREPARE or originally assigned REVIEW_ASSIGNED',
        'same preparation/Case/Run and adopted P2 plan/version, exact current catalog/material/source/permission generations',
        'existing legal resource-plan approval source with exact binding, approver and authority reference, UTC validity/revocation',
        'already authorized trust mechanism and current authoritative head/revocation/approver validation',
        'approved read-only trusted-host adapter and already authorized connection; no credential discovery or creation',
    ],
    not_run=['Windows11 native', 'formalAT/AT35', 'real business/current real approval source', 'protected production positive adapter installation/restart',
             'resource execution/approval consumption', 'full project completion'],
    Actions_queries=0, unknown_processes_locks_sessions_removed=False,
    real_authority_credentials_security_permissions_changed=False, complete_project=False,
    pre_delivery_remote_old_heads_checked=preserved['old_heads_checked'], pre_delivery_remote_old_heads_drift=0,
    delivery_push_verification='recorded after final docs commit in private delivery-verification.json and final response; this artifact cannot embed its own future commit SHA',
)
(TARGET / 'gate.json').write_text(json.dumps(gate, indent=2, ensure_ascii=False) + '\n')
(TARGET / 'public-pairs.json').write_text(json.dumps(pairs, indent=2, ensure_ascii=False) + '\n')
(PRIVATE / 'export-validation.json').write_text(json.dumps(dict(result='PASSED', public_pairs=len(pairs), redactions=redactions,
    duplicate_keys_rejected=True, keys_preserved=True, junit_identity_preserved=True, source_drift=0, inherited_drift=0), indent=2) + '\n')
print(json.dumps({key: gate[key] for key in ('result', 'source_sha', 'final', 'source_inputs', 'public_pairs', 'redacted_occurrences')}, ensure_ascii=False))
