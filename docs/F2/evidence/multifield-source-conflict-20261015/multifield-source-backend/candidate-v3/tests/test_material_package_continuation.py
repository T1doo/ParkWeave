"""Owned PostgreSQL/API probes for explicit two-slot package note confirmation."""
from copy import deepcopy
from uuid import uuid4
import json
import pytest
from pydantic import ValidationError
from parkweave import material_package_continuation as package, controlled_plans as cp, service_case_steps as service
from parkweave import case_opportunities as op
from parkweave.store import Conflict
from test_plan_source_conflicts import http_f,link_fixture,receipt_fixture,preparation_fixture,edit,complete,stored,snapshot
from test_plan_source_conflicts import read as old_read,send as old_send,cold as old_cold
from test_case_opportunities import imported,get as opportunities,post as opportunity_post,body as opportunity_body
from test_preparation import headers,add,command as prepare
from test_service_case_steps import adopt,read as plan_read,verified
from test_source_change_adoption import preview as source_preview
from test_registered_local_revision import patch_body


def path(p):return '/api/preparations/'+p['preparation_id']+'/plan-material-package'
def read(f,p,card=None):return f[3].get(path(p),params={'card_id':card['id']} if card else {},headers=headers(f[2]))
def send(f,p,value,action='KEEP_AND_CONTINUE',text=None,key=None):
    body=deepcopy(value['action_requests'][action]);body['reason']='SYNTHETIC explicit full material package confirmation'
    if action=='MERGE_NOTE':body['text']=text
    return f[3].post(path(p)+'/commands',headers=headers(f[2],key=key or uuid4().hex),json=body)
def cold(f,p,key):return f[3].get(path(p)+'/recovery/'+key,headers=headers(f[2]))
def card(f,p):
    _,value,_=imported(f,p);return value['cards'][0]
def refresh(f,p):
    r=opportunity_post(f,p,opportunity_body(opportunities(f,p).json(),'REFRESH'));assert r.status_code==200,r.text
    return r.json()['current']['cards'][0]
def setup(f):
    p,_,_,_=complete(f,local=True);first=edit(f,p,'  SYNTHETIC owner coordination only  ');return p,card(f,p),first


def test_first_get_is_readonly_and_explicit_post_enables_without_outline_obligation(http_f):
    f=http_f;p,c,first=setup(f);before=deepcopy(stored(f,p));business=snapshot(f)
    r=read(f,p,c);assert r.status_code==200,r.text;v=r.json();q=v['package_confirmation']
    assert stored(f,p)==before and snapshot(f)==business
    assert v['scope']==package.SCOPE and not q['active'] and q['mode']=='LEGACY_OUTLINE_ONLY'
    assert not q['outline_carriage_required'] and q['coverage']['required'] is False and q['coverage']['conditions']==[]
    assert q['can_keep_and_continue'] and q['can_merge'] and q['manual']['text']==first['current']['note']['text']
    key=uuid4().hex;r=send(f,p,v,key=key);assert r.status_code==200,r.text
    event=r.json()['receipt'];now=stored(f,p)
    assert event['plan_note']['version']==3 and event['plan_note']['request']['schema']==2
    assert now['events'][:-1]==before['events'] and now['steps']==before['steps'] and now['id']==before['id']
    assert now['owner_amendments'][v['step_id']]['text']==first['current']['note']['text']
    assert r.json()['current']['package_confirmation']['active']
    stable=deepcopy(stored(f,p));assert send(f,p,v,key=key).json()['receipt']==event and stored(f,p)==stable
    assert cold(f,p,key).json()['receipt']==event and old_cold(f,p,first['receipt']['request_key']).json()['receipt']==first['receipt']


