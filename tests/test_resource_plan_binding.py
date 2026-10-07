"""Actual isolated PG/API evidence for the read-only resource/plan binding view.

Fixtures create UUID databases on their own temporary PG server. No demo database,
external resource, formal approval or product permission is created by this suite.
"""
import hashlib
import json
from uuid import UUID, uuid4

import pytest

from test_case_resources import link_fixture, group, post as bind
from test_controlled_plans import through, check
from test_executor_receipts import receipt_fixture, ready
from test_plan_preview import digest, GOAL
from test_preparation import preparation_fixture, headers
from test_request_intents import save
from test_resource_combinations import pair, write, cancel
from test_service_dispatches import offer


def read(f, parent, candidate=None, user='fixture-a'):
    params={} if candidate is None else {'candidate_combination_id':candidate}
    return f[3].get('/api/preparations/'+parent['preparation_id']+'/resource-plan-binding',
                    headers=headers(f[2], user), params=params)


def complete_digest(f):
    """Include authorization audit too: successful GET must make zero writes."""
    with f[1].connect() as c:
        tables=[r['tablename'] for r in c.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
        data={t:sorted(json.dumps(dict(r),sort_keys=True,default=str)
                       for r in c.execute('SELECT * FROM "'+t+'"')) for t in tables}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def checked(f):
    p,g,_,_=through(f,2)
    return p,g


def get_without_writes(f,p,candidate=None):
    before=complete_digest(f)
    response=read(f,p,candidate)
    assert response.status_code==200,response.text
    assert complete_digest(f)==before
    row=response.json()
    assert row['scope']=='SYNTHETIC_RESOURCE_PLAN_BINDING_ONLY'
    assert row['approval']=='NOT_IMPLEMENTED'
    assert row['engineering_check_only'] is True
    assert row['execution_enabled'] is False
    return row


def assert_recheck(row,step):
    checkpoint=row['checkpoints'][step]
    assert checkpoint['state']=='NEEDS_RECHECK'
    assert checkpoint['issues'] or checkpoint['changes']
    assert row['required_rechecks']
    assert step in json.dumps(row['required_rechecks'])
    for change in checkpoint['changes']:
        assert change['path'] and change['before']!=change['after']


def test_current_binding_identifies_same_case_sources_without_approval(link_fixture):
    f=link_fixture;p,g=checked(f)
    row=get_without_writes(f,p)
    assert row['case_id']==p['case_id']
    for step in ('P1','P2'):
        checkpoint=row['checkpoints'][step]
        assert checkpoint['state']=='CURRENT'
        assert checkpoint['checked_source_sha256']==checkpoint['current_source_sha256']
        assert len(checkpoint['current_source_sha256'])==64
        assert checkpoint['changes']==[] and checkpoint['issues']==[]
    current=row['current']
    assert all(k in current for k in ('goal','required_goals','service','template',
                                     'plan','preparation','resource_link','grants'))
    encoded=json.dumps(current)
    assert p['preparation_id'] in encoded and g['id'] in encoded
    assert p['snapshot_sha256'] in encoded
    for member in g['members']:
        assert member['id'] in encoded
        assert member['starts_at'] in encoded and member['ends_at'] in encoded
    assert 'capacity' in encoded and 'buffer_seconds' in encoded
    assert len(row['history'])==1
    assert row['candidate'] is None
    with f[1].connect() as c:
        assert c.execute('SELECT state FROM cases WHERE id=%s',(UUID(p['case_id']),)).fetchone()['state']=='NEEDS_INPUT'


def test_request_goals_changes_preserve_original_and_stale_old_engineering_check(link_fixture):
    f=link_fixture;p,g=checked(f)
    old=get_without_writes(f,p)
    updated=save(f,p,text='SYNTHETIC changed original request for binding',
                 goals=[GOAL,'必须真实线下履约'])
    assert updated.status_code==200,updated.text
    row=get_without_writes(f,p)
    assert_recheck(row,'P1')
    assert_recheck(row,'P2')
    assert row['checkpoints']['P1']['checked_source_sha256']==old['checkpoints']['P1']['checked_source_sha256']
    assert row['checkpoints']['P1']['current_source_sha256']!=old['checkpoints']['P1']['current_source_sha256']
    assert '必须真实线下履约' in json.dumps(row['current'],ensure_ascii=False)
    assert old['current']['goal']==row['current']['goal']
    assert len(row['history'])==len(old['history'])==1
    assert row['history'][0]['record']==old['history'][0]['record']
    # Existing gateway rechecks the old checkpoint independently of this view.
    assert offer(f,p)[0].status_code==409
    assert check(f,p,'P2').status_code==409
    with f[1].connect() as c:
        assert c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=%s',(UUID(g['id']),)).fetchone()['state']=='CONFIRMED'


def test_replacement_candidate_requires_explicit_rebind_and_preserves_occupancy(link_fixture):
    f=link_fixture;p,old=checked(f);candidate=group(f)
    before=get_without_writes(f,p)
    row=get_without_writes(f,p,candidate['id'])
    proposal=row['candidate']
    assert proposal['combination']['id']==candidate['id']
    assert proposal['explicit_association_required'] is True
    assert proposal['original_plan_recheck_required'] is True
    assert proposal['old_occupancy_released'] is False
    assert proposal['changes']
    assert old['id'] in json.dumps(row['current'])
    assert row['history']==before['history']
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM case_resource_links').fetchone()['n']==1
        assert [r['state'] for r in c.execute('SELECT state FROM synthetic_resource_combinations ORDER BY id')]==['CONFIRMED','CONFIRMED']
    response=bind(f,p,candidate,revision=1)
    assert response.status_code==201,response.text
    after=get_without_writes(f,p)
    assert len(after['history'])==2
    assert after['history'][0]['record']==before['history'][0]['record']
    assert candidate['id'] in json.dumps(after['current'])
    assert_recheck(after,'P2')
    # A changed binding cannot use the previous P2 engineering check to dispatch.
    assert offer(f,p)[0].status_code==409
    assert check(f,p,'P2').status_code==200
    with f[1].connect() as c:
        assert c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=%s',(UUID(old['id']),)).fetchone()['state']=='CONFIRMED'


@pytest.mark.parametrize('change,reason',[
    ('cancel','RESOURCE_CANCELLED'),('rule','RESOURCE_RULE_CHANGED'),
    ('ended','RESOURCE_WINDOW_ENDED'),('disabled','RESOURCE_RULE_CHANGED')])
def test_resource_changes_have_concrete_impact_history_and_gateway_block(link_fixture,change,reason):
    f=link_fixture;p,g=checked(f);old=get_without_writes(f,p)
    if change=='cancel':
        assert cancel(f,g['id']).status_code==200
    else:
        with f[1].connect() as c:
            if change=='ended':
                c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '2 hours',ends_at=clock_timestamp()-interval '1 hour' WHERE id=%s",(UUID(g['members'][0]['id']),))
            else:
                c.execute('UPDATE synthetic_resources SET '+('revision=revision+1' if change=='rule' else 'enabled=false')+' WHERE id=%s',(UUID(g['members'][0]['resource_id']),))
    row=get_without_writes(f,p)
    assert_recheck(row,'P2')
    assert reason in json.dumps(row['checkpoints']['P2']['issues'])
    assert row['checkpoints']['P2']['changes']
    assert row['history'][0]['record']==old['history'][0]['record']
    assert offer(f,p)[0].status_code==409


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a',
                                 'executor-a','executor-b','executor-c','unassigned'])
