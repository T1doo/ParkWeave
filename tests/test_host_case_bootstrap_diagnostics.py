"""Actual helper control-flow fault injection, with all effects replaced by DI."""
import io,json,stat,sys
from pathlib import PurePosixPath,Path
from types import SimpleNamespace
import pytest
from scripts.host_case_once import bootstrap as b,controller as c,dependencies as deps
from test_host_case_once_candidate import no_physical_actions,context,SHA,PARENT

POISON='SYNTHETIC_SECRET_path_argv_stderr_password_DO_NOT_PROJECT'

class VirtualPath:
    nodes={};fdpaths={};writes={};reads=[];links={}
    def __init__(self,value):self.value=str(value)
    def __str__(self):return self.value
    def __truediv__(self,other):return type(self)(str(PurePosixPath(self.value)/str(other)))
    @property
    def parent(self):return type(self)(str(PurePosixPath(self.value).parent))
    @property
    def parents(self):return [type(self)(str(x)) for x in PurePosixPath(self.value).parents]
    @property
    def name(self):return PurePosixPath(self.value).name
    @property
    def suffix(self):return PurePosixPath(self.value).suffix
    @classmethod
    def cwd(cls):return cls('/SYNTHETIC_CHECKOUT')
    def mkdir(self,**kw):self.nodes[self.value]=stat.S_IFDIR|kw.get('mode',0o755)
    def exists(self):return self.value in self.nodes
    def is_symlink(self):return self.value in self.links
    def is_dir(self):return stat.S_ISDIR(self.lstat().st_mode)
    def lstat(self):
        mode=self.nodes.get(self.value,stat.S_IFDIR|0o755 if self.value in ('/','/usr','/usr/bin','/usr/lib','/usr/lib/python3.12') else stat.S_IFREG|0o644)
        if self.is_symlink():mode=stat.S_IFLNK|0o777
        return SimpleNamespace(st_mode=mode,st_uid=0,st_gid=0,st_nlink=1,st_dev=1,st_ino=2)
    stat=lstat
    def iterdir(self):return [type(self)(x) for x in sorted(self.nodes) if str(PurePosixPath(x).parent)==self.value]
    def rglob(self,pattern):return [type(self)(x) for x in sorted(self.nodes) if x.startswith(self.value+'/')]
    def write_bytes(self,value):self.nodes[self.value]=stat.S_IFREG|0o644;self.writes[self.value]=value
    def write_text(self,value):self.write_bytes(value.encode())
    def open(self,*a,**kw):return io.BytesIO()

@pytest.fixture
def virtual_bootstrap(monkeypatch):
    VirtualPath.nodes={};VirtualPath.links={};VirtualPath.writes={};VirtualPath.fdpaths={};VirtualPath.reads=[]
    monkeypatch.setattr(b,'Path',VirtualPath)
    monkeypatch.setattr(b,'gate',lambda *a:PARENT)
    monkeypatch.setattr(b,'git',lambda *a:'scripts/host_case_once/requirements.lock')
    monkeypatch.setattr(b.subprocess,'check_output',lambda *a,**kw:b'SYNTHETIC_CODE')
    monkeypatch.setattr(b.subprocess,'run',lambda *a,**kw:None)
    monkeypatch.setattr(b.os,'chmod',lambda *a:None);monkeypatch.setattr(b.os,'chown',lambda *a:None)
    monkeypatch.setattr(b.os,'close',lambda *a:None)
    monkeypatch.setattr(b.os,'write',lambda fd,raw:len(raw))
    monkeypatch.setattr(b.os,'read',lambda fd,size:b'')
    def opened(path,flags,*args):
        p=VirtualPath(str(path));fd=100+len(VirtualPath.fdpaths);VirtualPath.fdpaths[fd]=p
        if flags&b.os.O_CREAT:p.write_bytes(b'')
        else:VirtualPath.reads.append(str(path))
        return fd
    monkeypatch.setattr(b.os,'open',opened)
    monkeypatch.setattr(b.os,'fstat',lambda fd:VirtualPath.fdpaths[fd].lstat())
    monkeypatch.setattr(b.os,'readlink',lambda p:VirtualPath.links[str(p)])
    original_flags=sys.flags
    class Flags:
        isolated=1;no_site=1
        def __getattr__(self,name):return getattr(original_flags,name)
    monkeypatch.setattr(b.sys,'flags',Flags());monkeypatch.setattr(b.sys,'path',list(sys.path))
    monkeypatch.setattr(b,'uuid4',lambda:SimpleNamespace(hex='c'*32))
    monkeypatch.setattr(deps,'supported_host',lambda:None)
    monkeypatch.setattr(deps,'pip_commands',lambda *a:(['SYNTHETIC_DOWNLOAD'],['SYNTHETIC_INSTALL']))
    monkeypatch.setattr(deps,'verify',lambda *a:19)
    monkeypatch.setattr(c.reference,'sealed',lambda *a:123)
    monkeypatch.setattr(c.writer,'_pid_started',lambda pid:'SYNTHETIC_START')
    result=b.initial(PARENT);result.update(cleanup=True,phase='COMPLETE')
    result['cases']={k:'PASS' for k in b.CASES}
    child=SimpleNamespace(returncode=0,communicate=lambda **kw:(json.dumps(result).encode(),None),
        terminate=lambda:None,kill=lambda:None)
    monkeypatch.setattr(b.subprocess,'Popen',lambda *a,**kw:child)
    return child


