"""Independent persisted-state oracle for scoped synthetic personal work."""
from concurrent.futures import ThreadPoolExecutor
import json
import secrets
from uuid import UUID, uuid4
import pytest
from parkweave import preparation as prep
from parkweave.store import Store, digest
from test_preparation import preparation_fixture, create, command, add, read, counts, headers


def tasks(f, user='fixture-a'):
    r=f[3].get('/api/preparation-tasks', headers=headers(f[2], user))
    assert r.status_code==200, r.text
    x=r.json()
    assert x['qualification']=='NOT_EVALUATED' and x['external_acceptance']=='NOT_SUBMITTED' and x['offline_fulfillment']=='NO_EVIDENCE'
    return x


def test_task_lifecycle_and_read_only_persistent_history(preparation_fixture):
    f=preparation_fixture;row,_,_=create(f)
    items=tasks(f)['items'];assert len(items)==1
    assert items[0]['kind']=='SUPPLY_MATERIALS' and items[0]['missing_slots']==['need_summary','material_outline']
    assert tasks(f,'prep-specialist-fixture-a')['items']==[]
    row=add(f,row).json()
    assert tasks(f)['items'][0]['missing_slots']==['material_outline']
    row=command(f,row,'REQUEST_CHANGES','prep-specialist-fixture-a',reason='SYNTHETIC 请补目录').json()
    task=tasks(f)['items'][0];assert task['kind']=='RESPOND_TO_CORRECTION' and task['correction_reason']=='SYNTHETIC 请补目录'
    row=add(f,row,'material_outline').json()
    assert tasks(f)['items']==[]
    task=tasks(f,'prep-specialist-fixture-a')['items'][0]
    assert task['id']==row['preparation_id'] and task['case_id']==row['case_id'] and task['revision']==row['revision'] and task['kind']=='REVIEW_MATERIALS'
    row=command(f,row,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC 人工核对').json()
    assert tasks(f)['items'][0]['kind']=='CONFIRM_PREPARATION' and tasks(f,'prep-specialist-fixture-a')['items']==[]
    row=command(f,row,'CONFIRM',reason='SYNTHETIC 本地确认').json()
    assert tasks(f)['items']==tasks(f,'prep-specialist-fixture-a')['items']==[]
    row=command(f,row,'REOPEN',reason='SYNTHETIC 重新核对').json()
    expected=tasks(f,'prep-specialist-fixture-a');before=read(f,row).json();before_counts=counts(f[1])
    for _ in range(3):assert tasks(f,'prep-specialist-fixture-a')==expected
    fresh=prep.personal_tasks(Store(f[0].dsn),f[2]['prep-specialist-fixture-a'])
    assert str(fresh['items'][0]['id'])==row['preparation_id'] and fresh['items'][0]['kind']=='REVIEW_MATERIALS'
    assert counts(f[1])==before_counts and read(f,row).json()==before
    run=f[3].get('/api/runs/'+row['run_id'],headers=headers(f[2])).json()
    assert run['state']=='SUCCEEDED' and run['case']['state']=='NEEDS_INPUT'


def test_two_cases_do_not_mix_materials_correction_or_body(preparation_fixture):
    f=preparation_fixture;a,_,_=create(f,goal='SYNTHETIC A');b,_,_=create(f,goal='SYNTHETIC B')
    a=add(f,a,text='SYNTHETIC PRIVATE BODY A').json()
    a=command(f,a,'REQUEST_CHANGES','prep-specialist-fixture-a',reason='SYNTHETIC only A').json()
    items={t['id']:t for t in tasks(f)['items']}
    assert items[a['preparation_id']]['missing_slots']==['material_outline'] and items[a['preparation_id']]['correction_reason']=='SYNTHETIC only A'
    assert items[b['preparation_id']]['missing_slots']==['need_summary','material_outline'] and items[b['preparation_id']]['correction_reason'] is None
    assert 'PRIVATE BODY' not in json.dumps(items) and all('text' not in t and 'owner_id' not in t for t in items.values())


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-b','prep-specialist-fixture-c'])
def test_tasks_cross_org_and_park_isolation(preparation_fixture,user):
    f=preparation_fixture;create(f)
    assert tasks(f,user)['items']==[]


@pytest.mark.parametrize('role',['park_specialist','resource_admin','service_executor'])
def test_tasks_unassigned_or_wrong_role_cannot_expand_scope(preparation_fixture,role):
    f=preparation_fixture;create(f);token=secrets.token_urlsafe(32);f[2]['outsider']=token
    with f[1].connect() as c:
        c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',('outsider',digest(token),'park-a','org-a',role))
        c.execute("INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES('outsider','READ','park-a','org-a')")
        c.execute("INSERT INTO preparation_grants VALUES('outsider','park-a','org-a','REVIEW_ASSIGNED',true)")
    r=f[3].get('/api/preparation-tasks',headers=headers(f[2],'outsider'))
    assert r.status_code==(200 if role=='park_specialist' else 403)
    if role=='park_specialist':assert r.json()['items']==[]


@pytest.mark.parametrize('user',['fixture-a','prep-specialist-fixture-a'])
@pytest.mark.parametrize('target',['active','READ','preparation_grant'])
def test_tasks_current_identity_and_grant_revocation(preparation_fixture,user,target):
    f=preparation_fixture;create(f);assert tasks(f,user)['role']==('enterprise_operator' if user=='fixture-a' else 'park_specialist')
    with f[1].connect() as c:
        f[1].lock_principal(c,user,exclusive=True)
        if target=='active':c.execute('UPDATE principals SET active=false WHERE id=%s',(user,))
        elif target=='READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='READ'",(user,))
        else:c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(user,))
    assert f[3].get('/api/preparation-tasks',headers=headers(f[2],user)).status_code==403


