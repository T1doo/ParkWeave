"""PG/API evidence for the bounded assigned SYNTHETIC receipt; no physical claims."""
import hashlib
import secrets
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID,uuid4
import psycopg
import pytest
from parkweave import executor_receipts as er
from parkweave.store import Conflict,Store,digest
from test_preparation import preparation_fixture,filled,command as prep_command,headers

@pytest.fixture
def receipt_fixture(preparation_fixture):
    f=preparation_fixture
    for id,park,org in [('executor-a','park-a','org-a'),('executor-b','park-a','org-b'),('executor-c','park-b','org-c'),('unassigned','park-a','org-a')]:
        token=secrets.token_urlsafe(32);f[2][id]=token
        with f[1].connect() as c:
            c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',(id,digest(token),park,org,'service_executor'))
            c.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,%s,%s,%s)',(id,'READ',park,org))
    return f

def ready(f):
    row=filled(f);row=prep_command(f,row,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC current manual check').json()
    row=prep_command(f,row,'CONFIRM',reason='SYNTHETIC owner confirms preparation').json()
    f[1].assign_status('executor-a',UUID(row['run_id']),active=True)
    return row

def create(f,parent=None,key=None,**extra):
    parent=parent or ready(f)
    body={'preparation_id':parent['preparation_id'],'expected_preparation_revision':parent['revision'],'executor_id':'executor-a',**extra}
    r=f[3].post('/api/executor-receipts',headers=headers(f[2],key=key or uuid4().hex),json=body)
    return r,parent,body

def act(f,row,action,user=None,key=None,**extra):
    user=user or ('executor-a' if action=='SUBMIT' else 'fixture-a')
    body={'action':action,'expected_revision':row['step']['revision']}
    if action=='SUBMIT':body.update(text='SYNTHETIC local receipt',source_kind='SYNTHETIC',source_label='SYNTHETIC work log v1')
    else:body.update(reason='SYNTHETIC owner decision',receipt_sha256=row['current_receipt']['source_sha256'])
    body.update(extra)
    return f[3].post('/api/executor-receipts/'+row['step']['id']+'/commands',headers=headers(f[2],user,key or uuid4().hex),json=body)

def read(f,row,user='fixture-a'):
    return f[3].get('/api/executor-receipts/'+row['step']['id'],headers=headers(f[2],user))

def counts(f):
    with f[1].connect() as c:return [c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('service_receipt_steps','service_step_receipts','service_receipt_events')]

def test_full_append_correction_acknowledge_reopen_history_persistence(receipt_fixture):
    f=receipt_fixture;r,parent,_=create(f);assert r.status_code==201;row=r.json()
    assert row['step']['state']=='AWAITING_RECEIPT'
    row=act(f,row,'SUBMIT',text='<script>bad()</script> SYNTHETIC work record').json()
    assert row['current_receipt']['source_sha256']==hashlib.sha256(b'<script>bad()</script> SYNTHETIC work record').hexdigest()
    assert row['current_receipt']['actor_id']=='executor-a' and row['current_receipt']['version']==1
    row=act(f,row,'REQUEST_CHANGES').json();assert row['step']['state']=='CHANGES_REQUESTED'
    row=act(f,row,'SUBMIT',text='SYNTHETIC corrected receipt',source_label='SYNTHETIC v2').json()
    row=act(f,row,'ACKNOWLEDGE').json();assert row['step']['state']=='LOCAL_ACKNOWLEDGED'
    row=act(f,row,'REOPEN').json();assert row['step']['state']=='AWAITING_RECEIPT'
    row=act(f,row,'SUBMIT',text='SYNTHETIC reopened receipt',source_label='SYNTHETIC v3').json()
    assert [r['version'] for r in row['receipt_history']]==[1,2,3]
    assert [r['action'] for r in row['history']]==['CREATE','SUBMIT','REQUEST_CHANGES','SUBMIT','ACKNOWLEDGE','REOPEN','SUBMIT']
    assert counts(f)==[1,3,7] and not row['case_goal_completed']
    assert (row['qualification'],row['external_acceptance'],row['offline_fulfillment'])==('NOT_EVALUATED','NOT_SUBMITTED','NO_EVIDENCE')
    run=f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2])).json();assert run['state']=='SUCCEEDED' and run['case']['state']=='NEEDS_INPUT'
    fresh=er.read(Store(f[0].dsn),f[2]['executor-a'],UUID(row['step']['id']))
    assert fresh['step']['revision']==7 and len(fresh['receipt_history'])==3
    encoded=read(f,row,'executor-a').text
    assert 'current_materials' not in encoded and 'material_history' not in encoded and 'SYNTHETIC material list' not in encoded

