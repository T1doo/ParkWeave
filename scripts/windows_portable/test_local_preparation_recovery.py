"""Read-only recovery contracts on controlled ports; no actual SQL/network."""
from copy import deepcopy
from unittest.mock import Mock
from uuid import UUID

import pytest

from parkweave import preparation
from parkweave.store import Store
from .application_readiness import ExistingActorProbe
from .local_preparation import PreparationCommandUnknown, PreparationWorkspace
from .local_preparation_transport import OwnedPreparationRequest
from .test_local_preparation import (
    CASE, PREP, RUN, SCOPE, ControlledSocket, ScriptedRequests, controlled_application,
    event, http_response, identities, reference, workspace,
)

KEY = str(UUID(int=4))
PATH = '/api/preparations/' + PREP
OWNER = dict(id='fixture-a', park_id='park-a', org_id='org-a', role='enterprise_operator')


def unknown_write(current, key=KEY):
    with pytest.raises(PreparationCommandUnknown) as error:
        current.enterprise.add_evidence(reference(), key, slot='need_summary',
            text='SYNTHETIC immutable original source', source_label='SYNTHETIC v1')
    return error.value


def lost_workspace(key=KEY):
    transport = ScriptedRequests([
        ('fixture-a', 'POST', PATH + '/commands', OSError('CONTROLLED lost response'))])
    current = workspace(transport)
    pending = unknown_write(current, key)
    return current, pending, transport


def committed(pending):
    intent = pending.recovery_intent
    receipt = event('ADD_EVIDENCE', 2, snapshot_sha256='d' * 64)
    result = dict(preparation_id=PREP, status='COMMITTED', event=receipt,
                  current_revision=2, historical_only=True, automatically_replayed=False,
                  recovery_contract='parkweave-evidence-recovery/1',
                  request_binding=dict(request_key=intent.request_key,
                      fingerprint=intent.fingerprint, actor=dict(OWNER)),
                  **{k: v for k, v in SCOPE.items() if k != 'scope'})
    current = dict(SCOPE, preparation=dict(id=PREP, run_id=RUN, case_id=CASE, revision=2,
                    state='IN_PREPARATION', owner_id='fixture-a', park_id='park-a',
                    org_id='org-a', namespace='SYNTHETIC'),
                   snapshot_sha256='d' * 64,
                   history=[dict(revision=2, action='ADD_EVIDENCE', payload=deepcopy(receipt))])
    return result, current


def test_owned_recovery_sends_only_two_gets_after_one_unknown_post(monkeypatch):
    from . import local_preparation_transport as transport
    events = []
    app = controlled_application(events)

    def lose_reply():
        raise OSError('CONTROLLED reply lost after possible commit')

    lost = ControlledSocket(b'', events, on_recv=lose_reply)
    connections = [lost]
    factory = Mock(side_effect=lambda *args: connections.pop(0))
    monkeypatch.setattr(transport.socket, 'socket', factory)
    current = PreparationWorkspace(app, identities(), OwnedPreparationRequest(), lambda: None)
    pending = unknown_write(current)
    response, view = committed(pending)
    first = ControlledSocket(http_response(response), events)
    second = ControlledSocket(http_response(view), events)
    connections.extend([first, second])
    recovered = current.enterprise.recover_unknown(pending)
    assert recovered.status == 'COMMITTED'
    assert recovered.reference == reference(2)
    assert pending.recovery_intent.previous == reference()
    assert pending.request_key == KEY
    assert [s.sent[0].split(b' ', 1)[0] for s in [lost, first, second]] == [b'POST', b'GET', b'GET']
    assert b'Idempotency-Key: ' + KEY.encode() in first.sent[0].split(b'\r\n\r\n', 1)[0]
    assert first.sent[0].split(b'\r\n\r\n', 1)[1] == b''
    assert events.count('verified') == 3 and factory.call_count == 3


