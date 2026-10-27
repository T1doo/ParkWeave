"""Manual SUBMIT original-key reads, actual ASGI and owned synthetic PostgreSQL."""
from uuid import UUID,uuid4
import pytest
from test_executor_receipts import receipt_fixture,preparation_fixture,create,act,read
from test_preparation import headers
from test_dispatch_recovery import records,changed_materials
from service_release_acceptance_support import authority_snapshot,case_history


def selection(row):
    s=row['step']
    return dict(preparation_id=s['preparation_id'],case_id=s['case_id'],run_id=s['run_id'],
                preparation_revision=s['preparation_revision'],expected_revision=s['revision'])


def recover(f,row,key,*,user='executor-a',params=None):
    return f[3].get('/api/executor-receipts/'+row['step']['id']+'/submit-recovery',
        params=selection(row) if params is None else params,headers=headers(f[2],user,key))


def initial(f):
    r,parent,_=create(f);assert r.status_code==201,r.text
    return r.json(),parent


def test_committed_and_absence_are_read_only_with_opaque_metadata(receipt_fixture):
    f=receipt_fixture;row,parent=initial(f);key=uuid4().hex
    before=case_history(f[1],parent['preparation_id']);auth=authority_snapshot(f[1])
    absent=recover(f,row,key);assert absent.status_code==200,absent.text
    assert absent.json()['status']=='NOT_OBSERVED' and absent.json()['event'] is None
    assert case_history(f[1],parent['preparation_id'])==before
    done=act(f,row,'SUBMIT',key=key,text='  SYNTHETIC original private receipt  ',source_label='  SYNTHETIC private v1  ')
    assert done.status_code==200,done.text
    before=case_history(f[1],parent['preparation_id']);r=recover(f,row,key)
    assert r.status_code==200,r.text
    x=r.json();assert r.headers['cache-control']=='no-store' and x['status']=='COMMITTED'
    assert x['read_only'] and x['historical_only'] and not x['automatically_replayed'] and not x['case_goal_completed']
    receipt=done.json()['current_receipt'];assert x['event']['receipt_id']==receipt['id'] and x['event']['receipt_version']==1
    assert x['event']['receipt_sha256']==receipt['source_sha256']
    assert all(value not in r.text for value in (receipt['text'],receipt['source_label'],f[2]['executor-a'],'"text"'))
    assert x['actor_ref']==done.json()['actor_ref']
    assert case_history(f[1],parent['preparation_id'])==before and authority_snapshot(f[1])==auth


@pytest.mark.parametrize('user',['fixture-a','fixture-b','fixture-c','executor-b','executor-c','unassigned','prep-specialist-fixture-a'])
def test_other_current_actor_cannot_get_private_original_proof(receipt_fixture,user):
    f=receipt_fixture;row,_=initial(f);key=uuid4().hex;assert act(f,row,'SUBMIT',key=key).status_code==200
    before=records(f);r=recover(f,row,key,user=user)
    assert r.status_code==403 and r.json()=={'detail':'record unavailable or authorization denied'} and records(f)==before


@pytest.mark.parametrize('change',['READ','assignment','inactive','role','org'])
def test_current_revocation_dominates_original_committed_event(receipt_fixture,change):
    f=receipt_fixture;row,_=initial(f);key=uuid4().hex;act(f,row,'SUBMIT',key=key)
    with f[1].connect() as c:
        f[1].lock_principal(c,'executor-a',exclusive=True)
        if change=='READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
        elif change=='assignment':c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
        else:c.execute("UPDATE principals SET "+{'inactive':'active=false','role':"role='resource_admin'",'org':"org_id='org-b'"}[change]+" WHERE id='executor-a'")
    before=records(f);auth=authority_snapshot(f[1]);assert recover(f,row,key).status_code==403
    assert records(f)==before and authority_snapshot(f[1])==auth


@pytest.mark.parametrize('field',['preparation_id','case_id','run_id','expected_revision','preparation_revision'])
def test_original_coordinates_cannot_project_another_scope_or_revision(receipt_fixture,field):
    f=receipt_fixture;row,_=initial(f);key=uuid4().hex;act(f,row,'SUBMIT',key=key)
    q=selection(row);q[field]=q[field]+1 if 'revision' in field else str(uuid4())
    before=records(f);r=recover(f,row,key,params=q)
    assert r.status_code==(409 if 'revision' in field else 403) and records(f)==before


@pytest.mark.parametrize('bad',[{'extra':'x'},{'expected_revision':'1.0'},{'expected_revision':'true'},
                              {'expected_revision':'01'},{'expected_revision':'64'},{'preparation_revision':'0'}])
