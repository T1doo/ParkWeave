"""Actual isolated PG/API resource contracts; synthetic owner setup, no external booking."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, timezone
import secrets
import threading
from uuid import UUID, uuid4
import psycopg
import pytest
from parkweave import resource_holds as rh
from parkweave import preparation
from parkweave.store import Store,digest,Denied,Conflict
from test_preparation import headers,create as create_case,filled,read as read_preparation

@pytest.fixture
def resource_fixture(fixture):
    rh.seed_synthetic(fixture[1])
    return fixture


def body(f,quantity=1,ttl=120,**changes):
    with f[1].connect() as c:
        now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
        revision=c.execute('SELECT revision FROM synthetic_resources WHERE id=%s',(rh.RESOURCE_ID,)).fetchone()['revision']
    return {'starts_at':(now+timedelta(hours=1)).isoformat(),'ends_at':(now+timedelta(hours=2)).isoformat(),
            'quantity':quantity,'expected_revision':revision,'ttl_seconds':ttl,'purpose':'SYNTHETIC resource use',**changes}


def hold(f,data=None,user='fixture-a',key=None):
    return f[3].post('/api/synthetic-resources/'+str(rh.RESOURCE_ID)+'/holds',headers=headers(f[2],user,key or uuid4().hex),json=data or body(f))


def preview(f,data,user='fixture-a'):
    return f[3].post('/api/synthetic-resources/'+str(rh.RESOURCE_ID)+'/preview',headers=headers(f[2],user),json={k:data[k] for k in ('starts_at','ends_at','quantity')})


def read(f,id,user='fixture-a'):
    return f[3].get('/api/resource-holds/'+str(id),headers=headers(f[2],user))


def release(f,id,user='fixture-a',key=None):
    return f[3].post('/api/resource-holds/'+str(id)+'/release',headers=headers(f[2],user,key or uuid4().hex),json={})


def counts(f):
    with f[1].connect() as c:
        return tuple(c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('synthetic_resource_holds','synthetic_resource_receipts'))


def configure(f,**values):
    # Explicit isolated rule fixture; no product configuration or elevated app rights.
    assert set(values)<={'capacity','buffer_seconds','enabled','open_until'}
    with f[1].connect() as c:
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('synthetic-resource:'+str(rh.RESOURCE_ID),))
        c.execute('UPDATE synthetic_resources SET '+','.join(k+'=%s' for k in values)+',revision=revision+1 WHERE id=%s',(*values.values(),rh.RESOURCE_ID))


def test_api_hold_release_replay_persistent_receipts_and_case_separation(resource_fixture):
    f=resource_fixture;data=body(f);key=uuid4().hex
    before=counts(f);p=preview(f,data);assert p.status_code==200 and p.json()['available'] and p.json()['preview_only'] and counts(f)==before
    a=hold(f,data,key=key);assert a.status_code==201,a.text
    x=a.json();id=x['hold']['id'];assert x['hold']['state']=='HELD' and x['reservation']=='NOT_CONFIRMED' and x['external_acceptance']=='NOT_SUBMITTED' and x['offline_fulfillment']=='NO_EVIDENCE'
    assert hold(f,data,key=key).json()['receipt']==x['receipt'] and counts(f)==(1,1)
    assert str(rh.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(id))['hold']['id'])==id
    expired_at=x['hold']['expires_at'];release_key=uuid4().hex;b=release(f,id,key=release_key).json();assert b['hold']['state']=='RELEASED'
    assert release(f,id,key=release_key).json()['receipt']==b['receipt'] and counts(f)==(1,2)
    retry=hold(f,data,key=key).json();assert retry['hold']['state']=='RELEASED' and retry['hold']['expires_at']==expired_at and retry['receipt']==x['receipt']
    assert preview(f,data).json()['occupied_peak']==0
    next_hold=hold(f,data);assert next_hold.status_code==201 and next_hold.json()['hold']['id']!=id and counts(f)==(2,3)
    with f[1].connect() as c:assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==0


def test_peak_capacity_is_not_sum_of_nonoverlapping_holds(resource_fixture):
    f=resource_fixture;configure(f,buffer_seconds=0);data=body(f);start=rh.Hold(**data).starts_at
    a=dict(data,ends_at=(start+timedelta(minutes=30)).isoformat());b=dict(data,starts_at=a['ends_at'],ends_at=(start+timedelta(hours=1)).isoformat())
    assert hold(f,a).status_code==hold(f,b,user='fixture-b').status_code==201
    p=preview(f,data).json();assert p['occupied_peak']==1 and p['available_quantity']==1 and p['available']
    assert hold(f,data).status_code==201
    assert preview(f,data).json()['occupied_peak']==2 and not preview(f,data).json()['available']
    assert hold(f,data,user='fixture-b').status_code==409 and counts(f)==(3,3)


@pytest.mark.parametrize('buffer,gap_minutes,expected',[(0,0,201),(300,0,409),(300,5,409),(300,10,201)])
def test_half_open_intervals_and_both_sides_buffer(resource_fixture,buffer,gap_minutes,expected):
    f=resource_fixture;configure(f,capacity=1,buffer_seconds=buffer);a=body(f);assert hold(f,a).status_code==201
    parsed=rh.Hold(**a);b=dict(a,starts_at=(parsed.ends_at+timedelta(minutes=gap_minutes)).isoformat(),ends_at=(parsed.ends_at+timedelta(minutes=gap_minutes+30)).isoformat())
    assert hold(f,b,user='fixture-b').status_code==expected


def test_overcapacity_and_concurrent_distinct_keys_never_overbook(resource_fixture):
    f=resource_fixture;data=body(f);assert hold(f,dict(data,quantity=3)).status_code==409 and counts(f)==(0,0)
    def write(n):
        try:return rh.create(f[0],f[2]['fixture-a' if n%2==0 else 'fixture-b'],rh.RESOURCE_ID,uuid4().hex,rh.Hold(**data))['hold']['id']
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=6) as pool:result=list(pool.map(write,range(6)))
    assert result.count('CONFLICT')==4 and len({x for x in result if x!='CONFLICT'})==2
    with f[1].connect() as c:assert c.execute("SELECT sum(quantity) q FROM synthetic_resource_holds WHERE state='HELD' AND expires_at>clock_timestamp()").fetchone()['q']==2
    assert counts(f)==(2,2)


def test_same_key_concurrent_once_conflicts_and_UTC_normalization(resource_fixture):
    f=resource_fixture;data=body(f);key=uuid4().hex;model=rh.Hold(**data)
    with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(lambda _:rh.create(f[0],f[2]['fixture-a'],rh.RESOURCE_ID,key,model),range(2)))
    assert result[0]['hold']['id']==result[1]['hold']['id'] and result[0]['receipt']==result[1]['receipt'] and counts(f)==(1,1)
    equivalent=dict(data,starts_at=model.starts_at.astimezone(timezone(timedelta(hours=8))).isoformat(),ends_at=model.ends_at.astimezone(timezone(timedelta(hours=8))).isoformat())
    assert hold(f,equivalent,key=key).json()['receipt']==result[0]['receipt']
    assert hold(f,dict(data,purpose='different'),key=key).status_code==409 and release(f,result[0]['hold']['id'],key=key).status_code==409 and counts(f)==(1,1)


def test_expiration_without_cleaner_replay_does_not_extend_and_expired_release(resource_fixture):
    f=resource_fixture;configure(f,capacity=1);data=body(f);key=uuid4().hex;a=hold(f,data,key=key).json();id=a['hold']['id']
    with f[1].connect() as c:
        c.execute("UPDATE synthetic_resource_holds SET created_at=clock_timestamp()-interval '10 seconds',expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(UUID(id),))
    current=read(f,id).json();assert current['hold']['state']=='EXPIRED' and preview(f,data).json()['occupied_peak']==0
    replay=hold(f,data,key=key).json();assert replay['receipt']==a['receipt'] and replay['hold']['state']=='EXPIRED' and replay['hold']['expires_at']==current['hold']['expires_at'] and counts(f)==(1,1)
    r=release(f,id).json();assert r['hold']['state']==r['receipt']['observed_state']=='EXPIRED'
    with f[1].connect() as c:assert c.execute('SELECT state FROM synthetic_resource_holds WHERE id=%s',(UUID(id),)).fetchone()['state']=='HELD'
    assert hold(f,data,user='fixture-b').status_code==201


def test_clock_is_sampled_after_resource_lock_wait_not_transaction_start(resource_fixture,monkeypatch):
    f=resource_fixture;configure(f,capacity=1);data=body(f);id=hold(f,data).json()['hold']['id'];entered=threading.Event();original=rh._lock
    def signal(c,id,shared=False):entered.set();return original(c,id,shared)
    monkeypatch.setattr(rh,'_lock',signal)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('synthetic-resource:'+str(rh.RESOURCE_ID),))
            c.execute("UPDATE synthetic_resource_holds SET expires_at=clock_timestamp()+interval '0.15 seconds' WHERE id=%s",(UUID(id),))
            future=pool.submit(rh.create,f[0],f[2]['fixture-b'],rh.RESOURCE_ID,uuid4().hex,rh.Hold(**data))
            assert entered.wait(2)
            c.execute('SELECT pg_sleep(0.2)')
        assert future.result(timeout=5)['hold']['state']=='HELD'
    assert read(f,id).json()['hold']['state']=='EXPIRED'


def test_catalog_and_anonymous_availability_do_not_expose_other_enterprise_hold(resource_fixture):
    f=resource_fixture;data=body(f);a=hold(f,dict(data,purpose='SYNTHETIC PRIVATE PURPOSE')).json();id=a['hold']['id']
    p=preview(f,data,'fixture-b');assert p.status_code==200 and p.json()['occupied_peak']==1
    assert id not in p.text and 'PRIVATE PURPOSE' not in p.text and 'fixture-a' not in p.text and 'org-a' not in p.text
    assert read(f,id,'fixture-b').status_code==release(f,id,'fixture-b').status_code==403
    assert f[3].get('/api/resource-holds',headers=headers(f[2],'fixture-b')).json()['items']==[]
    assert f[3].get('/api/synthetic-resources',headers=headers(f[2],'fixture-c')).json()['items']==[]
    assert preview(f,data,'fixture-c').status_code==hold(f,data,'fixture-c').status_code==403
    assert counts(f)==(1,1)


def test_same_org_non_owner_cannot_read_or_release_hold(resource_fixture):
    f=resource_fixture;token=secrets.token_urlsafe(32);f[2]['same-org']=token
    with f[1].connect() as c:
        c.execute("INSERT INTO principals VALUES('same-org',%s,'park-a','org-a','enterprise_operator',true)",(digest(token),))
        for cap in ('READ','EXECUTE'):c.execute("INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES('same-org',%s,'park-a','org-a')",(cap,))
        for cap in ('READ','HOLD'):c.execute("INSERT INTO synthetic_resource_grants VALUES('same-org',%s,'park-a','org-a',%s,true)",(rh.RESOURCE_ID,cap))
    a=hold(f).json();id=a['hold']['id'];assert read(f,id,'same-org').status_code==release(f,id,'same-org').status_code==403
    assert f[3].get('/api/resource-holds',headers=headers(f[2],'same-org')).json()['items']==[]


@pytest.mark.parametrize('role',['park_specialist','resource_admin','service_executor'])
def test_explicit_grant_cannot_override_trusted_role_upper_bound(resource_fixture,role):
    f=resource_fixture;token=secrets.token_urlsafe(32);f[2]['wrong-role']=token
    with f[1].connect() as c:
        c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',('wrong-role',digest(token),'park-a','org-a',role))
        for cap in ('READ','EXECUTE'):c.execute("INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES('wrong-role',%s,'park-a','org-a')",(cap,))
        for cap in ('READ','HOLD'):c.execute("INSERT INTO synthetic_resource_grants VALUES('wrong-role',%s,'park-a','org-a',%s,true)",(rh.RESOURCE_ID,cap))
    data=body(f);assert preview(f,data,'wrong-role').status_code==hold(f,data,'wrong-role').status_code==403
    assert f[3].get('/api/synthetic-resources',headers=headers(f[2],'wrong-role')).status_code==403


@pytest.mark.parametrize('target',['active','role','org','READ','EXECUTE','resource_READ','resource_HOLD'])
def test_current_revocation_rechecked_before_replay_and_release(resource_fixture,target):
    f=resource_fixture;data=body(f);key=uuid4().hex;a=hold(f,data,key=key).json();id=a['hold']['id']
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        if target=='active':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif target=='role':c.execute("UPDATE principals SET role='resource_admin' WHERE id='fixture-a'")
        elif target=='org':c.execute("UPDATE principals SET org_id='org-x' WHERE id='fixture-a'")
        elif target.startswith('resource_'):c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability=%s",(target.removeprefix('resource_'),))
        else:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability=%s",(target,))
    assert hold(f,data,key=key).status_code==release(f,id).status_code==403 and counts(f)==(1,1)
    assert read(f,id).status_code==(200 if target in ('EXECUTE','resource_HOLD') else 403)
    rh.seed_synthetic(f[1])
    assert hold(f,data,key=key).status_code==403  # fixture setup never repairs revocation


@pytest.mark.parametrize('change',[{'quantity':0},{'quantity':21},{'quantity':True},{'ttl_seconds':4},{'ttl_seconds':301},{'purpose':' '},{'purpose':'x'*201},{'role':'enterprise_operator'},{'authority':'LOCAL_AUTHORITY'},{'expires_at':'2099-01-01T00:00:00Z'},{'confirmed':True}])
def test_invalid_shape_or_client_policy_is_not_trusted(resource_fixture,change):
    f=resource_fixture;data=body(f);assert hold(f,dict(data,**change)).status_code==422 and counts(f)==(0,0)


@pytest.mark.parametrize('window',['naive','reverse','zero','long','past','outside'])
def test_time_validation_including_DB_past_and_opening_buffer(resource_fixture,window):
    f=resource_fixture;data=body(f);model=rh.Hold(**data)
    if window=='naive':data['starts_at']=model.starts_at.replace(tzinfo=None).isoformat()
    elif window=='reverse':data['ends_at']=(model.starts_at-timedelta(minutes=1)).isoformat()
    elif window=='zero':data['ends_at']=data['starts_at']
    elif window=='long':data['ends_at']=(model.starts_at+timedelta(hours=4,seconds=1)).isoformat()
    elif window=='past':data.update(starts_at=(model.starts_at-timedelta(hours=2)).isoformat(),ends_at=(model.ends_at-timedelta(hours=2)).isoformat())
    else:
        with f[1].connect() as c:end=c.execute('SELECT open_until FROM synthetic_resources WHERE id=%s',(rh.RESOURCE_ID,)).fetchone()['open_until']
        data.update(starts_at=(end-timedelta(minutes=30)).isoformat(),ends_at=end.isoformat())
    assert hold(f,data).status_code==(422 if window in ('naive','reverse','zero','long') else 409) and counts(f)==(0,0)


def test_stale_rule_and_disable_rechecked_but_old_receipts_stay_historical(resource_fixture):
    f=resource_fixture;data=body(f);key=uuid4().hex;a=hold(f,data,key=key).json();id=a['hold']['id'];configure(f,enabled=False)
    assert hold(f,data).status_code==409 and preview(f,data).status_code==409
    assert hold(f,data,key=key).json()['receipt']==a['receipt'] and read(f,id).json()['hold']['state']=='HELD'
    assert release(f,id).json()['hold']['state']=='RELEASED'
    configure(f,enabled=True);assert hold(f,data).status_code==409
    assert hold(f,body(f)).status_code==201


def test_failed_receipt_insert_rolls_back_hold_and_registry_cannot_be_changed_by_app(resource_fixture):
    f=resource_fixture;data=rh.Hold(**body(f))
    with f[1].connect() as c:c.execute('REVOKE INSERT ON synthetic_resource_receipts FROM parkweave_app')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):rh.create(f[0],f[2]['fixture-a'],rh.RESOURCE_ID,uuid4().hex,data)
    assert counts(f)==(0,0)
    for sql in ('UPDATE synthetic_resources SET capacity=20','UPDATE synthetic_resource_grants SET active=true','DELETE FROM synthetic_resources','DELETE FROM synthetic_resource_receipts'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute(sql)


def test_app_cannot_extend_TTL_change_original_input_or_mutate_receipts(resource_fixture):
    f=resource_fixture;assert hold(f).status_code==201
    for sql in ("UPDATE synthetic_resource_holds SET expires_at=expires_at+interval '1 day'","UPDATE synthetic_resource_holds SET quantity=20","UPDATE synthetic_resource_holds SET purpose='changed'","DELETE FROM synthetic_resource_holds","UPDATE synthetic_resource_receipts SET payload='{}'"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute(sql)


def test_upgrade_from_9_and_repeat_migration_preserve_older_preparation_history(fixture):
    f=fixture
    for id in ('fixture-a','fixture-b','fixture-c'):f[2]['prep-specialist-'+id]=secrets.token_urlsafe(32)
    preparation.seed_synthetic(f[1],f[2]);row=filled(f);before=read_preparation(f,row).json()
    with f[1].connect() as c:
        c.execute('DROP TABLE synthetic_resource_receipts,synthetic_resource_holds,synthetic_resource_grants,synthetic_resources')
        c.execute('DELETE FROM schema_version WHERE version=10')
    f[1].migrate();f[1].migrate();assert read_preparation(f,row).json()==before
    with f[1].connect() as c:assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']==10


def test_same_request_key_cannot_cross_registered_resource(resource_fixture):
    f=resource_fixture;data=body(f);key=uuid4().hex;assert hold(f,data,key=key).status_code==201
    other=uuid4()
    with f[1].connect() as c:
        c.execute('INSERT INTO synthetic_resources SELECT %s,park_id,name,revision,capacity,buffer_seconds,open_from,open_until,enabled,timezone,namespace,authority,source FROM synthetic_resources WHERE id=%s',(other,rh.RESOURCE_ID))
        for cap in ('READ','HOLD'):c.execute("INSERT INTO synthetic_resource_grants VALUES('fixture-a',%s,'park-a','org-a',%s,true)",(other,cap))
    r=f[3].post('/api/synthetic-resources/'+str(other)+'/holds',headers=headers(f[2],key=key),json=data)
    assert r.status_code==409 and counts(f)==(1,1)


def test_resource_lock_timeout_rolls_back_and_same_key_can_retry(resource_fixture,monkeypatch):
    f=resource_fixture;data=rh.Hold(**body(f));key=uuid4().hex;original=rh._auth
    def bounded(store,c,token,write=False):
        p=original(store,c,token,write);c.execute("SET LOCAL lock_timeout='50ms'");return p
    monkeypatch.setattr(rh,'_auth',bounded)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('synthetic-resource:'+str(rh.RESOURCE_ID),))
            future=pool.submit(rh.create,f[0],f[2]['fixture-a'],rh.RESOURCE_ID,key,data)
            with pytest.raises(Conflict,match='resource busy'):future.result(timeout=2)
    assert counts(f)==(0,0)
    assert rh.create(f[0],f[2]['fixture-a'],rh.RESOURCE_ID,key,data)['hold']['state']=='HELD' and counts(f)==(1,1)


def test_identity_lock_timeout_is_a_bounded_conflict_not_a_write(resource_fixture,monkeypatch):
    f=resource_fixture;data=rh.Hold(**body(f));key=uuid4().hex;original=f[0].lock_principal
    def bounded(c,id,exclusive=False):
        c.execute("SET LOCAL lock_timeout='50ms'");return original(c,id,exclusive)
    monkeypatch.setattr(f[0],'lock_principal',bounded)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            f[1].lock_principal(c,'fixture-a',exclusive=True)
            future=pool.submit(rh.create,f[0],f[2]['fixture-a'],rh.RESOURCE_ID,key,data)
            with pytest.raises(Conflict,match='authorization busy'):future.result(timeout=2)
    assert counts(f)==(0,0) and rh.create(f[0],f[2]['fixture-a'],rh.RESOURCE_ID,key,data)['hold']['state']=='HELD'
