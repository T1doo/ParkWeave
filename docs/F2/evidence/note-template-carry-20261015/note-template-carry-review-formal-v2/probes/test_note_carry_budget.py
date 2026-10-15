"""New carry action: actual original commands at the unchanged 64/128 bounds.

The mature legacy upgrade fixture has five required goals and P1-P5 outputs.
This verifies budgets, not the separate new six-goal acceptance fixture.
"""
from copy import deepcopy
import json,os
from pathlib import Path
from uuid import uuid4
import pytest
from test_note_template_carry import ready,request,apply
from test_template_upgrade import upgrade_case,headers
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
from test_template_migration_independent import stored,facts,recovery,all_pg_rows
from test_plan_source_conflicts import edit
from test_service_case_steps import read as plan_read,command as plan_command,verified
from test_service_plan_manual_lock import lock


def record(value):
    path=Path(__file__).resolve().parent/(os.environ['NOTE_CARRY_REVIEW_WINDOW']+'-budget-observed.jsonl')
    with path.open('a') as f:f.write(json.dumps(value,sort_keys=True)+'\n')


def advance(u,row,p,target,locked):
    desired=target-int(locked)
    now=stored(u,row)['revision']
    if (desired-now)%2:
        edit(u['f'],p,'SYNTHETIC explicit original note edit to choose legal event parity')
    while stored(u,row)['revision']<desired:
        assert lock(u['f'],p,'P1').status_code==200
        unlocked=plan_command(u['f'],p,'P1','UNLOCK');assert unlocked.status_code==200,unlocked.text
    if locked:assert lock(u['f'],p,'P1').status_code==200
    assert stored(u,row)['revision']==target


@pytest.mark.parametrize('source,revision,locked,allowed',[
    ('2',58,False,True),('2',59,False,False),
    ('1',63,False,True),('1',62,True,True),('1',63,True,False),
])
def test_new_carry_exact_apply_verify_unlock_budget(upgrade_case,source,revision,locked,allowed):
    u=upgrade_case;row,p,target=ready(u,source)
    advance(u,row,p,revision,locked)
    v,body=request(u,row,target);projection=v['application']['note_carry']
    assert projection['eligible'] is allowed,projection
    if not allowed:assert 'PLAN_EVENT_LIMIT' in projection['blockers']
    before=deepcopy(stored(u,row));business=facts(u);all_rows=all_pg_rows(u);key=uuid4().hex
    response=apply(u,row,body,key)
    assert response.status_code==(200 if allowed else 409),response.text
    if allowed:
        after=stored(u,row)
        assert after['events'][:-1]==before['events'] and after['owner_amendments']==before['owner_amendments']
        if source=='2':
            for adapter in ('P1','P2','P3','P4','P5'):verified(u['f'],p,adapter)
        else:
            assert after['steps']==before['steps']
            if locked:
                unlocked=plan_command(u['f'],p,'P1','UNLOCK');assert unlocked.status_code==200,unlocked.text
        assert stored(u,row)['revision']==64
        assert plan_read(u['f'],p).json()['state']=='VERIFIED'
        assert recovery(u,row,key).json()['event']==response.json()['event']
    else:
        assert stored(u,row)==before and all_pg_rows(u)==all_rows
        assert recovery(u,row,key).json()['status']=='NOT_OBSERVED'
        assert stored(u,row)==before
    assert facts(u)==business
    record(dict(source=source,revision_before=revision,locked=locked,allowed=allowed,
                required_affected=['P1','P2','P3','P4','P5'] if source=='2' else [],
                final_revision=stored(u,row)['revision'],HTTP_status=response.status_code,
                original_commands_only=True,fixture_required_goal_count=len(before['required_goals']),
                note_and_original_history_preserved=True,business_rows_unchanged=True))


def test_new_carry_does_not_consume_any_129th_opportunity_event(upgrade_case):
    from test_case_opportunities import imported,get as opportunities,post as opportunity_post,body as opportunity_body
    u=upgrade_case;row,p,target=ready(u)
    imported(u['f'],p)
    current=opportunities(u['f'],p).json()
    while current['revision']<128:
        refreshed=opportunity_post(u['f'],p,opportunity_body(current,'REFRESH'));assert refreshed.status_code==200,refreshed.text
        current=refreshed.json()['current']
    assert current['revision']==128
    with u['f'][1].connect() as c:ledger=c.execute('SELECT opportunities FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['opportunities']
    assert ledger['revision']==len(ledger['events'])==128
    v,body=request(u,row,target);assert v['application']['note_carry']['eligible'],v['application']['note_carry']
    before=deepcopy(stored(u,row));business=facts(u);key=uuid4().hex
    response=apply(u,row,body,key);assert response.status_code==200,response.text
    with u['f'][1].connect() as c:after=c.execute('SELECT opportunities FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['opportunities']
    assert after==ledger and facts(u)==business
    assert stored(u,row)['owner_amendments']==before['owner_amendments']
    assert recovery(u,row,key).json()['event']==response.json()['event']
    record(dict(scenario='carry_at_existing_128_event_ledger',actual_original_REFRESHS=True,
                original_opportunity_limit=128,carry_added_opportunity_events=0,
                HTTP_status=200,ledger_before_after_equal=True,cold_GET='COMMITTED',
                fixture_required_goal_count=len(before['required_goals'])))
