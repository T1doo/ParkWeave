from conftest import fixture,pg
import json
import pytest
from parkweave.store import digest
from parkweave.template_consumer import canonical
from test_template_consumer import template_consumption,headers,resume,products
from test_template_consumer_planning import adoption,preview,post,edit
from test_template_partial import recover,journal
from test_template_terminal import unknown,finish,finish_body,advance

def legacy(f,monkeypatch):
    row,v,data=unknown(f,monkeypatch,commit=False)
    p=recover(f,row,'terminal-original').json()
    request=finish_body(p);request['expected_journal_state']='REJECTED_FIRST_SEND'
    meta=dict(original_request_key=p['original_request_key'],body_sha256=p['body_sha256'],state='CLOSED_NOT_COMMITTED',proof_kind='FIRST_DEFINITE_REFUSAL',refusal_code='FIRST_PRODUCT_CONFLICT',request=request,fingerprint=digest(canonical(request)))
    with f['repository'].connect(write=True) as c:
        c.execute("UPDATE consumer_stages SET state='CLOSED_NOT_COMMITTED',result=? WHERE name LIKE 'CONFIRM_PLAN_%'",(canonical({'consumer_finalization':meta}),))
    return row,v,data,p

def cold(f,row):
    return f['client'].get('/api/template-consumer/instances/'+row['instance_id'],headers=headers(f))

@pytest.mark.parametrize('kind',['adopt','edit','resume'])
def test_cold_without_local_handle_blocks_all_new_template_mutations(template_consumption,monkeypatch,kind):
    f=template_consumption;row,v,data,p=legacy(f,monkeypatch);saved=journal(f);before=products(f['owner'],include_audit=True)
    response=cold(f,row);assert response.status_code==200,response.text
    assert response.json()['state']=='UNKNOWN',response.json()
    # Normal cold session has no browser localStorage; admission must be server enforced.
    r=post(f,row,'adopt',data,'independent-fresh-adopt') if kind=='adopt' else post(f,row,'planning',edit(v),'independent-fresh-edit') if kind=='edit' else resume(f,row,key='independent-fresh-resume')
    assert r.status_code==409,r.text
    assert journal(f)==saved and products(f['owner'],include_audit=True)==before
    assert recover(f,row,'terminal-original').status_code==409


def test_late_original_commit_retained_but_no_new_template_key_escape(template_consumption,monkeypatch):
    f=template_consumption;row,v,data,p=legacy(f,monkeypatch)
    r=f['client'].post('/api/preparations/'+row['preparation_id']+'/service-case-plan',headers=headers(f,key=p['original_request_key']),json=data)
    assert r.status_code==201,r.text
    saved=journal(f);before=products(f['owner'],include_audit=True)
    r=cold(f,row);assert r.status_code==200 and r.json()['plan_id'] is not None
    assert r.json()['state']=='UNKNOWN'
    assert post(f,row,'adopt',data,'independent-after-late').status_code==409
    assert journal(f)==saved and products(f['owner'],include_audit=True)==before


def test_legitimate_strict_source_terminal_allows_fresh_review_and_adoption(template_consumption,monkeypatch):
    f=template_consumption;row,v,data=unknown(f,monkeypatch,commit=False)
    assert advance(f,row,v).status_code==200
    p=recover(f,row,'terminal-original').json();assert p['status']=='NOT_COMMITTED_STALE'
    assert finish(f,row,'terminal-original',finish_body(p)).status_code==200
    saved=journal(f);before=products(f['owner'],include_audit=True)
    read=cold(f,row);assert read.status_code==200 and read.json()['state']=='PLAN_CONFIRMATION_REQUIRED'
    current=preview(f,row);assert current.status_code==200
    assert journal(f)==saved and products(f['owner'],include_audit=True)==before
    assert post(f,row,'adopt',{**adoption(current.json()),'partial_adoption':True},'independent-strict-new').status_code==200

@pytest.mark.parametrize('capability',['READ','PREPARE','EXECUTE'])
def test_current_permission_denial_precedes_legacy_projection_and_admission(template_consumption,monkeypatch,capability):
    from template_candidate_support import ENTERPRISES
    f=template_consumption;row,v,data,p=legacy(f,monkeypatch)
    with f['owner'].connect() as c:
        f['owner'].lock_principal(c,ENTERPRISES[0],exclusive=True)
        table='preparation_grants' if capability=='PREPARE' else 'capability_grants'
        c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',(ENTERPRISES[0],capability))
    saved=journal(f);before=products(f['owner'])
    assert cold(f,row).status_code==403
    assert post(f,row,'adopt',data,'independent-revoked').status_code==403
    assert journal(f)==saved and products(f['owner'])==before

def test_label_only_strict_proof_without_actual_advanced_source_stays_unresolved(template_consumption,monkeypatch):
    f=template_consumption;row,v,data,p=legacy(f,monkeypatch)
    with f['repository'].connect(write=True) as c:
        raw=c.execute("SELECT result FROM consumer_stages WHERE name LIKE 'CONFIRM_PLAN_%'").fetchone()
        result=json.loads(raw['result']);result['consumer_finalization']['proof_kind']='STRICTLY_ADVANCED_SOURCE'
        result['consumer_finalization'].pop('refusal_code',None)
        c.execute("UPDATE consumer_stages SET result=? WHERE name LIKE 'CONFIRM_PLAN_%'",(canonical(result),))
    saved=journal(f);before=products(f['owner'],include_audit=True)
    read=cold(f,row);assert read.status_code==200 and read.json()['state']=='UNKNOWN'
    assert post(f,row,'adopt',data,'independent-forged-strict').status_code==409
    assert journal(f)==saved and products(f['owner'],include_audit=True)==before