def test_summary_only_requires_fresh_context_ack_without_copying_summary_into_manual(http_f):
    f=http_f;p,c,_=setup(f);v=read(f,p,c).json();r=send(f,p,v);assert r.status_code==200,r.text;note=r.json()['current']['note']
    changed=add(f,p,slot='need_summary',text='SYNTHETIC new context never required as owner note prose');assert changed.status_code==200,changed.text;p=changed.json();c=refresh(f,p)
    preview=source_preview(f,p,c);assert preview.status_code==200,preview.text
    assert not preview.json()['can_adopt'] and 'OWNER_NOTE_SOURCE_PACKAGE_CONFIRMATION_REQUIRED' in preview.json()['blocking_reasons']
    body=patch_body(f,p);before=snapshot(f);assert adopt(f,p,body).status_code==409 and snapshot(f)==before
    v=read(f,p,c).json();q=v['package_confirmation'];assert not q['outline_carriage_required'] and q['can_keep_and_continue']
    assert q['policy']['need_summary']=='CONTEXT_ACK_ONLY' and q['manual']['text']==note['text']
    r=send(f,p,v);assert r.status_code==200,r.text
    assert r.json()['current']['note']['text']==note['text'] and r.json()['current']['note']['origin']=='MANUAL'
    preview=source_preview(f,p,c);assert preview.status_code==200 and preview.json()['can_adopt'],preview.text
    assert adopt(f,p,preview.json()['adoption']).status_code==201
    assert package.active(stored(f,p)) and plan_read(f,p).status_code==200


def test_outline_obligation_stays_required_after_summary_change_and_edit(http_f):
    f=http_f;p,c,_=setup(f);p=add(f,p,slot='material_outline',text='SYNTHETIC actual new outline\n  required exact line').json();c=refresh(f,p)
    v=read(f,p,c).json();assert v['package_confirmation']['outline_carriage_required'] and not v['package_confirmation']['can_keep_and_continue']
    merged=v['note']['text']+'\n'+v['source']['text'];r=send(f,p,v,'MERGE_NOTE',merged);assert r.status_code==200,r.text
    p=add(f,p,slot='need_summary',text='SYNTHETIC subsequent summary only').json();c=refresh(f,p);v=read(f,p,c).json()
    assert v['package_confirmation']['outline_carriage_required'] and v['package_confirmation']['can_keep_and_continue']
    assert send(f,p,v).status_code==200
    edit(f,p,merged+'\nSYNTHETIC legal new manual addition')
    preview=source_preview(f,p,c).json();assert not preview['can_adopt'] and 'OWNER_NOTE_CONTENT_EDIT_REQUIRES_RECONFIRMATION' in preview['blocking_reasons']
    v=read(f,p,c).json();assert v['package_confirmation']['can_keep_and_continue'] and send(f,p,v).status_code==200
    edit(f,p,'SYNTHETIC manual edit removing required source rows')
    v=read(f,p,c).json();assert not v['package_confirmation']['can_keep_and_continue'] and v['package_confirmation']['can_merge']


@pytest.mark.parametrize('action',['ACCEPT_SOURCE','KEEP_AND_CONTINUE','MERGE_NOTE'])
def test_active_mode_rejects_legacy_source_rebase_without_note_or_ledger_writes(http_f,action):
    f=http_f;p,c,_=setup(f);assert send(f,p,read(f,p,c).json()).status_code==200
    p=add(f,p,slot='material_outline',text='SYNTHETIC later outline').json();c=refresh(f,p)
    old=old_read(f,p,c).json();assert action not in old['action_requests']
    value=deepcopy(read(f,p,c).json()['action_requests']['MERGE_NOTE'])
    value.pop('confirm_package');value.update(schema=1,action=action,reason='SYNTHETIC valid legacy downgrade attempt',text=old['note']['text']+'\n'+old['source']['text'] if action=='MERGE_NOTE' else None)
    before=snapshot(f);r=f[3].post('/api/preparations/'+p['preparation_id']+'/plan-source-conflicts/commands',headers=headers(f[2],key=uuid4().hex),json=value)
    assert r.status_code==409 and snapshot(f)==before


