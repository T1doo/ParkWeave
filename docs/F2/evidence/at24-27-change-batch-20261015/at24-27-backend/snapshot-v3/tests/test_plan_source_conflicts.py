"""Actual owner note commands, material sources and original plan operations."""
from copy import deepcopy
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from parkweave import plan_source_conflicts as notes,controlled_plans as cp
from test_registered_local_revision import http_f,link_fixture,receipt_fixture,preparation_fixture,add_resource
from test_case_goal_results import complete,get as results,snapshot
from test_case_opportunities import imported,get as opportunities,post as opp_post,body as opp_body
from test_service_case_steps import read as plan_read,command as plan_command,adopt,adopt_body,verified
from test_service_plan_manual_lock import lock,stored
from test_source_change_adoption import preview as source_preview
from test_preparation import headers,add,command as prepare
from test_template_upgrade import upgrade_case


def path(p):return '/api/preparations/'+p['preparation_id']+'/plan-source-conflicts'
def read(f,p,card=None,user='fixture-a'):
    return f[3].get(path(p),params={'card_id':card['id']} if card else {},headers=headers(f[2],user))
def send(f,p,v,action,*,text=None,key=None,user='fixture-a'):
    data=deepcopy(v['action_requests'][action]);data['reason']='SYNTHETIC explicit owner coordination choice'
    if action=='EDIT_NOTE':data['text']=text
    return f[3].post(path(p)+'/commands',headers=headers(f[2],user,key or uuid4().hex),json=data)
def edit(f,p,text='SYNTHETIC manual coordination text'):
    v=read(f,p);assert v.status_code==200,v.text;v=v.json();assert v['can_edit'],v
    r=send(f,p,v,'EDIT_NOTE',text=text);assert r.status_code==200,r.text;return r.json()
def changed(f,p,*,mixed=False,text='SYNTHETIC actual outline source\n  exact content'):
    _,v,_=imported(f,p);card=v['cards'][0]
    p=add(f,p,slot='material_outline',text=text).json()
    if mixed:add_resource(f)
    r=opp_post(f,p,opp_body(opportunities(f,p).json(),'REFRESH'));assert r.status_code==200,r.text
    return p,r.json()['current']['cards'][0]
def cold(f,p,key,user='fixture-a'):
    return f[3].get(path(p)+'/recovery/'+key,headers=headers(f[2],user))


def test_original_edit_note_is_real_exact_text_and_old_source_events_unchanged(http_f):
    f=http_f;p,_,_,_=complete(f,local=True);old=stored(f,p);before=snapshot(f)
    text='  SYNTHETIC human annotation\n line two  '
    receipt=edit(f,p,text);now=stored(f,p);event=receipt['receipt']
    assert receipt['status']=='COMMITTED' and event['action']=='EDIT_NOTE'
    assert receipt['current']['note']['text']==text and now['events'][:-1]==old['events']
    assert now['steps']==old['steps'] and now['revision']==old['revision']+1
    assert all(d['before'] and d['changed'] is False for d in receipt['current']['material_diffs'])
    assert results(f,p).status_code==200
    assert snapshot(f)['resources']==before['resources'] if 'resources' in before else True
    r=cold(f,p,event['request_key']);assert r.status_code==200,r.text
    assert r.json()['receipt']==event and r.json()['historical_only']
    assert r.json()['current']['history']==[event]


