"""Actual PG/API internal dispatch, current authorization and atomic receipt handoff."""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4
import psycopg
import pytest
from pydantic import ValidationError
from parkweave import service_dispatches as sd, executor_receipts as er
from parkweave.store import Conflict, Store
from test_executor_receipts import receipt_fixture, ready, create as legacy_create, act as receipt_act
from test_preparation import preparation_fixture, headers, command as prep_command

REVIEWER = 'prep-specialist-fixture-a'


def counts(f):
    with f[1].connect() as c:
        return [c.execute('SELECT count(*) n FROM ' + t).fetchone()['n'] for t in
                ('service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps','service_receipt_events')]


def offer(f,parent=None,user=REVIEWER,key=None,revision=0,executor='executor-a',**extra):
    parent = parent or ready(f)
    body = dict(expected_preparation_revision=parent['revision'],expected_dispatch_revision=revision,
                executor_id=executor,reason='SYNTHETIC explicit responsibility offer')
    body.update(extra)
    r = f[3].post('/api/preparations/'+parent['preparation_id']+'/dispatch',headers=headers(f[2],user,key or uuid4().hex),json=body)
    return r,parent,body


def command(f,row,action,user=None,key=None,**extra):
    user = user or (REVIEWER if action=='WITHDRAW' else row['current_offer']['executor_id'])
    body = dict(action=action,expected_revision=row['revision'],reason='SYNTHETIC explicit '+action)
    body.update(extra)
    return f[3].post('/api/service-dispatches/'+row['dispatch_id']+'/commands',headers=headers(f[2],user,key or uuid4().hex),json=body)


def read(f,row,user=REVIEWER):
    return f[3].get('/api/service-dispatches/'+row['dispatch_id'],headers=headers(f[2],user))


def test_decline_reoffer_accept_receipt_and_reload_persistence(receipt_fixture):
    f=receipt_fixture;r,parent,_=offer(f);assert r.status_code==201;row=r.json()
    assert row['revision']==1 and row['current_offer']['state']=='OFFERED'
    before_assignment=None
    with f[1].connect() as c:before_assignment=c.execute('SELECT * FROM run_assignments ORDER BY principal_id').fetchall()
    row=command(f,row,'DECLINE').json();assert row['current_offer']['state']=='DECLINED'
    row=offer(f,parent,revision=row['revision'])[0].json();assert len(row['offers'])==2
    row=command(f,row,'ACCEPT').json();assert row['current_offer']['state']=='ACCEPTED' and row['revision']==4
    id=row['receipt_step_id'];receipt=f[3].get('/api/executor-receipts/'+id,headers=headers(f[2],'executor-a')).json()
    assert receipt['step']['executor_id']=='executor-a' and receipt['history'][0]['payload']['actor_id']=='executor-a'
    receipt=receipt_act(f,receipt,'SUBMIT').json();receipt=receipt_act(f,receipt,'ACKNOWLEDGE').json()
    assert receipt['step']['state']=='LOCAL_ACKNOWLEDGED' and not receipt['case_goal_completed']
    assert [e['action'] for e in row['history']]==['OFFER','DECLINE','REOFFER','ACCEPT']
    assert sd.read(Store(f[0].dsn),f[2][REVIEWER],UUID(row['dispatch_id']))['revision']==4
    with f[1].connect() as c:assert c.execute('SELECT * FROM run_assignments ORDER BY principal_id').fetchall()==before_assignment
    assert row['qualification']=='NOT_EVALUATED' and row['offline_fulfillment']=='NO_EVIDENCE'


@pytest.mark.parametrize('user',['fixture-a','fixture-b','fixture-c','executor-a','unassigned','prep-specialist-fixture-b'])
def test_only_current_assigned_reviewer_can_offer(receipt_fixture,user):
    f=receipt_fixture;parent=ready(f);before=counts(f)
    assert offer(f,parent,user=user)[0].status_code==403 and counts(f)==before


@pytest.mark.parametrize('executor',['unassigned','executor-b','executor-c',REVIEWER,'fixture-a'])
def test_candidates_cannot_create_or_expand_assignment(receipt_fixture,executor):
    f=receipt_fixture;parent=ready(f);before=counts(f)
    catalog=f[3].get('/api/service-dispatches/catalog?preparation_id='+parent['preparation_id'],headers=headers(f[2],REVIEWER)).json()
    assert catalog['executors']==[{'id':'executor-a'}] and catalog['ready']
    assert offer(f,parent,executor=executor)[0].status_code==403 and counts(f)==before
    with f[1].connect() as c:assert not c.execute("SELECT 1 FROM run_assignments WHERE principal_id='unassigned'").fetchone()


