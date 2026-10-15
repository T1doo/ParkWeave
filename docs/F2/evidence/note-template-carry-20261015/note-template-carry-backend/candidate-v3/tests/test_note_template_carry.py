"""Actual owned PG/API carriage; literal five-step partitions and preserved facts."""
from copy import deepcopy
from uuid import uuid4
import pytest
from parkweave import template_migration as migration
from parkweave.store import Conflict
from test_template_upgrade import upgrade_case,publication,check,choose,headers,GOALS
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
from test_template_migration_independent import full,stored,facts,recovery
from test_plan_source_conflicts import edit
from test_service_plan_manual_lock import lock
from test_service_case_steps import read as plan_read,verified

ALL=('P1','P2','P3','P4','P5')

def ready(u,source='1',locked=False):
    row,old,p=full(u);edit(u['f'],p,'  SYNTHETIC manual text retained\nexact whitespace  ')
    if locked:assert lock(u['f'],p,'P1').status_code==200
    return row,p,publication(u,GOALS,source,'SYNTHETIC compatible note carry')

def request(u,row,target):
    v=check(u,row,target);assert v.status_code==200,v.text
    assert choose(u,row,v.json(),'REQUEST_RECHECK').status_code==200
    v=check(u,row,target);assert v.status_code==200,v.text
    v=v.json();a=v['application']
    return v,dict(expected_instance_id=row['instance_id'],target_release_id=target['release_id'],expected_target_sha256=target['release_sha256'],
        expected_check_sha256=v['check_sha256'],expected_choice_revision=a['choice_revision'],expected_choice_event_sha256=a['choice_event_sha256'],
        expected_plan_id=a['plan_id'],expected_plan_revision=a['plan_revision'],expected_preparation_revision=a['preparation_revision'],expected_source_sha256=a['source_sha256'],
        reason='SYNTHETIC explicit exact manual carry',expected_note_carry_sha256=a['note_carry']['preview_sha256'],confirm_note_carry=True)

def apply(u,row,body,key=None,path='apply-note-carry'):
    return u['client'].post('/api/template-upgrade/'+row['instance_id']+'/'+path,headers=headers(u['f'][2],key=key or uuid4().hex),json=body)

@pytest.mark.parametrize('source,locked',[('1',True),('2',False)])
def test_actual_manual_carry_preserves_history_locks_and_original_case_outputs(upgrade_case,source,locked):
    u=upgrade_case;row,p,target=ready(u,source,locked);old=deepcopy(stored(u,row));business=facts(u)
    v,body=request(u,row,target);a=v['application'];n=a['note_carry'];ids=[s['id'] for s in old['steps']]
    assert not a['eligible'] and n['eligible'],n
    assert n['affected']==([] if source=='1' else ids) and n['preserved']==(ids if source=='1' else [])
    assert n['notes']==old['owner_amendments'] and n['target_template_source']['revision']==source
    key=uuid4().hex;r=apply(u,row,body,key);assert r.status_code==200,r.text
    event=r.json()['event'];now=stored(u,row)
    assert now['owner_amendments']==old['owner_amendments'] and now['events'][:-1]==old['events']
    assert now['id']==old['id'] and [s['id'] for s in now['steps']]==ids and [s['contract'] for s in now['steps']]==[s['contract'] for s in old['steps']]
    assert now.get('history')==old.get('history') and facts(u)==business
    if source=='1':assert now['steps']==old['steps'] and now['steps'][0]['manual_lock']==old['steps'][0]['manual_lock']
    else:
        assert all(s['invalidated'] for s in now['steps'])
        assert [s['verified_sources'] for s in now['steps']]==[s['verified_sources'] for s in old['steps']]
        for adapter in ALL:verified(u['f'],p,adapter)
    result=u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(u['f'][2]))
    assert result.status_code==200,result.text
    assert result.json()['state']=='LOCAL_OUTPUTS_VERIFIED' and facts(u)==business
    saved=deepcopy(stored(u,row));r=recovery(u,row,key);assert r.status_code==200 and r.json()['event']==event
    assert apply(u,row,body,key).json()['event']==event and stored(u,row)==saved
    assert apply(u,row,{**body,'reason':'SYNTHETIC changed key parameters'},key).status_code==409

