"""V2 bytes and original held-lease flow, using only the existing memory fake.

No real directory, random source, Windows API, credentials or process is used.
"""
import hashlib
from unittest.mock import patch
import unittest

from . import fixed_journal as j, fixed_directories as d
from .directories import LeaseRefused
from .test_fixed_secret_store import MemoryJournal


V2 = j.FixedFormat.INSTANCE_V2
UUID_A = '00010203-0405-4607-8809-0a0b0c0d0e0f'
UUID_B = '11111111-1111-4111-8111-111111111111'


def initial(format=V2):
    value = dict(schema=j.schema(format), root=[7,11], lock=[7,12], journal=[7,13],
                 generation=1, sequence=2, phase='NEW', initialized=False, runtime='STOPPED', handoff='OWNED')
    if format is V2: value['instance_id'] = UUID_A
    return value


class MemorySlotIO(MemoryJournal):
    """Extend the previous memory journal fake with fixed-offset byte IO only."""
    def __init__(self, backing, format):
        super().__init__()
        self.backing, self._journal_format = backing, format
        self.root_id, self.lock_id, self.journal_id = [7,11], [7,12], [7,13]
        self.pinned = (tuple(self.root_id), tuple(self.lock_id), tuple(self.journal_id))
        self.owned = False; self.close_calls = 0; self.writes = []; self.flushes = 0
        self.short = self.flush_error = self.bad_readback = self.close_error = False
        self.storage = j.FixedJournal(self, format=format)

    @property
    def journal_format(self): return self._journal_format

    def acquire(self, name, *, fresh):
        assert name == 'instance'
        if fresh:
            if self.backing['exists']: raise FileExistsError('SYNTHETIC_EXISTING_ROOT')
            self.backing['exists'] = True
        elif not self.backing['exists']: raise FileNotFoundError('SYNTHETIC_MISSING_ROOT')
        if self.backing['held']: raise LeaseRefused('SYNTHETIC_BUSY')
        self.backing['held'] = self.owned = True
        self.verify()

    def verify(self):
        super().verify()
        if not self.owned or not self.backing['held']:
            raise LeaseRefused('SYNTHETIC_OWNERSHIP_LOST')
        if self.pinned != (tuple(self.root_id), tuple(self.lock_id), tuple(self.journal_id)):
            raise LeaseRefused('SYNTHETIC_OBJECT_DRIFT')

    def identity(self): return self.journal_id
    def length(self): return len(self.backing['raw'])
    def signature(self): return self.pinned, self.backing['revision']

    def read_at(self, offset, count):
        raw = bytes(self.backing['raw'][offset:offset+count])
        return b'X'+raw[1:] if self.bad_readback and self.writes and raw else raw

    def write_at(self, offset, raw):
        self.writes.append((offset, len(raw)))
        count = len(raw)-1 if self.short else len(raw)
        target = self.backing['raw']
        if len(target) < offset+count: target.extend(bytes(offset+count-len(target)))
        target[offset:offset+count] = raw[:count]
        self.backing['revision'] += 1
        return count

    def flush_file(self):
        self.flushes += 1
        if self.flush_error: raise OSError('SYNTHETIC_FLUSH_UNKNOWN')

    def read(self): return self.storage.read()
    def replace(self, raw, expected): return self.storage.write(raw, expected)

    def close(self):
        self.close_calls += 1
        if self.owned: self.backing['held'] = False
        self.owned = False
        super().close()
        if self.close_error: raise OSError('SYNTHETIC_CLOSE_UNKNOWN')