def inject(monkeypatch,target,exception=RuntimeError):
    original=b.Diagnostic.checkpoint
    def checkpoint(self,code,case=None):
        original(self,code,case)
        if code==target:raise exception(POISON)
    monkeypatch.setattr(b.Diagnostic,'checkpoint',checkpoint)

BOOT_CODES=[x for x in b.CHECKS if x.startswith('B_') and x not in ('B_TIMEOUT_TERM','B_TIMEOUT_KILL','B_PRIVATE_LOG')]

@pytest.mark.parametrize('code',BOOT_CODES)
def test_bootstrap_each_checkpoint_reports_closed_failure_without_private_data(monkeypatch,virtual_bootstrap,capsys,code):
    inject(monkeypatch,code)
    assert b.bootstrap(SHA)==1
    public=capsys.readouterr().out;assert POISON not in public
    value=json.loads(public);b.public_summary(value)
    found=[d for d in value['diagnostics'] if d['check_id']==code];assert len(found)==1
    assert found[0]['source']=='BOOTSTRAP' and 0<found[0]['line']<=10000
    assert set(found[0])=={'case','substage','check_id','source','line'}
    assert value['cases'][found[0]['case']]=='FAIL'


@pytest.mark.parametrize('code',['B_TIMEOUT_TERM','B_TIMEOUT_KILL'])
def test_timeout_stop_checkpoints_do_not_leak_exception_or_argv(monkeypatch,virtual_bootstrap,capsys,code):
    def timed(**kw):raise b.subprocess.TimeoutExpired(POISON,1,output=POISON,stderr=POISON)
    virtual_bootstrap.communicate=timed;inject(monkeypatch,code)
    assert b.bootstrap(SHA)==1
    raw=capsys.readouterr().out;assert POISON not in raw
    assert any(d['check_id']==code for d in json.loads(raw)['diagnostics'])


def test_private_log_failure_keeps_primary_and_secondary_check(monkeypatch,virtual_bootstrap,capsys):
    original=b.Diagnostic.checkpoint
    def checkpoint(self,code,case=None):
        original(self,code,case)
        if code in ('B_DOWNLOAD','B_PRIVATE_LOG'):raise RuntimeError(POISON)
    monkeypatch.setattr(b.Diagnostic,'checkpoint',checkpoint)
    assert b.bootstrap(SHA)==1
    raw=capsys.readouterr().out;assert POISON not in raw
    value=json.loads(raw);assert [d['check_id'] for d in value['diagnostics']]==['B_DOWNLOAD','B_PRIVATE_LOG']
    assert value['failure_logs']=='UNAVAILABLE'


@pytest.mark.parametrize('change',[{'check_id':POISON},{'source':POISON},{'substage':POISON},
    {'case':'CASE_CANCEL'},{'line':True},{'line':-1},{'line':10001},{'stderr':POISON},{'trace_sha256':'a'*64}])
