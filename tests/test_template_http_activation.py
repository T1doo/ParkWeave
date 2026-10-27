"""Pure synthetic activation/clock/files; no process, service or real permit."""
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import template_http_activation as a
from scripts import template_upgrade_http_once as m


@pytest.fixture
def approved(tmp_path,monkeypatch):
    path=tmp_path/a.RELATIVE;path.parent.mkdir()
    value=dict(version=1,enabled=True,reviewed_source='a'*40,invocation='PW_HTTP_SYNTHETIC_TEST',expires_utc='2026-10-26T12:30:00Z')
    path.write_text(json.dumps(value));monkeypatch.setattr(a,'ROOT',tmp_path)
    now=datetime(2026,10,26,12,tzinfo=timezone.utc).timestamp();monkeypatch.setattr(a.time,'time',lambda:now)
    return a.load(value['invocation']),path,value


def test_closed_contract_and_duplicate_fields_fail_without_git(tmp_path,monkeypatch):
    path=tmp_path/a.RELATIVE;path.parent.mkdir();monkeypatch.setattr(a,'ROOT',tmp_path)
    path.write_text('{"version":1,"enabled":false,"reviewed_source":null,"invocation":null,"expires_utc":null}')
    with pytest.raises(a.Closed):a.load('PW_HTTP_SYNTHETIC_TEST')
    path.write_text('{"version":1,"enabled":true,"enabled":true}')
    with pytest.raises(a.Closed):a.load('PW_HTTP_SYNTHETIC_TEST')


def test_source_exact_activation_only_and_parent_bytes(approved,monkeypatch):
    approval,path,value=approved
    def git(args,started):
        assert started==100
        responses={('rev-parse','HEAD'):b'b'*40+b'\n',('branch','--show-current'):a.BRANCH.encode()+b'\n',('status','--porcelain'):b'',('rev-parse','HEAD^'):b'a'*40+b'\n',('diff','--name-only','-z','a'*40,'b'*40):a.RELATIVE.encode()+b'\0',('show','b'*40+':'+a.RELATIVE):approval.raw}
        return responses[tuple(args)]
    monkeypatch.setattr(a,'git',git);a.verify_source('b'*40,approval,100)
    for overridden in (['rev-parse','HEAD^'],['status','--porcelain'],['diff','--name-only','-z','a'*40,'b'*40],['show','b'*40+':'+a.RELATIVE]):
        monkeypatch.setattr(a,'git',lambda args,started,bad=overridden:b'other' if args==bad else git(args,started))
        with pytest.raises(a.Closed):a.verify_source('b'*40,approval,100)
    path.write_text(json.dumps({**value,'invocation':'PW_HTTP_CHANGED_TEST'}))
    with pytest.raises(a.Closed):approval.check()


def test_git_uses_original_shared_deadline(monkeypatch):
    calls=[];monkeypatch.setattr(a.time,'monotonic',lambda:459)
    monkeypatch.setattr(a.subprocess,'check_output',lambda args,**kw:calls.append(kw) or b'OK')
    assert a.git(['status'],100)==b'OK' and calls[0]['timeout']==1
    monkeypatch.setattr(a.time,'monotonic',lambda:460)
    with pytest.raises(TimeoutError):a.git(['status'],100)
    assert len(calls)==1


def test_watchdog_is_absolute_daemon_never_canceled_or_resets(monkeypatch):
    state={};monkeypatch.setattr(a.time,'monotonic',lambda:150)
    class Timer:
        def __init__(self,seconds,callback):state.update(seconds=seconds,callback=callback);self.daemon=False
        def start(self):state['daemon']=self.daemon
        def cancel(self):pytest.fail('would reopen shutdown gap')
    monkeypatch.setattr(a.threading,'Timer',Timer);monkeypatch.setattr(a.os,'_exit',lambda code:state.update(exit=code))
    watchdog=a.TotalDeadline(100);watchdog.arm()
    assert state['seconds']==310 and state['daemon']
    state['callback']();assert state['exit']==124
    monkeypatch.setattr(a.time,'monotonic',lambda:460)
    with pytest.raises(TimeoutError):a.TotalDeadline(100).arm()


def test_once_marker_no_replay_original_clock_parent_and_file_identity(tmp_path,monkeypatch):
    monkeypatch.setattr(a.OnceClaim,'path_for',staticmethod(lambda invocation:tmp_path/'one-owned-marker'))
    monkeypatch.setattr(a.time,'monotonic',lambda:105)
    claim=a.OnceClaim.create('b'*40,'PW_HTTP_SYNTHETIC_TEST',100,777)
    with pytest.raises(FileExistsError):a.OnceClaim.create('b'*40,'PW_HTTP_SYNTHETIC_TEST',100,777)
    restored=a.OnceClaim.restore(claim.path,claim.identity,claim.file_identity,'b'*40,'PW_HTTP_SYNTHETIC_TEST',os.getpid(),777)
    assert restored.value['started']==100
    with pytest.raises(a.Closed):a.OnceClaim.restore(claim.path,claim.identity,claim.file_identity,'b'*40,'PW_HTTP_SYNTHETIC_TEST',os.getpid(),778)
    replacement=claim.path/'replacement';replacement.write_text(json.dumps(claim.value));os.replace(replacement,claim.path/'claim.json')
    with pytest.raises(a.Closed):claim.check('b'*40,'PW_HTTP_SYNTHETIC_TEST')
    assert claim.path.exists() # No cleanup/replay of an unknown marker.


