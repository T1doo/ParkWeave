"""Exact content carriage and original owner continuation against actual PG/HTTP."""
from copy import deepcopy
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from parkweave import plan_source_conflicts as notes, controlled_plans as cp
from test_plan_source_conflicts import (
    http_f,link_fixture,receipt_fixture,preparation_fixture,read,edit,changed,cold,
    send as old_send,path,stored,snapshot,complete,adopt,source_preview,plan_command,lock,
)
from test_preparation import headers


def send(f,p,value,action,text=None,key=None):
    data=deepcopy(value['action_requests'][action]);data['reason']='SYNTHETIC explicit exact-content continuation'
    if action in ('EDIT_NOTE','MERGE_NOTE'):data['text']=text
    return f[3].post(path(p)+'/commands',headers=headers(f[2],key=key or uuid4().hex),json=data)


@pytest.mark.parametrize('manual,source,known,satisfied,counts',[
    ('  A\nA\nA\n','  A\nA\nA\n',True,True,[(1,1),(2,2)]),
    ('A\nA','A\nA\nA',True,False,[(3,2)]),
    ('prefix A suffix','A',True,False,[(1,0)]),
    ('A',' A',True,False,[(1,0)]),
    ('a','A',True,False,[(1,0)]),
    ('A\r\nB','A\nB',True,True,[(1,1),(1,1)]),
    ('A',' \n\t\n',False,False,[]),
    ('A\n'*128,'A\n'*128,True,True,[(128,128)]),
    ('A\n'*129,'A\n'*129,False,False,[]),
])
def test_frozen_line_carriage_is_exact_bounded_and_counts_duplicates(manual,source,known,satisfied,counts):
    result=notes.line_coverage_v1(manual,source)
    assert result['coverage_known'] is known and result['coverage_satisfied'] is satisfied
    assert [(row['required_count'],row['present_count']) for row in result['conditions']]==counts
    assert all(row['missing_count']==max(0,row['required_count']-row['present_count']) for row in result['conditions'])


def test_real_append_merge_preserves_manual_and_allows_only_original_source_adopt(http_f):
    f=http_f;p,_,_,_=complete(f,local=True);manual='  SYNTHETIC owner authored explanation\n preserve exact whitespace  '
    first=edit(f,p,manual);p,card=changed(f,p,mixed=True,text='SYNTHETIC incoming exact row\n  second exact row')
    v=read(f,p,card);assert v.status_code==200,v.text;v=v.json();c=v['continuation']
    assert c['baseline']['text']==first['current']['source']['text'] and c['manual']['text']==manual and c['incoming']['text']==v['source']['text']
    assert c['can_merge'] and not c['can_keep_and_continue'] and not c['semantic_evaluated']
    before=stored(f,p);merged=manual+'\n'+v['source']['text'];key=uuid4().hex
    r=send(f,p,v,'MERGE_NOTE',merged,key);assert r.status_code==200,r.text;receipt=r.json()['receipt'];after=stored(f,p)
    assert r.json()['current']['state']=='CONTINUED_AWAITING_RECHECK'
    note=r.json()['current']['note'];assert note['text']==merged and note['origin']=='MANUAL' and note['verified_package_sha256'] is None
    assert receipt['plan_note']['version']==2 and receipt['plan_note']['preview_basis']['schema']==2
    assert after['steps']==before['steps'] and after['events'][:-1]==before['events']
    r=cold(f,p,key);assert r.status_code==200 and r.json()['receipt']==receipt
    preview=source_preview(f,p,card);assert preview.status_code==200 and preview.json()['can_adopt'],preview.text
    adopted=adopt(f,p,preview.json()['adoption']);assert adopted.status_code==201,adopted.text
    assert stored(f,p)['id']==after['id'] and stored(f,p)['owner_amendments']==after['owner_amendments']