@pytest.mark.parametrize('mismatch', [
    'not_observed', 'fingerprint', 'request_key', 'actor_scope', 'case', 'version', 'old_protocol',
])
def test_absent_or_mismatched_receipt_never_advances_or_retries(mismatch):
    current, pending, transport = lost_workspace()
    response, _ = committed(pending)
    if mismatch == 'not_observed':
        response.update(status='NOT_OBSERVED', event=None)
        response['request_binding']['fingerprint'] = None
    elif mismatch == 'fingerprint':
        response['request_binding']['fingerprint'] = 'e' * 64
    elif mismatch == 'request_key':
        response['request_binding']['request_key'] = str(UUID(int=8))
    elif mismatch == 'actor_scope':
        response['request_binding']['actor']['org_id'] = 'org-b'
    elif mismatch == 'case':
        response['event']['case_id'] = str(UUID(int=9))
    elif mismatch == 'version':
        response['current_revision'] = 3
    else:
        response.pop('request_binding')
        response.pop('recovery_contract')
    transport.steps.append(('fixture-a', 'GET', PATH + '/command-recovery', response))
    observed = current.enterprise.recover_unknown(pending)
    assert observed.status == 'UNKNOWN' and observed.reference is None
    assert pending.recovery_intent.previous == reference()
    assert [row[1] for row in transport.calls] == ['POST', 'GET']
    assert transport.calls[-1][-1] == KEY


@pytest.mark.parametrize('changed', ['actor', 'credential', 'application'])
def test_changed_identity_or_owned_invocation_does_not_even_issue_recovery_get(changed):
    current, pending, transport = lost_workspace()
    if changed == 'actor':
        current.enterprise.actor = ExistingActorProbe(current.enterprise.actor.bearer,
            ('fixture-a', 'park-a', 'org-b', 'enterprise_operator'))
    elif changed == 'credential':
        current.enterprise.actor = ExistingActorProbe('PUBLIC_DIFFERENT_TEST_LABEL',
                                                      current.enterprise.actor.actor)
    else:
        current.application = object()
    result = current.enterprise.recover_unknown(pending)
    assert result.status == 'UNKNOWN' and result.reference is None
    assert len(transport.calls) == 1


def test_recovery_read_error_keeps_original_unknown():
    current, pending, transport = lost_workspace()
    original = pending.primary
    transport.steps.append(('fixture-a', 'GET', PATH + '/command-recovery', OSError('CONTROLLED read failure')))
    result = current.enterprise.recover_unknown(pending)
    assert result.status == 'UNKNOWN' and result.reference is None
    assert pending.primary is original and pending.request_key == KEY
    assert len(transport.calls) == 2


def test_missing_exact_current_event_does_not_restore_reference():
    current, pending, transport = lost_workspace()
    response, view = committed(pending)
    view['history'] = []
    transport.steps.extend([
        ('fixture-a', 'GET', PATH + '/command-recovery', response),
        ('fixture-a', 'GET', PATH, view)])
    result = current.enterprise.recover_unknown(pending)
    assert result.status == 'UNKNOWN' and result.reference is None
    assert [row[1] for row in transport.calls] == ['POST', 'GET', 'GET']


def test_not_observed_then_late_commit_requires_separate_explicit_reads_never_resend():
    current, pending, transport = lost_workspace()
    response, view = committed(pending)
    absent = dict(response, status='NOT_OBSERVED', event=None)
    transport.steps.append(('fixture-a', 'GET', PATH + '/command-recovery', absent))
    assert current.enterprise.recover_unknown(pending).status == 'UNKNOWN'
    assert len(transport.calls) == 2  # No polling or extra command.
    transport.steps.extend([
        ('fixture-a', 'GET', PATH + '/command-recovery', response),
        ('fixture-a', 'GET', PATH, view)])
    assert current.enterprise.recover_unknown(pending).status == 'COMMITTED'
    assert [row[1] for row in transport.calls].count('POST') == 1


