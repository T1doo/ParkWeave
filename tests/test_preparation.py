"""F2 parallel engineering only: synthetic PG and actual API/worker commands."""
import hashlib
import json
from uuid import UUID,uuid4
from concurrent.futures import ThreadPoolExecutor
import secrets
import psycopg
import pytest
from parkweave import preparation as prep
from parkweave.store import Store,digest

@pytest.fixture
def preparation_fixture(fixture):
    store,owner,tokens,client=fixture
    tokens=dict(tokens)
    for id in ('fixture-a','fixture-b','fixture-c'):tokens['prep-specialist-'+id]=secrets.token_urlsafe(32)
    prep.seed_synthetic(owner,tokens)
    return store,owner,tokens,client

def headers(tokens,user='fixture-a',key=None):
    result={'Authorization':'Bearer '+tokens[user]}
    if key:result['Idempotency-Key']=key
    return result

def create(fixture,user='fixture-a',goal='SYNTHETIC资料准备'):
    store,owner,tokens,api=fixture
    run=api.post('/api/runs',headers=headers(tokens,user,uuid4().hex),json={'goal':goal}).json()['run_id']
    store.finish(store.claim('synthetic-preparation'))
    data={'run_id':run,'service_id':prep.SERVICE,'service_version':1,'reviewer_id':'prep-specialist-'+user}
    key=uuid4().hex;r=api.post('/api/preparations',headers=headers(tokens,user,key),json=data)
    assert r.status_code==201,r.text
    return r.json(),data,key

def command(fixture,row,action,user='fixture-a',key=None,revision=None,**extra):
    store,owner,tokens,api=fixture
    body={'action':action,'expected_revision':row['revision'] if revision is None else revision,**extra}
    return api.post('/api/preparations/'+row['preparation_id']+'/commands',headers=headers(tokens,user,key or uuid4().hex),json=body)

def add(f,row,slot='need_summary',text='SYNTHETIC source text',**kwargs):
    return command(f,row,'ADD_EVIDENCE',slot=slot,text=text,source_kind='DOCUMENT_EXCERPT',source_label='SYNTHETIC sample document v1',**kwargs)

def filled(f):
    row,_,_=create(f)
    row=add(f,row).json();row=add(f,row,'material_outline','SYNTHETIC material list').json()
    return row

def read(f,row,user='fixture-a'):
    return f[3].get('/api/preparations/'+row['preparation_id'],headers=headers(f[2],user))

def counts(owner):
    with owner.connect() as c:return {t:c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('preparations','preparation_evidence','preparation_events')}

def test_api_full_manual_preparation_confirm_and_reopen(preparation_fixture):
    f=preparation_fixture;store,owner,tokens,api=f
    catalogue=api.get('/api/preparation-catalog',headers=headers(tokens)).json()
    assert catalogue['services'][0]['source']['kind']=='SYNTHETIC' and catalogue['services'][0]['qualification']=='NOT_EVALUATED'
    assert catalogue['reviewers']==[{'id':'prep-specialist-fixture-a'}]
    row,_,_=create(f)
    row=command(f,row,'REQUEST_CHANGES','prep-specialist-fixture-a',reason='SYNTHETIC 请补两个材料槽').json()
    assert row['state']=='CHANGES_REQUESTED'
    row=add(f,row).json();row=add(f,row,'material_outline').json()
    before=read(f,row).json();row=command(f,row,'REVIEW','prep-specialist-fixture-a',reason='人工核对当前合成资料').json()
    assert row['state']=='REVIEWED' and row['snapshot_sha256']==before['snapshot_sha256']
    row=command(f,row,'CONFIRM',reason='企业确认本地资料准备').json();assert row['state']=='LOCAL_CONFIRMED'
    assert row['qualification']=='NOT_EVALUATED' and row['external_acceptance']=='NOT_SUBMITTED' and row['offline_fulfillment']=='NO_EVIDENCE'
    run=api.get('/api/runs/'+row['run_id'],headers=headers(tokens)).json()
    assert run['state']=='SUCCEEDED' and run['case']['state']=='NEEDS_INPUT'
    row=command(f,row,'REOPEN',reason='材料改变需要重新核对').json()
    state=read(f,row).json();assert state['preparation']['review_sha256'] is None and state['preparation']['state']=='IN_PREPARATION'
    assert [e['action'] for e in state['history']]==['CREATE','REQUEST_CHANGES','ADD_EVIDENCE','ADD_EVIDENCE','REVIEW','CONFIRM','REOPEN']
    assert all(i['authenticity']=='UNVERIFIED' for i in state['current_materials'])
    recreated=Store(store.dsn);assert prep.read(recreated,tokens['fixture-a'],UUID(row['preparation_id']))['snapshot_sha256']==state['snapshot_sha256']

