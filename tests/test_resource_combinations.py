"""Actual isolated PG/API all-or-none synthetic two-resource contracts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID,uuid4
import threading
import psycopg
import pytest
from parkweave import resource_combinations as rc,resource_holds as rh
from parkweave.store import Conflict,Denied,Store
from test_resource_holds import body,preview,read,release,counts
from test_resource_confirm import confirm as single_confirm
from test_preparation import headers

@pytest.fixture
def pair_fixture(fixture):
    rc.seed_synthetic(fixture[1]);return fixture


def hold(f,id,data,user='fixture-a',key=None):
    return f[3].post('/api/synthetic-resources/'+str(id)+'/holds',headers=headers(f[2],user,key or uuid4().hex),json=data)


def pair(f,user='fixture-a',quantity=1):
    data=body(f,quantity=quantity)
    hs=[hold(f,id,data,user).json()['hold'] for id in (rh.RESOURCE_ID,rc.SECOND_RESOURCE_ID)]
    return hs,{'members':[{'hold_id':h['id'],'expected_revision':h['resource_revision']} for h in hs]}


def write(f,data,user='fixture-a',key=None):
    return f[3].post('/api/resource-combinations',headers=headers(f[2],user,key or uuid4().hex),json=data)


def cancel(f,id,user='fixture-a',key=None):
    return f[3].post('/api/resource-combinations/'+str(id)+'/cancel',headers=headers(f[2],user,key or uuid4().hex),json={})


def totals(f):
    with f[1].connect() as c:
        return [c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('synthetic_resource_combinations','synthetic_resource_combination_members','synthetic_resource_combination_receipts')]


def states(f,hs):
    with f[1].connect() as c:return [c.execute('SELECT state FROM synthetic_resource_holds WHERE id=%s',(UUID(h['id']),)).fetchone()['state'] for h in hs]


def test_atomic_pair_persistence_order_equivalent_replay_and_whole_cancel(pair_fixture):
    f=pair_fixture;hs,data=pair(f,quantity=2);key=uuid4().hex;x=write(f,data,key=key);assert x.status_code==201,x.text
    x=x.json();g=x['combination'];id=g['id'];assert [h['state'] for h in g['members']]==['CONFIRMED']*2
    assert x['reservation']=='NOT_CONFIRMED' and x['external_acceptance']=='NOT_SUBMITTED' and totals(f)==[1,2,1]
    assert all(h['combination_id']==id for h in g['members'])
    assert write(f,{'members':list(reversed(data['members']))},key=key).json()['receipt']==x['receipt']
    assert rc.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(id))['combination']['state']=='CONFIRMED'
    assert single_confirm(f,hs[0]['id']).status_code==release(f,hs[1]['id']).status_code==409
    assert preview(f,body(f)).json()['occupied_peak']==2
    cancel_key=uuid4().hex;y=cancel(f,id,key=cancel_key).json();assert y['combination']['state']=='CANCELLED'
    assert states(f,hs)==['RELEASED']*2 and totals(f)==[1,2,2]
    assert cancel(f,id,key=cancel_key).json()['receipt']==y['receipt']
    replay=write(f,data,key=key).json();assert replay['receipt']==x['receipt'] and replay['combination']['state']=='CANCELLED'
    assert write(f,data).status_code==409 and preview(f,body(f)).json()['occupied_peak']==0


@pytest.mark.parametrize('bad',['expired','version','disabled','capacity','window','released','single_confirmed','grant'])
def test_second_resource_invalid_has_no_partial_confirmation(pair_fixture,bad):
    f=pair_fixture;hs,data=pair(f,quantity=2);id=UUID(hs[1]['id'])
    if bad=='released':release(f,str(id))
    elif bad=='single_confirmed':single_confirm(f,str(id))
    else:
        with f[1].connect() as c:
            if bad=='expired':c.execute("UPDATE synthetic_resource_holds SET created_at=clock_timestamp()-interval '10 seconds',expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(id,))
            elif bad=='grant':c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND resource_id=%s AND capability='HOLD'",(rc.SECOND_RESOURCE_ID,))
            else:
                sql={'version':'revision=revision+1','disabled':'enabled=false','capacity':'capacity=1','window':"open_until=clock_timestamp()+interval '30 minutes'"}[bad]
                c.execute('UPDATE synthetic_resources SET '+sql+' WHERE id=%s',(rc.SECOND_RESOURCE_ID,))
    before=counts(f);original=states(f,hs);x=write(f,data);assert x.status_code==(403 if bad=='grant' else 409),x.text
    assert states(f,hs)==original and counts(f)==before and totals(f)==[0,0,0]


@pytest.mark.parametrize('failure',['second_update','receipt'])
def test_failure_after_first_mutation_rolls_back_all(pair_fixture,failure):
    f=pair_fixture;hs,data=pair(f)
    with f[1].connect() as c:
        if failure=='receipt':c.execute('REVOKE INSERT ON synthetic_resource_combination_receipts FROM parkweave_app')
        else:
            c.execute("""CREATE FUNCTION fail_second() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN
              IF NEW.resource_id='fb161ea0-b665-4ec5-b345-a070bfec764d'::uuid AND NEW.state='CONFIRMED' THEN RAISE EXCEPTION 'isolated second update failure'; END IF; RETURN NEW; END$$""")
            c.execute('CREATE TRIGGER fail_second BEFORE UPDATE ON synthetic_resource_holds FOR EACH ROW EXECUTE FUNCTION fail_second()')
    with pytest.raises(psycopg.Error):rc.confirm(f[0],f[2]['fixture-a'],uuid4().hex,rc.Combination(**data))
    assert states(f,hs)==['HELD']*2 and totals(f)==[0,0,0] and counts(f)==(2,2)


def test_concurrent_same_key_reverse_order_and_distinct_key_commit_once(pair_fixture):
    f=pair_fixture;hs,data=pair(f);key=uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool:
        xs=list(pool.map(lambda d:rc.confirm(f[0],f[2]['fixture-a'],key,rc.Combination(**d)),[data,{'members':list(reversed(data['members']))}]))
    assert xs[0]['receipt']==xs[1]['receipt'] and totals(f)==[1,2,1]
    cancel(f,str(xs[0]['combination']['id']));hs,data=pair(f)
    def run(_):
        try:return rc.confirm(f[0],f[2]['fixture-a'],uuid4().hex,rc.Combination(**data))
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:xs=list(pool.map(run,range(2)))
    assert xs.count('CONFLICT')==1 and totals(f)==[2,4,3]


def test_competing_single_release_never_partial_pair(pair_fixture):
    f=pair_fixture;hs,data=pair(f)
    def run(action):
        try:return rc.confirm(f[0],f[2]['fixture-a'],uuid4().hex,rc.Combination(**data)) if action=='pair' else rh.release(f[0],f[2]['fixture-a'],UUID(hs[1]['id']),uuid4().hex)
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:xs=list(pool.map(run,['pair','release']))
    assert xs.count('CONFLICT')==1
    current=states(f,hs);assert current in (['CONFIRMED']*2,['HELD','RELEASED'])
    assert totals(f) in ([1,2,1],[0,0,0])


def test_two_enterprises_reverse_resource_order_capacity_and_cancel_race(pair_fixture):
    f=pair_fixture;ha,a=pair(f,'fixture-a');hb,b=pair(f,'fixture-b');b['members'].reverse()
    with ThreadPoolExecutor(max_workers=2) as pool:
        xs=list(pool.map(lambda p:rc.confirm(f[0],f[2][p[0]],uuid4().hex,rc.Combination(**p[1])),[('fixture-a',a),('fixture-b',b)]))
    assert totals(f)==[2,4,2] and states(f,ha+hb)==['CONFIRMED']*4
    assert preview(f,body(f)).json()['occupied_peak']==2
    id=xs[0]['combination']['id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        ys=list(pool.map(lambda _:rc.cancel(f[0],f[2]['fixture-a'],id,'same-cancel'),range(2)))
    assert ys[0]['receipt']==ys[1]['receipt'] and states(f,ha)==['RELEASED']*2 and states(f,hb)==['CONFIRMED']*2


@pytest.mark.parametrize('target',['active','role','org','READ','EXECUTE','resource_READ','resource_HOLD'])
def test_replay_and_cancel_require_current_whole_pair_authorization(pair_fixture,target):
    f=pair_fixture;hs,data=pair(f);key=uuid4().hex;g=write(f,data,key=key).json()['combination']
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        if target=='active':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif target=='role':c.execute("UPDATE principals SET role='resource_admin' WHERE id='fixture-a'")
        elif target=='org':c.execute("UPDATE principals SET org_id='org-x' WHERE id='fixture-a'")
        elif target.startswith('resource_'):c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND resource_id=%s AND capability=%s",(rc.SECOND_RESOURCE_ID,target.removeprefix('resource_')))
        else:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability=%s",(target,))
    assert write(f,data,key=key).status_code==cancel(f,g['id']).status_code==403
    assert states(f,hs)==['CONFIRMED']*2 and totals(f)==[1,2,1]


def test_cross_tenant_fake_identity_and_shared_key_fingerprints(pair_fixture):
    f=pair_fixture;hs,data=pair(f);assert write(f,data,user='fixture-b').status_code==write(f,data,user='fixture-c').status_code==403
    x=write(f,data,key='pair-key').json();id=x['combination']['id']
    for user in ('fixture-b','fixture-c'):
        assert cancel(f,id,user=user).status_code==f[3].get('/api/resource-combinations/'+id,headers=headers(f[2],user)).status_code==403
        assert f[3].get('/api/resource-combinations',headers=headers(f[2],user)).json()['items']==[]
    assert cancel(f,id,key='pair-key').status_code==409 and release(f,hs[0]['id'],key='pair-key').status_code==409
    changed={'members':[dict(data['members'][0],expected_revision=2),data['members'][1]]};assert write(f,changed,key='pair-key').status_code==409
    assert write(f,data,key='hold-key').status_code==409  # original holds already confirmed


@pytest.mark.parametrize('data',[{'members':[]},{'members':[{'hold_id':str(uuid4()),'expected_revision':1}]},{'members':[],'role':'enterprise_operator'}])
def test_invalid_pair_shape_has_no_effect(pair_fixture,data):
    assert write(pair_fixture,data).status_code==422 and totals(pair_fixture)==[0,0,0]


def test_duplicate_holds_same_resource_and_single_key_reuse_refused(pair_fixture):
    f=pair_fixture;hs,data=pair(f);duplicate={'members':[data['members'][0]]*2};assert write(f,duplicate).status_code==422
    extra=hold(f,rh.RESOURCE_ID,body(f)).json()['hold'];same={'members':[data['members'][0],{'hold_id':extra['id'],'expected_revision':1}]}
    assert write(f,same).status_code==409
    key='original-hold';other=hold(f,rc.SECOND_RESOURCE_ID,body(f),key=key).json()['hold'];request={'members':[data['members'][0],{'hold_id':other['id'],'expected_revision':1}]}
    assert write(f,request,key=key).status_code==409 and totals(f)==[0,0,0]


def test_second_lock_wait_expiry_and_stable_order(pair_fixture,monkeypatch):
    f=pair_fixture;hs,data=pair(f);entered=threading.Event();original=rh._lock;observed=[]
    def signal(c,id,shared=False):
        observed.append(str(id))
        if id==rc.SECOND_RESOURCE_ID:entered.set()
        return original(c,id,shared)
    monkeypatch.setattr(rh,'_lock',signal)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            original(c,rc.SECOND_RESOURCE_ID)
            c.execute("UPDATE synthetic_resource_holds SET expires_at=clock_timestamp()+interval '0.15 seconds' WHERE id=%s",(UUID(hs[1]['id']),))
            future=pool.submit(rc.confirm,f[0],f[2]['fixture-a'],uuid4().hex,rc.Combination(**{'members':list(reversed(data['members']))}))
            assert entered.wait(2);c.execute('SELECT pg_sleep(0.2)')
        with pytest.raises(Conflict,match='valid unconfirmed'):future.result(timeout=5)
    assert observed==sorted(observed) and states(f,hs)==['HELD']*2 and totals(f)==[0,0,0]


@pytest.mark.parametrize('failure',['second_release','group_state','receipt'])
def test_cancel_fault_rolls_back_every_member_and_group(pair_fixture,failure):
    f=pair_fixture;hs,data=pair(f);g=write(f,data).json()['combination'];before=totals(f)
    with f[1].connect() as c:
        if failure=='receipt':c.execute('REVOKE INSERT ON synthetic_resource_combination_receipts FROM parkweave_app')
        else:
            condition="NEW.resource_id='fb161ea0-b665-4ec5-b345-a070bfec764d'::uuid AND NEW.state='RELEASED'" if failure=='second_release' else "NEW.state='CANCELLED'"
            table='synthetic_resource_holds' if failure=='second_release' else 'synthetic_resource_combinations'
            c.execute('CREATE FUNCTION fail_cancel() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN IF '+condition+" THEN RAISE EXCEPTION 'isolated cancellation failure'; END IF; RETURN NEW; END$$")
            c.execute('CREATE TRIGGER fail_cancel BEFORE UPDATE ON '+table+' FOR EACH ROW EXECUTE FUNCTION fail_cancel()')
    with pytest.raises(psycopg.Error):rc.cancel(f[0],f[2]['fixture-a'],UUID(g['id']),uuid4().hex)
    assert states(f,hs)==['CONFIRMED']*2 and totals(f)==before
    assert rc.read(f[0],f[2]['fixture-a'],UUID(g['id']))['combination']['state']=='CONFIRMED'


def test_combination_and_single_confirmation_compete_without_partial_combo(pair_fixture):
    f=pair_fixture;hs,data=pair(f)
    def run(action):
        try:return rc.confirm(f[0],f[2]['fixture-a'],uuid4().hex,rc.Combination(**data)) if action=='pair' else rh.confirm(f[0],f[2]['fixture-a'],UUID(hs[0]['id']),uuid4().hex,rh.Confirm(expected_revision=1))
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:xs=list(pool.map(run,['pair','single']))
    assert xs.count('CONFLICT')==1
    assert (states(f,hs),totals(f)) in ((['CONFIRMED']*2,[1,2,1]),(['CONFIRMED','HELD'],[0,0,0]))


def test_combination_history_permissions_are_minimal(pair_fixture):
    f=pair_fixture;hs,data=pair(f);write(f,data)
    for sql in ("UPDATE synthetic_resource_combinations SET created_at=clock_timestamp()","DELETE FROM synthetic_resource_combinations","UPDATE synthetic_resource_combination_members SET combination_id=gen_random_uuid()","DELETE FROM synthetic_resource_combination_members","UPDATE synthetic_resource_combination_receipts SET payload='{}'","DELETE FROM synthetic_resource_combination_receipts"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute(sql)
    assert totals(f)==[1,2,1] and states(f,hs)==['CONFIRMED']*2
    with f[1].connect() as c:c.execute('DELETE FROM schema_version WHERE version>=12')
    f[1].migrate();f[1].migrate()
    assert totals(f)==[1,2,1] and states(f,hs)==['CONFIRMED']*2


def test_exact_11_upgrade_repeat_preserves_existing_single_receipts(pair_fixture):
    f=pair_fixture;hs,data=pair(f);single=single_confirm(f,hs[0]['id']).json();before=counts(f)
    with f[1].connect() as c:
        c.execute('DROP TABLE case_resource_links,resource_case_claims; DROP TABLE synthetic_resource_combination_receipts,synthetic_resource_combination_members,synthetic_resource_combinations')
        c.execute('DELETE FROM schema_version WHERE version>=12')
    f[1].migrate();f[1].migrate()
    with f[1].connect() as c:
        assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']==27
        c.execute('GRANT SELECT,INSERT ON synthetic_resource_combinations,synthetic_resource_combination_members,synthetic_resource_combination_receipts TO parkweave_app')
        c.execute('GRANT UPDATE(state) ON synthetic_resource_combinations TO parkweave_app')
        payload=c.execute("SELECT payload FROM synthetic_resource_receipts WHERE action='CONFIRM'").fetchone()['payload']
    assert payload==single['receipt'] and counts(f)==before and states(f,hs)==['CONFIRMED','HELD'] and totals(f)==[0,0,0]
