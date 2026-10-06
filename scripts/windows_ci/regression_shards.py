"""Opt-in fixed-file regression shards; partial evidence never means full PASS.

Also loaded as a pytest plugin to persist the actual parameterized collection.
No pytest import is needed by the coordinator or standalone publisher.
"""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

MAX_CASES = 10000
MAX_REPORT_BYTES = 4 * 1024 * 1024


def save(path, value):
    path = Path(path)
    temporary = path.with_name('.shards-' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=True, separators=(',', ':')) + '\n', encoding='ascii')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def pytest_addoption(parser):
    parser.addoption('--parkweave-shard-collection', default=None)


def pytest_collection_finish(session):
    destination = session.config.getoption('--parkweave-shard-collection')
    if destination:
        save(destination, {'schema': 2, 'nodeids': [item.nodeid for item in session.items],
                           'case_keys': [case_key(item.nodeid, getattr(getattr(item, 'callspec', None), 'indices', {})) for item in session.items]})


def case_key(nodeid, indices):
    """Keep every parameter dimension/index; values/UUID display IDs may vary."""
    return json.dumps([nodeid.split('[', 1)[0], sorted(indices.items())], separators=(',', ':'))


def validate_manifest(root, path):
    root = Path(root)
    manifest = json.loads(Path(path).read_text(encoding='utf-8'))
    shards = manifest.get('shards')
    if not isinstance(shards, list) or [s.get('id') for s in shards] != ['S1', 'S2', 'S3', 'S4']:
        raise ValueError('four fixed shard identities required')
    files = []
    for shard in shards:
        selected = shard.get('files')
        if not isinstance(selected, list) or not selected:
            raise ValueError('nonempty shard files required')
        for name in selected:
            if not isinstance(name, str) or not re.fullmatch(r'tests/test_[a-z0-9_]+\.py', name):
                raise ValueError('fixed test file required')
            files.append(name)
    actual = {str(p.relative_to(root)).replace('\\', '/') for p in (root / 'tests').rglob('test_*.py')}
    if len(set(files)) != len(files) or set(files) != actual:
        raise ValueError('shards must partition all current test files')
    hashes = manifest.get('source_file_sha256')
    if not isinstance(hashes, dict) or set(hashes) != set(files):
        raise ValueError('complete file fingerprint required')
    if any(hashlib.sha256((root / name).read_bytes()).hexdigest() != hashes[name] for name in files):
        raise ValueError('test file fingerprint changed')
    # Historical counts/weights never define current test coverage.
    return shards


def collection(path, allowed):
    with Path(path).open('rb') as stream:
        data = stream.read(MAX_REPORT_BYTES + 1)
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError('collection exceeds bound')
    row = json.loads(data)
    nodeids = row.get('nodeids') if isinstance(row, dict) and row.get('schema') == 2 and set(row) == {'schema', 'nodeids', 'case_keys'} else None
    if not isinstance(nodeids, list) or not 0 < len(nodeids) <= MAX_CASES:
        raise ValueError('actual collection required')
    if any(not isinstance(n, str) or len(n) > 1024 * 1024 or n.split('::', 1)[0] not in allowed for n in nodeids):
        raise ValueError('collection outside fixed files')
    if len(nodeids) != len(set(nodeids)):
        raise ValueError('duplicate collected case')
    keys = row['case_keys']
    if not isinstance(keys, list) or len(keys) != len(nodeids):
        raise ValueError('stable parameter identities required')
    for nodeid, key in zip(nodeids, keys):
        if not isinstance(key, str) or len(key) > 4096: raise ValueError('invalid parameter identity')
        value = json.loads(key)
        if not isinstance(value, list) or len(value) != 2 or value[0] != nodeid.split('[', 1)[0] or not isinstance(value[1], list):
            raise ValueError('invalid parameter dimensions')
        for pair in value[1]:
            if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', pair[0]) or type(pair[1]) is not int or not 0 <= pair[1] <= MAX_CASES:
                raise ValueError('invalid parameter index')
        indices = dict(value[1])
        if len(indices) != len(value[1]) or case_key(nodeid, indices) != key: raise ValueError('noncanonical parameter identity')
    if len(keys) != len(set(keys)): raise ValueError('duplicate stable parameter identity')
    return nodeids, keys


def inventory(path, allowed):
    return collection(path, allowed)[0]