def test_tasks_client_role_or_owner_query_does_not_change_authority(preparation_fixture):
    f=preparation_fixture;create(f)
    r=f[3].get('/api/preparation-tasks?role=enterprise_operator&owner_id=fixture-a',headers=headers(f[2],'prep-specialist-fixture-b'))
    assert r.status_code==200 and r.json()['items']==[] and r.json()['role']=='park_specialist'


def test_tasks_concurrent_material_change_only_observes_committed_snapshot(preparation_fixture):
    f=preparation_fixture;row,_,_=create(f);row=add(f,row).json()
    row=command(f,row,'REQUEST_CHANGES','prep-specialist-fixture-a',reason='SYNTHETIC missing outline').json()
    def update():return add(f,row,'material_outline').status_code
    def observe():return [prep.personal_tasks(f[0],f[2]['fixture-a'])['items'] for _ in range(20)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer=pool.submit(update);reader=pool.submit(observe);assert writer.result()==200;seen=reader.result()
    for items in seen:
        assert not items or (len(items)==1 and items[0]['state']=='CHANGES_REQUESTED' and items[0]['missing_slots']==['material_outline'] and items[0]['revision']==row['revision'])
    assert tasks(f)['items']==[] and tasks(f,'prep-specialist-fixture-a')['items'][0]['kind']=='REVIEW_MATERIALS'


def test_tasks_history_limit_is_visible_without_new_writes(preparation_fixture):
    f=preparation_fixture;row,_,_=create(f)
    # Explicit isolated owner fixture of the already tested terminal write bound.
    with f[1].connect() as c:c.execute('UPDATE preparations SET revision=64 WHERE id=%s',(UUID(row['preparation_id']),))
    before=counts(f[1]);task=tasks(f)['items'][0]
    assert task['blocked_reason']=='HISTORY_LIMIT_REACHED' and task['revision']==64
    assert add(f,row,revision=64).status_code==409 and counts(f[1])==before


def test_tasks_read_bound_and_older_records_are_explicit(preparation_fixture):
    f=preparation_fixture;row,_,_=create(f)
    # Isolated owner setup for bounded-read scale; no business acceptance credit.
    with f[1].connect() as c:
        for _ in range(100):
            run,case,id=uuid4(),uuid4(),uuid4()
            c.execute("INSERT INTO runs(id,principal_id,park_id,org_id,namespace,request_key,fingerprint,input,state) SELECT %s,principal_id,park_id,org_id,namespace,%s,fingerprint,input,state FROM runs WHERE id=%s",(run,uuid4().hex,UUID(row['run_id'])))
            c.execute('INSERT INTO cases SELECT %s,%s,park_id,org_id,goal,state,source,external_acceptance,offline_fulfillment FROM cases WHERE id=%s',(case,run,UUID(row['case_id'])))
            c.execute('INSERT INTO preparations(id,run_id,case_id,owner_id,reviewer_id,park_id,org_id,service_id,service_version,namespace,goal,state) SELECT %s,%s,%s,owner_id,reviewer_id,park_id,org_id,service_id,service_version,namespace,goal,state FROM preparations WHERE id=%s',(id,run,case,UUID(row['preparation_id'])))
    before=counts(f[1]);x=tasks(f)
    assert x['checked_count']==x['check_limit']==len(x['items'])==100 and x['has_older_records'] is True
    assert row['preparation_id'] not in {t['id'] for t in x['items']} and counts(f[1])==before
