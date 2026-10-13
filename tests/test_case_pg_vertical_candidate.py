"""Offline harness contracts. No server, role, connection or cloud execution."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json
import subprocess

import pytest

from scripts.case_pg_vertical import bootstrap as entry, probe
from scripts.case_pg_vertical.owned_pg import OwnedPG


def approved_env():
    return dict(VERTICAL_REPOSITORY='T1doo/ParkWeave', VERTICAL_REF=entry.BRANCH,
        VERTICAL_EVENT='push', VERTICAL_ATTEMPT='1', VERTICAL_NUMBER='1', VERTICAL_PUBLIC='true',
        RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Linux')


def gate_fixture(tmp_path, monkeypatch):
    sha, parent = 'a'*40, 'b'*40
    path = tmp_path/entry.APPROVAL_FILE; path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(approved=True, source_sha=parent, approval_ref=entry.APPROVAL_REF)))
    responses = {'rev-parse': sha, 'rev-list': sha+' '+parent, 'diff': entry.APPROVAL_FILE,
        'status': '', 'show': json.dumps(dict(approved=False, source_sha=None, approval_ref=None))}
    calls = []
    def git(args, **kwargs):
        calls.append(args)
        assert args[0] == '/usr/bin/git' and kwargs['env'] == {'LANG': 'C.UTF-8'}
        return responses[args[1]]
    monkeypatch.setattr(entry.os, 'geteuid', lambda: 1001)
    monkeypatch.setattr(entry.subprocess, 'check_output', git)
    return sha, parent, path, responses, calls


@pytest.mark.parametrize('field,value', [('VERTICAL_REF', 'refs/heads/dev/f2-catalog-only-once-20261013'),
    ('VERTICAL_REPOSITORY', 'other/repo'), ('VERTICAL_EVENT', 'workflow_dispatch'), ('VERTICAL_ATTEMPT', '2'),
    ('VERTICAL_NUMBER', '2'), ('VERTICAL_PUBLIC', 'false'), ('RUNNER_ENVIRONMENT', 'self-hosted'), ('RUNNER_OS', 'Windows')])
def test_vertical_gate_refuses_other_context_before_git(tmp_path, monkeypatch, field, value):
    sha, _, _, _, calls = gate_fixture(tmp_path, monkeypatch)
    env = approved_env(); env[field] = value
    with pytest.raises(PermissionError):entry.gate(tmp_path, sha, env)
    assert not calls


@pytest.mark.parametrize('kind', ['pending', 'old-marker', 'duplicate', 'extra', 'boolean', 'root', 'sha'])
def test_vertical_gate_requires_new_exact_approval(tmp_path, monkeypatch, kind):
    sha, parent, path, _, calls = gate_fixture(tmp_path, monkeypatch)
    receipt = dict(approved=True, source_sha=parent, approval_ref=entry.APPROVAL_REF)
    if kind == 'pending':receipt['approved'] = False
    elif kind == 'old-marker':receipt['approval_ref'] = 'USER_CONFIRMED_CATALOG_ONLY_ONCE_20261013'
    elif kind == 'extra':receipt['allow'] = True
    elif kind == 'boolean':receipt['approved'] = 1
    elif kind == 'root':monkeypatch.setattr(entry.os, 'geteuid', lambda: 0)
    elif kind == 'sha':sha = 'bad'
    path.write_text(json.dumps(receipt) if kind != 'duplicate' else '{"approved":true,"approved":true}')
    with pytest.raises((PermissionError, ValueError)):entry.gate(tmp_path, sha, approved_env())
    assert not calls


@pytest.mark.parametrize('cmd,value', [('rev-parse', 'c'*40), ('rev-list', 'a'*40+' '+'b'*40+' '+'c'*40),
    ('diff', entry.APPROVAL_FILE+'\nsrc/parkweave/store.py'), ('status', ' M README'), ('show', '{"approved":true}')])
def test_vertical_gate_single_parent_and_approval_only(tmp_path, monkeypatch, cmd, value):
    sha, parent, _, responses, _ = gate_fixture(tmp_path, monkeypatch)
    assert entry.gate(tmp_path, sha, approved_env()) == parent
    responses[cmd] = value
    with pytest.raises(PermissionError):entry.gate(tmp_path, sha, approved_env())


def test_vertical_selection_preserves_seven_original_and_excludes_host_preview():
    rows = entry.selection(); assert len(rows) == 27
    old = json.loads(Path('docs/F2/evidence/catalog-only-candidate-20261013/root/final-candidate/physical-not-run.json').read_text())['test_ids']
    assert [r['nodeid'] for r in rows[:7]] == old
    assert not any('preview' in r['nodeid'] or 'restricted_host' in r['nodeid'] for r in rows)


@pytest.mark.parametrize('corrupt', ['extra', 'free-state', 'free-diagnostic', 'large-line', 'raw-trace'])
def test_vertical_output_rejects_unbounded_values(corrupt):
    value = entry.initial('a'*40)
    if corrupt == 'extra':value['raw_exception'] = 'SYNTHETIC_SECRET'
    elif corrupt == 'free-state':value['tests']['PG01'] = 'SYNTHETIC_SECRET'
    else:
        value['diagnostics'] = [dict(id='PG01', phase='call', line=7, trace_sha256='b'*64)]
        if corrupt == 'free-diagnostic':value['diagnostics'][0]['raw'] = 'SYNTHETIC_SECRET'
        elif corrupt == 'large-line':value['diagnostics'][0]['line'] = 10001
        else:value['diagnostics'][0]['trace_sha256'] = 'SYNTHETIC_SECRET'
    with pytest.raises(ValueError):entry.public_summary(value)


def test_vertical_report_never_passes_before_teardown_and_cleanup_failure_overrides():
    rows = entry.selection(); output = entry.initial('a'*40); results = probe.Results(rows, output)
    for phase in ('setup', 'call'):
        results.pytest_runtest_logreport(SimpleNamespace(nodeid=rows[0]['nodeid'], when=phase,
            outcome='passed', failed=False, skipped=False))
        assert output['tests']['PG01'] == 'UNKNOWN'
    results.pytest_runtest_logreport(SimpleNamespace(nodeid=rows[0]['nodeid'], when='teardown',
        outcome='failed', failed=True, skipped=False, longrepr='SYNTHETIC private details'))
    assert output['tests']['PG01'] == 'ERROR'
    assert 'SYNTHETIC' not in json.dumps(entry.public_summary(output))


@pytest.mark.parametrize('phase', ['setup', 'call'])
def test_vertical_skipped_report_never_becomes_pass(phase):
    rows = entry.selection(); output = entry.initial('a'*40); results = probe.Results(rows, output)
    results.pytest_runtest_logreport(SimpleNamespace(nodeid=rows[0]['nodeid'], when=phase,
        outcome='skipped', failed=False, skipped=True))
    results.pytest_runtest_logreport(SimpleNamespace(nodeid=rows[0]['nodeid'], when='teardown',
        outcome='passed', failed=False, skipped=False))
    assert output['tests']['PG01'] == 'SKIP'


def test_vertical_adapter_overrides_original_session_supplier_without_calling_it(tmp_path, monkeypatch):
    # Nested in-process pytest proves hook precedence against a real pg fixture.
    test = tmp_path/'test_supplier.py'
    test.write_text('import pytest\n@pytest.fixture(scope="session")\ndef pg():\n raise AssertionError("ORIGINAL_PG_MUST_NOT_RUN")\ndef test_use(pg):\n assert pg == "SYNTHETIC_SUPPLIER"\n')
    supplier = probe.SessionSupplier(SimpleNamespace(get_uri=lambda: 'PRIVATE'))
    supplier.pg = SimpleNamespace(get_uri=lambda: 'PRIVATE')
    (tmp_path/'test_supplier.py').write_text(test.read_text().replace('assert pg == "SYNTHETIC_SUPPLIER"', 'assert pg.get_uri() == "PRIVATE"'))
    monkeypatch.setenv('PYTEST_DISABLE_PLUGIN_AUTOLOAD', '1')
    result = pytest.main([str(test), '-q', '-p', 'no:cacheprovider', '--basetemp='+str(tmp_path/'nested')], plugins=[supplier])
    assert result == 0 and supplier.calls == 1


def test_vertical_collection_drift_refuses_before_fixture():
    rows = entry.selection(); output = entry.initial('a'*40); results = probe.Results(rows, output)
    with pytest.raises(pytest.UsageError):results.pytest_collection_modifyitems(None, None, [])
    assert output['stages']['COLLECTION'] == 'FAIL'


@pytest.mark.parametrize('change', [dict(host='/tmp/other'), dict(port='5432'), dict(dbname='existing'),
    dict(user='postgres'), dict(passfile='/tmp/old'), dict(sslmode='prefer'), dict(gssencmode='prefer'),
    dict(service='existing'), dict(password='SYNTHETIC'), dict(hostaddr='127.0.0.1')])
def test_vertical_connection_cannot_leave_new_cluster(change):
    from psycopg.conninfo import make_conninfo
    pg = OwnedPG(Path('/tmp/parkweave-case-pg-synthetic'))
    d = dict(host=str(pg.cluster/'socket'), port='55441', dbname='fixture_'+'a'*32, user='parkweave_app',
        passfile=str(pg.root/'empty.pgpass'), sslmode='disable', gssencmode='disable')
    pg.validate_connection(make_conninfo(**d), {'row_factory': object(), 'autocommit': True})
    with pytest.raises(PermissionError):pg.validate_connection(make_conninfo(**{**d, **change}), {})


@pytest.mark.parametrize('exitcode', [-9, 1, False, None])
def test_vertical_abnormal_pg_stop_preserves_owned_directory(tmp_path, monkeypatch, exitcode):
    pg = OwnedPG(tmp_path); pg.cluster.mkdir(); pg.created = pg.init_started = pg.init_complete = True
    pg.process = Mock(); pg.process.poll.return_value = exitcode
    with pytest.raises(RuntimeError):pg.stop()
    assert pg.cluster.exists()


def test_vertical_unconfirmed_init_retains_directory_and_normal_exit_removes(tmp_path):
    pg = OwnedPG(tmp_path); pg.cluster.mkdir(); pg.created = pg.init_started = True
    assert pg.stop() == 'UNKNOWN' and pg.cluster.exists()
    pg.init_complete = True; pg.process = Mock(); pg.process.poll.return_value = 0
    assert pg.stop() == 'PASS' and not pg.cluster.exists()


def test_vertical_forced_stop_is_failure_even_when_kill_finishes_zero(tmp_path):
    pg = OwnedPG(tmp_path); pg.cluster.mkdir(); pg.created = pg.init_started = pg.init_complete = True
    pg.process = Mock(); pg.process.poll.return_value = None
    pg.process.wait.side_effect = [subprocess.TimeoutExpired('OWNED', 10), 0]
    with pytest.raises(RuntimeError):pg.stop()
    pg.process.kill.assert_called_once(); assert pg.cluster.exists()


def test_vertical_scoped_io_refuses_external_process_network_and_connection(monkeypatch):
    pg = Mock(); pg.validate_connection.side_effect = PermissionError('OUTSIDE')
    with probe.scoped_test_io(pg):
        with pytest.raises(PermissionError):probe.psycopg.connect('SYNTHETIC_OUTSIDE')
        with pytest.raises(PermissionError):probe.psycopg.Connection.connect('SYNTHETIC_OUTSIDE')
        with pytest.raises(PermissionError):probe.subprocess.Popen(['SYNTHETIC'])
        with probe.socket.socket() as sock:
            with pytest.raises(PermissionError):sock.connect(('127.0.0.1', 1))
            with pytest.raises(PermissionError):sock.bind(('127.0.0.1', 0))


def test_vertical_actual_pending_entry_cannot_start_physical_action(monkeypatch, capsys):
    assert json.loads(Path(entry.APPROVAL_FILE).read_text()) == dict(approved=False, source_sha=None, approval_ref=None)
    def forbidden(*a, **k):raise AssertionError('PHYSICAL_ACTION_MUST_NOT_RUN')
    monkeypatch.setattr(entry.subprocess, 'run', forbidden)
    monkeypatch.setattr(entry.tempfile, 'mkdtemp', forbidden)
    assert entry.bootstrap('a'*40) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['stages']['GATE'] == 'FAIL' and set(result['tests'].values()) == {'NOT_RUN'}


def test_vertical_real_pytest_fixture_wrapper_and_teardown_reporting(tmp_path, monkeypatch):
    test = tmp_path/'test_pipeline.py'
    test.write_text('''import pytest
@pytest.fixture(scope="session")
def pg():
 raise AssertionError("PGSERVER_NOT_ALLOWED")
@pytest.fixture
def fixture(pg):
 yield ("APP", "OWNER", "TOKEN", "ASGI")
 raise RuntimeError("SYNTHETIC_TEARDOWN_FAILURE")
def test_case(fixture):
 assert fixture[0] == "APP"
''')
    checks = []
    monkeypatch.setattr(probe, 'close_app_control', lambda owner, store: checks.append((owner, store)))
    monkeypatch.setenv('PYTEST_DISABLE_PLUGIN_AUTOLOAD', '1')
    rows = [dict(id='PG01', nodeid='test_pipeline.py::test_case', group='CASE')]
    output = entry.initial('a'*40); results = probe.Results(rows, output)
    supplier = probe.SessionSupplier(SimpleNamespace(get_uri=lambda: 'PRIVATE'))
    code = pytest.main([str(test), '-q', '-p', 'no:cacheprovider', '--rootdir='+str(tmp_path),
        '--basetemp='+str(tmp_path/'nested'), '--tb=no'], plugins=[supplier, results])
    assert code == 1 and supplier.calls == 1 and results.collected
    assert checks == [('OWNER', 'APP')] and results.case_acl_checks == 1
    assert output['tests']['PG01'] == 'ERROR'
    assert output['diagnostics'][0]['phase'] == 'teardown'
    assert 'SYNTHETIC_TEARDOWN_FAILURE' not in json.dumps(entry.public_summary(output))


@pytest.mark.parametrize('problem', ['none', 'forged', 'wrong-db', 'no-denial', 'wrong-error', 'bad-recovery'])
def test_vertical_fixture_acl_uses_issued_same_db_and_real_42501(monkeypatch, problem):
    from contextlib import nullcontext
    from datetime import datetime, timezone
    from uuid import uuid4
    cluster = probe.facts.FixtureClusterEvidence('SYNTHETIC', '/tmp/SYNTHETIC', datetime.now(timezone.utc),
        'pwci_owner', (), uuid4())
    proof = probe.facts.FixtureDatabaseEvidence(cluster, 'fixture_'+'a'*32, 123, uuid4())
    monkeypatch.setattr(probe.facts, '_fixture_databases', {} if problem == 'forged' else {proof.nonce: proof})
    monkeypatch.setattr(probe.facts, '_fixture_clusters', {cluster.nonce: cluster})
    identity = dict(database_name='wrong' if problem == 'wrong-db' else proof.database_name,
        database_oid=123, owner_name='pwci_owner', session_name='pwci_owner')
    monkeypatch.setattr(probe.facts, '_migration_identity', lambda c: identity)
    monkeypatch.setattr(probe.facts, '_same_cluster', lambda a, b: None)
    owner_connection = Mock(); app_connection = Mock()
    def execute(query):
        if 'pg_control_system' in query:
            if problem == 'no-denial':return None
            if problem == 'wrong-error':raise ValueError('NOT_PERMISSION_DENIAL')
            raise probe.psycopg.errors.InsufficientPrivilege('SYNTHETIC')
        return SimpleNamespace(fetchone=lambda: {'value': 0 if problem == 'bad-recovery' else 1})
    app_connection.execute.side_effect = execute
    owner = SimpleNamespace(_case_fact_fixture_receipt=proof, connect=lambda: nullcontext(owner_connection))
    store = SimpleNamespace(connect=lambda: nullcontext(app_connection))
    if problem == 'none':
        probe.close_app_control(owner, store)
        app_connection.rollback.assert_called_once()
        assert owner_connection.execute.call_args.args == (catalog_revoke(),)
    else:
        with pytest.raises((probe.Denied, AssertionError, ValueError)):probe.close_app_control(owner, store)
        if problem in ('forged', 'wrong-db'):owner_connection.execute.assert_not_called()


def catalog_revoke():
    return 'REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM PUBLIC'


def test_vertical_dependency_setup_closes_existing_auth_discovery(tmp_path, monkeypatch, capsys):
    import builtins, io, sys
    import scripts.case_pg_vertical.probe as actual_probe
    parent = 'b'*40
    monkeypatch.setattr(entry, 'gate', lambda *a: parent)
    monkeypatch.setattr(entry.tempfile, 'mkdtemp', lambda **kw: str(tmp_path))
    original_open = builtins.open
    monkeypatch.setattr(builtins, 'open', lambda file, *a, **k: io.StringIO() if str(file).endswith('.claim') else original_open(file, *a, **k))
    calls = []
    monkeypatch.setattr(entry.subprocess, 'run', lambda args, **kw: calls.append((args, kw)))
    monkeypatch.setattr(sys, 'path', list(sys.path))
    result = entry.initial(parent)
    for key in ('stages', 'tests'):result[key] = {k: 'PASS' for k in result[key]}
    monkeypatch.setattr(actual_probe, 'run', lambda *a: result)
    assert entry.bootstrap('a'*40) == 0
    command, options = calls[0]
    assert all(flag in command for flag in ('--isolated', '--no-input', '--keyring-provider=disabled', '--no-cache-dir', '--no-compile'))
    assert options['env'] == {'LANG': 'C.UTF-8', 'PATH': '/usr/bin:/bin', 'NETRC': str(tmp_path/'empty.netrc'), 'PIP_CONFIG_FILE': entry.os.devnull}
    assert not (tmp_path/'empty.netrc').read_bytes()
    assert json.loads(capsys.readouterr().out)['source_sha'] == parent


@pytest.mark.parametrize('problem', ['none', 'test-fail', 'teardown-fail', 'adapter-unused', 'pgserver-import', 'leftover-db', 'cleanup-fail'])
def test_vertical_full_probe_aggregation_requires_tests_adapter_and_cleanup(tmp_path, monkeypatch, problem):
    pg = Mock(); pg.stop.return_value = 'PASS'; pg.fixtures_removed.return_value = problem != 'leftover-db'
    if problem == 'cleanup-fail':pg.stop.side_effect = RuntimeError('SYNTHETIC')
    monkeypatch.setattr(probe, 'OwnedPG', lambda root: pg)
    monkeypatch.setattr(probe.signal, 'getsignal', lambda s: None)
    monkeypatch.setattr(probe.signal, 'signal', lambda *a: None)
    monkeypatch.setattr(probe.signal, 'setitimer', lambda *a: None)
    from contextlib import nullcontext
    monkeypatch.setattr(probe, 'scoped_test_io', lambda pg: nullcontext())
    def execute(args, plugins):
        supplier, results = plugins; supplier.calls = 0 if problem == 'adapter-unused' else 1
        results.collected = True; results.case_acl_checks = 19
        results.output['stages']['COLLECTION'] = 'PASS'
        results.output['tests'] = {k: 'PASS' for k in results.output['tests']}
        if problem in ('test-fail', 'teardown-fail'):
            results.output['tests']['PG01'] = 'FAIL' if problem == 'test-fail' else 'ERROR'
            return 1
        return 0
    monkeypatch.setattr(probe.pytest, 'main', execute)
    if problem == 'pgserver-import':monkeypatch.setitem(probe.sys.modules, 'pgserver', object())
    result = probe.run(tmp_path, 'a'*40)
    assert all(v == 'PASS' for v in result['stages'].values()) == (problem == 'none')
    pg.stop.assert_called_once()
    if problem in ('test-fail', 'teardown-fail'):
        assert result['tests']['PG01'] == ('FAIL' if problem == 'test-fail' else 'ERROR')
        assert result['stages']['TESTS'] == 'FAIL'
    if problem == 'cleanup-fail':assert result['stages']['PG_CLEANUP'] == 'FAIL'
