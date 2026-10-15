"""Separate reviewer probes for lease lifetime and original release anchors."""
from test_template_upgrade import upgrade_case, instance, publication, check, choose, headers, confirmed
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
from template_migration_test_helpers import admit, apply, recovery, stored, private_fixture_sessions
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
from uuid import uuid4
import json
import sqlite3
import psycopg
import pytest
from parkweave.template_candidate import canonical, sha


def test_independent_new_apply_rejects_rehashed_target_review(upgrade_case):
    u=upgrade_case;row,_=instance(u);confirmed(u,row)
    target=publication(u,name='SYNTHETIC independently reviewed description')
    with sqlite3.connect(u['engine'].repository.path) as c:
        doc=json.loads(c.execute('SELECT payload FROM template_releases WHERE id=?',(target['release_id'],)).fetchone()[0])
        doc['definition']['name']='SYNTHETIC injected unreviewed description'
        doc['definition_sha256']=sha(doc['definition']);doc['review']['definition_sha256']=doc['definition_sha256']
        c.execute('DROP TRIGGER immutable_template_release_payload')
        c.execute('UPDATE template_releases SET payload=?,payload_sha=? WHERE id=?',(canonical(doc),sha(doc),target['release_id']))
        c.execute(u['engine'].repository.TRIGGERS['immutable_template_release_payload'])
    target={**target,'release_sha256':sha(doc)}
    x=check(u,row,target);assert x.status_code==200,x.text
    x=x.json();assert not x['application']['eligible']
    result=choose(u,row,x,'ACK_COMPATIBLE');assert result.status_code==200,result.text
    event=result.json()['event'];plan=stored(u,row)
    data=dict(expected_instance_id=row['instance_id'],target_release_id=target['release_id'],expected_target_sha256=target['release_sha256'],expected_check_sha256=x['check_sha256'],expected_choice_revision=event['revision'],expected_choice_event_sha256=event['event_sha256'],expected_plan_id=plan['id'],expected_plan_revision=plan['revision'],expected_preparation_revision=3,expected_source_sha256=x['check']['case_state_sha256'],reason='SYNTHETIC independent original-source proof refusal')
    before=stored(u,row);r=apply(u,row,data,'proof-rehash')
    assert r.status_code in (403,409),r.text
    assert stored(u,row)==before


def test_independent_source_and_choice_leases_survive_actual_pg_commit(upgrade_case,monkeypatch):
    u=upgrade_case;row,_=instance(u);confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    original=psycopg.Connection.commit;observed=[]
    def commit(c):
        if c.info.user=='parkweave_app' and not observed:
            current=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()
            if current and current['service_case_plan']['events'][-1]['request_key']=='lease-commit':
                locks=[]
                for path in (u['engine'].repository.path,u['repository'].path):
                    test=sqlite3.connect(path,timeout=0)
                    try:
                        test.execute('BEGIN IMMEDIATE')
                        test.execute('PRAGMA user_version=0')
                        test.commit()
                        locks.append(False)
                    except sqlite3.OperationalError:
                        locks.append(True)
                    finally:test.rollback();test.close()
                observed.append(locks)
        return original(c)
    monkeypatch.setattr(psycopg.Connection,'commit',commit)
    r=apply(u,row,data,'lease-commit');assert r.status_code in (200,201),r.text
    assert observed==[[True,True]],observed


def test_independent_expiry_after_actual_owned_pg_parent_wait(upgrade_case):
    u=upgrade_case;row,_=instance(u);confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    before=stored(u,row);clock=u['engine'].clock
    with u['f'][1].connect() as blocker,ThreadPoolExecutor(max_workers=1) as pool:
        blocker.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(row['preparation_id'],))
        future=pool.submit(apply,u,row,data,'wait-expiry')
        waiting=False
        for _ in range(150):
            with u['f'][1].connect() as c:
                if c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT * FROM preparations%' AND pid<>pg_backend_pid()").fetchone():waiting=True;break
            Event().wait(.02)
        assert waiting,'actual PG parent lock wait not observed'
        u['engine'].clock=lambda:datetime(2100,1,1,tzinfo=timezone.utc)
        blocker.commit()
        response=future.result(timeout=8)
    u['engine'].clock=clock
    assert response.status_code in (403,409),response.text
    assert stored(u,row)==before


