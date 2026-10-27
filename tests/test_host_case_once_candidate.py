"""Pure DI guards; physical host/PG acceptance remains NOT_RUN."""
from copy import deepcopy
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
from types import SimpleNamespace

import psycopg
import pytest
from parkweave.store import Store, Denied
from scripts.host_case_once import bootstrap as b, controller as c, worker as w
from test_case_cancellation_business_binding import inputs, dsn, ROOT

SHA='a'*40
PARENT='b'*40
POISON='SYNTHETIC_PRIVATE_DO_NOT_PUBLISH'

@pytest.fixture(autouse=True)
def no_physical_actions(monkeypatch):
    def refuse(*args,**kwargs):raise AssertionError('PHYSICAL_ACTION_FORBIDDEN_IN_PURE_TEST')
    for obj,name in ((subprocess,'Popen'),(subprocess,'run'),(subprocess,'check_output'),
        (psycopg,'connect'),(psycopg.Connection,'connect'),(Store,'connect'),
        (socket.socket,'connect'),(socket.socket,'bind'),(os,'chown'),(os,'chmod'),
        (os,'fchown'),(os,'fchmod'),(os,'memfd_create'),(shutil,'rmtree'),
        (secrets,'token_hex'),(secrets,'token_bytes'),(secrets,'token_urlsafe')):
        monkeypatch.setattr(obj,name,refuse)


def approval(tmp_path,**change):
    p=tmp_path/b.APPROVAL_FILE;p.parent.mkdir(parents=True)
    value=dict(approved=True,source_sha=PARENT,approval_ref=b.APPROVAL_REF);value.update(change)
    p.write_text(json.dumps(value));return p


