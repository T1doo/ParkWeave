"""Fixed private PG process orchestration; no activated native/security ports.

No direct SQL, credential, role, session, service or filesystem operations.
The initdb command would initialize a new private cluster only after the original
creation gate and required protected-input checks. No entry calls this module.
"""
import time
from typing import Protocol

from .controller import CandidateRefused, DatabaseInputs
from .processes import Command, PrivateProcessAdapter, private_root


class ClusterPrerequisites(Protocol):
    """Required trusted Security/identity dependencies, not permissive defaults.

    No production implementation exists yet. A configuration object is not a
    creation receipt, permission, file-protection proof or readiness witness.
    All methods must respect the supplied absolute deadline without retrying
    uncertain writes or repairing an existing installation.
    """
    def configuration(self, lease, credentials, deadline) -> DatabaseInputs:
        """Existing protected inputs bound to this exact lease; never mint secrets."""
        ...
    def before_initdb(self, lease, inputs, password_file, deadline):
        """Verify/hold protected password file, parent and absent new data target.

        Native handle/owner/DACL/reparse/name guarantees must cover initdb's
        later path opens. No path-string equality or journal substitutes them.
        """
        ...
    def before_server(self, lease, inputs, mode, deadline):
        """Validate/hold new initialized or existing tree, config and PG identity.

        REOPEN must reject missing/partial/changed files, UNKNOWN handoff or
        unconfirmed previous process exit. It never initializes or repairs.
        Normal PostgreSQL WAL recovery is not schema migration; the later real
        ready probe must wait for it. Owned Job exit is not a clean-DB shutdown.
        """
        ...
    def server_ready(self, lease, inputs, adapter, token, deadline):
        """Real owner-authenticated maintenance DB and exact physical cluster.

        Check connected endpoint ownership against the original process birth
        before credentials are sent. An exec/port-open/pg_isready result is not
        sufficient. This does not provision the application's required role.
        """
        ...


class ClusterStartFailure(CandidateRefused):
    def __init__(self, phase, primary, initdb_returncode):
        self.phase, self.primary = phase, primary
        self.outcome = 'UNKNOWN'
        self.initdb_returncode = initdb_returncode
        super().__init__('PRIVATE_CLUSTER_UNKNOWN:' + phase)