@pytest.mark.parametrize('user',['fixture-b','fixture-c','executor-b','executor-c','unassigned','prep-specialist-fixture-a'])
def test_cross_owner_tenant_unassigned_wrong_role_refused(receipt_fixture,user):
    f=receipt_fixture;r,_,_=create(f);row=r.json();before=counts(f)
    assert read(f,row,user).status_code==403
    assert act(f,row,'SUBMIT',user).status_code==403
    listing=f[3].get('/api/executor-receipts',headers=headers(f[2],user))
    assert listing.status_code==403 if user.startswith('prep-') else listing.json()['items']==[]
    assert counts(f)==before

@pytest.mark.parametrize('action,user',[('SUBMIT','fixture-a'),('ACKNOWLEDGE','executor-a'),('REQUEST_CHANGES','executor-a'),('REOPEN','executor-a')])
def test_roles_cannot_act_for_counterparty(receipt_fixture,action,user):
    f=receipt_fixture;r,_,_=create(f);row=act(f,r.json(),'SUBMIT').json();before=counts(f)
    assert act(f,row,action,user).status_code==403 and counts(f)==before
    assert f[3].post('/api/runs',headers=headers(f[2],'executor-a',uuid4().hex),json={'goal':'SYNTHETIC forbidden'}).status_code==403
    assert f[3].get('/api/facts?fields=region',headers=headers(f[2],'executor-a')).status_code==403

@pytest.mark.parametrize('change',['assignment','read','inactive','role','org','owner_execute'])
def test_current_revocation_before_replay_and_owner_decision(receipt_fixture,change):
    f=receipt_fixture;r,_,_=create(f);row=r.json();key=uuid4().hex;done=act(f,row,'SUBMIT',key=key).json()
    user='fixture-a' if change=='owner_execute' else 'executor-a'
    with f[1].connect() as c:
        f[1].lock_principal(c,user,exclusive=True)
        if change=='assignment':c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
        elif change in ('read','owner_execute'):c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',(user,'EXECUTE' if change=='owner_execute' else 'READ'))
        else:c.execute("UPDATE principals SET "+{'inactive':'active=false','role':"role='resource_admin'",'org':"org_id='org-b'"}[change]+" WHERE id='executor-a'")
    before=counts(f)
    if change!='owner_execute':assert act(f,row,'SUBMIT',key=key).status_code==403
    assert act(f,done,'ACKNOWLEDGE').status_code==403 and counts(f)==before
    if change!='owner_execute':assert f[3].get('/api/executor-receipts',headers=headers(f[2],'executor-a')).status_code in (200,403)


def test_catalog_only_current_assigned_and_create_never_assigns(receipt_fixture):
    f=receipt_fixture;parent=ready(f)
    catalog=f[3].get('/api/executor-receipts/catalog?preparation_id='+parent['preparation_id'],headers=headers(f[2])).json()
    assert catalog['executors']==[{'id':'executor-a'}]
    for id in ('unassigned','executor-b','prep-specialist-fixture-a'):
        assert create(f,parent,executor_id=id)[0].status_code==403
    with f[1].connect() as c:assert c.execute("SELECT count(*) n FROM run_assignments WHERE principal_id='unassigned'").fetchone()['n']==0
    assert counts(f)==[0,0,0]