def test_cross_role_tenant_refused_without_business_or_authorization_mutation(link_fixture,user):
    f=link_fixture;p,_=checked(f);before=digest(f)
    response=read(f,p,user=user)
    assert response.status_code==403
    assert p['case_id'] not in response.text
    assert p['preparation_id'] not in response.text
    assert digest(f)==before


def test_cross_owner_candidate_and_unknown_identifiers_denied(link_fixture):
    f=link_fixture;p,_=checked(f)
    hs,data=pair(f,user='fixture-b');response=write(f,data,user='fixture-b')
    assert response.status_code==201,response.text
    other=response.json()['combination']['id']
    for candidate in (other,str(uuid4()),hs[0]['id']):
        before=digest(f)
        response=read(f,p,candidate)
        assert response.status_code==403
        assert other not in response.text and digest(f)==before
    assert read(f,p,'malformed').status_code==422
    assert read(f,{**p,'preparation_id':str(uuid4())}).status_code==403


@pytest.mark.parametrize('cap',['READ','PREPARE','resource_READ','inactive'])
def test_current_read_authority_revocation_denies_binding(link_fixture,cap):
    f=link_fixture;p,_=checked(f)
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        if cap=='inactive':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        else:
            table={'READ':'capability_grants','PREPARE':'preparation_grants',
                   'resource_READ':'synthetic_resource_grants'}[cap]
            c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap.removeprefix('resource_'),))
    before=digest(f)
    assert read(f,p).status_code==403 and digest(f)==before


