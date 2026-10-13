from uuid import uuid4,UUID
from concurrent.futures import ThreadPoolExecutor
from test_partial_service_plan import setup_partial,UNKNOWN
from test_case_resources import link_fixture,group
from test_executor_receipts import receipt_fixture,act as receipt_act
from test_preparation import preparation_fixture,headers
from test_service_case_steps import read,adopt,adopt_body,command,business
from parkweave import service_case_steps as scs
from parkweave.store import Store

def resource_change(f):
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET revision=revision+1')

def recover(f,p,key):
    return scs.recover(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']),key)

def test_independent_dependency_replacement_preserves_old_event_and_both_keys(link_fixture):
    f=link_fixture;p=setup_partial(f,'LOCAL_CASE_RESOURCE_ASSOCIATION');key=uuid4().hex
    r=adopt(f,p,adopt_body(f,p,partial_adoption=True),key);assert r.status_code==201,r.text
    old=r.json();assert command(f,p,'P1').status_code==200
    resource_change(f);row=read(f,p).json();assert row['can_adopt_partial'] and not row['local_revision_required']
    body=adopt_body(f,p,partial_adoption=True);body['expected_plan_revision']=row['revision'];newkey=uuid4().hex
    newer=adopt(f,p,body,newkey);assert newer.status_code==201,newer.text
    assert newer.json()['plan_id']!=old['plan_id'] and newer.json()['history'][0]['events'][0]==old['event']
    before=business(f)
    for k,e in ((key,old['event']),(newkey,newer.json()['event'])):
        proof=recover(f,p,k);assert proof['status']=='COMMITTED' and proof['event']['id']==e['id']
    assert business(f)==before

def test_independent_dependency_replacement_requires_unlock_and_rejects_local_patch(link_fixture):
    f=link_fixture;p=setup_partial(f,'LOCAL_CASE_RESOURCE_ASSOCIATION')
    assert adopt(f,p,adopt_body(f,p,partial_adoption=True)).status_code==201
    assert command(f,p,'P1').status_code==200
    row=read(f,p).json();s=row['steps'][0]
    lock=command(f,p,'P1',action='LOCK',row=row,expected_source_sha256=s['source_sha256']);assert lock.status_code==200,lock.text
    resource_change(f);row=read(f,p).json();body=adopt_body(f,p,partial_adoption=True);body['expected_plan_revision']=row['revision']
    assert adopt(f,p,body).status_code==409
    assert adopt(f,p,{**body,'local_revision':True}).status_code==409
    unlock=command(f,p,'P1',action='UNLOCK',row=row);assert unlock.status_code==200,unlock.text
    body['expected_plan_revision']=unlock.json()['revision']
    r=adopt(f,p,body);assert r.status_code==201,r.text
    assert r.json()['history'][0]['steps'][0]['id']==s['id']

def test_independent_same_key_different_reason_concurrent_only_one_commit(link_fixture):
    f=link_fixture;p=setup_partial(f);key=uuid4().hex;body=adopt_body(f,p,partial_adoption=True)
    bodies=[body,{**body,'reason':'SYNTHETIC independent differing request'}]
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda b:adopt(f,p,b,key),bodies))
    assert sorted(r.status_code for r in results)==[201,409]
    row=read(f,p).json();assert len(row['events'])==1
    assert recover(f,p,key)['event']['id']==row['events'][0]['id']

def test_independent_constraint_blocked_receipt_create_and_lifecycle_cannot_bypass(link_fixture):
    f=link_fixture;p=setup_partial(f,'LOCAL_CASE_RECORD_RECHECK',{'excluded_roles':['service_executor']})
    assert adopt(f,p,adopt_body(f,p,partial_adoption=True)).status_code==201
    assert command(f,p,'P1').status_code==200
    before=business(f)
    payload=dict(preparation_id=p['preparation_id'],executor_id='executor-a',expected_preparation_revision=p['revision'])
    r=f[3].post('/api/executor-receipts',headers=headers(f[2],key=uuid4().hex),json=payload)
    assert r.status_code==409,r.text
    from test_case_lifecycle import act,read as lifecycle_read
    row=lifecycle_read(f,p).json()
    r=act(f,p,row,'REVALIDATE');assert r.status_code==409,r.text
    assert business(f)==before
