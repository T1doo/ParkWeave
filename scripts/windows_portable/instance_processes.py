"""Fixed application-pair wiring for the explicit native composition.

Cluster creation and reopen are distinct ports; native admission stays gated.
The controller alone authenticates readiness, persists RUNNING and sends GO.
"""
from typing import Protocol

from .application_readiness import RegisteredApplication
from .controller import CandidateRefused, DatabaseInputs
from .processes import Command, PrivateProcessAdapter, private_root


class ClusterProcesses(Protocol):
    def create_cluster(self, lease, credentials, register) -> DatabaseInputs: ...
    def open_cluster(self, lease, credentials, register) -> DatabaseInputs:
        """Existing cluster only: no initdb, schema, seed or session repair."""
        ...
    def stop_owned(self, token) -> bool: ...


class InstanceProcesses:
    """One invocation, one exact lease, one create OR reopen, one app pair.

    The supplied cluster port is trusted internal code, not a loader or approval.
    The native composition supplies NativeProtectedClusterProcesses. Tokens go
    directly to the controller at original creation time, before startup finishes.
    """
    def __init__(self, cluster: ClusterProcesses, *, python_sha256, python_size, api_port=None, challenge,
                 endpoint_source=None,session_provider=None):
        from parkweave.runtime_readiness import challenge as require_challenge
        require_challenge(challenge)
        if endpoint_source is None:
            if type(api_port) is not int or not 1 <= api_port <= 65535:
                raise CandidateRefused('fixed local API port required')
        else:
            from .fixed_store_security import IsolatedFixedStoreSecurity
            from .native_instance_security import NativeFixedStoreSecurity
            if type(endpoint_source) not in (IsolatedFixedStoreSecurity,NativeFixedStoreSecurity) or api_port is not None:
                raise CandidateRefused('explicit endpoint source OR API port required')
        # Validate frozen payload identity without opening or executing anything.
        self.python = Command('runtime/python/python.exe', python_sha256, python_size, model='WINDOWS_JOB')
        self.cluster, self.api_port, self.challenge = cluster, api_port, challenge
        self.endpoint_source = endpoint_source
        if session_provider is not None:
            from .native_preparation_sessions import NativePreparationSessionProvider
            if type(session_provider) is not NativePreparationSessionProvider:
                raise CandidateRefused('original native session provider required')
        self.session_provider = session_provider
        self.lease = self.inputs = self.application = None
        self.mode = None
        self.app_attempted = self.failed = False
        self._owned = {}

    def _register(self, owner, callback):
        def record(token):
            if token is None or id(token) in self._owned or len(self._owned) >= 8:
                raise CandidateRefused('distinct invocation ownership required')
            # Retain ownership even when the external callback raises.
            self._owned[id(token)] = [token, owner, False, False]
            callback(token)
        return record

    def _cluster(self, mode, lease, credentials, register):
        if self.mode is not None or self.failed or lease.status() != 'CLUSTER' or not callable(register):
            raise CandidateRefused('single cluster attempt in original phase required')
        lease._verify()
        self.mode, self.lease = mode, lease  # Consume before an uncertain external action.
        try:
            if self.endpoint_source is not None and self.endpoint_source.mode.value != mode:
                raise CandidateRefused('same endpoint lifecycle mode required')
            method = self.cluster.create_cluster if mode == 'NEW' else self.cluster.open_cluster
            inputs = method(lease, credentials, self._register(self.cluster, register))
            if not self._owned or type(inputs) is not DatabaseInputs:
                raise CandidateRefused('registered explicit cluster inputs required')
            if inputs.data_directory != str(private_root(lease) / 'data' / 'postgresql'):
                raise CandidateRefused('held private cluster directory required')
            if self.endpoint_source is not None:self.endpoint_source.require_inputs(lease,inputs)
            self.inputs = inputs
            return inputs
        except BaseException:
            self.failed = True
            raise

    def create_cluster(self, lease, credentials, register):
        from scripts.windows.lifecycle import require_setup_readiness
        require_setup_readiness()  # No standalone creation can bypass the original pause.
        return self._cluster('NEW', lease, credentials, register)

    def open_cluster(self, lease, credentials, register):
        return self._cluster('REOPEN', lease, credentials, register)

    def start_application(self, lease, inputs, register):
        if (self.failed or self.app_attempted or self.lease is not lease or inputs is not self.inputs or
                self.inputs is None or lease.status() != 'APPLICATION' or not callable(register) or
                any(row[2] for row in self._owned.values())):
            raise CandidateRefused('same live lease and original cluster inputs required')
        lease._verify()
        self.app_attempted = True
        try:
            from parkweave.installed_fixture_receipt import _dsn
            if self.endpoint_source is not None:
                ports = self.endpoint_source.require_inputs(lease,inputs)
                self.api_port = ports['api_port']
            parsed = _dsn(inputs.application_dsn, 'parkweave')
            if int(parsed['port']) == self.api_port:
                raise CandidateRefused('distinct fixed database and API ports required')
            environment = (('PARKWEAVE_DSN', inputs.application_dsn), ('PARKWEAVE_MODE', 'LOCAL'),
                           ('PARKWEAVE_FILE_ROOT', str(private_root(lease) / 'files')))
            api_environment=environment
            api_factory='parkweave.api:configured_app'
            if self.session_provider is not None:
                from .native_web_login import ENVIRONMENT
                api_environment=environment+((ENVIRONMENT,self.session_provider.web_configuration(lease,inputs)),)
                api_factory='scripts.windows_portable.native_web_login:configured_app'
            def command(arguments, stdio='NONE', *, config=environment):
                return Command(self.python.relative_executable, self.python.sha256, self.python.size,
                               arguments, 'WINDOWS_JOB', stdio, config)
            commands = {
                'api': command(('-I', '-B', '-m', 'uvicorn', api_factory, '--factory',
                                '--host', '127.0.0.1', '--port', str(self.api_port), '--no-access-log'),config=api_environment),
                'worker': command(('-I', '-B', '-m', 'parkweave.worker', '--readiness-stdio',
                                   '--readiness-challenge', self.challenge), 'WORKER_READINESS_V1'),
            }
            adapter = PrivateProcessAdapter(lease, commands)
            record = self._register(adapter, register)
            api = adapter.launch('api', record)
            worker = adapter.launch('worker', record)
            self.application = RegisteredApplication(adapter, api, worker, self.api_port, self.challenge,
                database_endpoint=getattr(self.cluster,'endpoint',None))
            return self.application  # NOT ready; no probe, checkpoint or GO here.
        except BaseException:
            self.failed = True
            raise

    def stop_owned(self, token):
        row = self._owned.get(id(token))
        if row is None or row[0] is not token:
            raise CandidateRefused('this invocation ownership required')
        if row[2]:
            return True
        if row[3]:
            return False  # Unknown cleanup is never sent again to a cluster port.
        row[3] = True
        try:
            if row[1].stop_owned(token) is not True:
                self.failed = True
                return False
            row[2] = True
            return True
        except BaseException:
            self.failed = True
            raise