class FixedClusterProcesses:
    """One original lease and one NEW or REOPEN attempt; no fallback or repair."""
    def __init__(self, prerequisites: ClusterPrerequisites, *, initdb_sha256, initdb_size,
                 postgres_sha256, postgres_size):
        self.prerequisites = prerequisites
        self.initdb = Command('runtime/postgresql/bin/initdb.exe', initdb_sha256, initdb_size, model='WINDOWS_JOB')
        self.postgres = Command('runtime/postgresql/bin/postgres.exe', postgres_sha256, postgres_size, model='WINDOWS_JOB')
        self.lease = self.inputs = self.adapter = None
        self.mode = None
        self.failed = False
        self._owned = {}

    def _time(self, deadline, reserve=0):
        self.lease._verify()
        left = deadline - time.monotonic()
        if left <= reserve:
            raise CandidateRefused('private cluster startup deadline')
        return left - reserve

    def _configuration(self, lease, credentials, deadline):
        from parkweave.installed_fixture_receipt import _dsn
        self._time(deadline)
        inputs = self.prerequisites.configuration(lease, credentials, deadline)
        if type(inputs) is not DatabaseInputs or inputs.data_directory != str(private_root(lease) / 'data' / 'postgresql'):
            raise CandidateRefused('original held cluster inputs required')
        maintenance = _dsn(inputs.maintenance_dsn, 'postgres')
        owner = _dsn(inputs.owner_dsn, 'parkweave')
        application = _dsn(inputs.application_dsn, 'parkweave')
        if (maintenance['host'] != '127.0.0.1' or maintenance['user'] != 'postgres' or
                any(row['host'] != maintenance['host'] or row['port'] != maintenance['port'] for row in (owner, application)) or
                owner['user'] != 'postgres' or application['user'] != 'parkweave_app'):
            raise CandidateRefused('fixed local cluster roles and endpoint required')
        return inputs, maintenance['port']

    def _record(self, register):
        def record(token):
            if token is None or id(token) in self._owned or len(self._owned) >= 2:
                raise CandidateRefused('original distinct cluster capability required')
            self._owned[id(token)] = [token, False, False]
            register(token)  # Original callback, before child creation can continue.
        return record

    def _run(self, mode, lease, credentials, register):
        if self.mode is not None or self.failed or not callable(register) or lease.status() != 'CLUSTER':
            raise CandidateRefused('single original cluster phase required')
        lease._verify()
        self.mode, self.lease = mode, lease  # Consume before any fallible external operation.
        deadline = time.monotonic() + 30
        phase, initdb_returncode = 'CONFIGURATION', None
        try:
            self.inputs, port = self._configuration(lease, credentials, deadline)
            root = private_root(lease)
            password_file = str(root / 'secrets' / 'postgres-bootstrap.password')
            def command(source, arguments):
                return Command(source.relative_executable, source.sha256, source.size, arguments, 'WINDOWS_JOB')
            commands = {'postgres': command(self.postgres, ('-D', self.inputs.data_directory, '-h', '127.0.0.1',
                         '-p', port, '-c', 'unix_socket_directories=', '-c', 'ssl=off',
                         '-c', 'logging_collector=off', '-c', 'log_statement=none'))}
            if mode == 'NEW':
                # No injected trust/fsync-disable/service/shell/SQL/secret argv.
                # initdb itself uses bootstrap/standalone backends and pipes;
                # pinning this top-level EXE does not attest that inner closure.
                commands['initdb'] = command(self.initdb, ('-D', self.inputs.data_directory, '-U', 'postgres',
                                    '--pwfile', password_file, '--auth-local=scram-sha-256',
                                    '--auth-host=scram-sha-256', '--encoding=UTF8', '--locale=C'))
            self.adapter = PrivateProcessAdapter(lease, commands)
            record = self._record(register)
            if mode == 'NEW':
                phase = 'INITDB_INPUTS'
                self._time(deadline, 5)
                self.prerequisites.before_initdb(lease, self.inputs, password_file, deadline)
                self._time(deadline, 5)
                phase = 'INITDB_START'
                token = self.adapter.launch('initdb', record)
                phase = 'INITDB_WAIT'
                while True:
                    code = self.adapter.observe(token, min(5, self._time(deadline, 5)))
                    if code is not None:
                        break
                initdb_returncode = code if type(code) is int else None
                if type(code) is not int or code != 0:
                    raise CandidateRefused('private initdb did not confirm success')
                # Parent exit is not Job-tree exit. Keep the same original token.
                phase = 'INITDB_TREE_EXIT'
                if self.stop_owned(token) is not True:
                    raise CandidateRefused('private initdb tree exit unknown')
            phase = 'SERVER_INPUTS'
            self._time(deadline, 5)
            self.prerequisites.before_server(lease, self.inputs, mode, deadline)
            self._time(deadline, 5)
            phase = 'SERVER_START'
            token = self.adapter.launch('postgres', record)
            identity = self.adapter.live_identity(token)
            phase = 'SERVER_IDENTITY'
            self._time(deadline, 3)
            self.prerequisites.server_ready(lease, self.inputs, self.adapter, token, deadline - 3)
            if self.adapter.live_identity(token) != identity:
                raise CandidateRefused('private postgres creation identity changed')
            self._time(deadline, 3)
            return self.inputs  # Not CREATE DATABASE, schema, role, app readiness or session authority.
        except BaseException as primary:
            self.failed = True
            raise ClusterStartFailure(phase, primary, initdb_returncode) from primary

    def create_cluster(self, lease, credentials, register):
        from scripts.windows.lifecycle import require_setup_readiness
        require_setup_readiness()  # Before configuration, executable pinning, files or native calls.
        return self._run('NEW', lease, credentials, register)

    def open_cluster(self, lease, credentials, register):
        return self._run('REOPEN', lease, credentials, register)

    def stop_owned(self, token):
        row = self._owned.get(id(token))
        if row is None or row[0] is not token:
            raise CandidateRefused('this cluster invocation capability required')
        if row[1]: return True
        if row[2]: return False
        row[2] = True
        try:
            if self.adapter.stop_owned(token) is not True:
                self.failed = True
                return False
            row[1] = True
            return True
        except BaseException:
            self.failed = True
            raise
