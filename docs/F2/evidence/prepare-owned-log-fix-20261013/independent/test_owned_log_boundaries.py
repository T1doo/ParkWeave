"""Independent owned-FD and exclusive-log DI; no real security effect."""
import sys,os
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tests'))
from test_host_case_once_candidate import no_physical_actions
from test_prepare_only_candidate import virtual_prepare
from test_host_case_bootstrap_diagnostics import virtual_bootstrap,VirtualPath
from scripts.host_case_once import prepare_once as p

def root():
    r=VirtualPath('/SYNTHETIC_ROOT');r.mkdir(mode=0o711);(r/'private').mkdir(mode=0o700);return r

@pytest.mark.parametrize('index',[0,1])
def test_all_owned_fds_close_when_one_close_raises(monkeypatch,virtual_prepare,index):
    r=root();opened=[];closed=[];op=p.os.open
    def opened_fd(*a,**kw):fd=op(*a,**kw);opened.append(fd);return fd
    def close(fd):
        closed.append(fd)
        if fd==list(reversed(opened))[index]:raise OSError('SYNTHETIC_CLOSE_FAILURE')
    monkeypatch.setattr(p.os,'open',opened_fd);monkeypatch.setattr(p.os,'close',close)
    with pytest.raises(OSError):p.failure_log(r,(1,2),(1,2),b'SYNTHETIC')
    assert closed==list(reversed(opened))

@pytest.mark.parametrize('stage',[1,2,3])
def test_open_failure_closes_only_already_owned_fds(monkeypatch,virtual_prepare,stage):
    r=root();opened=[];closed=[];op=p.os.open;count=0
    def opening(*a,**kw):
        nonlocal count
        count+=1
        if count==stage:raise FileExistsError('SYNTHETIC_COLLISION')
        fd=op(*a,**kw);opened.append(fd);return fd
    monkeypatch.setattr(p.os,'open',opening);monkeypatch.setattr(p.os,'close',closed.append)
    with pytest.raises(FileExistsError):p.failure_log(r,(1,2),(1,2),b'SYNTHETIC')
    assert closed==list(reversed(opened))
    assert '/SYNTHETIC_ROOT/private/prepare-failure.log' not in VirtualPath.nodes

@pytest.mark.parametrize('step',[1,2,3])
def test_private_write_handles_short_writes_without_duplication(monkeypatch,virtual_prepare,step):
    r=root();out=[];closed=[]
    def written(fd,raw):out.append(raw[:step]);return min(step,len(raw))
    monkeypatch.setattr(p.os,'write',written);monkeypatch.setattr(p.os,'close',closed.append)
    p.failure_log(r,(1,2),(1,2),b'SYNTHETIC_DIAGNOSTIC')
    assert b''.join(out)==b'SYNTHETIC_DIAGNOSTIC' and len(closed)==3

def test_zero_write_fails_and_closes_all_fds(monkeypatch,virtual_prepare):
    r=root();closed=[];monkeypatch.setattr(p.os,'write',lambda *a:0);monkeypatch.setattr(p.os,'close',closed.append)
    with pytest.raises(OSError):p.failure_log(r,(1,2),(1,2),b'SYNTHETIC')
    assert len(closed)==3
