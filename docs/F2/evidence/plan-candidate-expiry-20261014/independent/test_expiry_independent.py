from conftest import pg,fixture
from test_preparation import preparation_fixture,headers
from test_service_plan_candidates import setup,GOAL,generate,preview,adopt,adoption,path
from test_plan_preview import digest
from test_request_intents import save
from parkweave import service_plan_candidates as candidates,service_case_steps as steps,controlled_plans as cp
from psycopg.types.json import Jsonb
from copy import deepcopy
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest,time,json

OUT=Path('.runtime/plan-candidate-expiry-20261014/independent')

def recovery(f,p,key):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan/command-recovery',headers=headers(f[2],key=key))

@pytest.mark.parametrize('offset,state',[(-1,'CLOCK_UNCERTAIN'),(0,'VERIFIED_STRUCTURE_ONLY'),(900,'EXPIRED')])
def test_independent_half_open_server_window(preparation_fixture,monkeypatch,offset,state):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json()
    now=candidates._time(v['validity']['created_at'])+timedelta(seconds=offset)
    monkeypatch.setattr(candidates,'clock',lambda c:now)
    before=digest(f);r=preview(f,p,v['candidate_id']);assert r.status_code==200
    assert r.json()['state']==state and r.json()['can_adopt']==(state=='VERIFIED_STRUCTURE_ONLY')
    if state!='VERIFIED_STRUCTURE_ONLY':assert adopt(f,p,v).status_code==409
    assert digest(f)==before

def test_independent_actual_pg_blocker_crosses_deadline(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json()
    with f[1].connect() as holder:
        records=holder.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews']
        end=candidates.clock(holder)+timedelta(seconds=2)
        w=dict(version=2,created_at=(end-timedelta(seconds=900)).isoformat(),expires_at=end.isoformat(),seconds=900)
        records[0]['validity']=w;records[0]['document']['candidate_validity']=deepcopy(w)
        holder.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(records),p['preparation_id']))
    v=preview(f,p,v['candidate_id']).json();assert v['state']=='VERIFIED_STRUCTURE_ONLY';data=adoption(f,p,v);before=digest(f)
    with ThreadPoolExecutor(1) as pool:
        with f[1].connect() as holder:
            holder.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],))
            pid=holder.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            pending=pool.submit(adopt,f,p,v,'ind-expiry-wait',data);seen=False;limit=time.monotonic()+5
            with f[1].connect() as monitor:
                while time.monotonic()<limit:
                    monitor.execute('SELECT pg_stat_clear_snapshot()')
                    seen=monitor.execute('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND %s=ANY(pg_blocking_pids(pid))) AS yes',(pid,)).fetchone()['yes']
                    if seen:break
                    time.sleep(.01)
            assert seen
            while candidates.clock(holder)<end:time.sleep(.01)
        r=pending.result(timeout=10);assert r.status_code==409
    assert digest(f)==before
    (OUT/'pg-deadline-wait.json').write_text(json.dumps({'actual_pg_blocking_pid_observed':seen,'fixture_deadline_accelerated_seconds':2,'clock':'real PG clock_timestamp','response':409,'business_snapshot_unchanged':True})+'\n')

def test_independent_second_consume_uses_final_clock(preparation_fixture,monkeypatch):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();before=digest(f);original=candidates.clock;calls=0
    def clock(c):
        nonlocal calls
        calls+=1
        return candidates._time(v['validity']['expires_at']) if calls==2 else original(c)
    monkeypatch.setattr(candidates,'clock',clock)
    assert adopt(f,p,v).status_code==409 and calls==2 and digest(f)==before

def test_independent_expired_key_replay_does_not_mint_metadata(preparation_fixture,monkeypatch):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p,'ind-expired-key').json()
    data=dict(expected_preparation_revision=v['preparation_revision'],expected_source_sha256=v['current_source_sha256'])
    monkeypatch.setattr(candidates,'clock',lambda c:candidates._time(v['validity']['expires_at']))
    before=digest(f);replay=generate(f,p,'ind-expired-key',data);assert replay.status_code==201
    assert replay.json()['candidate_id']==v['candidate_id'] and replay.json()['validity']==v['validity'] and replay.json()['state']=='EXPIRED'
    r=f[3].get(path(p)+'/recovery',headers=headers(f[2],key='ind-expired-key'))
    assert r.json()['status']=='COMMITTED' and r.json()['items'][0]['state']=='EXPIRED'
    assert generate(f,p,'ind-expired-key',{**data,'expected_preparation_revision':data['expected_preparation_revision']+1}).status_code==409
    assert digest(f)==before

@pytest.mark.parametrize('bad',['accepted_at_start_minus_tick','accepted_at_expiry','event_digest_missing'])
def test_independent_historical_clock_and_event_binding(preparation_fixture,bad):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();d=adoption(f,p,v);assert adopt(f,p,v,'ind-history-proof',d).status_code==201
    with f[1].connect() as c:
        plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
        if bad=='event_digest_missing':plan['events'][0].pop('candidate_consumption_sha256')
        else:
            plan['candidate_consumption']['accepted_at']=(candidates._time(v['validity']['created_at'])-timedelta(microseconds=1)).isoformat() if bad=='accepted_at_start_minus_tick' else v['validity']['expires_at']
            # Recomputed digest alone cannot make an out-of-window historic acceptance valid.
            plan['events'][0]['candidate_consumption_sha256']=cp._hash(plan['candidate_consumption'])
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=digest(f);assert recovery(f,p,'ind-history-proof').status_code==409
    assert adopt(f,p,v,'ind-history-proof',d).status_code==409
    assert f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2])).status_code==409
    assert digest(f)==before

def test_independent_v1_receipt_exact_old_basis_without_expiry(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);v=generate(f,p).json();d=adoption(f,p,v)
    with f[1].connect() as c:
        records=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews']
        records[0].pop('validity');records[0]['document'].pop('candidate_validity')
        c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(records),p['preparation_id']))
    basis={k:v[k] for k in ('validator_version','validated_contract_sha256','candidate_id','candidate_sha256','current_source_sha256','state','preparation_id','case_id','run_id','preparation_revision','request_revision','catalog_sha256','registry_sha256')};basis['validator_version']=1
    d['expected_verification_sha256']=cp._hash(basis)
    plain={k:x for k,x in d.items() if k not in ('candidate_id','expected_candidate_sha256','expected_verification_sha256')}
    assert adopt(f,p,v,'ind-v1-receipt',plain).status_code==201
    with f[1].connect() as c:
        plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
        plan['adoption_request']=d
        plan['candidate_consumption']=dict(candidate_id=v['candidate_id'],candidate_sha256=v['candidate_sha256'],verification_sha256=d['expected_verification_sha256'],origin=candidates.ORIGIN,verification_basis=basis)
        plan['events'][0]['fingerprint']=cp._hash(dict(preparation_id=p['preparation_id'],action='ADOPT',**steps._adopt_request(steps.Adopt.model_validate(d))))
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=digest(f);assert preview(f,p,v['candidate_id']).json()['state']=='LEGACY_REVALIDATION_REQUIRED'
    assert recovery(f,p,'ind-v1-receipt').json()['status']=='COMMITTED'
    assert adopt(f,p,v,'ind-v1-receipt',d).status_code==201
    assert adopt(f,p,v,data=d).status_code==409 and digest(f)==before
