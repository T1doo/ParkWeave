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