class IdentityJournalChecks(unittest.TestCase):
    def setUp(self):
        self.backing = dict(exists=False, held=False, raw=bytearray(), revision=0)
        self.dirs = d.FixedPrivateDirectories('/synthetic-private', format=V2)
        self.ios = []; self.leases = []; self.setup_io = lambda io: None
        def filesystem():
            io = MemorySlotIO(self.backing, self.dirs.journal_format)
            self.ios.append(io); self.setup_io(io); return io
        filesystem_patch=patch.object(self.dirs, '_filesystem', side_effect=filesystem)
        self.addCleanup(filesystem_patch.stop);filesystem_patch.start()
        random_patch=patch.object(d, '_random_bytes', return_value=bytes(range(16)))
        self.addCleanup(random_patch.stop);self.random=random_patch.start()
        self.addCleanup(self.finish)

    def finish(self):
        for lease in self.leases:
            if lease.active: lease.release()

    def acquire(self, fresh=True):
        method = self.dirs.claim_fresh if fresh else self.dirs.open_existing
        lease = method('/synthetic-private/instance'); self.leases.append(lease); return lease

    def advance(self, lease, reopen=False):
        phases = ('CLUSTER','VERIFY_DATABASE') if reopen else (
            'CREDENTIALS','CLUSTER','CREATE_SCHEMA','ROLES','SESSIONS','SEED','CONFIG','VERIFY_FILES','VERIFY_DATABASE')
        for phase in phases:
            lease.checkpoint(phase, reopen, 'STARTING')
            self.assertEqual(lease.instance_uuid(), UUID_A)
        for phase, runtime in (('READY','STOPPED'),('APPLICATION','STARTING'),
                               ('RUNNING','RUNNING'),('READY_STOPPED','STOPPED')):
            lease.checkpoint(phase, True, runtime)
            self.assertEqual(lease.instance_uuid(), UUID_A)

    def test_initial_single_draw_two_slots_and_full_cross_generation_flow(self):
        lease = self.acquire(); io = self.ios[-1]
        self.random.assert_called_once_with(); self.assertEqual(lease.record, initial())
        self.assertEqual(io.writes, [(0,8192)]); self.assertEqual(io.flushes,1)
        image = bytes(self.backing['raw'])
        for slot, seq in ((0,1),(1,2)):
            record, previous = j.parse_slot(image[slot*j.SLOT:(slot+1)*j.SLOT],slot,format=V2)
            self.assertEqual(record, {**initial(),'sequence':seq})
            self.assertEqual(previous,j.ZERO_HASH if slot==0 else hashlib.sha256(image[:j.SLOT]).digest())
        self.advance(lease); lease.release()
        pending = j.pair(bytes(self.backing['raw']),format=V2)[0]
        self.assertEqual(pending['handoff'],'RELEASE_PENDING')
        reopened = self.acquire(False)
        self.assertEqual(reopened.record['sequence'],pending['sequence']+1)
        self.assertEqual(reopened.record['generation'],2)
        self.assertEqual(reopened.record['handoff'],'OWNED')
        self.assertEqual(reopened.instance_uuid(),UUID_A); self.random.assert_called_once_with()
        self.advance(reopened,True)

    def test_initial_sequence_one_is_never_independently_published(self):
        io = MemorySlotIO(self.backing,V2); io.acquire('instance',fresh=True)
        for record in ({**initial(),'sequence':1},{**initial(),'phase':'CREDENTIALS','runtime':'STARTING'}):
            with self.assertRaises(LeaseRefused): io.replace(j.encode(record),None)
        self.assertEqual(io.writes,[]); self.assertEqual(io.length(),0); io.close()

    def test_closed_format_selection_and_no_codec_fallback(self):
        for wrong in (True,2,'INSTANCE_V2',object()):
            with self.assertRaises(LeaseRefused): d.FixedPrivateDirectories('/synthetic-private',format=wrong)
            with self.assertRaises(LeaseRefused): j.decode(j.encode(initial()),format=wrong)
        lease = self.acquire(); old = bytes(self.backing['raw'])
        with self.assertRaises(LeaseRefused): j.pair(old)  # Default remains V1.
        lease.release(); old=bytes(self.backing['raw'])
        self.dirs._journal_format=j.FixedFormat.V1
        with self.assertRaises(LeaseRefused): self.acquire(False)
        self.assertEqual(bytes(self.backing['raw']),old);self.assertEqual(self.ios[-1].writes,[])

    def test_uuid_getter_original_operation_gate_and_read_only_snapshot(self):
        lease=self.acquire();io=self.ios[-1];before=list(io.writes)
        self.assertEqual(lease.instance_uuid(),UUID_A);self.assertEqual(io.writes,before)
        with self.assertRaisesRegex(LeaseRefused,'FIXED_LEASE_OPERATION_BUSY'):
            self._reenter(lease)
        lease.poisoned=True
        with self.assertRaises(LeaseRefused):lease.instance_uuid()
        lease.release()
        with self.assertRaises(LeaseRefused):lease.instance_uuid()

    @staticmethod
    @d._exclusive_entry
    def _reenter(lease): return lease.instance_uuid()

    def test_default_v1_golden_initial_bytes_and_no_random_source(self):
        self.dirs._journal_format=j.FixedFormat.V1
        lease=self.acquire();raw=bytes(self.backing['raw'])
        self.assertEqual(lease.record,initial(j.FixedFormat.V1));self.random.assert_not_called()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         'b186a83544e93eaee92ea39c137fa40339506d79bce74535a9d31381b82d167c')
        with self.assertRaises(LeaseRefused):lease.instance_uuid()
        with self.assertRaises(LeaseRefused):j.pair(raw,format=V2)
        self.assertFalse(lease.poisoned)
        # A valid stopped V1 image is still not a V2 migration source.
        for phase in ('CREDENTIALS','CLUSTER','CREATE_SCHEMA','ROLES','SESSIONS','SEED',
                      'CONFIG','VERIFY_FILES','VERIFY_DATABASE'):
            lease.checkpoint(phase,False,'STARTING')
        for phase,runtime in (('READY','STOPPED'),('APPLICATION','STARTING'),
                              ('RUNNING','RUNNING'),('READY_STOPPED','STOPPED')):
            lease.checkpoint(phase,True,runtime)
        lease.release();original=bytes(self.backing['raw'])
        self.dirs._journal_format=V2
        with self.assertRaises(LeaseRefused):self.acquire(False)
        self.assertEqual(bytes(self.backing['raw']),original)
        self.assertEqual(self.ios[-1].writes,[]);self.random.assert_not_called()

    def test_strict_uuid_types_and_closed_fields(self):
        for change in ({'instance_id':UUID_A.upper()},{'instance_id':'00000000-0000-0000-0000-000000000000'},
                       {'instance_id':1},{'instance_id':'x'*1000},{'generation':True},
                       {'root':[True,11]},{'journal':[7,12]},{'journal':[8,13]},
                       {'extra':0}):
            with self.subTest(field=tuple(change)),self.assertRaises(LeaseRefused):
                j.decode(j.encode({**initial(),**change}),format=V2)
        raw=j.encode(initial())
        for bad in (raw+b'\n',raw.replace(b'"instance_id":',b'"instance_id":"x","instance_id":'),
                    raw.replace(b'"schema":"parkweave-directory-fixed/2"',b'"schema":"unknown"')):
            with self.assertRaises(LeaseRefused):j.decode(bad,format=V2)

    def test_mixed_uuid_version_single_slot_and_damage_keep_original(self):
        lease=self.acquire();self.advance(lease);lease.release()
        image=bytes(self.backing['raw']); latest,index=j.pair(image,format=V2)
        previous=j.parse_slot(image[(1-index)*j.SLOT:(2-index)*j.SLOT],1-index,format=V2)[0]
        older=j.slot_bytes(previous,1-index,j.ZERO_HASH,format=V2)
        mixed=j.slot_bytes({**latest,'instance_id':UUID_B},index,hashlib.sha256(older).digest(),format=V2)
        v1={k:v for k,v in latest.items() if k!='instance_id'};v1['schema']=j.SCHEMA
        mixed_version=j.slot_bytes(v1,index,hashlib.sha256(older).digest())
        assemble=lambda slot: older+slot if index==1 else slot+older
        cases=[assemble(mixed),assemble(mixed_version),image[:j.SLOT],image[:-1],
               b'X'+image[1:],image[:j.SLOT]+bytes(j.SLOT)]
        for raw in cases:
            with self.subTest(length=len(raw)):
                self.backing['raw']=bytearray(raw)
                with self.assertRaises(LeaseRefused):self.acquire(False)
                self.assertEqual(bytes(self.backing['raw']),raw)
                self.assertEqual(self.ios[-1].writes,[]);self.assertEqual(self.ios[-1].close_calls,1)
        self.random.assert_called_once_with()

    def test_initial_random_write_flush_and_readback_failures_are_not_retried(self):
        faults=('random_error','random_short','short','flush_error','bad_readback')
        for fault in faults:
            with self.subTest(fault=fault):
                self.backing.update(exists=False,held=False,raw=bytearray(),revision=0)
                self.random.reset_mock(side_effect=True,return_value=True)
                self.random.return_value=bytes(range(16));self.setup_io=lambda io:None
                if fault=='random_error':self.random.side_effect=OSError('SYNTHETIC_RANDOM_FAILURE')
                elif fault=='random_short':self.random.return_value=b'x'
                else:self.setup_io=lambda io:setattr(io,fault,True)
                with self.assertRaises((LeaseRefused,OSError)):self.acquire()
                io=self.ios[-1];original=bytes(self.backing['raw'])
                self.random.assert_called_once_with();self.assertEqual(io.close_calls,1)
                self.assertEqual(len(io.writes),0 if fault.startswith('random') else 1)
                with self.assertRaises(FileExistsError):self.acquire()
                self.random.assert_called_once_with();self.assertEqual(bytes(self.backing['raw']),original)

    def test_acquisition_identity_or_ownership_drift_after_draw_refuses_before_write(self):
        for field in ('root_id','lock_id','journal_id','ownership'):
            with self.subTest(field=field):
                self.backing.update(exists=False,held=False,raw=bytearray(),revision=0)
                def draw():
                    io=self.ios[-1]
                    if field=='ownership':io.owned=False;self.backing['held']=False
                    else:setattr(io,field,[7,999])
                    return bytes(range(16))
                self.random.side_effect=draw
                with self.assertRaises(LeaseRefused):self.acquire()
                self.assertEqual(self.ios[-1].writes,[]);self.assertEqual(self.ios[-1].close_calls,1)

    def test_acquisition_primary_and_close_unknown_keep_both_without_retry(self):
        self.random.side_effect=OSError('SYNTHETIC_RANDOM_FAILURE')
        self.setup_io=lambda io:setattr(io,'close_error',True)
        with self.assertRaises(BaseExceptionGroup)as raised:self.acquire()
        errors=raised.exception.exceptions
        self.assertEqual(len(errors),2)
        self.assertEqual(errors[0].args,('SYNTHETIC_RANDOM_FAILURE',))
        self.assertEqual(errors[1].args,('SYNTHETIC_CLOSE_UNKNOWN',))
        self.assertEqual(self.ios[-1].close_calls,1);self.assertEqual(self.ios[-1].writes,[])
        self.assertTrue(self.backing['exists']);self.random.assert_called_once_with()

    def test_reopen_generation_failure_preserves_unknown_and_no_redraw_or_repair(self):
        lease=self.acquire();self.advance(lease);lease.release()
        self.setup_io=lambda io:setattr(io,'flush_error',True)
        with self.assertRaises(OSError):self.acquire(False)
        original=bytes(self.backing['raw'])
        observed,_=j.pair(original,format=V2)
        self.assertEqual((observed['generation'],observed['handoff']),(2,'OWNED'))
        self.assertEqual(self.ios[-1].close_calls,1);self.random.assert_called_once_with()
        self.setup_io=lambda io:None
        with self.assertRaises(LeaseRefused):self.acquire(False)
        self.assertEqual(bytes(self.backing['raw']),original);self.assertEqual(self.ios[-1].writes,[])

    def test_immutable_identity_illegal_transition_and_unknown_refusal(self):
        lease=self.acquire();old=dict(lease.record)
        for change in ({'instance_id':UUID_B},{'generation':2},{'initialized':True},
                       {'phase':'CONFIG','runtime':'STARTING'},{'schema':j.SCHEMA}):
            with self.subTest(change=tuple(change)),self.assertRaises(LeaseRefused):
                j.transition(old,{**old,'sequence':old['sequence']+1,**change},format=V2)
        lease.mark_unknown('CREDENTIALS')
        with self.assertRaises(LeaseRefused):lease.instance_uuid()
        with self.assertRaises(LeaseRefused):lease.checkpoint('CREDENTIALS',False,'STARTING')
        lease.release();original=bytes(self.backing['raw'])
        with self.assertRaises(LeaseRefused):self.acquire(False)
        self.assertEqual(bytes(self.backing['raw']),original)

    def test_format_drift_poison_and_close_unknown_are_never_retried(self):
        lease=self.acquire();io=self.ios[-1];before=list(io.writes)
        io._journal_format=j.FixedFormat.V1
        with self.assertRaises(LeaseRefused):lease.instance_uuid()
        self.assertTrue(lease.poisoned);self.assertEqual(io.writes,before)
        io.close_error=True
        with self.assertRaises(BaseExceptionGroup):lease.release()
        with self.assertRaises(LeaseRefused):lease.release()
        self.assertEqual(io.close_calls,1)


if __name__=='__main__':unittest.main()
