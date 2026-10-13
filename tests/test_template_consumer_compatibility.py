"""Legacy original entry and adoption outcome compatibility on owned PG."""
from uuid import UUID
from copy import deepcopy
import pytest
from parkweave import service_case_steps,request_intents
from parkweave.template_consumer import ConsumerUnknown
from test_template_consumer import template_consumption,headers,resume,products
from test_template_consumer_planning import ready,preview,adoption,post,edit
from template_candidate_support import ENTERPRISES


def outside(f,row,data,key='outside-original'):
    return f['client'].post('/api/preparations/'+row['preparation_id']+'/service-case-plan',headers=headers(f,key=key),json=data)


def test_original_entry_adoption_is_visible_to_consumer_read(template_consumption):
    f=template_consumption;row=ready(f);v=preview(f,row).json();r=outside(f,row,adoption(v));assert r.status_code==201,r.text
    before=products(f['owner']);x=f['client'].get('/api/template-consumer/instances/'+row['instance_id'],headers=headers(f)).json();assert x['state']=='PLAN_ADOPTED' and x['plan_id']==r.json()['plan_id'];assert products(f['owner'])==before


def test_consumer_cannot_replace_plan_adopted_at_original_entry(template_consumption):
    f=template_consumption;row=ready(f);v=preview(f,row).json();assert outside(f,row,adoption(v)).status_code==201
    data=edit(v);data['request_text']='SYNTHETIC explicit current request changed by original entry';r=f['client'].post('/api/preparations/'+row['preparation_id']+'/request-intent',headers=headers(f,key='outside-source-edit'),json=data);assert r.status_code==200,r.text
    v=preview(f,row).json();data=adoption(v);data['expected_plan_revision']=v['service_case_plan']['revision'];before=products(f['owner']);r=post(f,row,'adopt',data,'attempt-consumer-replacement');assert r.status_code==409,r.text;assert products(f['owner'])==before
    from parkweave.store import Conflict
    with pytest.raises(Conflict):service_case_steps.adopt(f['store'],f['tokens'][ENTERPRISES[0]],UUID(row['preparation_id']),'internal-consumer-guard',service_case_steps.Adopt.model_validate(data),unadopted_only=True)
    assert products(f['owner'])==before
    allowed=outside(f,row,data,key='explicit-original-replacement');assert allowed.status_code==201,allowed.text
    assert f['client'].get('/api/template-consumer/instances/'+row['instance_id'],headers=headers(f)).json()['plan_id']==allowed.json()['plan_id']


def legacy_unknown(f,row,monkeypatch):
    v=preview(f,row).json();token=f['tokens'][ENTERPRISES[0]];p,db=f['consumer']._auth(token);inst=f['consumer']._instance(p,db,row['instance_id']);original=service_case_steps.adopt
    def lost(*a,**kw):original(*a,**kw);raise RuntimeError('Injected old ADOPT_PLAN committed reply loss')
    with monkeypatch.context() as m:
        m.setattr(service_case_steps,'adopt',lost)
        with pytest.raises(ConsumerUnknown):f['consumer']._perform(token,inst,'ADOPT_PLAN',lambda:adoption(v),lambda key,data:service_case_steps.adopt(f['store'],token,UUID(row['preparation_id']),key,service_case_steps.Adopt.model_validate(data)))
    return v


def test_old_committed_unknown_adoption_can_be_reconciled_without_re_adoption(template_consumption,monkeypatch):
    f=template_consumption;row=ready(f);legacy_unknown(f,row,monkeypatch);before=products(f['owner']);r=resume(f,row,key='legacy-reconcile-only');assert r.status_code==200,r.text
    stage=next(x for x in r.json()['stages'] if x['name']=='ADOPT_PLAN');assert stage['state']=='CONFIRMED';assert products(f['owner'])==before


