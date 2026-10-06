"""PG/API Case ownership and versioned synthetic resource association contracts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID,uuid4
import psycopg,pytest
from parkweave import case_resources as cr,resource_combinations as rc,preparation as prep
from parkweave.store import Conflict,Store
from test_executor_receipts import receipt_fixture,ready
from test_resource_combinations import pair,write,cancel
from test_preparation import preparation_fixture,headers,command as preparation_command

@pytest.fixture
def link_fixture(receipt_fixture):
    rc.seed_synthetic(receipt_fixture[1]);return receipt_fixture

def group(f):
    hs,data=pair(f);r=write(f,data);assert r.status_code==201;return r.json()['combination']
def post(f,parent,g,user='fixture-a',key=None,revision=0,**extra):
    data={**dict(combination_id=g['id'],expected_preparation_revision=parent['revision'],expected_link_revision=revision,reason='SYNTHETIC attach resource plan'),**extra}
    return f[3].post('/api/preparations/'+parent['preparation_id']+'/resource-link',headers=headers(f[2],user,key or uuid4().hex),json=data)
def get(f,parent,user='fixture-a'):
    return f[3].get('/api/preparations/'+parent['preparation_id']+'/resource-link',headers=headers(f[2],user))
def totals(f):
    with f[1].connect() as c:return [c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('resource_case_claims','case_resource_links')]

def test_persistent_association_replay_cancel_does_not_close_case(link_fixture):
    f=link_fixture;parent=ready(f);g=group(f);key=uuid4().hex;r=post(f,parent,g,key=key);assert r.status_code==201;row=r.json()
    assert row['current']['status']=='CURRENT' and row['case_id']==parent['case_id'] and row['link_revision']==1
    assert row['current']['record']['snapshot']['state']=='CONFIRMED' and row['current']['record']['preparation_sha256']==parent['snapshot_sha256']
    assert post(f,parent,g,key=key).json()['event']==row['event'] and totals(f)==[1,1]
    assert post(f,parent,g).status_code==409
    assert cancel(f,g['id']).status_code==200
    now=get(f,parent).json();assert now['current']['reasons']==['RESOURCE_CANCELLED']
    assert post(f,parent,g,key=key).json()['event']==row['event'] and totals(f)==[1,1]
    assert post(f,parent,g,revision=1).status_code==409
    assert now['case_state']=='NEEDS_INPUT' and not now['case_goal_completed'] and now['offline_fulfillment']=='NO_EVIDENCE'
    again=cr.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(parent['preparation_id']));assert len(again['history'])==1

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a','unassigned'])
def test_owner_role_scope_intersection(link_fixture,user):
    f=link_fixture;parent=ready(f);g=group(f);assert post(f,parent,g).status_code==201;before=totals(f)
    assert get(f,parent,user).status_code==403 and post(f,parent,g,user,revision=1).status_code==403
    assert f[3].get('/api/preparations/'+parent['preparation_id']+'/resource-link-candidates',headers=headers(f[2],user)).status_code==403
    assert totals(f)==before

@pytest.mark.parametrize('cap',['READ','HOLD','EXECUTE','PREPARE','inactive'])
def test_current_revocation_precedes_old_key_replay(link_fixture,cap):
    f=link_fixture;parent=ready(f);g=group(f);key=uuid4().hex;assert post(f,parent,g,key=key).status_code==201
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        if cap in ('READ','HOLD'):c.execute('UPDATE synthetic_resource_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',cap))
        elif cap=='EXECUTE':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        elif cap=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
        else:c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
    before=totals(f);assert post(f,parent,g,key=key).status_code==403 and totals(f)==before


def test_preparation_reopen_requires_explicit_rebind_preserves_resource_capacity(link_fixture):
    f=link_fixture;parent=ready(f);g=group(f);old=post(f,parent,g).json()
    parent=preparation_command(f,parent,'REOPEN',reason='SYNTHETIC changed materials').json()
    assert get(f,parent).json()['current']['reasons']==['PREPARATION_CHANGED']
    assert post(f,parent,g,revision=1).status_code==409
    assert rc.read(f[0],f[2]['fixture-a'],UUID(g['id']))['combination']['state']=='CONFIRMED'
    parent=preparation_command(f,parent,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC recheck').json();parent=preparation_command(f,parent,'CONFIRM',reason='SYNTHETIC reapproval').json()
    row=post(f,parent,g,revision=1);assert row.status_code==201
    now=row.json();assert now['link_revision']==2 and now['current']['status']=='CURRENT' and now['history'][0]['record']==old['history'][0]['record']
    assert totals(f)==[1,2]

@pytest.mark.parametrize('bad',['cancelled','ended','rule','disabled'])
def test_unusable_combo_cannot_create_claim_or_link(link_fixture,bad):
    f=link_fixture;parent=ready(f);g=group(f)
    if bad=='cancelled':cancel(f,g['id'])
    else:
        with f[1].connect() as c:
            if bad=='ended':c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '2 hours',ends_at=clock_timestamp()-interval '1 hour' WHERE id=%s",(UUID(g['members'][0]['id']),))
            else:c.execute('UPDATE synthetic_resources SET '+('revision=revision+1' if bad=='rule' else 'enabled=false')+' WHERE id=%s',(UUID(g['members'][0]['resource_id']),))
    assert post(f,parent,g).status_code==409 and totals(f)==[0,0]
    view=f[3].get('/api/preparations/'+parent['preparation_id']+'/resource-link-candidates',headers=headers(f[2])).json();assert view['items'][0]['eligible'] is False


def test_stale_revision_and_key_fingerprint_rejected(link_fixture):
    f=link_fixture;parent=ready(f);g=group(f);key=uuid4().hex;assert post(f,parent,g,key=key).status_code==201
    assert post(f,parent,g,key=key,reason='SYNTHETIC changed').status_code==409
    assert post(f,parent,g,revision=0).status_code==409
    assert post(f,parent,g,revision=1,expected_preparation_revision=1).status_code==409
    assert totals(f)==[1,1]

@pytest.mark.parametrize('same_case',[True,False])
def test_concurrent_same_combination_claim_or_same_case_cas(link_fixture,same_case):
    f=link_fixture;first=ready(f);second=first if same_case else ready(f);g=group(f)
    def bind(parent):
        try:return cr.bind(f[0],f[2]['fixture-a'],UUID(parent['preparation_id']),uuid4().hex,cr.Bind(combination_id=g['id'],expected_preparation_revision=parent['revision'],expected_link_revision=0,reason='SYNTHETIC parallel'))['link_revision']
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(bind,[first,second]))
    assert results.count('CONFLICT')==1 and totals(f)==[1,1]


def test_insert_failure_rolls_back_claim_and_history(link_fixture):
    f=link_fixture;parent=ready(f);g=group(f)
    with f[1].connect() as c:c.execute('REVOKE INSERT ON case_resource_links FROM parkweave_app')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):cr.bind(f[0],f[2]['fixture-a'],UUID(parent['preparation_id']),uuid4().hex,cr.Bind(combination_id=g['id'],expected_preparation_revision=parent['revision'],expected_link_revision=0,reason='SYNTHETIC rollback'))
    assert totals(f)==[0,0]


def test_immutable_tables_and_marker_repeat_preserve_history(link_fixture):
    f=link_fixture;parent=ready(f);g=group(f);post(f,parent,g);before=get(f,parent).json()
    for table in ('resource_case_claims','case_resource_links'):
        for action in ('DELETE FROM '+table,'UPDATE '+table+' SET owner_id=owner_id'):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with f[0].connect() as c:c.execute(action)
    with f[1].connect() as c:c.execute('DELETE FROM schema_version WHERE version=14')
    f[1].migrate();f[1].migrate();after=get(f,parent).json();before.pop('server_time');after.pop('server_time');assert after==before


@pytest.mark.parametrize('cap',['HOLD','EXECUTE'])
def test_read_only_history_and_candidate_operation_authorization(link_fixture,cap):
    f=link_fixture;parent=ready(f);g=group(f);assert post(f,parent,g).status_code==201
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        if cap=='HOLD':c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
        else:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    assert get(f,parent).status_code==200
    catalog=f[3].get('/api/preparations/'+parent['preparation_id']+'/resource-link-candidates',headers=headers(f[2])).json()
    if cap=='HOLD':assert not catalog['items'][0]['eligible'] and catalog['items'][0]['reason']=='RESOURCE_HOLD_PERMISSION_REQUIRED'
    else:assert not catalog['ready'] and catalog['blocked_reason']=='OWNER_EXECUTE_REQUIRED'
    assert post(f,parent,g,revision=1).status_code==403


def test_same_key_concurrency_and_cross_case_fingerprint(link_fixture):
    f=link_fixture;parent=ready(f);g=group(f);key=uuid4().hex
    def bind(_):return cr.bind(f[0],f[2]['fixture-a'],UUID(parent['preparation_id']),key,cr.Bind(combination_id=g['id'],expected_preparation_revision=parent['revision'],expected_link_revision=0,reason='SYNTHETIC replay'))['event']['id']
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(bind,range(2)))
    assert ids[0]==ids[1] and totals(f)==[1,1]
    second=ready(f);assert post(f,second,g,key=key,reason='SYNTHETIC replay').status_code==409 and totals(f)==[1,1]


def test_bind_cancel_race_has_serial_history_without_half_claim(link_fixture):
    f=link_fixture;parent=ready(f);g=group(f)
    def bind():
        try:return cr.bind(f[0],f[2]['fixture-a'],UUID(parent['preparation_id']),uuid4().hex,cr.Bind(combination_id=g['id'],expected_preparation_revision=parent['revision'],expected_link_revision=0,reason='SYNTHETIC competing cancel'))['link_revision']
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:
        binding=pool.submit(bind);cancelling=pool.submit(rc.cancel,f[0],f[2]['fixture-a'],UUID(g['id']),uuid4().hex);outcome=binding.result();cancelling.result()
    assert totals(f)==([0,0] if outcome=='CONFLICT' else [1,1])
    view=get(f,parent).json()
    assert view['current'] is None if outcome=='CONFLICT' else view['current']['reasons']==['RESOURCE_CANCELLED']


def test_replacement_retains_old_claim_capacity_and_history_read_only(link_fixture):
    f=link_fixture;parent=ready(f);old=group(f);assert post(f,parent,old).status_code==201;new=group(f)
    assert post(f,parent,new,revision=1).status_code==201
    assert totals(f)==[2,2] and rc.read(f[0],f[2]['fixture-a'],UUID(old['id']))['combination']['state']=='CONFIRMED'
    second=ready(f);assert post(f,second,old).status_code==409
    # New selection writes need HOLD only on the selected resource; history remains READ.
    with f[1].connect() as c:
        c.execute("UPDATE synthetic_resource_holds SET created_at=clock_timestamp()-interval '2 hours',expires_at=clock_timestamp()-interval '1 hour' WHERE id=ANY(%s)",([UUID(h['id']) for h in new['members']],))
    assert get(f,parent).json()['current']['status']=='CURRENT'


def test_real_schema13_upgrade_preserves_existing_preparation_and_combination(link_fixture):
    f=link_fixture;parent=ready(f);g=group(f)
    with f[1].connect() as c:
        c.execute('DROP TABLE case_resource_links,resource_case_claims')
        c.execute('DELETE FROM schema_version WHERE version>=14')
        assert c.execute('SELECT max(version) n FROM schema_version').fetchone()['n']==13
    f[1].migrate();f[1].migrate()
    with f[1].connect() as c:c.execute('GRANT SELECT,INSERT ON resource_case_claims,case_resource_links TO parkweave_app')
    assert rc.read(f[0],f[2]['fixture-a'],UUID(g['id']))['combination']['state']=='CONFIRMED'
    assert post(f,parent,g).status_code==201 and get(f,parent).json()['current']['status']=='CURRENT'


def test_confirmed_reservation_survives_hold_ttl_but_hold_id_is_not_combo(link_fixture):
    f=link_fixture;parent=ready(f);g=group(f)
    assert post(f,parent,{'id':g['members'][0]['id']}).status_code==403 and totals(f)==[0,0]
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_holds SET created_at=clock_timestamp()-interval '2 hours',expires_at=clock_timestamp()-interval '1 hour' WHERE id=ANY(%s)",([UUID(h['id']) for h in g['members']],))
    assert post(f,parent,g).status_code==201 and get(f,parent).json()['current']['status']=='CURRENT'


def test_read_reopen_race_returns_coherent_preparation_snapshot(link_fixture):
    f=link_fixture;parent=ready(f);g=group(f);assert post(f,parent,g).status_code==201
    with ThreadPoolExecutor(max_workers=2) as pool:
        reading=pool.submit(cr.read,f[0],f[2]['fixture-a'],UUID(parent['preparation_id']))
        opening=pool.submit(preparation_command,f,parent,'REOPEN',reason='SYNTHETIC parallel reopen')
        view=reading.result();assert opening.result().status_code==200
    assert view['current']['reasons']==([] if view['preparation_revision']==parent['revision'] else ['PREPARATION_CHANGED'])
    assert get(f,parent).json()['current']['reasons']==['PREPARATION_CHANGED'] and totals(f)==[1,1]
