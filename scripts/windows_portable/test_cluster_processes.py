"""Cluster orchestration stand-ins only. No PG, files, network or child process."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.windows import lifecycle
from . import cluster_processes as c
from .controller import CandidateRefused, DatabaseInputs


ROOT = Path('/synthetic/private-root')
NONCE = '0123456789abcdef0123456789abcdef'
INPUTS = DatabaseInputs('host=127.0.0.1 port=55432 user=postgres dbname=postgres sslmode=disable',
                        'host=127.0.0.1 port=55432 user=postgres dbname=parkweave sslmode=disable',
                        'host=127.0.0.1 port=55432 user=parkweave_app dbname=parkweave sslmode=disable',
                        str(ROOT / 'data' / 'postgresql'))


class Clock:
    value = 100
    def __call__(self): return self.value


class Checks:
    def __init__(self, events):
        self.events = events; self.inputs = INPUTS; self.failure = None; self.late = None; self.deadlines = {}
    def event(self, name):
        self.events.append(name)
        if self.failure is not None and name == self.failure[0]: raise self.failure[1]
        if self.late is not None and name == self.late[0]: self.late[1].value += 31
    def configuration(self, lease, credentials, deadline):
        self.deadlines['configuration'] = deadline; self.event('CONFIG'); return self.inputs
    def before_initdb(self, lease, inputs, password_file, deadline):
        assert inputs is self.inputs and password_file == str(ROOT / 'secrets' / 'postgres-bootstrap.password')
        self.deadlines['initdb'] = deadline
        self.event('NEW_INPUTS')
    def before_server(self, lease, inputs, mode, deadline):
        assert inputs is self.inputs; self.deadlines['server'] = deadline; self.event('FILES:' + mode)
    def server_ready(self, lease, inputs, adapter, token, deadline):
        assert inputs is self.inputs and token is adapter.tokens['postgres']
        self.deadlines['ready'] = deadline; self.event('READY_STANDIN')


class Adapter:
    """Records fixed commands/callback timing only; no original native backend."""
    def __init__(self, lease, commands, events, clock):
        self.lease, self.commands, self.events, self.clock = lease, commands, events, clock
        self.tokens = {name: object() for name in commands}
        self.exit_code, self.stop_result, self.launch_error = 0, True, None
        self.drift = False; self.identities = 0
    def name(self, token): return next(k for k, v in self.tokens.items() if v is token)
    def launch(self, name, register):
        self.events.append('REGISTER:' + name); register(self.tokens[name]); self.events.append('LAUNCH:' + name)
        if self.launch_error is not None and self.launch_error[0] == name: raise self.launch_error[1]
        return self.tokens[name]
    def observe(self, token, seconds):
        assert self.name(token) == 'initdb' and 0 < seconds <= 5
        self.events.append('OBSERVE:initdb'); self.clock.value += min(5, seconds)
        return self.exit_code
    def stop_owned(self, token):
        self.events.append('STOP:' + self.name(token))
        if isinstance(self.stop_result, BaseException): raise self.stop_result
        return self.stop_result
    def live_identity(self, token):
        assert self.name(token) == 'postgres'
        self.identities += 1
        return (123, 456 + (self.identities if self.drift else 0), 'f' * 64)


class ClusterProcessChecks(unittest.TestCase):
    def setUp(self):
        self.events, self.registered, self.adapters = [], [], []
        self.clock = Clock()
        self.lease = SimpleNamespace(_verify=Mock(), status=lambda: 'CLUSTER',
                                     fs=SimpleNamespace(base=ROOT.parent, chain=[(None, ROOT.name)]))
        self.checks = Checks(self.events)
        self.provider = self.provider_for(self.checks)
        self.make_options = {}
        def factory(lease, commands):
            adapter = Adapter(lease, commands, self.events, self.clock)
            for key, value in self.make_options.items(): setattr(adapter, key, value)
            self.adapters.append(adapter); return adapter
        for target, value in (('PrivateProcessAdapter', factory),):
            seam = patch.object(c, target, value); seam.start(); self.addCleanup(seam.stop)
        seam = patch.object(c.time, 'monotonic', self.clock); seam.start(); self.addCleanup(seam.stop)

    def provider_for(self, checks):
        return c.FixedClusterProcesses(checks, initdb_sha256='a' * 64, initdb_size=100,
                                        postgres_sha256='b' * 64, postgres_size=200)

    def create(self):
        with patch.object(lifecycle, 'require_setup_readiness'):
            return self.provider.create_cluster(self.lease, object(), self.registered.append)

    def reopen(self):
        return self.provider.open_cluster(self.lease, object(), self.registered.append)

    def cleanup(self):
        return [self.provider.stop_owned(token) for token in reversed(self.registered)]

    def test_original_new_pause_calls_no_configuration_or_process_port(self):
        with self.assertRaises(lifecycle.BoundaryError) as failure:
            self.provider.create_cluster(self.lease, object(), self.registered.append)
        self.assertEqual(failure.exception.parkweave_lifecycle_reason, 'OWNER_MUTATION_PAUSED')
        self.assertEqual(self.events, []); self.assertEqual(self.adapters, []); self.assertEqual(self.registered, [])

    def test_new_fixed_initdb_exit_and_tree_close_precede_foreground_postgres_and_identity_check(self):
        self.assertIs(self.create(), INPUTS)
        self.assertEqual(self.events, ['CONFIG', 'NEW_INPUTS', 'REGISTER:initdb', 'LAUNCH:initdb',
                         'OBSERVE:initdb', 'STOP:initdb', 'FILES:NEW', 'REGISTER:postgres', 'LAUNCH:postgres', 'READY_STANDIN'])
        adapter = self.adapters[0]
        self.assertEqual(self.registered, [adapter.tokens['initdb'], adapter.tokens['postgres']])
        self.assertEqual(adapter.commands['initdb'].arguments, ('-D', INPUTS.data_directory, '-U', 'postgres',
            '--pwfile', str(ROOT / 'secrets' / 'postgres-bootstrap.password'), '--auth-local=scram-sha-256',
            '--auth-host=scram-sha-256', '--encoding=UTF8', '--locale=C'))
        self.assertEqual(adapter.commands['postgres'].arguments[:6], ('-D', INPUTS.data_directory, '-h', '127.0.0.1', '-p', '55432'))
        for command in adapter.commands.values():
            self.assertEqual(command.environment, ()); self.assertEqual(command.model, 'WINDOWS_JOB')
            self.assertFalse(any('password=' in arg or arg in ('-F', '--no-sync', '--single') for arg in command.arguments))
        self.assertEqual(self.cleanup(), [True, True]); self.assertEqual(self.events.count('STOP:initdb'), 1)
        self.assertEqual(self.checks.deadlines, dict(configuration=130, initdb=130, server=130, ready=127))

    def test_reopen_has_no_initdb_password_file_or_new_gate_and_no_fallback_on_missing_files(self):
        with patch.object(lifecycle, 'require_setup_readiness', side_effect=AssertionError('NEW on REOPEN')):
            self.assertIs(self.reopen(), INPUTS)
        self.assertEqual(set(self.adapters[0].commands), {'postgres'})
        self.assertEqual(self.events, ['CONFIG', 'FILES:REOPEN', 'REGISTER:postgres', 'LAUNCH:postgres', 'READY_STANDIN'])
        self.assertEqual(self.cleanup(), [True])
        provider = self.provider_for(self.checks)
        marker = FileNotFoundError('SYNTHETIC_MISSING_TREE')
        self.checks.failure = ('FILES:REOPEN', marker)
        before = len(self.registered)
        with self.assertRaises(c.ClusterStartFailure) as failure:
            provider.open_cluster(self.lease, object(), self.registered.append)
        self.assertIs(failure.exception.primary, marker)
        self.assertEqual(len(self.registered), before); self.assertNotIn('NEW_INPUTS', self.events)

    def test_nonzero_or_wrong_type_initdb_exit_never_starts_server_and_retains_code(self):
        for code in (7, False):
            with self.subTest(code=code):
                self.provider = self.provider_for(self.checks); self.make_options['exit_code'] = code
                self.registered.clear(); self.events.clear()
                with self.assertRaises(c.ClusterStartFailure) as failure: self.create()
                self.assertEqual(failure.exception.phase, 'INITDB_WAIT')
                self.assertEqual(failure.exception.initdb_returncode, code if type(code) is int else None)
                self.assertNotIn('REGISTER:postgres', self.events); self.assertEqual(self.cleanup(), [True])

    def test_initdb_exit_zero_does_not_substitute_unknown_job_tree_cleanup(self):
        self.make_options['stop_result'] = False
        with self.assertRaises(c.ClusterStartFailure) as failure: self.create()
        self.assertEqual(failure.exception.phase, 'INITDB_TREE_EXIT'); self.assertEqual(failure.exception.initdb_returncode, 0)
        self.assertEqual(self.cleanup(), [False]); self.assertEqual(self.events.count('STOP:initdb'), 1)
        self.assertNotIn('REGISTER:postgres', self.events)
        with self.assertRaises(CandidateRefused): self.reopen()

    def test_partial_server_failure_keeps_primary_token_and_only_exact_once_cleanup(self):
        marker = OSError('SYNTHETIC_AFTER_REGISTRATION')
        self.make_options['launch_error'] = ('postgres', marker)
        with self.assertRaises(c.ClusterStartFailure) as failure: self.reopen()
        self.assertIs(failure.exception.primary, marker); self.assertIs(failure.exception.__cause__, marker)
        self.assertEqual(failure.exception.phase, 'SERVER_START')
        self.assertEqual(len(self.registered), 1); self.assertEqual(self.cleanup(), [True]); self.assertEqual(self.cleanup(), [True])
        self.assertEqual(self.events.count('STOP:postgres'), 1)
        with self.assertRaises(CandidateRefused): self.provider.stop_owned(object())

    def test_shared_deadline_blocks_late_input_and_never_invents_initdb_success(self):
        self.checks.late = ('NEW_INPUTS', self.clock)
        with self.assertRaises(c.ClusterStartFailure): self.create()
        self.assertEqual(self.registered, [])
        self.checks.late = None; self.clock.value = 100; self.events.clear()
        self.provider = self.provider_for(self.checks); self.make_options['exit_code'] = None
        with self.assertRaises(c.ClusterStartFailure) as failure: self.create()
        self.assertEqual(failure.exception.phase, 'INITDB_WAIT'); self.assertIsNone(failure.exception.initdb_returncode)
        self.assertNotIn('REGISTER:postgres', self.events); self.assertEqual(self.cleanup(), [True])

    def test_readiness_error_or_birth_drift_returns_no_inputs_and_cannot_relaunch(self):
        marker = PermissionError('SYNTHETIC_OWNER_WITNESS_REFUSED')
        self.checks.failure = ('READY_STANDIN', marker)
        with self.assertRaises(c.ClusterStartFailure) as failure: self.reopen()
        self.assertIs(failure.exception.primary, marker); self.assertEqual(self.cleanup(), [True])
        with self.assertRaises(CandidateRefused): self.reopen()
        self.checks.failure = None; self.provider = self.provider_for(self.checks)
        self.make_options['drift'] = True; self.registered.clear()
        with self.assertRaises(c.ClusterStartFailure): self.reopen()
        self.assertEqual(self.cleanup(), [True])

    def test_wrong_root_or_role_or_endpoint_is_refused_before_any_process(self):
        for inputs in (DatabaseInputs(INPUTS.maintenance_dsn, INPUTS.owner_dsn, INPUTS.application_dsn, '/synthetic/other'),
                       DatabaseInputs(INPUTS.maintenance_dsn, INPUTS.owner_dsn,
                                      INPUTS.application_dsn.replace('55432', '55433'), INPUTS.data_directory),
                       DatabaseInputs(INPUTS.maintenance_dsn, INPUTS.owner_dsn,
                                      INPUTS.application_dsn.replace('parkweave_app', 'postgres'), INPUTS.data_directory)):
            with self.subTest(inputs_type=type(inputs).__name__):
                self.provider = self.provider_for(self.checks); self.checks.inputs = inputs
                with self.assertRaises(c.ClusterStartFailure): self.reopen()
                self.assertEqual(self.registered, []); self.assertEqual(self.adapters, [])

    def test_original_controller_and_application_bridge_new_then_reopen_keep_full_token_routing(self):
        from . import instance_processes as pair
        from . import application_readiness as ready
        from .controller import Controller
        from .test_controller import FakeInstallation
        from .test_instance_processes import ApplicationAdapter
        installation = FakeInstallation()
        installation._verify = Mock(); installation.fs = self.lease.fs
        observed = []
        def before(lease, inputs, app, probe, registered):
            self.assertIs(lease, installation); self.assertIs(inputs, INPUTS)
            self.assertEqual(lease.state, 'APPLICATION'); self.assertEqual(registered, [app.api, app.worker])
            observed.append('READY_STANDIN'); return app
        def check(app): self.assertEqual(installation.state, 'APPLICATION'); observed.append('CHECK')
        def go(app): self.assertEqual(installation.state, 'RUNNING'); observed.append('GO_STANDIN')
        def use(app): self.assertEqual(observed[-1], 'GO_STANDIN'); observed.append('USE')
        def bridge(provider):
            return pair.InstanceProcesses(provider, python_sha256='c' * 64, python_size=300,
                                          api_port=58000, challenge=NONCE)
        ApplicationAdapter.fail, ApplicationAdapter.exit = None, True
        with patch.object(lifecycle, 'require_setup_readiness'), \
                patch.object(pair, 'PrivateProcessAdapter', ApplicationAdapter), \
                patch.object(ready, 'require_application_ready', side_effect=before), \
                patch.object(ready, 'check_before_running', side_effect=check), \
                patch.object(ready, 'activate_application', side_effect=go):
            application = bridge(self.provider)
            result = Controller(installation, installation, application, database=installation).create(str(ROOT), use)
            self.assertEqual(result['mode'], 'NEW')
            self.assertEqual(observed, ['READY_STANDIN', 'CHECK', 'GO_STANDIN', 'USE'])
            self.assertEqual(len(application._owned), 4)
            self.assertEqual(application.application.adapter.events[-2:], ['STOP:worker', 'STOP:api'])
            self.assertEqual(self.events.count('STOP:initdb'), 1); self.assertEqual(self.events.count('STOP:postgres'), 1)
            installation.events.clear(); self.events.clear(); observed.clear()
            provider = self.provider_for(self.checks); application = bridge(provider)
            result = Controller(installation, installation, application, database=installation).reopen(str(ROOT), use)
            self.assertEqual(result['mode'], 'REOPEN'); self.assertEqual(len(application._owned), 3)
            self.assertEqual(set(provider.adapter.commands), {'postgres'})
            self.assertNotIn('NEW_INPUTS', self.events)
            self.assertFalse({'prepare_roles', 'creation_support', 'credentials', 'sessions',
                              'create_schema', 'roles', 'seed', 'config'}.intersection(installation.events))

    def test_owner_readiness_and_cleanup_double_failure_keep_original_cause_and_unknown(self):
        from . import instance_processes as pair
        from .controller import Controller, ControlFailure
        from .test_controller import FakeInstallation
        installation = FakeInstallation().ready()
        installation._verify = Mock(); installation.fs = self.lease.fs
        marker, cleanup = PermissionError('SYNTHETIC_OWNER_REFUSAL'), OSError('SYNTHETIC_STOP_FAILURE')
        self.checks.failure = ('READY_STANDIN', marker); self.make_options['stop_result'] = cleanup
        application = pair.InstanceProcesses(self.provider, python_sha256='c' * 64, python_size=300,
                                             api_port=58000, challenge=NONCE)
        with self.assertRaises(ControlFailure) as failure:
            Controller(installation, installation, application, database=installation).reopen(str(ROOT), lambda app: self.fail('use'))
        self.assertIs(failure.exception.primary, marker)
        self.assertIs(failure.exception.cleanup_errors[0][1], cleanup)
        self.assertEqual(installation.state, 'UNKNOWN')
        self.assertEqual(self.events.count('STOP:postgres'), 1)
        self.assertFalse(application.stop_owned(self.adapters[0].tokens['postgres']))
        self.assertEqual(self.events.count('STOP:postgres'), 1)


if __name__ == '__main__': unittest.main()