def test_keep_requires_exact_conditions_then_edit_requires_explicit_reconfirmation(http_f):
    from test_registered_local_revision import patch_body
    f=http_f;p,_,_,_=complete(f,local=True);manual='  SYNTHETIC owner protected note  '
    edit(f,p,manual);assert lock(f,p,'P1').status_code==200
    p,card=changed(f,p,mixed=True,text='SYNTHETIC repeated condition\nSYNTHETIC repeated condition\n  exact condition  ')
    v=read(f,p,card).json();assert not v['continuation']['can_merge'] and not v['continuation']['can_keep_and_continue']
    assert plan_command(f,p,'P1','UNLOCK').status_code==200
    v=read(f,p,card).json();assert v['continuation']['can_merge'] and not v['continuation']['can_keep_and_continue']
    forged=deepcopy(v['action_requests']['MERGE_NOTE']);forged.update(action='KEEP_AND_CONTINUE',text=None,reason='SYNTHETIC missing exact lines')
    before=stored(f,p);r=f[3].post(path(p)+'/commands',headers=headers(f[2],key=uuid4().hex),json=forged)
    assert r.status_code==409 and stored(f,p)==before
    r=old_send(f,p,v,'KEEP_MANUAL');assert r.status_code==200,r.text
    assert source_preview(f,p,card).json()['can_adopt'] is False
    v=read(f,p,card).json();text=manual+'\n'+v['source']['text']
    r=send(f,p,v,'EDIT_NOTE',text);assert r.status_code==200,r.text
    v=read(f,p,card).json();assert v['continuation']['can_keep_and_continue']
    r=send(f,p,v,'KEEP_AND_CONTINUE');assert r.status_code==200,r.text
    assert r.json()['current']['note']['text']==text and r.json()['current']['note']['origin']=='MANUAL'
    assert source_preview(f,p,card).json()['can_adopt']
    # Even an edit that retains every exact condition needs a fresh decision.
    v=read(f,p,card).json();r=send(f,p,v,'EDIT_NOTE',text+'\nSYNTHETIC new human addition');assert r.status_code==200,r.text
    preview=source_preview(f,p,card).json();assert not preview['can_adopt'] and 'OWNER_NOTE_CONTENT_EDIT_REQUIRES_RECONFIRMATION' in preview['blocking_reasons']
    body=patch_body(f,p);before=snapshot(f);assert adopt(f,p,body).status_code==409 and snapshot(f)==before
    v=read(f,p,card).json();assert v['state']=='CONFLICT' and v['continuation']['can_keep_and_continue']
    r=send(f,p,v,'KEEP_AND_CONTINUE');assert r.status_code==200,r.text
    assert source_preview(f,p,card).json()['can_adopt']
    v=read(f,p,card).json();r=send(f,p,v,'EDIT_NOTE','SYNTHETIC explicit new manual content omitting conditions');assert r.status_code==200,r.text
    preview=source_preview(f,p,card).json();assert not preview['can_adopt'] and 'OWNER_NOTE_SOURCE_LINES_NOT_CARRIED' in preview['blocking_reasons']
    v=read(f,p,card).json();assert not v['continuation']['can_keep_and_continue'] and v['continuation']['can_merge']


def test_original_source_accept_then_plain_edit_retains_schema_one_behavior(http_f):
    f=http_f;p,_,_,_=complete(f,local=True);edit(f,p)
    p,card=changed(f,p,mixed=True);v=read(f,p,card).json();r=old_send(f,p,v,'ACCEPT_SOURCE');assert r.status_code==200,r.text
    accepted=r.json()['receipt'];assert accepted['plan_note']['version']==1
    edited=edit(f,p,'SYNTHETIC existing schema-one free coordination note')
    assert edited['receipt']['plan_note']['version']==1 and edited['current']['note']['origin']=='MANUAL'
    preview=source_preview(f,p,card);assert preview.status_code==200 and preview.json()['can_adopt'],preview.text
    assert not any('RECONFIRMATION' in reason for reason in preview.json()['blocking_reasons'])