@pytest.mark.parametrize('action,user',[('REVIEW','fixture-a'),('REQUEST_CHANGES','fixture-a'),('CONFIRM','prep-specialist-fixture-a'),('REOPEN','prep-specialist-fixture-a')])
def test_role_action_intersection_refuses_self_approval(preparation_fixture,action,user):
    f=preparation_fixture;row=filled(f);before=counts(f[1]);r=command(f,row,action,user,reason='SYNTHETIC')
    assert r.status_code==403 and counts(f[1])==before

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-b','prep-specialist-fixture-c'])
def test_cross_org_park_read_write_list_isolation(preparation_fixture,user):
    f=preparation_fixture;row=filled(f);before=counts(f[1])
    assert read(f,row,user).status_code==403
    assert command(f,row,'REVIEW',user,reason='SYNTHETIC').status_code==403
    assert f[3].get('/api/preparations',headers=headers(f[2],user)).json()['items']==[]
    assert counts(f[1])==before

@pytest.mark.parametrize('role',['park_specialist','resource_admin','service_executor'])
def test_unassigned_or_wrong_role_grant_is_not_authority(preparation_fixture,role):
    f=preparation_fixture;row=filled(f);token=secrets.token_urlsafe(32);f[2]['outsider']=token
    with f[1].connect() as c:
        c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',('outsider',digest(token),'park-a','org-a',role))
        c.execute("INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES('outsider','READ','park-a','org-a')")
        c.execute("INSERT INTO preparation_grants VALUES('outsider','park-a','org-a','REVIEW_ASSIGNED',true)")
    assert read(f,row,'outsider').status_code==403
    assert command(f,row,'REVIEW','outsider',reason='SYNTHETIC').status_code==403
    assert f[3].get('/api/facts?fields=region',headers=headers(f[2],'prep-specialist-fixture-a')).status_code==403
    assert f[3].get('/api/runs/'+row['run_id'],headers=headers(f[2],'prep-specialist-fixture-a')).status_code==403

@pytest.mark.parametrize('target',['enterprise_grant','reviewer_grant','reviewer_read','enterprise_execute','inactive'])
def test_current_revocation_rechecked_before_idempotent_replay(preparation_fixture,target):
    f=preparation_fixture;row=filled(f);user='prep-specialist-fixture-a' if target.startswith('reviewer') else 'fixture-a'
    action='REVIEW' if user.startswith('prep-') else 'REOPEN'
    if action=='REOPEN':row=command(f,row,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC').json()
    key=uuid4().hex;result=command(f,row,action,user,key=key,reason='SYNTHETIC');assert result.status_code==200
    with f[1].connect() as c:
        f[1].lock_principal(c,user,exclusive=True)
        if target in ('enterprise_grant','reviewer_grant'):c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(user,))
        elif target=='inactive':c.execute('UPDATE principals SET active=false WHERE id=%s',(user,))
        else:c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',(user,'READ' if target=='reviewer_read' else 'EXECUTE'))
    before=counts(f[1]);assert command(f,row,action,user,key=key,reason='SYNTHETIC').status_code==403
    assert counts(f[1])==before

