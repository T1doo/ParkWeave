"""Real POSIX fixed-slot IO; only the native fact sink is a controlled boundary.

No Windows calls, execution grant, accepted fact or access to a prior trial.
"""
from types import SimpleNamespace
import time

import pytest

from scripts.windows_portable import fixed_journal as journal,native_trial_facts as facts
from scripts.windows_portable.directories import LeaseRefused
from scripts.windows_portable.fixed_directories import FixedPrivateDirectories


@pytest.fixture
def observed_lease(tmp_path,monkeypatch):
    dirs=FixedPrivateDirectories(str(tmp_path),format=journal.FixedFormat.INSTANCE_V2)
    lease=dirs.claim_fresh(str(tmp_path/'owned-synthetic-case'))
    state=SimpleNamespace(deadline=time.monotonic()+10,cleanup_end=time.monotonic()+20)
    monkeypatch.setattr(facts.a,'bound_state',lambda resource,**kw:state if resource is lease else None)
    observed=[]
    def sink(original,names,origin,observation,**kw):
        # Keep the real subject identity gate. The old observer failed here
        # after committing UNKNOWN; this boundary issues NO NativeFact.
        observed.append((original._verified_instance_uuid(),original.snapshot,names))
    monkeypatch.setattr(facts,'_seal',sink)
    return dirs,lease,observed


def test_unknown_commits_once_without_success_fact_and_remains_unopenable(observed_lease):
    dirs,lease,observed=observed_lease
    sequence=lease.record['sequence']
    lease.checkpoint('CREDENTIALS',False,'STARTING')
    assert len(observed)==1
    lease.mark_unknown('CREDENTIALS')
    assert not lease.poisoned and lease.record['sequence']==sequence+2
    assert journal.decode(lease.fs.read()[0],format=journal.FixedFormat.INSTANCE_V2)['phase']=='UNKNOWN'
    assert len(observed)==1
    with pytest.raises(LeaseRefused,match='FIXED_INSTANCE_UNKNOWN'):lease.instance_uuid()
    with pytest.raises(LeaseRefused):lease.checkpoint('CONFIG',False,'STARTING')
    lease.release()
    assert not lease.active and len(observed)==1
    with pytest.raises(LeaseRefused):dirs.open_existing(dirs.base+'/owned-synthetic-case')


@pytest.mark.parametrize('failure',['readback','write','close'])
def test_real_storage_failures_are_preserved_without_success_fact(observed_lease,monkeypatch,failure):
    _,lease,observed=observed_lease
    original_close=lease.fs.close
    if failure=='readback':
        monkeypatch.setattr(lease.fs,'read',lambda:(_ for _ in ()).throw(LeaseRefused('CONTROLLED_READBACK_FAILURE')))
    elif failure=='write':
        monkeypatch.setattr(lease.fs,'write_at',lambda *args:(_ for _ in ()).throw(LeaseRefused('CONTROLLED_WRITE_FAILURE')))
    else:
        lease.mark_unknown('ACQUIRE')
        def close():
            original_close()
            raise LeaseRefused('CONTROLLED_CLOSE_ACK_UNKNOWN')
        monkeypatch.setattr(lease.fs,'close',close)
    try:
        if failure!='close':
            with pytest.raises(LeaseRefused):lease.mark_unknown('ACQUIRE')
            assert lease.poisoned
            lease.release()
        else:
            with pytest.raises(BaseExceptionGroup):lease.release()
        assert not lease.active and not observed
        with pytest.raises(LeaseRefused):lease.release()
    finally:
        if lease.active:original_close()


def test_observer_decodes_verified_snapshot_instead_of_mutable_record(observed_lease):
    _,lease,observed=observed_lease
    try:
        lease.record['phase']='UNKNOWN'  # Caller memory is never an observation.
        facts.journal_write(lease)
        assert len(observed)==1
    finally:lease.fs.close();lease.active=False


def test_controller_preserves_original_denial_without_spurious_cleanup_cascade(observed_lease,monkeypatch):
    dirs,lease,observed=observed_lease
    from parkweave import windows_files
    from parkweave.store import Denied
    from scripts.windows_portable.controller import Controller,ControlFailure
    sequence=lease.record['sequence'];writes=[];original=lease.fs.replace
    def replace(raw,expected):
        writes.append(journal.decode(raw,format=journal.FixedFormat.INSTANCE_V2))
        return original(raw,expected)
    monkeypatch.setattr(lease.fs,'replace',replace)
    class Directories:
        def claim_fresh(self,root):return lease
    class Security:
        def require_runtime_support(self,*args):pass
        def require_creation_support(self):pass
        def bind_new_lease(self,original):windows_files.component('CON')
        def close_owned_files(self,original):pass
    class Database:
        def prepare_new(self):return b'protocol-only-no-SQL-execution'
    control=Controller(Directories(),Security(),object(),database=Database())
    with pytest.raises(ControlFailure) as caught:control._run(dirs.base+'/owned-synthetic-case',lambda _:None,fresh=True)
    failure=caught.value
    assert failure.phase=='ACQUIRE' and type(failure.primary) is Denied
    assert failure.public()['outcome']=='UNKNOWN' and not failure.cleanup_errors
    assert not lease.active and not observed
    assert [row['phase'] for row in writes]==['UNKNOWN','UNKNOWN']
    assert [row['handoff'] for row in writes]==['OWNED','RELEASE_PENDING']
    assert lease.record['sequence']==sequence+2  # No duplicate mark_unknown retry.
    with pytest.raises(LeaseRefused):dirs.open_existing(dirs.base+'/owned-synthetic-case')
