"""Small synthetic orchestration; no database, lifecycle, Windows or model calls."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest
from scripts.windows_ci import regression_shards as shards


@pytest.fixture
def candidate(tmp_path):
    root = tmp_path / 'repo'
    (root / 'tests').mkdir(parents=True)
    files = []
    for name in ('a', 'b', 'c', 'd'):
        path = root / 'tests' / ('test_' + name + '.py')
        path.write_text('def test_one():\n assert True\n')
        files.append(str(path.relative_to(root)))
    manifest = root / 'manifest.json'
    document = {'shards': [{'id': 'S' + str(i + 1), 'files': [f]} for i, f in enumerate(files)],
                'source_file_sha256': {f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in files}}
    manifest.write_text(json.dumps(document))
    return root, manifest, document


def simulate(candidate, *, fault=None, budget=900, duration=1):
    root, manifest, document = candidate
    clock = [0.0]
    calls = []
    nodeids = [s['files'][0] + '::test_one' for s in document['shards']]
    def run(command, **kwargs):
        calls.append((command, kwargs['timeout']))
        assert 0 < kwargs['timeout'] <= (60 if '--collect-only' in command else 600)
        collect = '--collect-only' in command
        names = nodeids if collect else [n for n in nodeids if n.split('::', 1)[0] in command]
        inventory = Path(command[command.index('--parkweave-shard-collection') + 1])
        inventory.write_text(json.dumps({'schema': 2, 'nodeids': names, 'case_keys': [shards.case_key(n, {}) for n in names]}))
        clock[0] += duration
        if collect:
            if fault == 'collect_timeout': raise subprocess.TimeoutExpired(command, kwargs['timeout'])
            if fault == 'collect_failure': return SimpleNamespace(returncode=2)
            if fault == 'collect_cleanup_exception':
                error=subprocess.TimeoutExpired(command,kwargs['timeout']);error.cleanup='OWNED_TREE_STOP_UNCONFIRMED';raise error
            if fault == 'collect_cleanup_return':return SimpleNamespace(returncode=17,cleanup='UNKNOWN')
            return SimpleNamespace(returncode=0)
        number = len(calls) - 1
        junit = Path(command[command.index('--junitxml') + 1])
        suite = ET.Element('testsuite')
        for nodeid in names:
            file, name = nodeid.split('::')
            case = ET.SubElement(suite, 'testcase', classname=Path(file).stem, name=name)
            if fault == 'fail' and number == 1: ET.SubElement(case, 'failure')
            if fault == 'skip' and number == 2: ET.SubElement(case, 'skipped')
            if fault == 'duplicate' and number == 1: ET.SubElement(suite, 'testcase', classname=Path(file).stem, name=name)
        if fault == 'missing' and number == 1: suite.clear()
        ET.ElementTree(suite).write(junit)
        if fault == 'timeout' and number == 1:
            raise subprocess.TimeoutExpired(command, kwargs['timeout'])
        if fault == 'cleanup_exception' and number == 1:
            error=subprocess.TimeoutExpired(command,kwargs['timeout']);error.cleanup='OWNED_TREE_STOP_UNCONFIRMED';raise error
        if fault in ('missing_collection', 'cleanup_missing_inventory') and number == 1: inventory.unlink()
        if fault == 'nonzero_bad_junit' and number == 1: junit.write_text('<invalid')
        if fault == 'source_change' and number == 1: (root / names[0].split('::')[0]).write_text('changed')
        return SimpleNamespace(returncode=17 if fault in ('fail', 'nonzero_bad_junit') and number == 1 else 0,
                               cleanup='OWNED_TREE_STOP_UNCONFIRMED' if fault in ('cleanup', 'cleanup_missing_inventory') and number == 1 else 'OWNED_TREE_STOPPED')
    result = shards.execute(root, sys.executable, manifest, root / '.runtime', root / 'result.json',
                            env={}, total_seconds=budget, runner=run, clock=lambda: clock[0])
    return result, calls


def test_shards_complete_exactly_once_and_keep_counts(candidate):
    result, calls = simulate(candidate, fault='skip')
    assert len(calls) == 5 and result['coverage_complete'] and result['execution_exit_code'] == 0
    assert result['expected_cases'] == result['observed_cases'] == 4
    assert result['engineering_total_counts'] == {'PASS': 3, 'FAIL': 0, 'SKIP': 1}
    assert result['whole_AT_EX'] == 'NOT_RUN'


@pytest.mark.parametrize('fault', ['fail', 'timeout', 'missing', 'duplicate', 'missing_collection', 'source_change'])
def test_shard_failures_keep_running_other_shards_and_partial_reports(candidate, fault):
    result, calls = simulate(candidate, fault=fault)
    assert len(calls) == 5 and result['execution_exit_code'] == 1
    assert result['shards'][0]['status'] == 'FAIL' or fault == 'source_change'
    assert result['shards'][1]['status'] == result['shards'][2]['status'] == 'PASS'
    if fault not in ('missing',): assert result['engineering_total_counts']['PASS'] + result['engineering_total_counts']['FAIL'] == 4
    if fault == 'fail': assert result['shards'][0]['exit_code'] == 17
    if fault == 'timeout': assert result['shards'][0]['category'] == 'TimeoutExpired'
    if fault in ('missing', 'duplicate', 'missing_collection', 'source_change', 'timeout'): assert not result['coverage_complete']


def test_shard_budget_exhaustion_never_claims_complete_and_saves_missing(candidate):
    result, calls = simulate(candidate, budget=15, duration=3)
    assert len(calls) == 2 and result['execution_exit_code'] == 1 and not result['coverage_complete']
    assert result['engineering_total_counts']['PASS'] == 1
    assert [r['status'] for r in result['shards']] == ['PASS', 'NOT_RUN', 'NOT_RUN', 'NOT_RUN']
    assert all(r['reason'] == 'TOTAL_BUDGET_EXHAUSTED' for r in result['shards'][1:])


@pytest.mark.parametrize('fault', ['collect_timeout', 'collect_failure'])
def test_precollection_failure_keeps_independent_shard_evidence_without_full_pass(candidate, fault):
    result, calls = simulate(candidate, fault=fault)
    assert len(calls) == 5 and result['collection_state'] == 'UNAVAILABLE'
    assert result['execution_exit_code'] == 1 and not result['coverage_complete']
    assert result['expected_cases'] is None and result['observed_cases'] == 4
    assert result['engineering_total_counts'] == {'PASS': 4, 'FAIL': 0, 'SKIP': 0}


@pytest.mark.parametrize('fault', ['nonzero_bad_junit', 'cleanup_missing_inventory'])
def test_shard_parse_failure_never_discards_original_exit_or_cleanup(candidate, fault):
    result, calls = simulate(candidate, fault=fault)
    assert len(calls) == (2 if fault=='cleanup_missing_inventory' else 5) and result['execution_exit_code'] == 1 and not result['coverage_complete']
    first = result['shards'][0]
    assert first['status'] == 'FAIL'
    if fault == 'nonzero_bad_junit': assert first['exit_code'] == 17 and first['owned_tree_cleanup'] == 'OWNED_TREE_STOPPED'
    else: assert first['exit_code'] == 0 and first['owned_tree_cleanup'] == 'OWNED_TREE_STOP_UNCONFIRMED'


@pytest.mark.parametrize('fault',['collect_cleanup_return','collect_cleanup_exception','cleanup','cleanup_exception'])
def test_unconfirmed_tree_cleanup_preserves_original_evidence_and_isolates_following_shards(candidate,fault):
    result,calls=simulate(candidate,fault=fault)
    pre=fault.startswith('collect_');assert len(calls)==(1 if pre else 2)
    assert result['execution_exit_code']==1 and not result['coverage_complete']
    following=result['shards'] if pre else result['shards'][1:]
    assert all(r['status']=='NOT_RUN' and r['reason']=='CLEANUP_NOT_CONFIRMED' for r in following)
    if pre:
        assert result['collection_owned_tree_cleanup']==('UNKNOWN' if fault.endswith('return') else 'OWNED_TREE_STOP_UNCONFIRMED')
        if fault.endswith('return'):assert result['collection_exit_code']==17
    else:
        first=result['shards'][0];assert first['status']=='FAIL' and first['owned_tree_cleanup']=='OWNED_TREE_STOP_UNCONFIRMED'
        assert result['engineering_total_counts']=={'PASS':1,'FAIL':0,'SKIP':0}
        if fault=='cleanup':assert first['exit_code']==0
        else:assert first['category']=='TimeoutExpired'


def test_actual_expired_coordinator_persists_all_not_run_without_launch(candidate,monkeypatch):
    from scripts.windows_ci import job_budget
    actual=job_budget.JobBudget
    monkeypatch.setattr(job_budget,'JobBudget',lambda deadline,**kwargs:actual(deadline,wall=lambda:200,uptime=lambda:200000,clock=lambda:0,**kwargs))
    root,manifest,_=candidate
    result=shards.execute(root,sys.executable,manifest,root/'.runtime',root/'result.json',env={},total_seconds=0,
                          deadline=100,uptime_deadline=100000,runner=lambda *args,**kwargs:pytest.fail('expired launch'))
    assert result['execution_exit_code']==1 and result['observed_cases']==0 and not result['coverage_complete']
    assert all(r['status']=='NOT_RUN' and r['reason']=='TOTAL_BUDGET_EXHAUSTED' for r in result['shards'])


@pytest.mark.parametrize('fault', ['duplicate', 'missing_file', 'changed_hash', 'extra_file'])
def test_shard_manifest_rejects_incomplete_partition_or_source_drift(candidate, fault):
    root, path, document = candidate
    if fault == 'duplicate': document['shards'][1]['files'] = document['shards'][0]['files']
    if fault == 'missing_file': document['shards'][0]['files'] = []
    if fault == 'changed_hash': (root / 'tests/test_a.py').write_text('changed')
    if fault == 'extra_file': (root / 'tests/test_new.py').write_text('def test_new(): pass')
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError): shards.validate_manifest(root, path)


def test_shard_collection_plugin_records_parameterized_cases_without_execution(candidate):
    root, _, _ = candidate
    test = root / 'tests/test_a.py'
    test.write_text('import pytest\n@pytest.mark.parametrize("x",[1,2])\ndef test_one(x):\n raise AssertionError("must not execute")\n')
    report = root / 'collected.json'
    repo = Path(__file__).resolve().parents[1]
    from parkweave.process_env import minimal_environment
    env = minimal_environment(os.environ, PYTHONPATH=str(repo) + os.pathsep + str(repo / 'src'))
    process = subprocess.run([sys.executable, '-m', 'pytest', '-q', '--collect-only', '-p', 'scripts.windows_ci.regression_shards',
                              '--parkweave-shard-collection', str(report), 'tests/test_a.py'], cwd=root, env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    assert process.returncode == 0
    assert shards.inventory(report, {'tests/test_a.py'}) == ['tests/test_a.py::test_one[1]', 'tests/test_a.py::test_one[2]']


def test_real_small_four_shard_run_collects_executes_and_merges_exactly_once(candidate):
    root, manifest, document = candidate
    for shard in document['shards']:
        file = shard['files'][0]
        (root / file).write_text('import pytest\nfrom uuid import uuid4\n@pytest.mark.parametrize("value",[str(uuid4()),str(uuid4())])\ndef test_one(value):\n assert len(value)==36\n')
        document['source_file_sha256'][file] = hashlib.sha256((root / file).read_bytes()).hexdigest()
    manifest.write_text(json.dumps(document))
    repo = Path(__file__).resolve().parents[1]
    from parkweave.process_env import minimal_environment
    env = minimal_environment(os.environ, PYTHONPATH=str(repo) + os.pathsep + str(repo / 'src'))
    result = shards.execute(root, sys.executable, manifest, root / '.runtime', root / 'result.json', env=env, total_seconds=30)
    assert result['execution_exit_code'] == 0 and result['coverage_complete']
    assert result['expected_cases'] == result['observed_cases'] == 8
    assert result['engineering_total_counts'] == {'PASS': 8, 'FAIL': 0, 'SKIP': 0}
    assert all(row['coverage_complete'] and row['status'] == 'PASS' for row in result['shards'])
    assert len(shards.junit_cases(root / result['private_junit'])) == 8
    assert all(row['expected_cases'] == 2 for row in result['shards'])


def test_real_shard_failure_aggregate_uses_existing_public_junit_allowlist(candidate):
    root, manifest, document = candidate
    old=document['shards'][0]['files'][0];(root/old).unlink()
    file='tests/test_regression_shards.py';test_id=file+'::test_duplicate_stable_parameter_identity_is_rejected'
    (root/file).write_text('def test_duplicate_stable_parameter_identity_is_rejected():\n assert False\n')
    document['shards'][0]['files']=[file];del document['source_file_sha256'][old]
    document['source_file_sha256'][file]=hashlib.sha256((root/file).read_bytes()).hexdigest();manifest.write_text(json.dumps(document))
    repo=Path(__file__).resolve().parents[1]
    from parkweave.process_env import minimal_environment
    from test_windows_ci_preparation import module
    env=minimal_environment(os.environ,PYTHONPATH=str(repo)+os.pathsep+str(repo/'src'))
    result=shards.execute(root,sys.executable,manifest,root/'.runtime',root/'result.json',env=env,total_seconds=30)
    assert result['execution_exit_code']==1 and result['coverage_complete']
    assert result['engineering_total_counts']=={'PASS':3,'FAIL':1,'SKIP':0}
    public=module('diagnostics').failure_tests(root,result['private_junit'])
    assert public['state']=='AVAILABLE' and public['failed_test_ids']==[test_id]


def test_native_shard_opt_in_keeps_default_deadline_and_explicit_remaining_budget(tmp_path, monkeypatch):
    from test_windows_ci_preparation import module
    suite = module('native_suite')
    monkeypatch.setattr(suite, 'os', SimpleNamespace(name='nt'))
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=17, cleanup='OWNED_TREE_STOPPED')
    monkeypatch.setattr(suite, 'run_owned_job', run)
    suite.run_regression(sys.executable, tmp_path / 'default.json', tmp_path / 'default.progress.json', {})
    suite.run_regression(sys.executable, tmp_path / 'optin.json', tmp_path / 'optin.progress.json', {}, shards=tmp_path / 'manifest.json', budget=640)
    assert calls[0][1]['timeout'] == 600 and '--shards' not in calls[0][0]
    assert calls[1][1]['timeout'] == 640 and calls[1][0][-4:] == ['--shards', str(tmp_path / 'manifest.json'), '--shard-budget', '640']
    with pytest.raises(ValueError):
        suite.run_regression(sys.executable, tmp_path / 'bad.json', tmp_path / 'bad.progress.json', {}, shards=tmp_path / 'manifest.json', budget=901)
    assert len(calls) == 2


def test_acceptance_opt_in_keeps_partial_counts_without_full_regression(candidate, monkeypatch):
    from test_acceptance_runner import runner
    root, manifest, _ = candidate
    (root / 'docs/F1').mkdir(parents=True)
    row = {'id': 'AT-SYNTHETIC', 'stage': 'F1', 'gate': 'LIVE_BLOCKED', 'whole_status': 'NOT_RUN',
           'engineering_selectors': ['tests/test_a.py::test_one']}
    (root / 'docs/F1/ATBindings.json').write_text(json.dumps({'cases': [row]}))
    (root / 'docs/验收规格.json').write_text(json.dumps({'cases': [{'id': row['id']}]}))
    report = root / 'result.json'
    def execute(*args, **kwargs):
        assert kwargs['total_seconds'] == 30 and kwargs['env']['PYTHONPATH'] == str(root / 'src')
        junit = root / '.runtime/partial.xml'
        junit.write_text('<testsuite><testcase classname="test_a" name="test_one"/></testsuite>')
        return {'execution_exit_code': 1, 'coverage_complete': False, 'private_junit': '.runtime/partial.xml',
                'engineering_total_counts': {'PASS': 1, 'FAIL': 0, 'SKIP': 0}, 'shards': [{'id': 'S2', 'status': 'NOT_RUN'}]}
    monkeypatch.setitem(sys.modules, 'regression_shards', SimpleNamespace(execute=execute))
    monkeypatch.setattr(runner, 'ROOT', root)
    monkeypatch.setattr(sys, 'argv', ['run_acceptance', '--shards', str(manifest), '--shard-budget', '30', '--report', str(report)])
    with pytest.raises(SystemExit) as failure: runner.main()
    assert failure.value.code == 1
    saved = json.loads(report.read_text())
    assert not saved['full_regression'] and saved['whole_AT_EX'] == 'NOT_RUN'
    assert saved['engineering_total_counts'] == {'PASS': 1, 'FAIL': 0, 'SKIP': 0}
    assert saved['shards'][0]['status'] == 'NOT_RUN'


def test_native_shard_budget_exhaustion_does_not_launch_and_keeps_independent_stages(tmp_path, monkeypatch):
    from test_windows_ci_preparation import module
    suite = module('native_suite')
    suite.REPO = tmp_path
    monkeypatch.setattr(suite, 'require_server', lambda: None)
    monkeypatch.setattr(sys, 'executable', str(tmp_path / '.venv-windows/Scripts/python.exe'))
    monkeypatch.setattr(sys, 'argv', ['native_suite', '--report', str(tmp_path / 'report.json'), '--regression-shards', str(tmp_path / 'manifest.json')])
    config = {k: 'SYNTHETIC' for k in ('PARKWEAVE_OWNER_DSN', 'PARKWEAVE_DSN', 'PARKWEAVE_TEST_OWNER_DSN')}
    monkeypatch.setattr(suite, 'os', SimpleNamespace(environ=config))
    clock = iter([0, 701])
    monkeypatch.setattr(suite, 'time', SimpleNamespace(monotonic=lambda: next(clock)))
    records = []
    monkeypatch.setattr(suite, 'persist', lambda path, record, *args: records.append(json.loads(json.dumps(record))) or True)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if 'scripts/windows/file_candidate_probe.py' in command:
            return SimpleNamespace(returncode=1, stdout='NOT_RUN: explicit native Windows11', stderr='')
        return SimpleNamespace(returncode=1 if any(str(p).endswith('Setup.ps1') for p in command) else 0, stdout='', stderr='')
    monkeypatch.setattr(suite.subprocess, 'run', run)
    monkeypatch.setattr(suite, 'run_regression', lambda *args, **kwargs: pytest.fail('budget-exhausted child launched'))
    assert suite.main() == 1
    row = next(r for r in records[-1]['cases'] if r['case'] == 'full_engineering_regression')
    assert row['status'] == 'NOT_RUN' and row['reason'] == 'TOTAL_BUDGET_EXHAUSTED'
    assert any('scripts/windows/file_candidate_probe.py' in c for c in calls)
    assert any(any(str(p).endswith('ServerFileTest.ps1') for p in c) for c in calls)


def test_duplicate_stable_parameter_identity_is_rejected(tmp_path):
    path = tmp_path / 'collection.json'
    names = ['tests/test_a.py::test_one[uuid-a]', 'tests/test_a.py::test_one[uuid-b]']
    keys = [shards.case_key(n, {'value': 0}) for n in names]
    path.write_text(json.dumps({'schema': 2, 'nodeids': names, 'case_keys': keys}))
    with pytest.raises(ValueError, match='duplicate stable'): shards.collection(path, {'tests/test_a.py'})


def test_private_collection_accepts_existing_large_parameter_display_id(tmp_path):
    path = tmp_path / 'collection.json'
    name = 'tests/test_a.py::test_one[' + 'x' * 524288 + ']'
    key = shards.case_key(name, {'value': 0})
    path.write_text(json.dumps({'schema': 2, 'nodeids': [name], 'case_keys': [key]}))
    assert shards.collection(path, {'tests/test_a.py'}) == ([name], [key])
    oversized = 'tests/test_a.py::test_one[' + 'x' * (1024 * 1024) + ']'
    path.write_text(json.dumps({'schema': 2, 'nodeids': [oversized], 'case_keys': [key]}))
    with pytest.raises(ValueError, match='collection outside fixed files'):
        shards.collection(path, {'tests/test_a.py'})
    path.write_bytes(b'x' * (shards.MAX_REPORT_BYTES + 1))
    with pytest.raises(ValueError, match='collection exceeds bound'):
        shards.collection(path, {'tests/test_a.py'})


def test_budget_exhaustion_fixed_reason_survives_safe_annotation_projection():
    from test_windows_ci_preparation import module
    publisher = module('publish_summary')
    binding = {'synthetic': 'binding'}
    record = module('native_suite').summary([{'case': 'full_engineering_regression', 'status': 'NOT_RUN',
                                           'exit_code': 1, 'reason': 'TOTAL_BUDGET_EXHAUSTED'}])
    record.update(diagnostic_schema=1, diagnostic_binding=binding, report_state='COMPLETED', active_phase='UNKNOWN')
    public = publisher.project(record, binding)
    commands, ok = publisher.annotation_commands(public)
    assert ok and len(commands) == 2 and 'TOTAL_BUDGET_EXHAUSTED' in commands[1]
