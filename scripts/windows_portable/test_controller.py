"""Offline fake adapter tests only. No PG, native proof, secrets, ACL or spawn."""
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from scripts.windows import lifecycle
from . import controller as c


INPUTS = c.DatabaseInputs('fake-maintenance', 'fake-owner', 'fake-app', '/fake/private-data')


class FakeInstallation:
    def __init__(self):
        self.events, self.failures, self.exits = [], {}, {}
        self.state, self.exists = 'NEW', False
        self.cluster, self.app = object(), object()
        self.owner, self.credentials = object(), object()
        self.locks = 0
        self.sessions = {name: 'fake-private-' + name for name in ('fixture-a', 'fixture-b', 'fixture-c')}

    def event(self, name):
        self.events.append(name)
        if name in self.failures:
            raise self.failures[name]

    def claim_fresh(self, root):
        self.event('claim')
        if self.exists:
            raise FileExistsError('fake root already exists')
        self.exists = True; self.locks += 1
        return self

    def open_existing(self, root):
        self.event('open')
        if not self.exists:
            raise FileNotFoundError('fake root absent')
        self.locks += 1
        return self

    def status(self):
        self.event('status'); return self.state

    def checkpoint(self, phase, initialized, runtime):
        self.event('checkpoint:' + phase)
        self.state = phase
        if phase == 'READY_STOPPED':
            assert initialized is True and runtime == 'STOPPED'

    def mark_unknown(self, phase):
        self.event('unknown'); self.state = 'UNKNOWN'

    def release(self):
        self.events.append('release')
        if 'release' in self.failures:
            # Fake safety-adapter contract only, while the fake lease is held.
            self.state = 'UNKNOWN'
            raise self.failures['release']
        self.locks -= 1

    def require_creation_support(self): self.event('creation_support')
    def create_credentials(self, lease): self.event('credentials'); return self.credentials
    def create_sessions_exclusive(self, lease): self.event('sessions'); return self.sessions
    def publish_configuration_exclusive(self, lease, inputs): self.event('config')
    def verify_existing_files(self, lease): self.event('verify_files')
    def load_existing_credentials(self, lease): self.event('load_credentials'); return self.credentials
    def verify_database_binding(self, lease, inputs): self.event('verify_physical_binding')

    def create_cluster(self, lease, credentials, register):
        self.event('create_cluster_before_register')
        register(self.cluster)
        self.event('create_cluster_after_register')
        return INPUTS

    def open_cluster(self, lease, credentials, register):
        self.event('open_cluster')
        register(self.cluster)
        return INPUTS

    def start_application(self, lease, inputs, register):
        self.event('application_before_register')
        register(self.app)
        self.event('application_after_register')
        return object()

    def stop_owned(self, handle):
        assert handle is self.app or handle is self.cluster
        name = 'stop_app' if handle is self.app else 'stop_cluster'
        self.event(name)
        return self.exits.get(name, True)

    def prepare_new(self): self.event('prepare_roles'); return b'fake-frozen-roles'
    def create_schema32(self, inputs): self.event('create_schema'); return self.owner
    def grant_roles(self, owner, prepared): assert owner is self.owner; self.event('roles')
    def seed(self, owner, sessions): assert sessions is self.sessions; self.event('seed')
    def verify_existing(self, inputs): self.event('verify_schema')

    def controller(self):
        return c.Controller(self, self, self, database=self)

    def ready(self):
        self.exists, self.state = True, 'READY_STOPPED'
        return self