def environment():
    return dict(HOST_CASE_REPOSITORY='T1doo/ParkWeave',HOST_CASE_REF=b.BRANCH,
        HOST_CASE_EVENT='push',HOST_CASE_NUMBER='1',HOST_CASE_ATTEMPT='1',HOST_CASE_PUBLIC='true',
        RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux')


def git_answers(*args):
    command=args[1:]
    return {('rev-parse','HEAD'):SHA,('rev-list','--parents','-n','1','HEAD'):SHA+' '+PARENT,
        ('diff','--name-only',PARENT,SHA):b.APPROVAL_FILE,('status','--porcelain'):'',
        ('show',PARENT+':'+b.APPROVAL_FILE):json.dumps(dict(approved=False,source_sha=None,approval_ref=None))}[command]


def test_pending_bootstrap_denies_before_claim_or_any_physical_action(tmp_path,monkeypatch,capsys):
    approval(tmp_path,approved=False,source_sha=None,approval_ref=None)
    monkeypatch.chdir(tmp_path);monkeypatch.setattr(b.os,'geteuid',lambda:0)
    def forbidden(*a,**kw):raise AssertionError('CLAIM_OR_TARGET_FORBIDDEN')
    monkeypatch.setattr(b.os,'open',forbidden)
    assert b.bootstrap(SHA)==1
    result=json.loads(capsys.readouterr().out)
    assert result['cases']['GATE']=='FAIL' and set(result['cases'].values())=={'FAIL','NOT_RUN'}
    assert result['cleanup'] is False and result['failure_logs']=='UNAVAILABLE'


@pytest.mark.parametrize('field,value',[
    ('HOST_CASE_REPOSITORY','another/repo'),('HOST_CASE_REF','refs/heads/main'),
    ('HOST_CASE_EVENT','workflow_dispatch'),('HOST_CASE_NUMBER','2'),('HOST_CASE_ATTEMPT','2'),
    ('HOST_CASE_PUBLIC','false'),('RUNNER_ENVIRONMENT','self-hosted'),('RUNNER_OS','Windows')])
def test_untrusted_workflow_context_refused_before_git(tmp_path,monkeypatch,field,value):
    approval(tmp_path);monkeypatch.setattr(b.os,'geteuid',lambda:0)
    env=environment();env[field]=value
    with pytest.raises(PermissionError,match='NEW_EXPLICIT'):b.gate(tmp_path,SHA,env)


@pytest.mark.parametrize('change',[{'approved':1},{'approved':False},
    {'approval_ref':'USER_CONFIRMED_CASE_PG_VERTICAL_ONCE_20261013'},
    {'source_sha':'short'},{'extra':True}])
def test_new_exact_approval_required(tmp_path,monkeypatch,change):
    approval(tmp_path,**change);monkeypatch.setattr(b.os,'geteuid',lambda:0)
    with pytest.raises(PermissionError):b.gate(tmp_path,SHA,environment())


def test_duplicate_approval_keys_refused(tmp_path,monkeypatch):
    p=approval(tmp_path);p.write_text('{"approved":false,"approved":true}')
    monkeypatch.setattr(b.os,'geteuid',lambda:0)
    with pytest.raises(ValueError,match='DUPLICATE'):b.gate(tmp_path,SHA,environment())


def test_exact_pending_parent_and_approval_only_child_passes_read_gate(tmp_path,monkeypatch):
    approval(tmp_path);monkeypatch.setattr(b.os,'geteuid',lambda:0)
    monkeypatch.setattr(b,'git',git_answers)
    assert b.gate(tmp_path,SHA,environment())==PARENT


@pytest.mark.parametrize('bad_command,bad_result',[
    (('rev-parse','HEAD'),'c'*40),
    (('rev-list','--parents','-n','1','HEAD'),SHA+' '+PARENT+' '+'c'*40),
    (('diff','--name-only',PARENT,SHA),b.APPROVAL_FILE+'\nsrc/parkweave/api.py'),
    (('status','--porcelain'),' M source.py'),
    (('show',PARENT+':'+b.APPROVAL_FILE),'{"approved":true,"source_sha":null,"approval_ref":null}')])
def test_source_chain_dirty_or_extra_diff_refused(tmp_path,monkeypatch,bad_command,bad_result):
    approval(tmp_path);monkeypatch.setattr(b.os,'geteuid',lambda:0)
    monkeypatch.setattr(b,'git',lambda *a:bad_result if a[1:]==bad_command else git_answers(*a))
    with pytest.raises(PermissionError,match='REVIEWED_PARENT'):b.gate(tmp_path,SHA,environment())


@pytest.mark.parametrize('change',[{'phase':POISON},{'error':POISON},{'failure_logs':POISON},
    {'cases':{'GATE':'PASS'}},{'cleanup':1},{'source_sha':POISON},{'secret':POISON},
    {'diagnostics':[{'case':'GATE','line':1,'trace_sha256':'a'*64,'raw':POISON}]},
    {'diagnostics':[{'case':'GATE','line':True,'trace_sha256':'a'*64}]}])
def test_closed_public_result_refuses_private_or_untyped_values(change):
    result=b.initial(SHA);result.update(change)
    with pytest.raises(ValueError) as e:b.public_summary(result)
    assert POISON not in str(e.value)


def context():
    return dict(root=ROOT,source_sha=SHA,source=ROOT+'/source',environment=ROOT+'/environment',
        imports=[ROOT+'/source',ROOT+'/environment/lib/python3.12',ROOT+'/environment/lib/python3.12/lib-dynload',
            ROOT+'/environment/lib/python3.12/site-packages'],approval_ref=b.APPROVAL_REF,
        bootstrap_pid=10,bootstrap_started='SYNTHETIC_START')


def test_declaration_never_issues_root_controller_authority(monkeypatch):
    controller=c.Controller(context())
    monkeypatch.setattr(c.os,'geteuid',lambda:0)
    result=controller.run()
    assert result['error']=='REFUSED' and result['cases']['GATE']=='FAIL'
    assert not controller.processes and not controller.created_users


@pytest.mark.parametrize('change',[{'root':'/tmp/other'},{'approval_ref':'OLD_APPROVAL'},
    {'bootstrap_pid':True},{'imports':['/unprotected']},{'extra':POISON}])
def test_context_must_match_entire_new_protected_layout(change):
    value=context();assert c.context_valid(value)
    value.update(change);assert not c.context_valid(value)


class Child:
    pid=12345
    def __init__(self):
        class Pipe(BytesIO):
            def fileno(self):return 21
        self.stdin=Pipe();self.returncode=None;self.terminated=False
    def poll(self):return self.returncode
    def wait(self,timeout):self.returncode=0;return 0
    def terminate(self):self.terminated=True;self.returncode=-15


def test_normal_close_uses_no_reply_and_waits_for_exact_child(monkeypatch):
    controller=c.Controller(context());p=Child();controller.processes=[p];controller.starts[id(p)]='start'
    monkeypatch.setattr(c.writer,'_pid_started',lambda pid:'start')
    monkeypatch.setattr(c.select,'select',lambda *a:([],[p.stdin],[]))
    monkeypatch.setattr(c.os,'write',lambda fd,raw:p.stdin.write(raw))
    controller._close_owned(p)
    assert p.stdin.getvalue()==b'{"operation":"CLOSE"}\n' and p.returncode==0 and not p.terminated


def test_close_refuses_reused_pid_before_signal_or_write(monkeypatch):
    controller=c.Controller(context());p=Child();controller.processes=[p];controller.starts[id(p)]='old'
    monkeypatch.setattr(c.writer,'_pid_started',lambda pid:'new')
    with pytest.raises(PermissionError):controller._close_owned(p)
    assert p.stdin.getvalue()==b'' and not p.terminated


def test_cleanup_failure_retains_identity_owner_and_private_files(monkeypatch):
    controller=c.Controller(context());controller.value['error']='FAILURE'
    controller.created_users={'pwci_writer':(123,124)};controller.creation_attempts=1
    def forbidden(*a,**kw):raise AssertionError('IDENTITY_REMOVAL_FORBIDDEN_ON_FAILURE')
    monkeypatch.setattr(controller,'tool',forbidden)
    assert not controller.cleanup()
    assert controller.value['cases']['IDENTITIES_REMOVED']=='FAIL'
    assert controller.value['cases']['FILES_REMOVED']=='FAIL'


def test_partial_creation_never_deletes_unconfirmed_identities(monkeypatch):
    controller=c.Controller(context());controller.creation_attempts=1
    def forbidden(*a,**kw):raise AssertionError('UNCONFIRMED_IDENTITY_REMOVAL')
    monkeypatch.setattr(controller,'tool',forbidden)
    assert not controller.cleanup()
    assert controller.value['cases']['IDENTITIES_REMOVED']=='FAIL'


def test_setup_keeps_original_store_before_migration_failure(monkeypatch):
    class Conn:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def execute(self,*a):pass
    proof=SimpleNamespace(record_created_database=lambda connection:object())
    owner=SimpleNamespace(connect=lambda:Conn(),migrate=lambda:(_ for _ in ()).throw(RuntimeError('synthetic migration failure')))
    monkeypatch.setattr(w.os,'geteuid',lambda:500)
    monkeypatch.setattr(w,'capture_fixture_cluster',lambda *a:proof)
    monkeypatch.setattr(w.psycopg,'connect',lambda *a,**kw:Conn())
    monkeypatch.setattr(w,'Store',lambda *a:owner)
    owned={}
    cfg=dict(pg_uid=500,data='/synthetic/data',owner_maintenance_dsn='host=/synthetic dbname=postgres',database='fixture_'+'a'*32)
    with pytest.raises(RuntimeError,match='migration failure'):w.setup(cfg,owned)
    assert owned['store'] is owner and owned['cluster'] is proof and owned['database_attempted'] is True
    assert owner._case_fact_fixture_receipt is not None


def test_drop_unknown_creation_never_connects_or_adopts():
    with pytest.raises(Denied,match='unconfirmed'):w.drop_owned({},dict(database_attempted=True))


def test_forged_database_proof_refused_before_connection():
    with pytest.raises(Denied,match='issued creation'):w.checked_owner(SimpleNamespace(_case_fact_fixture_receipt=object()))


def test_protected_copy_refuses_source_link_before_copy(tmp_path):
    source=tmp_path/'source';source.symlink_to('/usr/bin/python3')
    with pytest.raises(PermissionError,match='protected source'):b.protected_copy(source,tmp_path/'target')
    assert not (tmp_path/'target').exists()


def test_business_input_wrong_peer_refused_before_store():
    with pytest.raises(Denied,match='identity'):w.business_session(dict(api_uid=-1))


def test_business_connection_wrong_database_closes_and_refuses(monkeypatch):
    _,binding=inputs();calls=[]
    class Conn:
        info=SimpleNamespace(host=binding.database_host,port=binding.database_port)
        def execute(self,*args):return SimpleNamespace(fetchone=lambda:dict(db='postgres',oid=1,session='pwci_case',role='pwci_case',owner=binding.installer_role))
        def close(self):calls.append('close')
        def rollback(self):calls.append('rollback')
    monkeypatch.setattr(Store,'connect',lambda self:Conn())
    store=w.BusinessStore(dsn(binding),binding)
    with pytest.raises(Denied,match='exact business'):store.connect()
    assert calls==['close']


def test_business_drop_response_has_one_post_then_original_get(monkeypatch,capsys):
    spec,binding=inputs();requests=[]
    cfg=dict(api_uid=100,api_gid=101,ipc_gid=102,spec=spec,business_binding=binding.model_dump(),
        business_dsn=dsn(binding),tokens={binding.source.owner_id:'SYNTHETIC_ONLY'})
    monkeypatch.setattr(w.os,'geteuid',lambda:100);monkeypatch.setattr(w.os,'getegid',lambda:101)
    monkeypatch.setattr(w.os,'getgroups',lambda:[102])
    monkeypatch.setattr(w,'BusinessStore',lambda *a:object());monkeypatch.setattr(w,'create_app',lambda *a:object())
    class Client:
        def __init__(self,*a):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def request(self,method,path,**kw):
            requests.append((method,path,kw));return SimpleNamespace(status_code=200,json=lambda:dict(private=POISON))
    monkeypatch.setattr(w,'TestClient',Client)
    body=dict(case_id=binding.source.case_id,expected_preparation_revision=binding.source.preparation_revision,
        expected_lifecycle_revision=0,expected_source_sha256='a'*64,confirm_cancel=True,reason='SYNTHETIC explicit')
    messages=[dict(operation='CANCEL_DROP',key='original',body=body),dict(operation='RECOVER',key='original'),dict(operation='CLOSE')]
    monkeypatch.setattr(w.sys,'stdin',SimpleNamespace(buffer=BytesIO(('\n'.join(map(json.dumps,messages))+'\n').encode())))
    w.business_session(cfg)
    output=capsys.readouterr().out.splitlines()
    assert json.loads(output[0])==dict(result=dict(sent_once=True)) and POISON not in output[0]
    assert [x[0] for x in requests]==['POST','GET']
    assert requests[0][1]==binding.read_path() and requests[1][1]==binding.recovery_path('original')
    assert requests[0][2]['headers']['Idempotency-Key']=='original'

@pytest.mark.parametrize('chunks',[[b'{"result":',b'1}\n'],[b'{"result":1}\n']])
def test_private_frame_partial_reads_are_bounded_and_complete(monkeypatch,chunks):
    controller=c.Controller(context());p=SimpleNamespace(stdout=SimpleNamespace(fileno=lambda:20));controller.processes=[p]
    parts=iter(chunks)
    monkeypatch.setattr(c.select,'select',lambda *a:([p.stdout],[],[]))
    monkeypatch.setattr(c.os,'read',lambda *a:next(parts))
    assert controller.read_frame(p,1)==dict(result=1)


def test_partial_frame_timeout_never_blocks_on_readline(monkeypatch):
    controller=c.Controller(context());p=SimpleNamespace(stdout=SimpleNamespace(fileno=lambda:20));controller.processes=[p]
    answers=iter([([p.stdout],[],[]),([],[],[])])
    monkeypatch.setattr(c.select,'select',lambda *a:next(answers))
    monkeypatch.setattr(c.os,'read',lambda *a:b'{"result":')
    with pytest.raises(TimeoutError,match='bounded'):controller.read_frame(p,1)


@pytest.mark.parametrize('raw',[b'',b'{"result":1}\n{"secret":"SYNTHETIC"}\n',b'x'*524289])
def test_missing_unsolicited_or_large_frames_refused(monkeypatch,raw):
    controller=c.Controller(context());p=SimpleNamespace(stdout=SimpleNamespace(fileno=lambda:20));controller.processes=[p]
    monkeypatch.setattr(c.select,'select',lambda *a:([p.stdout],[],[]))
    monkeypatch.setattr(c.os,'read',lambda *a:raw)
    with pytest.raises(ValueError):controller.read_frame(p,1)


def test_private_rpc_never_retries_timed_out_write(monkeypatch):
    controller=c.Controller(context());p=SimpleNamespace(stdin=SimpleNamespace(fileno=lambda:21));controller.processes=[p]
    monkeypatch.setattr(c.select,'select',lambda *a:([],[],[]))
    def forbidden(*a):raise AssertionError('UNREADY_WRITE')
    monkeypatch.setattr(c.os,'write',forbidden)
    with pytest.raises(TimeoutError,match='write'):controller.call(p,dict(operation='RECOVER',key='original'))


def test_new_workflow_is_closed_to_candidate_branch_and_nonstandard_runners():
    root=Path(__file__).resolve().parents[1]
    text=(root/'.github/workflows/host-case-security-once.yml').read_text()
    pending=json.loads((root/b.APPROVAL_FILE).read_text())
    assert pending==dict(approved=False,source_sha=None,approval_ref=None)
    assert 'branches: [dev/f2-host-case-security-once-20261013]' in text
    assert 'dev/f2-host-case-once-candidate-20261013' not in text
    assert 'github.run_attempt == 1 && github.run_number == 1' in text
    assert 'persist-credentials: false' in text and 'runs-on: ubuntu-24.04' in text
    assert 'timeout-minutes: 25' in text and 'timeout-minutes: 23' in text
    for denied in ('workflow_dispatch:','pull_request:','upload-artifact','actions/cache','matrix:','secrets.','self-hosted'):
        assert denied not in text


def test_cleanup_reclaims_credentials_before_identity_removal_even_if_rmtree_fails(monkeypatch):
    import stat
    controller=c.Controller(context());events=[]
    controller.root_instance=(2,3)
    controller.worker=SimpleNamespace(pw_uid=200);controller.pg=SimpleNamespace(pw_uid=201)
    controller.created_users={'pwci_writer':(200,202)};controller.creation_attempts=1
    monkeypatch.setattr(controller,'_no_unknown_identity_users',lambda:None)
    monkeypatch.setattr(Path,'lstat',lambda self:SimpleNamespace(st_mode=stat.S_IFDIR|0o711,st_uid=0,st_dev=2,st_ino=3))
    current={'uid':None}
    def opened(path,flags):
        current['uid']=200 if str(path).endswith('bootstrap.json') else 201
        assert flags&os.O_NOFOLLOW;return 90
    monkeypatch.setattr(c.os,'open',opened)
    monkeypatch.setattr(c.os,'fstat',lambda fd:SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_uid=current['uid'],st_nlink=1))
    monkeypatch.setattr(c.os,'fchown',lambda fd,uid,gid:events.append(('reclaim',current['uid'],uid,gid)))
    monkeypatch.setattr(c.os,'fchmod',lambda fd,mode:events.append(('protect',mode)))
    monkeypatch.setattr(c.os,'close',lambda fd:None)
    monkeypatch.setattr(c.pwd,'getpwnam',lambda name:SimpleNamespace(pw_uid=200,pw_gid=202))
    monkeypatch.setattr(controller,'tool',lambda args:events.append(('delete',args[-1])))
    monkeypatch.setattr(c.shutil,'rmtree',lambda path:(_ for _ in ()).throw(OSError('synthetic remove failure')))
    assert not controller.cleanup()
    assert events==[('reclaim',200,0,0),('protect',0o600),('reclaim',201,0,0),('protect',0o600),('delete','pwci_writer')]
    assert controller.value['cases']['IDENTITIES_REMOVED']=='PASS' and controller.value['cases']['FILES_REMOVED']=='FAIL'


