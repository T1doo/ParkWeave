"""The original event budget admits a complete recheck or rejects before Apply."""
from copy import deepcopy
from uuid import uuid4

import pytest
import test_template_migration_independent as original
from test_template_migration_independent import private_fixture_sessions
from test_template_upgrade import upgrade_case, publication, plan_read, plan_command, headers, GOALS
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture


def in_flight(u, monkeypatch):
    # Real original business outputs; P5 awaits its first owner VERIFY. This
    # gives the legal even revision needed to exercise the exact 58 boundary.
    verify=original.verified
    with monkeypatch.context() as m:
        m.setattr(original,'verified',lambda f,p,a:plan_read(f,p).json() if a=='P5' else verify(f,p,a))
        row,_,p=original.full(u)
    assert original.stored(u,row)['revision']==6
    return row,p


def advance(u,p,revision):
    current=plan_read(u['f'],p).json()
    assert (revision-current['revision'])%2==0
    while current['revision']<revision:
        step=current['steps'][0]
        result=plan_command(u['f'],p,'P1','LOCK',row=current,expected_source_sha256=step['source_sha256'])
        assert result.status_code==200,result.text
        result=plan_command(u['f'],p,'P1','UNLOCK',row=result.json())
        assert result.status_code==200,result.text
        current=result.json()
    assert current['revision']==revision


@pytest.mark.parametrize('revision',[58,60,62])
def test_source_upgrade_reserves_every_affected_verify_before_adoption(upgrade_case,monkeypatch,revision):
    u=upgrade_case;row,p=in_flight(u,monkeypatch);advance(u,p,revision)
    target=publication(u,GOALS,source='2')
    view,data=original.admit(u,row,target)
    assert len(view['application']['affected'])==5
    before=deepcopy(original.stored(u,row));all_rows=original.all_pg_rows(u);business=original.facts(u)
    key=uuid4().hex;result=original.apply(u,row,data,key)
    if revision==58:
        assert view['application']['eligible']
        assert result.status_code==200,result.text
        for adapter in original.ALL:original.verified(u['f'],p,adapter)
        current=plan_read(u['f'],p).json()
        assert current['revision']==64 and current['state']=='VERIFIED'
        goals=u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(u['f'][2]))
        assert goals.status_code==200 and goals.json()['state']=='LOCAL_OUTPUTS_VERIFIED',goals.text
    else:
        assert not view['application']['eligible'] and 'PLAN_EVENT_LIMIT' in view['application']['blockers']
        assert result.status_code==409,result.text
        assert original.stored(u,row)==before and original.all_pg_rows(u)==all_rows
        assert original.recovery(u,row,key).json()['status']=='NOT_OBSERVED'
    assert original.facts(u)==business


def test_description_upgrade_can_use_last_event_when_outputs_already_verified(upgrade_case):
    u=upgrade_case;row,_,p=original.full(u);advance(u,p,63)
    target=publication(u,GOALS,source='1',name='Synthetic description at the last available event')
    view,data=original.admit(u,row,target,'ACK_COMPATIBLE')
    before=deepcopy(original.stored(u,row));business=original.facts(u)
    assert view['application']['eligible'] and view['application']['affected']==[]
    result=original.apply(u,row,data,uuid4().hex)
    assert result.status_code==200,result.text
    current=plan_read(u['f'],p).json()
    assert current['revision']==64 and current['state']=='VERIFIED'
    assert original.stored(u,row)['steps']==before['steps'] and original.facts(u)==business


def test_description_upgrade_still_reserves_original_unlock_capacity(upgrade_case,monkeypatch):
    u=upgrade_case;row,p=in_flight(u,monkeypatch);advance(u,p,62)
    current=plan_read(u['f'],p).json();step=current['steps'][0]
    result=plan_command(u['f'],p,'P1','LOCK',row=current,expected_source_sha256=step['source_sha256'])
    assert result.status_code==200 and result.json()['revision']==63,result.text
    target=publication(u,GOALS,source='1',name='Synthetic description preserves the active owner lock')
    view,data=original.admit(u,row,target,'ACK_COMPATIBLE');before=original.all_pg_rows(u)
    assert view['application']['affected']==[] and 'PLAN_EVENT_LIMIT' in view['application']['blockers']
    assert original.apply(u,row,data,uuid4().hex).status_code==409
    assert original.all_pg_rows(u)==before
    # Rejection did not consume the event reserved by the original lock action.
    current=plan_read(u['f'],p).json()
    unlocked=plan_command(u['f'],p,'P1','UNLOCK',row=current)
    assert unlocked.status_code==200 and unlocked.json()['revision']==64,unlocked.text
