"""Isolated actual PG/API contracts for explicitly confirming a compared replacement.

Every case uses the existing UUID database fixtures. Synthetic owner changes are
test inputs; no demo PG, external acceptance, grants or formal Approval is created.
"""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest

from test_case_resources import link_fixture, group
from test_controlled_plans import through, check
from test_executor_receipts import receipt_fixture, ready
from test_plan_preview import digest, GOAL
from test_preparation import preparation_fixture, headers
from test_request_intents import save
from test_resource_combinations import cancel, pair, write
from test_resource_plan_binding import complete_digest


def prepare(f):
    p,old,_,_=through(f,2)
    candidate=group(f)
    return p,old,candidate


def preview(f,p,candidate,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/resource-plan-binding',
      headers=headers(f[2],user),params={'candidate_combination_id':candidate['id']})


def compared(f,p,candidate):
    before=complete_digest(f)
    response=preview(f,p,candidate)
    assert response.status_code==200,response.text
    assert complete_digest(f)==before
    row=response.json()
    comparison=row['candidate']['comparison']
    assert comparison==row['comparison']
    assert len(comparison['sha256'])==64
    assert comparison['preparation_revision']==p['revision']
    assert comparison['link_revision']==row['current']['resource_link']['record']['revision']
    assert row['approval']=='NOT_IMPLEMENTED' and row['execution_enabled'] is False
    return row


def body(candidate,row,**changes):
    comparison=row['candidate']['comparison']
    return {'combination_id':candidate['id'],
            'expected_preparation_revision':comparison['preparation_revision'],
            'expected_link_revision':comparison['link_revision'],
            'expected_comparison_sha256':comparison['sha256'],
            'reason':'SYNTHETIC owner explicitly confirms compared replacement',**changes}


def confirm(f,p,data,key=None,user='fixture-a'):
    return f[3].post('/api/preparations/'+p['preparation_id']+'/resource-plan-binding/confirm',
      headers=headers(f[2],user,key or uuid4().hex),json=data)


def actual_records(f):
    with f[1].connect() as c:
        return {table:c.execute('SELECT * FROM '+table+' ORDER BY id' if table!='resource_case_claims' else 'SELECT * FROM '+table+' ORDER BY combination_id').fetchall()
          for table in ('case_resource_links','resource_case_claims','synthetic_resource_combinations')}


def authority_records(f):
    with f[1].connect() as c:
        return {table:c.execute('SELECT * FROM '+table+' ORDER BY principal_id').fetchall()
          for table in ('capability_grants','preparation_grants','synthetic_resource_grants','run_assignments')}


def test_explicit_same_case_replacement_records_immutable_compared_impact(link_fixture):
    f=link_fixture;p,old,candidate=prepare(f);row=compared(f,p,candidate)
    assert row['comparison']['can_confirm'] is True
    first=actual_records(f);authority=authority_records(f)
    response=confirm(f,p,body(candidate,row))
    assert response.status_code==201,response.text
    result=response.json();event=result['event']
    assert result['case_id']==p['case_id'] and result['link_revision']==2
    assert result['current']['status']==result['current']['source_status']=='CURRENT'
    assert event['combination_id']==candidate['id'] and event['revision']==2
    impact=event['snapshot']['binding_impact']
    assert impact['comparison_sha256']==row['comparison']['sha256']
    assert impact['before']['link_id']==row['current']['resource_link']['record']['id']
    assert impact['before']['link_revision']==1
    assert impact['before']['plan']==row['current']['plan']
    assert impact['before']['source_snapshots']=={
        step:row['checkpoints'][step]['current_snapshot'] for step in ('P1','P2')}
    assert impact['after']['link_id']==event['id'] and impact['after']['link_revision']==2
    assert impact['approval']==impact['formal_approval']=='NOT_IMPLEMENTED'
    assert impact['old_occupancy_released'] is False
    assert impact['new_grants'] is False and impact['execution_enabled'] is False
    assert impact['before'] and impact['after'] and impact['changes']
    assert old['id'] in str(impact['before']) and candidate['id'] in str(impact['after'])
    for change in impact['changes']:
        assert change['path'] and change['before']!=change['after']
    assert all(step in str(impact['required_rechecks']) for step in ('P2','P3','P4'))
    assert result['history'][0]['record']['snapshot']==row['history'][0]['record']['snapshot']
    with f[1].connect() as c:
        persisted=c.execute('SELECT * FROM case_resource_links WHERE id=%s',(UUID(event['id']),)).fetchone()
        assert persisted['snapshot']['binding_impact']==impact
        assert c.execute('SELECT count(*) n FROM resource_case_claims').fetchone()['n']==2
        assert c.execute('SELECT count(*) n FROM case_resource_links').fetchone()['n']==2
        assert [r['state'] for r in c.execute('SELECT state FROM synthetic_resource_combinations ORDER BY id')]==['CONFIRMED','CONFIRMED']
        assert c.execute('SELECT state FROM cases WHERE id=%s',(UUID(p['case_id']),)).fetchone()['state']=='NEEDS_INPUT'
    current=compared(f,p,candidate)
    assert current['history'][1]['source_status']=='CURRENT'
    assert current['history'][1]['binding_impact']==impact
    assert any(item['document']==impact and item['link_id']==event['id']
               for item in current['impact_history'])
    assert current['checkpoints']['P2']['state']=='NEEDS_RECHECK'
    assert all(record in actual_records(f)['case_resource_links']
               for record in first['case_resource_links'])
    assert authority_records(f)==authority
    # The new link and its explicit downstream recheck cannot stale their own impact.
    assert check(f,p,'P2').status_code==200
    refreshed=compared(f,p,candidate)
    assert refreshed['history'][1]['source_status']=='CURRENT'
    assert refreshed['history'][1]['binding_impact']==impact
    # Impact is immutable under the actual application database role.
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with f[0].connect() as c:
            c.execute('UPDATE case_resource_links SET snapshot=snapshot WHERE id=%s',(UUID(event['id']),))


