"""New strict Release tail: original commands, fences, denial and atomicity."""
from uuid import UUID,uuid4
import pytest
from release_p345_support import (strict_p2,release_case,cancel33_case,capability_resource_catalog,
    capability_catalog,preparation_fixture,receipt_fixture,accept_new,submitted,snapshot,ok)
from test_preparation import headers
from test_service_case_steps import verified,command as verify,read as plan_read
from test_executor_receipts import act as receipt_command
from test_case_lifecycle import read as local_read,act as local_command
from test_case_lifecycle_recovery import recover as local_recover
from service_release_acceptance_support import case_history


def test_new_strict_release_original_p3_p5_outputs_and_local_original_recovery(strict_p2):
    x=strict_p2;f,p=x['f'],x['p'];row=submitted(x)
    ok(receipt_command(f,row,'ACKNOWLEDGE',expected_business_frontier=row['business_frontier']))
    verified(f,p,'P4')
    current=ok(local_read(f,p));key=uuid4().hex
    ok(local_command(f,p,current,'REVALIDATE',key=key,expected_business_frontier=current['business_frontier']))
    before=snapshot(f);recovery=ok(local_recover(f,p,key));assert recovery['status']=='COMMITTED'
    assert not recovery['automatically_replayed'] and snapshot(f)==before
    current=ok(local_read(f,p))
    ok(local_command(f,p,current,'CLOSE_LOCAL_RECORD',expected_business_frontier=current['business_frontier']))
    verified(f,p,'P5')
    result=ok(f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2])))
    assert result['state']=='LOCAL_OUTPUTS_VERIFIED' and len(result['results'])==6 and not result['case_goal_completed']
    work=ok(f[3].get('/api/cases/worklist',headers=headers(f[2])))
    assert next(i for i in work['items'] if i['case_id']==p['case_id'])['attention']=='LOCAL_CLOSED'
    assert case_history(f[1],x['t']['x']['p']['preparation_id'])==x['t']['old']


@pytest.mark.parametrize('mode',['old_receipt','stale_frontier','stale_plan','assignment_revoked','owner_revoked','rollback'])
def test_new_strict_release_rejects_wrong_receipt_stale_fence_revocation_and_rolls_back(strict_p2,mode,monkeypatch):
    x=strict_p2;f,p=x['f'],x['p']
    if mode=='stale_plan':
        old=ok(plan_read(f,p));accept_new(x)
        verified(f,p,'P3');before=snapshot(f)
        assert verify(f,p,'P3',row=old).status_code==409
    else:
        row=submitted(x)
        if mode=='old_receipt':
            old_hash=row['current_receipt']['source_sha256']
            row=ok(receipt_command(f,row,'REQUEST_CHANGES',expected_business_frontier=row['business_frontier']))
            row=ok(receipt_command(f,row,'SUBMIT',text='SYNTHETIC corrected strict Release receipt v2',expected_business_frontier=row['business_frontier']))
            before=snapshot(f)
            assert receipt_command(f,row,'ACKNOWLEDGE',receipt_sha256=old_hash,expected_business_frontier=row['business_frontier']).status_code==409
        elif mode=='stale_frontier':
            old_fence=row['business_frontier']
            row=ok(receipt_command(f,row,'REQUEST_CHANGES',expected_business_frontier=old_fence))
            row=ok(receipt_command(f,row,'SUBMIT',text='SYNTHETIC current corrected receipt',expected_business_frontier=row['business_frontier']))
            before=snapshot(f)
            assert receipt_command(f,row,'ACKNOWLEDGE',expected_business_frontier=old_fence).status_code==409
        elif mode in ('assignment_revoked','owner_revoked'):
            if mode=='assignment_revoked':
                f[1].assign_status('executor-a',UUID(p['run_id']),active=False)
                before=snapshot(f)
                assert receipt_command(f,row,'SUBMIT',expected_business_frontier=row['business_frontier']).status_code==403
            else:
                with f[1].connect() as c:
                    f[1].lock_principal(c,'fixture-a',exclusive=True)
                    c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
                before=snapshot(f)
                assert receipt_command(f,row,'ACKNOWLEDGE',expected_business_frontier=row['business_frontier']).status_code==403
        else:
            from parkweave import executor_receipts as receipts
            original=receipts._event
            def failed(*a,**kw):
                original(*a,**kw)
                raise RuntimeError('SYNTHETIC_STRICT_RECEIPT_EVENT_FAILURE')
            before=snapshot(f);key=uuid4().hex
            with monkeypatch.context() as m:
                m.setattr(receipts,'_event',failed)
                with pytest.raises(RuntimeError,match='SYNTHETIC_STRICT_RECEIPT_EVENT_FAILURE'):
                    receipt_command(f,row,'ACKNOWLEDGE',key=key,expected_business_frontier=row['business_frontier'])
            assert snapshot(f)==before
            ok(receipt_command(f,row,'ACKNOWLEDGE',key=key,expected_business_frontier=row['business_frontier']))
            assert case_history(f[1],x['t']['x']['p']['preparation_id'])==x['t']['old']
            return
    assert snapshot(f)==before
    assert case_history(f[1],x['t']['x']['p']['preparation_id'])==x['t']['old']
