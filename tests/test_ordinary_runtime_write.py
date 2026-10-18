"""Pure offline wiring tests, not writer authorization/IPC/PG acceptance.

Only protected host reads/bind_api and the RPC endpoint are replaced. Original
scope, public Client, validation and Native command/activation routing run.
No fixture issuer, key, database, service, installation or assignment is created.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient
from parkweave import api, native_run_access as native
from parkweave import native_run_access_writer as writer
from parkweave import native_run_access_restricted_host as host
from parkweave import ordinary_runtime_read as read, ordinary_runtime_write as write
from parkweave.domain import Intake
from parkweave.native_run_access_activation import Activate
from parkweave.store import Store, Denied, Conflict, digest

RUN, CASE, PREP = [UUID('00000000-0000-4000-8000-%012d' % x) for x in (1, 2, 3)]
LEASE = UUID('00000000-0000-4000-8000-000000000004')
NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


class MemoryConnection:
    """SELECT-only rows, never an SQL engine or business-authority simulation."""
    def __init__(self, h):
        self.h, self.info, self.row = h, SimpleNamespace(host='127.0.0.1', port=5432), None
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, sql, params=None):
        self.h.sql.append(sql)
        if sql.startswith('SET '):self.row = None
        elif 'pg_get_userbyid(d.datdba)' in sql:
            self.row = dict(database_name='offline-example', database_oid=10, database_owner='owner',
                            database_role='app', started=NOW)
        elif 'FROM pg_roles WHERE rolname=current_user' in sql:
            self.row = dict(rolsuper=self.h.admin, rolcreaterole=False, rolcreatedb=False)
        elif sql == 'SELECT current_schemas(true) value':self.row = {'value': ['pg_catalog', 'public']}
        elif 'SELECT native_run_access_protocol,native_run_access_activation' in sql:
            self.row = dict(native_run_access_protocol=None, native_run_access_activation=None)
        elif 'FROM principals WHERE token_hash=' in sql:self.row = None
        elif 'FROM preparations WHERE id=' in sql:self.row = deepcopy(self.h.parent)
        elif 'FROM runs WHERE id=' in sql:self.row = deepcopy(self.h.run)
        elif 'FROM preparation_catalog WHERE' in sql:self.row = deepcopy(self.h.catalog)
        elif 'FROM operations WHERE' in sql:self.row = deepcopy(self.h.operation)
        elif 'FROM cases WHERE' in sql:self.row = deepcopy(self.h.case)
        elif 'FROM preparation_evidence' in sql:self.row = []
        else:raise AssertionError('unexpected/offline non-read SQL: ' + sql)
        return self
    def fetchone(self):return self.row
    def fetchall(self):return self.row


class Harness:
    def __init__(self):
        self.sql, self.calls = [], []
        self.admin, self.refusal = False, None
        self.lock = Lock()
        self.store = Store('OFFLINE_NOT_A_DSN')
        self.parent = dict(id=PREP, run_id=RUN, case_id=CASE, owner_id='enterprise', park_id='park', org_id='org',
                           service_id='synthetic-material-preparation', service_version=1, namespace='SYNTHETIC',
                           state='LOCAL_CONFIRMED', revision=5, review_sha256='c'*64)
        intake = Intake(goal='SYNTHETIC offline source').model_dump(mode='json')
        self.run = dict(id=RUN, input=intake, fingerprint=digest(json.dumps(intake, sort_keys=True, ensure_ascii=False)),
                        principal_id='enterprise', park_id='park', org_id='org', namespace='SYNTHETIC',
                        state='SUCCEEDED', success_scope='LOCAL_CASE_CREATED', revision=2)
        self.case = dict(id=CASE, source='SYNTHETIC', park_id='park', org_id='org', state='NEEDS_INPUT')
        self.operation = dict(action='case.create', state='VERIFIED', receipt=dict(case_id=str(CASE),
                              source='LOCAL_DATABASE', verified=True, success_scope='LOCAL_CASE_CREATED'))
        self.catalog = dict(service_id=self.parent['service_id'], version=1, name='SYNTHETIC',
                            source={'kind':'SYNTHETIC'}, namespace='SYNTHETIC', qualification='NOT_EVALUATED', row_generation='10')
        # Use the original preparation snapshot canonicalization, not a fixture permit.
        from parkweave.preparation import snapshot
        self.parent['review_sha256'] = snapshot(self.parent, [])
        source = dict(run_id=str(RUN), run_revision=2, input_fingerprint=self.run['fingerprint'], owner_id='enterprise',
                      park_id='park', org_id='org', preparation_id=str(PREP), preparation_revision=5,
                      preparation_state='LOCAL_CONFIRMED', review_sha256=self.parent['review_sha256'],
                      material_sha256=self.parent['review_sha256'], case_id=str(CASE))
        self.policy = dict(scheme=writer.SCHEME, environment='PRODUCTION',
            policy_id='00000000-0000-4000-8000-000000000005', revision=1,
            owner_id='enterprise', approver_id='specialist', beneficiary_id='executor',
            approver_actions=['APPROVE','REJECT','REVOKE'], capability='READ', max_access_seconds=3600,
            valid_from=(NOW-timedelta(minutes=1)).isoformat(), valid_until=(NOW+timedelta(minutes=30)).isoformat(),
            source=source, generations={}, database_name='offline-example', database_oid=10,
            system_identifier='offline-system', database_host='127.0.0.1', database_port=5432,
            application_role='app', writer_role='writer')
        self.policy = writer.WriterPolicy.model_validate(self.policy).model_dump()
        self.pin = dict(command_path='/offline/command.sock', verify_path='/offline/verify.sock',
            command_device=1, command_inode=2, verify_device=1, verify_inode=3, pid=99, uid=1001,
            process_started='offline', boot_id='offline', policy_sha256=writer._sha(self.policy))
        self.public = dict(schema='parkweave-restricted-api-binding/1', policy=self.policy, pin=self.pin,
                           api_uid=1000, api_gid=1000, ipc_gid=1001, source_sha='a'*40)
        self.binding = dict(schema_version='parkweave-ordinary-runtime-write-binding/1',
            binding_path='/offline/host.json', binding_sha256='b'*64,
            preparation_id=str(PREP), case_id=str(CASE), run_id=str(RUN), service_id=self.parent['service_id'],
            service_version=1, catalog_sha256=read.catalog_hash({k:v for k,v in self.catalog.items() if k!='row_generation'}),
            catalog_generation='10', operations=['COMMAND','ACTIVATE'])
        self.cfg = dict(schema_version='parkweave-ordinary-runtime-write/1',
                        binding_path='/offline/write.json', binding_sha256='a'*64)
        self.raw_binding, self.raw_public = None, None
        self.stack = ExitStack()
    def protected(self, path, owner, *, expected, limit=host.MAX_PRIVATE, **kwargs):
        assert owner == 0
        if path == '/offline/write.json':
            assert expected == 'a'*64 and limit == write.LIMIT
            return self.raw_binding if self.raw_binding is not None else json.dumps(self.binding).encode()
        assert (path, expected) == ('/offline/host.json', 'b'*64)
        return self.raw_public if self.raw_public is not None else json.dumps(self.public).encode()
    def bind(self, store, path, sha, *, read_only):
        assert (path, sha, read_only) == ('/offline/host.json', 'b'*64, False)
        bridge = native.NativeRunAccess(store, writer=writer.WriterClient(store, self.policy, self.pin))
        store._native_run_access = bridge
        return bridge
    def rpc(self, client, operation, **data):
        with self.lock:self.calls.append((operation, deepcopy(data)))
        if self.refusal:raise self.refusal
        if operation == 'VALIDATE':return dict(database_name='offline-example', database_oid=10,
                                               system_identifier='offline-system', started=NOW.isoformat())
        if operation == 'VERIFY':return True
        return dict(scope='OFFLINE_RPC_STUB_ONLY', operation=operation, key=data['request_key'], command=data['command'])
    def __enter__(self):
        self.stack.enter_context(patch.object(Store, '_guarded_connect', lambda store: MemoryConnection(self)))
        self.stack.enter_context(patch.object(host, '_protected_bytes', self.protected))
        self.stack.enter_context(patch.object(host, 'bind_api', self.bind))
        self.stack.enter_context(patch.object(writer.WriterClient, 'rpc', lambda client, op, **data:self.rpc(client,op,**data)))
        self.stack.enter_context(patch('psycopg.connect', side_effect=AssertionError('database forbidden')))
        self.stack.enter_context(patch.dict('os.environ', {'PARKWEAVE_DSN':'OFFLINE_NOT_A_DSN', 'PARKWEAVE_MODE':'LOCAL'}, clear=True))
        return self
    def __exit__(self, *args):return self.stack.__exit__(*args)
    def configure(self):return write.configure(self.store, json.dumps(self.cfg))
    def command(self, action='CANCEL'):
        interval=dict(valid_from=NOW.isoformat(), valid_until=(NOW+timedelta(minutes=5)).isoformat(), timezone='UTC')
        extra = (dict(target_id='executor', target_role='service_executor', capability='READ',
                      requested_validity=interval, confirm_request=True) if action=='REQUEST' else
                 dict(approved_validity=interval) if action=='APPROVE' else {})
        return native.RunCommand(action=action, expected_revision=1, expected_run_revision=2,
                                 expected_authority_sha256='d'*64, reason='SYNTHETIC offline routing', **extra)
    def activation(self):
        return Activate(action='ACTIVATE', lease_id=LEASE, expected_revision=1, expected_run_revision=2,
                        expected_activation_revision=0, expected_authority_sha256='d'*64,
                        activation_policy_sha256='e'*64, confirm_activate=True, reason='SYNTHETIC offline routing')


class OrdinaryWriteTests(TestCase):
    def test_absent_config_has_no_effect_or_io(self):
        with patch.object(host,'bind_api',side_effect=AssertionError('host forbidden')), patch('psycopg.connect',side_effect=AssertionError('database forbidden')):
            s=Store('OFFLINE');self.assertIsNone(write.configure(s,None));self.assertFalse(hasattr(s,'_native_run_access'))
            with patch.dict('os.environ', {'PARKWEAVE_DSN':'OFFLINE'}, clear=True):
                self.assertIsInstance(api.configured_app(), api.FastAPI)
    def test_invalid_environment_never_reaches_host(self):
        with Harness() as h:
            for raw in ['', '[', json.dumps({**h.cfg,'writer_dsn':'PRIVATE_SENTINEL'}), json.dumps({**h.cfg,'binding_path':'relative'}), json.dumps({**h.cfg,'binding_sha256':True}), json.dumps({**h.cfg,'schema_version':'parkweave-ordinary-runtime-read/1'}), json.dumps(h.cfg)[:-1]+',"binding_sha256":"b"}', 'x'*16385]:
                with self.subTest(raw=raw[:15]), patch.object(host,'_protected_bytes',side_effect=AssertionError('host forbidden')):
                    with self.assertRaises(Denied) as caught:write.configure(h.store,raw)
                    self.assertNotIn('PRIVATE_SENTINEL',str(caught.exception))
                    self.assertFalse(hasattr(h.store,'_native_run_access'))
    def test_read_write_conflict_even_empty_values_precedes_store_and_host(self):
        with patch.dict('os.environ', {'PARKWEAVE_RUNTIME_READ_CONFIG':'','PARKWEAVE_RUNTIME_WRITE_CONFIG':''}, clear=True), patch.object(api,'Store',side_effect=AssertionError('store forbidden')):
            with self.assertRaises(Denied):api.configured_app()
    def test_actual_unprotected_file_is_not_startup_authority(self):
        with TemporaryDirectory(prefix='pw-write-offline-') as folder:
            p=Path(folder)/'public.json';raw=b'{"synthetic":"offline"}';p.write_bytes(raw)
            cfg=dict(schema_version='parkweave-ordinary-runtime-write/1',binding_path=str(p),binding_sha256=sha256(raw).hexdigest())
            with patch.object(host,'bind_api',side_effect=AssertionError('binder forbidden')), patch('psycopg.connect',side_effect=AssertionError('database forbidden')):
                with self.assertRaises(Denied):write.configure(Store('OFFLINE'),json.dumps(cfg))
    def test_factory_routes_original_commands_and_activation_without_provisioning(self):
        with Harness() as h, patch.dict('os.environ', {'PARKWEAVE_RUNTIME_WRITE_CONFIG':json.dumps(h.cfg)}):
            with TestClient(api.configured_app()) as client:
                for model,path in [(h.command('REQUEST'),'/access/commands'), (h.command('APPROVE'),'/access/commands'), (h.activation(),'/access/activate')]:
                    response=client.post('/api/runs/'+str(RUN)+path,headers={'Authorization':'Bearer OFFLINE_NOT_A_SESSION','Idempotency-Key':'original-key'},json=model.model_dump(mode='json'))
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(response.json()['key'],'original-key')
                    self.assertEqual(response.json()['command'],model.model_dump(mode='json'))
            self.assertEqual([op for op,_ in h.calls if op in ('COMMAND','ACTIVATE')],['COMMAND','COMMAND','ACTIVATE'])
            self.assertTrue(all(sql.startswith(('SELECT ','SET ')) for sql in h.sql))
    def test_bad_protected_record_shape_operations_and_duplicates_refuse(self):
        with Harness() as h:
            for change in [{'operations':['COMMAND']},{'operations':['COMMAND','ACTIVATE','ACTIVATE']},{'operations':['SIGN','ACTIVATE']},{'writer_key':'PRIVATE_SENTINEL'},{'service_version':True}]:
                with self.subTest(change=change):
                    h.raw_binding=json.dumps({**h.binding,**change}).encode()
                    with self.assertRaises(Denied):h.configure()
                    self.assertFalse(hasattr(h.store,'_native_run_access'))
            h.raw_binding=json.dumps(h.binding)[:-1].encode()+b',"operations":["COMMAND","ACTIVATE"]}'
            with self.assertRaises(Denied):h.configure()
    def test_inner_public_duplicate_or_foreign_policy_pin_refuses(self):
        with Harness() as h:
            for raw in [json.dumps(h.public)[:-1]+',"schema":"parkweave-restricted-api-binding/1"}',json.dumps({**h.public,'extra':1}),json.dumps({**h.public,'policy':{**h.policy,'revision':2}}),json.dumps({**h.public,'pin':{**h.pin,'boot_id':'changed'}})]:
                with self.subTest(raw=raw[-30:]):
                    h.raw_public=raw.encode()
                    with self.assertRaises(Denied):h.configure()
                    self.assertFalse(hasattr(h.store,'_native_run_access'))
    def test_missing_protected_pin_and_non_linux_refuse(self):
        with Harness() as h:
            with patch.object(host,'_protected_bytes',side_effect=OSError('PRIVATE_SENTINEL')):
                with self.assertRaises(Denied) as caught:h.configure()
                self.assertNotIn('PRIVATE_SENTINEL',str(caught.exception))
            with patch.object(write.sys,'platform','win32'):
                with self.assertRaises(Denied):h.configure()
    def test_no_reference_test_permit_private_context_or_readonly_upgrade(self):
        with Harness() as h:
            original=h.bind
            for damage in ['reference','decision','activation','context','readonly','read-binding']:
                def bad(store,path,sha,*,read_only):
                    b=original(store,path,sha,read_only=read_only)
                    if damage=='reference':
                        policy={**h.policy,'environment':'OWNED_SYNTHETIC_REFERENCE','database_name':'fixture_'+'a'*32}
                        b.writer=writer.WriterClient(store,policy,{**h.pin,'policy_sha256':writer._sha(policy)})
                    elif damage=='decision':b.test_permit=object()
                    elif damage=='activation':b.activation_permit=object()
                    elif damage=='context':b.writer=object.__new__(writer.WriterContext)
                    elif damage=='readonly':b.read_only=True
                    else:b.runtime_read_binding='{}'
                    return b
                with self.subTest(damage=damage), patch.object(host,'bind_api',bad):
                    with self.assertRaises(Denied):h.configure()
                    self.assertFalse(hasattr(h.store,'_native_run_access'))
    def test_failed_start_preserves_preexisting_bridge_and_default_closed(self):
        with Harness() as h:
            previous=native.NativeRunAccess(h.store);h.store._native_run_access=previous
            with self.assertRaises(Denied):h.configure()
            self.assertIs(h.store._native_run_access,previous)
            with self.assertRaises(Denied):previous.command('OFFLINE',RUN,'key',h.command())
            with self.assertRaises(Denied):previous.activate('OFFLINE',RUN,'key',h.activation())
    def test_admin_application_role_refuses_and_rolls_back_binding(self):
        with Harness() as h:
            h.admin=True
            with self.assertRaises(Denied):h.configure()
            self.assertFalse(hasattr(h.store,'_native_run_access'))
    def test_unexpected_startup_error_and_interruption_clean_only_own_bridge(self):
        for error in [RuntimeError('offline'),AttributeError('offline'),KeyboardInterrupt()]:
            with self.subTest(error=type(error).__name__), Harness() as h:
                with patch.object(write,'before_invoke',side_effect=error):
                    with self.assertRaises(type(error)):h.configure()
                self.assertFalse(hasattr(h.store,'_native_run_access'))
        with Harness() as h:
            replacement=object()
            def interrupted(*args):
                h.store._native_run_access=replacement
                raise RuntimeError('unrelated replacement must remain')
            with patch.object(write,'before_invoke',interrupted):
                with self.assertRaises(RuntimeError):h.configure()
            self.assertIs(h.store._native_run_access,replacement)
    def test_exact_scope_catalog_generation_and_original_source_proof(self):
        for damage in ['case','run','service','version','catalog','generation','owner','receipt']:
            with self.subTest(damage=damage), Harness() as h:
                if damage in ('case','run'):h.binding[damage+'_id']=str(LEASE)
                elif damage=='service':h.binding['service_id']='other'
                elif damage=='version':h.binding['service_version']=2
                elif damage=='catalog':h.catalog['source']['kind']='UNVERIFIED'
                elif damage=='generation':h.catalog['row_generation']='11'
                elif damage=='owner':h.parent['owner_id']='other'
                else:h.operation['receipt']['verified']=False
                with self.assertRaises(Denied):h.configure()
                self.assertFalse(hasattr(h.store,'_native_run_access'))
    def test_expiry_revocation_missing_permission_from_existing_rpc_are_not_fallback(self):
        for reason in ['EXPIRED','REVOKED','MISSING_PERMISSION']:
            with self.subTest(reason=reason), Harness() as h:
                b=h.configure();h.calls.clear();h.refusal=Denied(reason)
                with self.assertRaises(Denied):b.command('OFFLINE',RUN,'same-key',h.command())
                self.assertFalse(any(op=='COMMAND' for op,_ in h.calls))
    def test_endpoint_replay_conflict_and_unknown_result_never_retry(self):
        for error in [Conflict('REPLAY_CONFLICT'),Denied('UNKNOWN_RESULT')]:
            with self.subTest(error=type(error).__name__), Harness() as h:
                b=h.configure();original=h.rpc
                def endpoint(client,operation,**data):
                    if operation=='COMMAND':
                        h.calls.append((operation,data));raise error
                    return original(client,operation,**data)
                with patch.object(writer.WriterClient,'rpc',endpoint):
                    with self.assertRaises(type(error)):b.command('OFFLINE',RUN,'same-key',h.command())
                self.assertEqual(sum(op=='COMMAND' for op,_ in h.calls),1)
    def test_changed_binding_refuses_explicit_replay_instead_of_caching_success(self):
        with Harness() as h:
            b=h.configure();b.command('OFFLINE',RUN,'same-key',h.command());h.calls.clear()
            h.binding['catalog_generation']='11'
            with self.assertRaises(Denied):b.command('OFFLINE',RUN,'same-key',h.command())
            self.assertFalse(any(op=='COMMAND' for op,_ in h.calls))
    def test_managed_assignment_gate_uses_same_connection_and_rechecks_scope(self):
        with Harness() as h:
            b=h.configure();h.binding['catalog_generation']='11'
            with patch.object(Store,'_guarded_connect',side_effect=AssertionError('no nested connection')), patch('parkweave.native_run_access_activation.effective',side_effect=AssertionError('invalid scope cannot reach effective')):
                self.assertFalse(b.assignment_allowed(MemoryConnection(h),{},RUN,{}))
    def test_old_readonly_bridge_and_unsupported_operation_stay_closed(self):
        with Harness() as h:
            b=h.configure();b.read_only=True
            with self.assertRaises(Denied):b.command('OFFLINE',RUN,'key',h.command())
            with self.assertRaises(Denied):b.activate('OFFLINE',RUN,'key',h.activation())
            b.read_only=False
            with self.assertRaises(Denied):write.before_invoke(b,'SIGN',RUN)
    def test_existing_read_scope_wrapper_keeps_exact_readonly_contract(self):
        with Harness() as h:
            b=h.configure();del b.runtime_write_binding;b.read_only=True
            fields={k:v for k,v in h.binding.items() if k!='operations'}
            fields['schema_version']='parkweave-ordinary-runtime-read/1'
            b.runtime_read_binding=read.ReadConfig.model_validate(fields).model_dump_json()
            self.assertEqual(read.check_binding(b,MemoryConnection(h),RUN).run_id,RUN)
            b.read_only=False
            with self.assertRaises(Denied):read.check_binding(b,MemoryConnection(h),RUN)
    def test_concurrent_revoked_binding_blocks_delayed_call_before_endpoint(self):
        with Harness() as h:
            b=h.configure();entered=Event();release=Event();original=h.protected
            def delayed(path,*args,**kwargs):
                if path=='/offline/write.json' and not entered.is_set():
                    entered.set();self.assertTrue(release.wait(3))
                return original(path,*args,**kwargs)
            with patch.object(host,'_protected_bytes',delayed), ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(b.command,'OFFLINE',RUN,'delayed-key',h.command())
                self.assertTrue(entered.wait(3));h.binding['catalog_generation']='11';h.calls.clear();release.set()
                with self.assertRaises(Denied):future.result(timeout=3)
            self.assertFalse(any(op=='COMMAND' for op,_ in h.calls))
    def test_concurrent_calls_preserve_independent_keys_bodies_and_original_replay(self):
        with Harness() as h:
            b=h.configure()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda key:b.command('OFFLINE',RUN,key,h.command()),['first-key','second-key']))
            self.assertEqual({x['key'] for x in results},{'first-key','second-key'})
            self.assertEqual(b.command('OFFLINE',RUN,'first-key',h.command()),results[0])


if __name__=='__main__':main(verbosity=2)
