"""Pure preparation control-flow, never executes the root entry or physical tools."""
import json,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts.host_case_once import bootstrap as b,prepare_once as p
from test_host_case_once_candidate import no_physical_actions,SHA,PARENT,environment
from test_host_case_bootstrap_diagnostics import virtual_bootstrap,VirtualPath,POISON,inject


def test_source_git_failure_stderr_is_captured_and_never_projected(monkeypatch,virtual_bootstrap,capsys):
    seen=[]
    def failed(*a,**kw):
        seen.append(kw)
        # A child stderr stream would be inherited unless explicitly captured.
        if kw.get('stderr')!=subprocess.PIPE:print(POISON,file=sys.stderr)
        raise subprocess.CalledProcessError(1,[POISON],stderr=POISON.encode())
    monkeypatch.setattr(b.subprocess,'check_output',failed)
    assert b.bootstrap(SHA)==1
    captured=capsys.readouterr();assert not captured.err and POISON not in captured.out
    value=json.loads(captured.out);b.public_summary(value)
    assert value['diagnostics'][0]['check_id']=='B_SOURCE_COPY'
    assert seen and all(x['stderr']==subprocess.PIPE for x in seen)


@pytest.fixture
def virtual_prepare(monkeypatch,virtual_bootstrap):
    monkeypatch.setattr(b,'CHECKS',dict(p.b.CHECKS))
    b.register_source('BOOTSTRAP',[p.run.__code__,p.probe.__code__,p.remove_owned.__code__])
    monkeypatch.setattr(p,'b',b);monkeypatch.setattr(p,'Path',VirtualPath)
    monkeypatch.setattr(sys,'dont_write_bytecode',True)
    monkeypatch.setattr(p.signal,'signal',lambda *a:0);monkeypatch.setattr(p.signal,'alarm',lambda *a:0)
    monkeypatch.setattr(p,'probe',lambda *a:b'PREPARE_IMPORTS_PASS\n')
    monkeypatch.setattr(p,'remove_owned',lambda *a:None)
    monkeypatch.setattr(b,'gate',lambda *a,**kw:PARENT)


def test_prepare_success_stops_before_any_business_and_only_reports_three_cases(virtual_prepare,capsys):
    assert p.run(SHA)==0
    v=json.loads(capsys.readouterr().out)
    assert {k for k,x in v['cases'].items() if x=='PASS'}=={'GATE','PROTECTED_RUNTIME','FILES_REMOVED'}
    assert set(v['cases'].values())=={'PASS','NOT_RUN'} and v['cleanup']


PREP_CODES=['B_PREP_FLAGS','B_GATE','B_CLAIM','B_ROOT','B_PRIVATE_DIR',
    *[x for x in b.CHECKS if b.CHECKS[x][1] in ('SOURCE','RUNTIME','DEPENDENCIES')],
    'B_PREP_PROBE','B_PREP_OUTPUT','B_PREP_CLEANUP','B_PREP_TIMER']
@pytest.mark.parametrize('code',PREP_CODES)
def test_prepare_faults_are_closed_and_do_not_run_business(monkeypatch,virtual_prepare,capsys,code):
    inject(monkeypatch,code)
    assert p.run(SHA)==1
    captured=capsys.readouterr();assert not captured.err and POISON not in captured.out
    value=json.loads(captured.out);b.public_summary(value)
    assert any(d['check_id']==code for d in value['diagnostics'])
    assert all(value['cases'][k]=='NOT_RUN' for k in ('REAL_IDENTITIES','FRESH_CLUSTER','CASE_CANCEL','BUSINESS_BIND'))


def test_prepare_pending_gate_has_no_claim_timer_or_tools(tmp_path,monkeypatch,capsys):
    path=tmp_path/p.APPROVAL_FILE;path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(approved=False,source_sha=None,approval_ref=None)))
    monkeypatch.chdir(tmp_path);monkeypatch.setattr(p.b.os,'geteuid',lambda:0)
    monkeypatch.setattr(p.sys,'flags',SimpleNamespace(isolated=1,no_site=1));monkeypatch.setattr(p.sys,'dont_write_bytecode',True)
    def refuse(*a,**kw):raise AssertionError('PRE_GATE_EFFECT')
    monkeypatch.setattr(p.b.os,'open',refuse);monkeypatch.setattr(p.signal,'signal',refuse);monkeypatch.setattr(p.signal,'alarm',refuse)
    assert p.run(SHA)==1
    value=json.loads(capsys.readouterr().out)
    assert value['cases']['GATE']=='FAIL' and value['diagnostics'][0]['check_id']=='B_GATE'


@pytest.mark.parametrize('field,value',[('HOST_CASE_REF',b.BRANCH),('HOST_CASE_NUMBER','2'),
    ('HOST_CASE_ATTEMPT','2'),('HOST_CASE_EVENT','workflow_dispatch'),('HOST_CASE_PUBLIC','false')])
def test_new_probe_gate_refuses_spent_or_other_context(tmp_path,monkeypatch,field,value):
    path=tmp_path/p.APPROVAL_FILE;path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(approved=True,source_sha=PARENT,approval_ref=p.APPROVAL_REF)))
    monkeypatch.setattr(b.os,'geteuid',lambda:0)
    env=environment();env['HOST_CASE_REF']=p.BRANCH;env[field]=value
    with pytest.raises(PermissionError):b.gate(tmp_path,SHA,env,approval_file=p.APPROVAL_FILE,branch=p.BRANCH,approval_ref=p.APPROVAL_REF)