def test_current_material_row_aba_invalidates_preview_and_persistent_confirmation(http_f):
    f=http_f;p,c,_=setup(f);v=read(f,p,c).json();key=uuid4().hex;assert send(f,p,v,key=key).status_code==200
    fresh=read(f,p,c).json();material=fresh['package_confirmation']['current_package'][0]
    for label in ('SYNTHETIC temporary owned material label',material['source_label']):
        with f[1].connect() as connection:connection.execute('UPDATE preparation_evidence SET source_label=%s WHERE id=%s',(label,material['id']))
    r=send(f,p,fresh);assert r.status_code==409 and r.json()['status']=='DEFINITIVELY_REJECTED'
    x=source_preview(f,p,c);assert x.status_code==200 and not x.json()['can_adopt']
    assert 'OWNER_NOTE_SOURCE_PACKAGE_CONFIRMATION_REQUIRED' in x.json()['blocking_reasons']
    assert cold(f,p,key).json()['status']=='COMMITTED'
    current=read(f,p,c).json();assert current['package_confirmation']['can_keep_and_continue'] and send(f,p,current).status_code==200


def test_execute_revoke_denies_new_post_but_original_package_history_stays_readable(http_f):
    f=http_f;p,c,_=setup(f);v=read(f,p,c).json();key=uuid4().hex;r=send(f,p,v,key=key);assert r.status_code==200,r.text;event=r.json()['receipt']
    with f[1].connect() as connection:
        f[1].lock_principal(connection,'fixture-a',exclusive=True)
        connection.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    assert cold(f,p,key).status_code==200 and cold(f,p,key).json()['receipt']==event
    assert send(f,p,v,key=key).status_code==403


