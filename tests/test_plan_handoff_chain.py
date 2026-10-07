"""Existing same-Case plan/handoff/receipt chain on isolated PostgreSQL records."""
from uuid import UUID, uuid4

import pytest

from parkweave import controlled_plans as cp
from parkweave.store import Store
from test_preparation import preparation_fixture, headers
from test_executor_receipts import receipt_fixture, ready, act as receipt_act
from test_case_resources import link_fixture, group, post as link
from test_controlled_plans import create, check, read, through
from test_service_dispatches import offer, command as dispatch_act, REVIEWER


def authority(f):
    with f[1].connect() as c:
        return [c.execute('SELECT * FROM '+table+' ORDER BY '+order).fetchall()
                for table, order in (
                    ('capability_grants', 'principal_id,capability'),
                    ('preparation_grants', 'principal_id,capability'),
                    ('run_assignments', 'run_id,principal_id'))]


def records(f):
    with f[1].connect() as c:
        return [c.execute('SELECT count(*) n FROM '+table).fetchone()['n']
                for table in ('controlled_plan_events', 'service_dispatch_events',
                              'service_receipt_steps', 'service_step_receipts',
                              'service_receipt_events')]


def test_same_case_existing_acceptance_receipt_and_plan_sources_persist(link_fixture):
    f=link_fixture;p=ready(f);before=authority(f)
    assert create(f,p).status_code==201
    assert check(f,p,'P1').status_code==200
    assert link(f,p,group(f)).status_code==201
    assert check(f,p,'P2').status_code==200
    offered=offer(f,p)[0];assert offered.status_code==201
    offered=offered.json()
    with f[1].connect() as c:
        assert not c.execute('SELECT 1 FROM service_receipt_steps WHERE preparation_id=%s',
                             (UUID(p['preparation_id']),)).fetchone()
    key=uuid4().hex
    accepted=dispatch_act(f,offered,'ACCEPT',key=key)
    assert accepted.status_code==200;accepted=accepted.json()
    assert dispatch_act(f,offered,'ACCEPT',key=key).json()['event']==accepted['event']
    assert check(f,p,'P3').status_code==200
    receipt=f[3].get('/api/executor-receipts/'+accepted['receipt_step_id'],
                     headers=headers(f[2],'executor-a')).json()
    submitted=receipt_act(f,receipt,'SUBMIT');assert submitted.status_code==200
    acknowledged=receipt_act(f,submitted.json(),'ACKNOWLEDGE')
    assert acknowledged.status_code==200;receipt=acknowledged.json()
    assert check(f,p,'P4').status_code==200
    plan=read(f,p).json()
    assert plan['state']=='LOCAL_RECORDS_CHECKED'
    with f[1].connect() as c:
        step=c.execute('SELECT * FROM service_receipt_steps WHERE preparation_id=%s',
                       (UUID(p['preparation_id']),)).fetchall()
        assert len(step)==1;step=step[0]
        assert tuple(str(step[k]) for k in ('preparation_id','case_id','run_id'))==tuple(
            p[k] for k in ('preparation_id','case_id','run_id'))
        assert step['executor_id']=='executor-a' and step['state']=='LOCAL_ACKNOWLEDGED'
        dispatch=c.execute('SELECT * FROM service_dispatches WHERE preparation_id=%s',
                           (step['preparation_id'],)).fetchone()
        accepted_offer=c.execute('SELECT * FROM service_dispatch_offers WHERE id=%s',
                                 (dispatch['current_offer_id'],)).fetchone()
        assert accepted_offer['receipt_step_id']==step['id']
        assert accepted_offer['executor_id']==step['executor_id']
        acceptance=c.execute("SELECT * FROM service_dispatch_events WHERE dispatch_id=%s AND action='ACCEPT'",
                             (dispatch['id'],)).fetchall()
        assert len(acceptance)==1 and acceptance[0]['actor_id']==step['executor_id']
        assert acceptance[0]['payload']['receipt_step_id']==str(step['id'])
        receipt_events=c.execute('SELECT * FROM service_receipt_events WHERE step_id=%s ORDER BY revision',
                                 (step['id'],)).fetchall()
        assert [e['action'] for e in receipt_events]==['CREATE','SUBMIT','ACKNOWLEDGE']
        assert receipt_events[0]['payload']['dispatch_id']==str(dispatch['id'])
        assert receipt_events[0]['payload']['offer_id']==str(accepted_offer['id'])
        current=c.execute('SELECT * FROM service_step_receipts WHERE id=%s',
                          (step['current_receipt_id'],)).fetchone()
        assert current['version']==1 and current['actor_id']==step['executor_id']
        checks=c.execute("SELECT step,snapshot FROM controlled_plan_events WHERE preparation_id=%s AND action='CHECK_STEP' ORDER BY revision",
                         (step['preparation_id'],)).fetchall()
        snapshots={e['step']:e['snapshot'] for e in checks}
        assert snapshots==plan['source_snapshots']
        assert snapshots['P1']['case_id']==p['case_id'] and snapshots['P1']['run_id']==p['run_id']
        assert snapshots['P3']['offer_id']==str(accepted_offer['id'])
        assert snapshots['P3']['dispatch_revision']==dispatch['revision']
        assert snapshots['P3']['receipt_step_id']==str(step['id'])
        assert snapshots['P4']['receipt_step_revision']==step['revision']
        assert snapshots['P4']['receipt_id']==str(current['id'])
        assert snapshots['P4']['receipt_sha256']==current['source_sha256']
        assert receipt_events[-1]['payload']['receipt_sha256']==current['source_sha256']
    assert authority(f)==before
    fresh=cp.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']))
    assert fresh['source_snapshots']==plan['source_snapshots']
    assert not fresh['new_grants'] and not fresh['automatic_execution']
    assert not fresh['case_goal_completed'] and not fresh['full_original_goal_verified']