def test_independent_withdrawn_target_blocks_original_begin_without_erasing_history(upgrade_case):
    from test_template_upgrade import plan_read, plan_command
    from parkweave.template_candidate import Command
    u=upgrade_case;row,_=instance(u);p=confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    response=apply(u,row,data,'before-withdraw');assert response.status_code==200,response.text
    now=u['engine'].read('template-publisher',u['scope'])
    u['engine'].command('template-publisher',u['scope'],uuid4().hex,Command(action='WITHDRAW',expected_revision=now['revision'],expected_definition_sha256=now['definition_sha256'],reason='SYNTHETIC independent source withdrawn'))
    original=stored(u,row)
    current=plan_read(u['f'],p);assert current.status_code==200,current.text
    result=plan_command(u['f'],p,'P1','BEGIN',row=current.json())
    from pathlib import Path
    Path('.runtime/template-migration-review-20261014/begin-detail.json').write_text(json.dumps(dict(status=result.status_code,response=result.json(),plan=current.json())))
    assert result.status_code in (403,409),result.text
    assert stored(u,row)==original
    assert recovery(u,row,'before-withdraw').json()['status']=='COMMITTED'


@pytest.mark.parametrize('kind',['withdraw','revoke'])
def test_independent_source_or_authority_changes_while_actual_pg_waiting(upgrade_case,kind):
    from parkweave.template_candidate import Command
    u=upgrade_case;row,_=instance(u);confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    before=stored(u,row)
    with u['f'][1].connect() as blocker,ThreadPoolExecutor(max_workers=1) as pool:
        if kind=='revoke':u['f'][1].lock_principal(blocker,'fixture-a',exclusive=True)
        else:blocker.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(row['preparation_id'],))
        future=pool.submit(apply,u,row,data,'wait-'+kind)
        waiting=False
        for _ in range(150):
            with u['f'][1].connect() as c:
                if c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND usename='parkweave_app' AND wait_event_type='Lock' AND pid<>pg_backend_pid()").fetchone():waiting=True;break
            Event().wait(.02)
        assert waiting,'actual owned PG lock wait not observed'
        if kind=='revoke':blocker.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        else:
            now=u['engine'].read('template-publisher',u['scope'])
            u['engine'].command('template-publisher',u['scope'],uuid4().hex,Command(action='WITHDRAW',expected_revision=now['revision'],expected_definition_sha256=now['definition_sha256'],reason='SYNTHETIC withdraw while PG parent wait'))
        blocker.commit();response=future.result(timeout=8)
    assert response.status_code in (403,409),response.text
    assert stored(u,row)==before


def test_independent_original_command_commit_expiry_rolls_back_saved_event(upgrade_case,monkeypatch):
    from parkweave.store import _AccessConnection
    from test_template_upgrade import plan_read, plan_command
    u=upgrade_case;row,_=instance(u);p=confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    assert apply(u,row,data,'command-base').status_code==200
    current=plan_read(u['f'],p).json();before=stored(u,row);clock=u['engine'].clock
    original=_AccessConnection.commit;observed=[]
    def commit(c):
        if not observed and c.info.user=='parkweave_app':
            state=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()
            if state and state['service_case_plan']['events'][-1]['request_key']=='commit-expiry-begin':
                observed.append(bool(getattr(c,'_template_source_leases',{})))
                u['engine'].clock=lambda:datetime(2100,1,1,tzinfo=timezone.utc)
        return original(c)
    monkeypatch.setattr(_AccessConnection,'commit',commit)
    result=plan_command(u['f'],p,'P1','BEGIN',row=current,key='commit-expiry-begin')
    u['engine'].clock=clock
    assert observed==[True],observed
    assert result.status_code in (403,409),result.text
    assert stored(u,row)==before
    assert recovery(u,row,'command-base').json()['status']=='COMMITTED'


