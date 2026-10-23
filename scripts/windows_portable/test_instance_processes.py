"""Control-flow stand-ins only: no processes, PG, secrets, native APIs or files."""
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from . import instance_processes as m
from . import processes as p
from .controller import DatabaseInputs, CandidateRefused
from scripts.windows import lifecycle


NONCE = '0123456789abcdef0123456789abcdef'
DSN = 'host=127.0.0.1 port=55432 user=parkweave_app dbname=parkweave sslmode=disable'


class Cluster:
    def __init__(self, inputs):
        self.inputs, self.events = inputs, []
        self.token = object()
        self.exit = True

    def create_cluster(self, lease, credentials, register):
        self.events.append('NEW'); register(self.token); return self.inputs

    def open_cluster(self, lease, credentials, register):
        self.events.append('REOPEN'); register(self.token); return self.inputs

    def stop_owned(self, token):
        assert token is self.token
        self.events.append('STOP'); return self.exit


class ApplicationAdapter:
    """Creation callback timing only, not the real PrivateProcessAdapter."""
    fail = None
    exit = True

    def __init__(self, lease, commands):
        self.lease, self.commands, self.events = lease, commands, []
        self.tokens = {'api': object(), 'worker': object()}

    def launch(self, name, register):
        self.events.append('REGISTER:' + name)
        register(self.tokens[name])
        self.events.append('CREATION_CONTINUES:' + name)
        if self.fail == name:
            raise p.ProcessRefused('SYNTHETIC_CREATION_FAILURE')
        return self.tokens[name]

    def stop_owned(self, token):
        name = next(name for name, value in self.tokens.items() if value is token)
        self.events.append('STOP:' + name); return self.exit