def test_same_case_handoff_without_existing_assignment_stays_blocked(link_fixture):
    f=link_fixture;p=ready(f)
    f[1].assign_status('executor-a',UUID(p['run_id']),active=False)
    before=authority(f)
    assert create(f,p).json()['state']=='BLOCKED'
    assert check(f,p,'P1').status_code==200
    assert link(f,p,group(f)).status_code==201
    assert check(f,p,'P2').status_code==200
    baseline=records(f)
    assert offer(f,p)[0].status_code==403
    plan=read(f,p).json()
    assert plan['state']=='BLOCKED'
    assert 'EXISTING_RUN_ASSIGNMENT_REQUIRED' in plan['steps'][2]['issues']
    assert check(f,p,'P3').status_code==409
    assert records(f)==baseline and authority(f)==before


@pytest.mark.parametrize('user',[REVIEWER,'fixture-b','executor-b','unassigned'])
def test_same_case_receipt_boundary_rejects_wrong_roles_and_scope(link_fixture,user):
    f=link_fixture;p,g,d,s=through(f);baseline=records(f)
    assert f[3].get('/api/executor-receipts/'+s['step']['id'],
                     headers=headers(f[2],user)).status_code==403
    assert receipt_act(f,s,'SUBMIT',user=user).status_code==403
    assert records(f)==baseline


def test_other_case_snapshot_and_revoked_late_commands_cannot_change_chain(link_fixture):
    f=link_fixture;p,g,d,s=through(f);plan=read(f,p).json()
    other,g2,d2,s2=through(f)
    assert p['case_id']!=other['case_id'] and p['run_id']!=other['run_id']
    assert d['receipt_step_id']!=d2['receipt_step_id']
    reopened=receipt_act(f,s,'REOPEN');assert reopened.status_code==200
    assert read(f,p).json()['steps'][3]['state']=='NEEDS_RECHECK'
    baseline=records(f)
    assert receipt_act(f,s,'ACKNOWLEDGE').status_code==409
    assert records(f)==baseline
    replacement=receipt_act(f,reopened.json(),'SUBMIT',text='SYNTHETIC corrected local receipt')
    assert replacement.status_code==200
    acknowledged=receipt_act(f,replacement.json(),'ACKNOWLEDGE')
    assert acknowledged.status_code==200
    stale=read(f,p).json();baseline=records(f)
    assert stale['steps'][3]['source_ready']
    other_plan=read(f,other).json()
    assert check(f,p,'P4',row=stale,
                 expected_source_sha256=other_plan['steps'][3]['source_sha256']).status_code==409
    assert records(f)==baseline and read(f,other).json()['state']=='LOCAL_RECORDS_CHECKED'
    assert check(f,p,'P4',row=stale).status_code==200
    f[1].assign_status('executor-a',UUID(p['run_id']),active=False)
    baseline=records(f)
    assert dispatch_act(f,d,'ACCEPT').status_code==403
    assert receipt_act(f,s,'SUBMIT').status_code==403
    assert read(f,p,'executor-a').status_code==403
    assert check(f,p,'P3',row=plan).status_code==409
    assert records(f)==baseline and read(f,other).json()['state']=='LOCAL_RECORDS_CHECKED'