class ControllerChecks(unittest.TestCase):
    def setUp(self):
        self.fake = FakeInstallation()
        self.patch = patch.object(lifecycle, 'require_setup_readiness')
        self.gate = self.patch.start(); self.addCleanup(self.patch.stop)

    def create(self, use=lambda app: None):
        return self.fake.controller().create('/fake/private-root', use)

    def reopen(self, use=lambda app: None):
        return self.fake.controller().reopen('/fake/private-root', use)

    def test_original_pause_calls_no_adapter_even_in_cleanup(self):
        self.patch.stop()
        with self.assertRaises(lifecycle.BoundaryError) as failure:
            self.create()
        self.assertEqual(failure.exception.parkweave_lifecycle_reason, 'OWNER_MUTATION_PAUSED')
        self.assertEqual(self.fake.events, [])

    def test_new_order_and_confirmed_exit_separate_from_ready(self):
        result = self.create(lambda app: self.fake.event('use'))
        names = self.fake.events
        expected = ['creation_support', 'prepare_roles', 'claim', 'credentials',
                    'create_cluster_after_register', 'create_schema', 'roles', 'sessions',
                    'seed', 'config', 'verify_files', 'verify_schema', 'verify_physical_binding',
                    'checkpoint:READY', 'application_after_register', 'use',
                    'stop_app', 'stop_cluster', 'checkpoint:READY_STOPPED', 'release']
        self.assertEqual([name for name in names if name in expected], expected)
        self.assertEqual(result, dict(initialization='READY', runtime='STOPPED_CONFIRMED', mode='NEW'))
        self.assertEqual((self.fake.state, self.fake.locks), ('READY_STOPPED', 0))

    def test_same_root_reopen_never_calls_new_consumers_or_mints_anything(self):
        self.create(); self.fake.events.clear(); self.gate.reset_mock()
        result = self.reopen()
        self.assertEqual(result['mode'], 'REOPEN'); self.gate.assert_not_called()
        forbidden = {'prepare_roles', 'creation_support', 'claim', 'credentials', 'sessions',
                     'create_schema', 'create_cluster_before_register', 'roles', 'seed', 'config'}
        self.assertFalse(forbidden.intersection(self.fake.events))
        names = self.fake.events
        expected = ['open', 'verify_files', 'load_credentials', 'open_cluster', 'verify_schema',
                    'verify_physical_binding', 'application_after_register', 'stop_app', 'stop_cluster', 'release']
        self.assertEqual([name for name in names if name in expected], expected)

    def test_partial_unknown_running_or_ready_without_stop_cannot_reopen(self):
        for status in ('NEW', 'CREATE_SCHEMA', 'UNKNOWN', 'RUNNING', 'READY', ''):
            with self.subTest(status=status):
                self.fake = FakeInstallation().ready(); self.fake.state = status
                with self.assertRaises(c.ControlFailure): self.reopen()
                self.assertNotIn('open_cluster', self.fake.events)
                self.assertNotIn('verify_schema', self.fake.events)
                self.assertNotIn('credentials', self.fake.events)

    def test_existing_root_and_missing_root_never_repair_or_overwrite(self):
        self.fake.ready()
        with self.assertRaises(c.ControlFailure) as error: self.create()
        self.assertIsInstance(error.exception.primary, FileExistsError)
        self.assertNotIn('credentials', self.fake.events)
        self.fake = FakeInstallation()
        with self.assertRaises(c.ControlFailure) as error: self.reopen()
        self.assertIsInstance(error.exception.primary, FileNotFoundError)
        self.assertNotIn('release', self.fake.events)

    def test_each_partial_new_failure_retained_unknown_without_retry_or_followups(self):
        actions = ['credentials', 'create_cluster_after_register', 'create_schema', 'roles',
                   'sessions', 'seed', 'config', 'verify_files', 'verify_schema',
                   'verify_physical_binding', 'application_after_register']
        for name in actions:
            with self.subTest(name=name):
                self.fake = FakeInstallation()
                original = RuntimeError('fake-secret-not-for-report')
                self.fake.failures[name] = original
                with self.assertRaises(c.ControlFailure) as failure: self.create()
                self.assertIs(failure.exception.primary, original)
                self.assertEqual(failure.exception.outcome, 'UNKNOWN')
                self.assertEqual(self.fake.state, 'UNKNOWN')
                self.assertNotIn('checkpoint:READY_STOPPED', self.fake.events)
                self.assertEqual(self.fake.events.count(name), 1)
                self.assertNotIn('fake-secret', json.dumps(failure.exception.public()))
                if name == 'sessions': self.assertNotIn('seed', self.fake.events)
                if name == 'create_schema': self.assertNotIn('roles', self.fake.events)
                self.fake.failures.clear(); self.fake.events.clear()
                with self.assertRaises(c.ControlFailure): self.reopen()
                self.assertNotIn('open_cluster', self.fake.events)

    def test_unknown_commit_does_not_grant_seed_or_reissue_on_reopen(self):
        original = ConnectionError('fake COMMIT reply lost')
        self.fake.failures['create_schema'] = original
        with self.assertRaises(c.ControlFailure) as result: self.create()
        self.assertIs(result.exception.primary, original)
        self.assertEqual(result.exception.phase, 'CREATE_SCHEMA')
        self.assertNotIn('roles', self.fake.events); self.assertNotIn('seed', self.fake.events)
        self.fake.failures.clear(); self.fake.events.clear()
        with self.assertRaises(c.ControlFailure): self.reopen()
        self.assertNotIn('open_cluster', self.fake.events)

    def test_sql_rollback_close_chain_and_additional_cleanup_failures_all_retained(self):
        sql, rollback, close = ValueError('private SQL'), OSError('private rollback'), RuntimeError('private close')
        rollback.__context__ = sql; close.__context__ = rollback
        stop, release = OSError('private stop'), OSError('private release')
        self.fake.failures.update(create_schema=close, stop_cluster=stop, release=release)
        with self.assertRaises(c.ControlFailure) as raised: self.create()
        failure = raised.exception
        self.assertIs(failure.surfaced, close); self.assertIs(failure.primary, sql)
        self.assertEqual(failure.causes, (sql, rollback, close))
        self.assertEqual(failure.cleanup_errors, (('STOP_OWNED', stop), ('RELEASE', release)))
        self.assertEqual(failure.outcome, 'UNKNOWN')
        self.assertIs(failure.__cause__, close)
        self.assertNotIn('private ', json.dumps(failure.public()))

    def test_application_start_partial_failure_cleans_registered_groups_in_reverse(self):
        self.fake.failures['application_after_register'] = TimeoutError('fake startup')
        with self.assertRaises(c.ControlFailure): self.create()
        self.assertEqual([n for n in self.fake.events if n.startswith('stop_')], ['stop_app', 'stop_cluster'])
        self.assertEqual(self.fake.state, 'UNKNOWN')

    def test_failure_before_any_registration_never_signals_unknown_handles(self):
        self.fake.failures['create_cluster_before_register'] = TimeoutError('fake startup before registration')
        with self.assertRaises(c.ControlFailure): self.create()
        self.assertFalse(any(n.startswith('stop_') for n in self.fake.events))

    def test_exit_unknown_prevents_success_and_blocks_reopen(self):
        self.fake.exits['stop_app'] = False
        with self.assertRaises(c.ControlFailure) as result: self.create()
        self.assertEqual(result.exception.outcome, 'UNKNOWN')
        self.assertEqual(self.fake.state, 'UNKNOWN')
        self.assertNotIn('checkpoint:READY_STOPPED', self.fake.events)
        self.assertIn('stop_cluster', self.fake.events)

    def test_checkpoint_failure_blocks_action_and_final_state_failure_never_passes(self):
        for phase, forbidden in (('CREATE_SCHEMA', 'create_schema'), ('READY_STOPPED', None)):
            with self.subTest(phase=phase):
                self.fake = FakeInstallation()
                self.fake.failures['checkpoint:' + phase] = OSError('fake state write')
                with self.assertRaises(c.ControlFailure): self.create()
                if forbidden is not None: self.assertNotIn(forbidden, self.fake.events)
                self.assertEqual(self.fake.state, 'UNKNOWN')

    def test_bad_binding_or_missing_existing_secrets_never_starts_application_or_repairs(self):
        for name in ('verify_files', 'load_credentials', 'verify_physical_binding', 'verify_schema'):
            with self.subTest(name=name):
                self.fake = FakeInstallation().ready(); self.fake.failures[name] = PermissionError('fake binding')
                with self.assertRaises(c.ControlFailure): self.reopen()
                self.assertNotIn('application_before_register', self.fake.events)
                self.assertNotIn('credentials', self.fake.events); self.assertNotIn('create_schema', self.fake.events)

    def test_use_failure_cleanup_and_public_report_do_not_leak_private_values(self):
        def use(app): raise ValueError('fake-maintenance fake-owner fake-session')
        with self.assertRaises(c.ControlFailure) as result: self.create(use)
        self.assertIn('stop_app', self.fake.events); self.assertIn('stop_cluster', self.fake.events)
        public = str(result.exception) + json.dumps(result.exception.public()) + repr(INPUTS)
        for secret in ('fake-maintenance', 'fake-owner', 'fake-session', '/fake/private-data'):
            self.assertNotIn(secret, public)

    def test_long_causal_chain_and_cycle_do_not_replace_primary_with_recursion_error(self):
        original = ValueError('private oldest SQL')
        surfaced = original
        for _ in range(2500):
            following = OSError('private cleanup')
            following.__context__ = surfaced
            surfaced = following
        self.fake.failures['create_schema'] = surfaced
        with self.assertRaises(c.ControlFailure) as result: self.create()
        failure = result.exception
        self.assertIs(failure.primary, original)
        self.assertEqual(len(failure.causes), 2501)
        self.assertEqual(len(failure.public()['causes']), 16)
        # Cycles may appear in manually linked adapter failures; keep each
        # original object once without recursion or unbounded public output.
        original.__cause__ = surfaced
        chain = c.exception_chain(surfaced)
        self.assertEqual(len(chain), 2501)
        self.assertIs(chain[0], original)

    def test_exception_group_preserves_all_leaves_and_declared_primary_order(self):
        sql, rollback, close = ValueError('private SQL'), OSError('private rollback'), RuntimeError('private close')
        nested = ExceptionGroup('private nested', [rollback, close])
        group = ExceptionGroup('private group', [sql, nested])
        self.fake.failures['create_schema'] = group
        with self.assertRaises(c.ControlFailure) as result: self.create()
        self.assertEqual(result.exception.causes, (sql, rollback, close, nested, group))
        self.assertIs(result.exception.primary, sql)
        self.assertNotIn('private', json.dumps(result.exception.public()))

    def test_release_unknown_never_attempts_unlocked_journal_write(self):
        self.fake.failures['release'] = OSError('fake release unknown')
        with self.assertRaises(c.ControlFailure) as result: self.create()
        self.assertEqual(result.exception.cleanup_errors[0][0], 'RELEASE')
        self.assertEqual(self.fake.events[-1], 'release')
        self.assertEqual(self.fake.state, 'UNKNOWN')