def test_cleanup_refuses_changed_credential_owner_before_identity_delete(monkeypatch):
    import stat
    controller=c.Controller(context());controller.root_instance=(2,3)
    controller.worker=SimpleNamespace(pw_uid=200);controller.pg=SimpleNamespace(pw_uid=201)
    controller.created_users={'pwci_writer':(200,202)};controller.creation_attempts=1
    monkeypatch.setattr(controller,'_no_unknown_identity_users',lambda:None)
    monkeypatch.setattr(Path,'lstat',lambda self:SimpleNamespace(st_mode=stat.S_IFDIR|0o711,st_uid=0,st_dev=2,st_ino=3))
    monkeypatch.setattr(c.os,'open',lambda *a:90)
    monkeypatch.setattr(c.os,'fstat',lambda fd:SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_uid=999,st_nlink=1))
    monkeypatch.setattr(c.os,'close',lambda fd:None)
    assert not controller.cleanup()
    assert controller.value['cases']['IDENTITIES_REMOVED']=='FAIL' and controller.value['cases']['FILES_REMOVED']=='FAIL'


def test_full_close_pipe_times_out_without_buffered_write_or_wait(monkeypatch):
    controller=c.Controller(context());p=Child();controller.processes=[p];controller.starts[id(p)]='start'
    monkeypatch.setattr(c.writer,'_pid_started',lambda pid:'start')
    monkeypatch.setattr(c.select,'select',lambda *a:([],[],[]))
    with pytest.raises(TimeoutError,match='write'):controller._close_owned(p)
    assert p.returncode is None and not p.terminated and not p.stdin.getvalue()


