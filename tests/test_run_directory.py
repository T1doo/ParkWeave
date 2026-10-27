"""Current owner discovery only; real existing Store/API permissions and PG."""
from uuid import UUID, uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from parkweave.domain import Intake
from parkweave.store import Store, Denied
from test_authorization_files import add_role


def directory(f, user='fixture-a', **params):
    return f[3].get('/api/runs', headers={'Authorization': 'Bearer '+f[2][user]}, params=params)


def create(f, user='fixture-a', action='case.create'):
    args={'goal':'SYNTHETIC directory private goal', 'action':action}
    if action=='facts.assess':args['fact_fields']=['region']
    return f[0].submit(f[2][user],uuid4().hex,Intake(**args))


def snapshot(f):
    from normal_recovery_process import snapshot as capture
    return capture(f[1])


def test_pagination_current_owner_exact_projection_and_no_writes(fixture):
    f=fixture;ids=sorted(str(create(f)) for _ in range(5));create(f,'fixture-b');create(f,'fixture-c')
    create(f,action='facts.assess')
    before=snapshot(f);seen=[];after=None
    for n in range(3):
        params={'limit':2}
        if after:params['after']=after
        r=directory(f,**params);assert r.status_code==200,r.text;x=r.json()
        assert set(x)=={'scope','read_only','automatically_replayed','items','next_after'}
        assert x['scope']=='CURRENT_OWNER_LOCAL_CASE_RECORDS' and x['read_only'] and not x['automatically_replayed']
        assert all(set(row)=={'run_id','state','revision','namespace'} for row in x['items'])
        assert all(row['state']=='QUEUED' and row['revision']==1 and row['namespace']=='SYNTHETIC' for row in x['items'])
        seen.extend(row['run_id'] for row in x['items']);after=x['next_after']
        assert after==(x['items'][-1]['run_id'] if n<2 else None)
    assert seen==ids and snapshot(f)==before
    assert directory(f,limit=50).json()['items']==f[0].list_local_records(f[2]['fixture-a'],limit=50)['items']
    for other in ('fixture-b','fixture-c'):
        rows=directory(f,other).json()['items'];assert len(rows)==1 and rows[0]['run_id'] not in ids
    assert directory(f,after=str(UUID(int=2**128-1))).json()['items']==[]
    assert snapshot(f)==before


def test_read_only_transaction_and_no_action_or_role_scope_expansion(fixture):
    f=fixture;run=create(f);other=create(f,'fixture-b')
    from psycopg.conninfo import make_conninfo
    fault=Store(make_conninfo(f[0].dsn),mode='FAULT_INJECTION')
    fault.submit(f[2]['fixture-a'],uuid4().hex,Intake(goal='SYNTHETIC hidden fault',action='fault.record'))
    before=snapshot(f);r=directory(f,role='enterprise_operator',principal='fixture-b',action='fault.record')
    assert [x['run_id'] for x in r.json()['items']]==[str(run)] and snapshot(f)==before
    cursor=directory(f,after=str(other)).json()
    assert all(UUID(x['run_id']).int>UUID(str(other)).int for x in cursor['items'])
    # Always exercise a nonempty cursor result; the foreign random UUID above
    # can legitimately sort after this owner's only record.
    nonempty=directory(f,after=str(UUID(int=0))).json()
    assert [x['run_id'] for x in nonempty['items']]==[str(run)]
    assert all(UUID(x['run_id']).int>0 for x in nonempty['items'])
    original=f[0].auth
    def checked(c,*args,**kwargs):
        assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']=='on'
        return original(c,*args,**kwargs)
    f[0].auth=checked
    try:assert directory(f).status_code==200
    finally:f[0].auth=original
    assert snapshot(f)==before


@pytest.mark.parametrize('role',['park_specialist','resource_admin','service_executor'])
def test_non_owner_directory_refused_even_with_original_status_assignment(fixture,role):
    f=fixture;run=create(f);user=add_role(f[1],f[2],role);f[1].assign_status(user,run)
    assert f[3].get('/api/runs/'+str(run),headers={'Authorization':'Bearer '+f[2][user]}).status_code==200
    before=snapshot(f);r=directory(f,user);assert r.status_code==403 and 'items' not in r.json()
    assert snapshot(f)==before


@pytest.mark.parametrize('changed',['identity','read','role','org','park'])
def test_current_auth_change_never_uses_previous_directory(fixture,changed):
    f=fixture;create(f);assert directory(f).json()['items']
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        if changed=='identity':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif changed=='read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        elif changed=='role':c.execute("UPDATE principals SET role='service_executor' WHERE id='fixture-a'")
        else:c.execute('UPDATE principals SET '+('org_id' if changed=='org' else 'park_id')+"='changed' WHERE id='fixture-a'")
    before=snapshot(f);r=directory(f);assert r.status_code==403 and 'run_id' not in r.text
    assert snapshot(f)==before


@pytest.mark.parametrize('params',[{'limit':0},{'limit':51},{'limit':-1},{'limit':'true'},{'after':'not-a-uuid'}])
def test_bounded_query_rejected_without_business_writes(fixture,params):
    before=snapshot(fixture);assert directory(fixture,**params).status_code==422;assert snapshot(fixture)==before


def test_cold_store_concurrent_get_and_missing_or_wrong_session(fixture):
    f=fixture;run=create(f);before=snapshot(f)
    with ThreadPoolExecutor(max_workers=4) as pool:
        pages=list(pool.map(lambda _:Store(f[0].dsn).list_local_records(f[2]['fixture-a']),range(8)))
    assert all([row['run_id'] for row in p['items']]==[str(run)] for p in pages)
    assert f[3].get('/api/runs').status_code==401
    assert f[3].get('/api/runs',headers={'Authorization':'Bearer SYNTHETIC-UNKNOWN'}).status_code==403
    assert snapshot(f)==before
    for limit in [True,False,0,51,'20']:
        with pytest.raises(ValueError):f[0].list_local_records(f[2]['fixture-a'],limit=limit)
    with pytest.raises(ValueError):f[0].list_local_records(f[2]['fixture-a'],after=str(run))