def test_independent_original_business_gate_holds_source_until_actual_pg_commit(upgrade_case,monkeypatch):
    from template_migration_test_helpers import full, verified, ALL
    from test_case_lifecycle import read as lifecycle_read, act as lifecycle_act
    from parkweave.template_candidate import Command
    u=upgrade_case;row,_,p=full(u);target=publication(u,[__import__('test_template_upgrade').GOALS[-1]],source='2')
    _,data=admit(u,row,target);assert apply(u,row,data,'business-base').status_code==200
    for adapter in ALL:verified(u['f'],p,adapter)
    current=lifecycle_read(u['f'],p).json();head=u['engine'].read('template-publisher',u['scope'])
    original=psycopg.Connection.commit;started=Event();finished=Event();pg_committed=Event();observation=[];futures=[]
    with ThreadPoolExecutor(max_workers=1) as pool:
        def withdraw():
            started.set()
            result=u['engine'].command('template-publisher',u['scope'],uuid4().hex,Command(action='WITHDRAW',expected_revision=head['revision'],expected_definition_sha256=head['definition_sha256'],reason='SYNTHETIC publisher waiting for original business PG commit'))
            assert pg_committed.is_set(),'publisher proceeded before original business PG COMMIT'
            finished.set();return result
        def commit(c):
            if c.info.user=='parkweave_app' and not observation:
                found=c.execute("SELECT 1 FROM case_local_lifecycles WHERE preparation_id=%s AND state='LOCAL_RECORD_CLOSED'",(row['preparation_id'],)).fetchone()
                if found:
                    assert getattr(c,'_template_source_leases',{}),'original business gate missing source lease'
                    futures.append(pool.submit(withdraw))
                    assert started.wait(2)
                    assert not finished.wait(.1),'withdraw did not wait for actual PG COMMIT'
                    observation.append('SOURCE_HELD_BEFORE_ACTUAL_PG_COMMIT')
                    result=original(c);pg_committed.set();return result
            return original(c)
        monkeypatch.setattr(psycopg.Connection,'commit',commit)
        response=lifecycle_act(u['f'],p,current,'CLOSE_LOCAL_RECORD')
        assert response.status_code==200,response.text
        assert observation==['SOURCE_HELD_BEFORE_ACTUAL_PG_COMMIT']
        assert futures[0].result(timeout=5)['state']=='WITHDRAWN'
    assert finished.is_set()
    with u['f'][1].connect() as c:
        assert c.execute("SELECT state FROM case_local_lifecycles WHERE preparation_id=%s",(row['preparation_id'],)).fetchone()['state']=='LOCAL_RECORD_CLOSED'
    assert recovery(u,row,'business-base').json()['status']=='COMMITTED'


