"""Ordinary P5 consumes existing owned synthetic records, never real setup."""
from datetime import timedelta
from uuid import UUID,uuid4
import pytest
from fastapi.testclient import TestClient
from parkweave import case_step_assignments as cs
from parkweave.api import create_app,configured_app
from parkweave.store import Store
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture,act as receipt_act
from test_ordinary_case_steps import ordinary
from test_ordinary_case_goal_results import ordinary_plan,start,finish,results
from test_case_step_assignments import ok,REVIEWER
from test_service_case_steps import GOALS,verified,command,read as plan_read
from test_case_lifecycle import read,act,counts
from service_release_acceptance_support import authority_snapshot


def prepared(f):
    p=start(f,GOALS);d,r=finish(f,p);return p,d,r


def closed(f,p):
    key=uuid4().hex;initial=ok(read(f,p))
    validated=ok(act(f,p,initial,'REVALIDATE',key=key))
    close_key=uuid4().hex;close_before=ok(read(f,p))
    final=ok(act(f,p,close_before,'CLOSE_LOCAL_RECORD',key=close_key))
    return final,key,close_key,close_before


def recover(f,p,key,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/local-case/recovery/'+key,headers=headers(f[2],user))


def test_original_ordinary_revalidate_close_p5_verify_cold_recovery_and_no_run_authority(ordinary_plan):
    f,baseline=ordinary_plan;p,d,r=prepared(f)
    initial=ok(read(f,p));assert initial['can_revalidate'] and initial['local_record_state']=='NOT_STARTED'
    ok(act(f,p,initial,'CLOSE_LOCAL_RECORD'),409);ok(command(f,p,'P5'),409)
    row,key,close_key,close_before=closed(f,p)
    assert row['local_record_state']=='LOCAL_RECORD_CLOSED' and row['case_state']=='WAITING_CONFIRMATION'
    assert row['verification_current'] and not row['case_goal_completed']
    assert ok(results(f,p))['results'][4]['state']=='AWAITING_OWNER_VERIFICATION'
    verified(f,p,'P5');current=ok(results(f,p));assert current['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert len(current['results'])==5 and current['results'][4]['actual_output']['local_record_state']=='LOCAL_RECORD_CLOSED'
    assert not current['case_goal_completed'] and current['offline_fulfillment']=='NO_EVIDENCE'
    before=counts(f);ok(act(f,p,close_before,'CLOSE_LOCAL_RECORD',key=close_key));assert counts(f)==before==[1,2]
    with TestClient(configured_app()) as api:
        cold=(*f[:3],api);assert ok(results(cold,p))==current
        saved=ok(recover(cold,p,key));assert saved['status']=='COMMITTED' and saved['historical_only'] and not saved['automatically_replayed']
        assert saved['receipt']['action']=='REVALIDATE' and not saved['original_is_current_version']
        latest=ok(recover(cold,p,close_key));assert latest['original_is_current_version']
        assert latest['current']['local_record_state']=='LOCAL_RECORD_CLOSED'
    assert authority_snapshot(f[1])==baseline
    with f[1].connect() as c:assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
    with TestClient(create_app(Store(f[0].dsn))) as api:
        legacy=(*f[:3],api);ok(read(legacy,p),403);ok(recover(legacy,p,close_key),403)


def test_ordinary_reopen_preserves_history_and_requires_new_cycle_without_reauthorizing_step(ordinary_plan):
    f,baseline=ordinary_plan;p,d,r=prepared(f);row,key,close_key,_=closed(f,p);verified(f,p,'P5')
    old=ok(results(f,p))['results'][4]['historical_verification']
    with f[1].connect() as c:holds=c.execute('SELECT id,state FROM synthetic_resource_holds ORDER BY id').fetchall()
    reopened=ok(act(f,p,row,'REOPEN'));assert reopened['cycle']==2 and reopened['verified_snapshot_sha256'] is None
    assert reopened['local_record_state']=='REOPENED'
    stale=ok(results(f,p))['results'][4]
    assert stale['historical_verification']['id']==old['id'] and not stale['historical_verification']['current']
    assert stale['actual_output'] is None and stale['state']!='LOCAL_OUTPUT_VERIFIED'
    ok(command(f,p,'P5'),409);now=ok(read(f,p));ok(act(f,p,now,'CLOSE_LOCAL_RECORD'),409)
    saved=ok(recover(f,p,close_key));assert saved['receipt']['event']['local_record_state']=='LOCAL_RECORD_CLOSED'
    assert saved['current']['local_record_state']=='REOPENED' and not saved['original_is_current_version']
    ok(act(f,p,now,'REVALIDATE'));second=ok(act(f,p,ok(read(f,p)),'CLOSE_LOCAL_RECORD'));verified(f,p,'P5')
    assert second['cycle']==2 and [e['action'] for e in second['history']]==['REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN','REVALIDATE','CLOSE_LOCAL_RECORD']
    assert ok(results(f,p))['state']=='LOCAL_OUTPUTS_VERIFIED'
    with f[1].connect() as c:
        assert c.execute('SELECT id,state FROM synthetic_resource_holds ORDER BY id').fetchall()==holds
        assert c.execute('SELECT count(*) n FROM service_dispatch_offers').fetchone()['n']==1
        assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n']==1
    assert authority_snapshot(f[1])==baseline


def test_current_cycle_may_be_revalidated_after_new_original_manual_receipt(ordinary_plan):
    f,_=ordinary_plan;p,d,r=prepared(f);ok(act(f,p,ok(read(f,p)),'REVALIDATE'))
    r=ok(receipt_act(f,r,'REOPEN'));r=ok(receipt_act(f,r,'SUBMIT',text='SYNTHETIC next actual output'))
    r=ok(receipt_act(f,r,'ACKNOWLEDGE'));verified(f,p,'P4')
    now=ok(read(f,p));assert not now['verification_current']
    ok(act(f,p,now,'REVALIDATE'));last=ok(act(f,p,ok(read(f,p)),'CLOSE_LOCAL_RECORD'));verified(f,p,'P5')
    assert last['cycle']==1 and [x['action'] for x in last['history']]==['REVALIDATE','REVALIDATE','CLOSE_LOCAL_RECORD']
    assert ok(results(f,p))['results'][4]['state']=='LOCAL_OUTPUT_VERIFIED'


@pytest.mark.parametrize('change',['expiry','executor_read','generation','owner_execute','resource_hold'])
def test_changed_sources_preserve_history_and_reopen_never_renews_the_original_step(ordinary_plan,monkeypatch,change):
    f,_=ordinary_plan;p,d,r=prepared(f);row,key,close_key,_=closed(f,p);verified(f,p,'P5')
    if change=='expiry':
        clock=cs._now;monkeypatch.setattr(cs,'_now',lambda c:clock(c)+timedelta(hours=1))
    else:
        with f[1].connect() as c:
            if change in ('executor_read','generation'):
                c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
                if change=='generation':c.execute("UPDATE capability_grants SET active=true WHERE principal_id='executor-a' AND capability='READ'")
            elif change=='owner_execute':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
            else:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    with TestClient(configured_app()) as api:
        cold=(*f[:3],api);now=ok(read(cold,p));assert not now['verification_current']
        goal=ok(results(cold,p))['results'][4];assert not goal['historical_verification']['current'] and goal['actual_output'] is None
        before=counts(f);ok(act(cold,p,now,'REVALIDATE'),403 if change=='owner_execute' else 409);assert counts(f)==before
        if change=='owner_execute':
            ok(act(cold,p,now,'REOPEN'),403);assert not now['can_reopen']
        else:
            opened=ok(act(cold,p,now,'REOPEN'));assert opened['cycle']==2
            assert not ok(read(cold,p))['can_revalidate'];ok(command(cold,p,'P5'),409)
    with f[1].connect() as c:
        first=c.execute("SELECT payload FROM service_dispatch_events WHERE action='OFFER'").fetchone()['payload'][cs.MARKER]
        assert first['valid_until']==d['assignment_valid_until']


@pytest.mark.parametrize('user',[REVIEWER,'executor-a','unassigned','fixture-b','fixture-c'])
def test_ordinary_p5_retains_original_owner_write_and_minimal_counterpart_scope(ordinary_plan,user):
    f,_=ordinary_plan;p,d,r=prepared(f);row,key,close_key,_=closed(f,p);before=counts(f)
    response=read(f,p,user)
    if user==REVIEWER:
        minimal=ok(response);assert minimal['checks'] is None and minimal['verified_snapshot_sha256'] is None
        assert 'SYNTHETIC explicit' not in response.text and minimal['history'][0].get('payload') is None
    else:ok(response,403)
    ok(act(f,p,row,'REOPEN',user),403);ok(recover(f,p,close_key,user),403);assert counts(f)==before


@pytest.mark.parametrize('damage',['revalidation_fingerprint','close_fingerprint','ledger_sha','event_actor','event_scope'])
def test_ordinary_p5_requires_original_local_event_and_ledger_proofs(ordinary_plan,damage):
    f,_=ordinary_plan;p,d,r=prepared(f);row,key,close_key,_=closed(f,p);verified(f,p,'P5')
    with f[1].connect() as c:
        if damage.endswith('fingerprint'):
            c.execute('UPDATE case_local_events SET fingerprint=repeat(\'0\',64) WHERE action=%s',('REVALIDATE' if damage.startswith('revalidation') else 'CLOSE_LOCAL_RECORD',))
        elif damage=='ledger_sha':c.execute("UPDATE case_local_lifecycles SET verified_sha256=repeat('0',64)")
        elif damage=='event_actor':c.execute("UPDATE case_local_events SET actor_id='fixture-b' WHERE action='CLOSE_LOCAL_RECORD'")
        else:c.execute("UPDATE case_local_events SET payload=jsonb_set(payload,'{scope}',to_jsonb('UNKNOWN'::text)) WHERE action='CLOSE_LOCAL_RECORD'")
    before=counts(f);ok(read(f,p),409);ok(results(f,p),409)
    # An actor-corrupted key is no longer visible in the original actor scope;
    # an intact original key still reaches and rejects the corrupt current row.
    if damage=='event_actor':
        assert ok(recover(f,p,close_key))['status']=='NOT_OBSERVED'
        ok(recover(f,p,key),409)
    else:ok(recover(f,p,close_key),409)
    assert counts(f)==before


@pytest.mark.parametrize('change',['owner_read','owner_prepare','resource_read','run_inactive'])
def test_ordinary_p5_history_requires_its_original_read_scope_and_never_falls_back(ordinary_plan,change):
    f,_=ordinary_plan;p,d,r=prepared(f);row,key,close_key,_=closed(f,p);verified(f,p,'P5')
    if change=='run_inactive':f[1].assign_status('executor-a',UUID(p['run_id']),active=False)
    else:
        with f[1].connect() as c:
            if change=='owner_read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
            elif change=='owner_prepare':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
            else:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
    before=counts(f)
    with TestClient(configured_app()) as api:
        cold=(*f[:3],api)
        if change=='resource_read':
            local=ok(read(cold,p));assert not local['verification_current'] and not local['can_revalidate']
            assert local['history'] and local['checks']['RESOURCE_RECHECK']
        else:ok(read(cold,p),403);ok(results(cold,p),403)
        # Recovery requires READ to both historical and currently linked resources.
        ok(recover(cold,p,close_key),403)
        ok(act(cold,p,row,'REVALIDATE'),409 if change=='resource_read' else 403)
    assert counts(f)==before


def test_original_ready_p5_and_reopen_optional_sha_remain_compatible(ordinary_plan):
    f,_=ordinary_plan;p,d,r=prepared(f)
    ready=ok(act(f,p,ok(read(f,p)),'REVALIDATE'));assert ready['local_record_state']=='READY'
    verified(f,p,'P5');assert ok(results(f,p))['results'][4]['actual_output']['local_record_state']=='READY'
    row=ok(act(f,p,ok(read(f,p)),'CLOSE_LOCAL_RECORD'))
    reopen_key=uuid4().hex
    reopened=ok(act(f,p,row,'REOPEN',key=reopen_key,expected_snapshot_sha256='0'*64))
    saved=ok(recover(f,p,reopen_key));assert saved['status']=='COMMITTED' and saved['original_is_current_version']
    assert saved['receipt']['action']=='REOPEN' and saved['current']['cycle']==reopened['cycle']==2
    assert saved['current']['verified_snapshot_sha256'] is None