def test_public_diagnostic_schema_refuses_poison_and_mismatched_enums(change):
    value=b.initial(SHA);diag=dict(case='GATE',source='BOOTSTRAP',substage='GATE',check_id='B_GATE',line=0)
    diag.update(change);value['diagnostics']=[diag]
    with pytest.raises(ValueError) as error:b.public_summary(value)
    assert POISON not in str(error.value)


def test_unreviewed_exception_frame_is_zero_and_cannot_supply_public_line():
    diag=b.Diagnostic([]);diag.checkpoint('B_GATE')
    try:raise RuntimeError(POISON)
    except RuntimeError:value=diag.capture()
    assert value['line']==0 and set(value)=={'case','substage','check_id','source','line'}


def test_diagnostic_list_remains_bounded():
    diag=b.Diagnostic([]);diag.checkpoint('B_GATE')
    for _ in range(100):diag.capture()
    assert len(diag.items)==32


def test_official_fixed_stdlib_links_are_materialized_or_omitted_without_target_discovery(monkeypatch,virtual_bootstrap):
    root='/usr/lib/python3.12'
    for name in ['sitecustomize.py','_sysconfigdata__linux_x86_64-linux-gnu.py','_sysconfigdata__x86_64-linux-gnu.py']:
        VirtualPath.nodes[root+'/'+name]=stat.S_IFREG|0o644
    VirtualPath.links={root+'/sitecustomize.py':'/etc/python3.12/sitecustomize.py',root+'/_sysconfigdata__linux_x86_64-linux-gnu.py':'_sysconfigdata__x86_64-linux-gnu.py'}
    b.protected_copy(VirtualPath(root),VirtualPath('/SYNTHETIC_TARGET'),stdlib=True)
    assert '/etc/python3.12/sitecustomize.py' not in VirtualPath.reads
    assert '/SYNTHETIC_TARGET/sitecustomize.py' not in VirtualPath.nodes
    assert '/SYNTHETIC_TARGET/_sysconfigdata__linux_x86_64-linux-gnu.py' in VirtualPath.nodes
    assert not any(stat.S_ISLNK(v) for k,v in VirtualPath.nodes.items() if k.startswith('/SYNTHETIC_TARGET'))


@pytest.mark.parametrize('source,target',[('sitecustomize.py','/SYNTHETIC_OTHER'),
    ('_sysconfigdata__linux_x86_64-linux-gnu.py','../SYNTHETIC_OTHER'),('arbitrary.py','_sysconfigdata__x86_64-linux-gnu.py')])
def test_other_stdlib_links_and_wrong_destinations_refused(monkeypatch,virtual_bootstrap,source,target):
    name='/usr/lib/python3.12/'+source;VirtualPath.nodes[name]=stat.S_IFLNK|0o777;VirtualPath.links[name]=target
    with pytest.raises(PermissionError):b.protected_copy(VirtualPath('/usr/lib/python3.12'),VirtualPath('/SYNTHETIC_TARGET'),stdlib=True)
    assert target not in VirtualPath.reads


def test_fixed_alias_target_symlink_chain_refused(monkeypatch,virtual_bootstrap):
    root='/usr/lib/python3.12';alias=root+'/_sysconfigdata__linux_x86_64-linux-gnu.py';target=root+'/_sysconfigdata__x86_64-linux-gnu.py'
    VirtualPath.nodes[alias]=VirtualPath.nodes[target]=stat.S_IFLNK|0o777
    VirtualPath.links={alias:'_sysconfigdata__x86_64-linux-gnu.py',target:POISON}
    with pytest.raises(PermissionError):b.protected_copy(VirtualPath(root),VirtualPath('/SYNTHETIC_TARGET'),stdlib=True)


def test_stdlib_exceptions_require_exact_root_and_no_site_flags(monkeypatch,virtual_bootstrap):
    with pytest.raises(PermissionError):b.protected_copy(VirtualPath('/SYNTHETIC_OTHER'),VirtualPath('/SYNTHETIC_TARGET'),stdlib=True)
    monkeypatch.setattr(b.sys,'flags',SimpleNamespace(isolated=1,no_site=0))
    with pytest.raises(PermissionError):b.protected_copy(VirtualPath('/usr/lib/python3.12'),VirtualPath('/SYNTHETIC_TARGET'),stdlib=True)