@pytest.mark.parametrize('action,user',[('ACCEPT','fixture-a'),('DECLINE',REVIEWER),('WITHDRAW','executor-a'),('ACCEPT','unassigned'),('WITHDRAW','prep-specialist-fixture-b')])
def test_counterparty_and_unassigned_actions_denied(receipt_fixture,action,user):
    f=receipt_fixture;r,_,_=offer(f);row=r.json();before=counts(f)
    assert command(f,row,action,user).status_code==403 and counts(f)==before
    if user=='unassigned':assert read(f,row,user).status_code==403


def test_current_own_projection_after_reassignment_never_other_executor_or_materials(receipt_fixture):
    f=receipt_fixture;r,parent,_=offer(f);row=r.json();row=command(f,row,'DECLINE').json()
    f[1].assign_status('unassigned',UUID(parent['run_id']),active=True)
    current=offer(f,parent,revision=row['revision'],executor='unassigned')[0].json()
    old=read(f,current,'executor-a');assert old.status_code==200;view=old.json()
    assert not view['is_current_offer'] and view['current_offer']['state']=='DECLINED'
    assert len(view['offers'])==1 and len(view['history'])==2
    assert 'unassigned' not in old.text and 'material_history' not in old.text and 'SYNTHETIC material list' not in old.text
    assert command(f,view,'ACCEPT','executor-a').status_code==409
    for user in ('fixture-b','fixture-c','executor-b','executor-c'):
        assert read(f,current,user).status_code==403
        assert f[3].get('/api/service-dispatches',headers=headers(f[2],user)).json()['items']==[]


@pytest.mark.parametrize('change',['executor_assignment','executor_read','executor_inactive','executor_role','executor_org','reviewer_read','reviewer_grant','owner_execute','owner_grant','parent_revision','parent_hash','parent_state'])
def test_accept_rechecks_live_authority_and_parent_without_side_effects(receipt_fixture,change):
    f=receipt_fixture;r,parent,_=offer(f);row=r.json();before=counts(f)
    with f[1].connect() as c:
        who=REVIEWER if change.startswith('reviewer') else 'fixture-a' if change.startswith('owner') else 'executor-a'
        f[1].lock_principal(c,who,exclusive=True)
        if change=='executor_assignment':c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
        elif change in ('executor_read','reviewer_read','owner_execute'):
            c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',(who,'EXECUTE' if change=='owner_execute' else 'READ'))
        elif change in ('reviewer_grant','owner_grant'):c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(who,))
        elif change.startswith('executor_'):c.execute("UPDATE principals SET "+{'executor_inactive':'active=false','executor_role':"role='resource_admin'",'executor_org':"org_id='org-b'"}[change]+" WHERE id='executor-a'")
        else:c.execute('UPDATE preparations SET '+{'parent_revision':'revision=revision+1','parent_hash':"review_sha256=repeat('0',64)",'parent_state':"state='IN_PREPARATION',review_sha256=NULL"}[change]+' WHERE id=%s',(UUID(parent['preparation_id']),))
    assert command(f,row,'ACCEPT').status_code==(409 if change.startswith('parent') else 403) and counts(f)==before


def test_withdraw_after_target_revoked_and_parent_reopened_then_fresh_reoffer(receipt_fixture):
    f=receipt_fixture;r,parent,_=offer(f);row=r.json()
    f[1].assign_status('executor-a',UUID(parent['run_id']),active=False)
    assert prep_command(f,parent,'REOPEN',reason='SYNTHETIC changed documents').status_code==200
    row=command(f,row,'WITHDRAW').json();assert row['current_offer']['state']=='WITHDRAWN' and row['dependency']=='DEPENDENCY_CHANGED'
    assert offer(f,parent,revision=row['revision'])[0].status_code==403
    assert counts(f)==[1,1,2,0,0]


@pytest.mark.parametrize('decision',['DECLINE','WITHDRAW','ACCEPT'])
def test_legacy_create_cannot_bypass_any_new_dispatch_state(receipt_fixture,decision):
    f=receipt_fixture;r,parent,_=offer(f);row=r.json()
    assert legacy_create(f,parent)[0].status_code==409
    row=command(f,row,decision).json();before=counts(f)
    assert legacy_create(f,parent)[0].status_code==409 and counts(f)==before
    if decision=='ACCEPT':
        assert command(f,row,'WITHDRAW').status_code==409
        assert offer(f,parent,revision=row['revision'])[0].status_code==409


def test_existing_legacy_receipt_replay_preserved_new_offer_denied(receipt_fixture):
    f=receipt_fixture;key=uuid4().hex;r,parent,_=legacy_create(f,key=key);assert r.status_code==201
    assert offer(f,parent)[0].status_code==409
    assert legacy_create(f,parent,key=key)[0].json()==r.json()
    assert counts(f)==[0,0,0,1,1]


