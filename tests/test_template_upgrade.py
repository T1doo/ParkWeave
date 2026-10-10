"""Actual PG / HTTP inspection, immutable decisions and preserved business history."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import sqlite3
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict
import pytest

from parkweave.template_candidate import TemplateEngine, TemplateRepository, Scope, Command, draft_for_goals
from parkweave.template_consumer import TemplateConsumer, ConsumerConfig, ConsumerRepository
from parkweave.template_isolated_app import create_isolated_template_app
from parkweave.template_upgrade import TemplateUpgradeChecker, UpgradeRepository
from parkweave.store import Conflict, Denied
from test_template_candidate import template_config, definition, VALID
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture, act as receipt_act
from test_preparation import preparation_fixture, command as preparation_act, headers
from test_service_case_steps import accepted, verified, business, read as plan_read, command as plan_command, GOALS


@pytest.fixture
def upgrade_case(link_fixture, tmp_path):
    f = link_fixture
    config = template_config().model_dump()
    for permit in config['permits']: permit['scope']['park_id'] = 'park-a'
    from parkweave.template_candidate import TemplateConfig
    engine = TemplateEngine(TemplateConfig.model_validate(config), TemplateRepository(tmp_path/'upgrade.template.candidate.sqlite3'), lambda: datetime(2026,10,10,tzinfo=timezone.utc))
    scope = Scope(park_id='park-a', template_id='new-enterprise-material-template')
    consumer = TemplateConsumer(f[0], engine, ConsumerConfig(enabled_for_isolated_tests=True,
        allowed_database_names=[conninfo_to_dict(f[0].dsn)['dbname']], allowed_orgs=[{'park_id':'park-a','org_id':'org-a'}]), ConsumerRepository(tmp_path/'upgrade.consumer.candidate.sqlite3'))
    repository = UpgradeRepository(tmp_path/'check.upgrade.candidate.sqlite3')
    checker = TemplateUpgradeChecker(consumer, repository, enabled_for_isolated_tests=True)
    with TestClient(create_isolated_template_app(f[0], engine, consumer, checker)) as client:
        yield dict(f=f,engine=engine,consumer=consumer,checker=checker,repository=repository,client=client,scope=scope)


def publication(u, goals=None, source='1', name='Synthetic template version'):
    e=u['engine']; s=u['scope']; view=e.read('template-author',s)
    def act(action, actor='template-author', **fields):
        current=e.read(actor,s)
        return e.command(actor,s,uuid4().hex,Command.model_validate(dict(action=action,expected_revision=current['revision'],expected_definition_sha256=current['definition_sha256'],reason='Explicit synthetic version operation',**fields)))
    if view['state']!='NOT_CREATED': act('RETURN_DRAFT')
    draft=definition(goals,source); draft.name=name
    act('SAVE_DRAFT',draft=draft); act('SUBMIT'); act('REVIEW','template-reviewer'); act('CANDIDATE_PUBLISH','template-publisher',validity=VALID)
    return e.public_catalog('park-a')['items'][0]


def instance(u, goals=None, legacy=False):
    r=publication(u,goals)
    data=dict(release_id=r['release_id'],expected_release_sha256=r['release_sha256'],goal='SYNTHETIC PRIVATE_UPGRADE_CASE',reviewer_id='prep-specialist-fixture-a',
        materials=[dict(slot=s,text='SYNTHETIC PRIVATE_UPGRADE_MATERIAL '+s,source_kind='USER_STATEMENT',source_label='Synthetic current input') for s in ('need_summary','material_outline')],reason='Explicit original instance')
    response=u['client'].post('/api/template-consumer/instances',headers=headers(u['f'][2],key=uuid4().hex),json=data)
    assert response.status_code==201,response.text
    row=response.json();u['f'][0].finish(u['f'][0].claim('template-upgrade-case'))
    from unittest.mock import patch
    from parkweave.template_consumer import canonical, normal
    from parkweave.store import digest
    original=u['consumer']._perform
    def perform(token,inst,name,build,send):
        if legacy and name=='ADOPT_PLAN':
            body=normal(build());key='tc:'+inst['id']+':'+name
            with u['consumer'].repository.connect(write=True) as c:
                c.execute('INSERT INTO consumer_stages VALUES(?,?,?,?,?,?,NULL,NULL)',(inst['id'],name,key,digest(canonical(body)),canonical(body),'STARTED'))
        return original(token,inst,name,build,send)
    with patch.object(u['consumer'],'_perform',perform):
        response=u['client'].post('/api/template-consumer/instances/'+row['instance_id']+'/resume',headers=headers(u['f'][2],key=uuid4().hex),json={})
    assert response.status_code==200,response.text
    return response.json(),r


def check(u,row,target,user='fixture-a'):
    return u['client'].get('/api/template-upgrade/'+row['instance_id']+'/check',headers=headers(u['f'][2],user),params=dict(target_release_id=target['release_id'],target_sha256=target['release_sha256']))


def selection(x,choice='KEEP_CURRENT'):
    return dict(target_release_id=x['check']['target_release_id'],expected_target_sha256=x['check']['target_release_sha256'],expected_check_sha256=x['check_sha256'],expected_revision=x['revision'],choice=choice,reason='Explicit synthetic selection preserves old data')


def choose(u,row,x,choice='KEEP_CURRENT',key=None,user='fixture-a',**fields):
    return u['client'].post('/api/template-upgrade/'+row['instance_id']+'/choices',headers=headers(u['f'][2],user,key or uuid4().hex),json={**selection(x,choice),**fields})


def recover(u,row,key,user='fixture-a'):
    return u['client'].get('/api/template-upgrade/'+row['instance_id']+'/requests/'+key,headers=headers(u['f'][2],user))


def snapshot(u):
    with u['f'][1].connect() as c:
        # Include all product history and permissions, not only row counts.
        tables=[r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'authorization_audit' ORDER BY tablename")]
        pg={t:c.execute('SELECT * FROM '+t+' ORDER BY to_jsonb('+t+')::text').fetchall() for t in tables}
    with u['consumer'].repository.connect() as c:
        consumer={t:[tuple(r) for r in c.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in u['consumer'].repository.COLUMNS}
    return pg,consumer


@pytest.mark.parametrize('goals,source,status',[(None,'1','COMPATIBLE'),(GOALS[:2],'1','NEEDS_RECHECK'),(None,'2','NEEDS_RECHECK')])
def test_classification_and_explicit_choices_never_change_old_binding_or_product(upgrade_case,goals,source,status):
    u=upgrade_case;row,old=instance(u);target=publication(u,goals,source,'Updated synthetic description')
    before=snapshot(u);x=check(u,row,target);assert x.status_code==200,x.text;x=x.json()
    assert x['check']['classification']==status and snapshot(u)==before
    result=choose(u,row,x,'ACK_COMPATIBLE' if status=='COMPATIBLE' else 'REQUEST_RECHECK')
    assert result.status_code==200,result.text
    assert result.json()['event']['check']['original_release_id']==old['release_id']
    assert snapshot(u)==before and not result.json()['migration_performed']
    # Superseded original release stays historical and cannot be resumed.
    assert u['client'].post('/api/template-consumer/instances/'+row['instance_id']+'/resume',headers=headers(u['f'][2],key=uuid4().hex),json={}).status_code==403


def test_breaking_goal_removal_and_definition_rollback_are_refused(upgrade_case):
    u=upgrade_case;row,old=instance(u,GOALS[:2]);target=publication(u,[GOALS[0]])
    before=snapshot(u);x=check(u,row,target).json();assert x['check']['classification']=='BREAKING_REJECTED'
    assert choose(u,row,x,'REQUEST_RECHECK').status_code==409
    assert choose(u,row,x).status_code==200 and snapshot(u)==before
    # A later Case cannot point back to this superseded historical release.
    assert check(u,row,old).status_code==403 and snapshot(u)==before


def confirmed(u,row):
    p=u['client'].get('/api/preparations/'+row['preparation_id'],headers=headers(u['f'][2])).json()
    p=dict(preparation_id=row['preparation_id'],revision=p['preparation']['revision'])
    p=preparation_act(u['f'],p,'REVIEW','prep-specialist-fixture-a',reason='Synthetic explicit material review').json()
    return preparation_act(u['f'],p,'CONFIRM',reason='Synthetic explicit enterprise confirmation').json()


def test_manual_lock_requires_original_unlock_and_never_overwrites_decision(upgrade_case):
    u=upgrade_case;row,_=instance(u);p=confirmed(u,row);verified(u['f'],p,'P1')
    current=plan_read(u['f'],p).json();s=current['steps'][0]
    r=plan_command(u['f'],p,'P1','LOCK',row=current,expected_source_sha256=s['source_sha256']);assert r.status_code==200,r.text
    target=publication(u,GOALS[:2]);before=snapshot(u);x=check(u,row,target);assert x.status_code==200,x.text;x=x.json()
    assert x['check']['classification']=='LOCK_CONFLICT' and x['check']['allowed_choices']==['KEEP_CURRENT']
    assert choose(u,row,x,'REQUEST_RECHECK').status_code==409
    assert choose(u,row,x).status_code==200 and snapshot(u)==before


def test_real_holds_acceptance_receipt_and_entire_history_survive_check_and_choice(upgrade_case):
    u=upgrade_case;row,_=instance(u,[GOALS[3]]);p=confirmed(u,row)
    # Existing fixture service actors need their ordinary new-Run read assignments.
    with u['f'][1].connect() as c:
        for actor in ('prep-specialist-fixture-a','executor-a'):
            c.execute('INSERT INTO run_assignments(run_id,principal_id,park_id,org_id) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',(row['run_id'],actor,'park-a','org-a'))
    group,dispatch=accepted(u['f'],p);verified(u['f'],p,'P3')
    receipt=u['f'][3].get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(u['f'][2],'executor-a')).json()
    receipt=receipt_act(u['f'],receipt,'SUBMIT').json();receipt=receipt_act(u['f'],receipt,'ACKNOWLEDGE').json();verified(u['f'],p,'P4')
    target=publication(u,[GOALS[3]],'2');before=snapshot(u)
    assert len(before[0]['synthetic_resource_holds'])==2 and len(before[0]['service_step_receipts'])==1
    x=check(u,row,target).json();assert x['check']['classification']=='NEEDS_RECHECK'
    assert choose(u,row,x,'REQUEST_RECHECK').status_code==200
    assert snapshot(u)==before


@pytest.mark.parametrize('same_key',[True,False])
def test_concurrent_cas_and_same_request_idempotency(upgrade_case,same_key):
    u=upgrade_case;row,_=instance(u);target=publication(u);x=check(u,row,target).json();key=uuid4().hex;before=snapshot(u)
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda i:choose(u,row,x,key=key if same_key else key+str(i)),range(2)))
    assert sorted(r.status_code for r in results)==([200,200] if same_key else [200,409])
    with u['repository'].connect() as c: assert c.execute('SELECT count(*) FROM upgrade_events').fetchone()[0]==1
    assert snapshot(u)==before
    if same_key:
        assert results[0].json()['event']==results[1].json()['event']
        assert choose(u,row,x,key=key,reason='Changed body').status_code==409


@pytest.mark.parametrize('change',['material','target-withdraw','source-head'])
def test_stale_check_denied_without_partial_event_and_historical_recovery_retained(upgrade_case,change):
    u=upgrade_case;row,_=instance(u);target=publication(u);x=check(u,row,target).json();key=uuid4().hex
    assert choose(u,row,x,key=key).status_code==200
    fresh=check(u,row,target).json()
    if change=='material':
        parent=u['client'].get('/api/preparations/'+row['preparation_id'],headers=headers(u['f'][2])).json()['preparation']
        assert preparation_act(u['f'],dict(preparation_id=row['preparation_id'],revision=parent['revision']),'ADD_EVIDENCE',slot='need_summary',text='SYNTHETIC changed data',source_kind='USER_STATEMENT',source_label='Changed input').status_code==200
    elif change=='target-withdraw':
        view=u['engine'].read('template-publisher',u['scope'])
        u['engine'].command('template-publisher',u['scope'],uuid4().hex,Command(action='WITHDRAW',expected_revision=view['revision'],expected_definition_sha256=view['definition_sha256'],reason='Synthetic withdrawal'))
    else: publication(u,source='2')
    before=snapshot(u)
    assert choose(u,row,fresh).status_code in (403,409)
    recovered=recover(u,row,key);assert recovered.status_code==200,recovered.text
    assert recovered.json()['status']=='COMMITTED' and recovered.json()['historical_only']
    assert choose(u,row,x,key=key).json()['historical_only'] and snapshot(u)==before


@pytest.mark.parametrize('cap',['READ','EXECUTE','PREPARE','case.create','inactive'])
def test_revocation_before_check_write_replay_and_recovery(upgrade_case,cap):
    u=upgrade_case;row,_=instance(u);target=publication(u);x=check(u,row,target).json();key=uuid4().hex;assert choose(u,row,x,key=key).status_code==200
    with u['f'][1].connect() as c:
        u['f'][1].lock_principal(c,'fixture-a',exclusive=True)
        if cap=='inactive': c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif cap=='case.create':c.execute("UPDATE action_grants SET active=false WHERE principal_id='fixture-a' AND action='case.create'")
        else:c.execute('UPDATE '+('preparation_grants' if cap=='PREPARE' else 'capability_grants')+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap,))
    before=snapshot(u)
    for r in [check(u,row,target),choose(u,row,x,key=key),recover(u,row,key)]:
        assert r.status_code==403 and 'PRIVATE_UPGRADE' not in r.text
    assert snapshot(u)==before


@pytest.mark.parametrize('actor',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_cross_enterprise_park_role_privacy_denied(upgrade_case,actor):
    u=upgrade_case;row,_=instance(u);target=publication(u);x=check(u,row,target).json();key=uuid4().hex;before=snapshot(u)
    for r in [check(u,row,target,actor),choose(u,row,x,key=key,user=actor),recover(u,row,key,actor)]:
        assert r.status_code==403 and 'PRIVATE_UPGRADE' not in r.text and row['case_id'] not in r.text
    assert snapshot(u)==before


def test_exact_key_read_recovery_and_new_objects_preserve_immutable_journal(upgrade_case):
    u=upgrade_case;row,_=instance(u);target=publication(u);x=check(u,row,target).json();key=uuid4().hex;event=choose(u,row,x,key=key).json()['event'];before=snapshot(u)
    assert recover(u,row,'not-seen').json()['status']=='NOT_OBSERVED'
    repo=UpgradeRepository(u['repository'].path)
    checker=TemplateUpgradeChecker(u['consumer'],repo,enabled_for_isolated_tests=True)
    assert checker.recover(u['f'][2]['fixture-a'],UUID(row['instance_id']),key)['event']==event
    with repo.connect() as c:
        for sql in ['UPDATE upgrade_events SET hash=?','DELETE FROM upgrade_events']:
            with pytest.raises(sqlite3.IntegrityError):c.execute(sql,('0'*64,) if '?' in sql else ())
    assert snapshot(u)==before


def test_default_factory_and_wrong_composition_never_expose_upgrade_routes(upgrade_case):
    u=upgrade_case
    assert not any(r.path.startswith('/api/template-upgrade') or r.path=='/template-upgrade' for r in u['f'][3].app.routes)
    with pytest.raises(Denied):TemplateUpgradeChecker(u['consumer'],u['repository'])
    client=TestClient(create_isolated_template_app(u['f'][0],u['engine'],u['consumer']))
    assert client.get('/template-upgrade').status_code==404
    with pytest.raises(ValueError):UpgradeRepository(u['repository'].path.parent/'foreign.sqlite3')


def test_legacy_original_key_remains_byte_identical_and_original_lock_works(upgrade_case):
    u=upgrade_case;row,_=instance(u,legacy=True);p=confirmed(u,row);verified(u['f'],p,'P1')
    target=publication(u,source='2');before=snapshot(u)
    x=check(u,row,target);assert x.status_code==200,x.text
    old=before[0]['preparations'][0]['service_case_plan']['events'][0]
    assert old['request_key']=='tc:'+row['instance_id']+':ADOPT_PLAN'
    assert snapshot(u)==before
    current=plan_read(u['f'],p).json();r=plan_command(u['f'],p,'P1','LOCK',row=current,expected_source_sha256=current['steps'][0]['source_sha256']);assert r.status_code==200,r.text
    assert snapshot(u)[0]['preparations'][0]['service_case_plan']['events'][0]==old


def test_actual_64_event_bound_and_original_replay_remains_readonly(upgrade_case):
    u=upgrade_case;row,_=instance(u);target=publication(u);x=check(u,row,target).json();before=snapshot(u)
    keys=[]
    for revision in range(64):
        keys.append(uuid4().hex)
        r=choose(u,row,{**x,'revision':revision},key=keys[-1]);assert r.status_code==200,r.text
    assert choose(u,row,{**x,'revision':63}).status_code==409
    assert recover(u,row,keys[0]).json()['event']['revision']==1
    assert choose(u,row,x,key=keys[0]).json()['historical_only']
    with u['repository'].connect() as c:assert c.execute('SELECT count(*) FROM upgrade_events').fetchone()[0]==64
    assert snapshot(u)==before


@pytest.mark.parametrize('damage',['hash','payload','schema'])
def test_corrupted_event_or_foreign_schema_fails_closed(upgrade_case,damage):
    u=upgrade_case;row,_=instance(u);target=publication(u);x=check(u,row,target).json();key=uuid4().hex;assert choose(u,row,x,key=key).status_code==200;before=snapshot(u)
    if damage=='schema':
        with sqlite3.connect(u['repository'].path) as c:c.execute('DROP TRIGGER upgrade_no_update')
        with pytest.raises(Conflict):UpgradeRepository(u['repository'].path)
    else:
        with sqlite3.connect(u['repository'].path) as c:
            c.execute('DROP TRIGGER upgrade_no_update')
            c.execute('UPDATE upgrade_events SET '+('hash=?' if damage=='hash' else 'payload=?'),('0'*64 if damage=='hash' else '{}',))
        assert recover(u,row,key).status_code==409
        assert choose(u,row,x,key=key).status_code==409
    assert snapshot(u)==before


def test_target_hash_extra_action_and_cross_instance_key_refused(upgrade_case):
    u=upgrade_case;row,_=instance(u);target=publication(u);x=check(u,row,target).json();key=uuid4().hex;assert choose(u,row,x,key=key).status_code==200
    before=snapshot(u)
    assert choose(u,row,x,choice='MIGRATE').status_code==422
    assert choose(u,row,x,expected_target_sha256='0'*64).status_code==409
    assert snapshot(u)==before
    newrow,_=instance(u)
    before=snapshot(u)
    assert recover(u,newrow,key).status_code==409 and snapshot(u)==before


def test_actual_case_lock_wait_crossing_target_expiry_refuses_choice(upgrade_case,monkeypatch):
    import threading,time
    u=upgrade_case;row,_=instance(u);target=publication(u);x=check(u,row,target).json();before=snapshot(u)
    now=[datetime(2026,10,10,tzinfo=timezone.utc)];u['engine'].clock=lambda:now[0]
    observed=threading.Event();original=u['engine']._available
    def available(*args):
        result=original(*args)
        if result['candidate_available']:observed.set()
        return result
    monkeypatch.setattr(u['engine'],'_available',available)
    with u['f'][1].connect() as blocker,ThreadPoolExecutor(1) as pool:
        blocker.execute('SELECT id FROM cases WHERE id=%s FOR UPDATE',(row['case_id'],))
        future=pool.submit(choose,u,row,x)
        assert observed.wait(2)
        end=time.monotonic()+2;wait=False
        while time.monotonic()<end:
            with u['f'][1].connect() as observer:
                wait=bool(observer.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT id FROM cases%' AND pid<>pg_backend_pid()").fetchone())
            if wait:break
            time.sleep(.01)
        assert wait,'actual Case source FOR SHARE must wait'
        now[0]=datetime(2100,1,1,tzinfo=timezone.utc);blocker.commit()
        response=future.result(timeout=5)
    assert response.status_code==403,response.text
    with u['repository'].connect() as c:assert c.execute('SELECT count(*) FROM upgrade_events').fetchone()[0]==0
    assert snapshot(u)==before