def test_probe_command_is_fixed_no_site_and_child_output_stays_captured(tmp_path,monkeypatch):
    (tmp_path/'private').mkdir();seen=[]
    def fake(args,**kw):seen.append((args,kw));return SimpleNamespace(stdout=b'PREPARE_IMPORTS_PASS\n')
    monkeypatch.setattr(p.subprocess,'run',fake)
    ctx=dict(environment='/SYNTHETIC/environment',imports=['/SYNTHETIC/source','/SYNTHETIC/environment/lib'])
    assert p.probe(ctx,tmp_path)==b'PREPARE_IMPORTS_PASS\n'
    args,kw=seen[0];assert args[1:5]==['-I','-S','-B','-c']
    assert kw['stdout']==subprocess.PIPE and kw['stderr'].name==str(tmp_path/'private/import-stderr.log')
    assert kw['timeout']==30 and kw['env']=={'LANG':'C.UTF-8'}
    assert 'controller' not in args[5] and 'get_config_vars' in args[5]


def test_unexpected_probe_stdout_is_not_public(monkeypatch,virtual_prepare,capsys):
    monkeypatch.setattr(p,'probe',lambda *a:POISON.encode())
    assert p.run(SHA)==1
    v=capsys.readouterr();assert POISON not in v.out and not v.err
    assert json.loads(v.out)['diagnostics'][0]['check_id']=='B_PREP_OUTPUT'


def test_failed_preparation_keeps_owned_root_and_private_log(monkeypatch,virtual_prepare,capsys):
    def fail(*a):raise subprocess.TimeoutExpired([POISON],30,stderr=POISON)
    monkeypatch.setattr(p,'probe',fail)
    def refuse(*a):raise AssertionError('FAILURE_MUST_RETAIN_ROOT')
    monkeypatch.setattr(p,'remove_owned',refuse)
    assert p.run(SHA)==1
    v=json.loads(capsys.readouterr().out)
    assert not v['cleanup'] and v['failure_logs']=='SAVED' and v['cases']['FILES_REMOVED']=='NOT_RUN'


def test_probe_workflow_is_separate_pending_and_bounded():
    text=Path('.github/workflows/prepare-only-security-once.yml').read_text()
    assert p.BRANCH.removeprefix('refs/heads/') in text and p.APPROVAL_FILE in text
    assert 'timeout-minutes: 12' in text and 'github.run_attempt == 1' in text and 'github.run_number == 1' in text
    assert 'controller.py' not in text
    for file in (b.APPROVAL_FILE,p.APPROVAL_FILE):
        assert json.loads(Path(file).read_text())==dict(approved=False,source_sha=None,approval_ref=None)


def test_new_gate_accepts_only_exact_new_pending_parent_and_approval_child(tmp_path,monkeypatch):
    path=tmp_path/p.APPROVAL_FILE;path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(approved=True,source_sha=PARENT,approval_ref=p.APPROVAL_REF)))
    monkeypatch.setattr(b.os,'geteuid',lambda:0)
    answers={('rev-parse','HEAD'):SHA,('rev-list','--parents','-n','1','HEAD'):SHA+' '+PARENT,
        ('diff','--name-only',PARENT,SHA):p.APPROVAL_FILE,('status','--porcelain'):'',
        ('show',PARENT+':'+p.APPROVAL_FILE):json.dumps(dict(approved=False,source_sha=None,approval_ref=None))}
    monkeypatch.setattr(b,'git',lambda *args:answers[args[1:]])
    env=environment();env['HOST_CASE_REF']=p.BRANCH
    assert b.gate(tmp_path,SHA,env,approval_file=p.APPROVAL_FILE,branch=p.BRANCH,approval_ref=p.APPROVAL_REF)==PARENT
    answers[('diff','--name-only',PARENT,SHA)]=p.APPROVAL_FILE+'\nscripts/host_case_once/prepare_once.py'
    with pytest.raises(PermissionError):b.gate(tmp_path,SHA,env,approval_file=p.APPROVAL_FILE,branch=p.BRANCH,approval_ref=p.APPROVAL_REF)


@pytest.mark.parametrize('mode',['inode','owner','writable','link','parent','prefix','unsafe_remover'])
def test_cleanup_refuses_changed_or_unowned_root(monkeypatch,mode):
    import stat
    root=Path('/tmp/parkweave-prepare-'+'c'*32)
    data=dict(st_mode=stat.S_IFDIR|0o711,st_uid=0,st_dev=1,st_ino=2)
    if mode=='inode':data['st_ino']=3
    if mode=='owner':data['st_uid']=1000
    if mode=='writable':data['st_mode']|=0o022
    if mode=='link':data['st_mode']=stat.S_IFLNK|0o777
    if mode=='parent':root=Path('/SYNTHETIC/parkweave-prepare-'+'c'*32)
    if mode=='prefix':root=Path('/tmp/other-owned-root')
    monkeypatch.setattr(Path,'lstat',lambda *a:SimpleNamespace(**data))
    def refuse(*a):raise AssertionError('UNOWNED_REMOVAL_FORBIDDEN')
    refuse.avoids_symlink_attacks=mode!='unsafe_remover'
    monkeypatch.setattr(p.shutil,'rmtree',refuse)
    with pytest.raises(PermissionError):p.remove_owned(root,(1,2))
