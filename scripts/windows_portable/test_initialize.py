"""Offline control-flow/transaction seams, NOT native migration acceptance.

The positive seam patches the original pause, CREATE, migration and issuer
authorization. No proof is issued and no database or Windows process is run.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import builtins
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from scripts.windows import lifecycle
from . import initialize as candidate


class SchemaChecks(unittest.TestCase):
    def test_original_pause_precedes_dependency_import_and_file_or_database_work(self):
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.startswith(('parkweave', 'psycopg')):
                self.fail('heavy dependency imported before original pause')
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=guarded_import), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('file IO before pause')):
            with self.assertRaises(lifecycle.BoundaryError) as result:
                candidate.create_fresh_native_schema32(None, None, None, None)
        self.assertEqual(result.exception.parkweave_lifecycle_reason, 'OWNER_MUTATION_PAUSED')

    def seam(self, *, initial=25, fail_at=None, wrong_at=None, autocommit=False,
             commit_failure=None):
        from parkweave import installed_fixture_receipt as native
        from parkweave.store import Denied
        stack = ExitStack(); self.addCleanup(stack.close)
        events = []
        sql_versions = {
            Path(native.__file__).with_name(f'migration-{v:03}.sql').read_text(): v
            for v, _ in candidate.MIGRATIONS
        }

        class Connection:
            def __init__(self):
                self.autocommit = autocommit
                self.committed = initial
                self.pending = initial
                self.closed = False

            def __enter__(self):
                events.append('enter'); return self

            def __exit__(self, kind, value, tb):
                try:
                    if kind is None:
                        if commit_failure == 'before':
                            raise ConnectionError('COMMIT result UNKNOWN')
                        self.committed = self.pending; events.append('commit')
                        if commit_failure == 'after':
                            raise ConnectionError('COMMIT result UNKNOWN')
                    else:
                        self.pending = self.committed; events.append('rollback')
                finally:
                    self.close()

            def close(self):
                self.closed = True; events.append('close')

            def execute(self, sql):
                if sql == candidate.LOCK_QUERY:
                    events.append('lock')
                elif sql == candidate.VERSION_QUERY:
                    events.append(('read', self.pending))
                else:
                    version = sql_versions[sql]
                    events.append(('sql', version))
                    if version == fail_at:
                        raise RuntimeError('injected SQL failure')
                    self.pending = version - 1 if version == wrong_at else version
                return self

            def fetchone(self):
                return {'version': self.pending}

        connection = Connection()
        receipt = native.NativeDatabaseCreationEvidence(
            1, 'parkweave', 'owner', 'fake-static-identity', '/offline/not-a-cluster',
            datetime.now(timezone.utc), uuid4(), uuid4(), os.getpid())
        owner = native._InstalledSyntheticSetupStore(
            'host=127.0.0.1 port=5432 user=owner dbname=parkweave sslmode=disable',
            'host=127.0.0.1 port=5432 user=parkweave_app dbname=parkweave sslmode=disable', receipt)
        factory = stack.enter_context(patch.object(native, 'create_installed_synthetic_store', return_value=owner))
        migrate = stack.enter_context(patch.object(native._InstalledSyntheticSetupStore, 'migrate',
                                                  side_effect=lambda: events.append('committed_original_25')))
        stack.enter_context(patch.object(native, '_connect', return_value=connection))
        stack.enter_context(patch.object(lifecycle, 'require_setup_readiness'))
        return native, Denied, owner, receipt, connection, events, factory, migrate, stack

    def authorize(self, stack, native, receipt, connection, events):
        def check(actual, c):
            self.assertIs(actual, receipt); self.assertIs(c, connection)
            events.append('authorize_original_class_seam')
        return stack.enter_context(patch.object(native.NativeDatabaseCreationEvidence,
                                                'authorize_migration', side_effect=check))

    def run_candidate(self):
        return candidate.create_fresh_native_schema32('maintenance', 'owner', 'application', '/offline')

    def test_exact_sql_order_original_class_authorization_and_single_commit(self):
        native, _, owner, receipt, c, events, factory, migrate, stack = self.seam()
        auth = self.authorize(stack, native, receipt, c, events)
        self.assertIs(self.run_candidate(), owner)
        factory.assert_called_once_with('maintenance', 'owner', 'application', '/offline')
        migrate.assert_called_once_with()
        self.assertEqual(auth.call_count, 9)  # connect + pre-lock + each original SQL
        self.assertEqual([x for x in events if isinstance(x, tuple) and x[0] == 'sql'],
                         [('sql', v) for v in range(26, 33)])
        self.assertLess(events.index('lock'), events.index(('read', 25)))
        for v in range(26, 33):
            index = events.index(('sql', v))
            self.assertEqual(events[index - 1], 'authorize_original_class_seam')
            self.assertEqual(events[index + 1], ('read', v))
        self.assertEqual((c.committed, c.closed, events[-2:]), (32, True, ['commit', 'close']))

    def test_unissued_or_copied_receipt_uses_real_registry_refusal_before_extension(self):
        _, denied, _, _, c, events, factory, _, _ = self.seam()
        with self.assertRaisesRegex(denied, 'issued installed database creation evidence required'):
            self.run_candidate()
        self.assertFalse(any(isinstance(x, tuple) and x[0] == 'sql' for x in events))
        self.assertEqual(c.committed, 25); self.assertTrue(c.closed)
        factory.assert_called_once()

    def test_wrong_starting_version_refused_without_any_extension_or_retry(self):
        for version in (24, 26, 32, None, True, '25'):
            with self.subTest(version=version):
                native, denied, _, receipt, c, events, factory, _, stack = self.seam(initial=version)
                self.authorize(stack, native, receipt, c, events)
                with self.assertRaisesRegex(denied, 'exact schema version refused'):
                    self.run_candidate()
                self.assertNotIn(('sql', 26), events)
                self.assertIn('rollback', events); self.assertTrue(c.closed)
                self.assertEqual(c.committed, version); factory.assert_called_once()
                stack.close()

    def test_sql_failure_rolls_back_all_extensions_but_preserves_original_25(self):
        for failed in range(26, 33):
            with self.subTest(failed=failed):
                native, _, _, receipt, c, events, factory, _, stack = self.seam(fail_at=failed)
                self.authorize(stack, native, receipt, c, events)
                with self.assertRaisesRegex(RuntimeError, 'injected SQL failure'):
                    self.run_candidate()
                self.assertEqual((c.committed, c.pending, c.closed), (25, 25, True))
                self.assertNotIn('commit', events); self.assertIn('rollback', events)
                self.assertNotIn(('sql', failed + 1), events); factory.assert_called_once()
                stack.close()

    def test_wrong_increment_refuses_commit_even_at_final_version(self):
        for wrong in (26, 29, 32):
            with self.subTest(wrong=wrong):
                native, denied, _, receipt, c, events, _, _, stack = self.seam(wrong_at=wrong)
                self.authorize(stack, native, receipt, c, events)
                with self.assertRaisesRegex(denied, 'exact schema version refused'):
                    self.run_candidate()
                self.assertEqual(c.committed, 25); self.assertIn('rollback', events)
                stack.close()

    def test_commit_failure_preserves_unknown_error_without_retry_or_claimed_rollback(self):
        for mode, possible_version in (('before', 25), ('after', 32)):
            with self.subTest(mode=mode):
                native, _, _, receipt, c, events, factory, _, stack = self.seam(commit_failure=mode)
                self.authorize(stack, native, receipt, c, events)
                with self.assertRaisesRegex(ConnectionError, 'COMMIT result UNKNOWN'):
                    self.run_candidate()
                factory.assert_called_once(); self.assertTrue(c.closed)
                self.assertEqual(c.committed, possible_version)
                self.assertNotIn('rollback', events)
                stack.close()

    def test_autocommit_refused_before_sql(self):
        native, denied, _, receipt, c, events, _, _, stack = self.seam(autocommit=True)
        self.authorize(stack, native, receipt, c, events)
        with self.assertRaisesRegex(denied, 'explicit owner migration transaction required'):
            self.run_candidate()
        self.assertNotIn('lock', events); self.assertIn('rollback', events)

    def test_wrong_store_or_evidence_exact_type_refused_before_migrate(self):
        for mode in ('store', 'receipt', 'subclass'):
            with self.subTest(mode=mode):
                native, denied, owner, receipt, _, _, factory, migrate, stack = self.seam()
                if mode == 'store':
                    factory.return_value = object()
                elif mode == 'receipt':
                    owner._case_fact_fixture_receipt = object()
                else:
                    class Subclass(native.NativeDatabaseCreationEvidence):
                        pass
                    owner._case_fact_fixture_receipt = Subclass(**receipt.__dict__)
                with self.assertRaisesRegex(denied, 'exact native creation store'):
                    self.run_candidate()
                migrate.assert_not_called(); stack.close()

    def test_any_migration_hash_drift_refused_before_create(self):
        native, denied, _, _, _, _, factory, migrate, _ = self.seam()
        original = Path.read_bytes
        for drift in range(26, 33):
            with self.subTest(drift=drift):
                def read(path):
                    return b'changed' if path.name == f'migration-{drift:03}.sql' else original(path)
                with patch.object(Path, 'read_bytes', read):
                    with self.assertRaisesRegex(denied, 'source integrity refused'):
                        self.run_candidate()
        factory.assert_not_called(); migrate.assert_not_called()

    def test_unknown_create_and_original_migration_failure_not_retried_or_hidden(self):
        for at in ('create', 'original_migration'):
            with self.subTest(at=at):
                _, _, _, _, _, events, factory, migrate, stack = self.seam()
                error = RuntimeError('injected unknown outcome')
                (factory if at == 'create' else migrate).side_effect = error
                with self.assertRaises(RuntimeError) as raised:
                    self.run_candidate()
                self.assertIs(raised.exception, error)
                factory.assert_called_once(); self.assertNotIn('enter', events)
                stack.close()


if __name__ == '__main__':
    unittest.main()
