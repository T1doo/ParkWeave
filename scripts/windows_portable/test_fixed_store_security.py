"""Isolated controller wiring: memory slots/files, fake facts, zero real SQL/OS IO."""
from copy import copy,deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import hashlib
import time
import unittest
from unittest.mock import patch

from . import fixed_store_security as f, controller as c, application_readiness as ready
from . import credential_envelope as e, endpoint_plan as ep, fixed_directories as d, fixed_journal as j
from . import fixed_secret_store as s, instance_processes as instance
from .directories import LeaseRefused
from .test_fixed_identity_journal import MemorySlotIO
from .test_fixed_secret_store import MemoryFiles, SENTINEL
from .test_credential_envelope import binding,payloads
from .test_windows_user_protection import Buffers
from .test_instance_processes import ApplicationAdapter,NONCE
from .windows_user_protection import IsolatedUserProtection


class Facts(f.FakeSecurityAPI):
    def __init__(self,events):
        self.events=events;self.records={};self.runtime=None;self.cluster=None;self.sid=binding().sid
        self.database_value=deepcopy(payloads()[e.Purpose.CONFIG]['database'])
        self.secrets=deepcopy(payloads()[e.Purpose.DATABASE]);self.secrets['postgres']="SYNTHETIC ' owner\\ quote"
        self.sessions=None;self.active=True;self.ownership=True;self.faults={};self.hook=None

    def event(self,name):
        self.events.append(name)
        if name in self.faults:raise self.faults[name]

    def issue(self,subject,kind,value,inputs=None):
        token=f.SecurityFact();self.records[token]=(subject,kind,inputs,value);return token

    def owns(self,token,subject,kind,inputs):
        if token not in self.records:return False
        a,b,value,_=self.records[token]
        same=(value is inputs)if type(inputs)is not tuple else (
            type(value)is tuple and len(value)==len(inputs)and all(x is y for x,y in zip(value,inputs)))
        return a is subject and b is kind and same

    def read(self,token):return self.records[token][3]
    def creation_support(self,subject):
        self.event('creation_guard');return self.issue(subject,f.FactKind.CREATION,f.SyntheticSupport.LOCAL_NO_MODEL)
    def runtime_support(self,subject,database,processes):
        self.event('runtime_guard')
        if self.runtime is None or self.runtime[0] is not database or self.runtime[1] is not processes:
            raise PermissionError('SYNTHETIC_RUNTIME_NOT_REGISTERED')
        return self.issue(subject,f.FactKind.RUNTIME,f.SyntheticSupport.LOCAL_NO_MODEL,(database,processes))
    def current_user(self,lease):
        self.event('current_user')
        if self.hook:self.hook()
        return self.issue(lease,f.FactKind.USER,self.sid)
    def material(self,lease,purpose):
        self.event('material:'+purpose.value)
        value=self.secrets if purpose is e.Purpose.DATABASE else payloads()[e.Purpose.SESSION]
        kind=f.FactKind.DATABASE_MATERIAL if purpose is e.Purpose.DATABASE else f.FactKind.SESSION_MATERIAL
        return self.issue(lease,kind,deepcopy(value))
    def owned_cluster(self,lease,inputs):
        self.event('owned_endpoint')
        if (not self.ownership or self.cluster is None or self.cluster[0] is not lease or self.cluster[1] is not inputs):
            raise PermissionError('SYNTHETIC_ENDPOINT_OWNERSHIP_UNKNOWN')
        return self.issue(lease,f.FactKind.ENDPOINT,('127.0.0.1',54000),inputs)
    def database(self,lease,inputs,witness):
        assert self.owns(witness,lease,f.FactKind.ENDPOINT,inputs)
        self.event('database_observation');return self.issue(lease,f.FactKind.DATABASE,deepcopy(self.database_value),inputs)
    def actor(self,lease,inputs,witness,bearer):
        assert self.owns(witness,lease,f.FactKind.ENDPOINT,inputs)
        self.event('actor_observation')
        if self.sessions is None or bearer!=self.sessions['fixture-a']:raise PermissionError('SYNTHETIC_SESSION_UNKNOWN')
        value=dict(id='fixture-a',park_id='park-a',org_id='org-a',role='enterprise_operator',active=self.active,
                   token_hash=hashlib.sha256(bearer.encode()).hexdigest())
        return self.issue(lease,f.FactKind.ACTOR,value,inputs)