def controller_fixture(monkeypatch):
    value=c.Controller(context(),c._BOOT_ISSUER);value.root_instance=(1,2)
    value.worker=SimpleNamespace(pw_uid=200);value.pg=SimpleNamespace(pw_uid=201)
    value.created_users={'pwci_writer':(200,202)};value.created_groups={'pwci_writer':202};value.creation_attempts=2
    value.business=SimpleNamespace(returncode=0,poll=lambda:0);value.setup_process=SimpleNamespace(returncode=0,poll=lambda:0)
    value.pg_process=SimpleNamespace(returncode=0,poll=lambda:0);value.writer_process=SimpleNamespace(returncode=0)
    value.linux_host=SimpleNamespace(stop=lambda *a:None)
    monkeypatch.setattr(value,'_close_owned',lambda *a:None);monkeypatch.setattr(value,'_stop_owned',lambda *a:None)
    monkeypatch.setattr(value,'call',lambda *a:dict(dropped=True));monkeypatch.setattr(value,'_no_unknown_identity_users',lambda:None)
    monkeypatch.setattr(value,'tool',lambda *a,**kw:None)
    monkeypatch.setattr(Path,'lstat',lambda *a:SimpleNamespace(st_mode=stat.S_IFDIR|0o711,st_uid=0,st_dev=1,st_ino=2))
    current={'uid':200}
    def opened(path,*args):current['uid']=200 if str(path).endswith('bootstrap.json') else 201;return 90
    monkeypatch.setattr(c.os,'open',opened);monkeypatch.setattr(c.os,'close',lambda *a:None)
    monkeypatch.setattr(c.os,'fstat',lambda *a:SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_uid=current['uid'],st_nlink=1))
    monkeypatch.setattr(c.os,'fchown',lambda *a:None);monkeypatch.setattr(c.os,'fchmod',lambda *a:None)
    monkeypatch.setattr(c.pwd,'getpwnam',lambda *a:SimpleNamespace(pw_uid=200,pw_gid=202))
    monkeypatch.setattr(c.grp,'getgrnam',lambda *a:SimpleNamespace(gr_gid=202))
    monkeypatch.setattr(c.shutil,'rmtree',lambda *a:None)
    return value

CLEANUP_CODES=['C_CLOSE','C_WRITER_STOP','C_DROP','C_SETUP_CLOSE','C_PG_STOP','C_CHILDREN','C_IDENTITY_CHECK','C_SECRET_RECLAIM','C_USER_DELETE','C_GROUP_DELETE','C_FILES_REMOVE']

@pytest.mark.parametrize('code',CLEANUP_CODES)
def test_cleanup_each_checkpoint_keeps_closed_failure(monkeypatch,code):
    value=controller_fixture(monkeypatch);inject(monkeypatch,code)
    try:ok=value.cleanup()
    except RuntimeError:ok=False;value.diag.capture()
    assert not ok
    raw=json.dumps(b.public_summary(value.value));assert POISON not in raw
    assert any(d['check_id']==code and d['source']=='CONTROLLER' for d in value.value['diagnostics'])


@pytest.mark.parametrize('code',['C_IDENTITIES','C_PG','C_HOST','C_ACCEPTANCE','C_CLEANUP'])
def test_controller_primary_and_cleanup_failure_returns_diagnostics(monkeypatch,code):
    value=controller_fixture(monkeypatch)
    monkeypatch.setattr(c.os,'geteuid',lambda:0)
    monkeypatch.setattr(c.host,'_process',lambda *a:dict(pid=10,uid=0,started='SYNTHETIC_START'))
    monkeypatch.setattr(c.os,'getppid',lambda:10)
    monkeypatch.setattr(c.signal,'signal',lambda *a:None);monkeypatch.setattr(c.signal,'setitimer',lambda *a:None)
    for name in ['identities','pg_start','host_start','acceptance']:monkeypatch.setattr(value,name,lambda:None)
    monkeypatch.setattr(Path,'write_text',lambda *a,**kw:None)
    inject(monkeypatch,code)
    result=value.run();raw=json.dumps(result);assert POISON not in raw and result['error']=='FAILURE'
    assert any(d['check_id']==code for d in result['diagnostics'])


