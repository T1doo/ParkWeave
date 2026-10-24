"""Same-lease endpoint/config flow with existing in-memory files and fake crypto."""
from copy import copy, deepcopy
from dataclasses import replace
import hashlib
import pickle
from threading import get_ident, Thread
from unittest.mock import patch
import unittest

from . import credential_envelope as e, endpoint_plan as p, fixed_directories as d, fixed_journal as j
from . import fixed_secret_store as s
from .directories import LeaseRefused, NEXT
from .test_credential_envelope import binding, payloads
from .test_fixed_identity_journal import MemorySlotIO
from .test_fixed_secret_store import MemoryFiles, MemoryJournal
from .test_windows_user_protection import Buffers
from .windows_user_protection import IsolatedUserProtection


PROFILE=e.ConfigFormat.INSTANCE_SCHEMA3
REQUEST=p.EndpointRequest(54000,58000)


class EndpointPlanChecks(unittest.TestCase):
    def setUp(self):
        self.backing=dict(exists=False,held=False,raw=bytearray(),revision=0)
        self.dirs=d.FixedPrivateDirectories('/synthetic-private',format=j.FixedFormat.INSTANCE_V2)
        def filesystem():return MemorySlotIO(self.backing,self.dirs.journal_format)
        for fixture in (patch.object(self.dirs,'_filesystem',side_effect=filesystem),
                        patch.object(d,'_random_bytes',return_value=bytes(range(16)))):
            fixture.start();self.addCleanup(fixture.stop)
        self.leases=[];self.addCleanup(self.finish)
        self.lease=self.dirs.claim_fresh('/synthetic-private/instance');self.leases.append(self.lease)
        self.api=MemoryFiles(self.lease);self.crypto=Buffers();self.values=payloads()
        self.b=replace(binding(),instance_id=self.lease.instance_uuid())
        self.store=s.IsolatedFixedSecretStore(self.lease,self.b,self.api,IsolatedUserProtection(self.crypto),config_format=PROFILE)

    def finish(self):
        for lease in self.leases:
            if lease.active:lease.release()

    def phase(self,target):
        while self.lease.record['phase']!=target:
            phase=self.lease.record['phase']
            target_phase='CREATE_SCHEMA'if phase=='CLUSTER'else NEXT[phase]
            self.lease.checkpoint(target_phase,False,'STARTING')

    def complete(self):
        plan=p.create_new_plan(self.lease,REQUEST)
        self.phase('CREDENTIALS');self.store.create(e.Purpose.DATABASE,self.values[e.Purpose.DATABASE])
        self.phase('SESSIONS');self.store.create(e.Purpose.SESSION,self.values[e.Purpose.SESSION])
        self.phase('CONFIG');config=self.values[e.Purpose.CONFIG]
        self.store.publish_config(config['database'],config['runtime'],endpoint_plan=plan)
        self.phase('VERIFY_FILES')
        state=self.store.read_existing()
        self.assertEqual(state.config['schema'],3)
        self.assertEqual(state.config['endpoints'],p.endpoint_record(self.lease,plan,mode=p.PlanMode.NEW))
        return plan,state

    def reopen(self):
        plan,state=self.complete()
        self.lease.checkpoint('VERIFY_DATABASE',False,'STARTING')
        for phase,runtime in (('READY','STOPPED'),('APPLICATION','STARTING'),
                              ('RUNNING','RUNNING'),('READY_STOPPED','STOPPED')):
            self.lease.checkpoint(phase,True,runtime)
        self.lease.release()
        self.lease=self.dirs.open_existing('/synthetic-private/instance');self.leases.append(self.lease)
        self.api=MemoryFiles(self.lease,self.api.files);self.crypto=Buffers()
        self.store=s.IsolatedFixedSecretStore(self.lease,self.b,self.api,IsolatedUserProtection(self.crypto),config_format=PROFILE)
        return plan,state

    def assert_no_secret_writes(self):
        self.assertFalse(any(x[0]in('create','write','flush')for x in self.api.events if isinstance(x,tuple)))
        self.assertTrue(all(x[0]=='unprotect'for x in self.crypto.calls))

    def test_strict_request_and_endpoint_record_data(self):
        for ports in ((True,2),(1,False),(0,2),(1,65536),(2,2),('54000',58000),(1.0,2)):
            with self.subTest(ports=ports),self.assertRaises(p.EndpointRefused):p.EndpointRequest(*ports)
        for bad in (None,{},dict(schema='unknown',host='127.0.0.1',database_port=1,api_port=2),
                    dict(schema='parkweave-private-endpoints/1',host='localhost',database_port=1,api_port=2),
                    dict(schema='parkweave-private-endpoints/1',host='127.0.0.1',database_port=1,api_port=2,role='postgres')):
            with self.assertRaises(p.EndpointRefused):p.validate_record(bad)
        self.assertEqual(p.EndpointRequest(1,65535),p.EndpointRequest(1,65535))  # Data equality is not a plan.

    def test_exact_single_registration_forgery_copy_and_legal_sequence(self):
        plan=p.create_new_plan(self.lease,REQUEST)
        with self.assertRaises(p.EndpointRefused):p.create_new_plan(self.lease,REQUEST)
        for forged in (p.InstanceEndpointPlan(),REQUEST,object(),dict(database_port=54000,api_port=58000)):
            with self.assertRaises(p.EndpointRefused):p.endpoint_record(self.lease,forged,mode=p.PlanMode.NEW)
        for transfer in (copy,deepcopy,pickle.dumps):
            with self.assertRaises(TypeError):transfer(plan)
        before=p.endpoint_record(self.lease,plan,mode=p.PlanMode.NEW)
        before['api_port']=1
        self.lease.checkpoint('CREDENTIALS',False,'STARTING')
        self.assertEqual(p.endpoint_record(self.lease,plan,mode=p.PlanMode.NEW)['api_port'],58000)
        with self.assertRaises(p.EndpointRefused):p.endpoint_record(self.lease,plan,mode=p.PlanMode.REOPEN)
        self.assertFalse(self.lease.poisoned)

    def test_request_mutation_cannot_change_registered_values(self):
        request=p.EndpointRequest(54000,58000);plan=p.create_new_plan(self.lease,request)
        object.__setattr__(request,'api_port',58001)
        self.assertEqual(p.endpoint_record(self.lease,plan,mode=p.PlanMode.NEW)['api_port'],58000)

    def test_schema3_roundtrip_explicit_selection_and_unchanged_secret_bytes(self):
        config=deepcopy(self.values[e.Purpose.CONFIG]);config['schema']=3
        config['endpoints']=dict(schema='parkweave-private-endpoints/1',host='127.0.0.1',database_port=54000,api_port=58000)
        raw=e.encode_plaintext(self.b,e.Purpose.CONFIG,config,config_format=PROFILE)
        self.assertEqual(e.decode_plaintext(self.b,e.Purpose.CONFIG,raw,config_format=PROFILE),config)
        with self.assertRaises(e.EnvelopeRefused):e.decode_plaintext(self.b,e.Purpose.CONFIG,raw)
        old=e.encode_plaintext(self.b,e.Purpose.CONFIG,self.values[e.Purpose.CONFIG])
        with self.assertRaises(e.EnvelopeRefused):e.decode_plaintext(self.b,e.Purpose.CONFIG,old,config_format=PROFILE)
        for purpose in (e.Purpose.DATABASE,e.Purpose.SESSION):
            value=self.values[purpose]
            self.assertEqual(e.encode_plaintext(self.b,purpose,value),e.encode_plaintext(self.b,purpose,value,config_format=PROFILE))
        for wrong in (3,True,'INSTANCE_SCHEMA3'):
            with self.assertRaises(e.EnvelopeRefused):e.encode_plaintext(self.b,e.Purpose.CONFIG,config,config_format=wrong)
        for changes in ({'api_port':54000},{'database_port':False},{'host':'::1'},{'extra':1}):
            bad=deepcopy(config);bad['endpoints'].update(changes)
            with self.assertRaises(e.EnvelopeRefused):e.encode_plaintext(self.b,e.Purpose.CONFIG,bad,config_format=PROFILE)

    def test_schema2_default_bytes_and_entropy_match_original_commit(self):
        # Computed from exact parent 389cf19f's original pure codec, not this implementation.
        expected={
            'DATABASE':('3e5ac2b2fc3a4af426b70e2d1f768996e7b6fb4c22ea59f12102082e03b74536',
                        '107a15d1f5e292f3509048889ec18dfe86cfaa0d153fabcb85ac32a362e1de47'),
            'SESSION':('d2378b30e878ef3369285a935a5b9d3cf8febe2bb6b38db916173bc3aba496a0',
                       '411a995d85f0e42c01b93b1d352495b15243044abe1ec413690bf443e4004361'),
            'CONFIG':('cde46b772320d4f2f32f503d6a8b479b8e5c1d22cf53cdbbf4fa1d57557d12e0',
                      'a7d30920afc4517919ef34c9c39bdcd8ce3ef3dbacccd7725be2fe7c7e600291')}
        for purpose,value in self.values.items():
            raw=e.encode_plaintext(binding(),purpose,value)
            self.assertEqual((hashlib.sha256(raw).hexdigest(),e.entropy_bytes(binding(),purpose).hex()),expected[purpose.name])

    def test_schema3_store_requires_v2_lease_before_any_file_or_protection(self):
        fs=MemoryJournal();lease=d.FixedDirectoryLease(fs,fs.record,fs.snapshot)
        self.leases.append(lease);lease.checkpoint('CREDENTIALS',False,'STARTING')
        api=MemoryFiles(lease);crypto=Buffers()
        store=s.IsolatedFixedSecretStore(lease,binding(),api,IsolatedUserProtection(crypto),config_format=PROFILE)
        with self.assertRaises(s.StoreFailure):store.create(e.Purpose.DATABASE,self.values[e.Purpose.DATABASE])
        self.assertEqual(api.events,[]);self.assertEqual(crypto.calls,[])
        self.assertTrue(store.failed and lease.poisoned)

    def test_new_config_requires_exact_plan_and_correct_uuid_before_file_writes(self):
        self.phase('CREDENTIALS');self.store.binding=replace(self.b,instance_id=binding().instance_id)
        with self.assertRaises(s.StoreFailure):self.store.create(e.Purpose.DATABASE,self.values[e.Purpose.DATABASE])
        self.assertEqual(self.api.events,[]);self.assertTrue(self.store.failed and self.lease.poisoned)

    def test_config_rejects_unregistered_plan_before_any_config_object(self):
        self.phase('CONFIG');cfg=self.values[e.Purpose.CONFIG]
        with self.assertRaises(s.StoreFailure):self.store.publish_config(cfg['database'],cfg['runtime'],endpoint_plan=REQUEST)
        self.assertNotIn(e.Purpose.CONFIG,self.api.files)
        self.assertFalse(self.crypto.calls);self.assertTrue(self.lease.poisoned)

    def test_restore_registers_only_after_all_closes_final_verify_and_in_original_gate(self):
        old_plan,state=self.reopen();closed={};original_close=self.api.close
        original_register=p._register_held
        def close(cap):
            self.assertNotIn(self.lease,p._by_lease)
            with self.assertRaisesRegex(LeaseRefused,'FIXED_LEASE_OPERATION_BUSY'):self.lease.instance_uuid()
            result=original_close(cap)
            if not self.api.caps:closed['verifies']=self.lease.fs.verifies
            return result
        def register(lease,request,mode,**kwargs):
            self.assertFalse(self.api.caps);self.assertIn('verifies',closed)
            self.assertGreater(lease.fs.verifies,closed['verifies'])
            self.assertEqual(lease._operation_owner,get_ident());self.assertGreater(lease._operation_depth,0)
            self.assertIsNone(request)
            return original_register(lease,request,mode,**kwargs)
        with patch.object(self.api,'close',side_effect=close),patch.object(p,'_register_held',side_effect=register)as minted:
            restored,plan=self.store.read_existing_with_endpoint_plan()
        minted.assert_called_once();self.assertEqual(restored.config,state.config)
        self.assertEqual(p.endpoint_record(self.lease,plan,mode=p.PlanMode.REOPEN),state.config['endpoints'])
        with self.assertRaises(p.EndpointRefused):p.endpoint_record(self.lease,old_plan,mode=p.PlanMode.NEW)
        self.assert_no_secret_writes()

    def test_new_request_cannot_override_reopen_or_be_passed_as_recovery_source(self):
        self.reopen()
        with self.assertRaises(p.EndpointRefused):p.create_new_plan(self.lease,p.EndpointRequest(54001,58001))
        with self.assertRaises(TypeError):self.store.read_existing_with_endpoint_plan(REQUEST)
        state,plan=self.store.read_existing_with_endpoint_plan()
        self.assertEqual(p.endpoint_record(self.lease,plan,mode=p.PlanMode.REOPEN)['api_port'],58000)
        self.assertEqual(state.config['endpoints']['database_port'],54000);self.assert_no_secret_writes()

    def test_private_registration_without_closed_store_proof_is_not_a_recovery_source(self):
        self.reopen()
        @d._exclusive_entry
        def arbitrary_request(lease):return p._register_held(lease,REQUEST,p.PlanMode.REOPEN)
        with self.assertRaises(p.EndpointRefused):arbitrary_request(self.lease)
        self.assertNotIn(self.lease,p._by_lease)
        _,plan=self.store.read_existing_with_endpoint_plan()
        self.assertEqual(p.endpoint_record(self.lease,plan,mode=p.PlanMode.REOPEN)['api_port'],58000)

    def test_closed_completion_proof_is_exact_single_use_and_cleared(self):
        self.reopen();captured=[];original=p._register_held
        def register(lease,request,mode,**kwargs):
            token=kwargs['closed_recovery'];captured.append(token)
            denied=[]
            def outside_gate():
                try:s._consume_closed_endpoint_recovery(lease,token)
                except p.EndpointRefused:denied.append(True)
            thread=Thread(target=outside_gate);thread.start();thread.join(2)
            self.assertFalse(thread.is_alive());self.assertEqual(denied,[True])
            for forged in (s._ClosedEndpointRecovery(),{},object()):
                with self.assertRaises(p.EndpointRefused):s._consume_closed_endpoint_recovery(lease,forged)
            for transfer in (copy,deepcopy,pickle.dumps):
                with self.assertRaises(TypeError):transfer(token)
            result=original(lease,request,mode,**kwargs)
            with self.assertRaises(p.EndpointRefused):s._consume_closed_endpoint_recovery(lease,token)
            return result
        with patch.object(p,'_register_held',side_effect=register):
            _,plan=self.store.read_existing_with_endpoint_plan()
        self.assertEqual(len(captured),1);self.assertIsNone(self.store._endpoint_finalizing)
        self.assertNotIn(captured[0],s._closed_endpoint_recoveries)
        self.assertEqual(p.endpoint_record(self.lease,plan,mode=p.PlanMode.REOPEN)['database_port'],54000)

    def test_missing_session_never_mints_a_plan(self):
        self.reopen();del self.api.files[e.Purpose.SESSION]
        with patch.object(p,'_register_held',wraps=p._register_held)as minted:
            with self.assertRaises(s.StoreFailure):self.store.read_existing_with_endpoint_plan()
        minted.assert_not_called();self.assertNotIn(self.lease,p._by_lease)
        self.assert_no_secret_writes();self.assertTrue(self.lease.poisoned)

    def test_corrupt_config_endpoints_never_mint_despite_fake_unprotect_success(self):
        self.reopen();row=self.api.files[e.Purpose.CONFIG]
        before=row['raw'];row['raw']=before.replace(b'"api_port":58000',b'"api_port":58001')
        self.assertNotEqual(before,row['raw']);self.assertEqual(len(before),len(row['raw']))
        with patch.object(p,'_register_held',wraps=p._register_held)as minted:
            with self.assertRaises(s.StoreFailure):self.store.read_existing_with_endpoint_plan()
        minted.assert_not_called();self.assertNotIn(self.lease,p._by_lease)
        self.assert_no_secret_writes();self.assertTrue(self.lease.poisoned)

    def test_changed_file_identity_refuses_before_registration(self):
        self.reopen();row=self.api.files[e.Purpose.SESSION]
        row['info']=replace(row['info'],identity=(7,999))
        with patch.object(p,'_register_held',wraps=p._register_held)as minted:
            with self.assertRaises(s.StoreFailure):self.store.read_existing_with_endpoint_plan()
        minted.assert_not_called();self.assertNotIn(self.lease,p._by_lease)
        self.assert_no_secret_writes();self.assertTrue(self.lease.poisoned)

    def test_close_failure_never_registers_even_when_all_fake_handles_are_gone(self):
        self.reopen();self.api.close_unknown=True
        with patch.object(p,'_register_held',wraps=p._register_held)as minted:
            with self.assertRaises(s.StoreFailure):self.store.read_existing_with_endpoint_plan()
        minted.assert_not_called();self.assertFalse(self.api.caps);self.assertNotIn(self.lease,p._by_lease)
        self.assert_no_secret_writes();self.assertTrue(self.store.failed and self.lease.poisoned)

    def test_final_lease_check_failure_after_close_never_registers_or_repairs(self):
        self.reopen();original_close=self.api.close;before=bytes(self.backing['raw'])
        def close(cap):
            result=original_close(cap)
            if not self.api.caps:self.lease.fs.closed=True
            return result
        with patch.object(self.api,'close',side_effect=close),patch.object(p,'_register_held',wraps=p._register_held)as minted:
            with self.assertRaises(s.StoreFailure):self.store.read_existing_with_endpoint_plan()
        minted.assert_not_called();self.assertNotIn(self.lease,p._by_lease)
        self.assertEqual(bytes(self.backing['raw']),before);self.assertTrue(self.lease.poisoned)
        self.assert_no_secret_writes()

    def test_registration_exception_after_close_uses_unknown_and_poison(self):
        self.reopen()
        with patch.object(p,'_register_held',side_effect=RuntimeError('SYNTHETIC_REGISTRATION_FAILURE')):
            with self.assertRaises(s.StoreFailure)as raised:self.store.read_existing_with_endpoint_plan()
        self.assertIsInstance(raised.exception.primary,RuntimeError)
        self.assertEqual(self.lease.record['phase'],'UNKNOWN')
        self.assertFalse(self.api.caps);self.assertNotIn(self.lease,p._by_lease)
        self.assertTrue(self.store.failed and self.lease.poisoned);self.assert_no_secret_writes()

    def test_exception_after_partial_registration_leaves_no_usable_plan(self):
        self.reopen();captured=[];original=p._register_held
        def fail_after_register(*args,**kwargs):
            captured.append(original(*args,**kwargs));raise RuntimeError('SYNTHETIC_POST_REGISTER_FAILURE')
        with patch.object(p,'_register_held',side_effect=fail_after_register):
            with self.assertRaises(s.StoreFailure):self.store.read_existing_with_endpoint_plan()
        self.assertEqual(len(captured),1)
        with self.assertRaises(LeaseRefused):p.endpoint_record(self.lease,captured[0],mode=p.PlanMode.REOPEN)
        self.assertTrue(self.store.failed and self.lease.poisoned);self.assertEqual(self.lease.record['phase'],'UNKNOWN')

    def test_generation_is_bound_but_sequence_is_not(self):
        plan,state=self.complete()
        self.lease.checkpoint('VERIFY_DATABASE',False,'STARTING')
        for phase,runtime in (('READY','STOPPED'),('APPLICATION','STARTING'),
                              ('RUNNING','RUNNING'),('READY_STOPPED','STOPPED')):
            self.lease.checkpoint(phase,True,runtime)
        self.assertEqual(p.endpoint_record(self.lease,plan,mode=p.PlanMode.NEW),state.config['endpoints'])
        self.lease._publish(dict(handoff='RELEASE_PENDING'))
        newer={**self.lease.record,'generation':2,'sequence':self.lease.record['sequence']+1,'handoff':'OWNED'}
        snapshot=self.lease.fs.replace(j.encode(newer),self.lease.snapshot)
        self.lease.record,self.lease.snapshot=newer,snapshot
        with self.assertRaises(p.EndpointRefused):p.endpoint_record(self.lease,plan,mode=p.PlanMode.NEW)

    def test_duplicate_restore_is_not_reissued_and_enters_unknown(self):
        self.reopen();_,plan=self.store.read_existing_with_endpoint_plan()
        self.assertEqual(p.endpoint_record(self.lease,plan,mode=p.PlanMode.REOPEN)['api_port'],58000)
        with self.assertRaises(s.StoreFailure):self.store.read_existing_with_endpoint_plan()
        self.assertTrue(self.store.failed and self.lease.poisoned)
        with self.assertRaises(LeaseRefused):p.endpoint_record(self.lease,plan,mode=p.PlanMode.REOPEN)


if __name__=='__main__':unittest.main()