class Database:
    def __init__(self,api,events):self.api,self.events=api,events;self.owner=object()
    def prepare_new(self):self.events.append('prepare_roles');return b'SYNTHETIC_ROLES'
    def create_schema32(self,inputs):
        self.api.owned_cluster(self.api.cluster[0],inputs);self.events.append('schema32');return self.owner
    def grant_roles(self,owner,prepared):
        assert owner is self.owner and prepared==b'SYNTHETIC_ROLES';self.events.append('roles')
    def seed(self,owner,identities):
        assert owner is self.owner and set(identities)=={'fixture-a','fixture-b','fixture-c'}
        self.events.append('seed');self.api.sessions=dict(identities)
    def verify_existing(self,inputs):
        self.api.owned_cluster(self.api.cluster[0],inputs);self.events.append('verify_schema')


class Processes:
    def __init__(self,security,api,events):
        self.security,self.api,self.events=security,api,events;self.owned=[]
    def cluster(self,mode,lease,credentials,register):
        inputs=self.security.configuration(lease,credentials,time.monotonic()+25)
        token=object();self.owned.append((token,'cluster'));register(token)
        self.api.cluster=(lease,inputs,token);self.events.append('cluster:'+mode)
        return inputs
    def create_cluster(self,*args):return self.cluster('NEW',*args)
    def open_cluster(self,*args):return self.cluster('REOPEN',*args)
    def start_application(self,lease,inputs,register):
        self.security.require_inputs(lease,inputs)
        app=SimpleNamespace(api=object(),worker=object(),lease=lease,inputs=inputs)
        for name in ('api','worker'):
            token=getattr(app,name);self.owned.append((token,name));register(token)
        self.events.append('application');return app
    def stop_owned(self,token):
        name=next(name for value,name in self.owned if value is token)
        self.events.append('stop:'+name)
        if name=='cluster':self.api.cluster=None
        return True


