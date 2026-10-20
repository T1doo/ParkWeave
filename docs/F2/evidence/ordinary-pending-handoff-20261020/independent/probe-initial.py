"""Independent bounded review: only owned temporary Linux PG and existing fixtures."""
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from fastapi.testclient import TestClient
from parkweave.api import configured_app
from test_preparation import headers
from test_case_step_assignments import prepared, ok, REVIEWER
from test_service_dispatches import offer, command as decision
from test_executor_receipts import act
from test_ordinary_case_steps import dispatch
from service_release_acceptance_support import authority_snapshot


def pending_withdrawn(f,p):
    first=ok(offer(f,p)[0],201)
    accepted=ok(decision(f,first,'ACCEPT'))
    ended=ok(decision(f,accepted,'WITHDRAW'))
    return first,accepted,ended


def counts(owner):
    with owner.connect() as c:
        return {t:c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in (
            'service_dispatch_offers','service_dispatch_events','service_receipt_steps',
            'service_receipt_events','service_step_receipts','dispatch_notice_outbox')}


def duplicate_create(c,step):
    # Valid SQL/types/FKs, additional CREATE with a distinct unique revision/key.
    c.execute("INSERT INTO service_receipt_events SELECT (jsonb_populate_record(NULL::service_receipt_events,to_jsonb(e)||jsonb_build_object('id',%s::text,'request_key',%s::text,'revision',2))).* FROM service_receipt_events e WHERE e.step_id=%s AND e.action='CREATE'",(str(uuid4()),'independent-duplicate:'+uuid4().hex,step))


def test_independent_positive_second_executor_new_step_and_receipt(ordinary):
    f,authority=ordinary;p=prepared(f)
    first,accepted,ended=pending_withdrawn(f,p)
    oldstep=accepted['receipt_step_id']
    renewed=ok(offer(f,p,revision=ended['revision'],executor='unassigned')[0],201)
    assert renewed['assignment_valid_until']==first['assignment_valid_until']
    new=ok(decision(f,renewed,'ACCEPT'))
    assert new['receipt_step_id']!=oldstep
    receipt=ok(f[3].get('/api/executor-receipts/'+new['receipt_step_id'],headers=headers(f[2],'unassigned')))
    receipt=ok(act(f,receipt,'SUBMIT',user='unassigned'))
    receipt=ok(act(f,receipt,'ACKNOWLEDGE'))
    assert receipt['step']['state']=='LOCAL_ACKNOWLEDGED'
    assert not receipt['case_goal_completed']
    assert f[3].get('/api/executor-receipts/'+oldstep,headers=headers(f[2],'executor-a')).status_code==403
    with TestClient(configured_app()) as cold:
        history=ok(dispatch((*f[:3],cold),new,'fixture-a'))
        assert [e['action'] for e in history['history']]==['OFFER','ACCEPT','WITHDRAW','REOFFER','ACCEPT']
    with f[1].connect() as c:
        old=c.execute('SELECT revision,state,current_receipt_id FROM service_receipt_steps WHERE id=%s',(oldstep,)).fetchone()
        assert old==dict(revision=1,state='AWAITING_RECEIPT',current_receipt_id=None)
    assert authority_snapshot(f[1])==authority


@pytest.mark.parametrize('moment',['before_offer','after_offer'])
def test_duplicate_create_refuses_offer_or_accept_without_writes(ordinary,moment):
    f,authority=ordinary;p=prepared(f)
    _,accepted,ended=pending_withdrawn(f,p)
    renewed=ok(offer(f,p,revision=ended['revision'],executor='unassigned')[0],201) if moment=='after_offer' else None
    with f[1].connect() as c:duplicate_create(c,accepted['receipt_step_id'])
    before=counts(f[1])
    result=decision(f,renewed,'ACCEPT') if renewed else offer(f,p,revision=ended['revision'],executor='unassigned')[0]
    assert result.status_code in (403,409)
    assert counts(f[1])==before
    assert authority_snapshot(f[1])==authority


def test_two_original_acceptances_cannot_claim_one_step(ordinary):
    f,authority=ordinary;p=prepared(f)
    _,first,ended=pending_withdrawn(f,p)
    invited=ok(offer(f,p,revision=ended['revision'],executor='unassigned')[0],201)
    second=ok(decision(f,invited,'ACCEPT'))
    ended=ok(decision(f,second,'WITHDRAW'))
    with f[1].connect() as c:
        event=c.execute("SELECT id,payload FROM service_dispatch_events WHERE offer_id=%s AND action='ACCEPT'",(second['current_offer']['id'],)).fetchone()
        payload=event['payload'];payload['receipt_step_id']=first['receipt_step_id']
        c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s',(Jsonb(payload),event['id']))
    before=counts(f[1])
    result=offer(f,p,revision=ended['revision'],executor='executor-a')[0]
    assert result.status_code in (403,409)
    assert counts(f[1])==before
    assert authority_snapshot(f[1])==authority


def test_missing_all_steps_does_not_erase_original_acceptance(ordinary):
    f,authority=ordinary;p=prepared(f)
    _,accepted,ended=pending_withdrawn(f,p)
    with f[1].connect() as c:
        c.execute('DELETE FROM service_receipt_events WHERE step_id=%s',(accepted['receipt_step_id'],))
        c.execute('DELETE FROM service_receipt_steps WHERE id=%s',(accepted['receipt_step_id'],))
        assert c.execute("SELECT count(*) n FROM service_dispatch_events WHERE action='ACCEPT'").fetchone()['n']==1
    before=counts(f[1])
    result=offer(f,p,revision=ended['revision'],executor='unassigned')[0]
    assert result.status_code in (403,409)
    assert counts(f[1])==before
    assert authority_snapshot(f[1])==authority