@pytest.mark.parametrize('missing',['both','one'])
def test_missing_materials_cannot_be_reviewed(preparation_fixture,missing):
    f=preparation_fixture;row,_,_=create(f)
    if missing=='one':row=add(f,row).json()
    before=counts(f[1]);assert command(f,row,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC').status_code==409
    assert counts(f[1])==before


def test_material_update_invalidates_review_keeps_history_and_source(preparation_fixture):
    f=preparation_fixture;row=filled(f);row=command(f,row,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC').json();review_hash=row['snapshot_sha256'];old_revision=row['revision']
    row=add(f,row,text='<script>globalThis.PARKWEAVE_BAD=true</script> SYNTHETIC changed').json()
    assert row['state']=='IN_PREPARATION' and row['snapshot_sha256']!=review_hash
    assert command(f,row,'CONFIRM',revision=old_revision,reason='SYNTHETIC old page').status_code==409
    assert command(f,row,'CONFIRM',reason='SYNTHETIC no new review').status_code==409
    data=read(f,row).json();assert len(data['material_history'])==3 and data['current_materials'][1]['version']==2
    assert data['history'][-2]['payload']['snapshot_sha256']==review_hash
    # Independently compute rather than calling implementation helper.
    expected={'preparation_id':row['preparation_id'],'service_id':prep.SERVICE,'service_version':1,'materials':data['current_materials']}
    assert hashlib.sha256(json.dumps(expected,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==data['snapshot_sha256']


def test_idempotent_create_commands_and_cross_preparation_key_conflict(preparation_fixture):
    f=preparation_fixture;row,data,key=create(f)
    again=f[3].post('/api/preparations',headers=headers(f[2],key=key),json=data);assert again.json()==row
    altered=dict(data,service_version=2);assert f[3].post('/api/preparations',headers=headers(f[2],key=key),json=altered).status_code==409
    key=uuid4().hex;r=add(f,row,key=key);again=add(f,row,key=key);assert r.status_code==200 and again.json()==r.json()
    assert add(f,row,key=key,text='different').status_code==409
    assert counts(f[1])=={'preparations':1,'preparation_evidence':1,'preparation_events':2}
    other,_,_=create(f,goal='SYNTHETIC independent new case')
    assert read(f,other).json()['current_materials']==[]
    assert add(f,other,key=key).status_code==409


def test_concurrent_material_writes_reject_stale_version(preparation_fixture):
    f=preparation_fixture;row,_,_=create(f)
    body=prep.PreparationCommand(action='ADD_EVIDENCE',expected_revision=row['revision'],slot='need_summary',text='SYNTHETIC parallel',source_kind='USER_STATEMENT',source_label='SYNTHETIC')
    def write(_):
        try:return prep.command(f[0],f[2]['fixture-a'],UUID(row['preparation_id']),uuid4().hex,body)['revision']
        except __import__('parkweave.store',fromlist=['Conflict']).Conflict:return 'STALE'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(write,range(2)))
    assert sorted(str(x) for x in results)==['2','STALE']
    assert counts(f[1])=={'preparations':1,'preparation_evidence':1,'preparation_events':2}


def test_application_cannot_mutate_history_or_grants_and_migration_preserves(preparation_fixture):
    f=preparation_fixture;row=filled(f);before=read(f,row).json();f[1].migrate();f[1].migrate();assert read(f,row).json()==before
    for table in ('preparation_evidence','preparation_events','preparation_catalog','preparation_grants'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute('DELETE FROM '+table)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute('UPDATE '+table+' SET '+('active=false' if table=='preparation_grants' else 'namespace=namespace' if table=='preparation_catalog' else 'actor_id=actor_id'))


def test_event_insert_failure_rolls_back_material_and_revision(preparation_fixture):
    f=preparation_fixture;row,_,_=create(f);before=counts(f[1])
    with f[1].connect() as c:c.execute('REVOKE INSERT ON preparation_events FROM parkweave_app')
    body=prep.PreparationCommand(action='ADD_EVIDENCE',expected_revision=1,slot='need_summary',text='SYNTHETIC',source_kind='USER_STATEMENT',source_label='SYNTHETIC')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):prep.command(f[0],f[2]['fixture-a'],UUID(row['preparation_id']),uuid4().hex,body)
    assert counts(f[1])==before and read(f,row).json()['preparation']['revision']==1

@pytest.mark.parametrize('mutation',[{'role':'park_specialist'},{'text':' '},{'text':'x'*4001},{'source_kind':'MODEL_VERIFIED'},{'slot':'eligibility'},{'source_label':''}])
def test_untrusted_shape_and_false_provenance_rejected(preparation_fixture,mutation):
    f=preparation_fixture;row,_,_=create(f);before=counts(f[1])
    body={'action':'ADD_EVIDENCE','expected_revision':1,'slot':'need_summary','text':'SYNTHETIC','source_kind':'USER_STATEMENT','source_label':'SYNTHETIC',**mutation}
    assert f[3].post('/api/preparations/'+row['preparation_id']+'/commands',headers=headers(f[2],key=uuid4().hex),json=body).status_code==422
    assert counts(f[1])==before

def test_concurrent_distinct_create_keys_same_case_return_one_clear_conflict(preparation_fixture):
    from parkweave.domain import Intake
    from parkweave.store import Conflict
    f=preparation_fixture;run=f[0].submit(f[2]['fixture-a'],uuid4().hex,Intake(goal='SYNTHETIC create race'));f[0].finish(f[0].claim('synthetic'))
    body=prep.CreatePreparation(run_id=UUID(run),service_id=prep.SERVICE,service_version=1,reviewer_id='prep-specialist-fixture-a')
    def create_one(_):
        try:return prep.create(f[0],f[2]['fixture-a'],uuid4().hex,body)['state']
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(create_one,range(2)))
    assert sorted(results)==['CONFLICT','IN_PREPARATION'] and counts(f[1])['preparations']==1


def test_parallel_review_and_update_cannot_preserve_stale_approval(preparation_fixture):
    from parkweave.store import Conflict
    f=preparation_fixture;row=filled(f);id=UUID(row['preparation_id'])
    review=prep.PreparationCommand(action='REVIEW',expected_revision=row['revision'],reason='SYNTHETIC current snapshot')
    update=prep.PreparationCommand(action='ADD_EVIDENCE',expected_revision=row['revision'],slot='need_summary',text='SYNTHETIC changed',source_kind='USER_STATEMENT',source_label='SYNTHETIC v2')
    def apply(pair):
        token,body=pair
        try:return prep.command(f[0],token,id,uuid4().hex,body)['state']
        except Conflict:return 'STALE'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(apply,[(f[2]['fixture-a'],update),(f[2]['prep-specialist-fixture-a'],review)]))
    assert results.count('STALE')==1
    data=read(f,row).json()
    assert data['preparation']['revision']==row['revision']+1
    if data['preparation']['state']=='REVIEWED':assert data['preparation']['review_sha256']==data['snapshot_sha256']
    else:assert data['preparation']['review_sha256'] is None


def test_failed_or_foreign_run_and_invalid_reviewer_rejected(preparation_fixture):
    f=preparation_fixture;run=f[3].post('/api/runs',headers=headers(f[2],key=uuid4().hex),json={'goal':'SYNTHETIC queued'}).json()['run_id']
    data={'run_id':run,'service_id':prep.SERVICE,'service_version':1,'reviewer_id':'prep-specialist-fixture-a'}
    assert f[3].post('/api/preparations',headers=headers(f[2],key=uuid4().hex),json=data).status_code==409
    f[0].finish(f[0].claim('synthetic'))
    assert f[3].post('/api/preparations',headers=headers(f[2],'fixture-b',uuid4().hex),json=data).status_code==403
    data['reviewer_id']='prep-specialist-fixture-b'
    assert f[3].post('/api/preparations',headers=headers(f[2],key=uuid4().hex),json=data).status_code==403
    assert counts(f[1])['preparations']==0


def test_scope_grant_change_and_seed_never_reactivates(preparation_fixture):
    f=preparation_fixture;row=filled(f)
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        c.execute("UPDATE preparation_grants SET org_id='org-b',active=false WHERE principal_id='fixture-a'")
    prep.seed_synthetic(f[1],f[2])
    assert read(f,row).status_code==403
    with f[1].connect() as c:assert c.execute("SELECT active,org_id FROM preparation_grants WHERE principal_id='fixture-a'").fetchone()=={'active':False,'org_id':'org-b'}

def test_history_limit_rejects_write_without_partial_event(preparation_fixture):
    f=preparation_fixture;row,_,_=create(f)
    with f[1].connect() as c:c.execute('UPDATE preparations SET revision=64 WHERE id=%s',(UUID(row['preparation_id']),))
    before=counts(f[1]);assert add(f,row,revision=64).status_code==409
    assert counts(f[1])==before