def legacy_fault(f,row,monkeypatch,state,outcome='before_send',mismatch=False):
    from parkweave.store import Conflict
    class ProcessStopped(BaseException):pass
    v=preview(f,row).json();data=adoption(v);token=f['tokens'][ENTERPRISES[0]];p,db=f['consumer']._auth(token);inst=f['consumer']._instance(p,db,row['instance_id'])
    if outcome=='failed_stale':
        changed=edit(v);changed['request_text']='SYNTHETIC explicit corrected source';r=f['client'].post('/api/preparations/'+row['preparation_id']+'/request-intent',headers=headers(f,key='corrected-source'),json=changed);assert r.status_code==200,r.text
    def send(key,saved):
        if outcome in ('committed','failed_stale'):
            actual=deepcopy(saved)
            if mismatch:actual['reason']='SYNTHETIC different actual original request'
            try:service_case_steps.adopt(f['store'],token,UUID(row['preparation_id']),key,service_case_steps.Adopt.model_validate(actual))
            except Conflict:
                assert outcome=='failed_stale'
        if state=='STARTED':raise ProcessStopped('Injected old process stopped before confirmation')
        raise RuntimeError('Injected old operation reply unknown')
    with pytest.raises(ProcessStopped if state=='STARTED' else ConsumerUnknown):f['consumer']._perform(token,inst,'ADOPT_PLAN',lambda:data,send)
    with f['repository'].connect() as c:before=dict(c.execute("SELECT * FROM consumer_stages WHERE instance_id=? AND name='ADOPT_PLAN'",(row['instance_id'],)).fetchone());assert before['state']==state
    return before


def reconcile(f,row,persist=True,index=0):
    path='/api/template-consumer/instances/'+row['instance_id']+'/adoption-reconciliation'
    return f['client'].post(path,headers=headers(f,index),json={}) if persist else f['client'].get(path,headers=headers(f,index))


@pytest.mark.parametrize('state',['STARTED','UNKNOWN'])
@pytest.mark.parametrize('outcome',['committed','failed_stale','before_send'])
def test_old_exact_key_reconciliation_committed_stale_failure_and_unprovable_no_auto_send(template_consumption,monkeypatch,state,outcome):
    f=template_consumption;row=ready(f);saved=legacy_fault(f,row,monkeypatch,state,outcome);before=products(f['owner']);original_adopt=service_case_steps.adopt;attempts=[]
    def forbidden(*a,**kw):attempts.append(True);raise AssertionError('reconciliation must never send ADOPT')
    monkeypatch.setattr(service_case_steps,'adopt',forbidden);proof=reconcile(f,row,False);assert proof.status_code==200,proof.text
    expected={'committed':'COMMITTED','failed_stale':'NOT_COMMITTED_STALE','before_send':'NOT_OBSERVED'}[outcome];assert proof.json()['status']==expected and not proof.json()['automatically_replayed']
    with f['repository'].connect() as c:assert dict(c.execute("SELECT * FROM consumer_stages WHERE name='ADOPT_PLAN'").fetchone())==saved
    r=reconcile(f,row);assert r.status_code==200,r.text;assert r.json()['adoption_reconciliation']['status']==expected;assert products(f['owner'])==before;assert attempts==[];monkeypatch.setattr(service_case_steps,'adopt',original_adopt)
    with f['repository'].connect() as c:
        actual=dict(c.execute("SELECT * FROM consumer_stages WHERE name='ADOPT_PLAN'").fetchone());assert actual['state']==('CONFIRMED' if outcome=='committed' else 'REFUSED' if outcome=='failed_stale' else state);assert (actual['request_key'],actual['body'],actual['body_sha256'])==(saved['request_key'],saved['body'],saved['body_sha256'])
    from parkweave.template_consumer import TemplateConsumer,ConsumerRepository
    f['consumer']=TemplateConsumer(f['store'],f['engine'],f['config'],ConsumerRepository(f['repository'].path))
    from fastapi.testclient import TestClient
    from parkweave.template_isolated_app import create_isolated_template_app
    with TestClient(create_isolated_template_app(f['store'],f['engine'],f['consumer'])) as cold_client:
        response=cold_client.get('/api/template-consumer/instances/'+row['instance_id'],headers=headers(f));assert response.status_code==200; cold=response.json()
        cold_proof=cold_client.get('/api/template-consumer/instances/'+row['instance_id']+'/adoption-reconciliation',headers=headers(f));assert cold_proof.status_code==200 and cold_proof.json()['status']==expected
    assert cold['state']==('PLAN_ADOPTED' if outcome=='committed' else 'BLOCKED' if outcome=='failed_stale' else 'UNKNOWN')
    if outcome=='before_send':assert post(f,row,'adopt',adoption(preview(f,row).json()),'new-after-unproven').status_code==409
    if outcome=='failed_stale':assert post(f,row,'adopt',adoption(preview(f,row).json()),'new-explicit-after-proven-stale').status_code==200