class SecurityLifecycleChecks(unittest.TestCase):
    def setUp(self):
        self.events=[];self.api=Facts(self.events);self.files={};self.file_apis=[];self.leases=[]
        self.backing=dict(exists=False,held=False,raw=bytearray(),revision=0)
        self.dirs=d.FixedPrivateDirectories('/synthetic-private',format=j.FixedFormat.INSTANCE_V2)
        def filesystem():
            io=MemorySlotIO(self.backing,j.FixedFormat.INSTANCE_V2)
            io.base=Path('/synthetic-private');io.chain=[(None,'instance',None)]
            return io
        for fixture in (patch.object(self.dirs,'_filesystem',side_effect=filesystem),
                        patch.object(d,'_random_bytes',return_value=bytes(range(16)))):
            fixture.start();self.addCleanup(fixture.stop)
        self.addCleanup(self.finish)
        self.security=self.make_security(ep.PlanMode.NEW)
        self.db=Database(self.api,self.events);self.processes=Processes(self.security,self.api,self.events)
        self.api.runtime=(self.db,self.processes)
        self.receipts={}
        def require_ready(lease,inputs,app,probe,registered):
            self.assertIs(type(probe),ready.ExistingActorProbe);probe.expected()
            self.assertIs(app.lease,lease);self.assertIs(app.inputs,inputs)
            self.assertEqual(registered,[app.api,app.worker])
            receipt=object();self.receipts[receipt]=lease;self.events.append('ready');return receipt
        def check(receipt):
            self.assertEqual(self.receipts[receipt].record['phase'],'APPLICATION');self.events.append('check_ready')
        def go(receipt):
            self.assertEqual(self.receipts.pop(receipt).record['phase'],'RUNNING');self.events.append('go')
        for name,method in (('require_application_ready',require_ready),('check_before_running',check),('activate_application',go)):
            fixture=patch.object(ready,name,side_effect=method);fixture.start();self.addCleanup(fixture.stop)

    def finish(self):
        for lease in self.leases:
            if lease.active:lease.release()

    def make_security(self,mode):
        def factory(lease,b):
            self.leases.append(lease);api=MemoryFiles(lease,self.files);self.file_apis.append(api)
            return s.IsolatedFixedSecretStore(lease,b,api,IsolatedUserProtection(Buffers()),config_format=e.ConfigFormat.INSTANCE_SCHEMA3)
        return f.IsolatedFixedStoreSecurity(mode,request=ep.EndpointRequest(54000,58000)if mode is ep.PlanMode.NEW else None,
            api=self.api,store_factory=factory,runtime=payloads()[e.Purpose.CONFIG]['runtime'])

    def controller(self):return c.Controller(self.dirs,self.security,self.processes,database=self.db)

    def new(self):
        # Explicit isolated _run seam. Public create/OWNER is never enabled.
        return self.controller()._run('/synthetic-private/instance',lambda app:self.events.append('use'),fresh=True)

    def prepare_reopen(self):
        self.new();self.events.clear()
        self.security=self.make_security(ep.PlanMode.REOPEN)
        self.processes=Processes(self.security,self.api,self.events);self.api.runtime=(self.db,self.processes)

    def test_new_full_original_order_real_store_and_quoted_fixed_dsns(self):
        result=self.new();self.assertEqual(result['mode'],'NEW')
        ordered=['runtime_guard','creation_guard','prepare_roles','material:DATABASE','cluster:NEW','schema32','roles',
                 'material:SESSION','seed','verify_schema','application','actor_observation','ready','check_ready','go',
                 'use','stop:worker','stop:api','stop:cluster']
        self.assertEqual([x for x in self.events if x in ordered],ordered)
        self.assertEqual(set(self.files),set(e.Purpose));self.assertFalse(self.file_apis[-1].caps)
        from parkweave.installed_fixture_receipt import _dsn
        inputs=self.security._inputs
        self.assertEqual(_dsn(inputs.owner_dsn,'parkweave')['password'],self.api.secrets['postgres'])
        self.assertEqual(_dsn(inputs.application_dsn,'parkweave')['user'],'parkweave_app')
        self.assertNotIn(self.api.secrets['postgres'],repr(inputs))
        self.assertFalse(self.security.lease.active)

    def test_reopen_consumes_one_authentication_without_any_new_business_or_file_writes(self):
        self.prepare_reopen();original={k:v['raw']for k,v in self.files.items()}
        result=self.controller().reopen('/synthetic-private/instance',lambda app:self.events.append('use'))
        self.assertEqual(result['mode'],'REOPEN');self.assertEqual(self.security.lease.record['generation'],2)
        self.assertFalse({'prepare_roles','creation_guard','schema32','roles','seed','material:DATABASE','material:SESSION'}&set(self.events))
        self.assertEqual({k:v['raw']for k,v in self.files.items()},original)
        self.assertFalse(any(x[0]in('create','write','flush')for x in self.file_apis[-1].events if type(x)is tuple))
        self.assertEqual(sum(x==('open','CONFIG')for x in self.file_apis[-1].events),1)

    def manual_new(self):
        lease=self.dirs.claim_fresh('/synthetic-private/instance');self.leases.append(lease)
        self.security.bind_new_lease(lease);lease.checkpoint('CREDENTIALS',False,'STARTING')
        credentials=self.security.create_credentials(lease);return lease,credentials

    def manual_reopen(self):
        self.prepare_reopen();lease=self.dirs.open_existing('/synthetic-private/instance');self.leases.append(lease)
        self.security.verify_existing_files(lease);return lease

    def test_binding_is_mandatory_before_credentials_and_public_native_create_stays_paused(self):
        from scripts.windows import lifecycle
        with self.assertRaises(lifecycle.BoundaryError):self.controller().create('/synthetic-private/instance',lambda app:None)
        self.assertEqual(self.events,[]);self.assertFalse(self.backing['exists'])
        lease=self.dirs.claim_fresh('/synthetic-private/instance');self.leases.append(lease)
        lease.checkpoint('CREDENTIALS',False,'STARTING')
        with self.assertRaises(f.SecurityFailure):self.security.create_credentials(lease)
        self.assertEqual(self.files,{})

    def test_replaced_authentication_is_not_a_consumable_completed_read(self):
        lease=self.manual_reopen();self.security._authentication=s.StoreAuthentication()
        with self.assertRaises(f.SecurityFailure):self.security.load_existing_credentials(lease)
        self.assertIsNone(self.security._credential);self.assertTrue(lease.poisoned)

    def test_matching_forged_authentication_fields_still_do_not_replace_store_registration(self):
        lease=self.manual_reopen();forged=s.StoreAuthentication()
        self.security._authentication=self.security._auth_registered=forged
        with self.assertRaises(f.SecurityFailure):self.security.load_existing_credentials(lease)
        self.assertIsNone(self.security._credential);self.assertTrue(self.security.failed and lease.poisoned)

    def test_authentication_registration_failure_after_closed_read_is_unknown(self):
        self.prepare_reopen();lease=self.dirs.open_existing('/synthetic-private/instance');self.leases.append(lease)
        class FailedRegistry(dict):
            def __setitem__(self,key,value):raise RuntimeError('SYNTHETIC_AUTH_REGISTRATION_FAILURE')
        with patch.object(s,'_authenticated_reads',FailedRegistry()):
            with self.assertRaises(f.SecurityFailure):self.security.verify_existing_files(lease)
        self.assertIsNone(self.security._authentication);self.assertFalse(self.file_apis[-1].caps)
        self.assertTrue(self.security.failed and lease.poisoned)

    def test_duplicate_authentication_consumption_is_refused(self):
        lease=self.manual_reopen();credentials=self.security.load_existing_credentials(lease)
        self.assertIs(type(credentials),f.PrivateCredentials)
        with self.assertRaises(f.SecurityFailure):self.security.load_existing_credentials(lease)
        self.assertTrue(self.security.failed and lease.poisoned)

    def test_changed_authentication_snapshot_is_not_refreshed_or_reissued(self):
        lease=self.manual_reopen();lease.checkpoint('CLUSTER',True,'STARTING')
        with self.assertRaises(f.SecurityFailure):self.security.load_existing_credentials(lease)
        self.assertIsNone(self.security._credential);self.assertNotIn('material:DATABASE',self.events)

    def test_public_store_reentry_is_busy_but_held_wiring_registers_before_unlock(self):
        seen=[]
        def hook():
            if self.security.store is not None:
                with self.assertRaisesRegex(LeaseRefused,'FIXED_LEASE_OPERATION_BUSY'):self.security.store.read_existing()
                seen.append(self.security.lease._operation_depth)
        self.api.hook=hook
        self.new();self.assertTrue(seen);self.assertTrue(all(x>0 for x in seen))

    def test_ownership_mismatch_stops_before_independent_database_query(self):
        lease,credentials=self.manual_new();lease.checkpoint('CLUSTER',False,'STARTING')
        inputs=self.processes.create_cluster(lease,credentials,lambda token:None)
        self.api.ownership=False
        with self.assertRaises(f.SecurityFailure):self.security._run(lease,lambda:self.security._database(lease,inputs))
        self.assertNotIn('database_observation',self.events)

    def test_current_user_change_rejects_before_material_or_inputs(self):
        lease,credentials=self.manual_new();lease.checkpoint('CLUSTER',False,'STARTING')
        self.api.sid='S-1-5-21-1-2-3-1002'
        with self.assertRaises(f.SecurityFailure):self.security.configuration(lease,credentials,time.monotonic()+25)
        self.assertIsNone(self.security._inputs)

    def test_physical_or_actor_disagreement_never_sends_go_or_repairs_identity(self):
        self.prepare_reopen();self.api.database_value['database_oid']+=1
        with self.assertRaises(c.ControlFailure):self.controller().reopen('/synthetic-private/instance',lambda app:self.fail('use'))
        self.assertNotIn('go',self.events);self.assertNotIn('material:SESSION',self.events)

    def test_revoked_actor_is_not_recreated_or_changed_to_fallback_identity(self):
        self.prepare_reopen();self.api.active=False
        with self.assertRaises(c.ControlFailure):self.controller().reopen('/synthetic-private/instance',lambda app:self.fail('use'))
        self.assertIn('actor_observation',self.events);self.assertNotIn('go',self.events)
        self.assertNotIn('seed',self.events);self.assertNotIn('material:SESSION',self.events)

    def test_credential_forgery_copied_inputs_and_post_registration_failure_are_refused(self):
        lease,credentials=self.manual_new();lease.checkpoint('CLUSTER',False,'STARTING')
        for transfer in (copy,deepcopy):
            with self.assertRaises(TypeError):transfer(credentials)
        with self.assertRaises(f.SecurityFailure):self.security.configuration(lease,f.PrivateCredentials(),time.monotonic()+25)
        self.assertIsNone(self.security._inputs)

    def test_equal_database_inputs_copy_is_not_the_registered_instance(self):
        lease,credentials=self.manual_new();lease.checkpoint('CLUSTER',False,'STARTING')
        inputs=self.processes.create_cluster(lease,credentials,lambda token:None)
        self.assertEqual(inputs,replace(inputs))
        with self.assertRaises(PermissionError):self.api.owned_cluster(lease,replace(inputs))
        with self.assertRaises(f.SecurityFailure):self.security.require_inputs(lease,replace(inputs))
        self.assertNotIn('database_observation',self.events)

    def test_plain_identity_dict_cannot_self_certify_current_user(self):
        lease=self.dirs.claim_fresh('/synthetic-private/instance');self.leases.append(lease)
        with patch.object(self.api,'current_user',return_value={'sid':binding().sid}):
            with self.assertRaises(f.SecurityFailure):self.security.bind_new_lease(lease)
        self.assertEqual(self.files,{});self.assertTrue(lease.poisoned)

    def test_post_credential_registration_exception_poison_keeps_no_usable_handle(self):
        lease=self.dirs.claim_fresh('/synthetic-private/instance');self.leases.append(lease)
        self.security.bind_new_lease(lease);lease.checkpoint('CREDENTIALS',False,'STARTING')
        original=self.security._context;captured=[]
        def fail_after(held):
            original(held)
            if self.security._credential is not None:
                captured.append(self.security._credential);raise RuntimeError('SYNTHETIC_POST_REGISTRATION_FAILURE')
        with patch.object(self.security,'_context',side_effect=fail_after):
            with self.assertRaises(f.SecurityFailure):self.security.create_credentials(lease)
        self.assertEqual(len(captured),1);self.assertIsNone(self.security._credential)
        self.assertTrue(self.security.failed and lease.poisoned)

    def test_original_write_error_close_and_journal_failure_are_all_retained(self):
        lease=self.dirs.claim_fresh('/synthetic-private/instance');self.leases.append(lease)
        self.security.bind_new_lease(lease);lease.checkpoint('CREDENTIALS',False,'STARTING')
        api=self.file_apis[-1];api.write_error=api.close_errors=True;lease.fs.flush_error=True
        with self.assertRaises(f.SecurityFailure)as raised:self.security.create_credentials(lease)
        store_failure=raised.exception.primary
        self.assertIsInstance(store_failure,s.StoreFailure);self.assertIsInstance(store_failure.primary,RuntimeError)
        self.assertEqual(len(store_failure.cleanup),2);self.assertIsInstance(store_failure.journal_error,OSError)
        self.assertNotIn(SENTINEL,str(raised.exception));self.assertTrue(lease.poisoned)

    def test_controller_preserves_security_primary_and_uncertain_release_failure(self):
        factory=self.security.store_factory
        def failing_factory(lease,b):
            store=factory(lease,b);store.api.write_error=store.api.close_errors=True
            write=store.api.write
            def fail_at_write(cap,raw):
                lease.fs.flush_error=lease.fs.close_error=True
                return write(cap,raw)
            store.api.write=fail_at_write
            return store
        self.security.store_factory=failing_factory
        with self.assertRaises(c.ControlFailure)as raised:self.new()
        failure=raised.exception
        self.assertIsInstance(failure.surfaced,f.SecurityFailure)
        self.assertIsInstance(failure.surfaced.primary,s.StoreFailure)
        self.assertEqual(failure.surfaced.primary.primary.args,(SENTINEL,))
        self.assertTrue(any(phase=='RELEASE'for phase,_ in failure.cleanup_errors))
        self.assertFalse(self.leases[-1].active)

    def test_native_database_default_and_native_security_factory_cannot_be_blessed_by_fake_facts(self):
        with self.assertRaises(c.ControlFailure):
            c.Controller(self.dirs,self.security,self.processes).reopen('/synthetic-private/instance',lambda app:None)
        self.assertFalse(self.backing['exists']);self.assertEqual(self.events,[])
        with self.assertRaises(c.CandidateRefused):f.native_fixed_store_security()

    def test_instance_source_route_is_explicit_and_uses_restored_plan(self):
        lease=self.manual_reopen();credentials=self.security.load_existing_credentials(lease)
        with self.assertRaises(c.CandidateRefused):instance.InstanceProcesses(self.processes,python_sha256='a'*64,
            python_size=100,api_port=58000,endpoint_source=self.security,challenge=NONCE)
        runner=instance.InstanceProcesses(self.processes,python_sha256='a'*64,python_size=100,
                                          endpoint_source=self.security,challenge=NONCE)
        lease.checkpoint('CLUSTER',True,'STARTING');owned=[]
        inputs=runner.open_cluster(lease,credentials,owned.append)
        for phase,runtime in (('VERIFY_DATABASE','STARTING'),('READY','STOPPED'),('APPLICATION','STARTING')):
            lease.checkpoint(phase,True,runtime)
        with patch.object(instance,'PrivateProcessAdapter',ApplicationAdapter):
            app=runner.start_application(lease,inputs,owned.append)
        self.assertEqual(app.port,58000);self.assertIn('58000',app.adapter.commands['api'].arguments)
        self.assertEqual(inputs.data_directory,'/synthetic-private/instance/data/postgresql')


if __name__=='__main__':unittest.main()
