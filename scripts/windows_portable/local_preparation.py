"""One synthetic local preparation chain, composed only from explicit ports.

No entry calls this candidate. No socket, SQL connection, process, secret
generator or native admission is implemented here. Individual role actions are
explicit; there is no automatic review/confirmation or write retry.
"""
from dataclasses import dataclass, field
import json
import re
import time
from typing import Protocol
from uuid import UUID

from parkweave.domain import Intake
from parkweave.preparation import CreatePreparation, PreparationCommand

from .application_readiness import ExistingActorProbe
from .cluster_processes import FixedClusterProcesses, ClusterPrerequisites
from .controller import CandidateRefused, Controller
from .instance_processes import InstanceProcesses
from .local_preparation_identity import (
    PreparationDatabaseOperations, PreparationIdentities, PreparationSecurity,
)

SCOPE = dict(scope='SYNTHETIC_LOCAL_PREPARATION_ONLY', qualification='NOT_EVALUATED',
             external_acceptance='NOT_SUBMITTED', offline_fulfillment='NO_EVIDENCE')


class PreparationRequestPort(Protocol):
    """Explicit owned transport contract; native endpoint admission is separate.

    Must bound the entire request/response by deadline and a 1 MB JSON limit,
    use only this application's owned IPv4 loopback API, and verify the actual
    connected endpoint against its original process capability BEFORE sending
    the bearer. No redirects, proxies, automatic retries, fallback endpoint or
    response-as-native-authority. Server routes retain their real auth/SQL gates.
    """
    def request(self, application, actor: ExistingActorProbe, method, path, body,
                request_key, deadline): ...


class PreparationCommandUnknown(RuntimeError):
    def __init__(self, action, request_key, primary):
        self.action, self.request_key, self.primary = action, request_key, primary
        # Never include material, bearer, DSN or transport exception text.
        super().__init__('LOCAL_PREPARATION_COMMAND_UNKNOWN:' + action)


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise CandidateRefused('canonical business UUID required')
    return value


def _scope(value):
    if type(value) is not dict or any(value.get(k) != v for k, v in SCOPE.items()):
        raise CandidateRefused('local synthetic preparation scope required')


def _key(value):
    if type(value) is not str or re.fullmatch('[A-Za-z0-9_-]{1,100}', value) is None:
        raise CandidateRefused('explicit bounded request key required')
    return value


@dataclass(frozen=True)
class PreparationReference:
    preparation_id: str
    run_id: str
    case_id: str
    revision: int
    state: str

    def validate(self):
        for value in (self.preparation_id, self.run_id, self.case_id):
            _uuid(value)
        if (type(self.revision) is not int or not 1 <= self.revision <= 64
                or self.state not in ('IN_PREPARATION', 'CHANGES_REQUESTED', 'REVIEWED', 'LOCAL_CONFIRMED')):
            raise CandidateRefused('bounded current preparation reference required')


@dataclass(frozen=True, repr=False)
class PreparationCheckpoint:
    reference: PreparationReference
    view: bytes = field(repr=False)

    def __reduce__(self):
        raise TypeError('private local material checkpoint cannot be serialized')


