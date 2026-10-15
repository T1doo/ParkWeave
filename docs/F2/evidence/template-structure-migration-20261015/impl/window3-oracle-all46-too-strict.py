from copy import deepcopy
import pytest
from structure_impl_fixture import (private_fixture_sessions,upgrade_case,link_fixture,receipt_fixture,preparation_fixture,complete_declared,SIX_GOALS,GOALS,publication,check,choose,headers,goal_results,all_pg_rows)
from test_template_migration_independent import admit,stored,facts,recovery,verified,plan_read,plan_command


def send(u,row,data,key='structure-impl',**changes):
    body={**data,**changes}
    return u['client'].post('/api/template-upgrade/'+row['instance_id']+'/apply-structure',headers=headers(u['f'][2],key=key),json=body)


def body(u,row,target):
    v,data=admit(u,row,target)
    a=v['application']
    return v,{**data,'expected_structure_sha256':a['structure_sha256'],'confirm_structure_change':True}


@pytest.mark.parametrize('start,target_goals,affected',[(GOALS[:4],GOALS,['P5']),(GOALS[:4],GOALS[:4]+[SIX_GOALS[4]],['P4','P5']),([GOALS[0]],SIX_GOALS,['P2','P3','P4','P5'])])
def test_smoke_real_structure(upgrade_case,start,target_goals,affected):
    u=upgrade_case;row,old,p=complete_declared(u,start)
    before=deepcopy(stored(u,row));effects=facts(u)
    target=publication(u,target_goals,source='1')
    v,data=body(u,row,target)
    assert v['application']['eligible'],v
    ids={s['adapter_id']:s['id'] for s in before['steps']}
    assert v['application']['affected']==[ids[a] for a in affected]
    result=send(u,row,data)
    assert result.status_code==200,result.text
    saved=stored(u,row)
    assert saved['required_goals']==SIX_GOALS
    assert saved['events'][:-1]==before['events']
    assert saved['binding']==before['binding'] and saved['adoption_preview']==before['adoption_preview']
    assert result.json()['event']['template_upgrade']['source_changed'] is False
    current=plan_read(u['f'],p).json()
    assert [s['adapter_id'] for s in current['steps'] if s['state']!='VERIFIED']==affected
    for adapter in affected:verified(u['f'],p,adapter)
    assert goal_results(u,row)['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert facts(u)==effects
    assert recovery(u,row,'structure-impl').json()['status']=='COMMITTED'
    assert send(u,row,data).status_code==200


def test_smoke_preserved_lock_and_strict_true(upgrade_case):
    u=upgrade_case;row,old,p=complete_declared(u)
    current=plan_read(u['f'],p).json();s=current['steps'][0]
    assert plan_command(u['f'],p,'P1','LOCK',row=current,expected_source_sha256=s['source_sha256']).status_code==200
    target=publication(u,GOALS,source='1')
    v,data=body(u,row,target);assert v['application']['eligible'],v
    before=all_pg_rows(u)
    assert send(u,row,data,confirm_structure_change=1).status_code==422
    assert all_pg_rows(u)==before
    result=send(u,row,data);assert result.status_code==200,result.text
    verified(u['f'],p,'P5')
    assert goal_results(u,row)['state']=='LOCAL_OUTPUTS_VERIFIED'


def test_structure_version_bool_tamper_is_not_integer_one(upgrade_case):
    from psycopg.types.json import Jsonb
    u=upgrade_case;row,_,p=complete_declared(u)
    target=publication(u,GOALS,source='1')
    v,data=body(u,row,target);r=send(u,row,data)
    assert r.status_code==200,r.text
    saved=stored(u,row)
    saved['events'][-1]['template_upgrade']['structure_change']['version']=True
    with u['f'][1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(saved),row['preparation_id']))
    before=all_pg_rows(u)
    r=u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(u['f'][2]))
    assert r.status_code==409,r.text
    assert all_pg_rows(u)==before


@pytest.mark.parametrize('kind',['structure','source','description'])
def test_actual_update_before_commit_expiry_rolls_back(upgrade_case,monkeypatch,kind):
    from parkweave import service_case_steps as plans
    from datetime import datetime,timezone
    import json
    u=upgrade_case;row,_,p=complete_declared(u)
    target=publication(u,GOALS if kind=='structure' else GOALS[:4],source='2' if kind=='source' else '1',name='Synthetic after-update commit expiry')
    if kind=='structure':view,data=body(u,row,target)
    else:view,data=admit(u,row,target,'ACK_COMPATIBLE' if kind=='description' else 'REQUEST_RECHECK')
    assert view['application']['eligible'],view
    before=all_pg_rows(u);save=plans._save;observed=[]
    def expiry_after_actual_update(c,parent,plan):
        save(c,parent,plan)
        stored_row=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(parent['id'],)).fetchone()['service_case_plan']
        assert stored_row['events'][-1]['action']=='TEMPLATE_UPGRADE'
        observed.append(stored_row['events'][-1]['id'])
        u['engine'].clock=lambda:datetime(2100,1,1,tzinfo=timezone.utc)
    monkeypatch.setattr(plans,'_save',expiry_after_actual_update)
    if kind=='structure':response=send(u,row,data,'expire-before-commit')
    else:response=u['client'].post('/api/template-upgrade/'+row['instance_id']+'/apply',headers=headers(u['f'][2],key='expire-before-commit'),json=data)
    assert observed
    assert response.status_code in (403,409),response.text
    assert all_pg_rows(u)==before
    recovered=recovery(u,row,'expire-before-commit')
    assert recovered.status_code==200 and recovered.json()['status']=='NOT_OBSERVED',recovered.text
