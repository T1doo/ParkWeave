"""Actual scoped persistence, migration compatibility and proposal invalidation."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from pathlib import Path
import pytest
from parkweave.store import Store
from parkweave import controlled_plans as cp
from test_preparation import preparation_fixture,create as prepare,headers,read as materials
from test_plan_preview import digest,preview,GOAL
from test_executor_receipts import receipt_fixture
from test_controlled_plans import create as adopt,read as plan_read,check,link_fixture,through

def save(f,p,text='SYNTHETIC 用户明确修订诉求',goals=None,key=None,user='fixture-a',revision=None):
    return f[3].post('/api/preparations/'+p['preparation_id']+'/request-intent',headers=headers(f[2],user,key or uuid4().hex),
      json={'expected_preparation_revision':p['revision'] if revision is None else revision,'request_text':text,'required_goals':goals if goals is not None else [GOAL]})

def test_persistent_partial_coverage_original_request_and_readback(preparation_fixture):
    f=preparation_fixture;p,_,_=prepare(f);original=plan_read(f,p).json()['request_intent'];assert not original['recorded'] and original['required_goals']==[]
    key=uuid4().hex;r=save(f,p,goals=[GOAL,'外部机构受理回执'],key=key);assert r.status_code==200,r.text
    v=r.json()['request_intent'];assert v['original_request']==original['original_request'] and v['current_request']!=''
    assert v['coverage']['state']=='PARTIAL' and v['coverage']['unsupported_goals']==['外部机构受理回执']
    assert not v['coverage']['original_request_understood'] and not v['coverage']['original_case_goal_completed']
    assert save(f,p,goals=[GOAL,'外部机构受理回执'],key=key).json()==r.json()
    current=plan_read(f,p).json();assert current['request_intent']==v and not current['can_create']
    assert preview(f,p,[GOAL,'外部机构受理回执']).json()['state']=='PARTIAL'
    assert preview(f,p,[GOAL]).status_code==409 and adopt(f,{**p,'revision':v['revision']}).status_code==409
    with f[1].connect() as c:
        assert c.execute('SELECT goal,state FROM cases WHERE id=%s',(p['case_id'],)).fetchone()=={'goal':original['original_request'],'state':'NEEDS_INPUT'}
        assert not c.execute('SELECT 1 FROM run_assignments WHERE run_id=%s',(p['run_id'],)).fetchone()
    assert materials(f,p).json()['history'][-1]['payload']['request_intent']==v
    fresh=cp.read(Store(f[0].dsn),f[2]['fixture-a'],p['preparation_id']);assert fresh['request_intent']==v

def test_changed_request_or_goals_invalidates_preview_and_material_confirmation(preparation_fixture):
    f=preparation_fixture;p,_,_=prepare(f);x=preview(f,p).json()
    r=save(f,p).json();p={**p,'revision':r['revision']}
    assert adopt(f,p,expected_preview_sha256=x['preview_sha256']).status_code==409
    current=preview(f,p).json();assert current['request_intent']['current_request']=='SYNTHETIC 用户明确修订诉求'
    r=save(f,p,text='SYNTHETIC 再次修订',goals=[]).json();p={**p,'revision':r['revision']}
    x=preview(f,p,[]).json();assert x['state']=='UNKNOWN' and not x['can_adopt'] and x['required_goals']==[]
    assert adopt(f,p,expected_preview_sha256=current['preview_sha256']).status_code==409
    assert materials(f,p).json()['preparation']['state']=='IN_PREPARATION'

def test_changed_goals_invalidate_existing_checked_plan_without_discarding_business(link_fixture):
    f=link_fixture;p,g,d,s=through(f)
    before=plan_read(f,p).json();r=save(f,p,goals=[GOAL,'必须真实线下履约']).json()
    after=plan_read(f,p).json();assert before['state']=='LOCAL_RECORDS_CHECKED' and after['state']=='BLOCKED'
    assert after['revision']==before['revision'] and after['history']==before['history']
    assert after['steps'][0]['state']=='NEEDS_RECHECK' and not after['steps'][0]['can_check']
    assert after['request_intent']['coverage']['state']=='PARTIAL'
    assert check(f,p,'P1',row=after).status_code==409
    with f[1].connect() as c:
        assert c.execute('SELECT checked FROM controlled_plans WHERE preparation_id=%s',(p['preparation_id'],)).fetchone()['checked']
        assert c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=%s',(g['id'],)).fetchone()['state']=='CONFIRMED'
        assert c.execute('SELECT count(*) n FROM service_step_receipts r JOIN service_receipt_steps s ON s.id=r.step_id WHERE s.preparation_id=%s',(p['preparation_id'],)).fetchone()['n']>=1

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_cross_case_role_write_denied_and_private_owner_text_hidden(preparation_fixture,user):
    f=preparation_fixture;p,_,_=prepare(f);r=save(f,p,text='SYNTHETIC OWNER_PRIVATE_ENG085',goals=[GOAL,'PRIVATE_TARGET_ENG085']);assert r.status_code==200
    before=digest(f);assert save(f,{**p,'revision':r.json()['revision']},user=user).status_code==403 and digest(f)==before
    if user=='prep-specialist-fixture-a':
        detail=materials(f,p,user);row=plan_read(f,p,user)
        assert detail.status_code==200 and row.status_code==200
        assert 'OWNER_PRIVATE_ENG085' not in detail.text+row.text and 'PRIVATE_TARGET_ENG085' not in detail.text+row.text
        assert row.json()['request_intent'] is None and row.json()['request_coverage_state']=='PARTIAL'

def test_stale_concurrent_save_conflict_and_same_key_replay(preparation_fixture):
    f=preparation_fixture;p,_,_=prepare(f);key=uuid4().hex
    with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda _:save(f,p,key=key),range(2)))
    assert [r.status_code for r in rs]==[200,200] and rs[0].json()==rs[1].json()
    assert save(f,p,text='SYNTHETIC stale changed text').status_code==409
    assert save(f,p,key=key,text='SYNTHETIC same-key mismatch').status_code==409

def test_additive_v18_upgrade_and_repeat_migration_preserves_history_and_grants(preparation_fixture):
    f=preparation_fixture;p,_,_=prepare(f)
    with f[1].connect() as c:
        history=c.execute('SELECT * FROM preparation_events').fetchall()
        grants=c.execute('SELECT * FROM capability_grants ORDER BY principal_id,capability').fetchall()
        c.execute('ALTER TABLE preparations DROP COLUMN request_intent')
        c.execute('DELETE FROM schema_version WHERE version=19')
    f[1].migrate();f[1].migrate()
    with f[1].connect() as c:
        assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']==19
        assert c.execute('SELECT * FROM preparation_events').fetchall()==history
        assert c.execute('SELECT * FROM capability_grants ORDER BY principal_id,capability').fetchall()==grants
        assert c.execute('SELECT request_intent FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['request_intent'] is None
    assert plan_read(f,p).json()['request_intent']['required_goals']==[]
    assert adopt(f,p).status_code==201  # existing fixed-support API remains compatible for legacy data


def test_case_bound_preview_and_save_key_not_reused_across_cases(preparation_fixture):
    f=preparation_fixture;a,_,_=prepare(f);b,_,_=prepare(f);key=uuid4().hex
    r=save(f,a,key=key);assert r.status_code==200
    assert save(f,b,key=key).status_code==409
    a={**a,'revision':r.json()['revision']};x=preview(f,a).json()
    assert adopt(f,b,expected_preview_sha256=x['preview_sha256']).status_code==409
    assert not plan_read(f,b).json()['request_intent']['recorded']


def test_saved_coverage_stale_template_is_visible_and_not_adoptable(preparation_fixture,monkeypatch):
    f=preparation_fixture;p,_,_=prepare(f);r=save(f,p).json();p={**p,'revision':r['revision']}
    monkeypatch.setattr(cp,'TEMPLATE_SHA','f'*64)
    x=plan_read(f,p).json();assert x['request_coverage_state']=='STALE' and x['request_intent']['coverage']['state']=='STALE'
    assert not x['can_create'] and not preview(f,p).json()['can_adopt']


def test_request_update_rollback_keeps_prior_request_and_material_history(preparation_fixture,monkeypatch):
    from parkweave import preparation as prep
    f=preparation_fixture;p,_,_=prepare(f);before=digest(f)
    def failed_event(*a,**kw):raise RuntimeError('SYNTHETIC_EVENT_FAILURE')
    monkeypatch.setattr(prep,'event',failed_event)
    with pytest.raises(RuntimeError,match='SYNTHETIC_EVENT_FAILURE'):save(f,p)
    assert digest(f)==before and not plan_read(f,p).json()['request_intent']['recorded']


def test_executor_cannot_read_or_edit_private_request_intent(link_fixture):
    f=link_fixture;p,g,d,s=through(f);r=save(f,p,text='SYNTHETIC PRIVATE_EXECUTOR_REQUEST',goals=[GOAL,'PRIVATE_EXECUTOR_TARGET']);assert r.status_code==200
    before=digest(f);assert save(f,{**p,'revision':r.json()['revision']},user='executor-a').status_code==403 and digest(f)==before
    x=plan_read(f,p,'executor-a');assert x.status_code==200 and x.json()['request_intent'] is None
    assert 'PRIVATE_EXECUTOR_REQUEST' not in x.text and 'PRIVATE_EXECUTOR_TARGET' not in x.text


@pytest.mark.parametrize('capability',['READ','EXECUTE','PREPARE'])
def test_current_authority_revocation_refuses_save_without_business_change(preparation_fixture,capability):
    f=preparation_fixture;p,_,_=prepare(f);r=save(f,p);assert r.status_code==200
    p={**p,'revision':r.json()['revision']}
    with f[1].connect() as c:
        table='preparation_grants' if capability=='PREPARE' else 'capability_grants'
        c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(capability,))
    before=digest(f)
    assert save(f,p,text='SYNTHETIC unauthorized revised request').status_code==403 and digest(f)==before
