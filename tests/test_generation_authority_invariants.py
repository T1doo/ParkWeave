"""Independent FAULT_INJECTION gold: logical protocol, never OS protection."""
from dataclasses import replace
import hashlib
import json
from uuid import uuid4

import pytest

from parkweave.windows import lifecycle_generation_candidate as g


def uid():
    return str(uuid4())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def document(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


class Files:
    """Independent object identities; same bytes never imply the same object."""
    def __init__(self, data):
        self.root = g.FileSnapshot(g.FileIdentity(7, 1), data)
        self.generations, self.events = {}, []
        self.next_id = 1
        self.create_failure = False

    def read_root(self):
        self.events.append(('read_root',))
        return self.root

    def create_generation(self, name, data):
        self.events.append(('create', name, data))
        if self.create_failure:
            raise OSError('simulated precommit storage failure')
        if name in self.generations:
            raise FileExistsError(name)
        self.next_id += 1
        result = g.FileSnapshot(g.FileIdentity(7, self.next_id), data)
        self.generations[name] = result
        return result

    def read_generation(self, name):
        self.events.append(('read', name))
        return self.generations[name]


class SemanticAuthority:
    """Persistent model head, NOT protected storage or principal isolation.

    Valid proofs are issued here and checked independently; CAS is the only
    operation advancing the head. Every method is explicitly FAULT_INJECTION.
    """
    scope = g.Scope.FAULT_INJECTION

    def __init__(self, root):
        self.root, self.head, self.pending = root, None, None
        self.proofs, self.results, self.events = {}, {}, []
        self.read_fault = self.claim_fault = self.result_fault = None
        self.unknown_after_commit = self.unavailable = False
        self.last_nonce = None

    def read(self, root, nonce):
        self.events.append(('read', nonce))
        if self.unavailable:
            raise OSError('authority offline')
        result = g.AuthorityView(self.scope, self.root, nonce, self.head, self.pending)
        if self.read_fault:
            result = self.read_fault(result)
        self.last_nonce = nonce
        return result

    def authorize(self, root, event, run, nonce):
        self.events.append(('authorize', event, nonce))
        assert root == self.root and nonce == self.last_nonce
        value = g.Authorization(self.scope, root.root_id, event, sha(document({
            'epoch': run.epoch, 'session_id': run.session_id,
            'processes': [dict(role=p.role, pid=p.pid, created_ticks=p.created_ticks,
                               command_digest=p.command_digest, server_pid=p.server_pid,
                               server_created_ticks=p.server_created_ticks,
                               server_parent_pid=p.server_parent_pid,
                               server_parent_created_ticks=p.server_parent_created_ticks)
                          for p in run.processes]})), nonce, uid())
        self.proofs[value.proof_id] = value
        return self.claim_fault(value) if self.claim_fault else value

    def validate_authorization(self, claim):
        self.events.append(('validate', claim.proof_id))
        if self.proofs.get(claim.proof_id) != claim:
            raise ValueError('unissued or modified proof')

    def commit(self, pending):
        self.events.append(('commit', pending.key))
        self.validate_authorization(pending.authorization)
        assert pending.root == self.root
        if pending.expected_checkpoint != self.head:
            return g.CommitResult(self.scope, pending.key, pending.request_digest,
                                  g.Status.CONFLICT, self.head)
        assert pending.proposed_checkpoint.revision == (0 if self.head is None else self.head.revision) + 1
        self.pending = pending
        self.head = pending.proposed_checkpoint
        result = g.CommitResult(self.scope, pending.key, pending.request_digest,
                                g.Status.COMMITTED, self.head)
        self.results[pending.key] = result
        if self.unknown_after_commit:
            raise OSError('simulated committed response loss')
        self.pending = None
        return self.result_fault(result) if self.result_fault else result

    def resolve(self, root, key, request_digest, nonce):
        self.events.append(('resolve', key, request_digest, nonce))
        assert root == self.root
        result = self.results[key]
        assert result.request_digest == request_digest
        self.pending = None
        return replace(result, nonce=nonce)


def harness():
    root_id = uid()
    parts = [sha(label.encode()) for label in ('config', 'session', 'source', 'permissions')]
    data = document(dict(schema=1, root_id=root_id, config_digest=parts[0],
                         session_digest=parts[1], source_digest=parts[2], permissions_digest=parts[3]))
    files = Files(data)
    root = g.RootBinding(root_id, files.root.identity, sha(data), *parts)
    authority = SemanticAuthority(root)
    candidate = fresh(files, authority, root)
    return candidate, files, authority, root


def fresh(files, authority, root):
    return g.GenerationCandidate.for_protocol_tests(storage=files, authority=authority,
                                                    root=root, scope=g.Scope.FAULT_INJECTION)


def run():
    return g.RunIdentity(uid(), uid(), (
        g.ProcessIdentity('API', 101, 1001, sha(b'api command')),
        g.ProcessIdentity('WORKER', 202, 2002, sha(b'worker command'))))


def advance(candidate, event, identity):
    pending = candidate.prepare(event, identity, uid())
    return candidate.commit(pending)


def bound_run(candidate):
    value = run()
    advance(candidate, g.Event.ROOT_CREATED, value)
    value = replace(value, processes=(replace(value.processes[0], server_pid=303,
                                             server_created_ticks=3003,
                                             server_parent_pid=101,
                                             server_parent_created_ticks=1001), value.processes[1]))
    advance(candidate, g.Event.BIND_API, value)
    value = replace(value, processes=(value.processes[0], replace(value.processes[1], server_pid=202,
                                                               server_created_ticks=2002)))
    advance(candidate, g.Event.BIND_WORKER, value)
    return value


def creations(files):
    return [event for event in files.events if event[0] == 'create']


@pytest.mark.parametrize('operation', ['recover', 'prepare', 'commit', 'reconcile', 'process_actions'])
def test_unconfigured_candidate_has_no_protected_authority(operation):
    candidate = g.GenerationCandidate()
    arguments = {'prepare': (g.Event.ROOT_CREATED, run(), uid()), 'commit': (None,),
                 'reconcile': (uid(), sha(b'body'))}.get(operation, ())
    with pytest.raises(g.GenerationRefused, match='MISSING_PROTECTED_AUTHORITY'):
        getattr(candidate, operation)(*arguments)


@pytest.mark.parametrize('scope', [True, 'FAULT_INJECTION', None])
def test_self_declared_protection_cannot_enable_default_candidate(scope):
    _, files, authority, root = harness()
    with pytest.raises(g.GenerationRefused, match='EXPLICIT_TEST_SCOPE_REQUIRED'):
        g.GenerationCandidate.for_protocol_tests(storage=files, authority=authority, root=root, scope=scope)
    assert not creations(files)


@pytest.mark.parametrize('field', ['identity', 'root_digest', 'config_digest', 'session_digest', 'source_digest', 'permissions_digest'])
def test_root_binding_checks_exact_file_identity_and_all_digest_inputs(field):
    _, files, authority, root = harness()
    changed = g.FileIdentity(7, 999) if field == 'identity' else sha(b'changed')
    with pytest.raises(g.GenerationRefused, match='ROOT_IDENTITY_CHANGED'):
        fresh(files, authority, replace(root, **{field: changed}))
    assert not creations(files) and authority.head is None


@pytest.mark.parametrize('change', ['identity', 'bytes'])
def test_root_swap_after_prepare_prevents_authority_commit(change):
    candidate, files, authority, _ = harness()
    pending = candidate.prepare(g.Event.ROOT_CREATED, run(), uid())
    files.root = replace(files.root, **({'identity': g.FileIdentity(7, 88)} if change == 'identity'
                                       else {'data': files.root.data + b' '}))
    with pytest.raises(g.GenerationRefused, match='ROOT_IDENTITY_CHANGED'):
        candidate.commit(pending)
    assert authority.head is None and not any(e[0] == 'commit' for e in authority.events)


@pytest.mark.parametrize('fault', ['nonce', 'root', 'scope', 'offline'])
def test_fresh_authority_view_required_before_generation_create(fault):
    candidate, files, authority, root = harness()
    if fault == 'offline':
        authority.unavailable = True
    else:
        authority.read_fault = lambda view: replace(view, **{
            'nonce': {'nonce': 'replayed nonce'}, 'root': {'root': replace(root, source_digest=sha(b'old'))},
            'scope': {'scope': g.Scope.ISOLATED_PROTOCOL_TEST}}[fault])
    with pytest.raises(g.GenerationRefused, match='FRESH_AUTHORITY_REQUIRED|AUTHORITY_UNAVAILABLE'):
        candidate.prepare(g.Event.ROOT_CREATED, run(), uid())
    assert not creations(files) and authority.head is None


@pytest.mark.parametrize('field', ['bool', 'root_id', 'event', 'run_digest', 'nonce', 'proof_id'])
def test_exact_issued_process_authorization_required_before_storage_write(field):
    candidate, files, authority, _ = harness()
    values = {'root_id': uid(), 'event': g.Event.STOP_INTENT, 'run_digest': sha(b'wrong run'),
              'nonce': 'old nonce', 'proof_id': uid()}
    authority.claim_fault = lambda claim: True if field == 'bool' else replace(claim, **{field: values[field]})
    with pytest.raises(g.GenerationRefused, match='EXACT_PROCESS_AUTHORIZATION_REQUIRED'):
        candidate.prepare(g.Event.ROOT_CREATED, run(), uid())
    assert not creations(files) and authority.head is None


def test_create_before_commit_is_orphan_and_restart_never_selects_directory_prefix():
    candidate, files, authority, root = harness()
    pending = candidate.prepare(g.Event.ROOT_CREATED, run(), uid())
    assert len(creations(files)) == 1 and authority.head is None
    restarted = fresh(files, authority, root)
    assert restarted.recover() is None
    assert pending.proposed_checkpoint.reference.name in files.generations
    assert not any(e[0] == 'commit' for e in authority.events)


def test_precommit_storage_failure_does_not_advance_authority():
    candidate, files, authority, _ = harness()
    files.create_failure = True
    with pytest.raises(OSError):
        candidate.prepare(g.Event.ROOT_CREATED, run(), uid())
    assert authority.head is None and not any(e[0] == 'commit' for e in authority.events)


def test_expected_head_cas_admits_only_one_competing_generation():
    first, files, authority, root = harness()
    second = fresh(files, authority, root)
    a = first.prepare(g.Event.ROOT_CREATED, run(), uid())
    b = second.prepare(g.Event.ROOT_CREATED, run(), uid())
    assert first.commit(a) == a.proposed_checkpoint
    assert second.commit(b) is None
    assert authority.head == a.proposed_checkpoint
    assert fresh(files, authority, root).recover() == a.proposed_checkpoint
    assert len(creations(files)) == 2  # Losing orphan is retained, never a fallback.


def test_lost_commit_reply_reconciles_exact_request_after_restart_without_republication():
    candidate, files, authority, root = harness()
    pending = candidate.prepare(g.Event.ROOT_CREATED, run(), uid())
    authority.unknown_after_commit = True
    with pytest.raises(g.GenerationRefused, match='COMMIT_OUTCOME_UNKNOWN'):
        candidate.commit(pending)
    before = len(creations(files))
    with pytest.raises(g.GenerationRefused, match='COMMIT_OUTCOME_UNKNOWN'):
        candidate.prepare(g.Event.ROOT_CREATED, run(), uid())
    restarted = fresh(files, authority, root)
    with pytest.raises(g.GenerationRefused, match='COMMIT_OUTCOME_UNKNOWN'):
        restarted.recover()
    for key, digest in ((uid(), pending.request_digest), (pending.key, sha(b'changed body'))):
        with pytest.raises(g.GenerationRefused, match='EXACT_UNCERTAIN_REQUEST_REQUIRED'):
            restarted.reconcile(key, digest)
    assert not any(e[0] == 'resolve' for e in authority.events)
    assert restarted.reconcile(pending.key, pending.request_digest) == authority.head
    assert restarted.recover() == authority.head and len(creations(files)) == before
    nonces = [e[1] for e in authority.events if e[0] == 'read']
    resolution_nonce = next(e[3] for e in authority.events if e[0] == 'resolve')
    assert len(nonces) == len(set(nonces)) and resolution_nonce not in nonces


@pytest.mark.parametrize('field', ['key', 'request_digest', 'checkpoint', 'scope'])
def test_forged_commit_reply_stays_uncertain_and_blocks_new_publication(field):
    candidate, files, authority, _ = harness()
    pending = candidate.prepare(g.Event.ROOT_CREATED, run(), uid())
    values = {'key': uid(), 'request_digest': sha(b'forged'), 'checkpoint': None,
              'scope': g.Scope.ISOLATED_PROTOCOL_TEST}
    authority.result_fault = lambda result: replace(result, **{field: values[field]})
    with pytest.raises(g.GenerationRefused, match='EXACT_REQUEST_RESULT_REQUIRED|COMMIT_BINDING_MISMATCH'):
        candidate.commit(pending)
    with pytest.raises(g.GenerationRefused, match='COMMIT_OUTCOME_UNKNOWN'):
        candidate.prepare(g.Event.ROOT_CREATED, run(), uid())
    assert len(creations(files)) == 1


@pytest.mark.parametrize('tamper', ['missing', 'identity', 'bytes', 'checkpoint_event'])
def test_authoritative_anchor_never_falls_back_to_an_older_valid_generation(tamper):
    candidate, files, authority, root = harness()
    identity = bound_run(candidate)
    point = authority.head
    ref = point.reference
    if tamper == 'missing':
        del files.generations[ref.name]
    elif tamper == 'identity':
        files.generations[ref.name] = replace(files.generations[ref.name], identity=g.FileIdentity(7, 999))
    elif tamper == 'bytes':
        files.generations[ref.name] = replace(files.generations[ref.name], data=files.generations[ref.name].data + b' ')
    else:
        authority.head = replace(point, event=g.Event.STOP_INTENT)
    restarted = fresh(files, authority, root)
    before = len(creations(files))
    with pytest.raises(g.GenerationRefused, match='ANCHORED_GENERATION_UNAVAILABLE|GENERATION_IDENTITY_CHANGED|CHECKPOINT_BINDING_MISMATCH'):
        restarted.recover()
    assert len(creations(files)) == before and len(files.generations) >= 2


def test_live_candidate_rejects_authority_rollback_even_with_old_valid_bytes():
    candidate, _, authority, _ = harness()
    value = run()
    old = advance(candidate, g.Event.ROOT_CREATED, value)
    value = replace(value, processes=(replace(value.processes[0], server_pid=101, server_created_ticks=1001), value.processes[1]))
    advance(candidate, g.Event.BIND_API, value)
    authority.head = old
    with pytest.raises(g.GenerationRefused, match='AUTHORITY_ROLLBACK'):
        candidate.recover()


@pytest.mark.parametrize('field', ['epoch', 'session_id', 'pid', 'created_ticks', 'command_digest', 'server_created_ticks'])
def test_stop_requires_exact_current_fake_session_and_process_identity(field):
    candidate, files, authority, _ = harness()
    identity = bound_run(candidate)
    if field in ('epoch', 'session_id'):
        changed = replace(identity, **{field: uid()})
    else:
        values = {'pid': 909, 'created_ticks': 9090, 'command_digest': sha(b'other command'),
                  'server_created_ticks': 9191}
        changed = replace(identity, processes=(replace(identity.processes[0], **{field: values[field]}), identity.processes[1]))
    before, head = len(creations(files)), authority.head
    with pytest.raises(g.GenerationRefused):
        candidate.prepare(g.Event.STOP_INTENT, changed, uid())
    assert len(creations(files)) == before and authority.head == head


def test_stop_appends_tombstones_and_new_epoch_does_not_overwrite_or_kill():
    candidate, files, authority, root = harness()
    identity = bound_run(candidate)
    prior = dict(files.generations)
    stop = advance(candidate, g.Event.STOP_INTENT, identity)
    confirmed = advance(candidate, g.Event.STOP_CONFIRMED, identity)
    assert stop.revision == 4 and confirmed.revision == 5
    assert prior.items() <= files.generations.items()
    with pytest.raises(g.GenerationRefused, match='PROCESS_ACTIONS_NOT_IMPLEMENTED'):
        candidate.process_actions(identity)
    with pytest.raises(g.GenerationRefused, match='OLD_EPOCH_REPLAY'):
        candidate.prepare(g.Event.ROOT_CREATED, replace(run(), epoch=identity.epoch), uid())
    advance(candidate, g.Event.ROOT_CREATED, run())
    assert authority.head.revision == 6 and fresh(files, authority, root).recover() == authority.head


def test_real_synthetic_uuid_create_new_store_is_only_a_protocol_fixture(tmp_path):
    root_id = uid()
    data = g.root_document(root_id, *[sha(x) for x in (b'config', b'session', b'source', b'permissions')])
    store = g.SyntheticFileStore(tmp_path / uid())
    root_file = store.create_root(data)
    root = g.RootBinding(root_id, root_file.identity, sha(data),
                         *[sha(x) for x in (b'config', b'session', b'source', b'permissions')])
    authority = SemanticAuthority(root)
    candidate = fresh(store, authority, root)
    value = advance(candidate, g.Event.ROOT_CREATED, run())
    assert fresh(store, authority, root).recover() == value
    assert store.read_generation(value.reference.name).identity == value.reference.identity
    with pytest.raises(FileExistsError):
        store.create_root(data)
    assert authority.scope is g.Scope.FAULT_INJECTION  # Explicitly not OS protection.


@pytest.mark.parametrize('attestation', [True, False])
def test_boolean_validator_return_cannot_attest_exact_authorization(attestation):
    candidate, files, authority, _ = harness()
    authority.validate_authorization = lambda claim: attestation
    with pytest.raises(g.GenerationRefused, match='EXACT_PROCESS_AUTHORIZATION_REQUIRED'):
        candidate.prepare(g.Event.ROOT_CREATED, run(), uid())
    assert not creations(files) and authority.head is None


def test_replayed_authority_nonce_after_successful_read_is_refused():
    candidate, files, authority, _ = harness()
    candidate.recover()
    prior_nonce = authority.last_nonce
    authority.read_fault = lambda view: replace(view, nonce=prior_nonce)
    with pytest.raises(g.GenerationRefused, match='FRESH_AUTHORITY_REQUIRED'):
        candidate.prepare(g.Event.ROOT_CREATED, run(), uid())
    assert not creations(files)


def test_equal_but_unissued_prepared_object_is_not_committed():
    candidate, _, authority, _ = harness()
    pending = candidate.prepare(g.Event.ROOT_CREATED, run(), uid())
    with pytest.raises(g.GenerationRefused, match='EXACT_PREPARED_REQUEST_REQUIRED'):
        candidate.commit(replace(pending))
    assert authority.head is None and not any(e[0] == 'commit' for e in authority.events)
    assert candidate.commit(pending) == pending.proposed_checkpoint


@pytest.mark.parametrize('fault', ['gap', 'fork', 'replayed_binding', 'wrong_root', 'noncanonical'])
def test_even_self_consistent_digest_and_name_cannot_hide_invalid_anchored_chain(fault):
    candidate, files, authority, root = harness()
    bound_run(candidate)
    point = authority.head
    original = files.generations[point.reference.name]
    body = json.loads(original.data)
    if fault == 'gap':
        body['sequence'] += 1
    elif fault == 'fork':
        body['previous'] = None
    elif fault == 'replayed_binding':
        body['event'] = 'BIND_API'
    elif fault == 'wrong_root':
        body['root_id'] = uid()
    data = document(body) + (b'\n' if fault == 'noncanonical' else b'')
    digest = sha(data)
    name = f"gen-{body['run']['epoch']}-{body['sequence']:020d}-{digest}.json"
    forged = g.FileSnapshot(g.FileIdentity(7, 999), data)
    files.generations[name] = forged
    authority.head = replace(point, reference=g.FileRef(name, forged.identity, digest),
                             event=g.Event(body['event']))
    before = len(creations(files))
    with pytest.raises(g.GenerationRefused, match='CHAIN_GAP|INVALID_TRANSITION|INVALID_GENERATION'):
        fresh(files, authority, root).recover()
    assert len(creations(files)) == before


def test_restarted_unknown_pending_cannot_claim_a_different_predecessor():
    candidate, files, authority, root = harness()
    identity = run()
    advance(candidate, g.Event.ROOT_CREATED, identity)
    identity = replace(identity, processes=(replace(identity.processes[0], server_pid=101,
                                                    server_created_ticks=1001), identity.processes[1]))
    pending = candidate.prepare(g.Event.BIND_API, identity, uid())
    authority.pending = replace(pending, expected_checkpoint=None)
    with pytest.raises(g.GenerationRefused, match='PENDING_PREDECESSOR_MISMATCH'):
        fresh(files, authority, root).recover()
    assert authority.head.revision == 1
    assert not any(e[0] == 'resolve' for e in authority.events)
