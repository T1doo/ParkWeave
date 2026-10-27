"""Pure synthetic installer flow: no actual DB, FD, process or permission write."""
from contextlib import ExitStack,contextmanager
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace
from unittest import TestCase,main
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import psycopg
from psycopg.pq import TransactionStatus
from parkweave import native_run_access_installer as installer
from parkweave import native_run_access_preflight as preflight
from parkweave import native_run_access_restricted_host as host
from parkweave import native_run_access_restricted_runtime as runtime
from parkweave import native_run_access_writer as writer
from parkweave.store import Denied
import test_installed_writer_launch as support


def snapshots():
    spec,catalog,layout,private,receipt=support.inputs()
    catalog['database'].update(session_user=spec['installer_role'],current_user=spec['installer_role'])
    catalog['privileges']['writer:SELECT:schema_version:']=True
    post=dict(catalog=catalog,extra_acl={key:False for key in runtime.EXTRA_CHECKS},
              default_function_acl=[],connection_prerequisites={key:True for key in installer.CONNECT_KEYS})
    before=deepcopy(post);before['catalog'].update(columns={},functions={},triggers={})
    for row in runtime.required_privileges('revision'):
        key=preflight._privilege_key(*row)
        if row[3] and row[2]+'.'+row[3] in preflight.COLUMNS:before['catalog']['privileges'].pop(key,None)
        else:before['catalog']['privileges'][key]=False
    return spec,layout,before,post,receipt


class MemoryConnection:
    def __init__(self,spec):
        p=spec['policy'];self.info=SimpleNamespace(host=p['database_host'],port=p['database_port'],dbname=p['database_name'],user=spec['installer_role'],transaction_status=TransactionStatus.IDLE)
        self.autocommit=True;self.closed=False;self.events=[];self.pending=[];self.committed=[]
        self.fail_step=None;self.commit_error=False;self.rollback_error=False
    def execute(self,query,args=None):
        query=query.as_string() if hasattr(query,'as_string') else query;self.events.append((query,args))
        if query.startswith('BEGIN'):self.info.transaction_status=TransactionStatus.INTRANS
        if query.startswith(('ALTER TABLE','CREATE FUNCTION','CREATE TRIGGER','GRANT ')):
            self.pending.append(query)
            if self.fail_step==len(self.pending):raise RuntimeError('DI failed exact step')
        return self
    def cursor(self,**kwargs):return self
    def commit(self):
        self.events.append(('COMMIT',None));self.committed.extend(self.pending);self.pending=[];self.info.transaction_status=TransactionStatus.IDLE
        if self.commit_error:raise OSError('DI commit acknowledgement lost')
    def rollback(self):
        self.events.append(('ROLLBACK',None))
        if self.rollback_error:raise OSError('DI rollback acknowledgement lost')
        self.pending=[];self.info.transaction_status=TransactionStatus.IDLE


class Harness:
    def __init__(self):
        self.spec,self.layout,self.before,self.after,self.receipt=snapshots()
        self.controller=host.LinuxHost(self.spec,self.layout)
        self.plan=installer.prepare(self.spec,self.layout,self.before)
        self.connection=MemoryConnection(self.spec);self.files={};self.collect_count=0;self.reads=[];self.file_events=[]
        self.approval_path=self.layout['runtime_root']+'/host/install-approval.json'
        self.claim_path=self.layout['runtime_root']+'/host/install-claim.json'
        self.approval=support.signed(installer.installation_request(self.controller,self.plan))
    def identity(self):
        p=self.spec['policy'];return dict(database_name=p['database_name'],database_oid=p['database_oid'],system_identifier=p['system_identifier'],session_name=self.spec['installer_role'],current_name=self.spec['installer_role'],owner_name=self.spec['installer_role'])
    def protected(self,path,owner,**kwargs):
        self.reads.append(path)
        return {self.controller.layout.approval_key_path:support.KEY,self.approval_path:self.approval}[path]
    def collect(self,*args):
        self.collect_count+=1;return deepcopy(self.before if self.collect_count==1 else self.after)
    def output(self,path,raw):
        self.file_events.append((path,raw,len(self.connection.committed)))
        if path in self.files:raise FileExistsError('DI existing output')
        self.files[path]=raw
    @contextmanager
    def observations(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(host,'_supported_linux_runtime',return_value=True))
            stack.enter_context(patch.object(os,'geteuid',return_value=0))
            stack.enter_context(patch.object(host,'_protected_bytes',side_effect=self.protected))
            for name in ('_identities_check','_code_check','_dependencies_check'):
                stack.enter_context(patch.object(host,name,return_value=None))
            # Explicit type/identity/catalog observations, never a real connection.
            stack.enter_context(patch.object(installer.psycopg,'Connection',MemoryConnection))
            stack.enter_context(patch.object(installer,'_identity',side_effect=lambda *args:self.identity()))
            stack.enter_context(patch.object(installer,'_collect',side_effect=self.collect))
            stack.enter_context(patch.object(installer,'_new_private_output',side_effect=self.output))
            stack.enter_context(patch.object(installer.Path,'exists',new=lambda p:str(p) in self.files))
            stack.enter_context(patch.object(installer.Path,'is_symlink',return_value=False))
            yield
    def apply(self):return installer.install(self.controller,self.connection,self.plan,self.approval_path)