@pytest.mark.parametrize('change',[
    'goals','catalog','plan_revision','candidate_rule','candidate_source',
    'candidate_hold_source','candidate_window','candidate_cancel',
    'old_rule','old_source','old_cancel','reviewer_grant'])
def test_changed_comparison_refuses_old_preview_without_any_persisted_effect(link_fixture,change):
    f=link_fixture;p,old,candidate=prepare(f);row=compared(f,p,candidate)
    data=body(candidate,row)
    if change=='goals':assert save(f,p,goals=[GOAL,'必须真实线下履约']).status_code==200
    elif change=='plan_revision':assert check(f,p,'P3').status_code==200
    elif change.endswith('_cancel'):
        assert cancel(f,(candidate if change.startswith('candidate') else old)['id']).status_code==200
    else:
        with f[1].connect() as c:
            if change=='catalog':
                c.execute("UPDATE preparation_catalog SET source=source || '{\"revision\":2}'::jsonb WHERE (park_id,service_id,version) IN (SELECT park_id,service_id,service_version FROM preparations WHERE id=%s)",(UUID(p['preparation_id']),))
            elif change=='reviewer_grant':
                f[1].lock_principal(c,'prep-specialist-fixture-a',exclusive=True)
                c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a'")
            elif change=='candidate_window':
                c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '2 hours',ends_at=clock_timestamp()-interval '1 hour' WHERE id=%s",(UUID(candidate['members'][0]['id']),))
            elif change=='candidate_hold_source':
                c.execute("UPDATE synthetic_resource_holds SET expires_at=expires_at+interval '1 second' WHERE id=%s",(UUID(candidate['members'][0]['id']),))
            else:
                selected=candidate if change.startswith('candidate') else old
                assignment='revision=revision+1' if change.endswith('_rule') else "source=source || '{\"revision\":2}'::jsonb"
                c.execute('UPDATE synthetic_resources SET '+assignment+' WHERE id=%s',(UUID(selected['members'][0]['resource_id']),))
    before=digest(f)
    response=confirm(f,p,data)
    assert response.status_code==409,response.text
    assert digest(f)==before
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM case_resource_links').fetchone()['n']==1
        assert c.execute('SELECT count(*) n FROM resource_case_claims').fetchone()['n']==1


def test_comparison_is_stable_across_reads_but_expired_time_window_cannot_confirm(link_fixture):
    f=link_fixture;p,_,candidate=prepare(f)
    with f[1].connect() as c:
        c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '1 second',ends_at=clock_timestamp()+interval '0.5 seconds' WHERE id=ANY(%s)",([UUID(h['id']) for h in candidate['members']],))
    row=compared(f,p,candidate)
    assert row['comparison']['can_confirm']
    repeated=compared(f,p,candidate)
    assert repeated['comparison']['sha256']==row['comparison']['sha256']
    with f[1].connect() as c:c.execute('SELECT pg_sleep(0.6)')
    before=digest(f)
    assert confirm(f,p,body(candidate,row)).status_code==409
    assert digest(f)==before


