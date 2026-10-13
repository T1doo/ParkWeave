"""Independent offline scope and DI; no real entry execution."""
import ast,io,json,sys,stat
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tests'))
from test_host_case_once_candidate import no_physical_actions
from scripts.host_case_once import prepare_once as p

class Root:
    parent=Path('/tmp');name='parkweave-prepare-SYNTHETIC'
    def __init__(self,mode=stat.S_IFDIR|0o711,uid=0,dev=1,ino=2):self.s=SimpleNamespace(st_mode=mode,st_uid=uid,st_dev=dev,st_ino=ino)
    def lstat(self):return self.s
    def __truediv__(self,x):return self
    def open(self,*a,**k):return io.BytesIO()
    def exists(self):return False
    def is_symlink(self):return False

@pytest.mark.parametrize('change',[{'uid':1000},{'mode':stat.S_IFDIR|0o777},{'mode':stat.S_IFLNK|0o777},{'dev':2},{'ino':3}])
def test_owned_cleanup_refuses_nonowned_root_before_rmtree(monkeypatch,change):
    called=[];fn=lambda *a:called.append(a);fn.avoids_symlink_attacks=True;monkeypatch.setattr(p.shutil,'rmtree',fn)
    with pytest.raises(PermissionError):p.remove_owned(Root(**change),(1,2))
    assert called==[]

def test_cleanup_requires_fd_safe_rmtree(monkeypatch):
    fn=lambda *a:pytest.fail('removal forbidden');fn.avoids_symlink_attacks=False;monkeypatch.setattr(p.shutil,'rmtree',fn)
    with pytest.raises(PermissionError):p.remove_owned(Root(),(1,2))

def test_probe_captures_only_private_stderr_and_closed_stdout(monkeypatch):
    calls=[]
    def sub(argv,**kw):calls.append((argv,kw));return SimpleNamespace(stdout=b'PREPARE_IMPORTS_PASS\n')
    monkeypatch.setattr(p.subprocess,'run',sub)
    assert p.probe(dict(imports=['/SYNTHETIC/source','/SYNTHETIC/environment/lib'],environment='/SYNTHETIC/environment'),Root())==b'PREPARE_IMPORTS_PASS\n'
    argv,kw=calls[0];assert argv[:4]==['/SYNTHETIC/environment/bin/python3.12','-I','-S','-B']
    assert kw['env']=={'LANG':'C.UTF-8'} and kw['cwd']=='/' and kw['stdout']==p.subprocess.PIPE and hasattr(kw['stderr'],'write') and kw['timeout']==30 and kw['check'] is True

def test_probe_import_scope_has_no_business_or_security_namespace():
    tree=ast.parse(p.PROBE);names={a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
    assert names=={'sys','json','os','sysconfig','fastapi','uvicorn','psycopg','pydantic','httpx'}
    assert not any(isinstance(n,ast.ImportFrom) for n in ast.walk(tree))
    assert not {'connect','run','Popen','socket','Store','Controller','token_hex','token_urlsafe'}.intersection({n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)})

def test_source_git_show_stderr_is_captured():
    tree=ast.parse(Path(p.b.__file__).read_text());calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='check_output']
    assert len(calls)==2
    for n in calls:
        kw={k.arg:k.value for k in n.keywords};assert ast.unparse(kw['stderr'])=='subprocess.PIPE'

def test_only_pending_new_scope_receipt_and_nonexecution_ref():
    root=Path(__file__).resolve().parents[3]
    assert json.loads((root/p.APPROVAL_FILE).read_text())==dict(approved=False,source_sha=None,approval_ref=None)
    assert p.BRANCH=='refs/heads/dev/f2-prepare-only-security-once-20261013'
    assert p.CLAIM=='/tmp/parkweave-prepare-only-once-20261013.claim' and p.APPROVAL_REF=='USER_CONFIRMED_PREPARE_ONLY_ONCE_20261013'