@pytest.mark.parametrize('damage',['origin_database','unexpected_patch','effective_target','choice_reason'])
def test_independent_migration_original_request_proofs_refuse_tampered_copy(upgrade_case,damage):
    from copy import deepcopy
    from parkweave import service_case_steps as steps
    from parkweave.store import Conflict
    u=upgrade_case;row,_=instance(u);confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    assert apply(u,row,data,'tamper-base').status_code==200
    original=stored(u,row);plan=deepcopy(original);patch=plan['events'][-1]['template_upgrade']
    if damage=='origin_database':patch['origin_binding']['database_name']='fixture_'+'0'*32
    elif damage=='unexpected_patch':patch['synthetic_extra_unproven_authority']=True
    elif damage=='effective_target':plan['template_migration']['release']['release_id']=str(uuid4())
    else:
        patch['choice']['reason']='SYNTHETIC substituted old choice reason'
        patch['choice']['event_sha256']=sha({k:v for k,v in patch['choice'].items() if k!='event_sha256'})
    with u['f'][1].connect() as c:parent=c.execute('SELECT * FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()
    with pytest.raises(Conflict):steps._recovery_proofs({**parent,'service_case_plan':plan})
    assert stored(u,row)==original


def test_independent_code_rollback_reader_refuses_new_event_preserving_business(upgrade_case):
    from pathlib import Path
    import types
    from parkweave.store import Conflict
    from template_migration_test_helpers import full,facts
    u=upgrade_case;row,_,p=full(u);target=publication(u,[__import__('test_template_upgrade').GOALS[-1]],source='2');_,data=admit(u,row,target)
    assert apply(u,row,data,'rollback-reader-base').status_code==200
    before=facts(u);original=stored(u,row)
    with u['f'][1].connect() as c:parent=c.execute('SELECT * FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()
    old=types.ModuleType('parkweave._old_service_case_steps');old.__package__='parkweave'
    exec(compile(Path('.runtime/template-migration-review-20261014/old-service-case-steps.py').read_text(),'old-service-case-steps.py','exec'),old.__dict__)
    with pytest.raises(Conflict):old._recovery_proofs(parent)
    assert stored(u,row)==original and facts(u)==before


@pytest.mark.parametrize('unavailable',['withdraw','expiry','unmounted'])
def test_independent_unavailable_effective_target_is_history_not_current_verification(upgrade_case,unavailable):
    from template_migration_test_helpers import full
    from test_template_upgrade import plan_read
    from test_case_goal_results import get as goal_results
    from parkweave.template_candidate import Command
    u=upgrade_case;row,_,p=full(u);target=publication(u,[__import__('test_template_upgrade').GOALS[-1]],source='1',name='SYNTHETIC new description same source')
    _,data=admit(u,row,target,'ACK_COMPATIBLE');assert apply(u,row,data,'current-target-base').status_code==200
    original=stored(u,row);clock=u['engine'].clock
    if unavailable=='withdraw':
        head=u['engine'].read('template-publisher',u['scope'])
        u['engine'].command('template-publisher',u['scope'],uuid4().hex,Command(action='WITHDRAW',expected_revision=head['revision'],expected_definition_sha256=head['definition_sha256'],reason='SYNTHETIC current target no longer available'))
    elif unavailable=='expiry':u['engine'].clock=lambda:datetime(2100,1,1,tzinfo=timezone.utc)
    else:delattr(u['f'][0],'_isolated_template_migration_checker')
    page=plan_read(u['f'],p);assert page.status_code==200,page.text
    assert page.json()['state']!='VERIFIED',page.text
    goals=goal_results(u['f'],p);assert goals.status_code==200,goals.text
    assert goals.json()['state']!='LOCAL_OUTPUTS_VERIFIED',goals.text
    assert stored(u,row)==original
    assert recovery(u,row,'current-target-base').json()['status']=='COMMITTED'
    u['engine'].clock=clock


@pytest.mark.parametrize('endpoint',['plan','goals'])
def test_independent_read_currentness_rechecked_after_last_owned_pg_source_wait(upgrade_case,endpoint):
    from template_migration_test_helpers import full
    from test_template_upgrade import plan_read
    from test_case_goal_results import get as goal_results
    u=upgrade_case;row,_,p=full(u);target=publication(u,[__import__('test_template_upgrade').GOALS[-1]],source='1',name='SYNTHETIC description with timed currentness')
    _,data=admit(u,row,target,'ACK_COMPATIBLE');assert apply(u,row,data,'timed-read-base').status_code==200
    original=stored(u,row);clock=u['engine'].clock
    with u['f'][1].connect() as blocker,ThreadPoolExecutor(max_workers=1) as pool:
        blocker.execute('SELECT preparation_id FROM case_local_lifecycles WHERE preparation_id=%s FOR UPDATE',(row['preparation_id'],))
        future=pool.submit(plan_read if endpoint=='plan' else goal_results,u['f'],p)
        waiting=False
        for _ in range(150):
            with u['f'][1].connect() as c:
                if c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND usename='parkweave_app' AND wait_event_type='Lock' AND query LIKE 'SELECT * FROM case_local_lifecycles%' AND pid<>pg_backend_pid()").fetchone():waiting=True;break
            Event().wait(.02)
        assert waiting,'actual late lifecycle PG source wait not observed'
        u['engine'].clock=lambda:datetime(2100,1,1,tzinfo=timezone.utc)
        blocker.commit();response=future.result(timeout=8)
    u['engine'].clock=clock
    assert response.status_code==200,response.text
    assert response.json()['state'] not in ('VERIFIED','LOCAL_OUTPUTS_VERIFIED'),response.text
    assert stored(u,row)==original


@pytest.mark.parametrize('bad_key',['other_canonical_instance','arbitrary_colon','noninitial_colon'])
def test_independent_legacy_upgrade_goal_history_proof_and_narrow_key_refusal(upgrade_case,bad_key):
    from copy import deepcopy
    from test_case_goal_results import get as goal_results
    from parkweave.case_goal_results import structure
    from parkweave.store import Conflict
    u=upgrade_case;row,_=instance(u,legacy=True);p=confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    assert apply(u,row,data,'legacy-independent-base').status_code==200
    result=goal_results(u['f'],p);assert result.status_code==200,result.text
    original=stored(u,row);assert original['events'][0]['request_key']=='tc:'+row['instance_id']+':ADOPT_PLAN'
    with u['f'][1].connect() as c:parent=c.execute('SELECT * FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()
    changed=deepcopy(original)
    if bad_key=='other_canonical_instance':changed['events'][0]['request_key']='tc:'+str(uuid4())+':ADOPT_PLAN'
    elif bad_key=='arbitrary_colon':changed['events'][0]['request_key']='tc:not-an-original-instance:ADOPT_PLAN'
    else:changed['events'][-1]['request_key']='tc:'+row['instance_id']+':ADOPT_PLAN'
    with pytest.raises(Conflict):structure(changed,parent={**parent,'service_case_plan':changed})
    assert stored(u,row)==original