@pytest.mark.parametrize('cap',['HOLD','EXECUTE'])
def test_write_permission_revocation_remains_visible_but_blocks_execution(link_fixture,cap):
    f=link_fixture;p,_=checked(f)
    with f[1].connect() as c:
        table='synthetic_resource_grants' if cap=='HOLD' else 'capability_grants'
        c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap,))
    row=get_without_writes(f,p)
    assert row['current']['grants']
    assert cap in json.dumps(row['current']['grants'])
    assert row['execution_enabled'] is False


def test_missing_plan_binding_is_read_only_and_does_not_create_business_records(link_fixture):
    f=link_fixture;p=ready(f)
    row=get_without_writes(f,p)
    assert row['history']==[] and row['candidate'] is None
    assert all(row['checkpoints'][step]['state']!='CURRENT' for step in ('P1','P2'))
    assert row['required_rechecks']


def test_catalog_change_blocks_old_checkpoints_at_actual_business_gate(link_fixture):
    f=link_fixture;p,g=checked(f);old=get_without_writes(f,p)
    replacement=group(f)
    with f[1].connect() as c:
        c.execute("UPDATE preparation_catalog SET name='SYNTHETIC changed catalog source',source=source || '{\"binding_revision\":2}'::jsonb WHERE (park_id,service_id,version) IN (SELECT park_id,service_id,service_version FROM preparations WHERE id=%s)",
                  (UUID(p['preparation_id']),))
    row=get_without_writes(f,p)
    assert_recheck(row,'P1')
    assert row['checkpoints']['P1']['checked_source_sha256']==old['checkpoints']['P1']['checked_source_sha256']
    assert row['checkpoints']['P1']['current_source_sha256']!=old['checkpoints']['P1']['current_source_sha256']
    assert any('catalog' in change['path'] for change in row['checkpoints']['P1']['changes'])
    assert offer(f,p)[0].status_code==409
    assert bind(f,p,replacement,revision=1).status_code==409
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM case_resource_links').fetchone()['n']==1
        assert c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=%s',(UUID(g['id']),)).fetchone()['state']=='CONFIRMED'


@pytest.mark.parametrize('change,reason',[('cancel','RESOURCE_CANCELLED'),
                                      ('ended','RESOURCE_WINDOW_ENDED')])
def test_unusable_replacement_is_visible_and_never_implicitly_bound(link_fixture,change,reason):
    f=link_fixture;p,g=checked(f);candidate=group(f)
    if change=='cancel':
        assert cancel(f,candidate['id']).status_code==200
    else:
        with f[1].connect() as c:
            c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '2 hours',ends_at=clock_timestamp()-interval '1 hour' WHERE id=%s",
                      (UUID(candidate['members'][0]['id']),))
    row=get_without_writes(f,p,candidate['id'])
    assert reason in row['candidate']['issues']
    assert row['candidate']['explicit_association_required']
    assert row['candidate']['old_occupancy_released'] is False
    assert len(row['history'])==1
    assert g['id'] in json.dumps(row['current']['resource_link'])


