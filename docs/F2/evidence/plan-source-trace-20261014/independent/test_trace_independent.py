from conftest import pg,fixture
from test_preparation import preparation_fixture,headers,add
from test_service_plan_candidates import setup,GOAL,generate,adopt,adoption
from test_plan_preview import digest
from test_request_intents import save
from parkweave import controlled_plans as cp,service_case_steps as steps,service_plan_candidates as candidates
from psycopg.types.json import Jsonb
from pathlib import Path
from datetime import timedelta
from copy import deepcopy
import pytest,json

OUT=Path('.runtime/plan-source-trace-20261014/independent')

def overview(f,p):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]))

def test_independent_trace_full_public_snapshot_and_goal_hashes(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL,'SYNTHETIC_TRACE_UNSUPPORTED']);v=generate(f,p).json();assert adopt(f,p,v).status_code==201
    def snapshot():
        with f[1].connect() as c:
            tables=[x['tablename'] for x in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename!='authorization_audit' ORDER BY tablename")]
            return {t:c.execute('SELECT * FROM "'+t+'" ORDER BY 1').fetchall() for t in tables}
    before=snapshot();r=overview(f,p);assert r.status_code==200;view=r.json();trace=view['source_trace']
    assert snapshot()==before and len(before)==45
    assert cp._hash({k:x for k,x in trace.items() if k!='trace_sha256'})==trace['trace_sha256']
    assert trace['required_goals']==[GOAL,'SYNTHETIC_TRACE_UNSUPPORTED']
    for goal in view['results']:
        assert goal['adoption_trace_sha256']==trace['trace_sha256']
        assert cp._hash({k:x for k,x in goal.items() if k!='result_sha256'})==goal['result_sha256']
    with f[1].connect() as c:audit_count=c.execute('SELECT count(*) AS n FROM authorization_audit').fetchone()['n']
    (OUT/'trace-full-snapshot.json').write_text(json.dumps({'public_tables_compared':list(before),'count':45,'all_columns_unchanged':True,'audit_separate':True,'audit_rows':audit_count,'trace_hash_verified':True,'per_goal_result_and_trace_hashes_verified':True})+'\n')

def test_independent_owner_READ_trace_survives_EXECUTE_revoke(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();assert adopt(f,p,v).status_code==201;trace=overview(f,p).json()['source_trace']
    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    before=digest(f);r=overview(f,p);assert r.status_code==200 and r.json()['source_trace']==trace
    assert not trace['execution_enabled'] and not trace['new_grants'] and not trace['case_goal_completed']
    assert digest(f)==before

@pytest.mark.parametrize('bad',['candidate_metadata_missing','historical_time_outside_window','adoption_request_missing'])
def test_independent_trace_cannot_bypass_original_candidate_proof(preparation_fixture,bad):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();assert adopt(f,p,v).status_code==201
    with f[1].connect() as c:
        parent=c.execute('SELECT service_case_plan,planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone();plan=parent['service_case_plan'];records=parent['planning_previews']
        if bad=='candidate_metadata_missing':records=[]
        elif bad=='adoption_request_missing':plan.pop('adoption_request')
        else:
            plan['candidate_consumption']['accepted_at']=v['validity']['expires_at']
            plan['events'][0]['candidate_consumption_sha256']=cp._hash(plan['candidate_consumption'])
        c.execute('UPDATE preparations SET service_case_plan=%s,planning_previews=%s WHERE id=%s',(Jsonb(plan),Jsonb(records),p['preparation_id']))
    before=digest(f);assert overview(f,p).status_code==409 and digest(f)==before

def test_independent_trace_is_historic_not_current_material_eligibility(preparation_fixture,monkeypatch):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();assert adopt(f,p,v).status_code==201;original=overview(f,p).json()['source_trace']
    assert add(f,p).status_code==200
    monkeypatch.setattr(candidates,'clock',lambda c:candidates._time(v['validity']['expires_at'])+timedelta(days=1))
    before=digest(f);r=overview(f,p);assert r.status_code==200 and r.json()['source_trace']==original
    assert r.json()['preparation_revision']>original['adoption']['preparation_revision'] and r.json()['state']!='LOCAL_OUTPUTS_VERIFIED'
    assert digest(f)==before

def test_independent_plain_replacement_does_not_claim_old_candidate_origin(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();assert adopt(f,p,v).status_code==201;old=overview(f,p).json()['source_trace']
    assert save(f,p,goals=[GOAL,'SYNTHETIC_TRACE_REPLACEMENT_GOAL']).status_code==200;v2=generate(f,p).json();data=adoption(f,p,v2)
    for key in ('candidate_id','expected_candidate_sha256','expected_verification_sha256'):data.pop(key)
    assert adopt(f,p,v2,data=data).status_code==201;before=digest(f);view=overview(f,p).json();trace=view['source_trace']
    assert trace['plan_id']!=old['plan_id'] and trace['candidate'] is None and trace['origin']=='ORIGINAL_REGISTERED_DETERMINISTIC_PLAN'
    assert view['historical_plans'][0]['id']==old['plan_id'] and digest(f)==before

def test_independent_original_V1_trace_without_invented_clock(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();data=adoption(f,p,v)
    with f[1].connect() as c:
        records=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews'];records[0].pop('validity');records[0]['document'].pop('candidate_validity')
        c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(records),p['preparation_id']))
    basis={k:v[k] for k in ('validator_version','validated_contract_sha256','candidate_id','candidate_sha256','current_source_sha256','state','preparation_id','case_id','run_id','preparation_revision','request_revision','catalog_sha256','registry_sha256')};basis['validator_version']=1;data['expected_verification_sha256']=cp._hash(basis)
    plain={k:x for k,x in data.items() if k not in ('candidate_id','expected_candidate_sha256','expected_verification_sha256')};assert adopt(f,p,v,'ind-v1-trace',plain).status_code==201
    with f[1].connect() as c:
        plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'];plan['adoption_request']=data
        plan['candidate_consumption']=dict(candidate_id=v['candidate_id'],candidate_sha256=v['candidate_sha256'],verification_sha256=data['expected_verification_sha256'],origin=candidates.ORIGIN,verification_basis=basis)
        plan['events'][0]['fingerprint']=cp._hash(dict(preparation_id=p['preparation_id'],action='ADOPT',**steps._adopt_request(steps.Adopt.model_validate(data))))
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=digest(f);r=overview(f,p);assert r.status_code==200;trace=r.json()['source_trace'];assert trace['candidate']['validator_version']==1 and trace['candidate']['accepted_at'] is None and trace['candidate']['validity'] is None
    assert digest(f)==before
