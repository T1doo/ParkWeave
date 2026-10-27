"""Offline candidate contracts only: no subprocess, PG, API or token factory."""
import ast
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import template_upgrade_http_once as m


class Response:
    status_code=200
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def iter_bytes(self):yield b'{}'


class Client:
    def __init__(self):self.calls=[]
    def stream(self,*args,**kw):self.calls.append((args,kw));return Response()


def transport():
    client=Client();http=m.BudgetHTTP('http://127.0.0.1:12345',client,m.Clock(0,now=lambda:1),'SYNTHETIC_TOKEN')
    http.instance='00000000-0000-4000-8000-000000000001';http.target='00000000-0000-4000-8000-000000000002';http.target_hash='a'*64
    return http,client


def test_closed_before_any_process_or_private_directory(monkeypatch):
    def forbidden(*a,**kw):pytest.fail('closed candidate attempted an actual side effect')
    monkeypatch.setattr(m.subprocess,'check_output',forbidden)
    monkeypatch.setattr(m.PrivateRoot,'create',forbidden)
    assert m.main(['--source','a'*40,'--invocation','NOT_APPROVED'])==2
    with pytest.raises(m.Closed):m.Permit(m._SEAL,'a'*40,'NOT_APPROVED')


@pytest.mark.parametrize('path,options',[
    ('http://other.invalid/api/template-consumer/catalog',{}),
    ('/api/template-consumer/catalog?extra=1',{}),
    ('/api/template-consumer/catalog',{'method':'POST','headers':{'Authorization':m.PLACEHOLDER}}),
    ('/api/template-consumer/catalog',{'headers':{'Authorization':'Bearer OTHER'}}),
])
def test_page_boundary_denies_before_http(path,options):
    http,client=transport()
    with pytest.raises(m.Closed):http.page_read(path,options)
    assert not client.calls and http.gets==http.posts==0


def test_exact_page_get_and_no_redirect_or_proxy(monkeypatch):
    http,client=transport();http.page_read('/api/template-consumer/catalog',{'method':'GET','headers':{'Authorization':m.PLACEHOLDER,'Content-Type':'application/json'}})
    args,kw=client.calls[0];assert args==('GET','http://127.0.0.1:12345/api/template-consumer/catalog')
    assert kw['headers']=={'Authorization':'Bearer SYNTHETIC_TOKEN'} and kw['follow_redirects'] is False
    assert 'SYNTHETIC_TOKEN' not in json.dumps(http.traffic)
    for _ in range(19):http.page_read('/api/template-consumer/catalog',{'headers':{'Authorization':m.PLACEHOLDER,'Content-Type':'application/json'}})
    with pytest.raises(m.Closed):http.page_read('/api/template-consumer/catalog',{'headers':{'Authorization':m.PLACEHOLDER,'Content-Type':'application/json'}})
    assert len(client.calls)==20


def test_post_sequence_and_claimed_stage_cannot_open_arbitrary_post():
    http,client=transport()
    for path,body,actor,stage in [('/api/other',{},'template-author','publication'),('/api/template-consumer/instances',{},None,'create')]:
        with pytest.raises(m.Closed):http.request('POST',path,body=body,actor=actor,stage=stage)
    assert not client.calls
    path='/api/template-candidate/park-a/new-enterprise-material-template/commands'
    http.request('POST',path,body={'action':'SAVE_DRAFT'},actor='template-author',stage='publication',key='SYNTHETIC_KEY')
    with pytest.raises(m.Closed):http.request('POST',path,body={'action':'SAVE_DRAFT'},actor='template-author',stage='publication',key='SYNTHETIC_KEY')
    assert len(client.calls)==1


def test_shared_clock_does_not_restart_for_cleanup():
    now=[299];clock=m.Clock(0,now=lambda:now[0]);assert clock.left(10)==1
    now[0]=301
    with pytest.raises(TimeoutError):clock.left()
    assert clock.left(30,cleanup=True)==14
    clock.stopped=True
    with pytest.raises(m.Closed):clock.left()
    assert clock.left(30,cleanup=True)==14


def test_report_blocks_raw_fields_and_secret_output(tmp_path):
    with pytest.raises(m.Closed):m.save(tmp_path/'never.json',{'message':'SYNTHETIC_TOKEN'},['SYNTHETIC_TOKEN'])
    assert not (tmp_path/'never.json').exists()
    valid=dict(status='FAIL',phase='START',real_models=False,worker_final=False,partial=True,sanitized=False)
    m.validate_worker_report(valid)
    for update in [{'Authorization':'SYNTHETIC_TOKEN'},{'phase':'SYNTHETIC_TOKEN'},{'error':{'type':'RuntimeError','errno':None,'message':'SYNTHETIC_TOKEN'}}]:
        with pytest.raises(m.Closed):m.validate_worker_report({**valid,**update})


