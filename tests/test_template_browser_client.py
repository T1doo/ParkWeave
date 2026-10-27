"""Offline contracts only: synthetic bytes, fake transport/Playwright, no services."""
from hashlib import sha256
import json
import os
from pathlib import Path
from types import SimpleNamespace
import time
import pytest
import httpx
from scripts import template_browser_client as b
from scripts import template_upgrade_http_once as m
from scripts import template_http_activation as a


class Response:
    def __init__(self,body,code,headers):self.body=body;self.status_code=code;self.headers=httpx.Headers(headers)
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_bytes(self):yield self.body


class Client:
    def __init__(self):self.calls=[];self.body=b'SYNTHETIC ORIGINAL RESPONSE';self.code=200;self.headers={'content-type':'text/html','content-security-policy':"frame-ancestors 'none'; script-src 'unsafe-inline'",'content-length':str(len(self.body))}
    def stream(self,*args,**kw):self.calls.append((args,kw));return Response(self.body,self.code,self.headers)


def relay():
    record={'favicon_GET':0,'forwarded_GET':0,'blocked_requests':0};client=Client()
    http=m.BudgetHTTP('http://127.0.0.1:12345',client,m.Clock(0,now=lambda:1),'SYNTHETIC_RAM_ONLY_TOKEN',browser=True)
    http.instance='synthetic-instance';http.target='synthetic-release';http.target_hash='a'*64
    r=b.Relay(http,record,sha256(client.body).hexdigest());return r,http,client,record


def route(path='/template-upgrade',method='GET',headers=None):
    state={}
    return SimpleNamespace(request=SimpleNamespace(url='http://127.0.0.1:12345'+path,method=method,post_data=None,all_headers=lambda:headers or {}),fulfill=lambda **kw:state.update(fulfilled=kw),abort=lambda reason:state.update(aborted=reason)),state


def test_real_transport_bytes_csp_preserved_no_bearer_in_browser():
    r,http,client,record=relay();request,state=route('/api/template-consumer/catalog',headers={'authorization':b.PLACEHOLDER})
    r.route(request)
    assert state['fulfilled']['body']==client.body and state['fulfilled']['status']==200
    assert state['fulfilled']['headers']['content-security-policy']==client.headers['content-security-policy']
    assert 'content-length' not in state['fulfilled']['headers']
    assert client.calls[0][1]['headers']=={'Authorization':'Bearer SYNTHETIC_RAM_ONLY_TOKEN'}
    assert 'SYNTHETIC_RAM_ONLY_TOKEN' not in str(state) and http.gets==record['forwarded_GET']==1


@pytest.mark.parametrize('kind',['foreign','post','wrong-identity','unknown','redirect','cookie','encoding','secret-body'])
def test_relay_rejects_unknown_and_no_secret_or_synthetic_response(kind):
    r,http,client,record=relay();request,state=route()
    if kind=='foreign':request.request.url='https://outside.invalid/api/template-consumer/catalog'
    elif kind=='post':request.request.method='POST'
    elif kind=='wrong-identity':request,state=route('/api/template-consumer/catalog',headers={'authorization':'Bearer OTHER'})
    elif kind=='unknown':request,state=route('/api/not-allowed')
    elif kind=='redirect':client.code=302
    elif kind=='cookie':client.headers['set-cookie']='SYNTHETIC unexpected cookie'
    elif kind=='encoding':client.headers['content-encoding']='gzip'
    elif kind=='secret-body':client.body=b'SYNTHETIC_RAM_ONLY_TOKEN'
    r.route(request)
    assert r.failed and state.get('aborted')=='blockedbyclient' and 'fulfilled' not in state
    assert record['blocked_requests']==1
    if kind in ('foreign','post','wrong-identity','unknown'):assert not client.calls


def test_document_and_favicon_share_twenty_gets_no_extra_budget():
    r,http,client,record=relay();request,state=route();r.route(request)
    assert http.gets==1 and 'Authorization' not in client.calls[0][1]['headers']
    client.code=404;fav,state=route('/favicon.ico');r.route(fav);assert state['fulfilled']['status']==404 and record['favicon_GET']==1 and http.gets==2
    http.gets=20;another,state=route();r.route(another)
    assert 'aborted' in state and len(client.calls)==2 and http.gets==20


def test_browser_mode_does_not_use_node_activation_or_any_default_side_effect(monkeypatch):
    monkeypatch.setattr(a.TotalDeadline,'arm',lambda self:pytest.fail('closed activated watchdog'))
    monkeypatch.setattr(a.OnceClaim,'create',lambda *args:pytest.fail('closed consumed claim'))
    assert m.main(['--source','b'*40,'--invocation','PW_HTTP_SYNTHETIC_BROWSER'],mode='BROWSER')==2
    fake=SimpleNamespace(invocation='PW_HTTP_SYNTHETIC_BROWSER',relative=a.RELATIVE)
    with pytest.raises(m.Closed):m.Permit(m._SEAL,'b'*40,fake.invocation,fake,'BROWSER')


