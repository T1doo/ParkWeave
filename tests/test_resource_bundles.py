"""Existing resource grants, real PG transactions and API; no new resource authority."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from uuid import UUID,uuid4
import threading
import psycopg
import pytest
from parkweave import resource_bundles as rb,resource_holds as rh,resource_combinations as rc
from parkweave.store import Store,Conflict,Denied
from test_resource_combinations import pair_fixture,hold,states,totals
from test_resource_holds import body,counts,release
from test_preparation import headers
from test_case_resources import link_fixture,post as bind,get as link_read
from test_executor_receipts import receipt_fixture,ready
from test_preparation import preparation_fixture
from test_installed_fixture_receipt import native_database,installed_tcp_cluster

def bundle(f,n=3,user='fixture-a',key=None,quantity=1):
    base=body(f,ttl=300,quantity=quantity);start=datetime.fromisoformat(base['starts_at']);hs=[]
    for i in range(n):
        data={**base,'starts_at':(start+timedelta(hours=i*3)).isoformat(),'ends_at':(start+timedelta(hours=i*3+1)).isoformat(),
              'purpose':'SYNTHETIC private session '+str(i)}
        r=hold(f,rh.RESOURCE_ID if i%2==0 else rc.SECOND_RESOURCE_ID,data,user=user)
        assert r.status_code==201,r.text;hs.append(r.json()['hold'])
    return hs,{'members':[{'hold_id':h['id'],'expected_revision':h['resource_revision']} for h in hs]}

def write(f,d,user='fixture-a',key=None):return f[3].post('/api/resource-bundles',headers=headers(f[2],user,key or uuid4().hex),json=d)
def cancel(f,id,user='fixture-a',key=None):return f[3].post('/api/resource-bundles/'+str(id)+'/cancel',headers=headers(f[2],user,key or uuid4().hex),json={})
def recovery(f,key,user='fixture-a'):return f[3].get('/api/resource-bundles/recovery/'+key,headers=headers(f[2],user))

@pytest.mark.parametrize('n',[3,8])
def test_actual_group_manifest_cold_store_order_replay_and_whole_cancel(pair_fixture,n):
    f=pair_fixture;hs,d=bundle(f,n);key=uuid4().hex;x=write(f,d,key=key);assert x.status_code==201,x.text
    x=x.json();id=x['combination']['id'];assert states(f,hs)==['CONFIRMED']*n and totals(f)==[1,n,1]
    assert x['confirmation_scope']==rb.SCOPE and x['receipt']==write(f,{'members':list(reversed(d['members']))},key=key).json()['receipt']
    assert len(x['receipt']['manifest'])==n and all('purpose' not in m for m in x['receipt']['manifest'])
    assert str(rb.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(id))['combination']['id'])==id
    assert recovery(f,key).json()['status']=='COMMITTED'
    assert f[3].get('/api/resource-bundles',headers=headers(f[2])).json()['items'][0]['id']==id
    assert f[3].get('/api/resource-combinations',headers=headers(f[2])).json()['items']==[]
    assert f[3].get('/api/resource-combinations/'+id,headers=headers(f[2])).status_code==409
    assert release(f,hs[0]['id']).status_code==409
    ck=uuid4().hex;c=cancel(f,id,key=ck);assert c.status_code==200,c.text
    assert states(f,hs)==['RELEASED']*n and totals(f)==[1,n,2]
    assert cancel(f,id,key=ck).json()['receipt']==c.json()['receipt']
    assert recovery(f,ck).json()['combination']['state']=='CANCELLED'
    assert write(f,d,key=key).json()['combination']['state']=='CANCELLED'
    assert states(f,hs)==['RELEASED']*n

@pytest.mark.parametrize('bad',['expired','version','capacity','disabled','window','released','grant'])
def test_third_member_failure_never_partially_confirms(pair_fixture,bad):
    f=pair_fixture;hs,d=bundle(f,quantity=2 if bad=='capacity' else 1);third=UUID(hs[2]['id'])
    with f[1].connect() as c:
        if bad=='expired':c.execute("UPDATE synthetic_resource_holds SET created_at=clock_timestamp()-interval '10 seconds',expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(third,))
        elif bad=='released':c.execute("UPDATE synthetic_resource_holds SET state='RELEASED' WHERE id=%s",(third,))
        elif bad=='grant':c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD' AND resource_id=%s",(rh.RESOURCE_ID,))
        else:c.execute('UPDATE synthetic_resources SET '+{'version':'revision=revision+1','capacity':'capacity=1','disabled':'enabled=false','window':"open_until=clock_timestamp()+interval '2 hours'"}[bad]+' WHERE id=%s',(rh.RESOURCE_ID,))
    original=states(f,hs);before=totals(f);r=write(f,d);assert r.status_code==(403 if bad=='grant' else 409),r.text
    assert states(f,hs)==original and totals(f)==before==[0,0,0]

@pytest.mark.parametrize('change',['duplicate','few','many','extra','version'])
def test_bounded_shape_and_stale_version(pair_fixture,change):
    f=pair_fixture;hs,d=bundle(f)
    if change=='duplicate':d['members']=[d['members'][0]]*3
    if change=='few':d['members']=d['members'][:2]
    if change=='many':d['members']=d['members']*3
    if change=='extra':d['org_id']='org-b'
    if change=='version':d['members'][2]['expected_revision']=2
    r=write(f,d);assert r.status_code==(409 if change=='version' else 422)
    assert totals(f)==[0,0,0] and states(f,hs)==['HELD']*3

@pytest.mark.parametrize('user',['fixture-b','fixture-c'])
def test_cross_tenant_write_read_recovery_list_privacy(pair_fixture,user):
    f=pair_fixture;hs,d=bundle(f);key=uuid4().hex;x=write(f,d,key=key).json();id=x['combination']['id'];before=totals(f)
    assert write(f,d,user=user).status_code==cancel(f,id,user=user).status_code==403
    assert f[3].get('/api/resource-bundles/'+id,headers=headers(f[2],user)).status_code==403
    assert recovery(f,key,user).json()['status']=='NOT_OBSERVED'
    assert f[3].get('/api/resource-bundles',headers=headers(f[2],user)).json()['items']==[]
    assert totals(f)==before and states(f,hs)==['CONFIRMED']*3

@pytest.mark.parametrize('cap',['EXECUTE','HOLD','READ'])
def test_current_withdrawal_precedes_replay_but_read_recovery_is_separate(pair_fixture,cap):
    f=pair_fixture;hs,d=bundle(f);key=uuid4().hex;x=write(f,d,key=key).json();id=x['combination']['id']
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        if cap=='EXECUTE':c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        else:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND resource_id=%s AND capability=%s",(rh.RESOURCE_ID,cap))
    assert write(f,d,key=key).status_code==cancel(f,id).status_code==403
    r=recovery(f,key);assert r.status_code==(403 if cap=='READ' else 200)
    if cap!='READ':assert r.json()['status']=='COMMITTED'
    else:assert f[3].get('/api/resource-bundles',headers=headers(f[2])).json()['items']==[]
    assert states(f,hs)==['CONFIRMED']*3 and totals(f)==[1,3,1]

def test_same_and_distinct_key_concurrency_and_shared_original_key(pair_fixture):
    f=pair_fixture;hs,d=bundle(f);key=uuid4().hex
    def do(d):return rb.confirm(f[0],f[2]['fixture-a'],key,rb.Bundle(**d))
    with ThreadPoolExecutor(max_workers=2) as pool:xs=list(pool.map(do,[d,{'members':list(reversed(d['members']))}]))
    assert xs[0]['receipt']==xs[1]['receipt'] and totals(f)==[1,3,1]
    assert write(f,d).status_code==409
    assert cancel(f,xs[0]['combination']['id'],key=key).status_code==409
    changed={'members':[dict(m,expected_revision=2) for m in d['members']]};assert write(f,changed,key=key).status_code==409
    assert recovery(f,'unseen-key').json()['status']=='NOT_OBSERVED'

@pytest.mark.parametrize('operation',['CONFIRM','CANCEL'])
def test_after_first_update_fault_rolls_back_all_three(pair_fixture,operation):
    f=pair_fixture;hs,d=bundle(f);id=None
    if operation=='CANCEL':id=write(f,d).json()['combination']['id']
    with f[1].connect() as c:
        c.execute("""CREATE FUNCTION fail_bundle_receipt() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'SYNTHETIC receipt fault'; END$$""")
        c.execute('CREATE TRIGGER fail_bundle_receipt BEFORE INSERT ON synthetic_resource_combination_receipts FOR EACH ROW EXECUTE FUNCTION fail_bundle_receipt()')
    before=totals(f);prior=states(f,hs)
    with pytest.raises(psycopg.Error):
        if operation=='CONFIRM':rb.confirm(f[0],f[2]['fixture-a'],uuid4().hex,rb.Bundle(**d))
        else:rb.cancel(f[0],f[2]['fixture-a'],UUID(id),uuid4().hex)
    assert states(f,hs)==prior and totals(f)==before

@pytest.mark.parametrize('corrupt',['manifest','member','missing_proof'])
def test_manifest_and_members_cannot_be_guessed_or_mutated(pair_fixture,corrupt):
    f=pair_fixture;hs,d=bundle(f);x=write(f,d).json();id=x['combination']['id']
    for table in ['synthetic_resource_combination_receipts','synthetic_resource_combination_members']:
        for verb in ['UPDATE','DELETE']:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with f[0].connect() as c:c.execute((f"UPDATE {table} SET combination_id=combination_id" if verb=='UPDATE' else f'DELETE FROM {table}'))
    with f[1].connect() as c:
        if corrupt=='manifest':c.execute("UPDATE synthetic_resource_combination_receipts SET payload=jsonb_set(payload,'{manifest_sha256}','\"bad\"') WHERE combination_id=%s",(UUID(id),))
        elif corrupt=='member':c.execute('UPDATE synthetic_resource_holds SET quantity=2 WHERE id=%s',(UUID(hs[2]['id']),))
        else:c.execute("DELETE FROM synthetic_resource_combination_receipts WHERE combination_id=%s AND action='CONFIRM'",(UUID(id),))
    assert f[3].get('/api/resource-bundles/'+id,headers=headers(f[2])).status_code==409
    assert cancel(f,id).status_code==409 and states(f,hs)==['CONFIRMED']*3

def test_case_explicit_association_all_members_and_cancel_is_stale_not_completed(link_fixture):
    f=link_fixture;p=ready(f);hs,d=bundle(f);g=write(f,d).json()['combination']
    candidates=f[3].get('/api/preparations/'+p['preparation_id']+'/resource-link-candidates',headers=headers(f[2])).json()
    assert candidates['items'][0]['combination']['id']==g['id']
    r=bind(f,p,g);assert r.status_code==201,r.text
    assert len(r.json()['current']['combination']['members'])==3 and not r.json()['case_goal_completed']
    cancel(f,g['id']);x=link_read(f,p).json();assert x['current']['status']=='NEEDS_RECHECK' and not x['case_goal_completed']

def test_wait_then_expiry_no_partial_and_lock_order_deduplicates_resources(pair_fixture,monkeypatch):
    f=pair_fixture;hs,d=bundle(f);signal=threading.Event();seen=[];original=rh._lock
    def observed(c,id,shared=False):
        seen.append(str(id))
        if id==rc.SECOND_RESOURCE_ID:signal.set()
        return original(c,id,shared)
    monkeypatch.setattr(rh,'_lock',observed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            original(c,rc.SECOND_RESOURCE_ID)
            c.execute("UPDATE synthetic_resource_holds SET expires_at=clock_timestamp()+interval '0.15 seconds' WHERE id=%s",(UUID(hs[2]['id']),))
            future=pool.submit(rb.confirm,f[0],f[2]['fixture-a'],uuid4().hex,rb.Bundle(**d));assert signal.wait(2);c.execute('SELECT pg_sleep(0.2)')
        with pytest.raises(Conflict,match='valid unconfirmed'):future.result(timeout=5)
    assert seen==sorted(set(seen)) and totals(f)==[0,0,0] and states(f,hs)==['HELD']*3

def test_simultaneous_distinct_keys_or_single_release_never_partial(pair_fixture):
    f=pair_fixture;hs,d=bundle(f)
    def confirm():
        try:return rb.confirm(f[0],f[2]['fixture-a'],uuid4().hex,rb.Bundle(**d))
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:xs=list(pool.map(lambda _:confirm(),range(2)))
    assert xs.count('CONFLICT')==1 and totals(f)==[1,3,1] and states(f,hs)==['CONFIRMED']*3

def test_bundle_competes_with_original_single_release_without_partial(pair_fixture):
    f=pair_fixture;hs,d=bundle(f)
    def run(action):
        try:
            if action=='bundle':return rb.confirm(f[0],f[2]['fixture-a'],uuid4().hex,rb.Bundle(**d))
            return rh.release(f[0],f[2]['fixture-a'],UUID(hs[2]['id']),uuid4().hex)
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:xs=list(pool.map(run,['bundle','release']))
    assert xs.count('CONFLICT')==1
    assert (states(f,hs),totals(f)) in ((['CONFIRMED']*3,[1,3,1]),(['HELD','HELD','RELEASED'],[0,0,0]))

def test_simultaneous_cancel_keys_do_not_split_or_reoccupy(pair_fixture):
    f=pair_fixture;hs,d=bundle(f);id=write(f,d).json()['combination']['id']
    with ThreadPoolExecutor(max_workers=2) as pool:xs=list(pool.map(lambda _:rb.cancel(f[0],f[2]['fixture-a'],UUID(id),uuid4().hex),range(2)))
    assert all(x['combination']['state']=='CANCELLED' for x in xs) and states(f,hs)==['RELEASED']*3 and totals(f)==[1,3,3]

@pytest.mark.parametrize('role',['park_specialist','resource_admin','service_executor'])
def test_existing_role_alone_never_grants_bundle_write_or_read(pair_fixture,role):
    f=pair_fixture;hs,d=bundle(f);key=uuid4().hex;g=write(f,d,key=key).json()['combination']
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE principals SET role=%s WHERE id='fixture-a'",(role,))
    assert write(f,d,key=key).status_code==cancel(f,g['id']).status_code==recovery(f,key).status_code==403
    assert totals(f)==[1,3,1]

def test_schema25_existing_tables_support_bundle_without_schema_or_grant_extension(native_database):
    import secrets
    from psycopg.conninfo import make_conninfo
    from fastapi.testclient import TestClient
    from parkweave.api import create_app
    from pathlib import Path
    receipt,maintenance,target=native_database;owner=Store(target);owner._case_fact_fixture_receipt=receipt;owner.migrate()
    with psycopg.connect(maintenance,autocommit=True) as c:c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
    tokens={name:secrets.token_urlsafe(32) for name in ('fixture-a','fixture-b','fixture-c')};owner.seed(tokens);rc.seed_synthetic(owner)
    with owner.connect() as c:c.execute(Path('src/parkweave/roles.sql').read_text())
    store=Store(make_conninfo(target,user='parkweave_app'))
    with TestClient(create_app(store)) as api:
        f=(store,owner,tokens,api);hs,d=bundle(f);g=write(f,d).json()['combination'];assert states(f,hs)==['CONFIRMED']*3
        assert cancel(f,g['id']).status_code==200 and states(f,hs)==['RELEASED']*3
    with owner.connect() as c:assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']==25