def test_unknown_historical_summary_expands_package_scope_after_legacy_adopt_p1_verify(http_f):
    from parkweave.store import digest
    f=http_f;p,c,first=setup(f);original=deepcopy(first['current']['note'])
    p=add(f,p,slot='need_summary',text='SYNTHETIC actually accepted later context').json()
    p=prepare(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC actual context review').json()
    p=prepare(f,p,'CONFIRM',reason='SYNTHETIC actual context confirmation').json();c=refresh(f,p)
    current=source_preview(f,p,c);assert current.status_code==200 and current.json()['can_adopt'],current.text
    assert adopt(f,p,current.json()['adoption']).status_code==201;verified(f,p,'P1')
    graph=f[3].get('/api/preparations/'+p['preparation_id']+'/source-impact',headers=headers(f[2]));assert graph.status_code==200,graph.text
    assert graph.json()['source_impact']['affected']==[]
    old=next(m for m in original['source_package'] if m['slot']=='need_summary')
    text='SYNTHETIC owned historical summary now unavailable'
    with f[1].connect() as connection:connection.execute('UPDATE preparation_evidence SET text=%s,source_sha256=%s WHERE id=%s',(text,digest(text),old['id']))
    before=deepcopy(stored(f,p));r=read(f,p,c);assert r.status_code==200,r.text;v=r.json()
    assert v['state']=='UNKNOWN' and v['unknown_scope']=='THIS_CASE' and v['affected']==[s['id'] for s in before['steps']] and v['preserved']==[]
    assert v['package_confirmation']['manual']['text']==original['text'] and v['package_confirmation']['baseline_package'] is None
    assert not v['action_requests'] and stored(f,p)==before


@pytest.mark.parametrize('field,value',[('schema',True),('schema',2.0),('confirm_package',1),('confirm_package',1.0),('confirm_package','true'),('reason','\ud800')])
def test_new_request_strict_types_and_utf8_fail_before_any_execution(field,value):
    body=dict(schema=2,action='KEEP_AND_CONTINUE',expected_plan_id=str(uuid4()),expected_plan_revision=1,expected_note_revision=1,
        expected_ledger_revision=0,expected_preview_sha256='a'*64,card_id=str(uuid4()),text=None,reason='SYNTHETIC exact confirmation',confirm_package=True)
    body[field]=value
    with pytest.raises(ValidationError):package.Command.model_validate(body)


def test_actual_http_lone_surrogate_reason_is_structural_422_without_writes(http_f):
    f=http_f;p,c,_=setup(f);value=read(f,p,c).json();body=deepcopy(value['action_requests']['KEEP_AND_CONTINUE'])
    body['reason']='\ud800';before=snapshot(f)
    h=headers(f[2],key=uuid4().hex);h['content-type']='application/json'
    r=f[3].post(path(p)+'/commands',headers=h,content=json.dumps(body,ensure_ascii=True).encode('utf-8'))
    assert r.status_code==422 and snapshot(f)==before


@pytest.mark.parametrize('damage',['invented_step_endpoint','changed_original_before_sources'])
def test_full_history_rejects_rehashed_source_context_detached_from_actual_plan(http_f,damage):
    f=http_f;p,c,_=setup(f);r=send(f,p,read(f,p,c).json());assert r.status_code==200,r.text
    with f[1].connect() as connection:parent=connection.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
    parent=deepcopy(parent);plan=parent['service_case_plan'];event=plan['events'][-1];proof=event['plan_note'];basis=proof['preview_basis'];change=basis['source_change']
    if damage=='invented_step_endpoint':
        graph=change['source_impact'];old=next(e['id'] for e in graph['step_endpoints'] if e['adapter_id']=='P2');new=str(uuid4())
        for endpoint in graph['step_endpoints']:
            if endpoint['id']==old:endpoint['id']=new
        for node in graph['nodes']:
            if node['step_id']==old:node['step_id']=new
        for edge in graph['edges']:
            for key in ('upstream','downstream'):
                if edge[key]==old:edge[key]=new
        for part in ('affected','preserved'):
            graph[part]=[new if id==old else id for id in graph[part]];change[part]=[new if id==old else id for id in change[part]]
        change['directly_changed']=[new if id==old else id for id in change['directly_changed']]
        graph['sha256']=op.sha({k:v for k,v in graph.items() if k!='sha256'})
    else:change['before_sources']['P2']['preparation_revision']+=1
    change['sha256']=op.sha({k:v for k,v in change.items() if k!='sha256'})
    proof['preview_sha256']=op.sha(basis);proof['request']['expected_preview_sha256']=proof['preview_sha256']
    event['fingerprint']=package.fingerprint(p['preparation_id'],package.Command.model_validate(proof['request']))
    proof['sha256']=op.sha({k:v for k,v in proof.items() if k!='sha256'})
    linked=parent['opportunities']['events'][-1];linked['fingerprint']=event['fingerprint'];linked['payload']['plan_event']=deepcopy(event)
    linked['sha256']=op.sha({k:v for k,v in linked.items() if k!='sha256'})
    with pytest.raises(Conflict):service._recovery_proofs(parent)


def test_final_current_availability_refusal_rolls_back_when_basis_is_unchanged(http_f,monkeypatch):
    f=http_f;p,c,_=setup(f);v=read(f,p,c).json();original=package._view;calls=0
    def final_unavailable(*args,**kwargs):
        nonlocal calls
        calls+=1;value,basis=original(*args,**kwargs)
        if calls==2:
            value=dict(value,state='UNKNOWN',action_requests={},can_edit=False,can_resolve=False,unknown_scope='THIS_CASE')
            value['package_confirmation']=dict(value['package_confirmation'],can_keep_and_continue=False,can_merge=False)
        return value,basis
    monkeypatch.setattr(package,'_view',final_unavailable);before=snapshot(f);key=uuid4().hex
    r=send(f,p,v,key=key)
    assert r.status_code==409 and r.json().get('status')!='DEFINITIVELY_REJECTED' and snapshot(f)==before
    monkeypatch.setattr(package,'_view',original)
    assert cold(f,p,key).json()['status']=='NOT_OBSERVED'