class PreparationClient:
    """One existing actor, one running invocation; never switches role silently."""
    def __init__(self, workspace, actor):
        self.workspace, self.actor = workspace, actor

    def _role(self, expected):
        self.actor.expected()
        if self.actor.actor[3] != expected:
            raise CandidateRefused('explicit preparation action role required')

    def _request(self, method, path, body=None, key=None):
        self.workspace.check()
        deadline = time.monotonic() + 30
        result = self.workspace.transport.request(self.workspace.application, self.actor,
                                                  method, path, body, key, deadline)
        self.workspace.check()
        if time.monotonic() >= deadline:
            raise CandidateRefused('local preparation request deadline')
        # Copy provider-owned objects and enforce the shared response bound.
        raw = json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')
        if len(raw) > 1_000_000:
            raise CandidateRefused('bounded preparation JSON response required')
        result = json.loads(raw)
        if type(result) is not dict:
            raise CandidateRefused('preparation JSON object required')
        return result

    def _write(self, action, key, method, path, body, consume):
        self.workspace.check()  # Known expired/pre-dispatch refusal is not a write outcome.
        _key(key)
        try:
            return consume(self._request(method, path, body, key))
        except Exception as error:
            # A lost response may follow a committed SQL transaction. Retain the
            # SAME caller key/previous reference for explicit recovery; no retry,
            # compensating delete, fabricated rollback or local state advance.
            raise PreparationCommandUnknown(action, key, error) from None

    def submit_case(self, goal, key):
        self._role('enterprise_operator')
        body = Intake(goal=goal).model_dump(mode='json')
        return self._write('CASE_SUBMIT', key, 'POST', '/api/runs', body,
                           lambda value: _uuid(value['run_id']))

    def create_preparation(self, run_id, key):
        self._role('enterprise_operator')
        _uuid(run_id)
        run = self._request('GET', '/api/runs/' + run_id)
        if run.get('state') != 'SUCCEEDED':
            raise CandidateRefused('original worker must finish case before preparation')
        body = CreatePreparation(run_id=run_id, service_id='synthetic-material-preparation',
                                 service_version=1, reviewer_id='prep-specialist-fixture-a')
        return self._write('CREATE', key, 'POST', '/api/preparations', body.model_dump(mode='json'),
                           lambda value: self._event(value, 'CREATE', run_id=run_id))

    def _event(self, value, action, previous=None, run_id=None):
        _scope(value)
        if value.get('action') != action or value.get('actor_id') != self.actor.actor[0]:
            raise CandidateRefused('current actor command event required')
        ref = PreparationReference(value['preparation_id'], value['run_id'], value['case_id'],
                                   value['revision'], value['state'])
        ref.validate()
        if previous is not None:
            if ((ref.preparation_id, ref.run_id, ref.case_id) !=
                    (previous.preparation_id, previous.run_id, previous.case_id)
                    or ref.revision != previous.revision + 1):
                raise CandidateRefused('same preparation and next revision required')
        elif ref.run_id != run_id or ref.revision != 1:
            raise CandidateRefused('original run and initial revision required')
        expected = {'CREATE': 'IN_PREPARATION', 'ADD_EVIDENCE': 'IN_PREPARATION',
                    'REVIEW': 'REVIEWED', 'CONFIRM': 'LOCAL_CONFIRMED'}
        if ref.state != expected[action]:
            raise CandidateRefused('expected local command state required')
        return ref

    def _command(self, ref, key, data):
        if type(ref) is not PreparationReference:
            raise CandidateRefused('explicit preparation reference required')
        ref.validate()
        return self._write(data.action, key, 'POST', '/api/preparations/' + ref.preparation_id + '/commands',
                           data.model_dump(mode='json', exclude_unset=True), lambda value: self._event(value, data.action, ref))

    def add_evidence(self, ref, key, *, slot, text, source_label):
        self._role('enterprise_operator')
        return self._command(ref, key, PreparationCommand(action='ADD_EVIDENCE',
            expected_revision=ref.revision, slot=slot, text=text,
            source_kind='DOCUMENT_EXCERPT', source_label=source_label))

    def review(self, ref, key, *, reason):
        self._role('park_specialist')
        return self._command(ref, key, PreparationCommand(action='REVIEW',
                                                        expected_revision=ref.revision, reason=reason))

    def confirm(self, ref, key, *, reason):
        self._role('enterprise_operator')
        return self._command(ref, key, PreparationCommand(action='CONFIRM',
                                                        expected_revision=ref.revision, reason=reason))

    def read(self, ref):
        if type(ref) is not PreparationReference:
            raise CandidateRefused('explicit preparation reference required')
        ref.validate()
        value = self._request('GET', '/api/preparations/' + ref.preparation_id)
        _scope(value)
        row = value['preparation']
        if (row['id'], row['run_id'], row['case_id']) != (ref.preparation_id, ref.run_id, ref.case_id):
            raise CandidateRefused('same persistent preparation required')
        if (type(row['revision']) is not int or row['revision'] < ref.revision
                or type(value.get('snapshot_sha256')) is not str
                or re.fullmatch('[a-f0-9]{64}', value['snapshot_sha256']) is None):
            raise CandidateRefused('current persisted revision and snapshot required')
        return value

    def checkpoint(self, ref):
        self._role('enterprise_operator')
        value = self.read(ref)
        if value['preparation']['state'] != 'LOCAL_CONFIRMED' or value['preparation']['revision'] != ref.revision:
            raise CandidateRefused('current local confirmation required before checkpoint')
        fields = ('preparation', 'current_materials', 'material_history', 'history', 'snapshot_sha256', *SCOPE)
        view = {name: value[name] for name in fields}
        return PreparationCheckpoint(ref, json.dumps(view, ensure_ascii=False,
            sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8'))

    def verify_reopened(self, expected):
        self._role('enterprise_operator')
        if type(expected) is not PreparationCheckpoint:
            raise CandidateRefused('previous private material checkpoint required')
        observed = self.checkpoint(expected.reference)
        if observed.view != expected.view:
            raise CandidateRefused('persistent preparation changed; explicit review required')
        return observed  # Business readback only, never native restart evidence.


class PreparationWorkspace:
    def __init__(self, application, identities, transport, check):
        if type(identities) is not PreparationIdentities or not callable(check):
            raise CandidateRefused('explicit running workspace dependencies required')
        self.application, self.transport = application, transport
        self._check, self._active = check, True
        values = identities.mapping()
        self.enterprise = PreparationClient(self, ExistingActorProbe(values['fixture-a'],
            ('fixture-a', 'park-a', 'org-a', 'enterprise_operator')))
        self.reviewer = PreparationClient(self, ExistingActorProbe(values['prep-specialist-fixture-a'],
            ('prep-specialist-fixture-a', 'park-a', 'org-a', 'park_specialist')))

    def check(self):
        if not self._active:
            raise CandidateRefused('business session ended with its owned invocation')
        self._check()

    def close(self):
        self._active = False


class LocalPreparationInvocation:
    native_acceptance = False

    def __init__(self, controller, processes, security, transport):
        if (type(controller) is not Controller or controller.processes is not processes
                or controller.security is not security or type(security) is not PreparationSecurity
                or type(controller.database) is not PreparationDatabaseOperations
                or not callable(getattr(transport, 'request', None))):
            raise CandidateRefused('one explicit local composition required')
        self.controller, self.processes, self.security, self.transport = controller, processes, security, transport

    def _use(self, use):
        if not callable(use):
            raise CandidateRefused('explicit local business callback required')

        def run(application):
            lease, inputs = self.processes.lease, self.processes.inputs

            def check():
                lease._verify()
                if (lease.status() != 'RUNNING' or self.processes.lease is not lease
                        or self.processes.inputs is not inputs or self.processes.application is not application
                        or self.processes.failed):
                    raise CandidateRefused('same live running invocation required')

            check()
            workspace = PreparationWorkspace(application, self.security.identities(lease), self.transport, check)
            try:
                use(workspace)  # Callback/private materials never become Controller report data.
            finally:
                workspace.close()
        return run

    def create(self, root, use):
        return self.controller.create(root, self._use(use))  # Original OWNER gate, unchanged.

    def reopen(self, root, use):
        return self.controller.reopen(root, self._use(use))  # No new seed/credential path.


def compose_local_preparation(directories, security, prerequisites: ClusterPrerequisites, sessions,
                              transport: PreparationRequestPort, *, initdb_sha256, initdb_size,
                              postgres_sha256, postgres_size, python_sha256, python_size,
                              api_port, challenge):
    """Pure dependency wiring, NOT a native factory or portable-entry admission.

    Required native Security/ClusterPrerequisites, protected reviewer storage
    and native endpoint ownership remain missing. Nothing opens/starts here.
    Each lifecycle attempt requires a new composition; original process ports
    are single use. No usable_product or acceptance value is promoted.
    """
    adapted = PreparationSecurity(security, sessions)
    cluster = FixedClusterProcesses(prerequisites, initdb_sha256=initdb_sha256, initdb_size=initdb_size,
                                   postgres_sha256=postgres_sha256, postgres_size=postgres_size)
    processes = InstanceProcesses(cluster, python_sha256=python_sha256, python_size=python_size,
                                  api_port=api_port, challenge=challenge)
    controller = Controller(directories, adapted, processes, database=PreparationDatabaseOperations())
    return LocalPreparationInvocation(controller, processes, adapted, transport)