def test_missing_old_second_slot_refuses_new_continuation_without_rewriting_history(http_f):
    from test_case_opportunities import get as opportunities,post as opp_post,body as opp_body
    from parkweave.store import digest
    f=http_f;p,_,_,_=complete(f,local=True);first=edit(f,p);p,card=changed(f,p,mixed=True)
    old=next(m for m in first['current']['note']['source_package'] if m['slot']=='need_summary')
    with f[1].connect() as c:c.execute('UPDATE preparation_evidence SET text=%s,source_sha256=%s WHERE id=%s',('SYNTHETIC owned historical source corruption',digest('SYNTHETIC owned historical source corruption'),old['id']))
    refreshed=opp_post(f,p,opp_body(opportunities(f,p).json(),'REFRESH'));assert refreshed.status_code==200,refreshed.text;card=refreshed.json()['current']['cards'][0]
    before=stored(f,p);v=read(f,p,card);assert v.status_code==200,v.text;v=v.json();projection=v['continuation']
    assert projection['baseline'] is None and projection['baseline_package_epochs'] is None and projection['preview_sha256'] is None
    assert not projection['can_merge'] and not projection['can_keep_and_continue'] and stored(f,p)==before
    assert 'ACTUAL_HISTORICAL_NOTE_SOURCE_REQUIRED' in projection['blocking_reasons']


def test_historical_source_row_aba_stales_only_new_exact_continuation_preview(http_f):
    from parkweave.store import digest
    f=http_f;p,_,_,_=complete(f,local=True);first=edit(f,p);p,card=changed(f,p,mixed=True)
    v=read(f,p,card).json();body=deepcopy(v['action_requests']['MERGE_NOTE']);body.update(text=v['note']['text']+'\n'+v['source']['text'],reason='SYNTHETIC stale exact historical source preview')
    original=next(m for m in first['current']['note']['source_package'] if m['slot']=='material_outline')
    for text in ('SYNTHETIC temporary historical source change',original['text']):
        with f[1].connect() as c:c.execute('UPDATE preparation_evidence SET text=%s,source_sha256=%s WHERE id=%s',(text,digest(text),original['id']))
    fresh=read(f,p,card).json();assert fresh['preview_sha256']==v['preview_sha256'] and fresh['continuation']['preview_sha256']!=v['continuation']['preview_sha256']
    before=snapshot(f);key=uuid4().hex;r=f[3].post(path(p)+'/commands',headers=headers(f[2],key=key),json=body)
    assert r.status_code==409 and snapshot(f)==before and cold(f,p,key).json()['status']=='NOT_OBSERVED'


def test_new_proof_rebuild_uses_frozen_v1_line_rules_after_current_wrapper_changes(http_f,monkeypatch):
    from parkweave import service_case_steps as service
    f=http_f;p,_,_,_=complete(f,local=True);edit(f,p);p,card=changed(f,p,mixed=True);v=read(f,p,card).json()
    r=send(f,p,v,'MERGE_NOTE',v['note']['text']+'\n'+v['source']['text']);assert r.status_code==200,r.text
    with f[1].connect() as c:parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
    monkeypatch.setattr(notes,'line_coverage',lambda *args:dict(coverage_known=False,coverage_satisfied=False,conditions=[]))
    assert service._recovery_proofs(parent)


def test_actual_catalog_becomes_unknown_at_final_reread_refuses_without_new_event(http_f,monkeypatch):
    f=http_f;p,_,_,_=complete(f,local=True);edit(f,p);p,card=changed(f,p,mixed=True);v=read(f,p,card).json()
    original=notes._view;calls=0
    def changed_at_final_read(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2:
            # Actual owned PG source changes in a separate committed admin
            # transaction. SELECT-only catalogue scope is never escalated.
            with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}','\"UNKNOWN\"'::jsonb) WHERE (park_id,service_id,version) IN (SELECT park_id,service_id,service_version FROM preparations WHERE id=%s)",(p['preparation_id'],))
        return original(*args,**kwargs)
    monkeypatch.setattr(notes,'_view',changed_at_final_read)
    before=snapshot(f);key=uuid4().hex;r=send(f,p,v,'MERGE_NOTE',v['note']['text']+'\n'+v['source']['text'],key)
    assert calls==2 and r.status_code==409,r.text
    assert r.json().get('status')!='DEFINITIVELY_REJECTED' and snapshot(f)==before
    with f[1].connect() as c:assert c.execute("SELECT source->>'kind' AS kind FROM preparation_catalog WHERE (park_id,service_id,version) IN (SELECT park_id,service_id,service_version FROM preparations WHERE id=%s)",(p['preparation_id'],)).fetchone()['kind']=='UNKNOWN'
    recovery=cold(f,p,key);assert recovery.status_code==200 and recovery.json()['status']=='NOT_OBSERVED'
    assert snapshot(f)==before