def test_old_offer_and_accept_replay_never_revives_state_or_duplicates_receipt(receipt_fixture):
    f=receipt_fixture;key=uuid4().hex;r,parent,_=offer(f,key=key);initial=r.json();akey=uuid4().hex
    done=command(f,initial,'ACCEPT',key=akey).json();before=counts(f)
    replay=offer(f,parent,key=key)[0].json();assert replay['event']==initial['event'] and replay['current_offer']['state']=='ACCEPTED'
    assert command(f,initial,'ACCEPT',key=akey).json()['event']==done['event']
    assert command(f,initial,'ACCEPT',key=akey,reason='SYNTHETIC different').status_code==409 and counts(f)==before
    f[1].assign_status('executor-a',UUID(parent['run_id']),active=False)
    assert command(f,initial,'ACCEPT',key=akey).status_code==403


@pytest.mark.parametrize('other',['WITHDRAW','DECLINE','ACCEPT'])
def test_concurrent_accept_and_decision_one_atomic_winner(receipt_fixture,other):
    f=receipt_fixture;r,_,_=offer(f);row=r.json()
    def send(action):
        try:
            p=REVIEWER if action=='WITHDRAW' else 'executor-a'
            return sd.command(f[0],f[2][p],UUID(row['dispatch_id']),uuid4().hex,sd.Command(action=action,expected_revision=1,reason='SYNTHETIC concurrent'))['current_offer']['state']
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(send,['ACCEPT',other]))
    assert out.count('CONFLICT')==1
    after=counts(f);assert after[:3]==[1,1,2] and after[3:]==([1,1] if 'ACCEPTED' in out else [0,0])


def test_same_key_concurrent_accept_replays_once_and_event_failure_rolls_back(receipt_fixture):
    f=receipt_fixture;r,_,_=offer(f);row=r.json();key=uuid4().hex
    body=sd.Command(action='ACCEPT',expected_revision=1,reason='SYNTHETIC accept')
    def send(_):return sd.command(f[0],f[2]['executor-a'],UUID(row['dispatch_id']),key,body)['event']
    with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(send,range(2)))
    assert out[0]==out[1] and counts(f)==[1,1,2,1,1]
    r,_,_=offer(f);row=r.json();before=counts(f)
    with f[1].connect() as c:c.execute('REVOKE INSERT ON service_dispatch_events FROM parkweave_app')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):sd.command(f[0],f[2]['executor-a'],UUID(row['dispatch_id']),uuid4().hex,body)
    assert counts(f)==before and read(f,row).json()['current_offer']['state']=='OFFERED'


def test_migration_repeat_minimal_table_permissions_and_immutable_history(receipt_fixture):
    f=receipt_fixture;r,_,_=offer(f);row=r.json();before=read(f,row).json();f[1].migrate();f[1].migrate()
    assert read(f,row).json()==before
    for sql in ('DELETE FROM service_dispatches','UPDATE service_dispatches SET preparation_id=preparation_id','UPDATE service_dispatch_offers SET executor_id=executor_id','UPDATE service_dispatch_offers SET reason=reason','DELETE FROM service_dispatch_offers','UPDATE service_dispatch_events SET payload=payload','DELETE FROM service_dispatch_events','UPDATE run_assignments SET active=active','UPDATE preparation_grants SET active=active'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute(sql)


@pytest.mark.parametrize('mutation',[{'reason':' '},{'reason':'x'*1001},{'expected_dispatch_revision':True},{'actor_id':'spoof'},{'executor_id':' '},{'expected_preparation_revision':0}])
def test_strict_offer_shape(mutation):
    body=dict(expected_preparation_revision=1,expected_dispatch_revision=0,executor_id='executor-a',reason='SYNTHETIC reason');body.update(mutation)
    with pytest.raises(ValidationError):sd.Offer(**body)


def test_exact14_upgrade_keeps_legacy_receipt_and_creates_dispatch_tables(receipt_fixture):
    f=receipt_fixture;r,parent,_=legacy_create(f);before=r.json()
    with f[1].connect() as c:
        c.execute('DROP TABLE dispatch_notices,dispatch_notice_outbox')
        c.execute('DROP TABLE service_dispatch_events,service_dispatch_offers,service_dispatches CASCADE')
        c.execute('DELETE FROM schema_version WHERE version>=15')
        assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']==14
    f[1].migrate();f[1].migrate()
    with f[1].connect() as c:
        c.execute('GRANT SELECT,INSERT ON service_dispatches,service_dispatch_offers,service_dispatch_events TO parkweave_app')
        c.execute('GRANT UPDATE(revision,current_offer_id) ON service_dispatches TO parkweave_app')
        c.execute('GRANT UPDATE(state,receipt_step_id) ON service_dispatch_offers TO parkweave_app')
    assert f[3].get('/api/executor-receipts/'+before['step']['id'],headers=headers(f[2])).json()['step']==before['step']
    assert counts(f)==[0,0,0,1,1] and offer(f,parent)[0].status_code==409


def test_legacy_create_races_first_offer_and_cannot_race_accepted_handoff(receipt_fixture):
    f=receipt_fixture;parent=ready(f)
    legacy=er.Create(preparation_id=parent['preparation_id'],expected_preparation_revision=parent['revision'],executor_id='executor-a')
    offered=sd.Offer(expected_preparation_revision=parent['revision'],expected_dispatch_revision=0,executor_id='executor-a',reason='SYNTHETIC offer')
    def send(kind):
        try:
            if kind=='LEGACY':er.create(f[0],f[2]['fixture-a'],uuid4().hex,legacy)
            else:sd.offer(f[0],f[2][REVIEWER],UUID(parent['preparation_id']),uuid4().hex,offered)
            return kind
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(send,['LEGACY','OFFER']))
    assert out.count('CONFLICT')==1
    assert counts(f) in ([0,0,0,1,1],[1,1,1,0,0])
    r,parent,_=offer(f);row=r.json()
    legacy=er.Create(preparation_id=parent['preparation_id'],expected_preparation_revision=parent['revision'],executor_id='executor-a')
    def handoff(kind):
        try:
            if kind=='LEGACY':er.create(f[0],f[2]['fixture-a'],uuid4().hex,legacy)
            else:sd.command(f[0],f[2]['executor-a'],UUID(row['dispatch_id']),uuid4().hex,sd.Command(action='ACCEPT',expected_revision=1,reason='SYNTHETIC accept'))
            return kind
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(handoff,['LEGACY','ACCEPT']))
    assert out==['CONFLICT','ACCEPT']