def test_cloned_code_cannot_impersonate_reviewed_source_line(monkeypatch,virtual_bootstrap,capsys):
    import types
    clone=b.bootstrap.__code__.replace(co_filename=POISON)
    assert b.reviewed_source(clone) is None and b.reviewed_source(b.bootstrap.__code__)=='BOOTSTRAP'
    function=types.FunctionType(clone,b.bootstrap.__globals__)
    inject(monkeypatch,'B_GATE')
    assert function(SHA)==1
    value=json.loads(capsys.readouterr().out)
    assert value['diagnostics'][0]['line']==0 and POISON not in json.dumps(value)


def test_cleanup_fallback_stop_failure_is_recorded_separately(monkeypatch):
    value=controller_fixture(monkeypatch)
    def fail(*a):raise RuntimeError(POISON)
    monkeypatch.setattr(value,'_close_owned',fail)
    inject(monkeypatch,'C_FALLBACK_STOP')
    assert not value.cleanup()
    assert any(d['check_id']=='C_CLOSE' for d in value.value['diagnostics'])
    assert any(d['check_id']=='C_FALLBACK_STOP' for d in value.value['diagnostics'])
    assert POISON not in json.dumps(b.public_summary(value.value))


@pytest.mark.parametrize('code',['C_PARENT','C_ROOT'])
def test_controller_precheck_exception_has_public_enum_without_private_path(monkeypatch,code):
    value=controller_fixture(monkeypatch)
    monkeypatch.setattr(c.os,'geteuid',lambda:0)
    monkeypatch.setattr(c.host,'_process',lambda *a:dict(pid=10,uid=0,started='SYNTHETIC_START'))
    monkeypatch.setattr(c.os,'getppid',lambda:10)
    inject(monkeypatch,code)
    result=value.run()
    assert result['cases']['GATE']=='FAIL' and result['error']=='FAILURE'
    assert result['diagnostics'][0]['check_id']==code and POISON not in json.dumps(result)


def test_fixed_alias_source_open_uses_nofollow_and_rejects_wrong_owner(monkeypatch,virtual_bootstrap):
    root='/usr/lib/python3.12';alias=root+'/_sysconfigdata__linux_x86_64-linux-gnu.py';target=root+'/_sysconfigdata__x86_64-linux-gnu.py'
    VirtualPath.nodes[alias]=stat.S_IFLNK|0o777;VirtualPath.links[alias]='_sysconfigdata__x86_64-linux-gnu.py'
    opened=b.os.open;calls=[]
    def checked_open(path,flags,*args):
        calls.append((str(path),flags));return opened(path,flags,*args)
    monkeypatch.setattr(b.os,'open',checked_open)
    monkeypatch.setattr(b.os,'fstat',lambda fd:SimpleNamespace(st_mode=stat.S_IFREG|0o644,st_uid=1000))
    with pytest.raises(PermissionError):b.protected_copy(VirtualPath(root),VirtualPath('/SYNTHETIC_TARGET'),stdlib=True)
    assert calls==[(target,b.os.O_RDONLY|b.os.O_NOFOLLOW|b.os.O_CLOEXEC)]


def test_forged_traceback_line_outside_reviewed_code_is_not_projected(monkeypatch,virtual_bootstrap,capsys):
    import types
    def forged_gate(*a):
        frame=sys._getframe(1)
        assert b.reviewed_source(frame.f_code)=='BOOTSTRAP'
        assert not b.reviewed_line(frame.f_code,9999)
        raise RuntimeError(POISON).with_traceback(types.TracebackType(None,frame,frame.f_lasti,9999))
    monkeypatch.setattr(b,'gate',forged_gate)
    assert b.bootstrap(SHA)==1
    value=json.loads(capsys.readouterr().out)
    assert value['diagnostics'][0]['check_id']=='B_GATE' and value['diagnostics'][0]['line']!=9999
    assert POISON not in json.dumps(value)
