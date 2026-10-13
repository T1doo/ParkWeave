"""Pure candidate tests. All PG/process/signal/privilege actions are intercepted."""
from copy import deepcopy
import json
import io
from pathlib import Path
import shutil
import signal
import socket
import stat
import subprocess
import tempfile
from types import SimpleNamespace

import psycopg
import pytest

from scripts.catalog_only import bootstrap as boot, probe
from test_linux_trial_catalog import trial_inputs

ROOT = Path(__file__).resolve().parents[1]
SHA, BASE = 'a'*40, 'b'*40
POISON = 'SYNTHETIC_PRIVATE_VALUE_MUST_NOT_BE_PUBLIC'


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*a, **kw):pytest.fail('physical action forbidden in catalog-only candidate tests')
    for obj, name in [(psycopg, 'connect'), (psycopg.Connection, 'connect'), (subprocess, 'Popen'),
            (subprocess, 'run'), (subprocess, 'check_output'), (socket.socket, 'connect'),
            (socket.socket, 'bind'), (signal, 'signal'), (signal, 'setitimer')]:
        monkeypatch.setattr(obj, name, denied)


def environment():
    return dict(CATALOG_REPOSITORY='T1doo/ParkWeave', CATALOG_REF=boot.BRANCH, CATALOG_EVENT='push',
        CATALOG_ATTEMPT='1', CATALOG_NUMBER='1', CATALOG_PUBLIC='true',
        RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Linux')


def approval():return dict(approved=True, source_sha=BASE, approval_ref=boot.APPROVAL_REF)


@pytest.mark.parametrize('change', [dict(CATALOG_REPOSITORY='elsewhere/repo'), dict(CATALOG_REF='refs/heads/main'),
    dict(CATALOG_EVENT='workflow_dispatch'), dict(CATALOG_ATTEMPT='2'), dict(CATALOG_NUMBER='2'),
    dict(CATALOG_PUBLIC='false'), dict(RUNNER_ENVIRONMENT='self-hosted'), dict(RUNNER_OS='Windows')])
def test_catalog_gate_rejects_other_scope_or_repeated_run(change):
    env = environment(); assert boot.approved_context(env, 1001, SHA, approval())
    env.update(change); assert not boot.approved_context(env, 1001, SHA, approval())


@pytest.mark.parametrize('change', [dict(approved=False), dict(approved=1), dict(source_sha=None),
    dict(source_sha='a'*39), dict(approval_ref='OLD_APPROVAL'), dict(extra=True)])
def test_catalog_gate_requires_new_strict_approval(change):
    receipt = approval(); receipt.update(change)
    assert not boot.approved_context(environment(), 1001, SHA, receipt)
    assert not boot.approved_context(environment(), 0, SHA, approval())


def test_catalog_pending_real_entry_stops_before_any_physical_action(monkeypatch, capsys):
    monkeypatch.chdir(ROOT)
    assert json.loads((ROOT/boot.APPROVAL_FILE).read_text()) == dict(approved=False, source_sha=None, approval_ref=None)
    assert boot.bootstrap(SHA) == 1
    output = json.loads(capsys.readouterr().out)
    assert output['cases']['GATE'] == 'FAIL'
    assert set(v for k, v in output['cases'].items() if k != 'GATE') == {'NOT_RUN'}


@pytest.mark.parametrize('bad', ['none', 'head', 'parent', 'merge', 'diff', 'dirty', 'previous', 'duplicate'])
def test_catalog_git_gate_binds_single_parent_and_only_approval_diff(tmp_path, monkeypatch, bad):
    target = tmp_path/boot.APPROVAL_FILE; target.parent.mkdir(parents=True)
    target.write_text(json.dumps(approval()))
    if bad == 'duplicate':target.write_text('{"approved":false,"approved":true,"source_sha":"'+BASE+'","approval_ref":"'+boot.APPROVAL_REF+'"}')
    outputs = {('rev-parse', 'HEAD'): SHA, ('rev-list', '--parents', '-n', '1', 'HEAD'): SHA+' '+BASE,
        ('diff', '--name-only', BASE, SHA): boot.APPROVAL_FILE, ('status', '--porcelain'): '',
        ('show', BASE+':'+boot.APPROVAL_FILE): json.dumps(dict(approved=False, source_sha=None, approval_ref=None))}
    if bad == 'head':outputs[('rev-parse', 'HEAD')] = 'c'*40
    if bad in ('parent','merge'):outputs[('rev-list', '--parents', '-n', '1', 'HEAD')] = SHA+' '+'c'*40+(' '+BASE if bad=='merge' else '')
    if bad == 'diff':outputs[('diff', '--name-only', BASE, SHA)] += '\nscripts/catalog_only/probe.py'
    if bad == 'dirty':outputs[('status', '--porcelain')] = ' M scripts/catalog_only/probe.py'
    if bad == 'previous':outputs[('show', BASE+':'+boot.APPROVAL_FILE)] = json.dumps(approval())
    monkeypatch.setattr(boot.os, 'geteuid', lambda:1001)
    monkeypatch.setattr(subprocess, 'check_output', lambda args, **kw:outputs[tuple(args[1:])])
    if bad == 'none':assert boot.gate(tmp_path, SHA, environment()) == BASE
    else:
        with pytest.raises((PermissionError, ValueError)):boot.gate(tmp_path, SHA, environment())


@pytest.mark.parametrize('field', ['extra', 'case', 'right', 'comparison', 'sha', 'failure_logs'])
def test_catalog_projection_never_emits_arbitrary_data(field):
    value = boot.initial(SHA)
    if field == 'extra':value[POISON] = POISON
    elif field == 'case':value['cases']['GATE'] = POISON
    elif field == 'right':value['rights']['before_app'] = POISON
    elif field == 'comparison':value['comparisons']['after']['status'] = POISON
    elif field == 'failure_logs':value['failure_logs'] = POISON
    else:value['source_sha'] = POISON
    with pytest.raises(ValueError) as error:boot.public_summary(value)
    assert POISON not in str(error.value)


def test_catalog_secondary_log_failure_keeps_public_stderr_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(boot, 'gate', lambda *_:BASE)
    monkeypatch.setattr(boot, 'open', lambda *a, **kw:io.StringIO(), raising=False)
    monkeypatch.setattr(boot.tempfile, 'mkdtemp', lambda **kw:str(tmp_path))
    def fail(*a, **kw):raise OSError(POISON)
    monkeypatch.setattr(subprocess, 'run', fail)
    monkeypatch.setattr(Path, 'write_text', fail)
    assert boot.bootstrap(SHA)==1
    captured=capsys.readouterr(); assert captured.err=='' and POISON not in captured.out
    output=json.loads(captured.out)
    assert output['failure_logs']=='UNAVAILABLE' and output['cases']['DEPENDENCIES']=='FAIL'


@pytest.mark.parametrize('phase', ['before', 'after'])
def test_catalog_actual_analyzer_return_paths_remain_non_authorizing(phase):
    spec, catalog = trial_inputs(); output = boot.initial(SHA)
    catalog['privileges']['app:control_system_execute'] = phase == 'before'
    probe.record_rights(catalog, output, phase)
    probe.analyze_snapshot(spec, catalog, output, phase)
    assert output['comparisons'][phase]['status'] == ('REFUSED' if phase == 'before' else 'PASS')
    assert output['comparisons'][phase]['changes'] == 'EMPTY'


@pytest.mark.parametrize('bad', ['raised', 'status', 'changes', 'authority', 'malformed'])
def test_catalog_analyzer_failure_unknown_and_exception_are_distinct(monkeypatch, bad):
    spec, catalog = trial_inputs(); output = boot.initial(SHA)
    report = probe.preflight.analyze(spec.model_dump(), catalog)
    if bad == 'status':report['status'] = 'REFUSED'
    if bad == 'changes':report['changes'] = [{'private':POISON}]
    if bad == 'authority':report['activation_enabled'] = True
    if bad == 'malformed':report = {'status':POISON, 'checks':POISON, 'changes':POISON}
    def analyze(*_):
        if bad == 'raised':raise TypeError(POISON)
        return report
    monkeypatch.setattr(probe.preflight, 'analyze', analyze)
    with pytest.raises((AssertionError,TypeError)):probe.analyze_snapshot(spec, catalog, output, 'after')
    row = output['comparisons']['after']
    assert row['call'] == ('RAISED' if bad=='raised' else 'RETURNED')
    if bad in ('raised','malformed'):assert row['status'] == 'UNKNOWN'
    assert POISON not in json.dumps(boot.public_summary(output))
    assert output['comparisons']['before']['call'] == 'NOT_RUN'


@pytest.mark.parametrize('value', [None, 0, 1, 'false', [], {}])
def test_catalog_effective_rights_require_actual_booleans(value):
    _, catalog = trial_inputs(); output = boot.initial(SHA)
    catalog['privileges']['app:control_system_execute'] = value
    with pytest.raises(AssertionError):probe.record_rights(catalog, output, 'after')
    assert output['rights']['after_app'] == 'UNKNOWN'


class Session:
    def __init__(self, spec, role, behavior):
        self.spec, self.role, self.behavior = spec, role, behavior
        self.info = SimpleNamespace(host=spec.policy.database_host, port=spec.policy.database_port)
        self.queries = []; self.row = None
    def __enter__(self):return self
    def __exit__(self, *args):return False
    def transaction(self):return self
    def execute(self, query):
        self.queries.append(query)
        if query.startswith('SELECT current_user'):
            self.row = dict(actual=self.role, session=self.role, database=self.spec.policy.database_name,
                oid=self.spec.policy.database_oid, superuser=False)
            if self.behavior == 'wrong_role':self.row['session'] = probe.OWNER
            if self.behavior == 'superuser':self.row['superuser'] = True
            if self.behavior == 'wrong_db':self.row['oid'] += 1
        elif query == probe.FUNCTION_QUERY:
            if self.behavior == 'denied':raise psycopg.errors.InsufficientPrivilege(POISON)
            if self.behavior == 'syntax':raise psycopg.errors.SyntaxError(POISON)
            if self.behavior == 'connection':raise psycopg.OperationalError(POISON)
            self.row = {'value':self.spec.policy.system_identifier if self.behavior != 'wrong_system' else 'wrong'}
        elif query == 'SELECT 1 value':self.row = {'value':1}
        else:pytest.fail('unexpected role query')
        return self
    def fetchone(self):return self.row


@pytest.mark.parametrize('role,allowed,behavior,passes', [
    (probe.APP, True, 'success', True), (probe.WRITER, True, 'success', True),
    (probe.APP, False, 'denied', True), (probe.APP, False, 'success', False),
    (probe.WRITER, True, 'denied', False), (probe.APP, False, 'syntax', False),
    (probe.APP, False, 'connection', False), (probe.APP, False, 'wrong_role', False),
    (probe.WRITER, True, 'superuser', False), (probe.APP, False, 'wrong_db', False),
    (probe.WRITER, True, 'wrong_system', False)])
def test_catalog_role_call_requires_separate_identity_and_precise_denial(monkeypatch, role, allowed, behavior, passes):
    spec, _ = trial_inputs(); session = Session(spec, role, behavior); connections = []
    def connect(dsn, **kw):
        assert psycopg.conninfo.conninfo_to_dict(dsn)['user'] == role
        assert kw['autocommit'] is True
        connections.append(dsn); return session
    monkeypatch.setattr(psycopg, 'connect', connect)
    if passes:probe.role_call('host=/tmp/SYNTHETIC_ONLY dbname=fixture_'+'a'*32, role, spec, allowed)
    else:
        with pytest.raises((AssertionError,psycopg.Error)):
            probe.role_call('host=/tmp/SYNTHETIC_ONLY dbname=fixture_'+'a'*32, role, spec, allowed)
    assert len(connections) == 1 and all('SET ROLE' not in q for q in session.queries)
    if passes and not allowed:assert session.queries[-1] == 'SELECT 1 value'


@pytest.mark.parametrize('failure', ['none', 'initdb', 'before_collect', 'fix', 'after_collect', 'stop', 'log', 'cleanup_log'])
def test_catalog_pipeline_commit_order_stop_and_cleanup_are_not_guessed(monkeypatch, failure):
    root = Path(tempfile.mkdtemp(prefix='parkweave-catalog-')); remove = shutil.rmtree
    events = []; state = {'fixed':False}; spec, baseline = trial_inputs()
    original_lstat = Path.lstat
    real_uid = probe.os.geteuid()
    monkeypatch.setattr(probe.os, 'geteuid', lambda: real_uid or 1001)
    # Current container may be root; synthetic metadata only, no ownership change.
    original_stat = Path.stat
    def fstat(path, *a, **kw):
        result = original_stat(path, *a, **kw)
        if path == root or path == root/'cluster':return SimpleNamespace(st_uid=real_uid or 1001, st_mode=result.st_mode)
        return result
    monkeypatch.setattr(Path, 'stat', fstat)
    monkeypatch.setattr(Path, 'lstat', lambda path:SimpleNamespace(st_mode=stat.S_IFREG|0o755, st_uid=0)
        if str(path).startswith('/usr/lib/postgresql/16/bin/') else original_lstat(path))
    monkeypatch.setattr(signal, 'signal', lambda *a:None)
    monkeypatch.setattr(signal, 'setitimer', lambda *a:None)
    original_write = Path.write_text
    def write(path, *a, **kw):
        if (failure=='log' and path.name=='probe-failure.log' or
                failure=='cleanup_log' and path.name=='cleanup-failure.log'):
            raise OSError(POISON)
        return original_write(path,*a,**kw)
    monkeypatch.setattr(Path,'write_text',write)
    def tool(args, **kw):
        events.append('initdb')
        if failure == 'initdb':raise subprocess.TimeoutExpired(args,60)
        data = root/'cluster/data'; data.mkdir(); (data/'PG_VERSION').write_text('16\n')
    monkeypatch.setattr(subprocess, 'run', tool)
    class Process:
        pid = 1009
        def __init__(self, args, **kw):
            self.done = False
            kw['stdout'].write(b'database system is ready to accept connections\n'); kw['stdout'].flush()
            (root/'cluster/data/postmaster.pid').write_text('1009\n')
        def poll(self):return 0 if self.done else None
        def terminate(self):events.append('terminate')
        def wait(self, timeout):
            if failure in ('stop','cleanup_log') and not self.done:raise subprocess.TimeoutExpired('SYNTHETIC',timeout)
            self.done=True; return 0
        def kill(self):events.append('kill'); self.done=True
    monkeypatch.setattr(subprocess, 'Popen', Process)
    class Connection:
        def __enter__(self):return self
        def __exit__(self, *args):
            events.append('rollback' if args[0] else 'commit'); return False
        def execute(self, query):
            if query == probe.REVOKE:
                events.append('revoke')
                if failure == 'fix':raise PermissionError(POISON)
                state['fixed']=True
            return self
    monkeypatch.setattr(psycopg, 'connect', lambda *a, **kw:Connection())
    owner = SimpleNamespace(dsn='SYNTHETIC_ONLY',connect=lambda:Connection(),migrate=lambda:events.append('migrate'))
    proof = SimpleNamespace(record_created_database=lambda c:object())
    monkeypatch.setattr(probe, 'Store', lambda *_:owner)
    monkeypatch.setattr(probe, 'capture_fixture_cluster', lambda *_:proof)
    monkeypatch.setattr(probe.native, 'install_owned_test_storage', lambda *_:events.append('storage'))
    monkeypatch.setattr(probe.activation, 'install_owned_test_activation_storage', lambda *_:events.append('activation_storage'))
    monkeypatch.setattr(probe, 'apply_initial_acl', lambda *_:events.append('initial_acl'))
    monkeypatch.setattr(probe, 'make_spec', lambda *_:spec)
    monkeypatch.setattr(probe, 'role_call', lambda _, role, _spec, allowed:events.append((role,allowed)))
    def collect(*_):
        phase='after' if state['fixed'] else 'before'; events.append('collect_'+phase)
        if failure==phase+'_collect' or failure=='log':raise TypeError(POISON)
        snapshot=deepcopy(baseline); snapshot['privileges']['app:control_system_execute']=not state['fixed']; return snapshot
    monkeypatch.setattr(probe.preflight, 'collect_owned_catalog', collect)
    try:
        output=probe.run(root, BASE); assert POISON not in json.dumps(output)
        if failure=='none':
            assert set(output['cases'].values())=={'PASS'}
            assert events[events.index('revoke')+1:events.index('collect_after')]==['commit']
            assert events.index((probe.APP,True))<events.index('revoke')<events.index((probe.APP,False))
        elif failure=='initdb':
            assert output['cases']['CLEANUP']=='UNKNOWN' and 'migrate' not in events
            assert output['cases']['BEFORE_RIGHTS']=='NOT_RUN'
        elif failure in ('stop','cleanup_log'):assert output['cases']['CLEANUP']=='FAIL' and 'kill' in events
        else:
            failing={'before_collect':'BEFORE_RIGHTS','log':'BEFORE_RIGHTS','fix':'APPLY_FIX','after_collect':'AFTER_RIGHTS'}[failure]
            assert output['cases'][failing]=='FAIL' and output['cases']['CLEANUP']=='PASS'
            if failure!='after_collect':assert 'collect_after' not in events
            if failure=='fix':assert 'rollback' in events
        if failure in ('log','cleanup_log'):assert output['failure_logs']=='UNAVAILABLE'
        if failure not in ('initdb','stop','cleanup_log'):assert not (root/'cluster').exists()
        else:assert (root/'cluster').exists()
    finally:remove(root)


def test_catalog_workflow_and_probe_stay_within_pending_catalog_scope():
    workflow=(ROOT/'.github/workflows/catalog-only-once.yml').read_text()
    assert 'timeout-minutes: 15' in workflow and 'runs-on: ubuntu-24.04' in workflow
    assert 'github.run_attempt == 1 && github.run_number == 1' in workflow
    assert 'fetch-depth: 2' in workflow and 'persist-credentials: false' in workflow
    assert 'branches: [dev/f2-catalog-only-once-20261013]' in workflow
    assert "paths: ['scripts/catalog_only/approval.json']" in workflow
    for forbidden in ('workflow_dispatch:', 'pull_request:', 'secrets.', 'sudo', 'apt ', 'upload-artifact', 'actions/cache', 'matrix:'):
        assert forbidden not in workflow
    text=(ROOT/'scripts/catalog_only/probe.py').read_text()
    for forbidden in ('native_run_access_restricted_host', 'native_run_access_restricted_runtime', 'TestClient', 'create_app', '.seed(', 'useradd', 'os.chmod', 'os.chown', 'os.setuid'):
        assert forbidden not in text
    assert probe.REVOKE in (ROOT/'scripts/linux_trial/worker.py').read_text()
