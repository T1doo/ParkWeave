"""Original ACCEPT key recovery is a current-authorized read, never a retry."""
from uuid import UUID,uuid4
import pytest

from test_service_dispatches import receipt_fixture,preparation_fixture,offer,command
from test_preparation import headers
from service_release_acceptance_support import authority_snapshot,case_history
from test_dispatch_recovery import records,changed_materials


def selection(row):
    return dict(preparation_id=row['preparation_id'],case_id=row['case_id'],run_id=row['run_id'],
                offer_id=row['current_offer']['id'],expected_revision=row['revision'],
                preparation_revision=row['preparation_revision'])


def recover(f,row,key,*,user='executor-a',params=None):
    return f[3].get('/api/service-dispatches/'+row['dispatch_id']+'/accept-recovery',
                    params=selection(row) if params is None else params,headers=headers(f[2],user,key))


def test_original_accept_committed_and_not_observed_are_read_only(receipt_fixture):
    f=receipt_fixture;row=offer(f)[0].json();key=uuid4().hex
    before=case_history(f[1],row['preparation_id']);auth=authority_snapshot(f[1])
    missing=recover(f,row,key)
    assert missing.status_code==200,missing.text
    assert missing.json()['status']=='NOT_OBSERVED' and missing.json()['event'] is None
    assert case_history(f[1],row['preparation_id'])==before
    done=command(f,row,'ACCEPT',key=key).json()
    before=case_history(f[1],row['preparation_id'])
    result=recover(f,row,key);assert result.status_code==200,result.text
    data=result.json();assert result.headers['cache-control']=='no-store'
    assert data['status']=='COMMITTED' and data['historical_only'] and data['read_only']
    assert data['automatically_replayed'] is False and data['case_goal_completed'] is False
    assert data['event']['receipt_step_id']==done['receipt_step_id']
    assert data['event']['revision']==row['revision']+1 and data['event']['action']=='ACCEPT'
    assert 'reason' not in result.text and f[2]['executor-a'] not in result.text
    assert case_history(f[1],row['preparation_id'])==before and authority_snapshot(f[1])==auth


@pytest.mark.parametrize('user',['fixture-a','fixture-b','fixture-c','prep-specialist-fixture-a',
                                 'executor-b','executor-c','unassigned'])
def test_current_actor_scope_denies_without_private_proof(receipt_fixture,user):
    f=receipt_fixture;row=offer(f)[0].json();key=uuid4().hex
    command(f,row,'ACCEPT',key=key);before=records(f)
    r=recover(f,row,key,user=user)
    assert r.status_code==403 and r.json()=={'detail':'record unavailable or authorization denied'}
    assert records(f)==before


@pytest.mark.parametrize('change',['READ','assignment','inactive','role','org'])
def test_revocation_dominates_existing_accept_proof(receipt_fixture,change):
    f=receipt_fixture;row=offer(f)[0].json();key=uuid4().hex;command(f,row,'ACCEPT',key=key)
    with f[1].connect() as c:
        f[1].lock_principal(c,'executor-a',exclusive=True)
        if change=='READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
        elif change=='assignment':c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
        else:c.execute("UPDATE principals SET "+{'inactive':'active=false','role':"role='resource_admin'",'org':"org_id='org-b'"}[change]+" WHERE id='executor-a'")
    before=records(f);auth=authority_snapshot(f[1])
    assert recover(f,row,key).status_code==403
    assert records(f)==before and authority_snapshot(f[1])==auth


@pytest.mark.parametrize('field',['preparation_id','case_id','run_id','offer_id','expected_revision','preparation_revision'])
def test_selection_mismatch_cannot_project_other_case_or_offer(receipt_fixture,field):
    f=receipt_fixture;row=offer(f)[0].json();key=uuid4().hex;command(f,row,'ACCEPT',key=key)
    params=selection(row);params[field]=params[field]+1 if 'revision' in field else str(uuid4())
    before=records(f);r=recover(f,row,key,params=params)
    assert r.status_code==(409 if 'revision' in field else 403) and records(f)==before


def test_same_actor_other_case_key_and_non_accept_key_refused(receipt_fixture):
    f=receipt_fixture;a=offer(f)[0].json();ka=uuid4().hex;command(f,a,'ACCEPT',key=ka)
    b=offer(f)[0].json();kb=uuid4().hex;command(f,b,'DECLINE',key=kb);before=records(f)
    assert recover(f,b,ka).status_code==409 and recover(f,b,kb).status_code==409
    assert records(f)==before


@pytest.mark.parametrize('bad',[{'extra':'x'},{'expected_revision':'1.0'},{'expected_revision':'true'},
                              {'expected_revision':'01'},{'preparation_revision':'0'}])
def test_strict_recovery_query(receipt_fixture,bad):
    f=receipt_fixture;row=offer(f)[0].json();params={**selection(row),**bad};before=records(f)
    assert recover(f,row,uuid4().hex,params=params).status_code==422 and records(f)==before


def test_duplicate_query_and_missing_key_refused(receipt_fixture):
    f=receipt_fixture;row=offer(f)[0].json();params=list(selection(row).items())
    params.append(('offer_id',row['current_offer']['id']))
    assert recover(f,row,uuid4().hex,params=params).status_code==422
    assert f[3].get('/api/service-dispatches/'+row['dispatch_id']+'/accept-recovery',
                    params=selection(row),headers=headers(f[2],'executor-a')).status_code==422


@pytest.mark.parametrize('damage',['dispatch_payload','receipt_payload','receipt_fingerprint','receipt_binding'])
def test_inconsistent_atomic_proof_is_not_accepted(receipt_fixture,damage):
    f=receipt_fixture;row=offer(f)[0].json();key=uuid4().hex;done=command(f,row,'ACCEPT',key=key).json()
    with f[1].connect() as c:
        if damage=='dispatch_payload':c.execute("UPDATE service_dispatch_events SET payload=jsonb_set(payload,'{revision}','true') WHERE request_key=%s",(key,))
        elif damage=='receipt_payload':c.execute("UPDATE service_receipt_events SET payload=jsonb_set(payload,'{offer_id}',to_jsonb(%s::text)) WHERE step_id=%s",(str(uuid4()),UUID(done['receipt_step_id'])))
        elif damage=='receipt_fingerprint':c.execute("UPDATE service_receipt_events SET fingerprint=repeat('0',64) WHERE step_id=%s",(UUID(done['receipt_step_id']),))
        else:c.execute('UPDATE service_receipt_steps SET preparation_revision=preparation_revision+1 WHERE id=%s',(UUID(done['receipt_step_id']),))
    before=records(f);assert recover(f,row,key).status_code==409 and records(f)==before


def test_history_remains_read_only_after_parent_changes_and_original_arrives_later(receipt_fixture):
    f=receipt_fixture;r,parent,_=offer(f);row=r.json();key=uuid4().hex
    assert recover(f,row,key).json()['status']=='NOT_OBSERVED'
    done=command(f,row,'ACCEPT',key=key);assert done.status_code==200
    changed_materials(f,parent);before=records(f)
    r=recover(f,row,key);assert r.status_code==200 and r.json()['status']=='COMMITTED'
    assert r.json()['historical_only'] and r.json()['read_only'] and records(f)==before
