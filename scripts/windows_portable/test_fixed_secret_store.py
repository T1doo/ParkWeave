"""Actual store/lease logic with in-memory files, metadata and protection doubles."""
from copy import deepcopy
from dataclasses import replace
import json
import threading
import traceback
import unittest

from . import credential_envelope as e, fixed_journal as j, fixed_secret_store as s
from .directories import LeaseRefused, NEXT
from .fixed_directories import FixedDirectoryLease
from .test_credential_envelope import binding, payloads
from .test_windows_user_protection import Buffers
from .windows_user_protection import IsolatedUserProtection


SENTINEL = 'SYNTHETIC_STORAGE_ERROR_NOT_FOR_PUBLIC_OUTPUT'


class MemoryJournal:
    def __init__(self, record=None):
        self.record = record or dict(schema=j.SCHEMA, root=[7,11], lock=[7,12], journal=[7,13],
            generation=1, sequence=2, phase='NEW', initialized=False, runtime='STOPPED', handoff='OWNED')
        self.snapshot = (j.encode(self.record), self.record['sequence']); self.closed = False
        self.fail_publish = False; self.verifies = 0

    def verify(self):
        self.verifies += 1
        if self.closed: raise LeaseRefused('SYNTHETIC_CLOSED')

    def read(self): return self.snapshot

    def replace(self, raw, expected):
        if self.fail_publish: raise OSError(SENTINEL)
        assert expected == self.snapshot
        new = j.decode(raw); j.transition(self.record, new)
        self.record = new; self.snapshot = (raw, new['sequence'])
        return self.snapshot

    def close(self): self.closed = True


class MemoryFiles(s.FakeSecretAPI):
    def __init__(self, lease, files=None):
        self.lease = lease; self.files = files if files is not None else {}
        self.dir = s.ObjectInfo((7,100),(7,11),'secrets',True,binding().sid,0x1004,b'FAKE_ACL',True,False,1,0,0)
        self.caps = {}; self.events = []; self.hook = None; self.short = False
        self.flush_unknown = False; self.read_corrupt = False; self.write_error = False
        self.close_errors = False; self.close_unknown = False; self.before_change = None; self.close_hook = None

    def binds(self, lease): return lease is self.lease

    def _new(self, purpose):
        cap = s.FakeCapability(); self.caps[cap] = purpose; return cap

    def open_secrets(self, lease):
        assert lease is self.lease
        self.events.append('open_secrets'); return self._new(None)

    def open_file(self, directory, purpose, *, create):
        assert self.caps[directory] is None and type(purpose) is e.Purpose
        self.events.append(('create' if create else 'open', purpose.value))
        if create:
            if purpose in self.files: raise FileExistsError('SYNTHETIC_ALREADY_EXISTS')
            info = replace(self.dir, identity=(7,200+list(e.Purpose).index(purpose)), parent=self.dir.identity,
                           leaf=s.NAMES[purpose], directory=False)
            self.files[purpose] = dict(info=info, raw=b'')
            self.dir = replace(self.dir, revision=self.dir.revision+1)
        elif purpose not in self.files: raise FileNotFoundError('SYNTHETIC_MISSING')
        return self._new(purpose)

    def owns(self, cap, lease, parent):
        return cap in self.caps and lease is self.lease and (parent is None if self.caps[cap] is None else parent in self.caps and self.caps[parent] is None)

    def inspect(self, cap):
        purpose = self.caps[cap]
        return self.dir if purpose is None else self.files[purpose]['info']

    def creation_descriptor(self, cap):
        info = self.inspect(cap)
        result = (info.owner, info.control, info.raw_dacl)
        return self.before_change(result) if self.before_change else result

    def write(self, cap, raw):
        purpose = self.caps[cap]; self.events.append(('write', purpose.value))
        if self.write_error: raise RuntimeError(SENTINEL)
        count = len(raw)-1 if self.short else len(raw)
        self.files[purpose]['raw'] = raw[:count]
        self.files[purpose]['info'] = replace(self.files[purpose]['info'], size=count, revision=1)
        if self.hook: self.hook(self, cap)
        return count

    def flush(self, cap):
        self.events.append(('flush', self.caps[cap].value)); return not self.flush_unknown

    def read(self, cap, limit):
        purpose = self.caps[cap]; self.events.append(('read', purpose.value))
        raw = self.files[purpose]['raw']
        return (b'X'+raw[1:] if self.read_corrupt else raw)[:limit]

    def close(self, cap):
        if self.close_hook: self.close_hook()
        purpose = self.caps[cap]; self.events.append(('close', purpose.value if purpose else 'secrets'))
        del self.caps[cap]
        if self.close_errors: raise OSError(SENTINEL)
        return not self.close_unknown