def test_keep_defer_unlock_accept_changes_only_note_and_real_source_adopt_still_required(http_f):
    f=http_f;p,_,_,_=complete(f,local=True);first=edit(f,p);assert lock(f,p,'P1').status_code==200
    p,card=changed(f,p,mixed=True);baseline=stored(f,p);old_note=first['current']['note'];old_lock=baseline['steps'][0]['manual_lock']
    v=read(f,p,card);assert v.status_code==200,v.text;v=v.json()
    assert v['state']=='CONFLICT' and v['allowed_choices']==['KEEP_MANUAL','DEFER'] and not v['can_edit']
    assert v['source']['text']=='SYNTHETIC actual outline source\n  exact content'
    assert next(d for d in v['material_diffs'] if d['slot']=='material_outline')['before']['text']!=v['source']['text']
    r=send(f,p,v,'KEEP_MANUAL');assert r.status_code==200,r.text;v=r.json()['current']
    assert v['state']=='KEPT_MANUAL' and v['note']==old_note and stored(f,p)['steps'][0]['manual_lock']==old_lock
    x=plan_read(f,p).json();plain=adopt_body(f,p,local_revision=True);plain['expected_plan_revision']=x['revision']
    assert adopt(f,p,plain).status_code==409
    v=read(f,p,card).json()  # Original plan GET persists an invalidation/xmin.
    r=send(f,p,v,'DEFER');assert r.status_code==200,r.text;v=r.json()['current']
    assert v['state']=='DEFERRED' and v['note']==old_note and stored(f,p)['steps'][0]['manual_lock']==old_lock
    assert plan_command(f,p,'P1','UNLOCK').status_code==200
    v=read(f,p,card).json();r=send(f,p,v,'ACCEPT_SOURCE');assert r.status_code==200,r.text;v=r.json()['current']
    assert v['note']['text']==v['source']['text'] and v['note']['origin']=='SOURCE' and v['state']=='ACCEPTED_AWAITING_RECHECK'
    assert stored(f,p)['steps'][0]['verified_sources']==baseline['steps'][0]['verified_sources']
    source=source_preview(f,p,card);assert source.status_code==200,source.text;assert source.json()['can_adopt'],source.json()
    r=adopt(f,p,source.json()['adoption']);assert r.status_code==201,r.text
    assert results(f,p).json()['state']!='LOCAL_OUTPUTS_VERIFIED'


def test_unchanged_source_manual_text_difference_does_not_block_capacity_patch(http_f):
    f=http_f;p,_,_,_=complete(f,local=True);edit(f,p,'SYNTHETIC independent explanation differs from outline')
    _,v,_=imported(f,p);card=v['cards'][0];add_resource(f)
    card=opp_post(f,p,opp_body(opportunities(f,p).json(),'REFRESH')).json()['current']['cards'][0]
    v=read(f,p,card).json();assert v['state']=='NO_CHANGE' and not v['can_resolve']
    source=source_preview(f,p,card).json();assert source['can_adopt'],source
    assert adopt(f,p,source['adoption']).status_code==201


def test_note_key_idempotency_lost_response_cold_read_and_parameter_conflict(http_f):
    f=http_f;p,_,_,_=complete(f,local=True);v=read(f,p).json();key=uuid4().hex
    first=send(f,p,v,'EDIT_NOTE',text='SYNTHETIC exact original note',key=key);assert first.status_code==200,first.text
    event=first.json()['receipt'];before=stored(f,p)
    repeated=send(f,p,v,'EDIT_NOTE',text='SYNTHETIC exact original note',key=key)
    assert repeated.status_code==200 and repeated.json()['receipt']==event and stored(f,p)==before
    changed=send(f,p,v,'EDIT_NOTE',text='SYNTHETIC changed parameters',key=key)
    assert changed.status_code==409 and changed.json().get('status')!='DEFINITIVELY_REJECTED'
    assert cold(f,p,key).json()['receipt']==event and stored(f,p)==before
    assert cold(f,p,uuid4().hex).json()['status']=='NOT_OBSERVED'


def test_stale_domain_gate_proves_rollback_but_busy_and_key_conflict_do_not(http_f):
    f=http_f;p,_,_,_=complete(f,local=True);v=read(f,p).json();first=send(f,p,v,'EDIT_NOTE',text='SYNTHETIC changed revision');assert first.status_code==200
    key=uuid4().hex;body=deepcopy(v['action_requests']['EDIT_NOTE']);body.update(text='SYNTHETIC stale note',reason='SYNTHETIC explicit stale attempt')
    r=f[3].post(path(p)+'/commands',headers=headers(f[2],key=key),json=body)
    assert r.status_code==409,r.text;proof=r.json()
    assert proof['status']=='DEFINITIVELY_REJECTED' and proof['fingerprint']==cp._hash(dict(preparation_id=p['preparation_id'],**body))
    assert proof['request_key']==key and proof['business_writes'] is False
    assert cold(f,p,key).json()['status']=='NOT_OBSERVED'


