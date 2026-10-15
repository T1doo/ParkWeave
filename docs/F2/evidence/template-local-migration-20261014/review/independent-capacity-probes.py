"""Original PG command capacity: reject revisions that cannot finish rechecking."""
from copy import deepcopy
from uuid import uuid4
import pytest

from test_template_upgrade import upgrade_case, publication, plan_read, plan_command, snapshot, GOALS
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
import test_template_migration_independent as helper
from test_template_migration_independent import private_fixture_sessions, stored, admit, apply, ALL
from parkweave.template_consumer import normal, canonical


def all_pg_rows(u):
    with u['f'][1].connect() as c:
        tables=[r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
        return {t:sorted(normal(c.execute('SELECT * FROM '+t).fetchall()),key=canonical) for t in tables}


def unchanged_except_current_plan(before,after,preparation_id):
    projected=deepcopy(after)
    original=next(r for r in before['preparations'] if r['id']==preparation_id)
    current=next(r for r in projected['preparations'] if r['id']==preparation_id)
    current['service_case_plan']=deepcopy(original['service_case_plan'])
    projected['preparations'].sort(key=canonical)
    assert projected==before, 'a PG row outside the one allowed current-plan field changed'


def fill_with_original_lock_unlock(u,p,target_revision):
    current=plan_read(u['f'],p).json()
    assert (target_revision-current['revision'])%2==0 and current['revision']<=target_revision
    for _ in range((target_revision-current['revision'])//2):
        current=plan_read(u['f'],p).json();first=current['steps'][0]
        locked=plan_command(u['f'],p,'P1','LOCK',row=current,expected_source_sha256=first['source_sha256'])
        assert locked.status_code==200,locked.text
        unlocked=plan_command(u['f'],p,'P1','UNLOCK',row=locked.json())
        assert unlocked.status_code==200,unlocked.text
    current=plan_read(u['f'],p).json()
    assert current['revision']==target_revision and not any(s['manually_locked'] for s in current['steps'])


@pytest.mark.parametrize('pre_revision',[58,62])
def test_source_upgrade_reserves_all_affected_verify_slots(upgrade_case,monkeypatch,pre_revision):
    u=upgrade_case;real_verified=helper.verified
    # Genuine original in-flight business output. Only the owner's first P5
    # VERIFY is left pending; no plan/events/locks are rewritten through SQL.
    with monkeypatch.context() as m:
        m.setattr(helper,'verified',lambda f,p,a:plan_read(f,p).json() if a=='P5' else real_verified(f,p,a))
        row,_,p=helper.full(u)
    assert stored(u,row)['revision']==6
    fill_with_original_lock_unlock(u,p,pre_revision)
    target=publication(u,GOALS,source='2')
    view,data=admit(u,row,target)
    assert len(view['application']['affected'])==5
    original=deepcopy(stored(u,row));before=all_pg_rows(u);consumer_before=snapshot(u)[1]
    response=apply(u,row,data,'capacity-source-'+str(pre_revision))
    if pre_revision==62:
        assert response.status_code==409,response.text
        assert view['application']['eligible'] is False
        assert all_pg_rows(u)==before, 'rejected upgrade must leave every PG row unchanged, including audit'
        assert stored(u,row)==original
    else:
        assert response.status_code==200,response.text
        assert response.json()['event']['revision']==59
        for adapter in ALL:real_verified(u['f'],p,adapter)
        current=plan_read(u['f'],p).json()
        assert current['revision']==64 and current['state']=='VERIFIED'
        saved=stored(u,row)
        assert saved['id']==original['id']
        assert [s['id'] for s in saved['steps']]==[s['id'] for s in original['steps']]
        assert [s['contract'] for s in saved['steps']]==[s['contract'] for s in original['steps']]
        assert saved['events'][:len(original['events'])]==original['events']
        assert saved.get('history',[])==original.get('history',[])
        unchanged_except_current_plan(before,all_pg_rows(u),row['preparation_id'])
    assert snapshot(u)[1]==consumer_before, 'immutable original consumer rows/stages must not change'


def test_verified_description_upgrade_uses_last_slot_without_reverify(upgrade_case):
    u=upgrade_case;row,_,p=helper.full(u)
    assert stored(u,row)['revision']==7
    fill_with_original_lock_unlock(u,p,63)
    target=publication(u,GOALS,source='1',name='SYNTHETIC description only at final event slot')
    view,data=admit(u,row,target,'ACK_COMPATIBLE')
    assert view['application']['affected']==[] and view['application']['eligible'] is True
    original=deepcopy(stored(u,row));before=all_pg_rows(u);consumer_before=snapshot(u)[1]
    response=apply(u,row,data,'capacity-description-final')
    assert response.status_code==200,response.text
    saved=stored(u,row);current=plan_read(u['f'],p).json()
    assert saved['revision']==64 and current['state']=='VERIFIED'
    assert saved['steps']==original['steps']
    assert saved['events'][:63]==original['events']
    assert saved.get('history',[])==original.get('history',[])
    unchanged_except_current_plan(before,all_pg_rows(u),row['preparation_id'])
    assert snapshot(u)[1]==consumer_before
