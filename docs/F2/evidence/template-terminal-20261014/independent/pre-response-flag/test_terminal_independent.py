"""Independent real owned-PG tests. No source/Git changes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import json
import pytest
from parkweave import service_case_steps
from parkweave.store import Conflict
from test_template_consumer import template_consumption,headers,products
from test_template_consumer_planning import ready,preview,adoption,post
from test_template_partial import recover,journal
from template_candidate_support import ENTERPRISES


def request(f,key='independent-original'):
    row=ready(f); data=adoption(preview(f,row).json())
    return row,data,key


def finish_body(x):
    return dict(expected_body_sha256=x['body_sha256'],expected_original_request_key=x['original_request_key'],
        expected_journal_state=x['journal_state'],reason='SYNTHETIC explicit independent original-key close')


def finish(f,row,key,body):
    return post(f,row,'planning-finalization',body,key)


def test_committed_unknown_cold_finalize_idempotent_and_no_original_send(template_consumption,monkeypatch):
    from parkweave.template_consumer import ConsumerRepository,TemplateConsumer
    from parkweave.template_isolated_app import create_isolated_template_app
    from fastapi.testclient import TestClient
    f=template_consumption;row,data,key=request(f);original=service_case_steps.adopt;calls=[]
    def lost(*a,**kw):
        calls.append(a[3]);original(*a,**kw);raise RuntimeError('SYNTHETIC independent response loss')
    monkeypatch.setattr(service_case_steps,'adopt',lost)
    assert post(f,row,'adopt',data,key).status_code==503
    x=recover(f,row,key).json();assert x['status']=='COMMITTED' and not x['journal_terminal']
    saved=journal(f); before=products(f['owner'],include_audit=True)
    assert recover(f,row,key).status_code==200 and journal(f)==saved
    close=finish_body(x);r=finish(f,row,key,close);assert r.status_code==200,r.text
    assert products(f['owner'],include_audit=True)==before
    terminal=recover(f,row,key).json();assert terminal['journal_terminal'] and terminal['journal_state']=='CONFIRMED'
    stored=journal(f);assert finish(f,row,key,close).status_code==200 and journal(f)==stored
    assert finish(f,row,key,{**close,'reason':'SYNTHETIC altered close'}).status_code==409
    consumer=TemplateConsumer(f['store'],f['engine'],f['config'],ConsumerRepository(f['repository'].path))
    with TestClient(create_isolated_template_app(f['store'],f['engine'],consumer)) as client:
        r=client.get('/api/template-consumer/instances/'+row['instance_id']+'/planning-recovery',headers=headers(f,key=key))
        assert r.status_code==200 and r.json()['journal_terminal']
    assert len(calls)==1


def test_first_definite_refusal_is_durable_nonreplayable_and_can_close(template_consumption,monkeypatch):
    f=template_consumption;row,data,key=request(f);calls=[]
    def refused(*a,**kw):calls.append(a[3]);raise Conflict('SYNTHETIC explicit first-send refusal')
    monkeypatch.setattr(service_case_steps,'adopt',refused)
    assert post(f,row,'adopt',data,key).status_code==409
    x=recover(f,row,key).json();assert x['journal_state']=='REJECTED_FIRST_SEND' and not x['journal_terminal']
    assert post(f,row,'adopt',data,key).status_code==409 and calls==[x['original_request_key']]
    before=products(f['owner'],include_audit=True);r=finish(f,row,key,finish_body(x));assert r.status_code==200,r.text
    y=recover(f,row,key).json();assert y['journal_terminal'] and y['journal_state']=='CLOSED_NOT_COMMITTED'
    assert post(f,row,'adopt',data,key).status_code==409 and len(calls)==1
    assert products(f['owner'],include_audit=True)==before


@pytest.mark.parametrize('state',['UNKNOWN','REFUSED','ADMITTED','STARTED'])
def test_absent_or_legacy_refused_is_not_terminal_even_after_finalize(template_consumption,monkeypatch,state):
    f=template_consumption;row,data,key=request(f)
    monkeypatch.setattr(service_case_steps,'adopt',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('SYNTHETIC not sent')))
    assert post(f,row,'adopt',data,key).status_code==503
    with f['repository'].connect(write=True) as c:
        c.execute("UPDATE consumer_stages SET state=?,error='PRODUCT_CONFLICT' WHERE name LIKE 'CONFIRM_PLAN_%' AND instance_id=?",(state,row['instance_id']))
    x=recover(f,row,key).json();assert not x['receipt']['not_committed_final'] and not x['journal_terminal']
    saved=journal(f);before=products(f['owner'],include_audit=True)
    r=finish(f,row,key,finish_body(x));assert r.status_code==409,r.text
    assert journal(f)==saved and products(f['owner'],include_audit=True)==before


@pytest.mark.parametrize('capability',['READ','PREPARE','EXECUTE'])
def test_revocation_before_finalization_never_closes_journal(template_consumption,monkeypatch,capability):
    f=template_consumption;row,data,key=request(f);original=service_case_steps.adopt
    def lost(*a,**kw):original(*a,**kw);raise RuntimeError('SYNTHETIC independent lost reply')
    monkeypatch.setattr(service_case_steps,'adopt',lost);assert post(f,row,'adopt',data,key).status_code==503
    x=recover(f,row,key).json();body=finish_body(x)
    with f['owner'].connect() as c:
        table='preparation_grants' if capability=='PREPARE' else 'capability_grants'
        c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',(ENTERPRISES[0],capability))
    saved=journal(f);before=products(f['owner'])
    assert finish(f,row,key,body).status_code==403
    assert journal(f)==saved and products(f['owner'])==before


def test_delayed_original_send_and_finalization_share_key_lock(template_consumption,monkeypatch):
    f=template_consumption;row,data,key=request(f);original=service_case_steps.adopt
    entered=Event();release=Event();close_started=Event();close_done=Event();calls=[]
    def delayed(*a,**kw):
        entered.set();assert release.wait(15);calls.append(a[3]);return original(*a,**kw)
    monkeypatch.setattr(service_case_steps,'adopt',delayed)
    def close():
        close_started.set()
        try:return finish(f,row,key,close_body)
        finally:close_done.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        sending=pool.submit(post,f,row,'adopt',data,key)
        assert entered.wait(15)
        x=recover(f,row,key).json();assert x['journal_state']=='STARTED' and x['status']=='NOT_OBSERVED'
        close_body=finish_body(x);closing=pool.submit(close);assert close_started.wait(5)
        assert not close_done.wait(.2), 'finalization must wait for original external-key lock'
        release.set();assert sending.result(15).status_code==200
        r=closing.result(15)
        assert r.status_code in (200,409),r.text
    x=recover(f,row,key).json();assert x['status']=='COMMITTED'
    if not x['journal_terminal']:
        r=finish(f,row,key,finish_body(x));assert r.status_code==200,r.text
    assert recover(f,row,key).json()['journal_terminal'] and len(calls)==1


def test_monotonically_advanced_source_proves_never_committed_and_closes_old_key(template_consumption,monkeypatch):
    f=template_consumption;row,data,key=request(f);calls=[]
    def interrupted(*a,**kw):calls.append(a[3]);raise RuntimeError('SYNTHETIC before original submission')
    monkeypatch.setattr(service_case_steps,'adopt',interrupted)
    assert post(f,row,'adopt',data,key).status_code==503
    r=f['client'].post('/api/preparations/'+row['preparation_id']+'/commands',headers=headers(f,key='independent-advance'),json=dict(action='ADD_EVIDENCE',expected_revision=data['expected_preparation_revision'],slot='need_summary',text='SYNTHETIC source advanced independently',source_kind='USER_STATEMENT',source_label='SYNTHETIC exact current source'))
    assert r.status_code==200,r.text
    x=recover(f,row,key).json();assert x['status']=='NOT_COMMITTED_STALE' and x['receipt']['not_committed_final']
    before=products(f['owner'],include_audit=True);r=finish(f,row,key,finish_body(x));assert r.status_code==200,r.text
    assert recover(f,row,key).json()['journal_terminal']
    assert post(f,row,'adopt',data,key).status_code==409 and len(calls)==1
    assert products(f['owner'],include_audit=True)==before


def test_later_actual_original_receipt_must_not_be_reported_as_never_committed(template_consumption,monkeypatch):
    f=template_consumption;row,data,key=request(f);original=service_case_steps.adopt
    monkeypatch.setattr(service_case_steps,'adopt',lambda *a,**kw: (_ for _ in ()).throw(Conflict('SYNTHETIC first definite product refusal')))
    assert post(f,row,'adopt',data,key).status_code==409
    x=recover(f,row,key).json();assert finish(f,row,key,finish_body(x)).status_code==200
    # The existing authorized original API remains a separate access path. A
    # later actual immutable receipt contradicts the journal-only rejection.
    monkeypatch.setattr(service_case_steps,'adopt',original)
    r=f['client'].post('/api/preparations/'+row['preparation_id']+'/service-case-plan',headers=headers(f,key=x['original_request_key']),json=data)
    assert r.status_code==201,r.text
    r=recover(f,row,key)
    assert r.status_code==409, 'contradictory actual COMMITTED must never become NOT_COMMITTED_FINAL: '+r.text
