"""Existing ordinary CaseStep outputs feed original owner verification/pack.

All identities/resources/catalogs below belong to the owned synthetic fixture.
"""
from datetime import timedelta
from uuid import UUID,uuid4
import pytest
from fastapi.testclient import TestClient
from parkweave import case_step_assignments as cs,resource_combinations as rc
from parkweave.api import configured_app,create_app
from parkweave.store import Store,Denied
from test_preparation import preparation_fixture,headers,command as prep_command
from test_executor_receipts import receipt_fixture,act
from test_case_step_assignments import prepared,ok,REVIEWER
from test_ordinary_case_steps import ordinary
from test_request_intents import save
from test_case_resources import group,post as resource_link
from test_service_dispatches import offer,command as decision
from test_service_case_steps import GOALS,adopt,adopt_body,read,command,verified,step,business
from service_release_acceptance_support import authority_snapshot


@pytest.fixture
def ordinary_plan(ordinary):
    f,baseline=ordinary
    rc.seed_synthetic(f[1])
    return f,authority_snapshot(f[1])


def start(f,goals=GOALS[:4],*,partial=False):
    p=prepared(f)
    changed=ok(save(f,p,goals=goals,text='SYNTHETIC current ordinary outputs'))
    p={**p,'revision':changed['revision']}
    p=ok(prep_command(f,p,'REVIEW',REVIEWER,reason='SYNTHETIC exact goal review'))
    p=ok(prep_command(f,p,'CONFIRM',reason='SYNTHETIC current explicit owner confirmation'))
    ok(adopt(f,p,adopt_body(f,p,partial_adoption=True) if partial else None),201)
    return p


def acceptance(f,p):
    verified(f,p,'P1')
    ok(resource_link(f,p,group(f)),201)
    verified(f,p,'P2')
    d=ok(decision(f,ok(offer(f,p)[0],201),'ACCEPT'))
    return d,ok(f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')))


def finish(f,p):
    d,r=acceptance(f,p)
    verified(f,p,'P3')
    r=ok(act(f,r,'SUBMIT'));r=ok(act(f,r,'ACKNOWLEDGE'))
    verified(f,p,'P4')
    return d,r


def results(f,p,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2],user))


def test_ordinary_outputs_require_original_predecessors_and_explicit_owner_verification(ordinary_plan):
    f,baseline=ordinary_plan;p=start(f)
    initial=ok(read(f,p))
    assert 'EXISTING_RUN_ASSIGNMENT_REQUIRED' not in str(initial)
    assert step(initial,'P3')['state']!='VERIFIED'
    before=business(f)
    ok(command(f,p,'P3'),409);ok(offer(f,p)[0],409)
    assert business(f)==before
    d,r=acceptance(f,p)
    unverified=ok(results(f,p))
    assert unverified['results'][2]['state']=='AWAITING_OWNER_VERIFICATION'
    assert unverified['results'][2]['historical_verification'] is None
    assert unverified['results'][3]['state']=='WAITING_DEPENDENCY'
    verified(f,p,'P3');r=ok(act(f,r,'SUBMIT'));r=ok(act(f,r,'ACKNOWLEDGE'))
    assert ok(results(f,p))['results'][3]['state']=='AWAITING_OWNER_VERIFICATION'
    row=verified(f,p,'P4');after=business(f)
    current=ok(results(f,p))
    assert current['state']=='LOCAL_OUTPUTS_VERIFIED' and current['current_required_goals']==GOALS[:4]
    assert all(x['historical_verification']['current'] for x in current['results'])
    assert current['results'][2]['actual_output']['offer_id']==d['current_offer']['id']
    assert current['results'][3]['actual_output']['receipt_id']==r['current_receipt']['id']
    assert not current['case_goal_completed'] and not current['automatically_verified']
    assert business(f)==after and authority_snapshot(f[1])==baseline
    source=step(row,'P3')['verified_sources']['case_step_assignment']
    assert source['contract']==cs.ORDINARY_CONTRACT and source['current']
    assert source['marker']['valid_until']==d['assignment_valid_until']
    with f[1].connect() as c:assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
    with TestClient(configured_app()) as api:
        fresh=(*f[:3],api)
        assert ok(results(fresh,p))==current
    with TestClient(create_app(Store(f[0].dsn))) as api:
        legacy=(*f[:3],api);ok(read(legacy,p),403);ok(results(legacy,p),403)


