"""Original owner goal overview traces only its actual persisted adoption."""
from copy import deepcopy
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from test_preparation import preparation_fixture,headers,add
from test_bounded_planning import setup
from test_plan_preview import digest
from test_service_plan_candidates import generate,adopt,adoption,GOAL
from parkweave import controlled_plans as cp,service_plan_candidates as candidates

def overview(f,p,user='fixture-a'):return f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2],user))

def test_original_adopted_candidate_trace_is_owner_scoped_and_readonly(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL,'SYNTHETIC_UNSUPPORTED_GOAL']);v=generate(f,p).json();r=adopt(f,p,v);assert r.status_code==201,r.text
    before=digest(f);r=overview(f,p);assert r.status_code==200,r.text;x=r.json();trace=x['source_trace']
    assert trace['plan_id']==x['plan_id'] and trace['plan_revision']==x['plan_revision']
    assert trace['required_goals']==[GOAL,'SYNTHETIC_UNSUPPORTED_GOAL'] and len(trace['steps'])==5
    assert trace['candidate']['candidate_id']==v['candidate_id'] and trace['candidate']['verification_sha256']==v['verification_sha256']
    assert trace['adoption']['source_sha256']==v['current_source_sha256'] and trace['origin']=='SYNTHETIC_UNTRUSTED_CANDIDATE'
    assert cp._hash({k:v for k,v in trace.items() if k!='trace_sha256'})==trace['trace_sha256']
    assert trace['read_only'] and not trace['execution_enabled'] and not trace['new_grants'] and not trace['case_goal_completed']
    assert all(row['adoption_trace_sha256']==trace['trace_sha256'] for row in x['results']) and digest(f)==before
    for user in ('fixture-b','fixture-c','prep-specialist-fixture-a'):assert overview(f,p,user).status_code==403

@pytest.mark.parametrize('damage',['consumption','both_removed','event_digest'])
def test_goal_overview_cannot_bypass_original_candidate_consumption_proof(preparation_fixture,damage):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();assert adopt(f,p,v).status_code==201
    with f[1].connect() as c:
        plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
        if damage=='consumption':plan['candidate_consumption']['verification_sha256']='0'*64
        elif damage=='event_digest':plan['events'][0]['candidate_consumption_sha256']='0'*64
        else:plan.pop('candidate_consumption');plan.pop('adoption_request')
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=digest(f);r=overview(f,p);assert r.status_code==409,r.text;assert digest(f)==before

def test_historical_adopted_trace_survives_live_candidate_expiry_and_material_change(preparation_fixture,monkeypatch):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();assert adopt(f,p,v).status_code==201;trace=overview(f,p).json()['source_trace']
    monkeypatch.setattr(candidates,'clock',lambda c:candidates._time(v['validity']['expires_at']))
    before=digest(f);assert overview(f,p).json()['source_trace']==trace and digest(f)==before
    assert add(f,p).status_code==200;before=digest(f);assert overview(f,p).json()['source_trace']==trace and digest(f)==before

def test_original_plan_without_candidate_trace_does_not_invent_generation(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);assert overview(f,p).json()['source_trace'] is None
    v=generate(f,p).json();data=adoption(f,p,v);data={k:x for k,x in data.items() if k not in ('candidate_id','expected_candidate_sha256','expected_verification_sha256')};assert adopt(f,p,v,data=data).status_code==201
    before=digest(f);trace=overview(f,p).json()['source_trace'];assert trace['origin']=='ORIGINAL_REGISTERED_DETERMINISTIC_PLAN' and trace['candidate'] is None;assert digest(f)==before

def test_new_plan_trace_keeps_old_candidate_and_history_separate(preparation_fixture):
    from test_request_intents import save
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();r=adopt(f,p,v);assert r.status_code==201;old=overview(f,p).json()['source_trace']
    assert save(f,p,goals=[GOAL,'SYNTHETIC_NEW_REQUIRED_GOAL']).status_code==200;new=generate(f,p).json();r=adopt(f,p,new);assert r.status_code==201,r.text
    before=digest(f);x=overview(f,p).json();trace=x['source_trace'];assert trace['plan_id']!=old['plan_id'] and trace['candidate']['candidate_id']==new['candidate_id'];assert x['historical_plans'][0]['id']==old['plan_id'] and trace['trace_sha256']!=old['trace_sha256'];assert digest(f)==before
