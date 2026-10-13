"""Independent DI only: no protected-copy or subprocess real effects."""
import sys,json,stat
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tests'))
from test_host_case_bootstrap_diagnostics import virtual_bootstrap,VirtualPath,POISON
from test_host_case_once_candidate import no_physical_actions
from scripts.host_case_once import bootstrap as b

@pytest.mark.parametrize('mode,uid',[(stat.S_IFREG|0o666,0),(stat.S_IFREG|0o644,123),(stat.S_IFLNK|0o777,0),(stat.S_IFDIR|0o755,0)])
def test_alias_fstat_target_rejected_before_target_output(monkeypatch,virtual_bootstrap,mode,uid):
    root='/usr/lib/python3.12';alias=root+'/_sysconfigdata__linux_x86_64-linux-gnu.py';target=root+'/_sysconfigdata__x86_64-linux-gnu.py'
    VirtualPath.nodes[alias]=stat.S_IFLNK|0o777;VirtualPath.links[alias]='_sysconfigdata__x86_64-linux-gnu.py'
    old=b.os.fstat
    def fs(fd):
        if str(VirtualPath.fdpaths[fd])==target:return SimpleNamespace(st_mode=mode,st_uid=uid)
        return old(fd)
    monkeypatch.setattr(b.os,'fstat',fs)
    with pytest.raises(PermissionError):b.protected_copy(VirtualPath(root),VirtualPath('/SYNTHETIC_TARGET'),stdlib=True)
    assert '/SYNTHETIC_TARGET/_sysconfigdata__linux_x86_64-linux-gnu.py' not in VirtualPath.nodes

def test_alias_open_no_follow_and_create_exclusive(monkeypatch,virtual_bootstrap):
    root='/usr/lib/python3.12';alias=root+'/_sysconfigdata__linux_x86_64-linux-gnu.py'
    VirtualPath.nodes[alias]=stat.S_IFLNK|0o777;VirtualPath.links[alias]='_sysconfigdata__x86_64-linux-gnu.py';calls=[];old=b.os.open
    def op(p,f,*a):calls.append((str(p),f));return old(p,f,*a)
    monkeypatch.setattr(b.os,'open',op)
    b.protected_copy(VirtualPath(root),VirtualPath('/SYNTHETIC_TARGET'),stdlib=True)
    src=[f for p,f in calls if p==root+'/_sysconfigdata__x86_64-linux-gnu.py'];out=[f for p,f in calls if p.endswith('/_sysconfigdata__linux_x86_64-linux-gnu.py') and p.startswith('/SYNTHETIC_TARGET')]
    assert src and src[0]&b.os.O_NOFOLLOW and src[0]&b.os.O_CLOEXEC
    assert out and out[0]&b.os.O_NOFOLLOW and out[0]&b.os.O_EXCL

@pytest.mark.parametrize('isolated,no_site',[(0,1),(1,0)])
def test_no_site_isolation_required_before_source_access(monkeypatch,virtual_bootstrap,isolated,no_site):
    monkeypatch.setattr(b.sys,'flags',SimpleNamespace(isolated=isolated,no_site=no_site))
    with pytest.raises(PermissionError):b.protected_copy(VirtualPath('/usr/lib/python3.12'),VirtualPath('/SYNTHETIC_TARGET'),stdlib=True)
    assert VirtualPath.reads==[]

@pytest.mark.parametrize('field',['exception','message','type','path','argv','stderr','trace_sha256'])
def test_projection_rejects_all_extra_private_fields(field):
    v=b.initial('a'*40);d=dict(case='GATE',substage='GATE',check_id='B_GATE',source='BOOTSTRAP',line=0);d[field]=POISON;v['diagnostics']=[d]
    with pytest.raises(ValueError) as exc:b.public_summary(v)
    assert POISON not in str(exc.value)
