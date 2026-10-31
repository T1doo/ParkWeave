"""Controlled ports only: no PG instance, native evidence, network or secrets.

These checks exercise new Python composition/SQL-call boundaries. Their memory
responses and mocked readiness do NOT establish native or product acceptance.
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from scripts.windows import lifecycle
from . import application_readiness
from .controller import CandidateRefused, ControlFailure, NativeDatabaseOperations
from .local_preparation import (
    SCOPE, PreparationCheckpoint, PreparationCommandUnknown, PreparationReference,
    PreparationWorkspace, LocalPreparationInvocation, compose_local_preparation,
)
from .local_preparation_identity import (
    ENTERPRISES, REVIEWERS, PreparationDatabaseOperations, PreparationIdentities,
    PreparationSecurity, seed_preparation_transaction,
)
from .test_controller import FakeInstallation

RUN, CASE, PREP = [str(UUID(int=n)) for n in (1, 2, 3)]


def identities():
    # Public deterministic test labels, never actual generated credentials.
    return PreparationIdentities.from_mapping(
        {name: 'PUBLIC_SYNTHETIC_TEST_' + name for name in ENTERPRISES + REVIEWERS})


def event(action, revision, actor='fixture-a', **extra):
    state = {'CREATE': 'IN_PREPARATION', 'ADD_EVIDENCE': 'IN_PREPARATION',
             'REVIEW': 'REVIEWED', 'CONFIRM': 'LOCAL_CONFIRMED'}[action]
    return dict(SCOPE, preparation_id=PREP, run_id=RUN, case_id=CASE,
                action=action, actor_id=actor, revision=revision, state=state, **extra)


def reference(revision=1, state='IN_PREPARATION'):
    return PreparationReference(PREP, RUN, CASE, revision, state)


def view():
    return dict(SCOPE, preparation=dict(id=PREP, run_id=RUN, case_id=CASE,
                revision=5, state='LOCAL_CONFIRMED'),
                current_materials=[dict(slot='need_summary', source_sha256='a' * 64),
                                   dict(slot='material_outline', source_sha256='b' * 64)],
                material_history=[dict(slot='need_summary', version=1),
                                  dict(slot='material_outline', version=1)],
                history=[dict(revision=n, action=action) for n, action in enumerate(
                    ['CREATE', 'ADD_EVIDENCE', 'ADD_EVIDENCE', 'REVIEW', 'CONFIRM'], 1)],
                snapshot_sha256='c' * 64)


class ScriptedRequests:
    """Predeclared API responses; not a simulated database/worker or HTTP server."""
    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = []

    def request(self, application, actor, method, path, body, key, deadline):
        actor.expected()
        if method == 'POST' and path.endswith('/commands'):
            from parkweave.preparation import PreparationCommand
            PreparationCommand.model_validate(body)  # Actual server wire contract, including fields_set.
        self.calls.append((actor.actor[0], method, path, deepcopy(body), key))
        expected_actor, expected_method, expected_path, response = self.steps.pop(0)
        assert (actor.actor[0], method, path) == (expected_actor, expected_method, expected_path)
        if isinstance(response, BaseException):
            raise response
        return deepcopy(response)


def workspace(transport, check=lambda: None):
    return PreparationWorkspace(object(), identities(), transport, check)


def test_explicit_case_material_review_confirm_and_read_only_reopen_chain():
    commands = '/api/preparations/' + PREP + '/commands'
    transport = ScriptedRequests([
        ('fixture-a', 'POST', '/api/runs', {'run_id': RUN}),
        ('fixture-a', 'GET', '/api/runs/' + RUN, {'state': 'SUCCEEDED'}),
        ('fixture-a', 'POST', '/api/preparations', event('CREATE', 1)),
        ('fixture-a', 'POST', commands, event('ADD_EVIDENCE', 2)),
        ('fixture-a', 'POST', commands, event('ADD_EVIDENCE', 3)),
        ('prep-specialist-fixture-a', 'POST', commands,
         event('REVIEW', 4, 'prep-specialist-fixture-a')),
        ('fixture-a', 'POST', commands, event('CONFIRM', 5)),
        ('fixture-a', 'GET', '/api/preparations/' + PREP, view()),
        ('fixture-a', 'GET', '/api/preparations/' + PREP, view()),
    ])
    first = workspace(transport)
    owner, reviewer = first.enterprise, first.reviewer
    run_id = owner.submit_case('SYNTHETIC local preparation', 'case-key')
    ref = owner.create_preparation(run_id, 'preparation-key')
    ref = owner.add_evidence(ref, 'summary-key', slot='need_summary',
                             text='SYNTHETIC request', source_label='SYNTHETIC document v1')
    ref = owner.add_evidence(ref, 'outline-key', slot='material_outline',
                             text='SYNTHETIC material list', source_label='SYNTHETIC document v1')
    with pytest.raises(CandidateRefused, match='action role'):
        owner.review(ref, 'bad-self-review', reason='not a specialist')
    ref = reviewer.review(ref, 'review-key', reason='Explicit independent specialist action')
    with pytest.raises(CandidateRefused, match='action role'):
        reviewer.confirm(ref, 'bad-self-confirm', reason='not enterprise owner')
    ref = owner.confirm(ref, 'confirm-key', reason='Explicit enterprise local confirmation')
    checkpoint = owner.checkpoint(ref)
    assert type(checkpoint) is PreparationCheckpoint
    assert checkpoint.reference.state == 'LOCAL_CONFIRMED'
    first.close()
    with pytest.raises(CandidateRefused, match='session ended'):
        owner.read(ref)
    second = workspace(transport)  # NEW client invocation, not native restart proof.
    assert second.enterprise.verify_reopened(checkpoint).view == checkpoint.view
    assert transport.calls[-1][1] == 'GET'
    assert len(transport.calls) == 9 and not transport.steps
    assert transport.calls[0][3]['source'] == 'SYNTHETIC'
    assert transport.calls[2][3]['reviewer_id'] == 'prep-specialist-fixture-a'
    assert all(row[3]['expected_revision'] == revision for row, revision in
               zip(transport.calls[3:7], [1, 2, 3, 4]))


def test_worker_not_finished_never_submits_preparation():
    transport = ScriptedRequests([('fixture-a', 'GET', '/api/runs/' + RUN, {'state': 'QUEUED'})])
    with pytest.raises(CandidateRefused, match='worker must finish'):
        workspace(transport).enterprise.create_preparation(RUN, 'same-key')
    assert len(transport.calls) == 1 and not transport.steps


@pytest.mark.parametrize('response', [
    OSError('PRIVATE transport reply lost after possible commit'),
    event('ADD_EVIDENCE', 2, actor='wrong-actor'),
    event('ADD_EVIDENCE', 2, scope='FORMAL'),
])
def test_unknown_or_misbound_write_retains_original_key_and_reference_without_retry(response):
    transport = ScriptedRequests([
        ('fixture-a', 'POST', '/api/preparations/' + PREP + '/commands', response)])
    ref = reference()
    with pytest.raises(PreparationCommandUnknown) as error:
        workspace(transport).enterprise.add_evidence(ref, 'recover-this-key', slot='need_summary',
            text='SYNTHETIC source', source_label='SYNTHETIC v1')
    assert error.value.request_key == 'recover-this-key'
    assert ref == reference()
    assert len(transport.calls) == 1
    assert 'PRIVATE' not in str(error.value) and 'SYNTHETIC source' not in str(error.value)


def test_changed_reopen_material_refuses_without_repair_or_command():
    current = view()
    expected = workspace(ScriptedRequests([
        ('fixture-a', 'GET', '/api/preparations/' + PREP, current)])).enterprise.checkpoint(
            reference(5, 'LOCAL_CONFIRMED'))
    changed = deepcopy(current)
    changed['current_materials'][0]['source_sha256'] = 'd' * 64
    transport = ScriptedRequests([('fixture-a', 'GET', '/api/preparations/' + PREP, changed)])
    with pytest.raises(CandidateRefused, match='persistent preparation changed'):
        workspace(transport).enterprise.verify_reopened(expected)
    assert len(transport.calls) == 1 and transport.calls[0][1] == 'GET'


class RecordingTransaction:
    """Recording SQL port with ONE outer commit/rollback; no connection created."""
    autocommit = False

    def __init__(self, fail=False):
        self.fail = fail
        self.pending, self.committed = [], []
        self.commits = self.rollbacks = 0
        self.last = None

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        if kind:
            self.rollbacks += 1
            self.pending.clear()
        else:
            self.commits += 1
            self.committed.extend(self.pending)
            self.pending.clear()

    def execute(self, query, params=()):
        self.last = (query, params)
        if self.fail and query.startswith('INSERT INTO preparation_catalog'):
            raise ValueError('CONTROLLED preparation seed failure')
        self.pending.append(self.last)
        return self

    def fetchone(self):
        query, params = self.last
        if query.startswith('SELECT to_regclass'):
            return {'t': 'CONTROLLED_TABLE_EXISTS'}
        if query.startswith('SELECT * FROM principals'):
            name = params[0]
            return dict(park_id='park-b' if name == 'fixture-c' else 'park-a',
                        org_id='org-' + name[-1])
        raise AssertionError('Unexpected actual seed query')


@pytest.mark.parametrize('fail', [False, True])
def test_original_enterprise_and_preparation_seed_share_one_transaction(fail):
    connection = RecordingTransaction(fail)
    if fail:
        with pytest.raises(ValueError, match='CONTROLLED preparation seed'):
            with connection:
                seed_preparation_transaction(connection, identities())
        assert connection.rollbacks == 1 and not connection.committed
    else:
        with connection:
            seed_preparation_transaction(connection, identities())
        assert connection.commits == 1 and connection.rollbacks == 0
        queries = [row[0] for row in connection.committed]
        assert sum(x.startswith('INSERT INTO principals') for x in queries) == 6
        assert sum(x.startswith('INSERT INTO preparation_catalog') for x in queries) == 3
    assert not connection.pending


def test_material_is_cloned_and_unissued_native_owner_remains_refused():
    values = identities().mapping()
    frozen = PreparationIdentities.from_mapping(values)
    values['fixture-a'] = 'changed'
    assert frozen.mapping()['fixture-a'] != 'changed'
    assert isinstance(PreparationDatabaseOperations(), NativeDatabaseOperations)
    with patch('parkweave.installed_fixture_receipt._connect',
               side_effect=AssertionError('NO_DATABASE_CONNECTION')):
        with pytest.raises(CandidateRefused, match='exact live native owner'):
            PreparationDatabaseOperations().seed(object(), frozen)


def test_session_adapter_preserves_cluster_capability_and_requires_persisted_reviewers():
    lease, inputs, credential = object(), object(), object()
    security = Mock()
    security.load_existing_credentials.return_value = credential
    provider = Mock()
    provider.load_existing.return_value = identities()
    adapted = PreparationSecurity(security, provider)
    assert adapted.load_existing_credentials(lease) is credential
    adapted.verify_database_binding(lease, inputs)
    provider.load_existing.assert_called_once_with(lease)
    provider.create_exclusive.assert_not_called()
    provider.publish_binding_exclusive.assert_not_called()
    provider.verify_binding.assert_called_once_with(lease, inputs, adapted.identities(lease))
    provider.verify_binding.side_effect = CandidateRefused('missing protected reviewer binding')
    with pytest.raises(CandidateRefused, match='missing protected reviewer'):
        adapted.verify_database_binding(lease, inputs)


def test_composition_is_pure_and_real_owner_gate_calls_no_ports():
    directories, security, prerequisites, sessions, transport = [Mock() for _ in range(5)]
    candidate = compose_local_preparation(directories, security, prerequisites, sessions, transport,
        initdb_sha256='a' * 64, initdb_size=1, postgres_sha256='b' * 64, postgres_size=1,
        python_sha256='c' * 64, python_size=1, api_port=58000, challenge='d' * 32)
    assert candidate.native_acceptance is False
    assert candidate.processes.cluster.prerequisites is prerequisites
    for port in (directories, security, prerequisites, sessions, transport):
        assert port.mock_calls == []
    with pytest.raises(lifecycle.BoundaryError) as error:
        candidate.create('/NOT_ACCESSED', lambda _: pytest.fail('NO_BUSINESS_CALLBACK'))
    assert error.value.parkweave_lifecycle_reason == 'OWNER_MUTATION_PAUSED'
    for port in (directories, security, prerequisites, sessions, transport):
        assert port.mock_calls == []


def test_business_failure_uses_original_controller_unknown_and_reverse_cleanup():
    installation = FakeInstallation().ready()
    failure = PreparationCommandUnknown('ADD_EVIDENCE', 'same-key', OSError('reply lost'))
    # Existing Controller REOPEN control seams only. NO owner gate bypass and no
    # actual readiness/native receipt is created; fixture handles stay in memory.
    with patch.object(lifecycle, 'require_setup_readiness', side_effect=AssertionError('NEW_FORBIDDEN')), \
            patch.object(application_readiness, 'require_application_ready'), \
            patch.object(application_readiness, 'check_before_running'), \
            patch.object(application_readiness, 'activate_application'):
        with pytest.raises(ControlFailure) as error:
            installation.controller().reopen('/CONTROLLED_MEMORY_ROOT',
                lambda application: (_ for _ in ()).throw(failure))
    assert error.value.surfaced is failure
    assert installation.state == 'UNKNOWN'
    assert [e for e in installation.events if e.startswith('stop_')] == ['stop_app', 'stop_cluster']
    assert installation.events[-1] == 'release'
    assert 'seed' not in installation.events and 'sessions' not in installation.events


def test_business_callback_expires_clients_even_when_it_raises():
    from .controller import Controller
    application, inputs, lease = object(), object(), Mock()
    lease.status.return_value = 'RUNNING'
    processes = SimpleNamespace(application=application, inputs=inputs, lease=lease, failed=False)
    provider = Mock()
    security = PreparationSecurity(Mock(), provider)
    security._remember(lease, identities())
    transport = ScriptedRequests([('fixture-a', 'POST', '/api/runs', {'run_id': RUN})])
    controller = Controller(Mock(), security, processes, database=PreparationDatabaseOperations())
    invocation = LocalPreparationInvocation(controller, processes, security, transport)
    kept = []

    def use(current):
        kept.append(current.enterprise)
        assert current.enterprise.submit_case('SYNTHETIC local case', 'explicit-key') == RUN
        raise OSError('CONTROLLED business callback failure')

    # Callback adapter seam only; no Controller admission/readiness is claimed.
    with pytest.raises(OSError, match='CONTROLLED business callback'):
        invocation._use(use)(application)
    with pytest.raises(CandidateRefused, match='session ended'):
        kept[0].submit_case('SYNTHETIC stale callback', 'another-key')
    assert len(transport.calls) == 1


def test_isolated_security_still_refuses_native_database_subclass_before_provider():
    from .fixed_store_security import IsolatedFixedStoreSecurity, SecurityFailure
    isolated = object.__new__(IsolatedFixedStoreSecurity)
    isolated.failed, isolated.api = False, Mock()
    provider = Mock()
    adapted = PreparationSecurity(isolated, provider)
    with pytest.raises(SecurityFailure):
        adapted.require_runtime_support(PreparationDatabaseOperations(), object())
    assert isolated.api.mock_calls == []
    assert provider.mock_calls == []


class ControlledSocket:
    """In-memory socket port only; construction never calls the OS."""
    def __init__(self, response, events, on_recv=lambda: None):
        self.response, self.events, self.on_recv = response, events, on_recv
        self.sent = []
        self.address = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.events.append('closed')

    def settimeout(self, value):
        assert 0 < value <= .3

    def connect(self, address):
        self.address = address
        self.events.append('connected')

    def sendall(self, payload):
        assert 'verified' in self.events
        self.events.append('sent')
        self.sent.append(payload)

    def recv(self, limit):
        self.on_recv()
        self.events.append('received')
        part, self.response = self.response[:limit], self.response[limit:]
        return part


def http_response(body, extra=b'', status=b'200 OK'):
    import json
    raw = body if type(body) is bytes else json.dumps(body).encode('utf-8')
    return (b'HTTP/1.1 ' + status + b'\r\nContent-Type: application/json\r\nCache-Control: no-store\r\n'
            b'Content-Length: ' + str(len(raw)).encode() + b'\r\n' + extra + b'\r\n' + raw)


def controlled_application(events, fail_verify=False):
    from .application_readiness import RegisteredApplication
    from .processes import PrivateProcessAdapter
    adapter = object.__new__(PrivateProcessAdapter)
    adapter.require_endpoint_support = lambda token: events.append('supported')
    adapter.live_identity = lambda token: ('CONTROLLED_MEMORY_ONLY', id(token))

    def verify(token, connection):
        assert connection.sent == []
        if fail_verify:
            raise PermissionError('CONTROLLED endpoint owner mismatch')
        events.append('verified')

    adapter.verify_api_connection = verify
    return RegisteredApplication(adapter, object(), object(), 58000, 'd' * 32)


def test_owned_request_verifies_socket_before_bearer_and_sends_real_server_contract(monkeypatch):
    import json
    from parkweave.preparation import PreparationCommand
    from . import local_preparation_transport as transport
    events = []
    connection = ControlledSocket(http_response(event('ADD_EVIDENCE', 2)), events)
    created = Mock(return_value=connection)
    monkeypatch.setattr(transport.socket, 'socket', created)
    current = PreparationWorkspace(controlled_application(events), identities(),
                                   transport.OwnedPreparationRequest(), lambda: None)
    ref = current.enterprise.add_evidence(reference(), 'explicit-key', slot='need_summary',
                                         text='SYNTHETIC source', source_label='SYNTHETIC v1')
    assert ref.revision == 2 and created.call_count == 1
    assert events.index('verified') < events.index('sent')
    assert connection.address == ('127.0.0.1', 58000)
    assert len(connection.sent) == 1
    header, body = connection.sent[0].split(b'\r\n\r\n', 1)
    assert b'Idempotency-Key: explicit-key' in header
    data = json.loads(body)
    assert 'correction_slots' not in data
    assert PreparationCommand.model_validate(data).action == 'ADD_EVIDENCE'


def test_owned_request_refuses_wrong_endpoint_before_any_identity_is_sent(monkeypatch):
    from . import local_preparation_transport as transport
    events = []
    connection = ControlledSocket(http_response(event('ADD_EVIDENCE', 2)), events)
    created = Mock(return_value=connection)
    monkeypatch.setattr(transport.socket, 'socket', created)
    current = PreparationWorkspace(controlled_application(events, fail_verify=True), identities(),
                                   transport.OwnedPreparationRequest(), lambda: None)
    with pytest.raises(PreparationCommandUnknown):
        current.enterprise.add_evidence(reference(), 'same-key', slot='need_summary',
                                        text='SYNTHETIC source', source_label='SYNTHETIC v1')
    assert not connection.sent and created.call_count == 1


@pytest.mark.parametrize('response', [
    http_response({'ok': True}, b'Transfer-Encoding: chunked\r\n'),
    http_response({'ok': True}, b'Content-Length: 2\r\n'),
    http_response(b'{"same":1,"same":2}'),
    http_response({'ok': True}, status=b'302 Found'),
])
def test_owned_response_rejects_ambiguous_framing_json_and_redirect_without_retry(monkeypatch, response):
    from . import local_preparation_transport as transport
    events = []
    connection = ControlledSocket(response, events)
    created = Mock(return_value=connection)
    monkeypatch.setattr(transport.socket, 'socket', created)
    current = PreparationWorkspace(controlled_application(events), identities(),
                                   transport.OwnedPreparationRequest(), lambda: None)
    with pytest.raises(CandidateRefused):
        current.enterprise.read(reference())
    assert created.call_count == 1 and len(connection.sent) == 1


def test_owned_response_uses_one_absolute_deadline_without_retry(monkeypatch):
    from . import local_preparation_transport as transport
    events, clock = [], [0]
    monkeypatch.setattr(transport.time, 'monotonic', lambda: clock[0])
    connection = ControlledSocket(http_response(event('ADD_EVIDENCE', 2)), events,
                                  on_recv=lambda: clock.__setitem__(0, 31))
    created = Mock(return_value=connection)
    monkeypatch.setattr(transport.socket, 'socket', created)
    current = PreparationWorkspace(controlled_application(events), identities(),
                                   transport.OwnedPreparationRequest(), lambda: None)
    with pytest.raises(PreparationCommandUnknown) as error:
        current.enterprise.add_evidence(reference(), 'recover-key', slot='need_summary',
                                        text='SYNTHETIC source', source_label='SYNTHETIC v1')
    assert error.value.request_key == 'recover-key'
    assert created.call_count == 1 and len(connection.sent) == 1
