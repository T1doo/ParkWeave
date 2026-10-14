"""Owned PG/ASGI candidate lifetime; fixture ageing and clock faults are explicit."""
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
import time
from concurrent.futures import ThreadPoolExecutor
from psycopg.types.json import Jsonb
import pytest
from test_preparation import preparation_fixture,headers,add
from test_bounded_planning import setup
from test_plan_preview import digest
from test_service_plan_candidates import generate,preview,adopt,adoption,path,GOAL
from parkweave import service_plan_candidates as candidates,service_case_steps as steps,controlled_plans as cp


def age_unconsumed_fixture(f,p,remaining):
    # Only this unconsumed owned fixture; original request/document proof stays
    # consistent. This accelerates the 900 second window, never alters a real plan.
    with f[1].connect() as c:
        records=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews']
        end=candidates.clock(c)+timedelta(seconds=remaining)
        w=dict(version=2,created_at=(end-timedelta(seconds=900)).isoformat(),expires_at=end.isoformat(),seconds=900)
        records[-1]['validity']=w;records[-1]['document']['candidate_validity']=deepcopy(w)
        c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(records),p['preparation_id']))


def recover(f,p,key):return f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan/command-recovery',headers=headers(f[2],key=key))


def test_expired_original_key_never_renews_or_changes_business(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);key=uuid4().hex;v=generate(f,p,key).json()
    assert v['validator_version']==2 and v['validity']['seconds']==900
    age_unconsumed_fixture(f,p,-1);before=digest(f);v=preview(f,p,v['candidate_id']).json()
    assert v['state']=='EXPIRED' and not v['can_adopt'] and v['graph_comparison']=='UNCHANGED'
    assert adopt(f,p,v).status_code==409
    r=f[3].get(path(p)+'/recovery',headers=headers(f[2],key=key))
    assert r.status_code==200 and r.json()['status']=='COMMITTED' and r.json()['items'][0]['state']=='EXPIRED'
    data=dict(expected_preparation_revision=v['preparation_revision'],expected_source_sha256=v['current_source_sha256'])
    replay=generate(f,p,key,data).json();assert replay['validity']==v['validity'] and replay['candidate_id']==v['candidate_id']
    assert digest(f)==before
    new=generate(f,p).json();assert new['state']=='VERIFIED_STRUCTURE_ONLY' and new['candidate_id']!=v['candidate_id']


def test_server_clock_rollback_fails_closed(preparation_fixture,monkeypatch):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();before=digest(f)
    monkeypatch.setattr(candidates,'clock',lambda c:candidates._time(v['validity']['created_at'])-timedelta(microseconds=1))
    assert preview(f,p,v['candidate_id']).json()['state']=='CLOCK_UNCERTAIN'
    assert adopt(f,p,v).status_code==409;assert digest(f)==before


def test_actual_pg_wait_crosses_fixture_deadline_and_rejects_adopt(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();age_unconsumed_fixture(f,p,1)
    v=preview(f,p,v['candidate_id']).json();assert v['state']=='VERIFIED_STRUCTURE_ONLY';data=adoption(f,p,v);before=digest(f)
    with f[1].connect() as c,ThreadPoolExecutor(max_workers=1) as pool:
        c.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],))
        future=pool.submit(lambda:adopt(f,p,v,data=data));waits=[];end=time.monotonic()+10
        while time.monotonic()<end:
            with f[1].connect() as observer:
                waits=observer.execute("SELECT pid FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE '%%preparations%%FOR UPDATE%%'").fetchall()
            if waits:break
            time.sleep(.01)
        assert waits,'real owned PostgreSQL parent lock wait missing'
        while candidates.clock(c)<candidates._time(v['validity']['expires_at']):time.sleep(.01)
        c.commit();r=future.result(timeout=15);assert r.status_code==409,r.text
    assert digest(f)==before


def test_expiry_after_final_authority_recheck_rolls_back_original_event(preparation_fixture,monkeypatch):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();data=adoption(f,p,v);before=digest(f)
    original=steps._context;expired=False;calls=0;clock=candidates.clock
    def context(*a,**k):
        nonlocal expired,calls
        result=original(*a,**k);calls+=1
        if calls==2:expired=True
        return result
    monkeypatch.setattr(steps,'_context',context)
    monkeypatch.setattr(candidates,'clock',lambda c:candidates._time(v['validity']['expires_at']) if expired else clock(c))
    assert adopt(f,p,v,data=data).status_code==409;assert calls==2 and digest(f)==before