class InstanceProcessChecks(unittest.TestCase):
    def setUp(self):
        self.root = Path('/synthetic/private-root')
        self.lease = SimpleNamespace(_verify=Mock(), status=Mock(return_value='CLUSTER'),
                                     fs=SimpleNamespace(base=self.root.parent, chain=[(None, self.root.name)]))
        self.inputs = DatabaseInputs('NOT_A_MAINTENANCE_DSN', 'NOT_AN_OWNER_DSN', DSN,
                                     str(self.root / 'data' / 'postgresql'))
        self.cluster = Cluster(self.inputs)
        self.instance = m.InstanceProcesses(self.cluster, python_sha256='a' * 64, python_size=100,
                                            api_port=58000, challenge=NONCE)
        self.registered = []
        self.constructor = patch.object(m, 'PrivateProcessAdapter', ApplicationAdapter)
        self.constructor.start(); self.addCleanup(self.constructor.stop)
        ApplicationAdapter.fail, ApplicationAdapter.exit = None, True

    def open(self):
        value = self.instance.open_cluster(self.lease, object(), self.registered.append)
        self.assertIs(value, self.inputs)
        self.lease.status.return_value = 'APPLICATION'
        return value

    def application(self, callback=None):
        return self.instance.start_application(self.lease, self.inputs, callback or self.registered.append)

    def test_create_original_pause_zero_ports_then_explicit_standin_new_vs_reopen(self):
        with self.assertRaises(lifecycle.BoundaryError):
            self.instance.create_cluster(self.lease, object(), self.registered.append)
        self.assertEqual(self.cluster.events, []); self.assertEqual(self.registered, [])
        with patch.object(lifecycle, 'require_setup_readiness'):
            self.instance.create_cluster(self.lease, object(), self.registered.append)
        self.assertEqual(self.cluster.events, ['NEW'])
        with self.assertRaises(CandidateRefused):
            self.instance.open_cluster(self.lease, object(), self.registered.append)
        self.assertEqual(self.cluster.events, ['NEW'])

    def test_reopen_selects_only_existing_port_and_fixed_pair_registers_before_creation_continues(self):
        with patch.object(lifecycle, 'require_setup_readiness', side_effect=AssertionError('new gate on reopen')):
            self.open()
        def register(token):
            self.assertFalse(any(row[0] is token and row[2] for row in self.instance._owned.values()))
            self.registered.append(token)
        app = self.application(register)
        self.assertEqual(self.cluster.events, ['REOPEN'])
        self.assertEqual(self.registered, [self.cluster.token, app.api, app.worker])
        self.assertEqual(app.adapter.events, ['REGISTER:api', 'CREATION_CONTINUES:api',
                                               'REGISTER:worker', 'CREATION_CONTINUES:worker'])
        self.assertEqual(app.adapter.commands['api'].arguments,
                         ('-I', '-B', '-m', 'uvicorn', 'parkweave.api:configured_app', '--factory',
                          '--host', '127.0.0.1', '--port', '58000', '--no-access-log'))
        self.assertEqual(app.adapter.commands['worker'].arguments,
                         ('-I', '-B', '-m', 'parkweave.worker', '--readiness-stdio', '--readiness-challenge', NONCE))
        for command in app.adapter.commands.values():
            self.assertEqual(dict(command.environment), dict(PARKWEAVE_DSN=DSN, PARKWEAVE_MODE='LOCAL',
                                                             PARKWEAVE_FILE_ROOT=str(self.root / 'files')))
            self.assertNotIn(DSN, repr(command)); self.assertNotIn(DSN, str(command.arguments))
        self.assertEqual(app.adapter.commands['worker'].stdio_contract, 'WORKER_READINESS_V1')
        self.assertEqual(self.lease._verify.call_count, 4)
        # No readiness, GO, schema, seed, session or configuration API is exposed/called.
        self.assertEqual(set(app.adapter.commands), {'api', 'worker'})

    def test_wrong_lease_copied_inputs_and_second_pair_are_refused_before_launch(self):
        self.open()
        for lease, inputs in ((SimpleNamespace(), self.inputs),
                              (self.lease, DatabaseInputs(**self.inputs.__dict__))):
            with self.assertRaises(CandidateRefused):
                self.instance.start_application(lease, inputs, self.registered.append)
        app = self.application()
        with self.assertRaises(CandidateRefused): self.application()
        self.assertEqual(len(self.registered), 3)
        self.assertIs(app.adapter.lease, self.lease)

    def test_partial_application_failure_retains_exact_tokens_for_reverse_cleanup_and_no_replay(self):
        self.open(); ApplicationAdapter.fail = 'worker'
        with self.assertRaises(p.ProcessRefused): self.application()
        self.assertEqual(len(self.registered), 3)
        owner = self.instance._owned[id(self.registered[1])][1]
        for token in reversed(self.registered): self.assertTrue(self.instance.stop_owned(token))
        self.assertEqual(owner.events[-2:], ['STOP:worker', 'STOP:api'])
        self.assertEqual(self.cluster.events, ['REOPEN', 'STOP'])
        with self.assertRaises(CandidateRefused): self.application()
        with self.assertRaises(CandidateRefused): self.instance.stop_owned(object())

    def test_cleanup_false_or_raise_never_retries_unknown_owner(self):
        for raises in (False, True):
            with self.subTest(raises=raises):
                self.setUp(); self.open()
                original = self.cluster.stop_owned
                calls = []
                def stop(token):
                    calls.append(token)
                    if raises: raise OSError('SYNTHETIC_CLEANUP_FAILURE')
                    return False
                self.cluster.stop_owned = stop
                if raises:
                    with self.assertRaises(OSError): self.instance.stop_owned(self.cluster.token)
                else: self.assertFalse(self.instance.stop_owned(self.cluster.token))
                self.assertFalse(self.instance.stop_owned(self.cluster.token))
                self.assertEqual(calls, [self.cluster.token])
                with self.assertRaises(CandidateRefused): self.application()
                self.cluster.stop_owned = original

    def test_wrong_cluster_path_poison_attempt_without_application(self):
        self.cluster.inputs = DatabaseInputs('', '', DSN, '/synthetic/elsewhere')
        with self.assertRaises(CandidateRefused): self.open()
        with self.assertRaises(CandidateRefused): self.application()
        self.assertTrue(self.instance.stop_owned(self.cluster.token))
        self.assertEqual(self.cluster.events, ['REOPEN', 'STOP'])

    def test_environment_rejects_extra_live_owner_external_or_alias_input(self):
        from parkweave.store import Denied
        valid = (('PARKWEAVE_DSN', DSN), ('PARKWEAVE_MODE', 'LOCAL'), ('PARKWEAVE_FILE_ROOT', str(self.root / 'files')))
        for environment in (list(valid), (), valid + (('UNTRUSTED', 'x'),),
                            tuple((k, 'LIVE' if k == 'PARKWEAVE_MODE' else v) for k, v in valid),
                            tuple((k, v.replace('parkweave_app', 'postgres')) for k, v in valid),
                            tuple((k, v.replace('127.0.0.1', '192.0.2.1')) for k, v in valid)):
            with self.subTest(environment_type=type(environment).__name__):
                if environment == (): continue  # Original no-config command remains supported.
                with self.assertRaises((p.ProcessRefused, Denied)):
                    p.Command('runtime/python/python.exe', 'a' * 64, 100, model='WINDOWS_JOB', environment=environment)

    def test_original_controller_new_and_reopen_keep_readiness_and_go_after_running(self):
        from .controller import Controller
        from .test_controller import FakeInstallation
        from . import application_readiness as ready
        installation = FakeInstallation()
        installation._verify = Mock()
        installation.fs = self.lease.fs
        observed = []
        def ready_pair(lease, inputs, app, probe, registered):
            self.assertIs(lease, installation); self.assertIs(inputs, self.inputs)
            self.assertEqual(lease.state, 'APPLICATION')
            self.assertEqual(registered, [app.api, app.worker])
            observed.append('READY'); return app
        def check(app):
            self.assertEqual(installation.state, 'APPLICATION'); observed.append('CHECK')
        def go(app):
            self.assertEqual(installation.state, 'RUNNING'); observed.append('GO')
        def use(app):
            self.assertEqual(observed[-1], 'GO'); observed.append('USE')
        def instance():
            return m.InstanceProcesses(self.cluster, python_sha256='a' * 64, python_size=100,
                                       api_port=58000, challenge=NONCE)
        with patch.object(lifecycle, 'require_setup_readiness'), \
                patch.object(ready, 'require_application_ready', side_effect=ready_pair), \
                patch.object(ready, 'check_before_running', side_effect=check), \
                patch.object(ready, 'activate_application', side_effect=go):
            processes = instance()
            result = Controller(installation, installation, processes, database=installation).create(str(self.root), use)
            self.assertEqual(result['mode'], 'NEW')
            self.assertEqual(observed, ['READY', 'CHECK', 'GO', 'USE'])
            self.assertEqual(self.cluster.events, ['NEW', 'STOP'])
            self.assertEqual(processes.application.adapter.events[-2:], ['STOP:worker', 'STOP:api'])
            installation.events.clear(); observed.clear(); self.cluster.events.clear()
            # A fresh invocation object; reopen never reuses an already consumed adapter.
            processes = instance()
            result = Controller(installation, installation, processes, database=installation).reopen(str(self.root), use)
            self.assertEqual(result['mode'], 'REOPEN')
            self.assertEqual(observed, ['READY', 'CHECK', 'GO', 'USE'])
            self.assertEqual(self.cluster.events, ['REOPEN', 'STOP'])
            self.assertFalse({'prepare_roles', 'creation_support', 'credentials', 'sessions',
                              'create_schema', 'roles', 'seed', 'config'}.intersection(installation.events))