def test_unsupported_actions_and_non_uuid_keys_have_no_query_or_retry():
    current = workspace(ScriptedRequests([]))
    for action in ['CASE_SUBMIT', 'CREATE', 'REVIEW', 'CONFIRM']:
        pending = PreparationCommandUnknown(action, KEY, OSError('CONTROLLED'))
        assert current.enterprise.recover_unknown(pending).status == 'UNKNOWN'
    assert not current.transport.calls
    current, pending, transport = lost_workspace('valid-write-key-without-query-contract')
    assert current.enterprise.recover_unknown(pending).status == 'UNKNOWN'
    assert len(transport.calls) == 1


class RecoveryReadConnection:
    """Execute the actual server auth/scope/query code against recording rows."""
    def __init__(self, record):
        self.record, self.rows, self.queries = record, [], []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, params=()):
        assert query.startswith(('SET ', 'SELECT ')), 'No DML/DDL permitted'
        assert 'FOR SHARE' not in query and 'FOR UPDATE' not in query
        self.queries.append((query, params))
        if query.startswith('SELECT * FROM principals'):
            self.rows = [dict(OWNER, active=True)]
        elif query.startswith('SELECT 1 FROM'):
            self.rows = [{'allowed': 1}]
        elif query.startswith('SELECT * FROM preparations'):
            assert params == (UUID(PREP), 'park-a', 'org-a')
            self.rows = [dict(id=UUID(PREP), owner_id='fixture-a', reviewer_id='prep-specialist-fixture-a',
                             park_id='park-a', org_id='org-a', revision=2)]
        elif 'FROM preparation_events' in query:
            assert 'fingerprint' in query and params == ('fixture-a', KEY)
            self.rows = [self.record] if self.record is not None else []
        else:
            self.rows = []
        return self

    def fetchone(self):
        return self.rows[0] if self.rows else None


@pytest.mark.parametrize('exists', [False, True])
def test_actual_server_recovery_returns_stored_fingerprint_under_read_only_scope(monkeypatch, exists):
    _, pending, _ = lost_workspace()
    response, _ = committed(pending)
    record = dict(preparation_id=UUID(PREP), action='ADD_EVIDENCE',
                  payload=response['event'], fingerprint=pending.recovery_intent.fingerprint)
    connection = RecoveryReadConnection(record if exists else None)
    store = Store('CONTROLLED_NO_CONNECTION')
    monkeypatch.setattr(store, 'connect', lambda: connection)
    result = preparation.recover_evidence_command(store, 'PUBLIC_SYNTHETIC_TEST_fixture-a', UUID(PREP), KEY)
    assert connection.queries[0][0] == 'SET TRANSACTION READ ONLY'
    assert result['status'] == ('COMMITTED' if exists else 'NOT_OBSERVED')
    assert result['request_binding']['fingerprint'] == (record['fingerprint'] if exists else None)
    assert result['request_binding']['actor'] == OWNER
    assert result['request_binding']['request_key'] == KEY
    assert 'request_key' not in result and 'text' not in result


@pytest.mark.parametrize('changed', ['application', 'credential'])
@pytest.mark.parametrize('after', ['metadata', 'current_view'])
def test_binding_change_after_recovery_response_cannot_return_committed(changed, after):
    current, pending, transport = lost_workspace()
    response, view = committed(pending)
    transport.steps.extend([
        ('fixture-a', 'GET', PATH + '/command-recovery', response),
        ('fixture-a', 'GET', PATH, view)])
    request = transport.request

    def change_after_metadata(*args):
        result = request(*args)
        target = PATH + '/command-recovery' if after == 'metadata' else PATH
        if args[3] == target:
            if changed == 'application':
                current.application = object()
            else:
                current.enterprise.actor = ExistingActorProbe('PUBLIC_ROTATED_TEST_LABEL',
                                                              current.enterprise.actor.actor)
        return result

    transport.request = change_after_metadata
    observed = current.enterprise.recover_unknown(pending)
    assert observed.status == 'UNKNOWN' and observed.reference is None
    assert pending.recovery_intent.previous == reference()
    assert [row[1] for row in transport.calls] == (['POST', 'GET'] if after == 'metadata'
                                                  else ['POST', 'GET', 'GET'])
