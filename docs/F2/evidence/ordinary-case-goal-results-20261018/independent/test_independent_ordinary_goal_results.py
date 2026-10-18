"""Literal counterexamples for ordinary P3/P4 source admission; private only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import json,os,time
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from parkweave import case_step_assignments as cs,resource_combinations as rc
from parkweave.api import configured_app,create_app
from parkweave.store import Store,Denied
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture,act
from test_case_step_assignments import ok
from test_ordinary_case_goal_results import start,acceptance,finish,results
from test_service_case_steps import GOALS,read,verified,step,command,business
from ordinary_case_step_support import ordinary_api
from service_release_acceptance_support import authority_snapshot

OUT=Path(os.environ['PARKWEAVE_INDEPENDENT_GOAL_RESULTS_EVIDENCE'])
CONFIGS=('PARKWEAVE_RUNTIME_READ_CONFIG','PARKWEAVE_RUNTIME_WRITE_CONFIG','PARKWEAVE_SERVICE_PROFILE','PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG','PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG','PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG')
def record(name,data):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/(name+'.json')).write_text(json.dumps(data,sort_keys=True,indent=2,default=str)+'\n')
@pytest.fixture
def owned_normal(receipt_fixture,monkeypatch):
    f=receipt_fixture
    # Original owned fixture prepares existing resources/rights before app boot;
    # no positive authority mutation occurs while the ordinary application runs.
    rc.seed_synthetic(f[1]);baseline=authority_snapshot(f[1])
    for key in CONFIGS:monkeypatch.delenv(key,raising=False)
    monkeypatch.setenv('PARKWEAVE_DSN',f[0].dsn);monkeypatch.setenv('PARKWEAVE_MODE','LOCAL')
    monkeypatch.setenv('PARKWEAVE_CASE_STEP_MODE',cs.ORDINARY_MODE)
    with TestClient(configured_app()) as api:yield (*f[:3],api),baseline

def test_p1_p2_only_result_does_not_inherit_unrelated_offer_deadline(owned_normal,monkeypatch):
    from parkweave import case_goal_results as goals
    f,baseline=owned_normal
    monkeypatch.setattr(cs._OrdinaryCaseStep,'_offer_deadline',lambda self,c:cs._now(c)+timedelta(seconds=18))
    p=start(f,GOALS[:2]);d,_=acceptance(f,p)
    initial=ok(results(f,p));assert initial['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert [r['adapter_id'] for r in initial['results']]==['P1','P2']
    before=business(f);original=goals.outputs
    query="SELECT id FROM operations WHERE run_id=%s AND action='case.create' FOR SHARE /* independent_p1_p2_last_wait */"
    def after_outputs(*args,**kwargs):
        value=original(*args,**kwargs);args[1].execute(query,(p['run_id'],)).fetchone();return value
    monkeypatch.setattr(goals,'outputs',after_outputs)
    with f[1].connect() as c:
        remaining=c.execute('SELECT %s::timestamptz-clock_timestamp() remaining',(d['assignment_valid_until'],)).fetchone()['remaining'].total_seconds()
    assert remaining>2;time.sleep(remaining-1.5)
    with f[1].connect() as lock:
        lock.execute("SELECT id FROM operations WHERE run_id=%s AND action='case.create' FOR UPDATE",(p['run_id'],))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(results,f,p);observed=False
            for _ in range(100):
                with f[1].connect() as c:
                    observed=bool(c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT id FROM operations%%independent_p1_p2_last_wait%%'").fetchone())
                if observed:break
                if future.done():future.result()
                time.sleep(.01)
            assert observed
            with f[1].connect() as c:
                remaining=c.execute('SELECT %s::timestamptz-clock_timestamp() remaining',(d['assignment_valid_until'],)).fetchone()['remaining'].total_seconds()
            assert 0<remaining<1.6;time.sleep(remaining+.10);lock.commit();response=future.result(timeout=8)
    monkeypatch.setattr(goals,'outputs',original)
    fresh=results(f,p)
    record('p1-p2-only-deadline',dict(actual_pg_wait=observed,original_deadline=d['assignment_valid_until'],initial=initial,late_status=response.status_code,late_body=response.json(),fresh_status=fresh.status_code,fresh_body=fresh.json(),business_before=before,business_after=business(f),authority_unchanged=authority_snapshot(f[1])==baseline))
    # Only P1/P2 are actual adopted/required outputs. Their currentness is
    # independent of the unrelated accepted CaseStep's deadline.
    x=ok(response);assert x['state']=='LOCAL_OUTPUTS_VERIFIED' and x['results']==initial['results']
    assert ok(fresh)['state']=='LOCAL_OUTPUTS_VERIFIED' and business(f)==before and authority_snapshot(f[1])==baseline


def test_manual_correction_history_current_v2_and_cold_source_hash(owned_normal):
    f,baseline=owned_normal;p=start(f);d,r=acceptance(f,p);verified(f,p,'P3')
    r=ok(act(f,r,'SUBMIT',text='SYNTHETIC PRIVATE_OLD_RECEIPT_1'));first=r['current_receipt']
    r=ok(act(f,r,'REQUEST_CHANGES'))
    r=ok(act(f,r,'SUBMIT',text='SYNTHETIC PRIVATE_CURRENT_RECEIPT_2'));r=ok(act(f,r,'ACKNOWLEDGE'))
    current_plan=verified(f,p,'P4');expected=ok(results(f,p));before=business(f)
    out=expected['results'][3]['actual_output'];assert out['receipt_version']==2 and out['receipt_id']==r['current_receipt']['id'] and out['receipt_sha256']==r['current_receipt']['source_sha256'] and out['receipt_id']!=first['id']
    assert expected['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert all(secret not in json.dumps(expected) for secret in ('PRIVATE_OLD_RECEIPT_1','PRIVATE_CURRENT_RECEIPT_2','PRIVATE_MATERIAL','PRIVATE_OUTLINE'))
    assert expected['original_request'].startswith('PRIVATE_REQUEST_')  # Owner original request is an allowed field.
    with ordinary_api(f,OUT/'correction-cold') as api:
        cold=(*f[:3],api);assert ok(results(cold,p))==expected
        snapshot=ok(read(cold,p));assert step(snapshot,'P3')['verified_sha256']==step(current_plan,'P3')['verified_sha256']
    assert business(f)==before and authority_snapshot(f[1])==baseline
    record('correction-cold',dict(dispatch_id=d['dispatch_id'],deadline=d['assignment_valid_until'],current_result=expected,business_unchanged=True,authority_unchanged=True))


def test_forged_verify_field_cannot_become_ordinary_goal_proof(owned_normal):
    f,baseline=owned_normal;p=start(f);finish(f,p);old=ok(results(f,p));before=business(f)
    with f[1].connect() as c:
        plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
        p4=next(s for s in plan['steps'] if s['adapter_id']=='P4')
        event=next(e for e in reversed(plan['events']) if e['action']=='VERIFY' and e['step_id']==p4['id'])
        event['actor_id']='prep-specialist-fixture-a'
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    # Existing source and verified_sha256 still exist. Only the exact owner
    # VERIFY event proof is falsified in this negative fixture.
    with ordinary_api(f,OUT/'false-verify-cold') as api:
        response=results((*f[:3],api),p)
        assert response.status_code in (200,403,409) and response.status_code!=500
        if response.status_code==200:
            value=response.json();assert value['state']!='LOCAL_OUTPUTS_VERIFIED'
            row=value['results'][3];assert row['state']!='LOCAL_OUTPUT_VERIFIED' and row['historical_verification'] is None
        else:value=response.json()
    assert business(f)==before and authority_snapshot(f[1])==baseline
    record('forged-owner-verify',dict(original_verification=old['results'][3]['historical_verification'],status=response.status_code,response=value,authority_unchanged=True))


def test_cold_execute_revoke_preserves_history_without_current_source_or_verify(owned_normal):
    f,_=owned_normal;p=start(f);finish(f,p);old=ok(results(f,p))
    with f[1].connect() as c:
        c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    after_negative=authority_snapshot(f[1]);before=business(f)
    with ordinary_api(f,OUT/'execute-revoked-cold') as api:
        cold=(*f[:3],api);now=ok(results(cold,p))
        assert now['state']=='UNVERIFIED' and now['current_required_goals']==old['current_required_goals']
        for i in (2,3):
            assert now['results'][i]['historical_verification']['id']==old['results'][i]['historical_verification']['id']
            assert not now['results'][i]['historical_verification']['current'] and now['results'][i]['actual_output'] is None
        ok(command(cold,p,'P3'),403)
        ok(api.get('/api/runs/'+p['run_id'],headers=headers(f[2],'executor-a')),403)
    assert business(f)==before and authority_snapshot(f[1])==after_negative
    record('execute-revoke-cold',dict(result=now,business_unchanged=True,authority_unchanged_after_negative=True))


def test_explicit_store_binding_never_leaks_to_default_or_p5(owned_normal):
    f,baseline=owned_normal;p=start(f,GOALS);finish(f,p);before=business(f)
    value=ok(results(f,p));assert value['state']=='UNVERIFIED' and [r['state'] for r in value['results'][:4]]==['LOCAL_OUTPUT_VERIFIED']*4
    assert value['results'][4]['adapter_id']=='P5' and value['results'][4]['state']!='LOCAL_OUTPUT_VERIFIED'
    ok(command(f,p,'P5'),409)
    body=dict(action='REVALIDATE',expected_revision=0,expected_cycle=1,reason='SYNTHETIC must not inherit ordinary P3 proof')
    ok(f[3].post('/api/preparations/'+p['preparation_id']+'/local-case/commands',headers=headers(f[2],key=uuid4().hex),json=body),403)
    # Same Store cannot silently create an unconfigured app after explicit bind;
    # fresh unbound Store does not discover ordinary permissions from its marker.
    bound=f[3].app.state.store if hasattr(f[3].app.state,'store') else None
    from parkweave.ordinary_plan_sources import selected
    assert selected(f[0]) is None
    with TestClient(create_app(Store(f[0].dsn))) as default:
        cold=(*f[:3],default);ok(results(cold,p),403);ok(read(cold,p),403)
    with f[1].connect() as c:assert not c.execute('SELECT 1 FROM case_local_lifecycles').fetchone() and not c.execute('SELECT 1 FROM run_assignments').fetchone()
    assert business(f)==before and authority_snapshot(f[1])==baseline
    record('default-p5',dict(result=value,p5_unverified=True,default_ordinary_marker_refused=True,authority_unchanged=True))