def test_distinct_keys_concurrently_confirm_one_comparison_only_once(link_fixture):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    data=body(candidate,row)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:confirm(f,p,data),range(2)))
    assert sorted(r.status_code for r in responses)==[201,409],[r.text for r in responses]
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM case_resource_links').fetchone()['n']==2
        assert c.execute('SELECT count(*) n FROM resource_case_claims').fetchone()['n']==2
        assert c.execute("SELECT count(*) n FROM case_resource_links WHERE snapshot ? 'binding_impact'").fetchone()['n']==1


@pytest.mark.parametrize('change',['candidate_cancel','goals'])
def test_lost_reply_same_key_recovers_original_event_after_current_source_changes(link_fixture,change):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    data=body(candidate,row);key=uuid4().hex
    response=confirm(f,p,data,key=key)
    assert response.status_code==201,response.text
    event=response.json()['event']
    if change=='candidate_cancel':assert cancel(f,candidate['id']).status_code==200
    else:assert save(f,p,goals=[GOAL,'必须真实线下履约']).status_code==200
    before=complete_digest(f)
    recovered=confirm(f,p,data,key=key)
    assert recovered.status_code==201,recovered.text
    current=recovered.json()
    assert current['event']==event
    assert current['current']['record']['snapshot']['binding_impact']==event['snapshot']['binding_impact']
    assert current['current']['status']=='NEEDS_RECHECK'
    assert current['current']['reasons']
    assert complete_digest(f)==before


def test_same_key_changed_body_or_case_is_conflict_and_never_creates_access(link_fixture):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    data=body(candidate,row);key=uuid4().hex
    assert confirm(f,p,data,key=key).status_code==201
    second=ready(f)
    for parent,changed in ((p,{**data,'reason':'SYNTHETIC changed reason'}),
                           (p,{**data,'expected_comparison_sha256':'f'*64}),
                           (second,data)):
        before=digest(f)
        response=confirm(f,parent,changed,key=key)
        assert response.status_code==409,response.text
        assert digest(f)==before


@pytest.mark.parametrize('cap',['READ','resource_READ','HOLD','EXECUTE','PREPARE','inactive'])
@pytest.mark.parametrize('replay',[False,True])
def test_current_authority_precedes_confirmation_and_old_event_replay(link_fixture,cap,replay):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    data=body(candidate,row);key=uuid4().hex
    if replay:assert confirm(f,p,data,key=key).status_code==201
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        if cap=='inactive':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        else:
            table='preparation_grants' if cap=='PREPARE' else 'synthetic_resource_grants' if cap in ('HOLD','resource_READ') else 'capability_grants'
            c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap.removeprefix('resource_'),))
    before=digest(f)
    response=confirm(f,p,data,key=key)
    assert response.status_code==403,response.text
    assert digest(f)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a','unassigned'])
def test_other_role_or_tenant_cannot_confirm_private_comparison(link_fixture,user):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    before=digest(f)
    response=confirm(f,p,body(candidate,row),user=user)
    assert response.status_code==403,response.text
    assert p['case_id'] not in response.text and digest(f)==before


def test_other_owner_candidate_cannot_confirm_or_become_a_claim(link_fixture):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    # Distinct non-overlapping synthetic windows avoid sharing available capacity.
    assert cancel(f,candidate['id']).status_code==200
    _,data=pair(f,user='fixture-b');response=write(f,data,user='fixture-b')
    assert response.status_code==201,response.text
    other=response.json()['combination']
    before=digest(f)
    response=confirm(f,p,body(other,row))
    assert response.status_code==403,response.text
    assert digest(f)==before


def test_link_insert_failure_rolls_back_impact_claim_and_checkpoint(link_fixture):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    before=digest(f)
    with f[1].connect() as c:c.execute('REVOKE INSERT ON case_resource_links FROM parkweave_app')
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='case_resource_links'):
            confirm(f,p,body(candidate,row))
    finally:
        with f[1].connect() as c:c.execute('GRANT INSERT ON case_resource_links TO parkweave_app')
    assert digest(f)==before
    assert compared(f,p,candidate)['comparison']['sha256']==row['comparison']['sha256']