def test_old_note_history_survives_later_edit_and_next_hop_carry(upgrade_case):
    u=upgrade_case;row,p,target=ready(u);_,body=request(u,row,target);key=uuid4().hex
    first=apply(u,row,body,key);assert first.status_code==200,first.text
    before=deepcopy(stored(u,row));edit(u['f'],p,'SYNTHETIC later legitimate manual edit')
    assert plan_read(u['f'],p).status_code==200
    target2=publication(u,GOALS,'1','SYNTHETIC next compatible carry');_,nextbody=request(u,row,target2)
    assert apply(u,row,{**nextbody,'expected_note_carry_sha256':body['expected_note_carry_sha256']}).status_code==409
    second=apply(u,row,nextbody);assert second.status_code==200,second.text
    assert stored(u,row)['events'][:len(before['events'])]==before['events']
    assert recovery(u,row,key).json()['event']==first.json()['event'] and plan_read(u['f'],p).status_code==200

@pytest.mark.parametrize('kind',['preparation','material','action_grant'])
def test_actual_committed_aba_refuses_old_carry_without_writes(upgrade_case,kind):
    u=upgrade_case;row,p,target=ready(u);_,body=request(u,row,target)
    if kind=='preparation':
        for _ in range(2):
            with u['f'][1].connect() as c:c.execute('UPDATE preparations SET goal=goal WHERE id=%s',(row['preparation_id'],))
    elif kind=='material':
        for _ in range(2):
            with u['f'][1].connect() as c:c.execute("UPDATE preparation_evidence SET source_label=source_label WHERE preparation_id=%s AND slot='material_outline'",(row['preparation_id'],))
    else:
        for active in (False,True):
            with u['f'][1].connect() as c:c.execute("UPDATE action_grants SET active=%s WHERE principal_id='fixture-a' AND park_id='park-a' AND org_id='org-a' AND action='case.create'",(active,))
    old=deepcopy(stored(u,row));business=facts(u);key=uuid4().hex;r=apply(u,row,body,key)
    assert r.status_code==409,r.text
    assert stored(u,row)==old and facts(u)==business and recovery(u,row,key).json()['status']=='NOT_OBSERVED'

def test_carry_write_failure_rolls_back_note_event_and_original_history(upgrade_case,monkeypatch):
    u=upgrade_case;row,p,target=ready(u);_,body=request(u,row,target);old=deepcopy(stored(u,row));business=facts(u);key=uuid4().hex
    original=migration.plans._save
    def fail(c,parent,plan):original(c,parent,plan);raise Conflict('SYNTHETIC failure after original PG save')
    with monkeypatch.context() as patch:
        patch.setattr(migration.plans,'_save',fail);r=apply(u,row,body,key)
    assert r.status_code==409 and stored(u,row)==old and facts(u)==business
    assert recovery(u,row,key).json()['status']=='NOT_OBSERVED'

def test_old_apply_cannot_carry_note_and_affected_lock_still_requires_unlock(upgrade_case):
    u=upgrade_case;row,p,target=ready(u);v,body=request(u,row,target);old=deepcopy(stored(u,row))
    plain={k:v for k,v in body.items() if k not in ('expected_note_carry_sha256','confirm_note_carry')}
    assert apply(u,row,plain,path='apply').status_code==409 and stored(u,row)==old
    assert lock(u['f'],p,'P1').status_code==200
    target=publication(u,GOALS,'2','SYNTHETIC source revision with P1 lock');r=check(u,row,target);assert r.status_code==200,r.text
    assert not r.json()['application']['note_carry']['eligible'] and 'LOCK_CONFLICT' in r.json()['application']['note_carry']['blockers']

@pytest.mark.parametrize('value',[1,1.0,'true',False])
def test_confirmation_requires_exact_boolean_true(value):
    from pydantic import ValidationError
    base=dict(expected_instance_id=str(uuid4()),target_release_id=str(uuid4()),expected_target_sha256='a'*64,expected_check_sha256='b'*64,expected_choice_revision=1,expected_choice_event_sha256='c'*64,
        expected_plan_id=str(uuid4()),expected_plan_revision=1,expected_preparation_revision=1,expected_source_sha256='d'*64,reason='SYNTHETIC explicit confirmation',expected_note_carry_sha256='e'*64,confirm_note_carry=value)
    with pytest.raises(ValidationError):migration.NoteCarryApply.model_validate(base)