def junit_cases(path):
    with Path(path).open('rb') as stream:
        data = stream.read(MAX_REPORT_BYTES + 1)
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError('JUnit exceeds bound')
    cases = list(ET.fromstring(data).iter('testcase'))
    if len(cases) > MAX_CASES:
        raise ValueError('JUnit case limit exceeded')
    observed = []
    for case in cases:
        module = case.get('classname', '').split('.')[-1]
        nodeid = 'tests/' + module + '.py::' + case.get('name', '')
        status = 'FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
        observed.append((nodeid, status))
    return observed


def logical_cases(observed):
    outcomes = {}
    rank = {'PASS': 0, 'SKIP': 1, 'FAIL': 2}
    for nodeid, status in observed:
        if nodeid not in outcomes or rank[status] > rank[outcomes[nodeid]]:
            outcomes[nodeid] = status
    return list(outcomes.items())


def run_command(command, *, root, env, stdout, stderr, timeout):
    if os.name == 'nt':
        try:
            from .owned_job import run
        except ImportError:
            from owned_job import run
        return run(command, cwd=root, env=env, stdout=stdout, stderr=stderr, timeout=timeout)
    # Local synthetic harness only; Windows uses kernel-owned tree cleanup.
    process = subprocess.Popen(command, cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
    try:
        return subprocess.CompletedProcess(command, process.wait(timeout=timeout))
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        raise


def execute(root, executable, manifest, private, report, *, env, progress=None,
            total_seconds=900, runner=run_command, clock=time.monotonic):
    """Sequential candidate within a fixed total budget, including collection.

    Each command gets <=600 seconds; collection <=60. Keep ten seconds for tree
    cleanup/reporting. Exhaustion produces NOT_RUN shards and a failing report.
    """
    if type(total_seconds) not in (int, float) or not 0 < total_seconds <= 900:
        raise ValueError('existing 900-second maximum required')
    root, private, report = Path(root), Path(private), Path(report)
    private.mkdir(parents=True, exist_ok=True)
    started = clock()
    shards = validate_manifest(root, manifest)
    rows = [{'id': s['id'], 'status': 'NOT_RUN', 'reason': 'NOT_STARTED', 'expected_cases': None,
             'counts': {'PASS': 0, 'FAIL': 0, 'SKIP': 0}} for s in shards]
    all_cases = []
    expected = []
    expected_keys = []
    collection_state = 'NOT_RUN'
    collection_category = None
    aggregate_junit = private / ('shards-' + uuid.uuid4().hex + '.xml')

    def remaining():
        return max(0, total_seconds - (clock() - started) - 10)

    def persist():
        logical = logical_cases(all_cases)
        counts = Counter(status for _, status in logical)
        complete = collection_state == 'AVAILABLE' and all(r['status'] in ('PASS', 'FAIL') for r in rows) and all(r.get('coverage_complete') for r in rows)
        success = complete and all(r['status'] == 'PASS' for r in rows)
        value = {'schema': 1, 'scope': 'OPT_IN_SHARDED_ENGINEERING', 'execution_exit_code': 0 if success else 1,
                 'whole_AT_EX': 'NOT_RUN', 'collection_state': collection_state,
                 'expected_cases': len(expected) if expected else None, 'observed_cases': len(logical), 'observed_case_reports': len(all_cases),
                 'coverage_complete': complete, 'engineering_total_counts': {s: counts[s] for s in ('PASS', 'FAIL', 'SKIP')},
                 'shards': rows, 'private_junit': str(aggregate_junit.relative_to(root)),
                 'elapsed_seconds': round(clock() - started, 3), 'total_budget_seconds': total_seconds,
                 'per_shard_max_seconds': 600,
                 'capacity': '900 seconds cannot guarantee full completion; historical partial Windows trend ~1120 seconds is not a prediction'}
        if collection_category is not None: value['collection_category'] = collection_category
        suite = ET.Element('testsuite')
        for nodeid, status in logical:
            file, name = nodeid.split('::', 1)
            case = ET.SubElement(suite, 'testcase', classname=Path(file).stem, name=name)
            if status == 'FAIL': ET.SubElement(case, 'failure')
            elif status == 'SKIP': ET.SubElement(case, 'skipped')
        ET.ElementTree(suite).write(aggregate_junit, encoding='utf-8', xml_declaration=True)
        save(report, value)
        return value

    def invoke(files, collect=False):
        token = uuid.uuid4().hex
        inventory_path = private / ('collection-' + token + '.json')
        junit = private / ('pytest-shard-' + token + '.xml')
        command = [str(executable), '-m', 'pytest', '-q', '-p', 'scripts.windows_ci.regression_shards',
                   '--parkweave-shard-collection', str(inventory_path)]
        if collect: command.append('--collect-only')
        else:
            command.extend(['--junitxml', str(junit)])
            if progress is not None: command.extend(['-p', 'scripts.windows_ci.regression_plugin', '--parkweave-progress', str(progress)])
        command.extend(files)
        limit = min(60 if collect else 600, remaining())
        with (private / ('shard-' + token + '.stdout')).open('xb') as out, (private / ('shard-' + token + '.stderr')).open('xb') as err:
            try:
                result = runner(command, root=root, env=env, stdout=out, stderr=err, timeout=limit)
            except Exception as error:
                error.shard_collection = inventory_path
                error.shard_junit = junit
                raise
        return result.returncode, inventory_path, junit, getattr(result, 'cleanup', None)

    persist()
    try:
        if remaining() <= 0: raise TimeoutError('collection budget exhausted')
        code, collected, _, cleanup = invoke(['tests'], collect=True)
        if code != 0 or cleanup not in (None, 'OWNED_TREE_STOPPED'): raise ValueError('actual collection failed')
        expected, expected_keys = collection(collected, {f for s in shards for f in s['files']})
        collection_state = 'AVAILABLE'
    except Exception as error:
        collection_state = 'UNAVAILABLE'
        collection_category = type(error).__name__
        persist()  # Still obtain independent shard evidence if budget remains.
    for shard, row in zip(shards, rows):
        current = [n for n in expected if n.split('::', 1)[0] in shard['files']]
        current_keys = [key for n, key in zip(expected, expected_keys) if n.split('::', 1)[0] in shard['files']]
        row['expected_cases'] = len(current) if collection_state == 'AVAILABLE' else None
        if remaining() <= 0:
            row['reason'] = 'TOTAL_BUDGET_EXHAUSTED'
            persist()
            continue
        row.update(status='RUNNING', reason='IN_PROGRESS')
        persist()
        row_junit = None
        try:
            code, collected, junit, cleanup = invoke(shard['files'])
            row['exit_code'] = code
            if cleanup is not None: row['owned_tree_cleanup'] = cleanup
            row_junit = junit
            observed = junit_cases(junit)
            found, found_keys = collection(collected, set(shard['files']))
            if collection_state != 'AVAILABLE': row['expected_cases'] = len(found)
            coverage = (collection_state != 'AVAILABLE' or Counter(found_keys) == Counter(current_keys)) and Counter(n for n, _ in observed) == Counter(found)
            # Preserve partial actual results; duplicates/missing cases never complete.
            all_cases.extend(observed)
            counts = Counter(status for _, status in logical_cases(observed))
            clean = cleanup in (None, 'OWNED_TREE_STOPPED')
            row.update(status='PASS' if code == 0 and coverage and not counts['FAIL'] and clean else 'FAIL',
                       reason='CLEANUP_UNCONFIRMED' if not clean else 'COMPLETE' if coverage else 'COVERAGE_MISMATCH', exit_code=code,
                       coverage_complete=coverage, counts={s: counts[s] for s in ('PASS', 'FAIL', 'SKIP')})
            if cleanup is not None: row['owned_tree_cleanup'] = cleanup
        except Exception as error:
            row.update(status='FAIL', reason='SHARD_ERROR', category=type(error).__name__, coverage_complete=False)
            cleanup = getattr(error, 'cleanup', None)
            if cleanup is not None: row['owned_tree_cleanup'] = cleanup
            partial = getattr(error, 'shard_junit', row_junit)
            try:
                observed = junit_cases(partial) if partial is not None else []
                all_cases.extend(observed)
                counts = Counter(s for _, s in logical_cases(observed))
                row['counts'] = {s: counts[s] for s in ('PASS', 'FAIL', 'SKIP')}
            except Exception: pass
        persist()
    # Also reject files edited while the shards were executing.
    try: validate_manifest(root, manifest)
    except Exception:
        rows[-1].update(status='FAIL', reason='SOURCE_CHANGED', coverage_complete=False)
    return persist()