def test_adopted_plan_cold_original_key_survives_expiry_and_material_change(preparation_fixture,monkeypatch):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();key=uuid4().hex;data=adoption(f,p,v);r=adopt(f,p,v,key,data);assert r.status_code==201,r.text
    plan=r.json()['plan_id'];proof=r.json()['candidate_consumption'];assert proof['accepted_at']<v['validity']['expires_at']
    # Explicit future-clock fault only for live eligibility; stored historic
    # accepted_at is never rewritten or checked against the present clock.
    monkeypatch.setattr(candidates,'clock',lambda c:candidates._time(v['validity']['expires_at']))
    before=digest(f);assert preview(f,p,v['candidate_id']).json()['state']=='EXPIRED'
    current=f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2]))
    assert current.status_code==200 and current.json()['plan_id']==plan and current.json()['candidate_consumption']==proof
    assert recover(f,p,key).json()['status']=='COMMITTED' and adopt(f,p,v,key,data).status_code==201
    assert digest(f)==before
    assert add(f,p).status_code==200;before=digest(f);r=recover(f,p,key)
    assert r.status_code==200 and r.json()['event']['plan_id']==plan and digest(f)==before


@pytest.mark.parametrize('change',['clock','event_digest','validity','missing_validity'])
def test_candidate_historical_time_proof_cannot_be_forged(preparation_fixture,change):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();key=uuid4().hex;data=adoption(f,p,v);assert adopt(f,p,v,key,data).status_code==201
    with f[1].connect() as c:
        row=c.execute('SELECT planning_previews,service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone();plan=row['service_case_plan'];records=row['planning_previews']
        if change=='clock':plan['candidate_consumption']['accepted_at']=v['validity']['expires_at']
        elif change=='event_digest':plan['events'][0]['candidate_consumption_sha256']='0'*64
        elif change=='validity':records[0]['validity']['seconds']=True
        else:records[0].pop('validity')
        c.execute('UPDATE preparations SET planning_previews=%s,service_case_plan=%s WHERE id=%s',(Jsonb(records),Jsonb(plan),p['preparation_id']))
    before=digest(f);assert recover(f,p,key).status_code==409 and adopt(f,p,v,key,data).status_code==409;assert digest(f)==before


@pytest.mark.parametrize('change',['material','catalog','registry'])
def test_source_change_does_not_invent_different_dependency_graph(preparation_fixture,change,monkeypatch):
    from parkweave import bounded_planning as bp
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();data=adoption(f,p,v)
    if change=='material':assert add(f,p).status_code==200
    elif change=='catalog':
        with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=source||'{\"revision\":\"2\"}'::jsonb")
    else:
        registry=deepcopy(bp.REGISTRY);registry[0]['acceptance']='SYNTHETIC changed registry contract';monkeypatch.setattr(bp,'REGISTRY',registry)
    before=digest(f);r=preview(f,p,v['candidate_id']);assert r.status_code==200,r.text
    assert r.json()['state']=='STALE' and r.json()['graph_comparison']=='UNCHANGED' and not r.json()['can_adopt']
    assert adopt(f,p,v,data=data).status_code==409 and digest(f)==before


def test_v1_history_remains_readable_without_inventing_old_expiry(preparation_fixture):
    # Reconstruct the exact preceding V1 persisted format in this owned fixture.
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json()
    with f[1].connect() as c:
        records=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews'];record=records[0]
        record.pop('validity');record['document'].pop('candidate_validity')
        c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(records),p['preparation_id']))
    assert preview(f,p,v['candidate_id']).json()['state']=='LEGACY_REVALIDATION_REQUIRED'
    with f[1].connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
        v1=candidates.verify(parent,record,record['document'],historical=True)
    data=adoption(f,p,v1);key=uuid4().hex
    plain={k:x for k,x in data.items() if k not in ('candidate_id','expected_candidate_sha256','expected_verification_sha256')}
    assert adopt(f,p,v1,key,plain).status_code==201
    with f[1].connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone();plan=parent['service_case_plan']
        request=steps.Adopt.model_validate(data);plan['adoption_request']=data
        plan['candidate_consumption']=candidates.consume(parent,plan['adoption_preview'],request,historical=True)
        plan['events'][0]['fingerprint']=cp._hash(dict(preparation_id=p['preparation_id'],action='ADOPT',**steps._adopt_request(request)))
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=digest(f);r=recover(f,p,key);assert r.status_code==200,r.text
    assert r.json()['status']=='COMMITTED' and adopt(f,p,v1,key,data).status_code==201 and digest(f)==before
    assert adopt(f,p,v1,data=data).status_code==409