class InstallerTests(TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        def forbidden(*args,**kwargs):raise AssertionError('real connection/OS/permission action forbidden')
        for obj,name in [(psycopg,'connect'),(psycopg.Connection,'connect'),(socket.socket,'connect'),(socket.socket,'bind'),
                         (subprocess,'Popen'),(os,'open'),(os,'memfd_create'),(os,'chmod'),(os,'chown'),(os,'fchmod'),(os,'fchown'),(os,'unlink')]:
            self.stack.enter_context(patch.object(obj,name,side_effect=forbidden))
    def test_packaged_parser_consumes_nine_original_schema_qualified_objects(self):
        statements=installer.packaged_statements();self.assertEqual(len(statements),9)
        for name in preflight.COLUMNS:self.assertIn('ADD_COLUMN:public.'+name,statements)
        bodies,_=preflight.expected_storage()
        for name in preflight.FUNCTIONS:
            statement=statements['CREATE_FUNCTION:public.'+name+'()'];body=statement.split('$$')[1]
            self.assertEqual(preflight._body_sha(body),bodies[name]);self.assertIn('CREATE FUNCTION public.',statement)
        self.assertTrue(all('IF NOT EXISTS' not in text and 'OR REPLACE' not in text for text in statements.values()))
    def test_packaged_unknown_or_duplicate_statement_is_refused(self):
        originals={name:Path(installer.__file__).with_name(name).read_text() for name in preflight.FILES}
        for suffix in ('DROP TABLE runs;','ALTER TABLE runs ADD COLUMN unexpected jsonb;', 'ALTER TABLE runs ADD COLUMN native_run_access_protocol jsonb;'):
            with self.subTest(suffix=suffix),patch.object(installer.Path,'read_text',new=lambda p,**kw:originals[p.name]+(suffix if p.name==preflight.FILES[0] else '')),self.assertRaises(Denied):installer.packaged_statements()
    def test_first_install_plan_handles_missing_columns_and_only_known_grants(self):
        h=Harness();steps=h.plan['steps'];self.assertEqual(sum(x['kind']!='GRANT_PERMISSION' for x in steps),9)
        self.assertFalse(h.plan['installation_authorized']);self.assertFalse(h.plan['activation_enabled'])
        allowed={preflight._privilege_key(*row) for row in runtime.required_privileges('revision') if row[1]!='LOCK_UPDATE'}
        self.assertEqual({x['object'] for x in steps if x['kind']=='GRANT_PERMISSION'},allowed)
        self.assertTrue(all(not x['sql'].startswith(('CREATE ROLE','REVOKE ','DROP ','SET ROLE')) for x in steps))
    def test_partial_and_complete_installation_never_replay_existing_objects(self):
        spec,layout,before,after,_=snapshots();before['catalog']['columns']['runs.native_run_access_protocol']=deepcopy(after['catalog']['columns']['runs.native_run_access_protocol'])
        before['catalog']['privileges']['writer:UPDATE:runs:native_run_access_protocol']=True
        plan=installer.prepare(spec,layout,before)
        self.assertNotIn('ADD_COLUMN:public.runs.native_run_access_protocol',{x['kind']+':'+x['object'] for x in plan['steps']})
        self.assertEqual(installer.prepare(spec,layout,after)['steps'],[])
    def test_unknown_baseline_conflict_overload_or_privilege_observation_refuses(self):
        spec,layout,_,after,_=snapshots()
        for mutate in (lambda s:s['catalog'].update(schema_version=33),lambda s:s['catalog']['tables']['runs'].update(owner='unknown'),lambda s:s['catalog']['functions']['guard_native_assignment'].append(deepcopy(s['catalog']['functions']['guard_native_assignment'][0])),lambda s:s['catalog']['privileges'].pop('writer:SELECT:runs:')):
            bad=deepcopy(after);mutate(bad)
            with self.assertRaises(Denied):installer.prepare(spec,layout,bad)
    def test_unknown_acl_defaults_extra_authority_or_connection_prerequisite_refuses(self):
        spec,layout,_,after,_=snapshots()
        for mutate in (lambda s:s['catalog']['functions']['guard_native_assignment'][0].update(acl=['stranger=X/unknown']),lambda s:s['default_function_acl'].append({'unknown':'grant'}),lambda s:s['extra_acl'].update(database_extra=True),lambda s:s['extra_acl'].update(unknown=False),lambda s:s['connection_prerequisites'].update(writer_connect=False),lambda s:s['catalog']['privileges'].update({'app:control_system_execute':True})):
            bad=deepcopy(after);mutate(bad)
            with self.assertRaises((Denied,ValueError)):installer.prepare(spec,layout,bad)
    def test_missing_role_or_installer_ability_and_unsupported_strategy_refuse(self):
        spec,layout,before,_,_=snapshots()
        for mutate in (lambda s:s['catalog']['roles'].pop(spec['policy']['writer_role']),lambda s:s['catalog']['privileges'].update({'installer:schema_create':False})):
            bad=deepcopy(before);mutate(bad)
            with self.assertRaises(Denied):installer.prepare(spec,layout,bad)
        for key,value in [('permission_strategy','NARROW_FUNCTIONS'),('parent_lock_column','state')]:
            bad=deepcopy(spec);bad[key]=value
            with self.assertRaises(Denied):installer.prepare(bad,layout,before)
    def test_default_and_wrong_action_reference_refuse_before_private_or_connection_io(self):
        h=Harness()
        with patch.object(host,'_protected_bytes',side_effect=AssertionError('private read reached')):
            for reference in (None,True,{},h.controller.layout.approval_path,h.controller.layout.installation_path):
                with self.subTest(reference=reference),self.assertRaises(Denied):installer.install(h.controller,None,h.plan,reference)
        self.assertEqual(h.connection.events,[]);self.assertEqual(h.files,{})
    def test_signed_plan_sql_target_and_signature_tampering_never_mutates(self):
        for kind in ('sql','before','signature'):
            h=Harness()
            if kind=='sql':h.plan['steps'][0]['sql']='DROP TABLE public.runs'
            elif kind=='before':h.plan['before_sha256']='0'*64
            else:h.approval=h.approval.replace(b'"hmac_sha256":"',b'"hmac_sha256":"0')
            with self.subTest(kind=kind),h.observations(),self.assertRaises(Denied):h.apply()
            self.assertEqual(h.connection.events,[]);self.assertEqual(h.files,{})
    def test_exact_idle_connection_required_before_claim(self):
        for field,value in [('autocommit',False),('closed',True)]:
            h=Harness();setattr(h.connection,field,value)
            with h.observations(),self.assertRaises(Denied):h.apply()
            self.assertEqual(h.files,{})
        h=Harness();h.connection.info.transaction_status=TransactionStatus.INTRANS
        with h.observations(),self.assertRaises(Denied):h.apply()
        self.assertEqual(h.files,{})
        class Subclass(MemoryConnection):pass
        h=Harness();h.connection=Subclass(h.spec)
        with h.observations(),self.assertRaises(Denied):h.apply()
        self.assertEqual(h.files,{})
    def test_actual_identity_uses_session_role_and_physical_database(self):
        h=Harness()
        for field,value in [('session_name','unknown'),('current_name','unknown'),('database_oid',999),('system_identifier','other')]:
            bad=h.identity();bad[field]=value
            with self.subTest(field=field),patch.object(runtime,'_identity',return_value=bad),self.assertRaises(Denied):installer._identity(h.connection,host.preflight.InstallationSpec.model_validate(h.spec))
    def test_full_install_commits_then_publishes_original_host_compatible_receipt(self):
        h=Harness()
        with h.observations():result=h.apply()
        self.assertEqual(result['status'],'COMMITTED');self.assertFalse(result['host_started']);self.assertFalse(result['activation_enabled'])
        self.assertEqual(len(h.connection.committed),len(h.plan['steps']));self.assertEqual(h.connection.pending,[])
        self.assertEqual(h.file_events[0][0],h.claim_path);self.assertEqual(h.file_events[0][2],0)
        self.assertEqual(h.file_events[-1][2],len(h.plan['steps']));self.assertEqual(h.files[h.controller.layout.installation_path],h.receipt)
        host.verified_record(json.loads(h.receipt),support.KEY,host.installed_receipt_payload(h.spec,h.layout))
        locks=[query for query,_ in h.connection.events if query.startswith('LOCK TABLE')]
        self.assertEqual(len(locks),len(preflight.TABLES));self.assertTrue(all('ACCESS EXCLUSIVE' in query for query in locks))
    def test_fresh_catalog_drift_rolls_back_before_any_ddl(self):
        h=Harness();h.before['catalog']['tables']['runs']['oid']+=1
        with h.observations(),self.assertRaises(installer.InstallFailure) as caught:h.apply()
        self.assertEqual(caught.exception.outcome,'ROLLED_BACK');self.assertEqual(h.connection.committed,[]);self.assertEqual(h.connection.pending,[])
        self.assertEqual(list(h.files),[h.claim_path]);self.assertIsInstance(caught.exception.__cause__,Denied)
    def test_caller_plan_mutation_after_authorization_or_during_lock_cannot_expand_delta(self):
        for moment in ('authorized','lock_wait'):
            h=Harness();larger=deepcopy(h.plan)
            partial=deepcopy(h.before)
            name='runs.native_run_access_protocol'
            partial['catalog']['columns'][name]=deepcopy(h.after['catalog']['columns'][name])
            partial['catalog']['privileges']['writer:UPDATE:runs:native_run_access_protocol']=True
            h.plan=installer.prepare(h.spec,h.layout,partial)
            approved_sha=writer._sha(h.plan)
            h.approval=support.signed(installer.installation_request(h.controller,h.plan))
            authorize=installer._authorize;execute=h.connection.execute;changed=[]
            def mutate():
                h.plan.clear();h.plan.update(deepcopy(larger));changed.append(True)
            def authorize_and_mutate(*args):
                receipt=authorize(*args)
                if moment=='authorized':mutate()
                return receipt
            def execute_and_mutate(query,args=None):
                result=execute(query,args)
                text=query.as_string() if hasattr(query,'as_string') else query
                if moment=='lock_wait' and text.startswith('LOCK TABLE') and not changed:mutate()
                return result
            with self.subTest(moment=moment),h.observations(),patch.object(installer,'_authorize',side_effect=authorize_and_mutate),patch.object(h.connection,'execute',side_effect=execute_and_mutate),self.assertRaises(installer.InstallFailure) as caught:h.apply()
            self.assertTrue(changed);self.assertEqual(caught.exception.outcome,'ROLLED_BACK')
            self.assertEqual(h.connection.pending+h.connection.committed,[])
            self.assertEqual(json.loads(h.files[h.claim_path])['plan_sha256'],approved_sha)
    def test_mid_ddl_or_grant_failure_rolls_back_without_compensating_drop(self):
        for step in (1,10):
            h=Harness();h.connection.fail_step=step
            with self.subTest(step=step),h.observations(),self.assertRaises(installer.InstallFailure) as caught:h.apply()
            self.assertEqual(caught.exception.outcome,'ROLLED_BACK');self.assertEqual(h.connection.pending+h.connection.committed,[])
            self.assertFalse(any('DROP ' in query or 'REVOKE ' in query for query,_ in h.connection.events));self.assertEqual(list(h.files),[h.claim_path])
    def test_postcondition_or_extra_acl_drift_rolls_back_all_changes(self):
        h=Harness();h.after['extra_acl']['app_control']=True
        with h.observations(),self.assertRaises(installer.InstallFailure) as caught:h.apply()
        self.assertEqual(caught.exception.phase,'AFTER');self.assertEqual(caught.exception.outcome,'ROLLED_BACK');self.assertEqual(h.connection.committed,[])
    def test_expiry_before_an_apply_step_rolls_back_without_renewal(self):
        h=Harness();calls=[]
        def interval(spec):
            calls.append(1)
            if len(calls)==4:raise Denied('DI original interval expired')
        with h.observations(),patch.object(installer,'_live_interval',side_effect=interval),self.assertRaises(installer.InstallFailure) as caught:h.apply()
        self.assertEqual(caught.exception.phase,'APPLY');self.assertEqual(caught.exception.outcome,'ROLLED_BACK');self.assertEqual(h.connection.committed,[])
    def test_commit_response_loss_is_unknown_and_never_retried_or_published(self):
        h=Harness();h.connection.commit_error=True
        with h.observations(),self.assertRaises(installer.InstallFailure) as caught:h.apply()
        self.assertEqual(caught.exception.outcome,'COMMIT_UNKNOWN');self.assertEqual(len(h.connection.committed),len(h.plan['steps']))
        self.assertEqual([q for q,_ in h.connection.events].count('COMMIT'),1);self.assertNotIn('ROLLBACK',[q for q,_ in h.connection.events]);self.assertEqual(list(h.files),[h.claim_path])
    def test_rollback_failure_keeps_both_original_and_rollback_errors(self):
        h=Harness();h.connection.fail_step=1;h.connection.rollback_error=True
        with h.observations(),self.assertRaises(installer.InstallFailure) as caught:h.apply()
        self.assertEqual(caught.exception.outcome,'ROLLBACK_UNCONFIRMED');self.assertIsInstance(caught.exception.__cause__,RuntimeError);self.assertIsInstance(caught.exception.rollback_error,OSError)
    def test_publication_failure_reports_committed_and_preserves_unknown_file(self):
        h=Harness()
        def output(path,raw):
            h.output(path,raw)
            if path==h.controller.layout.installation_path:raise OSError('DI publish acknowledgement lost')
        with h.observations(),patch.object(installer,'_new_private_output',side_effect=output),self.assertRaises(installer.InstallFailure) as caught:h.apply()
        self.assertEqual(caught.exception.outcome,'COMMITTED_OUTPUT_UNCONFIRMED');self.assertEqual(len(h.connection.committed),len(h.plan['steps']));self.assertNotIn('ROLLBACK',[q for q,_ in h.connection.events])
        self.assertIn(h.controller.layout.installation_path,h.files)
    def test_existing_claim_or_receipt_is_not_overwritten_or_adopted(self):
        for path_kind in ('claim','receipt'):
            h=Harness();path=h.claim_path if path_kind=='claim' else h.controller.layout.installation_path;h.files[path]=b'UNKNOWN'
            with self.subTest(path=path_kind),h.observations(),self.assertRaises((Denied,FileExistsError)):h.apply()
            self.assertEqual(h.connection.events,[]);self.assertEqual(h.files[path],b'UNKNOWN')
    def test_output_uses_only_new_root_private_exclusive_nofollow_fd(self):
        calls=[]
        with patch.object(host,'_path_chain',side_effect=lambda path,owners:calls.append((path,owners))),patch.object(os,'open',return_value=91) as opened,patch.object(host,'_write_all') as wrote,patch.object(os,'fsync'),patch.object(os,'close') as closed:
            installer._new_private_output('/var/lib/parkweave/runtimes/'+'c'*32+'/host/install-claim.json',b'SYNTHETIC')
        self.assertEqual(opened.call_args.args[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW);self.assertEqual(opened.call_args.args[2],0o600);self.assertEqual(calls[0][1],{0});wrote.assert_called_once_with(91,b'SYNTHETIC');closed.assert_called_once_with(91)
    def test_protected_receipt_digest_mismatch_refuses_before_claim_or_sql(self):
        h=Harness();h.layout['installation_receipt_sha256']='0'*64;h.controller=host.LinuxHost(h.spec,h.layout);h.plan=installer.prepare(h.spec,h.layout,h.before);h.approval=support.signed(installer.installation_request(h.controller,h.plan))
        with h.observations(),self.assertRaises(Denied):h.apply()
        self.assertEqual(h.connection.events,[]);self.assertEqual(h.files,{})
    def test_collector_only_reads_metadata_and_adds_missing_runtime_observations(self):
        h=Harness();queries=[]
        class Reader:
            def cursor(self,**kwargs):return self
            def execute(self,query,args=None):queries.append((query,args));self.query=query;return self
            def fetchone(self):return {'connect':True,'usage':True} if 'has_database_privilege' in self.query else {'ok':False}
            def fetchall(self):return []
        with patch.object(preflight,'_read_catalog',return_value=deepcopy(h.after['catalog'])),patch.object(runtime,'_additional_acl',return_value=deepcopy(h.after['extra_acl'])):
            result=installer._collect(Reader(),host.preflight.InstallationSpec.model_validate(h.spec),h.identity())
        self.assertIs(result['catalog']['privileges']['writer:SELECT:schema_version:'],False)
        self.assertEqual(result['default_function_acl'],[]);self.assertTrue(all(query.startswith('SELECT') for query,_ in queries));self.assertTrue(any('pg_catalog.pg_default_acl' in query for query,_ in queries))
    def test_default_tuple_connection_uses_private_dict_cursors_without_changing_factory(self):
        h=Harness();factories=[]
        class Reader(MemoryConnection):
            row_factory=staticmethod(psycopg.rows.tuple_row)
            def cursor(self,**kwargs):
                factories.append(kwargs['row_factory']);return Cursor()
        class Cursor:
            def execute(self,query,args=None):self.query=query;return self
            def fetchone(self):
                if 'session_user session_name' in self.query:return h.identity()
                if 'role_flags' in self.query:return deepcopy(h.after['extra_acl'])
                if 'has_database_privilege' in self.query:return {'connect':True,'usage':True}
                return {'ok':True}
            def fetchall(self):return []
        connection=Reader(h.spec);spec=preflight.InstallationSpec.model_validate(h.spec)
        with patch.object(installer.psycopg,'Connection',Reader),patch.object(preflight,'_read_catalog',return_value=deepcopy(h.after['catalog'])):
            installer._connection_check(connection,spec)
            identity=installer._identity(connection,spec)
            result=installer._collect(connection,spec,identity)
        self.assertEqual(result['extra_acl'],h.after['extra_acl'])
        self.assertTrue(factories);self.assertTrue(all(x is psycopg.rows.dict_row for x in factories))
        self.assertIs(connection.row_factory,psycopg.rows.tuple_row)
    def test_unknown_baseline_structure_is_rejected_before_reused_data_reader(self):
        h=Harness();queries=[]
        class Reader:
            def cursor(self,**kwargs):return self
            def execute(self,query,args=None):queries.append(query);return self
            def fetchone(self):return None
        with patch.object(preflight,'_read_catalog',side_effect=AssertionError('unknown target data read reached')),self.assertRaises(Denied):
            installer._collect(Reader(),preflight.InstallationSpec.model_validate(h.spec),h.identity())
        self.assertEqual(len(queries),1)
        for clause in ("r.relkind='r'",'NOT r.relrowsecurity','NOT r.relforcerowsecurity','NOT r.relhasrules','pg_catalog.pg_rewrite','pg_catalog.pg_inherits',"'pg_catalog.int4'::pg_catalog.regtype"):
            self.assertIn(clause,queries[0])
    def test_read_only_inspect_prepares_without_private_inputs_or_any_installation_write(self):
        h=Harness()
        with h.observations(),patch.object(installer,'_baseline_check',return_value=None):
            result=installer.inspect(h.controller,h.connection)
        self.assertEqual(result['plan'],h.plan);self.assertFalse(result['installation_authorized'])
        self.assertEqual(h.reads,[]);self.assertEqual(h.files,{})
        queries=[query for query,_ in h.connection.events]
        self.assertEqual(queries[0],'BEGIN ISOLATION LEVEL READ COMMITTED READ ONLY')
        self.assertEqual(queries[-1],'ROLLBACK');self.assertNotIn('COMMIT',queries)
        self.assertFalse(any(q.startswith(('ALTER TABLE','CREATE ','GRANT ')) for q in queries))
    def test_inspect_rejection_ends_read_only_transaction_and_preserves_end_uncertainty(self):
        for end_fails in (False,True):
            h=Harness();h.connection.rollback_error=end_fails
            with self.subTest(end_fails=end_fails),h.observations(),patch.object(installer,'_identity',side_effect=Denied('DI unknown original role')),self.assertRaises(installer.InstallFailure) as caught:
                installer.inspect(h.controller,h.connection)
            self.assertEqual(caught.exception.outcome,'READ_ONLY_END_UNCONFIRMED' if end_fails else 'READ_ONLY_ENDED')
            self.assertIsInstance(caught.exception.__cause__,Denied)
            self.assertEqual(h.reads,[]);self.assertEqual(h.files,{})
            self.assertFalse(any(q.startswith('LOCK TABLE') for q,_ in h.connection.events))


if __name__=='__main__':main(verbosity=2)