def test_execute_revocation_keeps_read_history_but_denies_new_note_commands(http_f):
    f=http_f;p,_,_,_=complete(f,local=True);first=edit(f,p);key=first['receipt']['request_key']
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    r=cold(f,p,key);assert r.status_code==200,r.text
    assert r.json()['receipt']==first['receipt'] and not r.json()['current']['action_requests']
    v=first['current'];body=deepcopy(v['action_requests']['EDIT_NOTE']);body.update(text='SYNTHETIC refused new note',reason='SYNTHETIC after revocation')
    r=f[3].post(path(p)+'/commands',headers=headers(f[2],key=uuid4().hex),json=body)
    assert r.status_code==403


def test_binding_replacement_cannot_silently_drop_current_note(http_f):
    f=http_f;p,_,_,_=complete(f,local=True);edit(f,p)
    with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','999'::jsonb)")
    v=plan_read(f,p);assert v.status_code==200,v.text;v=v.json()
    assert not v['can_adopt'] and not v['can_adopt_partial']
    assert 'OWNER_NOTE_CONTROLLED_CARRY_REQUIRED_FOR_REPLACEMENT' in v['owner_note_blockers']
    body=adopt_body(f,{**p,'revision':v['preparation_revision']});body['expected_plan_revision']=v['revision']
    before=snapshot(f);original=stored(f,p)
    r=adopt(f,p,body);assert r.status_code==409,r.text
    assert snapshot(f)==before and stored(f,p)==original
    assert stored(f,p)['owner_amendments'] and read(f,p).json()['note']


@pytest.mark.parametrize('damage',['note_bool_version','note_float_version','op_counterpart','plan_counterpart','missing_op_counterpart'])
def test_annotation_history_rejects_single_side_tampering(http_f,damage):
    f=http_f;p,_,_,_=complete(f,local=True);edit(f,p)
    with f[1].connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
        plan=deepcopy(parent['service_case_plan']);ledger=deepcopy(parent['opportunities'])
        if damage.startswith('note_'):
            note=next(iter(plan['owner_amendments'].values()))
            note['source_ref']['version']=True if damage=='note_bool_version' else float(note['source_ref']['version'])
        elif damage=='op_counterpart':
            ledger['events'][-1]['payload']['plan_event']['reason']='SYNTHETIC one sided mutation'
            ledger['events'][-1]['sha256']=cp._hash({k:v for k,v in ledger['events'][-1].items() if k!='sha256'})
        elif damage=='plan_counterpart':plan['events'][-1]['reason']='SYNTHETIC other side mutation'
        else:ledger['events']=[];ledger['revision']=0
        c.execute('UPDATE preparations SET service_case_plan=%s,opportunities=%s WHERE id=%s',(Jsonb(plan),Jsonb(ledger),p['preparation_id']))
    before=snapshot(f);r=read(f,p);assert r.status_code==409,r.text
    assert results(f,p).status_code==409 and snapshot(f)==before


def test_template_apply_cannot_reinterpret_or_drop_annotation_history(upgrade_case):
    from test_template_upgrade import instance,confirmed,publication,check,choose,GOALS
    u=upgrade_case;f=u['f'];row,_=instance(u,GOALS[:1]);p=confirmed(u,row);verified(f,p,'P1');edit(f,p)
    target=publication(u,GOALS[:1],source='1',name='SYNTHETIC title-only template revision')
    v=check(u,row,target);assert v.status_code==200,v.text;v=v.json()
    r=choose(u,row,v,'ACK_COMPATIBLE');assert r.status_code==200,r.text
    v=check(u,row,target).json();a=v['application']
    body=dict(expected_instance_id=row['instance_id'],target_release_id=target['release_id'],expected_target_sha256=target['release_sha256'],
        expected_check_sha256=v['check_sha256'],expected_choice_revision=a['choice_revision'],expected_choice_event_sha256=a['choice_event_sha256'],
        expected_plan_id=a['plan_id'],expected_plan_revision=a['plan_revision'],expected_preparation_revision=a['preparation_revision'],
        expected_source_sha256=a['source_sha256'],reason='SYNTHETIC explicit compatibility apply must preserve annotation')
    before=snapshot(f);original=stored(f,p)
    r=u['client'].post('/api/template-upgrade/'+row['instance_id']+'/apply',headers=headers(f[2],key=uuid4().hex),json=body)
    assert r.status_code==409,r.text
    assert snapshot(f)==before and stored(f,p)==original and read(f,p).status_code==200
