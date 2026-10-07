"""Same-Case actual PG/API snapshot, current denial and zero authority writes."""
from uuid import uuid4
import pytest
from parkweave.case_path import read
from parkweave.store import Store
from test_preparation import preparation_fixture,create as prepare,headers
from test_executor_receipts import receipt_fixture,ready
from test_plan_preview import digest
from test_service_dispatches import offer,command


def path(f,p,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/case-path',headers=headers(f[2],user))


def test_unassigned_new_case_fails_closed_without_any_business_or_authority_write(preparation_fixture):
    f=preparation_fixture;p,_,_=prepare(f);before=digest(f)
    for _ in range(2):
        r=path(f,p);assert r.status_code==200,r.text;x=r.json()
        assert (x['case_id'],x['run_id'],x['preparation_id'])==(p['case_id'],p['run_id'],p['preparation_id'])
        assert x['existing_run_access']['state']=='BLOCKED_NO_EXISTING_ASSIGNMENT'
        assert not x['existing_run_access']['candidate_available'] and not x['existing_run_access']['creates_access']
        assert not x['request']['recorded'] and x['request']['coverage_state']=='NOT_RECORDED'
        assert not x['plan']['recorded'] and not x['dispatch']['recorded'] and not x['receipt']['recorded']
        assert x['qualification_truth']=='UNKNOWN' and not x['case_goal_completed']
        assert not x['business_writes'] and not x['authorization_writes'] and digest(f)==before
    assert f[3].post('/api/preparations/'+p['preparation_id']+'/case-path',headers=headers(f[2]),json={'approved':True}).status_code==405


def test_existing_assignment_and_offer_receipt_project_same_case_without_automatic_acceptance(receipt_fixture):
    # Existing test fixture setup is separate from the production GET, never a product grant API.
    f=receipt_fixture;p=ready(f);before=digest(f);x=path(f,p).json()
    assert x['existing_run_access']['state']=='EXISTING_ASSIGNMENT_AVAILABLE' and digest(f)==before
    d=offer(f,p)[0].json();d=command(f,d,'ACCEPT').json();before=digest(f);x=path(f,p).json()
    assert x['case_id']==p['case_id'] and x['run_id']==p['run_id']
    assert x['dispatch']=={'recorded':True,'offer_state':'ACCEPTED'} and x['receipt']=={'recorded':True,'state':'AWAITING_RECEIPT'}
    assert x['record_acceptance']=='NOT_REVALIDATED_BY_THIS_READ' and not x['case_goal_completed'] and digest(f)==before
    fresh=read(Store(f[0].dsn),f[2]['fixture-a'],p['preparation_id']);assert str(fresh['run_id'])==p['run_id']
    assert 'executor-a' not in path(f,p).text and 'token' not in path(f,p).text


@pytest.mark.parametrize('target',['assignment','read','inactive','role','tenant'])
def test_current_existing_access_loss_is_rechecked_not_cached_or_repaired(receipt_fixture,target):
    f=receipt_fixture;p=ready(f);assert path(f,p).json()['existing_run_access']['candidate_available']
    with f[1].connect() as c:
        if target=='assignment':c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
        elif target=='read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
        elif target=='inactive':c.execute("UPDATE principals SET active=false WHERE id='executor-a'")
        elif target=='role':c.execute("UPDATE principals SET role='resource_admin' WHERE id='executor-a'")
        else:c.execute("UPDATE principals SET org_id='org-b' WHERE id='executor-a'")
    before=digest(f);assert path(f,p).json()['existing_run_access']['state']=='BLOCKED_NO_EXISTING_ASSIGNMENT' and digest(f)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','prep-specialist-fixture-b','executor-a','unassigned'])
def test_owner_only_path_does_not_expand_other_role_or_tenant_visibility(receipt_fixture,user):
    f=receipt_fixture;p=ready(f);before=digest(f);r=path(f,p,user)
    assert r.status_code==403 and 'case_id' not in r.text and 'run_id' not in r.text and digest(f)==before


@pytest.mark.parametrize('target',['READ','PREPARE','inactive'])
def test_owner_authority_denial_never_serves_old_snapshot(receipt_fixture,target):
    f=receipt_fixture;p=ready(f);assert path(f,p).status_code==200
    with f[1].connect() as c:
        if target=='inactive':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif target=='READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        else:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
    before=digest(f);assert path(f,p).status_code==403 and digest(f)==before


def test_other_run_assignment_never_satisfies_current_case(receipt_fixture):
    f=receipt_fixture;assigned=ready(f);current,_,_=prepare(f);before=digest(f)
    assert path(f,assigned).json()['existing_run_access']['candidate_available']
    assert path(f,current).json()['existing_run_access']['state']=='BLOCKED_NO_EXISTING_ASSIGNMENT' and digest(f)==before
    assert path(f,{**current,'preparation_id':str(uuid4())}).status_code==403 and digest(f)==before

def test_read_does_not_require_execute_or_enable_commands(receipt_fixture):
    f=receipt_fixture;p=ready(f)
    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    before=digest(f);assert path(f,p).status_code==200 and digest(f)==before


def test_mismatched_receipt_binding_is_not_presented_as_same_case(receipt_fixture):
    f=receipt_fixture;p=ready(f);d=offer(f,p)[0].json();command(f,d,'ACCEPT');other,_,_=prepare(f)
    with f[1].connect() as c:c.execute('UPDATE service_receipt_steps SET case_id=%s WHERE preparation_id=%s',(other['case_id'],p['preparation_id']))
    before=digest(f);assert not path(f,p).json()['receipt']['recorded'] and digest(f)==before
