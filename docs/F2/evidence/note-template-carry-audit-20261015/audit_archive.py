"""Independent raw/export reconstruction. Never import root producer or verifier."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import ast
import hashlib
import json
import re
import subprocess
import traceback
import xml.etree.ElementTree as ET

from shared_matcher import KnownTokenRedactor

ROOT = Path('/workspace/ParkWeave')
HERE = Path(__file__).resolve().parent
FIXTURE = re.compile(r'^\s*\w+\s*=\s*[({].*Store object at 0x')
SESSIONS = re.compile(r'^\s*(?:tokens|session_tokens)\s*=\s*\{')
BEARER = re.compile(r'Bearer ([A-Za-z0-9_-]{43})(?![A-Za-z0-9_-])')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, 'duplicate JSON object key'
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def relpath(text):
    path = ROOT / text
    assert path.resolve().is_relative_to(ROOT), 'path leaves owned workspace'
    return path


def public_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def identity(path):
    data = path.read_bytes()
    return dict(bytes=len(data), sha256=digest(data))


def rebuild(raw, suffix, matcher):
    """Own traversal/serialization; only known-token matching is shared."""
    counts = dict(exact_private_value=0, fixture_repr_line=0)

    def clean(text):
        text, count = matcher.replace(text)
        counts['exact_private_value'] += count
        parts = []
        for line in text.splitlines(keepends=True):
            if suffix not in {'.py', '.js'} and (FIXTURE.match(line) or SESSIONS.match(line)):
                counts['fixture_repr_line'] += 1
                parts.append('[REDACTED_SYNTHETIC_FIXTURE_REPR]' + ('\n' if line.endswith('\n') else ''))
            else:
                parts.append(line)
        return ''.join(parts)

    def nested(value):
        if isinstance(value, str):
            return clean(value)
        if isinstance(value, list):
            return list(map(nested, value))
        if isinstance(value, dict):
            return {key: nested(item) for key, item in value.items()}
        return value

    text = raw.decode('utf-8')
    if suffix == '.json':
        rebuilt = (json.dumps(nested(json.loads(text)), indent=2, ensure_ascii=False) + '\n').encode()
    elif suffix == '.jsonl':
        rows = [nested(json.loads(line)) for line in text.splitlines() if line.strip()]
        rebuilt = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows).encode()
    elif suffix == '.xml':
        tree = ET.fromstring(raw)
        for node in tree.iter():
            if node.text:
                node.text = clean(node.text)
            if node.tail:
                node.tail = clean(node.tail)
            for key in tuple(node.attrib):
                node.attrib[key] = clean(node.attrib[key])
        rebuilt = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
    else:
        rebuilt = clean(text).encode()
    if not any(counts.values()):
        rebuilt = raw
    assert not matcher.has_residual(rebuilt.decode()), 'known private value remained after independent reconstruction'
    return rebuilt, counts


def source_inventory(config, copies):
    result = set()
    for name in config['dirs']:
        base = ROOT / '.runtime' / name
        assert base.is_dir(), 'configured runtime source missing'
        for path in base.rglob('*'):
            if not path.is_file() or path.suffix not in config['extensions']:
                continue
            if path.name in config['excluded_names'] or '.private.' in path.name:
                continue
            if set(path.parts).intersection(config['excluded_components']):
                continue
            if any(part.startswith('pytest-') for part in path.parts):
                if str(path.relative_to(ROOT)) not in copies:
                    continue
            assert path.resolve().is_relative_to(base.resolve()), 'source file symlink leaves runtime source'
            result.add(str(path.relative_to(ROOT)))
    return result


def legacy_copies(config):
    saved = read_json(relpath(config['legacy_index']))
    entries = saved['entries']
    assert len(entries) == config['legacy_expected_copies']
    copies = set()
    original_paths = set()
    pytest_count = 0
    records = []
    for item in entries:
        assert set(item) == {'original', 'copy', 'sha256', 'bytes'}
        original, copy = relpath(item['original']), relpath(item['copy'])
        assert any(original.is_relative_to(ROOT / '.runtime' / name) for name in config['legacy_roots'])
        assert copy.is_relative_to(relpath(config['legacy_copy_base']))
        assert not {'pgdata', 'postgres', '__pycache__', '.pytest_cache'}.intersection(copy.parts)
        assert original.suffix in config['extensions'] and original.suffix == copy.suffix
        expected = dict(bytes=item['bytes'], sha256=item['sha256'])
        assert identity(original) == identity(copy) == expected, 'preserved legacy original/copy changed'
        assert item['copy'] not in copies and item['original'] not in original_paths
        copies.add(item['copy']); original_paths.add(item['original'])
        pytest_count += any(part.startswith('pytest-') for part in copy.parts)
        records.append(dict(original=item['original'], copy=item['copy'], **expected))
    assert pytest_count == config['legacy_expected_pytest_named_files']
    actual = {str(p.relative_to(ROOT)) for p in relpath(config['legacy_copy_base']).rglob('*') if p.is_file()}
    assert actual == copies | {config['legacy_index']}, 'unexpected file in bounded legacy copy directory'
    return copies, dict(status='PASS', files=len(copies), pytest_name_exceptions=pytest_count,
        historical_not_final_run_evidence=True, records=records)


def known_values(config):
    paths = set(map(relpath, config['shared_private_sets']))
    for name in config['dirs']:
        paths.update((ROOT / '.runtime' / name).rglob('*redaction*.private.json'))
    pool = set()
    private = []
    for path in sorted(paths):
        if not path.is_file():
            continue
        values = read_json(path)
        assert isinstance(values, list) and all(isinstance(v, str) for v in values)
        pool.update(value for value in values if len(value) >= 16)
        private.append(dict(path=str(path.relative_to(ROOT)), **identity(path),
            role='KNOWN_SYNTHETIC_VALUE_LOOKUP_ONLY_NOT_EXCLUSIVE_TEST_EVIDENCE'))
    # Stable independent tie order. Fast nonoverlapping matching is order-independent.
    ordered = sorted(pool, key=lambda value: (-len(value), value))
    return ordered, dict(private_sets=private, unique_values=len(ordered),
        length_distribution=dict(Counter(map(len, ordered))),
        ordered_pool_sha256=digest(json.dumps(ordered, ensure_ascii=False).encode()),
        private_values_disclosed=False, shared_matcher_algorithm_diversity=False)


def source_freeze(config):
    freeze = read_json(relpath(config['freeze']))
    assert freeze['source_sha'] == config['source_sha']
    assert len(freeze['source_paths']) == config['source_paths']
    assert len(freeze['all_tracked_sha256']) == config['all_tracked_paths']
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert head == config['source_sha']
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT)
    entries = subprocess.check_output(['git', 'ls-files', '-s', '-z'], cwd=ROOT).split(b'\0')
    actual = {}
    for entry in entries:
        if not entry:
            continue
        header, raw_path = entry.split(b'\t', 1)
        mode, blob, stage = header.decode().split()
        assert stage == '0' and mode in {'100644', '100755'}
        path = raw_path.decode(); data = relpath(path).read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == blob
        actual[path] = digest(data)
    assert actual == freeze['all_tracked_sha256']
    assert {path: actual[path] for path in freeze['source_paths']} == freeze['source_paths']
    return dict(status='PASS', source_sha=head, source_paths=len(freeze['source_paths']),
        all_tracked_paths=len(actual), Git_blobs_exact=True, all_tracked_hashes=actual)


def prior_originals(config):
    records = {}
    for index in config['old_indices']:
        for row in read_json(relpath(index))['entries']:
            path = row['raw_path']
            assert path not in records
            expected = dict(bytes=row['raw_bytes'], sha256=row['raw_sha256'])
            assert identity(relpath(path)) == expected, 'old archived original changed'
            records[path] = expected
    assert len(records) == config['old_raw_count']
    return dict(status='PASS', old_raw_originals=len(records), records=records)


def residual_context(text, suffix=''):
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if suffix not in {'.py', '.js'} and (FIXTURE.match(line) or SESSIONS.match(line)):
            found.append(dict(line=number, kind='FIXTURE_OR_SESSION_REPR_LINE'))
        for match in BEARER.finditer(line):
            found.append(dict(line=number, kind='FULL_SESSION_IN_BEARER_CONTEXT', value_sha256=digest(match.group(1).encode())))
    return found


def check_structure(path):
    suffix = path.suffix
    if suffix == '.json':
        read_json(path)
    elif suffix == '.jsonl':
        for line in path.read_text().splitlines():
            if line.strip():
                json.loads(line)
    elif suffix == '.xml':
        ET.fromstring(path.read_bytes())
    elif suffix == '.py':
        ast.parse(path.read_bytes(), filename=str(path))
    elif suffix == '.js':
        result = subprocess.run(['node', '--check', str(path)], capture_output=True)
        assert result.returncode == 0, 'exported JavaScript syntax failed'
    return suffix


def perform(config, attempt):
    helper = HERE / 'shared_matcher.py'
    assert digest(helper.read_bytes()) == config['shared_matcher_sha256']
    primary = relpath(config['primary'])
    assert primary.is_dir(), 'primary archive not generated'
    for name in config['primary_metadata']:
        assert (primary / name).is_file(), 'primary metadata missing'
    report = relpath(config['report'])
    assert report.is_file(), 'delivery report not generated'
    before_primary = {str(p.relative_to(ROOT)): identity(p) for p in primary.rglob('*') if p.is_file()}
    before_report = identity(report)
    copies, legacy = legacy_copies(config)
    public_json(attempt / 'legacy-copy-verification.json', legacy)
    inventory = source_inventory(config, copies)
    index = read_json(primary / 'index.json')
    assert index['source_sha'] == config['source_sha']
    indexed = index['entries']
    assert {row['raw_path'] for row in indexed} == inventory
    assert len(indexed) == len(inventory)
    expected_exports = set()
    before_raw = {}
    values, pool_info = known_values(config)
    public_json(attempt / 'private-pool-metadata.json', pool_info)
    matcher = KnownTokenRedactor(values)
    records = []
    suffixes = Counter()
    redactions = Counter()
    for row in indexed:
        assert set(row) == {'raw_path','export_path','raw_sha256','raw_bytes','export_sha256','export_bytes','redactions'}
        source = relpath(row['raw_path'])
        target = relpath(row['export_path'])
        wanted = primary / source.relative_to(ROOT / '.runtime')
        assert target == wanted and target.is_relative_to(primary)
        assert row['export_path'] not in expected_exports
        expected_exports.add(row['export_path'])
        raw = source.read_bytes(); exported = target.read_bytes()
        assert digest(raw) == row['raw_sha256'] and len(raw) == row['raw_bytes']
        assert digest(exported) == row['export_sha256'] and len(exported) == row['export_bytes']
        before_raw[row['raw_path']] = identity(source)
        reconstructed, counts = rebuild(raw, source.suffix, matcher)
        assert reconstructed == exported, 'independent rebuilt bytes differ: ' + row['export_path']
        assert counts == row['redactions'], 'redaction counts differ: ' + row['export_path']
        assert not matcher.has_residual(exported.decode()), 'known private value in exported file'
        assert not residual_context(exported.decode(), target.suffix), 'unmasked fixture/session context: ' + row['export_path']
        suffixes[check_structure(target)] += 1
        redactions.update(counts)
        assert source.read_bytes() == raw
        records.append(dict(raw_path=row['raw_path'], export_path=row['export_path'],
            raw_sha256=digest(raw), raw_bytes=len(raw), export_sha256=digest(exported), export_bytes=len(exported),
            independently_rebuilt=True, redactions=counts))
    metadata = {str((primary / name).relative_to(ROOT)) for name in config['primary_metadata']}
    assert set(before_primary) == expected_exports | metadata, 'unexpected primary files outside indexed payload/four metadata'
    for path in metadata | {config['report']}:
        data = relpath(path).read_text()
        assert not matcher.has_residual(data) and not residual_context(data, relpath(path).suffix)
    attrs = (primary / '.gitattributes').read_text()
    assert any('-text' in line.split() and '-whitespace' in line.split() for line in attrs.splitlines()
               if line.strip() and not line.lstrip().startswith('#')), 'evidence raw-byte attributes absent'
    assert not re.search(r'@@[A-Z_]+@@|ROOT_RESULT|REVIEW_RESULT', report.read_text()), 'unfilled public report'
    public_json(attempt / 'pair-reconstruction.json', dict(status='PASS_MECHANICAL_RECONSTRUCTION_ONLY',
        pairs=len(records), exported_bytes=sum(r['export_bytes'] for r in records), records=records,
        structured_counts=dict(suffixes), redactions=dict(redactions), matcher_statistics=matcher.public_statistics(),
        producer_or_root_verifier_imported=False, shared_matcher_algorithm_diversity=False))
    public_json(attempt / 'source-Git-verification.json', source_freeze(config))
    public_json(attempt / 'old2127-verification.json', prior_originals(config))
    for path, expected in before_raw.items():
        assert identity(relpath(path)) == expected, 'raw source changed during audit'
    assert source_inventory(config, copies) == inventory, 'source inventory changed during audit'
    after_primary = {str(p.relative_to(ROOT)): identity(p) for p in primary.rglob('*') if p.is_file()}
    assert after_primary == before_primary and identity(report) == before_report, 'primary/report changed during audit'
    public_json(attempt / 'mechanical-gate.json', dict(status='PASS_MECHANICAL_ONLY_SCOPE_GATE_STILL_REQUIRED',
        source_sha=config['source_sha'], pairs=len(records), primary_and_raw_stable=True,
        known_session_and_fixture_context_residuals=0, source_paths=config['source_paths'],
        all_tracked_paths=config['all_tracked_paths'], old2127_unchanged=True,
        final_delivery_or_formal_AT_PASS_claimed=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--archive-ready', action='store_true')
    args = parser.parse_args()
    config = read_json(HERE / 'audit-config.json')
    assert args.archive_ready and config['archive_ready'] is True, 'NOT_RUN: await explicit parent archive-ready message'
    assert re.fullmatch(r'[a-z0-9_-]{1,60}', args.label)
    attempt = HERE / args.label
    attempt.mkdir(mode=0o700, exist_ok=False)
    try:
        perform(config, attempt)
    except BaseException as error:
        public_json(attempt / 'audit-failure.json', dict(status='FAIL_OR_STOP_NO_FINAL_PASS',
            error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc(),
            source_sha=config['source_sha'], utc=datetime.now(timezone.utc).isoformat(), originals_modified=False))
        raise


if __name__ == '__main__':
    main()