def test_unknown_cleanup_retains_original_private_files():
    root=m.PrivateRoot.create(SimpleNamespace(check=lambda:None));payload=root.path/'payload';payload.write_text('SYNTHETIC')
    try:
        with pytest.raises(m.Closed):root.remove({'status':'CLEANUP_UNCONFIRMED'},{'status':'PASS','sanitized':True,'worker_final':True,'partial':False})
        assert payload.read_text()=='SYNTHETIC'
        with pytest.raises(m.Closed):root.remove({'status':'CLEANUP_CONFIRMED'},{'status':'PASS','sanitized':True,'worker_final':False,'partial':True})
        assert payload.exists()
        root.remove({'status':'CLEANUP_CONFIRMED'},{'status':'PASS','sanitized':True,'worker_final':True,'partial':False})
        assert not root.path.exists()
    finally:os.close(root.fd)


def test_original_supervisor_body_preserved_except_explicit_limits():
    old=ast.parse(Path('scripts/visual_owned_launch.py').read_text());new=ast.parse(Path('scripts/template_http_supervision.py').read_text())
    a=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=='supervise');b=deepcopy(next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=='supervise'))
    b.args=deepcopy(a.args);b.body[0]=deepcopy(a.body[0]);b.body[1]=deepcopy(a.body[1])
    assert ast.dump(a)==ast.dump(b)


def test_publication_uses_original_engine_dtos_without_http_service(tmp_path):
    from parkweave.template_candidate import TemplateEngine,TemplateRepository,Scope,Command,TemplateConfig
    from test_template_candidate import template_config
    config=template_config().model_dump()
    for permit in config['permits']:permit['scope']['park_id']='park-a'
    engine=TemplateEngine(TemplateConfig.model_validate(config),TemplateRepository(tmp_path/'synthetic.template.candidate.sqlite3'))
    actions=[];scope=Scope(park_id='park-a',template_id='new-enterprise-material-template')
    class HTTP:
        def request(self,method,path,*,actor,body=None,**kw):
            if method=='GET':return 200,engine.read(actor,scope)
            actions.append(body['action'])
            return 200,engine.command(actor,scope,kw['key'],Command.model_validate(body))
    first=m.publish(HTTP(),engine,'1');second=m.publish(HTTP(),engine,'2')
    assert first['release_id']!=second['release_id']
    assert actions==['SAVE_DRAFT','SUBMIT','REVIEW','CANDIDATE_PUBLISH','RETURN_DRAFT','SAVE_DRAFT','SUBMIT','REVIEW','CANDIDATE_PUBLISH']


def test_api_setup_and_cleanup_double_failure_preserves_primary(monkeypatch):
    import uvicorn
    state={}
    class Listener:
        def bind(self,address):state['bound']=address
        def getsockname(self):return ('127.0.0.1',12345)
        def close(self):state['closed']=True;raise OSError(5,'SYNTHETIC private detail')
    def fail(*args,**kwargs):raise ValueError('SYNTHETIC private detail')
    monkeypatch.setattr(m.socket,'socket',Listener)
    monkeypatch.setattr(m.socket,'create_connection',lambda *a,**kw:(_ for _ in ()).throw(ConnectionRefusedError()))
    monkeypatch.setattr(uvicorn,'Config',fail)
    with pytest.raises(ValueError) as result:
        with m.api_server(object(),m.Clock(0,now=lambda:1)):pytest.fail('yielded after setup failure')
    assert state['closed'] and result.value.http_cleanup_errors==[{'type':'OSError','errno':5}]
    assert 'private detail' not in json.dumps(result.value.http_cleanup_errors)


def test_approved_invocation_cannot_self_attest_source(monkeypatch):
    approval=SimpleNamespace(invocation='PW_HTTP_SYNTHETIC',check=lambda:None,reviewed_source='a'*40)
    monkeypatch.setattr(m.activation,'load',lambda invocation:approval)
    monkeypatch.setattr(m.activation,'git',lambda args,started:b'b'*40+b'\n' if args==['rev-parse','HEAD'] else b'wrong')
    with pytest.raises(m.Closed):m.authorize('c'*40,'PW_HTTP_SYNTHETIC')
    with pytest.raises(m.Closed):m.Permit(m._SEAL,'b'*40,'PW_HTTP_OTHER',approval)


