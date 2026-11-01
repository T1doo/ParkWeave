"""Coordinator/scope counterexamples; no actual URL, store or Windows operations."""
import ctypes as C
import copy,io,json,time
import pytest
from scripts.windows_ci import crt_memory_trial as trial,crt_memory_revocation as memory
from scripts.windows_ci import crt_crl_preparation as prep
from tests.test_crt_memory_revocation import source,native


def test_disabled_default_platform_and_audit_refuse_forbidden_surfaces(monkeypatch,capsys):
    monkeypatch.setattr(C,'WinDLL',lambda *a,**kw:pytest.fail('native at disabled/default gate'),raising=False)
    assert trial.main([])==2 and json.loads(capsys.readouterr().out)['status']=='NOT_ENABLED'
    with pytest.raises(prep.PreparationRefused):trial.main(['--inspect-memory-once'])
    audit=trial.MemoryAudit()
    for symbol in trial.EXTRA:audit('ctypes.dlsym',(None,symbol))
    audit('ctypes.dlopen',('winhttp.dll',))
    for event,args in [('ctypes.dlsym',(None,'CryptRetrieveObjectByUrlW')),('ctypes.dlsym',(None,'CertOpenSystemStoreW')),
        ('ctypes.dlsym',(None,'SetTokenInformation')),('open',('forbidden','w',0)),('winreg.SetValue',()),('socket.connect',())]:
        with pytest.raises(RuntimeError):audit(event,args)


@pytest.mark.parametrize('change',[None,'changed_file','file_cleanup_unknown','missing_ca_crl'])
def test_coordinator_binds_before_after_and_closes_all_original_files(monkeypatch,change):
    prototype=source(monkeypatch);s=native(monkeypatch,prototype.state_snapshot)
    pins={'msvcp140.dll':'a'*64,'vcruntime140.dll':'b'*64};monkeypatch.setattr(memory,'FILE_PINS',pins);monkeypatch.setattr(trial,'FILE_PINS',pins)
    created=[];closed=[];fetched=[]
    def init(self,work_end,cleanup_end):
        clone=source(monkeypatch);self.__dict__.update(clone.__dict__);self.state_snapshot.owner=self
        self.initial_identity=(1,2,3);self.ordinal=len(created);created.append(self)
        if change=='changed_file' and self.ordinal>=2:self.initial_identity=(1,2,4)
        if change=='missing_ca_crl':self.state_snapshot.complete=False
    def inspect(self,name):
        self.result.update(file=name,sha256=pins[name]);return self.result
    def close(self):
        closed.append(self.ordinal);self.handles=[]
        return 'UNKNOWN' if change=='file_cleanup_unknown' and self.ordinal==0 else 'OWNED_FILE_HANDLES_CLOSED'
    monkeypatch.setattr(memory.MemoryFileProbe,'__init__',init)
    monkeypatch.setattr(memory.MemoryFileProbe,'inspect',inspect);monkeypatch.setattr(memory.MemoryFileProbe,'close',close)
    class Fetch:
        def __init__(self,*args):pass
        def fetch(self):fetched.append(1);return b'LEAF_CRL'
    monkeypatch.setattr(trial,'FixedCRLFetcher',Fetch)
    # The constructor fixture's source() updates pins while preparing each new
    # original graph, so preserve the two fixed per-file expected entries.
    original_constraints=memory.original_constraints
    def constraints(value):
        monkeypatch.setattr(memory,'FILE_PINS',pins);return original_constraints(value)
    monkeypatch.setattr(trial,'original_constraints',constraints);monkeypatch.setattr(memory,'original_constraints',constraints)
    before=len(trial._retained)
    try:
        result,code=trial.collect_once()
        assert sorted(closed)==list(range(len(created))) and result['usable_product'] is False
        if change is None:
            assert code==0 and result['status']=='CANDIDATE_CONJUNCTION_OBSERVED_NOT_ADMITTED'
            assert result['equivalent_or_stronger_proven'] is False
            assert all(x['verification']=='REFUSED_OR_UNKNOWN' for x in result['before']+result['after'])
        else:
            assert code==2 and result['status']=='REFUSED_OR_UNKNOWN_NO_RETRY'
        if change=='missing_ca_crl':
            assert not fetched and len(result['before'])==1
            assert result['failure']['phase']=='ORIGINAL_BEFORE'
    finally:del trial._retained[before:]