def test_existing_history_bound_64_cannot_be_bypassed_by_confirm(link_fixture):
    f=link_fixture;p,_,candidate=prepare(f)
    with f[1].connect() as c:
        c.execute("""INSERT INTO case_resource_links(id,preparation_id,case_id,run_id,owner_id,park_id,org_id,combination_id,revision,preparation_revision,preparation_sha256,service_id,service_version,reason,snapshot,actor_id,request_key,fingerprint)
          SELECT gen_random_uuid(),preparation_id,case_id,run_id,owner_id,park_id,org_id,combination_id,n,preparation_revision,preparation_sha256,service_id,service_version,reason,snapshot,actor_id,'SYNTHETIC-bound-'||n,'SYNTHETIC owner fixture'
          FROM case_resource_links CROSS JOIN generate_series(2,64) AS n WHERE preparation_id=%s AND revision=1""",(UUID(p['preparation_id']),))
    row=compared(f,p,candidate)
    assert row['comparison']['link_revision']==64
    assert row['comparison']['can_confirm'] is False
    before=digest(f)
    assert confirm(f,p,body(candidate,row)).status_code==409
    assert digest(f)==before
    with f[1].connect() as c:assert c.execute('SELECT count(*) n FROM case_resource_links').fetchone()['n']==64


@pytest.mark.parametrize('bad',[
    {'expected_comparison_sha256':None}, {'expected_comparison_sha256':'short'},
    {'expected_preparation_revision':True}, {'expected_link_revision':False},
    {'confirmed':True}, {'approval':'APPROVED'}, {'reason':' '}])
def test_confirmation_strict_schema_cannot_claim_authority(link_fixture,bad):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    before=complete_digest(f)
    assert confirm(f,p,body(candidate,row,**bad)).status_code==422
    assert complete_digest(f)==before


def test_confirmation_requires_comparison_hash_and_explicit_request_key(link_fixture):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    data=body(candidate,row);data.pop('expected_comparison_sha256')
    before=complete_digest(f)
    assert confirm(f,p,data).status_code==422
    assert complete_digest(f)==before
    response=f[3].post('/api/preparations/'+p['preparation_id']+'/resource-plan-binding/confirm',
                       headers=headers(f[2]),json=body(candidate,row))
    assert response.status_code==422,response.text
    assert complete_digest(f)==before


@pytest.mark.parametrize('field',[
    'expected_preparation_revision','expected_link_revision','expected_comparison_sha256'])
def test_forged_current_comparison_or_revision_rejected_without_writes(link_fixture,field):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    data=body(candidate,row)
    data[field]='f'*64 if field.endswith('sha256') else data[field]+1
    before=complete_digest(f)
    response=confirm(f,p,data)
    assert response.status_code==409,response.text
    assert complete_digest(f)==before


@pytest.mark.parametrize('change',['catalog','hold_source_ttl'])
def test_lost_reply_retains_event_but_rechecks_changed_comparison_source(link_fixture,change):
    f=link_fixture;p,_,candidate=prepare(f);row=compared(f,p,candidate)
    data=body(candidate,row);key=uuid4().hex
    response=confirm(f,p,data,key=key)
    assert response.status_code==201,response.text
    original=response.json()
    assert original['current']['status']==original['current']['source_status']=='CURRENT'
    event=original['event']
    with f[1].connect() as c:
        if change=='catalog':
            c.execute("UPDATE preparation_catalog SET source=source || '{\"revision\":2}'::jsonb WHERE (park_id,service_id,version) IN (SELECT park_id,service_id,service_version FROM preparations WHERE id=%s)",
                      (UUID(p['preparation_id']),))
        else:
            c.execute("UPDATE synthetic_resource_holds SET expires_at=expires_at+interval '1 second' WHERE id=%s",
                      (UUID(candidate['members'][0]['id']),))
    before=complete_digest(f)
    response=confirm(f,p,data,key=key)
    assert response.status_code==201,response.text
    recovered=response.json()
    assert recovered['event']==event
    assert recovered['current']['status']==recovered['current']['source_status']=='NEEDS_RECHECK'
    assert 'RESOURCE_BINDING_SOURCE_CHANGED' in recovered['current']['reasons']
    assert recovered['current']['record']['snapshot']['binding_impact']==event['snapshot']['binding_impact']
    assert complete_digest(f)==before
    view=compared(f,p,candidate)
    assert view['history'][1]['source_status']=='NEEDS_RECHECK'
    assert 'RESOURCE_BINDING_SOURCE_CHANGED' in view['history'][1]['issues']
    assert view['history'][1]['binding_impact']==event['snapshot']['binding_impact']
