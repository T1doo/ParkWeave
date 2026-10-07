"""Isolated protocol fixtures; no Windows/protected-authority evidence."""
from dataclasses import replace
from uuid import uuid4

import pytest

from parkweave.windows import lifecycle_generation_candidate as g


class FaultAuthority:
    scope = g.Scope.FAULT_INJECTION

    def __init__(self):
        self.head = self.pending = None
        self.proofs = set()
        self.results = {}
        self.unknown = False
        self.calls = []

    def read(self, root, nonce):
        self.calls.append('read')
        return g.AuthorityView(self.scope, root, nonce, self.head, self.pending)

    def authorize(self, root, event, run, nonce):
        claim = g.Authorization(self.scope, root.root_id, event, g.run_digest(run), nonce, str(uuid4()))
        self.proofs.add(claim)
        return claim

    def validate_authorization(self, claim):
        if claim not in self.proofs:
            raise ValueError('fake proof unknown')

    def commit(self, pending):
        self.calls.append('commit')
        if pending.expected_checkpoint != self.head:
            return g.CommitResult(self.scope, pending.key, pending.request_digest, g.Status.CONFLICT, self.head)
        self.pending = pending
        if self.unknown:
            return g.CommitResult(self.scope, pending.key, pending.request_digest, g.Status.UNKNOWN, None)
        self.head = pending.proposed_checkpoint
        self.results[(pending.key, pending.request_digest)] = self.head
        self.pending = None
        return g.CommitResult(self.scope, pending.key, pending.request_digest, g.Status.COMMITTED, self.head)

    def resolve(self, root, key, request_digest, nonce):
        self.calls.append('resolve')
        point = self.results.get((key, request_digest))
        status = g.Status.COMMITTED if point else g.Status.UNKNOWN
        return g.CommitResult(self.scope, key, request_digest, status, point, nonce)


def fixture(tmp_path):
    store = g.SyntheticFileStore(tmp_path / str(uuid4()))
    root_id = str(uuid4())
    sha = 'a' * 64
    data = g.root_document(root_id, sha, sha, sha, sha)
    snap = store.create_root(data)
    root = g.RootBinding(root_id, snap.identity, g.digest(data), sha, sha, sha, sha)
    authority = FaultAuthority()
    candidate = g.GenerationCandidate.for_protocol_tests(storage=store, authority=authority, root=root, scope=authority.scope)
    run = g.RunIdentity(str(uuid4()), str(uuid4()), (
        g.ProcessIdentity('API', 101, 1001, sha), g.ProcessIdentity('WORKER', 102, 1002, sha)))
    return candidate, store, authority, root, run


def write(candidate, event, run):
    pending = candidate.prepare(event, run, str(uuid4()))
    return candidate.commit(pending)


def test_default_missing_authority_touches_no_storage():
    candidate = g.GenerationCandidate()
    for action in (candidate.recover, lambda: candidate.prepare(None, None, None), lambda: candidate.process_actions('STOP')):
        with pytest.raises(g.GenerationRefused, match='MISSING_PROTECTED_AUTHORITY'):
            action()


def test_synthetic_journey_preserves_root_and_generations(tmp_path):
    candidate, store, authority, root, run = fixture(tmp_path)
    original = store.read_root()
    snapshots = []
    for event in g.Event:
        if event is g.Event.BIND_API:
            run = replace(run, processes=(replace(run.processes[0], server_pid=101, server_created_ticks=1001), run.processes[1]))
        elif event is g.Event.BIND_WORKER:
            run = replace(run, processes=(run.processes[0], replace(run.processes[1], server_pid=202, server_created_ticks=2002,
                                                                 server_parent_pid=102, server_parent_created_ticks=1002)))
        point = write(candidate, event, run)
        snapshots.append((point.reference.name, store.read_generation(point.reference.name)))
        assert candidate.recover() == point
    assert store.read_root() == original
    assert all(store.read_generation(name) == snapshot for name, snapshot in snapshots)
    assert authority.head.revision == 5
    with pytest.raises(g.GenerationRefused, match='PROCESS_ACTIONS_NOT_IMPLEMENTED'):
        candidate.process_actions('STOP', run)


def test_unknown_blocks_new_nonce_and_restart_requires_exact_reconcile(tmp_path):
    candidate, store, authority, root, run = fixture(tmp_path)
    pending = candidate.prepare(g.Event.ROOT_CREATED, run, str(uuid4()))
    authority.unknown = True
    with pytest.raises(g.GenerationRefused, match='COMMIT_OUTCOME_UNKNOWN'):
        candidate.commit(pending)
    calls = list(authority.calls)
    with pytest.raises(g.GenerationRefused, match='COMMIT_OUTCOME_UNKNOWN'):
        candidate.prepare(g.Event.ROOT_CREATED, run, str(uuid4()))
    assert authority.calls == calls
    restarted = g.GenerationCandidate.for_protocol_tests(storage=store, authority=authority, root=root, scope=authority.scope)
    with pytest.raises(g.GenerationRefused, match='COMMIT_OUTCOME_UNKNOWN'):
        restarted.recover()
    with pytest.raises(g.GenerationRefused, match='EXACT_UNCERTAIN_REQUEST_REQUIRED'):
        restarted.reconcile(str(uuid4()), pending.request_digest)
    authority.head = pending.proposed_checkpoint
    authority.results[(pending.key, pending.request_digest)] = authority.head
    authority.pending = None
    assert restarted.reconcile(pending.key, pending.request_digest) == authority.head


def test_missing_authoritative_generation_never_uses_old_prefix(tmp_path):
    candidate, store, authority, root, run = fixture(tmp_path)
    point = write(candidate, g.Event.ROOT_CREATED, run)
    bound = replace(run, processes=(replace(run.processes[0], server_pid=101, server_created_ticks=1001), run.processes[1]))
    latest = write(candidate, g.Event.BIND_API, bound)
    # Deliberately corrupt synthetic fixture only; candidate itself never deletes.
    (store.directory / latest.reference.name).unlink()
    assert (store.directory / point.reference.name).exists()
    with pytest.raises(g.GenerationRefused, match='ANCHORED_GENERATION_UNAVAILABLE'):
        candidate.recover()


def test_current_inode_content_tamper_refused(tmp_path):
    candidate, store, authority, root, run = fixture(tmp_path)
    point = write(candidate, g.Event.ROOT_CREATED, run)
    path = store.directory / point.reference.name
    data = path.read_bytes()
    path.write_bytes(data.replace(b'ROOT_CREATED', b'ROOT_CREA TED'))
    with pytest.raises(g.GenerationRefused, match='GENERATION_IDENTITY_CHANGED'):
        candidate.recover()


def test_boolean_authority_attestation_refused_before_generation(tmp_path):
    candidate, store, authority, root, run = fixture(tmp_path)
    authority.validate_authorization = lambda claim: True
    with pytest.raises(g.GenerationRefused, match='EXACT_PROCESS_AUTHORIZATION_REQUIRED'):
        candidate.prepare(g.Event.ROOT_CREATED, run, str(uuid4()))
    assert list(store.directory.iterdir()) == [store.directory / 'identity-root.json']