@pytest.mark.parametrize('state',['STARTED','UNKNOWN'])
def test_legacy_key_receipt_with_different_request_body_never_confirms_stage(template_consumption,monkeypatch,state):
    f=template_consumption;row=ready(f);saved=legacy_fault(f,row,monkeypatch,state,'committed',mismatch=True);before=products(f['owner']);r=reconcile(f,row);assert r.status_code==409,r.text
    with f['repository'].connect() as c:assert dict(c.execute("SELECT * FROM consumer_stages WHERE name='ADOPT_PLAN'").fetchone())==saved
    assert products(f['owner'])==before


@pytest.mark.parametrize('capability',['READ','PREPARE','EXECUTE'])
def test_legacy_reconciliation_current_revocation_preserves_unknown_and_product(template_consumption,monkeypatch,capability):
    f=template_consumption;row=ready(f);saved=legacy_fault(f,row,monkeypatch,'UNKNOWN','committed')
    with f['owner'].connect() as c:
        table='preparation_grants' if capability=='PREPARE' else 'capability_grants';c.execute(f'UPDATE {table} SET active=false WHERE principal_id=%s AND capability=%s',(ENTERPRISES[0],capability))
    before=products(f['owner']);assert reconcile(f,row).status_code==403
    with f['repository'].connect() as c:assert dict(c.execute("SELECT * FROM consumer_stages WHERE name='ADOPT_PLAN'").fetchone())==saved
    assert products(f['owner'])==before


def test_legacy_reconciliation_cross_owner_and_unavailable_source_preserve_unknown(template_consumption,monkeypatch):
    from test_template_candidate import advance_source_head
    f=template_consumption;row=ready(f);saved=legacy_fault(f,row,monkeypatch,'UNKNOWN','committed');before=products(f['owner']);assert reconcile(f,row,index=1).status_code==403;advance_source_head(f['engine']);assert reconcile(f,row).status_code==403
    with f['repository'].connect() as c:assert dict(c.execute("SELECT * FROM consumer_stages WHERE name='ADOPT_PLAN'").fetchone())==saved
    assert products(f['owner'])==before


def test_original_adopt_between_consumer_old_read_and_send_cannot_replace_with_valid_current_body(template_consumption,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    f=template_consumption;row=ready(f);old=preview(f,row).json();changed=edit(old);changed['request_text']='SYNTHETIC new owner request';# Same source is planned first; original entry may adopt while consumer waits.
    entered=Event();release=Event();original=f['consumer']._perform
    def pause(*args,**kwargs):
        if args[2].startswith('CONFIRM_PLAN_'):entered.set();assert release.wait(5)
        return original(*args,**kwargs)
    monkeypatch.setattr(f['consumer'],'_perform',pause);data=adoption(old)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending=pool.submit(post,f,row,'adopt',data,'pending-original-race')
        try:
            assert entered.wait(5);r=outside(f,row,adoption(old));assert r.status_code==201,r.text;before=products(f['owner'])
        finally:release.set()
        assert pending.result().status_code==409;assert products(f['owner'])==before



def test_original_cold_template_ui_reconciles_exact_legacy_receipt_without_adopt(template_consumption,monkeypatch):
    import json,selectors,subprocess
    from pathlib import Path
    f=template_consumption;row=ready(f);legacy_fault(f,row,monkeypatch,'UNKNOWN','committed');before=products(f['owner']);attempts=[]
    def forbidden(*a,**kw):attempts.append(True);raise AssertionError('cold reconciliation must not adopt')
    monkeypatch.setattr(service_case_steps,'adopt',forbidden)
    proc=subprocess.Popen(['node','tests/template_consumer_legacy_reconciliation.js','legacy_cold_reconcile',ENTERPRISES[0],row['instance_id']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ);requests=[];summary=None
    try:
        while True:
            assert sel.select(timeout=15);msg=json.loads(proc.stdout.readline())
            if 'request' not in msg:summary=msg;break
            q=msg['request'];o=q['options'];method=o.get('method','GET');data=json.loads(o['body']) if o.get('body') else None;r=f['client'].request(method,q['path'],headers=headers(f,key=o.get('headers',{}).get('Idempotency-Key')),json=data);requests.append({'method':method,'path':q['path'],'status':r.status_code});assert r.status_code==200,r.text;proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json()})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary['checks']==10 and attempts==[] and products(f['owner'])==before
        out=Path('.runtime/template-consumer-compatibility-20261013');out.mkdir(parents=True,exist_ok=True);(out/'actual-cold-chain.json').write_text(json.dumps({'summary':summary,'requests':requests,'ADOPT_calls':len(attempts),'product_rows_unchanged':True,'lost_responses':0},indent=2)+'\n')
    finally:
        sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
