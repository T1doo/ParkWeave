"""Standalone candidate in existing UUID/least-app-role fixtures; no added GRANT."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import psycopg
from psycopg.conninfo import make_conninfo
import pytest
from pydantic import ValidationError
from psycopg.types.json import Jsonb

from parkweave import case_fact_clarifications as facts
from parkweave import preparation as prep
from parkweave.domain import FactInput
from parkweave.store import Conflict, Denied, Store
from test_preparation import preparation_fixture, create, add, command
from conftest import drop_owned_fixture_database

MIGRATION = Path(__file__).resolve().parents[1] / 'src/parkweave/migration-025.sql'


@pytest.fixture
def fixture_cluster_evidence(pg):
    if not hasattr(pg, 'pgdata'):
        pytest.skip('NOT_RUN: native installed cluster creation receipt adapter not provided')
    return facts.capture_fixture_cluster(pg.get_uri(), pg.pgdata.resolve())


def authorize_migration(owner, connection):
    owner._case_fact_fixture_receipt.authorize_migration(connection)


@pytest.fixture
def f(fixture_cluster_evidence, preparation_fixture):
    f = preparation_fixture
    with f[1].connect() as c:
        f[1]._case_fact_fixture_receipt = fixture_cluster_evidence.record_created_database(c)
        authorize_migration(f[1], c)
        c.execute(MIGRATION.with_name('migration-028.sql').read_text())
    return f


def row(f):
    return create(f, goal='SYNTHETIC independently owned Case fact purpose')[0]


def idof(parent):
    return UUID(parent['preparation_id'])


def assertion(f, field='region', value='地区甲', user='fixture-a', start=None, end=None):
    now = datetime.now(timezone.utc)
    data = FactInput.model_validate(dict(schema_version='parkweave-domain/1.0-draft', field=field, value=value,
        unit='people' if field == 'employees' else 'text',
        source_ref=dict(id='SYNTHETIC source ' + uuid4().hex, kind='SYNTHETIC', revision='1'), source_excerpt=str(value),
        validity=dict(valid_from=(start or now-timedelta(hours=1)).isoformat(), valid_until=(end or now+timedelta(hours=1)).isoformat(), timezone='UTC')))
    return f[0].save_fact(f[2][user], uuid4().hex, data)


def three(f):
    return [assertion(f), assertion(f, 'employees', 7), assertion(f, 'service_need', '合成服务需求')]


def declare_body(parent):
    return facts.Declare(expected_preparation_revision=parent['revision'], profile=facts.PROFILE, purpose=facts.PURPOSE, reason='Explicit synthetic Case purpose declaration')


def declare(f, parent, key=None):
    return facts.declare(f[0], f[2]['fixture-a'], idof(parent), key or uuid4().hex, declare_body(parent))


def view(f, parent, user='fixture-a'):
    return facts.read(f[0], f[2][user], idof(parent))


def confirm_body(v, chosen=None):
    sources = v['sources']
    choices = []
    for field in facts.FIELDS:
        source = next(item for item in sources if item['field_name'] == field and (chosen is None or item['id'] in chosen))
        choices.append(dict(field=field, assertion_id=source['id'], expected_assertion_revision=source['revision'], expected_assertion_fingerprint=source['fingerprint']))
    return facts.Confirm(expected_preparation_revision=v['preparation_revision'], expected_clarification_revision=v['revision'], expected_source_sha256=v['source_sha256'], choices=choices, reason='Only user-selected assertions for this Case; authenticity unverified')


def confirm(f, parent, data=None, key=None):
    return facts.confirm(f[0], f[2]['fixture-a'], idof(parent), key or uuid4().hex, data or confirm_body(view(f, parent)))


def gate(f, parent):
    with f[0].connect() as c:
        current = c.execute('SELECT * FROM preparations WHERE id=%s FOR SHARE', (idof(parent),)).fetchone()
        return facts.gate(f[0], c, current)


def business(f):
    with f[1].connect() as c:
        return {table: c.execute('SELECT * FROM '+table+' ORDER BY to_jsonb('+table+')::text').fetchall()
            for table in ('preparations', 'preparation_events', 'preparation_evidence', 'fact_assertions', 'fact_reviews', 'fact_followups', 'cases', 'runs', 'service_dispatches', 'service_receipt_steps', 'case_local_lifecycles', 'controlled_plans')}


def authority(f):
    with f[1].connect() as c:
        return {table: c.execute('SELECT * FROM '+table+' ORDER BY to_jsonb('+table+')::text').fetchall()
            for table in ('principals', 'field_grants', 'capability_grants', 'action_grants', 'preparation_grants', 'run_assignments')}


def test_real_ledger_conflicting_sources_selection_history_and_redacted_events(f):
    p = row(f); selected = three(f); competitor = assertion(f, value='地区乙')
    before_facts = business(f)['fact_assertions']; permissions = authority(f)
    v = view(f, p)
    assert gate(f, p)['state'] == 'NOT_DECLARED'
    assert next(q for q in v['necessary_questions'] if q['field'] == 'region')['reason'] == 'CONFLICTING_EVIDENCE'
    d = declare(f, p)
    assert d['action'] == 'DECLARE_FACT_PURPOSE' and d['revision'] == p['revision']+1 and d['state'] == 'IN_PREPARATION'
    assert gate(f, p)['state'] == 'UNKNOWN'
    response = confirm(f, p, confirm_body(view(f, p), selected))
    assert response['revision'] == d['revision']+1 and response['public_status']['state'] == 'CURRENT'
    assert gate(f, p)['satisfied'] is True
    v = view(f, p)
    assert len(v['sources']) == 4 and len(v['history']) == 2
    assert {c['assertion_id'] for c in v['history'][-1]['choices']} == set(selected)
    assert all(q['state'] == 'USER_SELECTED_FOR_CASE' for q in v['necessary_questions'])
    assert v['qualification'] == 'NOT_EVALUATED' and v['authenticity'] == 'USER_ASSERTED_UNVERIFIED'
    assert business(f)['fact_assertions'] == before_facts and authority(f) == permissions
    # Public events contain opaque references, never assertion data/source IDs.
    with f[1].connect() as c:
        public = c.execute("SELECT payload FROM preparation_events WHERE action LIKE '%FACT_PURPOSE'").fetchall()
    serialized = prep.canonical(public)
    for secret in selected+[competitor, '地区甲', '地区乙', '合成服务需求', 'source_excerpt', 'source_snapshot']:
        assert secret not in serialized
    with f[0].connect() as c:
        parent = c.execute('SELECT * FROM preparations WHERE id=%s', (idof(p),)).fetchone()
        descriptor = facts.source_descriptor(f[0], c, parent)
    assert 'sources' not in descriptor and 'choices' not in descriptor and len(descriptor['descriptor_sha256']) == 64
    assert view((Store(f[0].dsn), *f[1:]), p)['history'] == v['history']


def test_source_addition_stale_read_only_reconfirmation_and_historical_key(f):
    p = row(f); three(f); declare(f, p)
    body = confirm_body(view(f, p)); key = uuid4().hex
    original = confirm(f, p, body, key)
    history = deepcopy(view(f, p)['history'])
    assertion(f, value='新竞争来源')
    before = business(f)
    current = view(f, p)
    assert current['state'] == 'STALE' and gate(f, p)['satisfied'] is False
    assert current['history'] == history and business(f) == before
    recovered = confirm(f, p, body, key)
    assert recovered['recovery'] == 'HISTORICAL_COMMITTED_EVENT' and recovered['current_decision_restored'] is False
    assert recovered['revision'] == original['revision'] and business(f) == before
    assert gate(f, p)['state'] == 'STALE'
    with pytest.raises(Conflict): confirm(f, p, body.model_copy(update={'reason':'different intent'}), key)
    new = confirm(f, p)
    assert new['revision'] == original['revision']+1 and gate(f, p)['state'] == 'CURRENT'
    assert view(f, p)['history'][:2] == history


def test_missing_expired_future_inputs_unknown_and_cannot_select(f):
    p = row(f); declare(f, p)
    v = view(f, p)
    assert all(q['reason'] == 'MISSING_EVIDENCE' and q['state'] == 'UNKNOWN' for q in v['necessary_questions'])
    now = datetime.now(timezone.utc)
    assertion(f, end=now-timedelta(seconds=1)); assertion(f, 'employees', 7, start=now+timedelta(minutes=1)); assertion(f, 'service_need', '合成')
    before = business(f)
    with pytest.raises(Conflict): confirm(f, p)
    assert business(f) == before
    v = view(f, p)
    assert next(q for q in v['necessary_questions'] if q['field']=='region')['reason'] == 'EXPIRED_OR_NOT_YET_VALID'


def test_expiration_boundary_stales_without_hash_change(f):
    p = row(f); three(f); declare(f, p); confirm(f, p)
    with f[1].connect() as c:
        parent = c.execute('SELECT * FROM preparations WHERE id=%s', (idof(p),)).fetchone()
        owner = c.execute("SELECT * FROM principals WHERE id='fixture-a'").fetchone()
        snapshot, sha, applicable = facts._sources(f[0], c, parent, owner)
    ledger = facts._ledger(parent)
    selected = ledger['events'][-1]['choices'][0]['assertion_id']
    expired = dict(applicable, **{selected:False})
    result = facts._evaluate(parent, ledger, snapshot, sha, expired)
    assert result['state'] == 'STALE' and result['source_sha256'] == sha
    assert 'FACT_SOURCE_VALIDITY_CHANGED' in result['issues']


@pytest.mark.parametrize('user', ['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_wrong_role_org_park_cannot_read_or_replay(f, user):
    p = row(f); data = declare_body(p); key = uuid4().hex
    facts.declare(f[0], f[2]['fixture-a'], idof(p), key, data)
    before = business(f)
    with pytest.raises(Denied): view(f, p, user)
    with pytest.raises(Denied): facts.declare(f[0], f[2][user], idof(p), key, data)
    assert business(f) == before


@pytest.mark.parametrize('capability', ['READ','WRITE'])
def test_current_field_revocation_precedes_history_replay(f, capability):
    p = row(f); three(f); declare(f, p); body = confirm_body(view(f, p)); key = uuid4().hex; confirm(f,p,body,key)
    f[1].revoke_field('fixture-a','region',capability)
    before = business(f)
    with pytest.raises(Denied): confirm(f,p,body,key)
    if capability == 'READ':
        with pytest.raises(Denied): view(f,p)
    else:
        assert view(f,p)['state']=='STALE' and len(view(f,p)['history'])==2
    assert gate(f,p)['state']=='STALE' and business(f)==before


@pytest.mark.parametrize('change', [
    {'actor_id':'fixture-b'}, {'org_id':'other'}, {'case_id':str(uuid4())}, {'value':'fabricated'},
    {'verified':True}, {'choices':[]}, {'expected_clarification_revision':True},
])
def test_confirm_contract_rejects_new_value_actor_and_incomplete_choices(change):
    raw=dict(expected_preparation_revision=2,expected_clarification_revision=1,expected_source_sha256='a'*64,
        choices=[dict(field=field,assertion_id=str(uuid4()),expected_assertion_revision=1,expected_assertion_fingerprint='b'*64) for field in facts.FIELDS],reason='Explicit selection')
    with pytest.raises(ValidationError): facts.Confirm.model_validate(raw|change)


@pytest.mark.parametrize('mutation', ['duplicate','wrong_field','wrong_id','revision','fingerprint','sha','prep_revision','ledger_revision'])
def test_choice_and_double_cas_binding_refusal_zero_write(f, mutation):
    p=row(f);three(f);declare(f,p);raw=confirm_body(view(f,p)).model_dump(mode='json')
    if mutation=='duplicate': raw['choices'][1]=deepcopy(raw['choices'][0])
    elif mutation=='wrong_field': raw['choices'][0]['field'],raw['choices'][1]['field']=raw['choices'][1]['field'],raw['choices'][0]['field']
    elif mutation=='wrong_id': raw['choices'][0]['assertion_id']=str(uuid4())
    elif mutation=='revision': raw['choices'][0]['expected_assertion_revision']+=1
    elif mutation=='fingerprint': raw['choices'][0]['expected_assertion_fingerprint']='f'*64
    elif mutation=='sha': raw['expected_source_sha256']='f'*64
    elif mutation=='prep_revision': raw['expected_preparation_revision']-=1
    else: raw['expected_clarification_revision']+=1
    before=business(f)
    with pytest.raises((Conflict,ValidationError)): confirm(f,p,raw)
    assert business(f)==before


def test_current_fact_body_drift_stales_even_when_stored_fingerprint_unchanged(f):
    p=row(f);three(f);declare(f,p);confirm(f,p);before=view(f,p)['history']
    with f[1].connect() as c:
        c.execute("UPDATE fact_assertions SET source_excerpt='SYNTHETIC actual body drift' WHERE field_name='region'")
    assert gate(f,p)['state']=='STALE' and view(f,p)['history']==before


def test_request_change_stales_but_material_revision_alone_does_not(f):
    from parkweave import request_intents
    p=row(f);three(f);declare(f,p);confirm(f,p)
    latest={'preparation_id':p['preparation_id'],'revision':view(f,p)['preparation_revision']}
    latest=add(f,latest).json()
    assert gate(f,p)['state']=='CURRENT'
    request_intents.save(f[0],f[2]['fixture-a'],idof(p),uuid4().hex,
        request_intents.Save(expected_preparation_revision=latest['revision'],request_text='New explicit request',required_goals=[]))
    assert gate(f,p)['state']=='STALE'


def test_reconfirmation_clears_review_and_requires_new_manual_review(f):
    p=row(f);three(f);declare(f,p);confirmed=confirm(f,p)
    p2=add(f,confirmed).json();p2=add(f,p2,'material_outline','SYNTHETIC own outline').json()
    p2=command(f,p2,'REVIEW',user='prep-specialist-fixture-a',reason='Real reviewer').json()
    p2=command(f,p2,'CONFIRM',reason='Real owner').json()
    renewed=confirm(f,p)
    assert renewed['revision']==p2['revision']+1 and renewed['state']=='IN_PREPARATION'
    assert command(f,renewed,'CONFIRM',reason='No reviewer after fact choice').status_code==409
    with f[1].connect() as c:
        assert c.execute('SELECT review_sha256 FROM preparations WHERE id=%s',(idof(p),)).fetchone()['review_sha256'] is None


def test_concurrent_confirm_one_dual_cas_winner_and_same_key_one_event(f):
    p=row(f);three(f);declare(f,p);body=confirm_body(view(f,p))
    def call(key):
        try:return confirm(f,p,body,key)
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool: replies=list(pool.map(call,[uuid4().hex,uuid4().hex]))
    assert sum(isinstance(x,dict) for x in replies)==1 and replies.count('CONFLICT')==1
    body=confirm_body(view(f,p));key=uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool: replies=list(pool.map(call,[key,key]))
    assert all(isinstance(x,dict) for x in replies)
    assert sorted(x.get('recovery','NEW') for x in replies)==['HISTORICAL_COMMITTED_EVENT','NEW']
    assert len(view(f,p)['history'])==3


@pytest.mark.parametrize('seam', ['invalidate','event'])
def test_transaction_rolls_back_ledger_revision_and_event(f, monkeypatch, seam):
    from parkweave import controlled_plans
    p=row(f);three(f);declare(f,p);body=confirm_body(view(f,p));before=business(f)
    def fail(*args,**kwargs):raise RuntimeError('SYNTHETIC transaction failure')
    monkeypatch.setattr(controlled_plans if seam=='invalidate' else prep,seam,fail)
    with pytest.raises(RuntimeError): confirm(f,p,body)
    assert business(f)==before


def test_migration_transaction_rollback_and_rerun_retains_ledger(f):
    p=row(f);three(f);declare(f,p);confirm(f,p);before=business(f);permissions=authority(f)
    with f[1].connect() as c:
        authorize_migration(f[1], c)
        c.execute(MIGRATION.with_name('migration-028.sql').read_text())
    assert business(f)==before and authority(f)==permissions
    with f[1].connect() as c:
        assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']==28
        assert c.execute("SELECT pg_get_constraintdef(oid) d FROM pg_constraint WHERE conname='preparation_events_action_check'").fetchone()['d'].count('CONFIRM_FACT_PURPOSE')==1
    # Test a clean DDL rollback on this same isolated fixture, not a production downgrade.
    with f[1].connect() as c:
        c.execute('SAVEPOINT candidate_ddl')
        c.execute("ALTER TABLE preparations ADD COLUMN test_transactional_ddl integer")
        c.execute('ROLLBACK TO SAVEPOINT candidate_ddl')
        assert not c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='preparations' AND column_name='test_transactional_ddl'").fetchone()


@pytest.mark.parametrize('bad', [False, True, 0.0, '0'])
def test_declaration_rejects_non_integer_zero_before_literal_coercion(bad):
    with pytest.raises(ValidationError):
        facts.Declare(expected_preparation_revision=1, expected_clarification_revision=bad, profile=facts.PROFILE, purpose=facts.PURPOSE, reason='Must be integer zero')


def test_real_db_clock_expiration_stales_without_revision_or_sha_change(f):
    p=row(f);ids=three(f);declare(f,p)
    # Fixture owner chooses a short validity before confirmation, never mutates
    # source after confirmation: expiry alone must cause STALE with same SHA.
    with f[1].connect() as c:
        c.execute("UPDATE fact_assertions SET valid_until=clock_timestamp()+interval '0.8 seconds' WHERE id=%s",(ids[0],))
    confirm(f,p);v=view(f,p);before=business(f)
    with f[1].connect() as c:c.execute('SELECT pg_sleep(0.85)')
    after=view(f,p)
    assert after['state']=='STALE' and after['source_sha256']==v['source_sha256'] and after['history']==v['history']
    assert after['preparation_revision']==v['preparation_revision'] and business(f)==before


def test_expiry_during_plan_lock_wait_rolls_back_confirmation(f, monkeypatch):
    from parkweave import controlled_plans
    p=row(f);ids=three(f);declare(f,p)
    with f[1].connect() as c:
        c.execute("UPDATE fact_assertions SET valid_until=clock_timestamp()+interval '0.8 seconds' WHERE id=%s",(ids[0],))
    body=confirm_body(view(f,p));before=business(f)
    original=controlled_plans.invalidate
    def delayed(c,*args):
        c.execute('SELECT pg_sleep(0.85)')
        return original(c,*args)
    monkeypatch.setattr(controlled_plans,'invalidate',delayed)
    with pytest.raises(Conflict,match='validity changed'):confirm(f,p,body)
    assert business(f)==before


@pytest.mark.parametrize('writer', ['save_fact','revoke_field'])
def test_original_source_writer_and_revoker_wait_until_confirm_commit(f,monkeypatch,writer):
    from time import monotonic, sleep
    p=row(f);three(f);declare(f,p);body=confirm_body(view(f,p))
    entered=Event();release=Event();started=Event();original=facts._persist
    def hold(*args,**kwargs):
        entered.set()
        if not release.wait(5):raise RuntimeError('test release deadline')
        return original(*args,**kwargs)
    monkeypatch.setattr(facts,'_persist',hold)
    def write():
        started.set()
        if writer=='save_fact':return assertion(f,value='SYNTHETIC concurrent new source')
        return f[1].revoke_field('fixture-a','region','WRITE')
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(confirm,f,p,body)
        assert entered.wait(3)
        second=pool.submit(write)
        try:
            assert started.wait(1)
            end=monotonic()+2;blocked=False
            while monotonic()<end:
                with f[1].connect() as c:
                    blocked=bool(c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND wait_event='advisory'").fetchone())
                if blocked:break
                sleep(.01)
            assert blocked and not second.done()
        finally:release.set()
        response=first.result(timeout=4);second.result(timeout=4)
    assert response['action']=='CONFIRM_FACT_PURPOSE' and gate(f,p)['state']=='STALE'
    with f[1].connect() as c:
        assert c.execute("SELECT count(*) n FROM preparation_events WHERE action='CONFIRM_FACT_PURPOSE'").fetchone()['n']==1


def test_bounds_fail_closed_without_new_effects(f):
    p=row(f);three(f);declare(f,p)
    for n in range(15):assertion(f,value='SYNTHETIC region competitor '+str(n))
    assert len([s for s in view(f,p)['sources'] if s['field_name']=='region'])==16
    before=business(f)
    with pytest.raises(Conflict):assertion(f,value='seventeenth refused by original Store')
    assert business(f)==before
    # Unsupported corrupt source history cannot silently truncate a competitor.
    with f[1].connect() as c:
        c.execute("INSERT INTO fact_assertions SELECT %s,%s,principal_id,park_id,org_id,field_name,value,unit,source_ref,source_kind,source_excerpt,valid_from,valid_until,%s,fingerprint,revision,confirmed_by,created_at FROM fact_assertions WHERE field_name='region' LIMIT 1",(uuid4(),uuid4(),uuid4().hex))
    before=business(f)
    with pytest.raises(Conflict):view(f,p)
    assert gate(f,p)['state']=='STALE' and business(f)==before


def test_preparation_and_ledger_limits_refuse_new_event(f):
    p=row(f);three(f);declare(f,p);body=confirm_body(view(f,p))
    with f[1].connect() as c:c.execute('UPDATE preparations SET revision=64 WHERE id=%s',(idof(p),))
    before=business(f)
    with pytest.raises(Conflict):confirm(f,p,body)
    assert business(f)==before
    # Invalid or oversized ledger is rejected, never reset as a legacy profile.
    with f[1].connect() as c:
        c.execute("UPDATE preparations SET fact_clarifications=jsonb_set(fact_clarifications,'{revision}','65'::jsonb) WHERE id=%s",(idof(p),))
    before=business(f)
    with pytest.raises(Conflict):view(f,p)
    assert gate(f,p)['enabled'] and not gate(f,p)['satisfied'] and business(f)==before


@pytest.fixture
def schema24_owner(pg, fixture_cluster_evidence):
    """Explicit 24 starting point, independent of main Store.migrate latest version.

    Existing local pg fixture and UUID cleanup only; no identities or GRANTs.
    """
    db = 'fixture_' + uuid4().hex
    created = False
    try:
        with psycopg.connect(pg.get_uri(), autocommit=True) as c:
            c.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(db)))
            created = True
        owner = Store(make_conninfo(pg.get_uri(), dbname=db))
        root = MIGRATION.parent
        with owner.connect() as c:
            owner._case_fact_fixture_receipt = fixture_cluster_evidence.record_created_database(c)
            c.execute((root / 'schema.sql').read_text())
            for version in range(2, 25):
                c.execute((root / f'migration-{version:03}.sql').read_text())
            assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v'] == 24
        yield owner
    finally:
        if created:
            drop_owned_fixture_database(pg, db)


def test_actual_migration_025_rolls_back_all_ddl(schema24_owner):
    owner = schema24_owner
    def unchanged():
        with owner.connect() as c:
            assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v'] == 24
            assert not c.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='preparations' AND column_name='fact_clarifications'").fetchone()
            constraint = c.execute("SELECT pg_get_constraintdef(oid) d FROM pg_constraint WHERE conrelid='public.preparation_events'::regclass AND conname='preparation_events_action_check'").fetchone()['d']
            assert 'DECLARE_FACT_PURPOSE' not in constraint and 'CONFIRM_FACT_PURPOSE' not in constraint
            return {table: c.execute('SELECT * FROM ' + table).fetchall() for table in
                    ('principals', 'field_grants', 'capability_grants', 'action_grants', 'preparation_grants', 'run_assignments')}
    permissions = unchanged()
    with pytest.raises(RuntimeError, match='SYNTHETIC before migration commit'):
        with owner.connect() as c:
            authorize_migration(owner, c)
            c.execute(MIGRATION.read_text())
            assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v'] == 25
            raise RuntimeError('SYNTHETIC before migration commit')
    assert unchanged() == permissions


def test_migration_refuses_maintenance_db_and_app_role(pg, f):
    with pytest.raises(psycopg.errors.RaiseException,match='creation evidence'):
        with psycopg.connect(pg.get_uri()) as c:c.execute(MIGRATION.read_text())
    before=business(f)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with f[0].connect() as c:c.execute(MIGRATION.read_text())
    assert business(f)==before


def test_real_p1_checkpoint_row_invalidates_in_same_transaction(f, monkeypatch):
    from parkweave import controlled_plans
    p=row(f);three(f)
    # Isolated checkpoint seam, not a claim that the full product plan ran.
    checked={'P1':{'sha256':'SYNTHETIC existing checkpoint'}}
    with f[1].connect() as c:
        c.execute('INSERT INTO controlled_plans(preparation_id,id,template_sha256,revision,checked) VALUES(%s,%s,%s,1,%s)',
            (idof(p),uuid4(),controlled_plans.TEMPLATE_SHA,Jsonb(checked)))
    before=business(f)
    original=prep.event
    def fail(*args,**kwargs):raise RuntimeError('SYNTHETIC failure after real checkpoint invalidation')
    monkeypatch.setattr(prep,'event',fail)
    with pytest.raises(RuntimeError):declare(f,p)
    assert business(f)==before
    monkeypatch.setattr(prep,'event',original)
    declare(f,p)
    with f[1].connect() as c:
        checkpoint=c.execute('SELECT * FROM controlled_plans WHERE preparation_id=%s',(idof(p),)).fetchone()
    assert checkpoint['invalidated_from']==1 and checkpoint['invalidated_at'] is not None and checkpoint['checked']==checked


@pytest.mark.parametrize('wrong', ['service_version','case_binding','run_owner','run_state'])
def test_exact_case_run_service_binding_denied_before_declare_write(f,wrong):
    p=row(f);three(f)
    with f[1].connect() as c:
        if wrong=='service_version':
            c.execute('INSERT INTO preparation_catalog SELECT park_id,service_id,2,name,source,namespace,qualification FROM preparation_catalog WHERE version=1')
            c.execute('UPDATE preparations SET service_version=2 WHERE id=%s',(idof(p),))
        elif wrong=='case_binding':
            from parkweave.domain import Intake
            other_run=f[0].submit(f[2]['fixture-b'],uuid4().hex,Intake(goal='SYNTHETIC unrelated real Case binding'))
            f[0].finish(f[0].claim('synthetic-unrelated-case'))
            other_case=c.execute('SELECT id FROM cases WHERE run_id=%s',(UUID(other_run),)).fetchone()['id']
            c.execute('UPDATE preparations SET case_id=%s WHERE id=%s',(other_case,idof(p)))
        elif wrong=='run_owner':c.execute("UPDATE runs SET principal_id='fixture-b' WHERE id=%s",(UUID(p['run_id']),))
        else:c.execute("UPDATE runs SET state='QUEUED' WHERE id=%s",(UUID(p['run_id']),))
    before=business(f)
    with pytest.raises(Denied):declare(f,p)
    with pytest.raises(Denied):view(f,p)
    assert business(f)==before


@pytest.mark.parametrize('corruption', [None, {}, 'drop_field'])
def test_declared_profile_cannot_be_removed_or_fields_unlocked(f,corruption):
    p=row(f);three(f);declare(f,p);confirm(f,p)
    with f[1].connect() as c:
        if corruption=='drop_field':
            c.execute("UPDATE preparations SET fact_clarifications=jsonb_set(fact_clarifications,'{required_fields}','[\"region\",\"employees\"]'::jsonb) WHERE id=%s",(idof(p),))
        else:
            c.execute('UPDATE preparations SET fact_clarifications=%s WHERE id=%s',(Jsonb(corruption) if corruption is not None else None,idof(p)))
    before=business(f)
    assert gate(f,p)['enabled'] and gate(f,p)['state']=='STALE' and not gate(f,p)['satisfied']
    with pytest.raises(Conflict):view(f,p)
    with pytest.raises(Conflict):declare(f,dict(p,revision=view_revision(f,p)))
    assert business(f)==before


def view_revision(f,p):
    with f[1].connect() as c:
        return c.execute('SELECT revision FROM preparations WHERE id=%s',(idof(p),)).fetchone()['revision']


@pytest.mark.parametrize('changed_grant', ['field_read', 'field_write', 'capability_read', 'capability_execute'])
def test_restored_existing_grant_generation_requires_explicit_new_confirmation(f, changed_grant):
    p = row(f); three(f); declare(f, p)
    original_body = confirm_body(view(f, p)); original_key = uuid4().hex
    original_event = confirm(f, p, original_body, original_key); original = view(f, p)
    before_authority = authority(f)
    kind, capability = changed_grant.split('_')
    if kind == 'field':
        f[1].revoke_field('fixture-a', 'region', capability.upper())
        table, where, params = 'field_grants', 'field_name=%s AND purpose=%s AND capability=%s', ('region', facts.PURPOSE, capability.upper())
    else:
        f[1].revoke_capability('fixture-a', capability.upper())
        table, where, params = 'capability_grants', 'capability=%s', (capability.upper(),)
    with pytest.raises(Denied): confirm(f, p, original_body, original_key)
    # Existing fixture administrator restores that same prerequisite row only.
    # No identity or grant is created, and the application performs no restore.
    with f[1].connect() as c:
        f[1].lock_principal(c, 'fixture-a', exclusive=True)
        c.execute('UPDATE ' + table + ' SET active=true,revision=revision+1 WHERE principal_id=%s AND ' + where,
                  ('fixture-a', *params))
    permissions = authority(f); before = business(f); current = view(f, p)
    assert {k: len(v) for k, v in permissions.items()} == {k: len(v) for k, v in before_authority.items()}
    assert current['state'] == 'STALE' and not current['satisfied']
    assert 'FACT_AUTHORITY_GENERATION_CHANGED' in current['issues']
    assert current['source_sha256'] != original['source_sha256'] and current['history'] == original['history']
    assert current['preparation_revision'] == original['preparation_revision']
    replay = confirm(f, p, original_body, original_key)
    assert replay['recovery'] == 'HISTORICAL_COMMITTED_EVENT' and not replay['current_decision_restored']
    assert replay['revision'] == original_event['revision'] and gate(f, p)['state'] == 'STALE'
    assert business(f) == before and authority(f) == permissions
    # New body with current SHA and both current revisions is required.
    confirmed = confirm(f, p)
    latest = view(f, p)
    assert latest['state'] == 'CURRENT' and latest['satisfied']
    assert latest['revision'] == original['revision'] + 1
    assert confirmed['revision'] == original['preparation_revision'] + 1
    assert latest['history'][:-1] == original['history'] and authority(f) == permissions


def test_fixed_lifecycle_name_requires_real_cluster_creation_receipt(pg, fixture_cluster_evidence):
    """Same fixed name; genuine new owned cluster/DB, no app GRANT/setup change.

    This checks migration compatibility, not native lifecycle/browser execution.
    """
    owner = Store(make_conninfo(pg.get_uri(), dbname='parkweave'))
    created = False; receipt = None
    try:
        with psycopg.connect(pg.get_uri(), autocommit=True) as c:
            c.execute('CREATE DATABASE parkweave'); created = True
        with owner.connect() as c:
            receipt = fixture_cluster_evidence.record_created_database(c)
        owner._case_fact_fixture_receipt = receipt
        owner.migrate()  # Current loader issues the ticket in its own schema-25 transaction.
        with pytest.raises(psycopg.errors.RaiseException, match='creation ticket required'):
            with owner.connect() as c: c.execute(MIGRATION.read_text())
        with owner.connect() as c:
            receipt.authorize_migration(c); c.execute(MIGRATION.with_name('migration-028.sql').read_text())
            assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v'] == 28
            assert c.execute('SELECT current_database() d').fetchone()['d'] == 'parkweave'
            assert c.execute("SELECT to_regclass('pg_temp.parkweave_fixture_migration_receipt') marker").fetchone()['marker'] is not None
            c.commit()
            assert c.execute("SELECT to_regclass('pg_temp.parkweave_fixture_migration_receipt') marker").fetchone()['marker'] is None
            receipt.authorize_migration(c); c.execute(MIGRATION.with_name('migration-028.sql').read_text())
            c.rollback()
            assert c.execute("SELECT to_regclass('pg_temp.parkweave_fixture_migration_receipt') marker").fetchone()['marker'] is None
        # Reissue only from the same actual creation receipt, preserving ledger.
        with owner.connect() as c: receipt.authorize_migration(c); c.execute(MIGRATION.with_name('migration-028.sql').read_text())
    finally:
        if created:
            with psycopg.connect(pg.get_uri(), autocommit=True) as c:
                actual = c.execute("SELECT oid FROM pg_database WHERE datname='parkweave'").fetchone()
                if receipt is not None:
                    assert actual and actual[0] == receipt.database_oid
                c.execute('DROP DATABASE parkweave')


@pytest.mark.parametrize('changed', ['database_oid', 'system_identifier', 'data_directory', 'backend_pid', 'transaction_id', 'owner_name', 'null'])
def test_migration_creation_ticket_mismatch_is_fail_closed(f, changed):
    before = business(f); permissions = authority(f)
    with pytest.raises(psycopg.errors.RaiseException, match='does not match'):
        with f[1].connect() as c:
            authorize_migration(f[1], c)
            assignments = {'database_oid': 'database_oid=0', 'system_identifier': "system_identifier='wrong'",
                'data_directory': "data_directory='/unowned'", 'backend_pid': 'backend_pid=0',
                'transaction_id': 'transaction_id=0', 'owner_name': "owner_name='parkweave_app'",
                'null': 'database_oid=NULL'}
            c.execute('UPDATE pg_temp.parkweave_fixture_migration_receipt SET ' + assignments[changed])
            c.execute(MIGRATION.read_text())
    assert business(f) == before and authority(f) == permissions


def test_uuid_name_and_database_owner_without_creation_evidence_do_not_authorize_migration(f):
    before = business(f)
    with f[1].connect() as c:
        c.autocommit = True
        with pytest.raises(Denied, match='explicit owner migration transaction'):
            authorize_migration(f[1], c)
    with pytest.raises(psycopg.errors.RaiseException, match='creation ticket required'):
        with f[1].connect() as c: c.execute(MIGRATION.read_text())
    assert business(f) == before
    with f[1].connect() as c:
        old = f[1]._case_fact_fixture_receipt
        fabricated = facts.FixtureDatabaseEvidence(old.cluster, old.database_name, old.database_oid, uuid4())
        with pytest.raises(Denied, match='issued fixture database'): fabricated.authorize_migration(c)


def test_migration_refuses_future_version_even_with_retained_24_and_valid_receipt(f):
    with f[1].connect() as c: c.execute('INSERT INTO schema_version VALUES(29)')
    before = business(f)
    with pytest.raises(psycopg.errors.RaiseException, match='schema 24 prerequisite'):
        with f[1].connect() as c:
            authorize_migration(f[1], c); c.execute(MIGRATION.read_text())
    with f[1].connect() as c:
        assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v'] == 29
    assert business(f) == before


def test_fixture_cluster_capture_rejects_existing_targets_or_mismatched_directory(pg, f):
    with pytest.raises(Denied, match='fresh empty test cluster'):
        facts.capture_fixture_cluster(pg.get_uri(), pg.pgdata.resolve())
    with pytest.raises(Denied, match='directory evidence'):
        facts.capture_fixture_cluster(pg.get_uri(), pg.pgdata.parent / 'not-created-by-fixture')