class FrozenEnvironmentChecks(unittest.TestCase):
    def test_actual_launch_builds_only_explicit_project_environment_using_fake_process_ports(self):
        root = Path('/synthetic/private-root')
        lease = SimpleNamespace(_verify=Mock(), status=lambda: 'APPLICATION',
                                fs=SimpleNamespace(base=root.parent, chain=[(None, root.name)]))
        project = (('PARKWEAVE_DSN', DSN), ('PARKWEAVE_MODE', 'LOCAL'), ('PARKWEAVE_FILE_ROOT', str(root / 'files')))
        command = p.Command('runtime/python/python.exe', 'a' * 64, 100, model='WINDOWS_JOB', environment=project)
        captured = []
        backend = SimpleNamespace(preflight=Mock())
        def create(state, register, env, deadline):
            captured.append(dict(env)); register(state)
        backend.create = create
        pin = SimpleNamespace(path=str(root / 'runtime' / 'python' / 'python.exe'))
        with patch.object(p, 'PinnedExecutable', return_value=pin), patch.dict(os.environ, {
                'PARKWEAVE_DSN': 'INHERITED_NOT_ALLOWED', 'PARKWEAVE_MODE': 'LIVE',
                'PARKWEAVE_SERVICE_PROFILE': 'INHERITED_NOT_ALLOWED', 'PGPASSWORD': 'INHERITED_NOT_ALLOWED',
                'PYTHONPATH': 'INHERITED_NOT_ALLOWED', 'PROVIDER_TOKEN': 'INHERITED_NOT_ALLOWED'}):
            adapter = p.PrivateProcessAdapter(lease, {'api': command}, _backend=backend)
            registered = []
            adapter.launch('api', registered.append)
        self.assertEqual(len(registered), 1); self.assertEqual(len(captured), 1)
        self.assertEqual({k: v for k, v in captured[0].items() if k.startswith('PARKWEAVE_')}, dict(project))
        for key in ('PGPASSWORD', 'PYTHONPATH', 'PROVIDER_TOKEN'): self.assertNotIn(key, captured[0])
        wrong = p.Command('runtime/python/python.exe', 'a' * 64, 100, model='WINDOWS_JOB',
                          environment=project[:-1] + (('PARKWEAVE_FILE_ROOT', '/synthetic/elsewhere'),))
        adapter = p.PrivateProcessAdapter(lease, {'api': wrong}, _backend=backend)
        with self.assertRaises(p.ProcessRefused): adapter.launch('api', registered.append)
        self.assertEqual(len(captured), 1)


if __name__ == '__main__': unittest.main()
