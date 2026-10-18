"""Independent literal P5 probes; original HTTP actions and owned synthetic setup."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event
from uuid import uuid4
import hashlib
import json
import os
import time

from fastapi.testclient import TestClient
from parkweave import case_lifecycle as life
from parkweave.api import configured_app, create_app
from parkweave.store import Store
from test_preparation import preparation_fixture, headers
from test_executor_receipts import receipt_fixture, act as receipt_act
from test_ordinary_case_steps import ordinary
from test_ordinary_case_goal_results import ordinary_plan, start, finish, results
from test_ordinary_case_record_recheck import prepared, closed, recover
from test_case_step_assignments import prepared as standalone_prepared, ok, REVIEWER
from test_case_resources import group, post as link
from test_service_dispatches import offer, command as dispatch_decision
from test_service_case_steps import GOALS, verified, command as plan_command
from test_case_lifecycle import read, act, counts
from service_release_acceptance_support import authority_snapshot


def evidence(name, value):
    out = Path(os.environ['PARKWEAVE_INDEPENDENT_RECORD_EVIDENCE'])
    out.mkdir(parents=True, exist_ok=True)
    (out / (name + '.json')).write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + '\n')


def business_digest(f):
    tables = ('cases', 'preparations', 'case_local_lifecycles', 'case_local_events',
              'service_dispatches', 'service_dispatch_offers', 'service_dispatch_events',
              'service_receipt_steps', 'service_step_receipts', 'service_receipt_events',
              'synthetic_resource_holds', 'case_resource_links', 'resource_case_claims')
    with f[1].connect() as c:
        rows = {table:c.execute('SELECT to_jsonb(t) AS row FROM ' + table + ' t ORDER BY to_jsonb(t)::text').fetchall() for table in tables}
    encoded = json.dumps(rows, sort_keys=True, default=str).encode()
    return dict(sha256=hashlib.sha256(encoded).hexdigest(), counts={k:len(v) for k,v in rows.items()})


def test_standalone_original_lifecycle_never_creates_or_verifies_a_plan(ordinary_plan):
    f,baseline = ordinary_plan
    # Unlike legacy ready(), this existing helper creates no Run assignment.
    p = standalone_prepared(f, 'P5_STANDALONE')
    ok(link(f, p, group(f)), 201)
    d = ok(dispatch_decision(f, ok(offer(f, p)[0], 201), 'ACCEPT'))
    r = ok(f[3].get('/api/executor-receipts/' + d['receipt_step_id'], headers=headers(f[2], 'executor-a')))
    r = ok(receipt_act(f, r, 'SUBMIT', text='SYNTHETIC independent original standalone receipt'))
    ok(receipt_act(f, r, 'ACKNOWLEDGE'))
    before = ok(read(f, p))
    ok(act(f, p, before, 'CLOSE_LOCAL_RECORD'), 409)
    ready = ok(act(f, p, before, 'REVALIDATE'))
    assert ready['local_record_state'] == 'READY'
    final = ok(act(f, p, ok(read(f, p)), 'CLOSE_LOCAL_RECORD'))
    assert final['local_record_state'] == 'LOCAL_RECORD_CLOSED'
    assert final['case_state'] == 'WAITING_CONFIRMATION' and final['verification_current']
    assert not final['case_goal_completed']
    with f[1].connect() as c:
        assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s', (p['preparation_id'],)).fetchone()['service_case_plan'] is None
        assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
    snap = business_digest(f)
    assert ok(read(f, p))['revision'] == 2
    assert business_digest(f) == snap and authority_snapshot(f[1]) == baseline
    evidence('standalone', dict(state=final['local_record_state'], revision=final['revision'], cycle=final['cycle'], no_adopted_plan=True, no_run_assignments=True, read_only=snap))


def test_same_cycle_revalidation_and_old_keys_never_restore_the_previous_cycle(ordinary_plan):
    f,_ = ordinary_plan
    p,d,r = prepared(f)
    original = ok(read(f, p)); first_key = uuid4().hex
    first = ok(act(f, p, original, 'REVALIDATE', key=first_key))
    r = ok(receipt_act(f, r, 'REOPEN'))
    r = ok(receipt_act(f, r, 'SUBMIT', text='SYNTHETIC independent changed actual receipt v2'))
    ok(receipt_act(f, r, 'ACKNOWLEDGE')); verified(f, p, 'P4')
    second = ok(act(f, p, ok(read(f, p)), 'REVALIDATE'))
    assert second['cycle'] == first['cycle'] == 1 and second['revision'] == 2
    before_close = ok(read(f, p)); close_key = uuid4().hex
    close = ok(act(f, p, before_close, 'CLOSE_LOCAL_RECORD', key=close_key))
    verified(f, p, 'P5')
    key = uuid4().hex
    opened = ok(act(f, p, close, 'REOPEN', key=key, expected_snapshot_sha256='1'*64))
    snap = business_digest(f)
    with TestClient(configured_app()) as api:
        cold = (*f[:3], api)
        histories = [ok(recover(cold, p, old)) for old in (first_key, close_key, key)]
        assert [x['status'] for x in histories] == ['COMMITTED']*3
        assert [x['original_is_current_version'] for x in histories] == [False,False,True]
        assert all(x['current']['cycle'] == 2 and x['current']['local_record_state'] == 'REOPENED' for x in histories)
        replay = ok(act(cold, p, before_close, 'CLOSE_LOCAL_RECORD', key=close_key))
        assert replay['cycle'] == 2 and replay['local_record_state'] == 'REOPENED'
        ok(act(cold, p, before_close, 'CLOSE_LOCAL_RECORD', key=close_key, reason='SYNTHETIC different original body'), 409)
    assert business_digest(f) == snap
    assert [x['action'] for x in opened['history']] == ['REVALIDATE','REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN']
    evidence('cycles-original-keys', dict(original_revisions=[first['revision'],second['revision'],close['revision'],opened['revision']], current_cycle=2, historical_current_flags=[x['original_is_current_version'] for x in histories], read_only=snap))


def test_owner_execute_history_then_aba_reopen_cannot_renew_original_acceptance(ordinary_plan):
    f,_ = ordinary_plan
    p,d,r = prepared(f); final,validation_key,close_key,close_before = closed(f,p)
    verified(f,p,'P5')
    with f[1].connect() as c:
        marker = c.execute("SELECT payload FROM service_dispatch_events WHERE action='OFFER'").fetchone()['payload']['case_step_assignment']
        holds = c.execute('SELECT id,state FROM synthetic_resource_holds ORDER BY id').fetchall()
        c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    snap = business_digest(f)
    with TestClient(configured_app()) as api:
        cold=(*f[:3],api)
        history=ok(read(cold,p)); saved=ok(recover(cold,p,close_key))
        assert history['history'] and saved['status']=='COMMITTED'
        assert not history['can_reopen'] and not history['verification_current']
        ok(act(cold,p,close_before,'CLOSE_LOCAL_RECORD',key=close_key),403)
        ok(act(cold,p,history,'REOPEN'),403)
    assert business_digest(f)==snap
    with f[1].connect() as c:
        c.execute("UPDATE capability_grants SET active=true WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
        c.execute("UPDATE capability_grants SET active=true WHERE principal_id='executor-a' AND capability='READ'")
    with TestClient(configured_app()) as api:
        cold=(*f[:3],api)
        now=ok(read(cold,p)); assert not now['verification_current']
        opened=ok(act(cold,p,now,'REOPEN')); assert opened['cycle']==2
        invalid=ok(read(cold,p)); ok(act(cold,p,invalid,'REVALIDATE'),409)
        ok(plan_command(cold,p,'P5'),409)
        saved=ok(recover(cold,p,close_key)); assert saved['status']=='COMMITTED' and not saved['original_is_current_version']
    with f[1].connect() as c:
        assert c.execute("SELECT payload FROM service_dispatch_events WHERE action='OFFER'").fetchone()['payload']['case_step_assignment']==marker
        assert c.execute('SELECT id,state FROM synthetic_resource_holds ORDER BY id').fetchall()==holds
        assert c.execute('SELECT count(*) n FROM service_dispatch_offers').fetchone()['n']==1
        assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
    evidence('history-execute-aba',dict(original_deadline=d['assignment_valid_until'], current_cycle=2, reopen_did_not_renew=True, no_current_p5=True))


def test_current_proof_rejects_changed_original_reason_and_cross_case_snapshot(ordinary_plan):
    f,_=ordinary_plan
    p,d,r=prepared(f); final,key,close_key,_=closed(f,p); verified(f,p,'P5')
    with f[1].connect() as c:
        event=c.execute("SELECT * FROM case_local_events WHERE action='REVALIDATE'").fetchone()
        c.execute("UPDATE case_local_events SET payload=jsonb_set(payload,'{reason}',to_jsonb('SYNTHETIC altered immutable reason'::text)) WHERE id=%s",(event['id'],))
    snap=business_digest(f)
    for response in (read(f,p),results(f,p),recover(f,p,key),recover(f,p,close_key)):
        ok(response,409)
    assert business_digest(f)==snap
    # Restore only this owned corruption; then alter source parent IDs without
    # replacing the immutable request fingerprint or calling a new verifier.
    from psycopg.types.json import Jsonb
    with f[1].connect() as c:
        c.execute('UPDATE case_local_events SET payload=%s WHERE id=%s',(Jsonb(event['payload']),event['id']))
        c.execute("UPDATE case_local_events SET snapshot=jsonb_set(snapshot,'{case_id}',to_jsonb(%s::text)) WHERE action='REVALIDATE'",(str(uuid4()),))
    snap2=business_digest(f)
    ok(read(f,p),409);ok(results(f,p),409);ok(recover(f,p,key),409)
    assert business_digest(f)==snap2
    evidence('original-proof-corruption',dict(reason_rejected=True, cross_case_snapshot_rejected=True, no_rehash_or_alternate_verifier=True, first_readonly=snap, second_readonly=snap2))


def test_actual_ledger_share_wait_crosses_resource_end_without_false_current(ordinary_plan,monkeypatch):
    import test_resource_combinations as pairs
    f,_=ordinary_plan
    original_body=pairs.body
    def short_original_resource_request(*args,**kwargs):
        data=original_body(*args,**kwargs)
        with f[1].connect() as c:now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
        return dict(data,starts_at=(now+timedelta(seconds=4)).isoformat(),ends_at=(now+timedelta(seconds=42)).isoformat())
    monkeypatch.setattr(pairs,'body',short_original_resource_request)
    p,d,r=prepared(f);final,key,close_key,_=closed(f,p)
    with f[1].connect() as c:
        deadline=c.execute('SELECT min(ends_at) t FROM synthetic_resource_holds').fetchone()['t']
    original_ledger=life._ledger;ready=Event()
    proof=dict(original_resource_end=deadline.isoformat(),original_offer_end=d['assignment_valid_until'],clock_offset_used=False,actual_ledger_wait_observed=False)
    def at_real_ledger(c,parent,write=False):
        if not ready.is_set():
            proof['backend_pid']=c.execute('SELECT pg_backend_pid() pid').fetchone()['pid']
            remaining=c.execute('SELECT %s-clock_timestamp() t',(deadline,)).fetchone()['t'].total_seconds()
            proof['remaining_at_original_ledger_entry']=remaining
            assert remaining>2,'independent resource deadline setup must leave launch headroom'
            time.sleep(max(0,remaining-0.9))
            ready.set()
        return original_ledger(c,parent,write=write)
    monkeypatch.setattr(life,'_ledger',at_real_ledger)
    snap=business_digest(f);response=None
    try:
        with f[1].connect() as lock:
            lock.execute('SELECT * FROM case_local_lifecycles WHERE preparation_id=%s FOR UPDATE',(p['preparation_id'],)).fetchone()
            with ThreadPoolExecutor(max_workers=1) as pool:
                def request():
                    proof['request_start_utc']=datetime.now(timezone.utc).isoformat()
                    result=read(f,p)
                    proof.update(status=result.status_code,detail=result.json().get('detail'),request_end_utc=datetime.now(timezone.utc).isoformat())
                    return result
                future=pool.submit(request)
                try:
                    assert ready.wait(50),'original lifecycle ledger entry was not reached'
                    for _ in range(80):
                        with f[1].connect() as c:
                            waiting=c.execute("SELECT query,wait_event,clock_timestamp() now FROM pg_stat_activity WHERE pid=%s AND wait_event_type='Lock'",(proof['backend_pid'],)).fetchone()
                        if waiting:
                            proof.update(actual_ledger_wait_observed=True, observed_wait=dict(waiting))
                            break
                        if future.done():break
                        time.sleep(.01)
                    assert proof['actual_ledger_wait_observed'],'actual original ledger FOR SHARE must block'
                    assert 'case_local_lifecycles' in proof['observed_wait']['query'] and 'FOR SHARE' in proof['observed_wait']['query']
                    with f[1].connect() as c:
                        remaining=c.execute('SELECT %s-clock_timestamp() t',(deadline,)).fetchone()['t'].total_seconds()
                    proof['remaining_at_observed_wait']=remaining
                    assert 0<remaining<1.5
                    time.sleep(remaining+.12)
                finally:
                    lock.commit()
                    response=future.result(timeout=10)
        assert response.status_code in (200,403)
        if response.status_code==200:assert response.json()['verification_current'] is not True
        monkeypatch.setattr(life,'_ledger',original_ledger)
        assert business_digest(f)==snap
        proof.update(no_business_write=True,original_counts=counts(f))
    finally:
        if response is not None:proof['response_current']=response.json().get('verification_current')
        evidence('actual-ledger-resource-end',proof)


def test_cross_case_original_key_and_legacy_or_counterparty_paths_do_not_expand_scope(ordinary_plan):
    f,baseline=ordinary_plan
    p,d,r=prepared(f);final,key,close_key,_=closed(f,p)
    other=standalone_prepared(f,'P5_OTHER_CASE')
    snap=business_digest(f)
    ok(recover(f,other,close_key),409)
    reviewer=ok(read(f,p,REVIEWER))
    assert reviewer['checks'] is None and reviewer['current_snapshot_sha256'] is None
    assert all('payload' not in e for e in reviewer['history'])
    for user in ('executor-a','fixture-b'):
        ok(read(f,p,user),403);ok(recover(f,p,close_key,user),403);ok(results(f,p,user),403)
        ok(act(f,p,final,'REOPEN',user),403)
    ok(act(f,p,final,'REOPEN',REVIEWER),403)
    ok(f[3].get('/api/runs/'+p['run_id'],headers=headers(f[2],'executor-a')),403)
    with TestClient(create_app(Store(f[0].dsn))) as api:
        legacy=(*f[:3],api)
        ok(read(legacy,p),403);ok(recover(legacy,p,close_key),403);ok(results(legacy,p),403)
    assert business_digest(f)==snap and authority_snapshot(f[1])==baseline
    evidence('scope-and-original-key',dict(cross_case_key_status=409, executor_whole_case_status=403, default_lane_status=403, reviewer_payload_hidden=True, read_only=snap))
