"""Independent pure probes; all storage is the review's own runtime."""
import builtins
from contextlib import nullcontext
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from psycopg.conninfo import make_conninfo
from scripts.case_pg_vertical import bootstrap as entry, probe
from scripts.case_pg_vertical.owned_pg import OwnedPG


def test_real_hook_acl_failure_still_finalizes_original_fixture(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(builtins, '_vertical_independent_seen', seen, raising=False)
    target = tmp_path / 'test_acl_hook_failure.py'
    target.write_text('''import pytest,builtins
@pytest.fixture(scope="session")
def pg():
 raise AssertionError("ORIGINAL_PG_MUST_NOT_RUN")
@pytest.fixture
def fixture(pg):
 try:
  yield ("APP", "OWNER", "SYNTHETIC", "ASGI")
 finally:
  builtins._vertical_independent_seen.append("FINALIZED")
def test_case(fixture):
 builtins._vertical_independent_seen.append("BODY_MUST_NOT_RUN")
''')
    def refuse(*args):
        raise probe.Denied('SYNTHETIC_ACL_HOOK_FAILURE')
    monkeypatch.setattr(probe, 'close_app_control', refuse)
    monkeypatch.setenv('PYTEST_DISABLE_PLUGIN_AUTOLOAD', '1')
    rows = [dict(id='PG01', nodeid='test_acl_hook_failure.py::test_case', group='CASE')]
    output = entry.initial('a' * 40)
    result = probe.Results(rows, output)
    supplier = probe.SessionSupplier(SimpleNamespace(get_uri=lambda: 'PRIVATE'))
    code = pytest.main([str(target), '-q', '-p', 'no:cacheprovider', '--tb=no',
        '--rootdir=' + str(tmp_path), '--basetemp=' + str(tmp_path / 'nested')], plugins=[supplier, result])
    assert int(code) == 1 and supplier.calls == 1
    assert seen == ['FINALIZED']
    assert output['tests']['PG01'] == 'ERROR'
    assert result.case_acl_checks == 0
    assert result.phases['PG01'] == dict(setup='failed', teardown='passed')
    assert 'SYNTHETIC_ACL_HOOK_FAILURE' not in json.dumps(entry.public_summary(output))


def test_scoped_connect_positive_both_entrypoints_use_saved_callable(monkeypatch):
    calls = []
    marker = object()
    def original(conninfo='', **kwargs):
        calls.append((conninfo, kwargs))
        return marker
    monkeypatch.setattr(probe.psycopg, 'connect', original)
    pg = Mock()
    with probe.scoped_test_io(pg):
        assert probe.psycopg.connect('SYNTHETIC', autocommit=True) is marker
        assert probe.psycopg.Connection.connect('SYNTHETIC', row_factory=None) is marker
    assert len(calls) == pg.validate_connection.call_count == 2
    assert probe.psycopg.connect is original


@pytest.mark.parametrize('kwargs', [
    {'host': '/tmp/other'}, {'user': 'outside'}, {'dbname': 'existing'},
    {'passfile': '/tmp/existing'}, {'service': 'existing'}, {'password': 'SYNTHETIC'},
    {'hostaddr': '127.0.0.1'}, {'sslmode': 'require'}, {'gssencmode': 'require'},
])
def test_connection_kwargs_cannot_override_valid_owned_dsn(tmp_path, kwargs):
    pg = OwnedPG(tmp_path)
    dsn = make_conninfo(host=str(pg.cluster / 'socket'), port='55441',
        dbname='fixture_' + 'a' * 32, user='parkweave_app',
        passfile=str(pg.root / 'empty.pgpass'), sslmode='disable', gssencmode='disable')
    with pytest.raises(PermissionError):
        pg.validate_connection(dsn, kwargs)


@pytest.mark.parametrize('wrong', ['system_identifier', 'data_directory', 'postmaster_start', 'current_name'])
def test_real_same_cluster_validation_refuses_before_revoke(monkeypatch, wrong):
    started = datetime.now(timezone.utc)
    cluster = probe.facts.FixtureClusterEvidence('SYNTHETIC', '/tmp/SYNTHETIC', started,
        'pwci_owner', (), uuid4())
    proof = probe.facts.FixtureDatabaseEvidence(cluster, 'fixture_' + 'a' * 32, 123, uuid4())
    monkeypatch.setattr(probe.facts, '_fixture_clusters', {cluster.nonce: cluster})
    monkeypatch.setattr(probe.facts, '_fixture_databases', {proof.nonce: proof})
    identity = dict(system_identifier=cluster.system_identifier, data_directory=cluster.data_directory,
        postmaster_start=started, current_name=cluster.owner, database_name=proof.database_name,
        database_oid=123, owner_name=cluster.owner, session_name=cluster.owner)
    identity[wrong] = 'SYNTHETIC_WRONG'
    monkeypatch.setattr(probe.facts, '_migration_identity', lambda c: identity)
    owner_connection = Mock()
    owner = SimpleNamespace(_case_fact_fixture_receipt=proof, connect=lambda: nullcontext(owner_connection))
    store = Mock()
    with pytest.raises(probe.Denied):
        probe.close_app_control(owner, store)
    owner_connection.execute.assert_not_called()
    store.connect.assert_not_called()


def test_new_bootstrap_double_logging_failure_remains_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(entry, 'gate', lambda *a: 'b' * 40)
    monkeypatch.setattr(entry.tempfile, 'mkdtemp', lambda **k: str(tmp_path))
    original_open = builtins.open
    monkeypatch.setattr(builtins, 'open', lambda p, *a, **k:
        io.StringIO() if str(p).endswith('.claim') else original_open(p, *a, **k))
    def fail(*a, **k):
        raise OSError('SYNTHETIC_PRIVATE_DETAIL')
    monkeypatch.setattr(entry.subprocess, 'run', fail)
    monkeypatch.setattr(Path, 'write_text', fail)
    assert entry.bootstrap('a' * 40) == 1
    captured = capsys.readouterr()
    assert captured.err == '' and 'SYNTHETIC_PRIVATE_DETAIL' not in captured.out
    result = json.loads(captured.out)
    assert result['failure_logs'] == 'UNAVAILABLE'
    assert result['stages']['DEPENDENCIES'] == 'FAIL'
    assert set(result['tests'].values()) == {'NOT_RUN'}


def test_new_probe_main_and_cleanup_logging_failures_remain_closed(tmp_path, monkeypatch):
    pg = Mock()
    pg.start.side_effect = RuntimeError('SYNTHETIC_START_PRIVATE')
    pg.stop.side_effect = RuntimeError('SYNTHETIC_STOP_PRIVATE')
    monkeypatch.setattr(probe, 'OwnedPG', lambda root: pg)
    monkeypatch.setattr(probe.signal, 'getsignal', lambda s: None)
    monkeypatch.setattr(probe.signal, 'signal', lambda *a: None)
    monkeypatch.setattr(probe.signal, 'setitimer', lambda *a: None)
    def fail(*a, **k):
        raise OSError('SYNTHETIC_LOG_PRIVATE')
    monkeypatch.setattr(Path, 'write_text', fail)
    result = probe.run(tmp_path, 'a' * 40)
    assert result['failure_logs'] == 'UNAVAILABLE'
    assert result['stages']['PG16_START'] == result['stages']['PG_CLEANUP'] == 'FAIL'
    assert set(result['tests'].values()) == {'NOT_RUN'}
    assert 'SYNTHETIC' not in json.dumps(result)
    pg.stop.assert_called_once()