def test_frozen_client_executes_initial_reviewed_bytes_and_rejects_drift(tmp_path,monkeypatch):
    repo=tmp_path/'repo';(repo/'scripts').mkdir(parents=True);original=repo/'scripts/template_upgrade_http_client.js';original.write_bytes(b'// SYNTHETIC_REVIEWED')
    private=tmp_path/'private';private.mkdir();monkeypatch.setattr(m,'ROOT',repo)
    monkeypatch.setattr(a,'git',lambda args,started:b'// SYNTHETIC_REVIEWED')
    frozen=m.freeze_client(SimpleNamespace(check=lambda:None,source='b'*40),private,m.Clock(100,now=lambda:101))
    original.write_bytes(b'// CHANGED_DURING_SETUP')
    assert m.verify_frozen_client(frozen).read_bytes()==b'// SYNTHETIC_REVIEWED'
    frozen[0].write_bytes(b'// CHANGED_FROZEN_COPY')
    with pytest.raises(a.Closed):m.verify_frozen_client(frozen)


def test_default_entry_never_arms_deadline_or_claims(monkeypatch):
    monkeypatch.setattr(a.TotalDeadline,'arm',lambda self:pytest.fail('default started watchdog'))
    monkeypatch.setattr(a.OnceClaim,'create',lambda *a,**kw:pytest.fail('default consumed window'))
    assert m.main(['--source','b'*40,'--invocation','PW_HTTP_SYNTHETIC_TEST'])==2


def test_parent_worker_timing_and_final_status_contract():
    assert (m.WORK,m.INNER,m.TREE,m.TOTAL)==(300,315,330,360)
    import inspect
    code=inspect.getsource(m.main)
    assert "OBSERVED_COMPLETE_REQUIRES_EXIT_0" in code
    assert 'cleanup_reserve_seconds=30' in code
    assert 'watchdog.arm()' in code and '.cancel()' not in code


@pytest.mark.parametrize('owned_status,expected,removed',[('CLEANUP_CONFIRMED',0,True),('CLEANUP_UNCONFIRMED',1,False)])
def test_full_entry_glue_and_unknown_tree_without_services(tmp_path,monkeypatch,owned_status,expected,removed):
    state={};permit=SimpleNamespace(source='b'*40,invocation='PW_HTTP_SYNTHETIC_TEST',check=lambda:None)
    monkeypatch.setattr(a,'load',lambda invocation:object())
    monkeypatch.setattr(a.TotalDeadline,'arm',lambda self:state.update(started=self.started))
    monkeypatch.setattr(m,'authorize',lambda *args:permit)
    monkeypatch.setattr(m.tree,'identity',lambda pid:{'start_ticks':777})
    claim=SimpleNamespace(path=tmp_path/'synthetic-marker',identity=(1,2),file_identity=(3,4))
    monkeypatch.setattr(a.OnceClaim,'create',lambda *args:claim)
    roots=[]
    def create(permit,*,evidence=False):
        path=tmp_path/('evidence' if evidence else 'data');path.mkdir()
        fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
        root=SimpleNamespace(path=path,fd=fd,identity=os.fstat(fd),verify=lambda:None)
        root.remove=lambda *args,**kw:state.update(removed=True)
        roots.append(root);return root
    monkeypatch.setattr(m.PrivateRoot,'create',create)
    def supervise(argv,**kw):
        state['argv']=argv;assert kw['started']==state['started']
        assert argv[-6]=='--claim' and argv[-5:]==[str(claim.path),'1','2','3','4']
        value=dict(status='PASS',phase='ORIGINAL_PAGE_REAL_HTTP',real_models=False,worker_final=True,partial=False,sanitized=True,GET=3,POST=12)
        (kw['directory']/'result.json').write_text(json.dumps(value))
        return dict(status=owned_status,operation_status='PASS')
    monkeypatch.setattr(m.tree,'supervise',supervise)
    assert m.main(['--source','b'*40,'--invocation','PW_HTTP_SYNTHETIC_TEST'])==expected
    report=json.loads((tmp_path/'evidence/result.json').read_text())
    assert state.get('removed',False)==removed
    assert report['status']==('OBSERVED_COMPLETE_REQUIRES_EXIT_0' if removed else 'FAIL')
    assert report['required_exit']==0 and report['cleanup_reserve_seconds']==30
    assert ('directory_retained' in report)!=removed