@pytest.mark.parametrize('user',[REVIEWER,'executor-a','unassigned','fixture-b','fixture-c'])
def test_ordinary_results_never_expand_owner_or_run_scope(ordinary_plan,user):
    f,_=ordinary_plan;p=start(f);finish(f,p)
    before=business(f);ok(results(f,p,user),403)
    if user in ('executor-a','unassigned','fixture-b','fixture-c'):ok(read(f,p,user),403)
    ok(f[3].get('/api/runs/'+p['run_id'],headers=headers(f[2],'executor-a')),403)
    assert business(f)==before


@pytest.mark.parametrize('change',['expiry','executor_read','generation','catalog','material','owner_execute'])
def test_changed_ordinary_source_preserves_historical_verify_without_current_output(ordinary_plan,monkeypatch,change):
    f,_=ordinary_plan;p=start(f);finish(f,p);old=ok(results(f,p))
    if change=='expiry':
        clock=cs._now;monkeypatch.setattr(cs,'_now',lambda c:clock(c)+timedelta(hours=1))
    else:
        with f[1].connect() as c:
            if change in ('executor_read','generation'):
                c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
                if change=='generation':c.execute("UPDATE capability_grants SET active=true WHERE principal_id='executor-a' AND capability='READ'")
            elif change=='catalog':c.execute("UPDATE preparation_catalog SET name=name||' changed' WHERE park_id='park-a'")
            elif change=='material':c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(p['preparation_id'],))
            else:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    with TestClient(configured_app()) as api:
        fresh=(*f[:3],api);now=ok(results(fresh,p))
        assert now['state']=='UNVERIFIED' and now['current_required_goals']==old['current_required_goals']
        if change in ('expiry','executor_read','generation'):
            assert [x['state'] for x in now['results'][:2]]==['LOCAL_OUTPUT_VERIFIED']*2
        for i in (2,3):
            row=now['results'][i]
            assert row['state']!='LOCAL_OUTPUT_VERIFIED' and row['actual_output'] is None
            assert row['historical_verification']['id']==old['results'][i]['historical_verification']['id']
            assert not row['historical_verification']['current']
        ok(command(fresh,p,'P3'),403 if change=='owner_execute' else 409)


@pytest.mark.parametrize('damage',['run_active','run_inactive','offer_marker','accept_fingerprint','submit_fingerprint','ack_fingerprint'])
def test_foreign_authority_or_broken_original_proof_is_denied_without_legacy_fallback(ordinary_plan,damage):
    f,_=ordinary_plan;p=start(f);finish(f,p)
    if damage.startswith('run_'):f[1].assign_status('executor-a',UUID(p['run_id']),active=damage=='run_active')
    else:
        with f[1].connect() as c:
            if damage=='offer_marker':c.execute("UPDATE service_dispatch_events SET payload=jsonb_set(payload,ARRAY[%s,'binding','contract'],to_jsonb('ISOLATED_CASE_STEP_ASSIGNMENT_V1'::text)) WHERE action='OFFER'",(cs.MARKER,))
            elif damage=='accept_fingerprint':c.execute("UPDATE service_dispatch_events SET fingerprint=repeat('0',64) WHERE action='ACCEPT'")
            else:c.execute('UPDATE service_receipt_events SET fingerprint=repeat(\'0\',64) WHERE action=%s',('SUBMIT' if damage=='submit_fingerprint' else 'ACKNOWLEDGE',))
    before=business(f)
    with TestClient(configured_app()) as api:
        fresh=(*f[:3],api);ok(results(fresh,p),403);ok(read(fresh,p),403)
    assert business(f)==before


