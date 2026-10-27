"""Actual owned tracked-frontier PG; isolated fixture approval never normal authority."""
from uuid import uuid4
from frontier_fixture_support import (frontier_case,capability_resource_catalog,capability_catalog,
                                      receipt_fixture,preparation_fixture)
from test_frontier_p4_race import awaiting_receipt
from test_executor_receipts import act
from test_receipt_submit_recovery import recover
from test_dispatch_recovery import records


def test_original_manual_fingerprint_uses_saved_frontier_after_epoch_moves(frontier_case):
    x=frontier_case;f=x['f'];_,_,row=awaiting_receipt(x);key=uuid4().hex
    result=act(f,row,'SUBMIT',key=key,expected_business_frontier=row['business_frontier'])
    assert result.status_code==200,result.text
    first=result.json();assert first['business_frontier']!=row['business_frontier']
    result=act(f,first,'ACKNOWLEDGE',expected_business_frontier=first['business_frontier'])
    assert result.status_code==200,result.text
    assert result.json()['business_frontier']!=first['business_frontier']
    before=records(f);r=recover(f,row,key);assert r.status_code==200,r.text
    assert r.json()['status']=='COMMITTED' and r.json()['event']['receipt_id']==first['current_receipt']['id']
    assert records(f)==before
