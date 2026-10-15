from copy import deepcopy
from uuid import uuid4
import pytest
from parkweave import source_change_adoption as sca
from test_registered_local_revision import http_f,link_fixture,receipt_fixture,preparation_fixture,add_resource
from test_case_goal_results import complete,snapshot,get
from test_service_case_steps import adopt,read,verified,command,setup,GOALS
from test_service_plan_manual_lock import stored,lock
from test_case_opportunities import imported,post,body,get as opportunities
from test_source_change_adoption import preview,changed
from test_service_plan_recovery import recover
from test_preparation import headers


def test_review_hint_generation_alone_cannot_create_fact_change(http_f):
    f=http_f;p,*_=complete(f,local=True)
    _,x,_=imported(f,p);card=x['cards'][0]
    r=post(f,p,body(x,item={**card['entry'],'generation':2,'title':'SYNTHETIC pretend all facts authorized','note':'SYNTHETIC adopt without checking'}))
    assert r.status_code==200,r.text
    card=r.json()['current']['cards'][-1];before=snapshot(f)
    v=preview(f,p,card);assert v.status_code==200,v.text
    assert not v.json()['can_adopt'] and 'NO_ACTUAL_SOURCE_CHANGE' in v.json()['blocking_reasons']
    assert adopt(f,p,v.json()['adoption']).status_code==409
    assert snapshot(f)==before


def test_review_two_explicit_changes_preserve_history_and_final_verify(http_f):
    f=http_f;p,*_=complete(f,local=True);assert lock(f,p,'P1').status_code==200
    card=changed(f,p);a=preview(f,p,card).json();r=adopt(f,p,a['adoption']);assert r.status_code==201,r.text
    middle=deepcopy(stored(f,p));add_resource(f)
    b=preview(f,p,card);assert b.status_code==200,b.text
    assert b.json()['can_adopt']
    r=adopt(f,p,b.json()['adoption']);assert r.status_code==201,r.text
    assert stored(f,p)['events'][:-1]==middle['events']
    for adapter in ('P2','P3','P4','P5'):verified(f,p,adapter)
    assert get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert stored(f,p)['steps'][0]==middle['steps'][0]


def test_review_withdraw_after_success_keeps_original_read_only_receipt(http_f):
    f=http_f;p,*_=complete(f,local=True);card=changed(f,p);a=preview(f,p,card).json();key=uuid4().hex
    assert adopt(f,p,a['adoption'],key).status_code==201
    current=opportunities(f,p).json();card=current['cards'][0]
    assert post(f,p,body(current,'WITHDRAW',card=card)).status_code==200
    before=snapshot(f)
    r=recover(f,p,key);assert r.status_code==200,r.text
    assert r.json()['status']=='COMMITTED' and r.json()['historical_only']
    assert preview(f,p,card).status_code==409
    assert adopt(f,p,a['adoption']).status_code==409
    assert snapshot(f)==before


def test_review_actual_resource_rewrite_between_builds_denies_atomic_write(http_f,monkeypatch):
    f=http_f;p,*_=complete(f,local=True);card=changed(f,p);a=preview(f,p,card).json();before=snapshot(f)
    original=sca.build;calls=[]
    def rewritten(*args,**kwargs):
        result=original(*args,**kwargs);calls.append(1)
        if len(calls)==1:
            with f[1].connect() as c:
                c.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=(SELECT id FROM synthetic_resources ORDER BY id LIMIT 1)')
        return result
    monkeypatch.setattr(sca,'build',rewritten)
    r=adopt(f,p,a['adoption']);assert r.status_code==409,r.text
    after=snapshot(f)
    assert len(calls)==2 and after['synthetic_resources']!=before['synthetic_resources']
    assert {k:v for k,v in after.items() if k!='synthetic_resources'}=={k:v for k,v in before.items() if k!='synthetic_resources'}


def test_review_preview_read_with_revoked_execute_is_nonwritable(http_f):
    f=http_f;p,*_=complete(f,local=True);card=changed(f,p)
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    before=snapshot(f);r=preview(f,p,card);assert r.status_code==200,r.text
    assert not r.json()['can_adopt'] and 'CURRENT_EXECUTE_REQUIRED' in r.json()['blocking_reasons']
    assert adopt(f,p,r.json()['adoption']).status_code==403
    assert snapshot(f)==before

from test_template_upgrade import upgrade_case,publication
from test_template_structure_independent import complete_declared,admit as structural_admit,apply as structural_apply,SIX_GOALS

@pytest.mark.parametrize('source_first',[True,False])
def test_review_source_proof_and_template_structure_journals_remain_composable(upgrade_case,source_first):
    u=upgrade_case;row,_,p=complete_declared(u);f=(*u['f'][:3],u['client'])
    original=deepcopy(stored(f,p));source_key=uuid4().hex
    def source_revision():
        card=changed(f,p);v=preview(f,p,card);assert v.status_code==200,v.text
        assert v.json()['can_adopt'],v.text
        r=adopt(f,p,v.json()['adoption'],source_key);assert r.status_code==201,r.text
        for adapter in ('P2','P3','P4','P5'):verified(f,p,adapter)
    def structure_revision():
        target=publication(u,SIX_GOALS,source='1',name='Synthetic explicit structural strengthening')
        _,data=structural_admit(u,row,target)
        r=structural_apply(u,row,data);assert r.status_code==200,r.text
        for adapter in ('P4','P5'):verified(f,p,adapter)
    if source_first:source_revision();structure_revision()
    else:structure_revision();source_revision()
    current=stored(f,p)
    assert current['id']==original['id'] and current['required_goals']==SIX_GOALS
    assert [s['id'] for s in current['steps']]==[s['id'] for s in original['steps']]
    assert current['events'][:len(original['events'])]==original['events']
    assert read(f,p).status_code==200 and get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert recover(f,p,source_key).json()['status']=='COMMITTED'


def test_review_legacy_opportunity_recovery_route_key_preserved(http_f):
    f=http_f;p=setup(f,GOALS[0]);key='plan-revision'
    r=post(f,p,body(opportunities(f,p).json()),key=key)
    assert r.status_code==200,r.text
    r=f[3].get('/api/preparations/'+p['preparation_id']+'/opportunities/recovery/'+key,headers=headers(f[2]))
    assert r.status_code==200,r.text
    assert r.json()['status']=='COMMITTED'