def test_exclusive_reviewer_revocation_is_bounded_then_all_reads_and_replays_deny(receipt_fixture):
    f=receipt_fixture;key=uuid4().hex;r,parent,_=offer(f,key=key);row=r.json();before=counts(f)
    with f[1].connect() as c:
        f[1].lock_principal(c,REVIEWER,exclusive=True)
        c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(REVIEWER,))
        with ThreadPoolExecutor(max_workers=1) as pool:response=pool.submit(command,f,row,'WITHDRAW').result(timeout=8)
        assert response.status_code==409
    assert command(f,row,'WITHDRAW').status_code==403
    assert read(f,row).status_code==403 and offer(f,parent,key=key)[0].status_code==403
    assert f[3].get('/api/service-dispatches',headers=headers(f[2],REVIEWER)).status_code==403 and counts(f)==before


def test_resource_admin_no_dispatch_role_even_with_run_read_assignment(receipt_fixture):
    f=receipt_fixture;r,parent,_=offer(f);row=r.json();before=counts(f)
    with f[1].connect() as c:
        f[1].lock_principal(c,'executor-a',exclusive=True)
        c.execute("UPDATE principals SET role='resource_admin' WHERE id='executor-a'")
    assert command(f,row,'ACCEPT').status_code==403
    assert read(f,row,'executor-a').status_code==403
    assert offer(f,parent,user='executor-a')[0].status_code==403
    assert f[3].get('/api/service-dispatches',headers=headers(f[2],'executor-a')).status_code==403 and counts(f)==before


def test_history_limit_reserves_last_decision_and_remains_readable(receipt_fixture):
    f=receipt_fixture;r,parent,_=offer(f);row=r.json()
    with f[1].connect() as c:c.execute('UPDATE service_dispatches SET revision=63 WHERE id=%s',(UUID(row['dispatch_id']),))
    row=read(f,row).json();row=command(f,row,'WITHDRAW').json();assert row['revision']==64
    catalog=f[3].get('/api/service-dispatches/catalog?preparation_id='+parent['preparation_id'],headers=headers(f[2],REVIEWER)).json()
    assert not catalog['ready'] and catalog['history_limit_reached']
    before=counts(f);assert offer(f,parent,revision=64)[0].status_code==409 and counts(f)==before


def test_stale_decline_allowed_but_old_withdraw_replay_does_not_withdraw_new_offer(receipt_fixture):
    f=receipt_fixture;r,parent,_=offer(f);row=r.json();key=uuid4().hex
    old=command(f,row,'WITHDRAW',key=key).json()
    current=offer(f,parent,revision=old['revision'])[0].json()
    replay=command(f,row,'WITHDRAW',key=key).json();assert replay['event']==old['event'] and replay['current_offer']['state']=='OFFERED'
    assert prep_command(f,parent,'REOPEN',reason='SYNTHETIC changed source').status_code==200
    assert command(f,current,'ACCEPT').status_code==409
    declined=command(f,current,'DECLINE').json();assert declined['current_offer']['state']=='DECLINED' and declined['dependency']=='DEPENDENCY_CHANGED'