def test_cleanup_deadline_escapes_per_resource_handlers(monkeypatch):
    controller=c.Controller(context());controller.business=Child();controller.client=Child();seen=[]
    def expired(p):
        seen.append(p);raise c.CleanupTimeout('synthetic deadline')
    monkeypatch.setattr(controller,'_close_owned',expired)
    with pytest.raises(c.CleanupTimeout):controller.cleanup()
    assert seen==[controller.business] and not controller.value['cleanup']


def test_cleanup_absolute_deadline_refuses_further_pipe_operations(monkeypatch):
    controller=c.Controller(context());controller.cleanup_deadline=1
    monkeypatch.setattr(c.time,'monotonic',lambda:2)
    p=Child();controller.processes=[p]
    with pytest.raises(c.CleanupTimeout):controller.write_frame(p,dict(operation='CLOSE'))
    assert not p.stdin.getvalue()


def test_actual_control_denial_rolls_back_before_positive_query(monkeypatch):
    calls=[]
    class Conn:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def execute(self,query):
            calls.append(query)
            if 'pg_control_system' in query:raise psycopg.errors.InsufficientPrivilege('SYNTHETIC denied')
            return SimpleNamespace(fetchone=lambda:dict(value=1))
        def rollback(self):calls.append('ROLLBACK')
    monkeypatch.setattr(w.psycopg,'connect',lambda *a,**kw:Conn())
    w.denied_control_positive('SYNTHETIC_ONLY_DSN')
    assert calls==['SELECT system_identifier FROM pg_catalog.pg_control_system()','ROLLBACK','SELECT 1 value']


def test_unexpected_control_execute_permission_refused(monkeypatch):
    class Conn:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def execute(self,query):return SimpleNamespace(fetchone=lambda:dict(value=1))
    monkeypatch.setattr(w.psycopg,'connect',lambda *a,**kw:Conn())
    with pytest.raises(Denied,match='control-system'):w.denied_control_positive('SYNTHETIC_ONLY_DSN')