def test_changed_hold_source_requires_explicit_recheck_without_canceling_confirmation(link_fixture):
    f=link_fixture;p,g=checked(f);old=get_without_writes(f,p)
    with f[1].connect() as c:
        c.execute("UPDATE synthetic_resource_holds SET created_at=clock_timestamp()-interval '2 hours',expires_at=clock_timestamp()-interval '1 hour' WHERE id=%s",
                  (UUID(g['members'][0]['id']),))
    row=get_without_writes(f,p)
    assert_recheck(row,'P2')
    assert any('hold_sources' in change['path'] for change in row['checkpoints']['P2']['changes'])
    assert 'RESOURCE_CANCELLED' not in row['checkpoints']['P2']['issues']
    assert 'RESOURCE_HOLD_EXPIRED' not in row['checkpoints']['P2']['issues']
    assert row['history'][0]['record']==old['history'][0]['record']
    assert check(f,p,'P2').status_code==200
    assert get_without_writes(f,p)['checkpoints']['P2']['state']=='CURRENT'


def test_unknown_catalog_source_is_visible_and_cannot_recheck_to_executable(link_fixture):
    f=link_fixture;p,_=checked(f)
    with f[1].connect() as c:
        c.execute("UPDATE preparation_catalog SET source='{\"kind\":\"UNKNOWN\"}'::jsonb WHERE (park_id,service_id,version) IN (SELECT park_id,service_id,service_version FROM preparations WHERE id=%s)",
                  (UUID(p['preparation_id']),))
    row=get_without_writes(f,p)
    assert_recheck(row,'P1')
    assert 'CURRENT_SERVICE_CATALOG_REQUIRED' in row['checkpoints']['P1']['issues']
    assert check(f,p,'P1').status_code==409
    assert offer(f,p)[0].status_code==409


@pytest.mark.parametrize('cap,reason',[('HOLD','RESOURCE_HOLD_PERMISSION_REQUIRED'),
                                    ('EXECUTE','OWNER_EXECUTE_REQUIRED')])
def test_candidate_current_authority_rechecked_before_explicit_association(link_fixture,cap,reason):
    f=link_fixture;p,g=checked(f);candidate=group(f)
    before=get_without_writes(f,p,candidate['id'])
    assert reason not in before['candidate']['issues']
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        table='synthetic_resource_grants' if cap=='HOLD' else 'capability_grants'
        c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap,))
    # Viewing a proposal continues to require READ, and cannot repair write grants.
    current=get_without_writes(f,p)
    row=get_without_writes(f,p,candidate['id'])
    assert reason in row['candidate']['issues']
    assert row['candidate']['execution_enabled'] is False
    assert row['candidate']['explicit_association_required'] is True
    assert row['candidate']['old_occupancy_released'] is False
    if cap=='HOLD':
        assert_recheck(row,'P2')
        assert 'CURRENT_RESOURCE_AUTHORITY_REQUIRED' in current['checkpoints']['P2']['issues']
        assert 'CURRENT_RESOURCE_AUTHORITY_REQUIRED' in row['checkpoints']['P2']['issues']
    else:
        assert_recheck(row,'P1')
        assert row['checkpoints']['P2']['state']=='NEEDS_RECHECK'
        assert 'P2' in row['required_rechecks']
    assert row['history'][0]['record']==before['history'][0]['record']
    unchanged=digest(f)
    response=bind(f,p,candidate,revision=1)
    assert response.status_code==403,response.text
    assert digest(f)==unchanged
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM case_resource_links').fetchone()['n']==1
        assert c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=%s',(UUID(g['id']),)).fetchone()['state']=='CONFIRMED'
        assert c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=%s',(UUID(candidate['id']),)).fetchone()['state']=='CONFIRMED'