def test_p5_stays_unverified_until_original_explicit_local_revalidation(ordinary_plan):
    f,_=ordinary_plan;p=start(f,GOALS)
    finish(f,p)
    current=ok(results(f,p));assert current['state']=='UNVERIFIED'
    assert [x['state'] for x in current['results'][:4]]==['LOCAL_OUTPUT_VERIFIED']*4
    assert current['results'][4]['state']!='LOCAL_OUTPUT_VERIFIED'
    ok(command(f,p,'P5'),409)
    local=ok(f[3].get('/api/preparations/'+p['preparation_id']+'/local-case',headers=headers(f[2])))
    assert local['can_revalidate'] and local['local_record_state']=='NOT_STARTED'


def test_only_explicit_exact_same_store_service_can_select_sources(ordinary_plan):
    f,_=ordinary_plan
    from parkweave.ordinary_plan_sources import selected
    store=Store(f[0].dsn);store._ordinary_case_step_sources=object()
    with pytest.raises(Denied):selected(store)
    store._ordinary_case_step_sources=cs.OrdinaryCaseStepAssignments(Store(f[0].dsn))
    with pytest.raises(Denied):selected(store)
    service=cs.OrdinaryCaseStepAssignments(Store(f[0].dsn))
    create_app(service.store,case_step_assignments=service)
    with pytest.raises(Denied):create_app(service.store)


def test_unknown_target_remains_in_original_partial_goal_result(ordinary_plan):
    f,_=ordinary_plan;goals=[GOALS[0],'EXTERNAL_QUALIFICATION_APPROVAL']
    p=start(f,goals,partial=True);verified(f,p,'P1')
    current=ok(results(f,p))
    assert current['state']=='PARTIAL' and current['current_required_goals']==goals
    assert current['results'][0]['state']=='LOCAL_OUTPUT_VERIFIED'
    assert current['results'][1]['state']=='UNSUPPORTED' and current['results'][1]['actual_output'] is None
    assert not current['case_goal_completed']


