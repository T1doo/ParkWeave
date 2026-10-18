"""New input UI; all positive template authorities remain the existing isolated fixture."""
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json, socket, subprocess, threading
import pytest
import uvicorn
from psycopg.types.json import Jsonb
from parkweave.template_candidate import canonical
from parkweave.template_consumer import TemplateConsumer
from test_template_consumer import template_consumption, headers, body, products, consume, resume
from template_candidate_support import ENTERPRISES, PARK, grant_snapshot
from ordinary_case_step_support import worker_once, ordinary_api


def pinned(f):
    r=f['client'].get('/api/template-consumer/catalog',headers=headers(f));assert r.status_code==200
    catalog=r.json();assert len(catalog['templates'])==1
    t=catalog['templates'][0];data=body(f);data['expected_catalog_sha256']=t['catalog_binding']['sha256']
    return catalog,t,data


def fingerprint(data):return sha256(canonical(dict(action='CONSUME',**data)).encode()).hexdigest()


def journal(f):
    with f['repository'].connect() as c:
        return {t:[dict(r) for r in c.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in ('consumer_instances','consumer_requests','consumer_stages')}


def drift(f):
    with f['owner'].connect() as c:
        row=c.execute('SELECT source FROM preparation_catalog WHERE park_id=%s',(PARK,)).fetchone()
        source={**row['source'],'revision':2,'statement':'SYNTHETIC directory source advanced after input selection'}
        c.execute('UPDATE preparation_catalog SET source=%s WHERE park_id=%s',(Jsonb(source),PARK))


def test_pinned_new_input_actual_worker_prepares_only_new_materials(template_consumption,tmp_path):
    f=template_consumption;before=grant_snapshot(f['owner']);catalog,t,data=pinned(f)
    row=consume(f,key='pinned-fresh-input',data=data).json()
    assert row['binding']['catalog_binding']==t['catalog_binding'] and row['state']=='PENDING_RUN'
    worker_once((f['store'],),tmp_path/'worker')
    reply=resume(f,row,key='explicit-new-materials');assert reply.status_code==200,reply.text
    current=reply.json();assert current['state']=='PLAN_CONFIRMATION_REQUIRED' and current['plan_id'] is None
    saved=products(f['owner']);assert len(saved['runs'])==len(saved['cases'])==len(saved['preparations'])==1
    assert {e['text'] for e in saved['preparation_evidence']}=={e['text'] for e in data['materials']}
    assert len(saved['preparation_evidence'])==2 and not saved['controlled_plans']
    assert not current['automatic_execution'] and not current['new_grants']
    assert grant_snapshot(f['owner'])==before
    # New consumer object, same original immutable journal; no fixture reinstall.
    other=TemplateConsumer(f['store'],f['engine'],f['config'],f['repository'])
    assert other.read(f['tokens'][ENTERPRISES[0]],row['instance_id'])['binding']==row['binding']
    (tmp_path/'chain.json').write_text(json.dumps(dict(instance_id=current['instance_id'],run_id=current['run_id'],case_id=current['case_id'],preparation_id=current['preparation_id'],state=current['state'],real_worker=True,isolated_template_authority=True,ordinary_formal_success=False,material_count=2,grants_unchanged=True),indent=2)+'\n')


def test_catalog_pin_rejects_stale_and_null_without_business_write(template_consumption):
    f=template_consumption;_,_,data=pinned(f);before=products(f['owner']);j=journal(f)
    bad=deepcopy(data);bad['expected_catalog_sha256']='0'*64
    assert consume(f,key='wrong-directory-pin',data=bad).status_code==409
    bad['expected_catalog_sha256']=None
    assert consume(f,key='null-directory-pin',data=bad).status_code==422
    drift(f)
    assert consume(f,key='advanced-directory-pin',data=data).status_code==409
    assert products(f['owner'])==before and journal(f)==j
    # A changed exact service/version disappears, never silently substituted.
    with f['owner'].connect() as c:c.execute('UPDATE preparation_catalog SET version=2 WHERE park_id=%s',(PARK,))
    assert f['client'].get('/api/template-consumer/catalog',headers=headers(f)).json()['templates']==[]


def test_directory_drift_after_admission_preserves_history_and_blocks_materials(template_consumption,tmp_path):
    f=template_consumption;_,_,data=pinned(f);row=consume(f,key='before-source-drift',data=data).json()
    worker_once((f['store'],),tmp_path/'worker');drift(f);before=products(f['owner']);j=journal(f)
    assert resume(f,row,key='after-source-drift').status_code in (403,409)
    read=f['client'].get('/api/template-consumer/instances/'+row['instance_id'],headers=headers(f)).json()
    assert not read['release_available'] and read['binding']==row['binding'] and read['run_state']=='SUCCEEDED'
    assert products(f['owner'])==before and journal(f)==j and not read['preparation_id']


def test_exact_creation_recovery_only_observes_original_consume(template_consumption,monkeypatch):
    f=template_consumption;_,_,data=pinned(f);key='original-consume-read-only'
    row=consume(f,key=key,data=data).json();fp=fingerprint(data)
    # Record a different original action's key with the same instance.
    assert resume(f,row,key='resume-is-not-create').status_code==200
    before=products(f['owner']);j=journal(f);authority=grant_snapshot(f['owner'])
    def no_send(*a,**kw):raise AssertionError('read-only recovery must never submit/resume')
    monkeypatch.setattr(f['store'],'submit',no_send);monkeypatch.setattr(f['consumer'],'resume',no_send)
    path='/api/template-consumer/creation-recovery'
    def get(k=key,hash=fp,index=0):return f['client'].get(path,params=dict(request_key=k,expected_fingerprint_sha256=hash),headers=headers(f,index))
    x=get();assert x.status_code==200;x=x.json()
    assert x['status']=='RECORDED_INSTANCE' and x['instance']['instance_id']==row['instance_id']
    assert x['read_only'] and not x['automatically_replayed'] and not x['not_committed_final']
    assert get(hash='0'*64).status_code==409
    assert get(k='resume-is-not-create').status_code==409
    assert get(index=1).json()['status']=='NOT_OBSERVED'
    assert get(k='never-observed').json()['status']=='NOT_OBSERVED'
    assert f['client'].get(path+'?request_key='+key+'&request_key=other&expected_fingerprint_sha256='+fp,headers=headers(f)).status_code==409
    assert products(f['owner'])==before and journal(f)==j and grant_snapshot(f['owner'])==authority


def test_unknown_original_create_stage_is_not_replayed_by_recovery(template_consumption,monkeypatch):
    f=template_consumption;_,_,data=pinned(f);original=f['store'].submit
    def lost(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('SYNTHETIC committed original Run reply unavailable')
    monkeypatch.setattr(f['store'],'submit',lost)
    assert consume(f,key='unknown-original-stage',data=data).status_code==503
    before=products(f['owner']);j=journal(f)
    result=f['client'].get('/api/template-consumer/creation-recovery',params=dict(request_key='unknown-original-stage',expected_fingerprint_sha256=fingerprint(data)),headers=headers(f))
    assert result.status_code==200
    x=result.json();assert x['status']=='RECORDED_INSTANCE' and x['instance']['state']=='UNKNOWN'
    assert x['instance']['run_id'] is None and len(before['runs'])==1
    assert products(f['owner'])==before and journal(f)==j


def test_creation_recovery_rechecks_current_permission(template_consumption):
    f=template_consumption;_,_,data=pinned(f);consume(f,key='before-revoke',data=data)
    with f['owner'].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability='PREPARE'",(ENTERPRISES[0],))
    before=products(f['owner']);j=journal(f)
    result=f['client'].get('/api/template-consumer/creation-recovery',params=dict(request_key='before-revoke',expected_fingerprint_sha256=fingerprint(data)),headers=headers(f))
    assert result.status_code==403 and products(f['owner'])==before and journal(f)==j


@contextmanager
def serving(app):
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(16)
    server=uvicorn.Server(uvicorn.Config(app,log_level='warning',access_log=False));thread=threading.Thread(target=server.run,kwargs=dict(sockets=[sock]),daemon=True);thread.start()
    try:yield 'http://127.0.0.1:'+str(sock.getsockname()[1])
    finally:
        server.should_exit=True;thread.join(10);assert not thread.is_alive();sock.close()


def html(f,tmp_path,base,mode):
    out=tmp_path/'html.stdout';err=tmp_path/'html.stderr'
    config=dict(base=base,token=f['tokens'][ENTERPRISES[0]],other_token=f['tokens'][ENTERPRISES[1]],mode=mode)
    with out.open('w') as stdout,err.open('w') as stderr:
        child=subprocess.Popen(['node','tests/ordinary_template_inputs_html.js'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True)
        timer=threading.Timer(60,child.terminate);timer.start()
        try:
            child.stdin.write(json.dumps(config)+'\n');child.stdin.flush()
            for line in child.stdout:
                stdout.write(line);stdout.flush();row=json.loads(line)
                if row.get('control')=='worker':worker_once((f['store'],),tmp_path/'worker');child.stdin.write('{}\n');child.stdin.flush()
                elif row.get('control')=='drift':drift(f);child.stdin.write('{}\n');child.stdin.flush()
                elif row.get('control')=='revoke':
                    with f['owner'].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability='PREPARE'",(ENTERPRISES[0],))
                    child.stdin.write('{}\n');child.stdin.flush()
            code=child.wait(timeout=10)
        finally:
            timer.cancel()
            if child.poll() is None:child.terminate();child.wait(timeout=10)
    assert code==0,err.read_text()
    return json.loads(out.read_text().splitlines()[-1])


@pytest.mark.parametrize('mode',['success','lost','edit','token','aba','pin','denied'])
def test_original_page_template_input_http_guards(template_consumption,tmp_path,mode):
    f=template_consumption;authority=grant_snapshot(f['owner'])
    with serving(f['client'].app) as base:result=html(f,tmp_path,base,mode)
    saved=products(f['owner']);assert (grant_snapshot(f['owner'])==authority)==(mode!='denied')
    if mode=='success':assert len(saved['preparation_evidence'])==2 and len(saved['runs'])==1 and not saved['controlled_plans']
    elif mode in ('lost','denied'):assert len(saved['runs'])==1 and not saved['preparation_evidence']
    else:assert not saved['runs'] and not saved['preparation_evidence']
    assert result['real_browser'] is False


def test_default_current_process_has_no_template_source_or_fixture_fallback(template_consumption,tmp_path,monkeypatch):
    f=template_consumption;initial=products(f['owner']);authority=grant_snapshot(f['owner'])
    with ordinary_api((f['store'],),tmp_path/'ordinary-api') as api:
        assert api.get('/api/template-consumer/catalog',headers=headers(f)).status_code==404
        assert api.post('/api/template-consumer/instances',headers=headers(f,key='no-ordinary-template'),json=body(f)).status_code==404
        assert api.get('/api/template-consumer/creation-recovery',params=dict(request_key='absent',expected_fingerprint_sha256='0'*64),headers=headers(f)).status_code==404
        result=html(f,tmp_path,str(api.base_url).rstrip('/'),'default')
    assert result['checks']>0 and products(f['owner'])==initial and grant_snapshot(f['owner'])==authority