def test_parent_version_change_blocks_new_writes_keeps_history_and_replay(receipt_fixture):
    f=receipt_fixture;r,parent,_=create(f);row=r.json();key=uuid4().hex;done=act(f,row,'SUBMIT',key=key).json()
    assert prep_command(f,parent,'REOPEN',reason='SYNTHETIC preparation changed').status_code==200
    before=counts(f);assert read(f,done).json()['dependency']=='DEPENDENCY_CHANGED'
    assert act(f,done,'ACKNOWLEDGE').status_code==409
    assert act(f,row,'SUBMIT',key=key).json()['event']==done['event'] and counts(f)==before


def test_stale_version_hash_and_invalid_state_have_no_effect(receipt_fixture):
    f=receipt_fixture;r,_,_=create(f);row=r.json();done=act(f,row,'SUBMIT').json();before=counts(f)
    assert act(f,row,'SUBMIT').status_code==409
    assert act(f,done,'SUBMIT').status_code==409
    assert act(f,done,'ACKNOWLEDGE',receipt_sha256='0'*64).status_code==409
    assert act(f,done,'ACKNOWLEDGE',expected_revision=1).status_code==409
    assert counts(f)==before


def test_idempotency_same_payload_historical_state_and_cross_step_conflict(receipt_fixture):
    f=receipt_fixture;key=uuid4().hex;r,parent,body=create(f,key=key);row=r.json();assert create(f,parent,key=key)[0].json()==row
    skey=uuid4().hex;done=act(f,row,'SUBMIT',key=skey).json();assert act(f,row,'SUBMIT',key=skey).json()==done
    assert act(f,row,'SUBMIT',key=skey,text='SYNTHETIC different').status_code==409
    acknowledged=act(f,done,'ACKNOWLEDGE').json();replayed=act(f,row,'SUBMIT',key=skey).json()
    assert replayed['event']==done['event'] and replayed['step']['state']=='LOCAL_ACKNOWLEDGED'
    other,_,_=create(f);assert act(f,other.json(),'SUBMIT',key=skey).status_code==409
    assert len(acknowledged['receipt_history'])==1

@pytest.mark.parametrize('same_key',[False,True])
def test_concurrent_create_and_submit_are_atomic(receipt_fixture,same_key):
    f=receipt_fixture;parent=ready(f);shared=uuid4().hex
    data=er.Create(preparation_id=parent['preparation_id'],expected_preparation_revision=parent['revision'],executor_id='executor-a')
    def make(_):
        try:return er.create(f[0],f[2]['fixture-a'],shared if same_key else uuid4().hex,data)
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(make,range(2)))
    assert rows.count('CONFLICT')==(0 if same_key else 1) and counts(f)==[1,0,1]
    row=next(r for r in rows if isinstance(r,dict));body=er.Command(action='SUBMIT',expected_revision=1,text='SYNTHETIC parallel receipt',source_kind='SYNTHETIC',source_label='SYNTHETIC v1');shared=uuid4().hex
    def send(_):
        try:return er.command(f[0],f[2]['executor-a'],row['step']['id'],shared if same_key else uuid4().hex,body)['step']['state']
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(send,range(2)))
    assert results.count('CONFLICT')==(0 if same_key else 1) and counts(f)==[1,1,2]


def test_event_failure_rolls_back_receipt_and_state(receipt_fixture):
    f=receipt_fixture;r,_,_=create(f);row=r.json();before=counts(f)
    with f[1].connect() as c:c.execute('REVOKE INSERT ON service_receipt_events FROM parkweave_app')
    body=er.Command(action='SUBMIT',expected_revision=1,text='SYNTHETIC',source_kind='SYNTHETIC',source_label='SYNTHETIC v1')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):er.command(f[0],f[2]['executor-a'],UUID(row['step']['id']),uuid4().hex,body)
    assert counts(f)==before and read(f,row).json()['step']['state']=='AWAITING_RECEIPT'