@pytest.mark.parametrize('operation',['VERIFY','READ_RESULT'])
def test_actual_last_pg_lock_wait_crosses_first_deadline_without_false_current_or_commit(ordinary_plan,monkeypatch,tmp_path,operation):
    import json,time
    from concurrent.futures import ThreadPoolExecutor
    from parkweave import case_goal_results as goals,service_case_steps as plans
    f,_=ordinary_plan
    monkeypatch.setattr(cs._OrdinaryCaseStep,'_offer_deadline',lambda self,c:cs._now(c)+timedelta(seconds=18))
    p=start(f);d,r=acceptance(f,p)
    r=ok(act(f,r,'SUBMIT'));r=ok(act(f,r,'ACKNOWLEDGE'))
    if operation=='READ_RESULT':verified(f,p,'P3');verified(f,p,'P4')
    before=ok(read(f,p));module,attribute=(plans,'_view') if operation=='VERIFY' else (goals,'outputs')
    original=getattr(module,attribute)
    query="SELECT id FROM operations WHERE run_id=%s AND action='case.create' FOR SHARE /* ordinary_goal_last_wait */"
    def after_sources(*args,**kw):
        value=original(*args,**kw);args[1].execute(query,(p['run_id'],)).fetchone();return value
    monkeypatch.setattr(module,attribute,after_sources)
    with f[1].connect() as c:
        initial_remaining=c.execute('SELECT %s::timestamptz-clock_timestamp() AS remaining',(d['assignment_valid_until'],)).fetchone()['remaining'].total_seconds()
    assert initial_remaining>2
    time.sleep(initial_remaining-2)
    with f[1].connect() as lock:
        lock.execute("SELECT id FROM operations WHERE run_id=%s AND action='case.create' FOR UPDATE",(p['run_id'],))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(command,f,p,'P3',row=before) if operation=='VERIFY' else pool.submit(results,f,p)
            observed=False
            for _ in range(100):
                with f[1].connect() as c:
                    observed=bool(c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT id FROM operations%%ordinary_goal_last_wait%%'").fetchone())
                if observed:break
                if future.done():future.result()
                time.sleep(.02)
            assert observed,'owned final row wait required'
            with f[1].connect() as c:
                remaining=(c.execute('SELECT %s::timestamptz-clock_timestamp() AS remaining',(d['assignment_valid_until'],)).fetchone()['remaining']).total_seconds()
            # Actual DB wall clock, original marker, original 3s lock_timeout.
            assert 0<remaining<2
            time.sleep(remaining+.12);lock.commit();response=future.result(timeout=10)
    ok(response,403)
    monkeypatch.setattr(module,attribute,original)
    with f[1].connect() as c:
        stored=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
    assert stored['revision']==before['revision']
    assert sum(e['action']=='VERIFY' for e in stored['events'])==sum(e['action']=='VERIFY' for e in before['events'])
    (tmp_path/'last-lock-proof.json').write_text(json.dumps(dict(operation=operation,actual_pg_lock_observed=observed,
        original_deadline=d['assignment_valid_until'],status=response.status_code,plan_revision_unchanged=True,
        clock_offset_used=False),indent=2)+'\n')


@pytest.mark.parametrize('goal',[GOALS[0],GOALS[1]])
def test_p1_p2_only_goal_result_does_not_acquire_unrelated_step_deadline(ordinary_plan,monkeypatch,tmp_path,goal):
    import json,time
    from concurrent.futures import ThreadPoolExecutor
    from parkweave import case_goal_results as goals
    f,baseline=ordinary_plan
    monkeypatch.setattr(cs._OrdinaryCaseStep,'_offer_deadline',lambda self,c:cs._now(c)+timedelta(seconds=18))
    p=start(f,[goal]);verified(f,p,'P1')
    if goal==GOALS[1]:ok(resource_link(f,p,group(f)),201);verified(f,p,'P2')
    d=ok(decision(f,ok(offer(f,p)[0],201),'ACCEPT'))
    initial=ok(results(f,p));assert initial['state']=='LOCAL_OUTPUTS_VERIFIED'
    original=goals.outputs
    query="SELECT id FROM operations WHERE run_id=%s FOR SHARE /* p1_p2_only_last_wait */"
    def wait_after_sources(*args,**kw):
        value=original(*args,**kw);args[1].execute(query,(p['run_id'],)).fetchall();return value
    monkeypatch.setattr(goals,'outputs',wait_after_sources)
    with f[1].connect() as c:
        remaining=c.execute('SELECT %s::timestamptz-clock_timestamp() AS t',(d['assignment_valid_until'],)).fetchone()['t'].total_seconds()
    assert remaining>2;time.sleep(remaining-2)
    with f[1].connect() as lock:
        lock.execute('SELECT id FROM operations WHERE run_id=%s FOR UPDATE',(p['run_id'],)).fetchall()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(results,f,p);observed=False
            for _ in range(100):
                with f[1].connect() as c:
                    observed=bool(c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT id FROM operations%%p1_p2_only_last_wait%%'").fetchone())
                if observed:break
                if future.done():future.result()
                time.sleep(.02)
            assert observed
            with f[1].connect() as c:
                remaining=c.execute('SELECT %s::timestamptz-clock_timestamp() AS t',(d['assignment_valid_until'],)).fetchone()['t'].total_seconds()
            assert 0<remaining<2;time.sleep(remaining+.12);lock.commit();late=ok(future.result(timeout=10))
    monkeypatch.setattr(goals,'outputs',original)
    fresh=ok(results(f,p));assert late==initial==fresh
    assert authority_snapshot(f[1])==baseline
    (tmp_path/'p1-p2-only-last-lock.json').write_text(json.dumps(dict(goal=goal,actual_pg_wait=observed,
        late_status=200,original_deadline=d['assignment_valid_until'],all_results_equal=True,
        original_p1_p2_current=True,clock_offset_used=False),indent=2)+'\n')