def test_private_environment_precedes_driver_and_restores_after_failure(tmp_path,monkeypatch):
    monkeypatch.setenv('HOME','SYNTHETIC_WORKER_HOME');monkeypatch.setenv('TMPDIR','SYNTHETIC_OLD_TMP');monkeypatch.delenv('XDG_CACHE_HOME',raising=False);(tmp_path/'tmp').mkdir()
    with pytest.raises(ValueError):
        with b.private_driver_environment(tmp_path):
            assert os.environ['TMPDIR']==str(tmp_path/'tmp') and os.environ['XDG_CACHE_HOME'].startswith(str(tmp_path))
            for name in ('HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_RUNTIME_DIR'):
                assert Path(os.environ[name]).is_relative_to(tmp_path) and Path(os.environ[name]).stat().st_mode&0o077==0
            raise ValueError('SYNTHETIC')
    assert os.environ['TMPDIR']=='SYNTHETIC_OLD_TMP' and 'XDG_CACHE_HOME' not in os.environ and os.environ['HOME']=='SYNTHETIC_WORKER_HOME'


def test_launch_failure_stops_driver_with_original_error_and_normal_sandbox(tmp_path,monkeypatch):
    import playwright.sync_api
    (tmp_path/'tmp').mkdir();calls={}
    def launch(**kw):calls['launch']=kw;raise ValueError('SYNTHETIC launch failed')
    def start():
        assert os.environ['TMPDIR']==str(tmp_path/'tmp')
        return SimpleNamespace(chromium=SimpleNamespace(launch=launch),stop=lambda:calls.update(stopped=True))
    monkeypatch.setattr(playwright.sync_api,'sync_playwright',lambda:SimpleNamespace(start=start))
    monkeypatch.setattr(b,'font_environment',lambda private,clock:dict(os.environ))
    http=SimpleNamespace();report={}
    with pytest.raises(ValueError) as error:b.run(http,object(),tmp_path,m.Clock(0,now=lambda:1),report,lambda owner:'SYNTHETIC_UNCHANGED','a'*64,lambda:None)
    assert calls['stopped'] and calls['launch']['chromium_sandbox'] is True and calls['launch']['channel']=='chrome'
    assert '--no-sandbox' not in calls['launch']['args'] and error.value.http_cleanup_errors==[]
    assert report['browser']['driver_stop']=='STOPPED' and report['browser']['status']=='FAIL'


def successful_record():
    images=[]
    raw=b'\x89PNG\r\n\x1a\nSYNTHETIC TEST BYTES'
    for name in b.IMAGES:images.append({'name':name,'bytes':len(raw),'sha256':sha256(raw).hexdigest()})
    return {'transport':'READ_ONLY_REAL_HTTP_RELAY_NOT_DIRECT_TCP','status':'PASS','browser_close':'CLOSED','driver_stop':'STOPPED','forwarded_GET':12,'favicon_GET':0,'blocked_requests':0,'pageerrors':0,'sandbox_observed':True,'chrome_internal_navigations':1,'checks':['WIDE_REFRESH_REAL_HTTP','NARROW_REFRESH_REAL_HTTP','WIDE_REAL_403_CLEAR','NARROW_REAL_403_CLEAR'],'images':images},raw


def test_export_only_four_whitelisted_files_after_cleanup_and_original_hash(tmp_path):
    record,raw=successful_record();data=tmp_path/'data';out=tmp_path/'out';data.mkdir();out.mkdir()
    root=SimpleNamespace(path=data,verify=lambda:None);evidence=SimpleNamespace(path=out,verify=lambda:None)
    for name in b.IMAGES:(data/name).write_bytes(raw)
    bad={**record,'browser_close':'UNKNOWN'}
    with pytest.raises(b.Closed):b.publish_images(root,evidence,bad,time.monotonic()+10)
    assert not list(out.iterdir())
    result=b.publish_images(root,evidence,record,time.monotonic()+10)
    assert len(result)==4 and sorted(x.name for x in out.iterdir())==sorted(b.IMAGES)
    record['images'][0]['name']='../unknown.png'
    with pytest.raises(b.Closed):b.validate_report(record)


@pytest.mark.parametrize('inside',[True,False])
def test_actual_profile_command_must_stay_in_private_tmp_without_launch(tmp_path,inside):
    private=tmp_path/'owned';(private/'tmp').mkdir(parents=True)
    profile=private/'tmp/profile' if inside else tmp_path/'outside-profile';profile.mkdir(mode=0o700)
    session=SimpleNamespace(send=lambda *args:{'arguments':['/opt/google/chrome/chrome','--user-data-dir='+str(profile)]},detach=lambda:None)
    browser=SimpleNamespace(new_browser_cdp_session=lambda:session)
    page=SimpleNamespace(goto=lambda *a,**kw:None,locator=lambda *a:SimpleNamespace(inner_text=lambda **kw:'You are adequately sandboxed. Seccomp-BPF sandbox Yes PID namespaces Yes'))
    record={}
    if inside:
        b.sandbox(browser,page,private,m.Clock(0,now=lambda:1),record);assert record['sandbox_observed'] is True
    else:
        with pytest.raises(b.Closed):b.sandbox(browser,page,private,m.Clock(0,now=lambda:1),record)
        assert not record
