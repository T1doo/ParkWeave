"""Actual PG/API single-resource local synthetic confirmation contracts."""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID,uuid4
import psycopg
import pytest
from parkweave import resource_holds as rh
from parkweave.store import Store,Conflict
from test_resource_holds import resource_fixture,body,hold,preview,read,release,counts,configure
from test_preparation import headers


def confirm(f,id,revision=1,key=None,user='fixture-a',**extra):
    return f[3].post('/api/resource-holds/'+str(id)+'/confirm',headers=headers(f[2],user,key or uuid4().hex),json={'expected_revision':revision,**extra})


def expire(f,id):
    with f[1].connect() as c:
        c.execute("UPDATE synthetic_resource_holds SET created_at=clock_timestamp()-interval '10 seconds',expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(UUID(id),))


def test_confirm_keeps_capacity_beyond_hold_ttl_and_cancel_replay_history(resource_fixture):
    f=resource_fixture;data=body(f,quantity=2);h=hold(f,data).json()['hold'];id=h['id'];key=uuid4().hex
    x=confirm(f,id,key=key);assert x.status_code==200,x.text
    x=x.json();assert x['hold']['state']==x['receipt']['observed_state']=='CONFIRMED'
    assert x['hold']['local_confirmation']=='CONFIRMED' and x['reservation']=='NOT_CONFIRMED'
    assert x['external_acceptance']=='NOT_SUBMITTED' and x['offline_fulfillment']=='NO_EVIDENCE'
    assert x['hold']['expires_at']==h['expires_at'] and counts(f)==(1,2)
    assert x['hold']['resource_name']==h['resource_name']=='合成协作空间'
    expire(f,id)
    assert rh.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(id))['hold']['state']=='CONFIRMED'
    assert preview(f,data,'fixture-b').json()['occupied_peak']==2
    assert hold(f,data,'fixture-b').status_code==409
    assert confirm(f,id,key=key).json()['receipt']==x['receipt']
    assert confirm(f,id).status_code==409
    released=release(f,id).json()['hold'];assert released['state']=='RELEASED' and released['resource_name']==h['resource_name']
    replay=confirm(f,id,key=key).json();assert replay['receipt']==x['receipt'] and replay['hold']['state']=='RELEASED'
    assert preview(f,data,'fixture-b').json()['occupied_peak']==0
    assert hold(f,data,'fixture-b').status_code==201


@pytest.mark.parametrize('change',['expired','released','revision','disabled','window','capacity'])
def test_current_rules_and_hold_deadline_refuse_without_receipt(resource_fixture,change):
    f=resource_fixture;h=hold(f,body(f,quantity=2)).json()['hold'];id=h['id']
    if change=='expired':expire(f,id)
    elif change=='released':release(f,id)
    elif change=='revision':configure(f,buffer_seconds=0)
    else:
        # Isolate each recheck independently of revision; explicit owner-only damaged fixture.
        with f[1].connect() as c:
            rh._lock(c,rh.RESOURCE_ID)
            sql={'disabled':'enabled=false','window':"open_until=clock_timestamp()+interval '30 minutes'",'capacity':'capacity=1'}[change]
            c.execute('UPDATE synthetic_resources SET '+sql+' WHERE id=%s',(rh.RESOURCE_ID,))
    before=counts(f);assert confirm(f,id).status_code==409 and counts(f)==before