def test_query_is_strict_and_bounded(receipt_fixture,bad):
    f=receipt_fixture;row,_=initial(f);before=records(f)
    assert recover(f,row,uuid4().hex,params={**selection(row),**bad}).status_code==422 and records(f)==before


def test_duplicate_query_and_missing_key_are_rejected(receipt_fixture):
    f=receipt_fixture;row,_=initial(f);q=list(selection(row).items());q.append(q[0]);before=records(f)
    assert recover(f,row,uuid4().hex,params=q).status_code==422
    assert f[3].get('/api/executor-receipts/'+row['step']['id']+'/submit-recovery',params=selection(row),headers=headers(f[2],'executor-a')).status_code==422
    assert records(f)==before


@pytest.mark.parametrize('damage',['fingerprint','payload_revision','payload_action','payload_receipt_hash',
    'payload_local_record_mode','payload_local_execution','receipt_text','receipt_version','receipt_local_execution','bad_frontier'])
def test_inconsistent_or_local_generated_evidence_cannot_be_manual_proof(receipt_fixture,damage):
    f=receipt_fixture;row,_=initial(f);key=uuid4().hex;done=act(f,row,'SUBMIT',key=key).json()
    with f[1].connect() as c:
        if damage=='fingerprint':c.execute("UPDATE service_receipt_events SET fingerprint=repeat('0',64) WHERE request_key=%s",(key,))
        elif damage=='receipt_text':c.execute("UPDATE service_step_receipts SET text='SYNTHETIC modified' WHERE id=%s",(UUID(done['current_receipt']['id']),))
        elif damage=='receipt_version':c.execute('UPDATE service_step_receipts SET version=2 WHERE id=%s',(UUID(done['current_receipt']['id']),))
        elif damage=='receipt_local_execution':
            c.execute('ALTER TABLE service_step_receipts ADD COLUMN IF NOT EXISTS adapter_execution jsonb')
            c.execute("UPDATE service_step_receipts SET adapter_execution='{}' WHERE id=%s",(UUID(done['current_receipt']['id']),))
        else:
            field,value={'payload_revision':('revision','true'),'payload_action':('action','"ACKNOWLEDGE"'),
                'payload_receipt_hash':('receipt_sha256','"'+'0'*64+'"'),
                'payload_local_record_mode':('record_mode','"SERVER_GENERATED_LOCAL_EXECUTION"'),
                'payload_local_execution':('adapter_execution','null'),'bad_frontier':('expected_business_frontier','{}')}[damage]
            c.execute('UPDATE service_receipt_events SET payload=jsonb_set(payload,%s,%s::jsonb) WHERE request_key=%s',([field],value,key))
    before=records(f);r=recover(f,row,key);assert r.status_code==409,r.text
    assert records(f)==before


def test_original_history_remains_precise_after_correction_new_version_and_ack(receipt_fixture):
    f=receipt_fixture;row,parent=initial(f);key=uuid4().hex
    first=act(f,row,'SUBMIT',key=key).json();later=act(f,first,'REQUEST_CHANGES').json()
    later=act(f,later,'SUBMIT',text='SYNTHETIC replacement').json();later=act(f,later,'ACKNOWLEDGE').json()
    before=case_history(f[1],parent['preparation_id']);r=recover(f,row,key)
    assert r.status_code==200,r.text
    assert r.json()['event']['receipt_id']==first['current_receipt']['id']!=later['current_receipt']['id']
    assert r.json()['event']['revision']==2 and case_history(f[1],parent['preparation_id'])==before


def test_original_arrives_after_absence_and_parent_can_later_change(receipt_fixture):
    f=receipt_fixture;row,parent=initial(f);key=uuid4().hex
    assert recover(f,row,key).json()['status']=='NOT_OBSERVED'
    assert act(f,row,'SUBMIT',key=key).status_code==200
    changed_materials(f,parent);before=records(f)
    assert recover(f,row,key).json()['status']=='COMMITTED' and records(f)==before


def test_other_step_key_and_non_submit_event_do_not_prove_this_request(receipt_fixture):
    f=receipt_fixture;a,_=initial(f);key=uuid4().hex;first=act(f,a,'SUBMIT',key=key).json()
    b,_=initial(f);before=records(f)
    assert recover(f,b,key).status_code==409 and records(f)==before
    owner_key=uuid4().hex;act(f,first,'ACKNOWLEDGE',key=owner_key)
    assert recover(f,a,owner_key).json()['status']=='NOT_OBSERVED'