def test_delete_and_publication_expired_deadline_preserve_original(monkeypatch,tmp_path):
    root=m.PrivateRoot.create(SimpleNamespace(check=lambda:None));payload=root.path/'payload';payload.write_text('SYNTHETIC')
    target=tmp_path/'result.json';target.write_text('SYNTHETIC_ORIGINAL')
    monkeypatch.setattr(m.time,'monotonic',lambda:360)
    try:
        with pytest.raises(TimeoutError):root.remove({'status':'CLEANUP_CONFIRMED'},{'status':'PASS','sanitized':True,'worker_final':True,'partial':False},deadline=360)
        assert payload.read_text()=='SYNTHETIC'
        with pytest.raises(TimeoutError):m.save(target,{'status':'PASS'},deadline=360)
        assert target.read_text()=='SYNTHETIC_ORIGINAL'
        monkeypatch.setattr(m.time,'monotonic',lambda:359)
        root.remove({'status':'CLEANUP_CONFIRMED'},{'status':'PASS','sanitized':True,'worker_final':True,'partial':False},deadline=360)
    finally:os.close(root.fd)


def test_created_root_verify_failure_closes_owned_fd_preserves_directory(monkeypatch):
    opened=[];original=m.os.open
    def record(*a,**kw):
        fd=original(*a,**kw);opened.append(fd);return fd
    monkeypatch.setattr(m.os,'open',record)
    monkeypatch.setattr(m.PrivateRoot,'verify',lambda self:(_ for _ in ()).throw(ValueError('SYNTHETIC')))
    with pytest.raises(ValueError) as result:m.PrivateRoot.create(SimpleNamespace(check=lambda:None))
    retained=Path(result.value.private_created_path)
    try:
        assert retained.is_dir() and result.value.private_close_errors==[]
        with pytest.raises(OSError):os.fstat(opened[0])
    finally:retained.rmdir() # Exact empty directory created by this test, no process.


def test_deadline_during_walk_retains_remaining_owned_file(monkeypatch):
    root=m.PrivateRoot.create(SimpleNamespace(check=lambda:None))
    for name in ('a','b'):(root.path/name).write_text('SYNTHETIC')
    now=[359];original=m.os.unlink
    def unlink(*a,**kw):original(*a,**kw);now[0]=360
    monkeypatch.setattr(m.os,'unlink',unlink);monkeypatch.setattr(m.time,'monotonic',lambda:now[0])
    try:
        with pytest.raises(TimeoutError):root.remove({'status':'CLEANUP_CONFIRMED'},{'status':'PASS','sanitized':True,'worker_final':True,'partial':False},deadline=360)
        assert root.path.exists() and len(list(root.path.iterdir()))==1
    finally:
        monkeypatch.setattr(m.os,'unlink',original);now[0]=359
        root.remove({'status':'CLEANUP_CONFIRMED'},{'status':'PASS','sanitized':True,'worker_final':True,'partial':False},deadline=360);os.close(root.fd)


def test_nested_browser_and_api_cleanup_errors_both_survive(monkeypatch):
    import uvicorn
    class Listener:
        def bind(self,address):pass
        def getsockname(self):return ('127.0.0.1',12345)
        def close(self):raise OSError(5,'SYNTHETIC API close failed')
    class Thread:
        ident=1
        def __init__(self,**kw):pass
        def start(self):pass
        def join(self,*args):raise TimeoutError('SYNTHETIC API join failed')
    monkeypatch.setattr(m.socket,'socket',Listener)
    monkeypatch.setattr(m.socket,'create_connection',lambda *a,**kw:(_ for _ in ()).throw(ConnectionRefusedError()))
    monkeypatch.setattr(m.threading,'Thread',Thread)
    monkeypatch.setattr(uvicorn,'Config',lambda *a,**kw:None)
    monkeypatch.setattr(uvicorn,'Server',lambda *a,**kw:SimpleNamespace(started=True,run=lambda:None))
    primary=ValueError('SYNTHETIC original browser failure')
    primary.http_cleanup_errors=[{'type':'RuntimeError','errno':None}]
    with pytest.raises(ValueError) as caught:
        with m.api_server(object(),m.Clock(0,now=lambda:1)):raise primary
    assert caught.value is primary
    assert primary.http_cleanup_errors==[{'type':'RuntimeError','errno':None},{'type':'TimeoutError','errno':None},{'type':'OSError','errno':5}]