def test_concurrent_same_key_once_distinct_keys_and_release_order(resource_fixture):
    f=resource_fixture;id=hold(f).json()['hold']['id'];key=uuid4().hex;data=rh.Confirm(expected_revision=1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        xs=list(pool.map(lambda _:rh.confirm(f[0],f[2]['fixture-a'],UUID(id),key,data),range(2)))
    assert xs[0]['receipt']==xs[1]['receipt'] and counts(f)==(1,2)
    assert confirm(f,id,key=key,revision=2).status_code==409
    assert release(f,id,key=key).status_code==409
    release(f,id)
    assert confirm(f,id).status_code==409
    id=hold(f).json()['hold']['id']
    def command(action):
        try:
            return rh.confirm(f[0],f[2]['fixture-a'],UUID(id),uuid4().hex,data) if action=='confirm' else rh.release(f[0],f[2]['fixture-a'],UUID(id),uuid4().hex)
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:xs=list(pool.map(command,['confirm','release']))
    assert read(f,id).json()['hold']['state']=='RELEASED'
    assert sum(x=='CONFLICT' for x in xs)<=1


@pytest.mark.parametrize('target',['active','role','org','READ','EXECUTE','resource_READ','resource_HOLD'])
def test_confirm_replay_requires_current_authorization(resource_fixture,target):
    f=resource_fixture;id=hold(f).json()['hold']['id'];key=uuid4().hex;assert confirm(f,id,key=key).status_code==200
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        if target=='active':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif target=='role':c.execute("UPDATE principals SET role='resource_admin' WHERE id='fixture-a'")
        elif target=='org':c.execute("UPDATE principals SET org_id='org-x' WHERE id='fixture-a'")
        elif target.startswith('resource_'):c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability=%s",(target.removeprefix('resource_'),))
        else:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability=%s",(target,))
    assert confirm(f,id,key=key).status_code==403 and counts(f)==(1,2)


def test_cross_owner_unknown_hold_and_client_authority_refused(resource_fixture):
    f=resource_fixture;id=hold(f).json()['hold']['id']
    assert confirm(f,id,user='fixture-b').status_code==confirm(f,id,user='fixture-c').status_code==403
    assert confirm(f,str(uuid4())).status_code==403
    for extra in ({'quantity':2},{'confirmed':True},{'role':'enterprise_operator'},{'resources':[]}):
        assert confirm(f,id,**extra).status_code==422
    assert confirm(f,id,revision=True).status_code==422 and counts(f)==(1,1)


def test_receipt_failure_rolls_back_confirmation_and_upgrade_keeps_history(resource_fixture):
    f=resource_fixture;id=hold(f).json()['hold']['id']
    with f[1].connect() as c:c.execute('REVOKE INSERT ON synthetic_resource_receipts FROM parkweave_app')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):rh.confirm(f[0],f[2]['fixture-a'],UUID(id),uuid4().hex,rh.Confirm(expected_revision=1))
    assert read(f,id).json()['hold']['state']=='HELD' and counts(f)==(1,1)
    with f[1].connect() as c:
        c.execute('GRANT INSERT ON synthetic_resource_receipts TO parkweave_app')
        c.execute('DELETE FROM schema_version WHERE version>=11')
        c.execute('DROP TABLE synthetic_resource_combination_receipts,synthetic_resource_combination_members,synthetic_resource_combinations')
        c.execute('ALTER TABLE synthetic_resource_holds DROP CONSTRAINT synthetic_resource_holds_state_check')
        c.execute("ALTER TABLE synthetic_resource_holds ADD CONSTRAINT synthetic_resource_holds_state_check CHECK(state IN ('HELD','RELEASED'))")
        c.execute('ALTER TABLE synthetic_resource_receipts DROP CONSTRAINT synthetic_resource_receipts_action_check')
        c.execute("ALTER TABLE synthetic_resource_receipts ADD CONSTRAINT synthetic_resource_receipts_action_check CHECK(action IN ('HOLD','RELEASE'))")
    f[1].migrate();f[1].migrate()
    with f[1].connect() as c:
        c.execute('GRANT SELECT,INSERT ON synthetic_resource_combinations,synthetic_resource_combination_members,synthetic_resource_combination_receipts TO parkweave_app')
        c.execute('GRANT UPDATE(state) ON synthetic_resource_combinations TO parkweave_app')
    assert counts(f)==(1,1)
    assert confirm(f,id).status_code==200


def test_confirm_uses_clock_after_lock_wait_and_never_revives_expired_hold(resource_fixture,monkeypatch):
    import threading
    f=resource_fixture;id=hold(f).json()['hold']['id'];entered=threading.Event();original=rh._lock
    def signal(c,id,shared=False):entered.set();return original(c,id,shared)
    monkeypatch.setattr(rh,'_lock',signal)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            original(c,rh.RESOURCE_ID)
            c.execute("UPDATE synthetic_resource_holds SET expires_at=clock_timestamp()+interval '0.15 seconds' WHERE id=%s",(UUID(id),))
            future=pool.submit(rh.confirm,f[0],f[2]['fixture-a'],UUID(id),uuid4().hex,rh.Confirm(expected_revision=1))
            assert entered.wait(2);c.execute('SELECT pg_sleep(0.2)')
        with pytest.raises(Conflict,match='valid unconfirmed'):future.result(timeout=5)
    assert read(f,id).json()['hold']['state']=='EXPIRED' and counts(f)==(1,1)


def test_two_owners_confirm_at_capacity_without_double_count_and_new_key_once(resource_fixture):
    f=resource_fixture;data=body(f);a=hold(f,data).json()['hold']['id'];b=hold(f,data,'fixture-b').json()['hold']['id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        xs=list(pool.map(lambda pair:rh.confirm(f[0],f[2][pair[0]],UUID(pair[1]),uuid4().hex,rh.Confirm(expected_revision=1)),[('fixture-a',a),('fixture-b',b)]))
    assert all(x['hold']['state']=='CONFIRMED' for x in xs) and preview(f,data).json()['occupied_peak']==2
    assert counts(f)==(2,4)


def test_same_hold_distinct_confirmation_keys_commit_once(resource_fixture):
    f=resource_fixture;id=hold(f).json()['hold']['id']
    def write(_):
        try:return rh.confirm(f[0],f[2]['fixture-a'],UUID(id),uuid4().hex,rh.Confirm(expected_revision=1))
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:xs=list(pool.map(write,range(2)))
    assert xs.count('CONFLICT')==1 and counts(f)==(1,2)
    assert read(f,id).json()['hold']['state']=='CONFIRMED'


def test_revocation_committed_while_confirmation_waits_prevents_write(resource_fixture,monkeypatch):
    import threading
    from parkweave.store import Denied
    f=resource_fixture;id=hold(f).json()['hold']['id'];entered=threading.Event();original=f[0].lock_principal
    def signal(c,id,exclusive=False):entered.set();return original(c,id,exclusive)
    monkeypatch.setattr(f[0],'lock_principal',signal)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            f[1].lock_principal(c,'fixture-a',exclusive=True)
            c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
            future=pool.submit(rh.confirm,f[0],f[2]['fixture-a'],UUID(id),uuid4().hex,rh.Confirm(expected_revision=1))
            assert entered.wait(2)
        with pytest.raises(Denied):future.result(timeout=5)
    assert counts(f)==(1,1)
    with f[1].connect() as c:assert c.execute('SELECT state FROM synthetic_resource_holds WHERE id=%s',(UUID(id),)).fetchone()['state']=='HELD'