class NativeConsumerChecks(unittest.TestCase):
    def test_original_roles_hash_and_modified_roles_refusal(self):
        db = c.NativeDatabaseOperations()
        raw = db.prepare_new(); self.assertIn(b'GRANT CONNECT', raw)
        with patch.object(Path, 'read_bytes', return_value=b'changed SQL'):
            with self.assertRaises(c.CandidateRefused): db.prepare_new()

    def test_create_delegates_exact_original_schema_candidate(self):
        with patch('scripts.windows_portable.initialize.create_fresh_native_schema32') as create:
            self.assertIs(c.NativeDatabaseOperations().create_schema32(INPUTS), create.return_value)
            create.assert_called_once_with('fake-maintenance', 'fake-owner', 'fake-app', '/fake/private-data')

    def owner(self):
        from datetime import datetime, timezone
        from uuid import uuid4
        import os
        from parkweave.installed_fixture_receipt import _InstalledSyntheticSetupStore, NativeDatabaseCreationEvidence
        evidence = NativeDatabaseCreationEvidence(1, 'parkweave', 'owner', 'fake-cluster', '/fake',
            datetime.now(timezone.utc), uuid4(), uuid4(), os.getpid())
        return _InstalledSyntheticSetupStore(
            'host=127.0.0.1 port=5432 user=owner dbname=parkweave sslmode=disable',
            'host=127.0.0.1 port=5432 user=parkweave_app dbname=parkweave sslmode=disable', evidence)

    def test_roles_real_unissued_receipt_refused_not_mock_authorized(self):
        from parkweave.store import Denied
        db = c.NativeDatabaseOperations(); owner = self.owner()
        # Native connect checks the live registry after connection; provide only
        # a fake connection so that this real refusal has no network side effect.
        from unittest.mock import Mock
        connection = Mock()
        with patch('parkweave.installed_fixture_receipt._connect', return_value=connection):
            with self.assertRaises(Denied): db.grant_roles(owner, db.prepare_new())
        connection.execute.assert_not_called(); connection.close.assert_called_once()

    def test_actual_schema_consumer_sql_rollback_close_double_fault_chain_is_retained(self):
        from parkweave import installed_fixture_receipt as native
        from .initialize import LOCK_QUERY, VERSION_QUERY
        owner = self.owner()
        sql, rollback, close = ValueError('private SQL'), OSError('private rollback'), RuntimeError('private close')

        class Connection:
            autocommit = False
            def __enter__(self): return self
            def __exit__(self, kind, value, tb):
                try: raise rollback
                finally: raise close
            def execute(self, query):
                if query not in (LOCK_QUERY, VERSION_QUERY): raise sql
                return self
            def fetchone(self): return {'version': 25}

        fake = FakeInstallation()
        controller = fake.controller()
        db = c.NativeDatabaseOperations()
        # Explicitly replace CREATE/25/authorization and transport in the test;
        # the actual extension function and Python exception propagation run.
        with patch.object(lifecycle, 'require_setup_readiness'), \
                patch.object(native, 'create_installed_synthetic_store', return_value=owner), \
                patch.object(type(owner), 'migrate'), \
                patch.object(native.NativeDatabaseCreationEvidence, 'authorize_migration'), \
                patch.object(native, '_connect', return_value=Connection()), \
                patch.object(fake, 'create_schema32', side_effect=lambda inputs: db.create_schema32(inputs)):
            with self.assertRaises(c.ControlFailure) as result:
                controller.create('/fake', lambda app: None)
        failure = result.exception
        self.assertIs(failure.surfaced, close)
        self.assertEqual(failure.causes, (sql, rollback, close))
        self.assertIs(failure.primary, sql)
        self.assertEqual(failure.outcome, 'UNKNOWN')
        self.assertNotIn('roles', fake.events); self.assertIn('stop_cluster', fake.events)

    def test_roles_exact_bytes_and_schema32_before_grants_offline_seam(self):
        db = c.NativeDatabaseOperations(); owner = self.owner()
        from unittest.mock import MagicMock
        connection = MagicMock(); connection.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = {'version': 32}
        with patch.object(type(owner), 'connect', return_value=connection):
            raw = db.prepare_new(); db.grant_roles(owner, raw)
            self.assertEqual(connection.execute.call_args_list[-1].args, (raw.decode(),))
            connection.reset_mock()
            connection.execute.return_value.fetchone.return_value = {'version': 25}
            with self.assertRaises(c.CandidateRefused): db.grant_roles(owner, raw)
            self.assertEqual(connection.execute.call_count, 1)
            connection.reset_mock()
            with self.assertRaises(c.CandidateRefused): db.grant_roles(owner, raw + b'changed')
            connection.execute.assert_not_called()

    def test_seed_uses_original_store_with_exact_distinct_sessions_only(self):
        from parkweave.store import Store
        db = c.NativeDatabaseOperations(); owner = self.owner(); identities = FakeInstallation().sessions
        with patch.object(Store, 'seed') as seed:
            db.seed(owner, identities); seed.assert_called_once_with(owner, identities)
            for bad in ({}, {'fixture-a': 'x'}, {n: 'same' for n in identities}):
                with self.assertRaises(c.CandidateRefused): db.seed(owner, bad)
            seed.assert_called_once()

    def test_reopen_queries_are_read_only_app_connections_no_receipt_or_owner(self):
        from unittest.mock import MagicMock
        from parkweave import installed_fixture_receipt as native
        inputs = c.DatabaseInputs('must-not-use', 'must-not-use',
            'host=127.0.0.1 port=5432 user=parkweave_app dbname=parkweave sslmode=disable', '/fake')
        connections = [MagicMock(), MagicMock()]
        for conn in connections:
            conn.__enter__.return_value = conn
            conn.execute.return_value.fetchone.return_value = {'version': 32}
        def role_check(dsn, *, app, connector):
            self.assertTrue(app)
            with connector(): pass
        with patch.object(native, '_connect', side_effect=connections) as connect, \
                patch.object(lifecycle, 'check_dsn_scope', side_effect=role_check), \
                patch.object(native, 'create_installed_synthetic_store', side_effect=AssertionError('CREATE')), \
                patch.object(native.NativeDatabaseCreationEvidence, 'authorize_migration', side_effect=AssertionError('proof')):
            c.NativeDatabaseOperations().verify_existing(inputs)
        for conn in connections:
            self.assertEqual(conn.execute.call_args_list[0].args, ('SET TRANSACTION READ ONLY',))
        self.assertEqual(connect.call_count, 2)
        for call in connect.call_args_list:
            self.assertEqual(call.args[0]['user'], 'parkweave_app')
            self.assertFalse(call.kwargs['autocommit'])


if __name__ == '__main__': unittest.main()