class FixedStoreChecks(unittest.TestCase):
    def setUp(self):
        self.fs = MemoryJournal(); self.lease = FixedDirectoryLease(self.fs,self.fs.record,self.fs.snapshot)
        self.api = MemoryFiles(self.lease); self.crypto = Buffers()
        self.store = s.IsolatedFixedSecretStore(self.lease,binding(),self.api,IsolatedUserProtection(self.crypto))
        self.values = payloads()

    def phase(self, target):
        while self.lease.record['phase'] != target:
            current = self.lease.record['phase']
            next_phase = 'CREATE_SCHEMA' if current == 'CLUSTER' else NEXT[current]
            self.lease.checkpoint(next_phase,False,'STARTING')

    def database(self):
        self.phase('CREDENTIALS'); return self.store.create(e.Purpose.DATABASE,self.values[e.Purpose.DATABASE])

    def complete(self):
        self.database(); self.phase('SESSIONS'); self.store.create(e.Purpose.SESSION,self.values[e.Purpose.SESSION])
        self.phase('CONFIG'); cfg=self.values[e.Purpose.CONFIG]
        self.store.publish_config(cfg['database'],cfg['runtime']); self.phase('VERIFY_FILES')
        return self.store.read_existing()

    def assert_failed(self):
        self.assertTrue(self.store.failed and self.lease.poisoned)
        self.assertEqual(self.fs.record['phase'],'UNKNOWN')
        before=list(self.api.events)
        with self.assertRaises(s.StoreRefused): self.store.read_existing()
        self.assertEqual(before,self.api.events)

    def test_full_flow_config_last_and_reopen_reads_without_any_secret_writes(self):
        self.api.before_change=lambda x:(x[0],x[1]|1,x[2])  # Only OWNER_DEFAULTED may differ at creation.
        state=self.complete(); self.assertEqual(state.database,self.values[e.Purpose.DATABASE])
        self.assertEqual(state.sessions,self.values[e.Purpose.SESSION]); self.assertNotIn('SYNTHETIC',repr(state))
        self.assertEqual([x for x in self.api.events if isinstance(x,tuple)and x[0]=='create'],
                         [('create','DATABASE'),('create','SESSION'),('create','CONFIG')])
        for p in (e.Purpose.DATABASE,e.Purpose.SESSION):
            self.assertEqual(state.config['files'][p.value]['identity'],list(self.api.files[p]['info'].identity))
        self.assertFalse(self.api.caps)
        # Simulate the existing journal handoff, not native acquisition/durability.
        self.lease.checkpoint('VERIFY_DATABASE',False,'STARTING'); self.lease.checkpoint('READY',True,'STOPPED')
        self.lease.checkpoint('APPLICATION',True,'STARTING'); self.lease.checkpoint('RUNNING',True,'RUNNING')
        self.lease.checkpoint('READY_STOPPED',True,'STOPPED'); self.lease.release()
        record={**self.fs.record,'generation':2,'sequence':self.fs.record['sequence']+1,'handoff':'OWNED'}
        j.transition(self.fs.record,record); fs=MemoryJournal(record); lease=FixedDirectoryLease(fs,record,fs.snapshot)
        api=MemoryFiles(lease,self.api.files); crypto=Buffers()
        store=s.IsolatedFixedSecretStore(lease,binding(),api,IsolatedUserProtection(crypto))
        self.assertEqual(store.read_existing().config,state.config)
        self.assertFalse(any(x[0] in ('create','write','flush') for x in api.events if isinstance(x,tuple)))
        self.assertTrue(all(x[0]=='unprotect' for x in crypto.calls))

    def test_closed_names_phase_and_native_factory(self):
        for purpose in ('DATABASE','../file',e.Purpose.CONFIG):
            with self.subTest(purpose=purpose),self.assertRaises(s.StoreRefused):self.store.create(purpose,{})
        self.assertEqual(self.api.events,[])
        with self.assertRaisesRegex(s.StoreRefused,'NATIVE_FIXED_SECRET_CAPABILITIES_NOT_ACCEPTED'):s.native_fixed_secret_store()
        with self.assertRaises(s.StoreFailure):self.store.create(e.Purpose.DATABASE,self.values[e.Purpose.DATABASE])
        self.assertEqual(self.api.events,[]);self.assert_failed()

    def test_config_requires_two_existing_verified_files(self):
        self.phase('CONFIG'); cfg=self.values[e.Purpose.CONFIG]
        with self.assertRaises(s.StoreFailure):self.store.publish_config(cfg['database'],cfg['runtime'])
        self.assertNotIn(e.Purpose.CONFIG,self.api.files);self.assert_failed()

    def test_short_write_flush_unknown_and_corruption_keep_original_object(self):
        for flag in ('short','flush_unknown','read_corrupt'):
            with self.subTest(fault=flag):
                self.setUp();setattr(self.api,flag,True)
                with self.assertRaises(s.StoreFailure):self.database()
                self.assertIn(e.Purpose.DATABASE,self.api.files);self.assert_failed()
                self.assertEqual(sum(x==('create','DATABASE')for x in self.api.events),1)

    def test_raw_dacl_control_owner_and_object_drift_refuse(self):
        changes=[dict(owner='S-1-5-21-1-2-3-1002'),dict(control=0x1005),dict(raw_dacl=b'CHANGED!'),
                 dict(reparse=True),dict(links=2),dict(identity=(7,11)),dict(private_acl_checked=False)]
        for change in changes:
            with self.subTest(metadata=tuple(change)):
                self.setUp()
                def mutate(api,cap):
                    row=api.files[api.caps[cap]];row['info']=replace(row['info'],**change)
                self.api.hook=mutate
                with self.assertRaises(s.StoreFailure):self.database()
                self.assert_failed()
        self.setUp();self.api.before_change=lambda x:(x[0],x[1],b'BEFORE!!')
        with self.assertRaises(s.StoreFailure):self.database()
        self.assertFalse(any(x[0]=='write'for x in self.api.events if isinstance(x,tuple)));self.assert_failed()

    def test_primary_close_and_unknown_journal_failures_remain_private(self):
        self.phase('CREDENTIALS');self.api.write_error=True;self.api.close_errors=True;self.fs.fail_publish=True
        with self.assertRaises(s.StoreFailure)as raised:self.store.create(e.Purpose.DATABASE,self.values[e.Purpose.DATABASE])
        error=raised.exception;self.assertIsInstance(error.primary,RuntimeError)
        self.assertEqual(len(error.cleanup),2);self.assertIsInstance(error.journal_error,OSError)
        self.assertEqual(len(self.store._unknown_caps),2)
        self.assertTrue(self.store.failed and self.lease.poisoned)
        self.assertNotIn(SENTINEL,str(error)+repr(error)+json.dumps(error.public())+''.join(traceback.format_exception(error)))
        before=list(self.api.events)
        with self.assertRaises(s.StoreRefused):self.store.read_existing()
        self.assertEqual(self.api.events,before)

    def test_close_false_is_unknown_and_never_retried(self):
        self.api.close_unknown=True
        with self.assertRaises(s.StoreFailure):self.database()
        self.assertEqual(len(self.store._unknown_caps),2);self.assert_failed()

    def test_existing_object_is_not_overwritten_or_reprotected(self):
        self.database(); original=self.api.files[e.Purpose.DATABASE]['raw'];calls=len(self.crypto.calls)
        with self.assertRaises(s.StoreFailure):self.database()
        self.assertEqual(self.api.files[e.Purpose.DATABASE]['raw'],original)
        self.assertEqual(len(self.crypto.calls),calls);self.assert_failed()

    def test_wrong_binding_or_unknown_capability_is_not_used(self):
        self.phase('CREDENTIALS');self.store.binding=replace(binding(),root=(7,999))
        with self.assertRaises(s.StoreFailure):self.database()
        self.assertEqual(self.api.events,[]);self.assert_failed()
        self.setUp();self.api.owns=lambda *args:False
        with self.assertRaises(s.StoreFailure):self.database()
        self.assertEqual(self.api.events,['open_secrets']);self.assert_failed()
        self.setUp()
        self.api.hook=lambda *args:setattr(self.api,'owns',lambda *args:False)
        with self.assertRaises(s.StoreFailure):self.database()
        self.assertFalse(any(x[0]=='close'for x in self.api.events if isinstance(x,tuple)))
        self.assertEqual(len(self.store._unknown_caps),2);self.assert_failed()
        self.setUp();self.phase('CREDENTIALS')
        def root_failure():raise OSError(SENTINEL)
        self.fs.verify=root_failure
        with self.assertRaises(s.StoreFailure)as raised:self.store.create(e.Purpose.DATABASE,self.values[e.Purpose.DATABASE])
        self.assertIsInstance(raised.exception.primary,OSError)
        self.assertNotIn(SENTINEL,str(raised.exception))
        self.assertTrue(self.store.failed and self.lease.poisoned);self.assertEqual(self.api.events,[])

    def test_same_lease_gate_rejects_reentry_and_real_thread_contender(self):
        entered=threading.Event();resume=threading.Event();errors=[];rejected=[];close_rejected=[]
        self.phase('CREDENTIALS')
        def wait(api,cap):
            for action,args in ((self.lease.release,()),(self.lease.status,()),(self.store.read_existing,())):
                try:action(*args)
                except LeaseRefused as error:
                    self.assertEqual(error.args,('FIXED_LEASE_OPERATION_BUSY',));rejected.append(True)
            entered.set()
            if not resume.wait(2):raise RuntimeError('SYNTHETIC_THREAD_DEADLINE')
        self.api.hook=wait
        def close_probe():
            for action in (self.lease.status,self.lease.release):
                try:action()
                except LeaseRefused as error:
                    self.assertEqual(error.args,('FIXED_LEASE_OPERATION_BUSY',));close_rejected.append(True)
        self.api.close_hook=close_probe
        def work():
            try:self.store.create(e.Purpose.DATABASE,self.values[e.Purpose.DATABASE])
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=work);thread.start()
        try:
            self.assertTrue(entered.wait(2));before=list(self.api.events)
            with self.assertRaisesRegex(LeaseRefused,'FIXED_LEASE_OPERATION_BUSY'):self.lease.release()
            self.assertEqual(self.api.events,before)
        finally:resume.set();thread.join(3)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[]);self.assertEqual(len(rejected),3)
        self.assertEqual(len(close_rejected),4)
        self.assertFalse(self.lease.poisoned or self.store.failed)

    def test_reopen_mismatch_or_missing_file_has_zero_secret_writes(self):
        for fault in ('missing','changed_cipher','wrong_reference'):
            with self.subTest(fault=fault):
                self.setUp();self.complete();self.api.events.clear();self.crypto.calls.clear()
                if fault=='missing':del self.api.files[e.Purpose.SESSION]
                elif fault=='changed_cipher':
                    self.api.files[e.Purpose.DATABASE]['raw']=self.api.files[e.Purpose.DATABASE]['raw'].replace(b'SYNTHETIC_OWNER',b'SYNTHETIC_OWNEX')
                else:
                    row=self.api.files[e.Purpose.SESSION];row['info']=replace(row['info'],identity=(7,999))
                with self.assertRaises(s.StoreFailure):self.store.read_existing()
                self.assertFalse(any(x[0]in('create','write','flush')for x in self.api.events if isinstance(x,tuple)))
                self.assertTrue(all(x[0]=='unprotect'for x in self.crypto.calls));self.assert_failed()


if __name__=='__main__':unittest.main()