def test_permissions_migration_and_current_receipt_foreign_step_constraint(receipt_fixture):
    f=receipt_fixture;r,_,_=create(f);row=act(f,r.json(),'SUBMIT').json();other,_,_=create(f)
    for sql in ('DELETE FROM service_receipt_steps','UPDATE service_receipt_steps SET executor_id=executor_id','UPDATE service_step_receipts SET text=text','DELETE FROM service_step_receipts','UPDATE service_receipt_events SET payload=payload','DELETE FROM service_receipt_events'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute(sql)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with f[0].connect() as c:c.execute('UPDATE service_receipt_steps SET current_receipt_id=%s WHERE id=%s',(UUID(row['current_receipt']['id']),UUID(other.json()['step']['id'])))
    before=read(f,row).json()
    with f[1].connect() as c:c.execute('DELETE FROM schema_version WHERE version>=13')
    f[1].migrate();f[1].migrate();assert read(f,row).json()==before
    with f[1].connect() as c:assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']==22

@pytest.mark.parametrize('mutation',[{'source_kind':'VERIFIED'},{'text':' '},{'source_label':''},{'actor_id':'fixture-a'},{'text':'x'*4001},{'reason':'cannot mix'}])
def test_invalid_provenance_shape_has_no_effect(receipt_fixture,mutation):
    f=receipt_fixture;r,_,_=create(f);row=r.json();before=counts(f)
    assert act(f,row,'SUBMIT',**mutation).status_code==422 and counts(f)==before

@pytest.mark.parametrize('field',['revision','hash','state'])
def test_parent_bindings_all_rechecked(receipt_fixture,field):
    f=receipt_fixture;r,parent,_=create(f);row=r.json()
    with f[1].connect() as c:c.execute('UPDATE preparations SET '+{'revision':'revision=revision+1','hash':"review_sha256=repeat('0',64)",'state':"state='IN_PREPARATION',review_sha256=NULL"}[field]+' WHERE id=%s',(UUID(parent['preparation_id']),))
    assert read(f,row,'executor-a').json()['dependency']=='DEPENDENCY_CHANGED'
    before=counts(f);assert act(f,row,'SUBMIT').status_code==409 and counts(f)==before


def test_exact12_upgrade_preserves_preparation_and_creates_receipt_tables(receipt_fixture):
    f=receipt_fixture;parent=ready(f)
    with f[1].connect() as c:
        c.execute('DROP TABLE service_receipt_events,service_step_receipts,service_receipt_steps CASCADE')
        c.execute('DELETE FROM schema_version WHERE version>=13')
    f[1].migrate();f[1].migrate()
    with f[1].connect() as c:
        c.execute('GRANT SELECT,INSERT ON service_receipt_steps,service_step_receipts,service_receipt_events TO parkweave_app')
        c.execute('GRANT UPDATE(state,revision,current_receipt_id) ON service_receipt_steps TO parkweave_app')
    r,_,_=create(f,parent);assert r.status_code==201 and r.json()['step']['preparation_revision']==parent['revision']


def test_exclusive_revocation_blocks_new_call_with_bounded_conflict_then_denies(receipt_fixture):
    f=receipt_fixture;r,_,_=create(f);row=r.json();before=counts(f)
    with f[1].connect() as c:
        f[1].lock_principal(c,'executor-a',exclusive=True)
        c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
        # In-flight administrative change is bounded by the domain 3s lock timeout.
        with ThreadPoolExecutor(max_workers=1) as pool:
            response=pool.submit(act,f,row,'SUBMIT').result(timeout=8)
        assert response.status_code==409
    assert act(f,row,'SUBMIT').status_code==403 and counts(f)==before
