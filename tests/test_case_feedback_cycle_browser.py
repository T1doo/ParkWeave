"""Continue the original ordinary DOM Case through feedback, close and cycle2.

Initial exact synthetic assignment is the existing installation fixture. All
later business writes are ordinary controls, including the original P1-P5 chain.
"""
import hashlib
import json

import pytest
from playwright.sync_api import expect
from test_local_synthetic_demo import demo_inputs,preparation_fixture,receipt_fixture
from test_assigned_demo_chain_browser import run_existing_assigned_chain
from test_demo_original_page_intake_browser import open_from_list,open_service_plan,verify,settled
from service_release_acceptance_support import case_history


def receipt(page,goal):
    page.locator('[data-tab="collaboration"]').click();page.locator('#receipt-list').click()
    item=page.locator('#receipt-items button').filter(has_text=goal);expect(item).to_have_count(1)
    item.click();expect(page.locator('#receipt-detail')).to_be_visible()


def receipt_decision(page,action,state):
    page.locator('#receipt-reason').fill('SYNTHETIC original owner '+action)
    page.locator({'REOPEN':'#receipt-reopen','REQUEST_CHANGES':'#receipt-correct','ACKNOWLEDGE':'#receipt-ack'}[action]).click()
    page.wait_for_function('(s)=>receiptView?.step.state===s',arg=state);settled(page)
    return page.evaluate('receiptView')


def submit(page,text,version):
    page.locator('#receipt-refresh').click();page.wait_for_function('()=>receiptContext!==null')
    page.locator('#receipt-text').fill(text);page.locator('#receipt-source').fill('SYNTHETIC corrected manual work record v'+str(version))
    page.locator('#receipt-submit-button').click()
    page.wait_for_function('(v)=>receiptView?.current_receipt?.version===v&&!receiptSubmitBusy&&!receiptSubmitStoredPending()',arg=version)
    settled(page);return page.evaluate('receiptView')


def local(page,goal,action,state):
    open_from_list(page,goal);page.locator('#local-case-prepare').click()
    expect(page.locator('#local-case-detail')).to_be_visible()
    page.locator('#local-case-reason').fill('SYNTHETIC owner explicitly '+action)
    page.locator({'REVALIDATE':'#local-case-validate','CLOSE_LOCAL_RECORD':'#local-case-close','REOPEN':'#local-case-reopen'}[action]).click()
    page.wait_for_function('(s)=>localCaseView?.local_record_state===s&&!localCaseRecoveryBusy&&localCaseHandles()?.length===0',arg=state)
    settled(page);view=page.evaluate('localCaseView');assert not view['case_goal_completed'];return view


def results(page,goal):
    open_from_list(page,goal);open_service_plan(page);page.locator('#goal-results-read').click()
    page.wait_for_function('()=>goalResultView!==null');return page.evaluate('goalResultView')


def feedback_close_reopen(f,parent,owner,reviewer,executor,initial,tmp_path):
    goal='SYNTHETIC资料准备';before=case_history(f[1],parent['preparation_id']);phases=[]
    def keep(label,view):
        phases.append(dict(label=label,view=view))
        (tmp_path/'feedback-cycle-phases.json').write_text(json.dumps(phases,ensure_ascii=False,indent=2)+'\n')
    receipt(owner,goal);original=owner.evaluate('receiptView');step_id=original['step']['id']
    assert original['step']['state']=='LOCAL_ACKNOWLEDGED'
    expect(owner.locator('#receipt-correct')).to_be_disabled()
    keep('owner-reopens-original-ack',receipt_decision(owner,'REOPEN','AWAITING_RECEIPT'))
    stale=results(owner,goal);keep('P4-invalid-after-reopen',stale)
    assert next(x for x in stale['results'] if x['adapter_id']=='P4')['state']=='NEEDS_RECHECK'
    second=submit(executor,'SYNTHETIC original executor first response to delivery feedback',2)
    assert second['step']['id']==step_id;keep('original-executor-second-version',second)
    receipt(owner,goal);keep('owner-requests-specific-correction',receipt_decision(owner,'REQUEST_CHANGES','CHANGES_REQUESTED'))
    third=submit(executor,'SYNTHETIC original executor corrected response to owner feedback',3)
    assert third['step']['id']==step_id;keep('original-executor-third-version',third)
    receipt(owner,goal);ack=receipt_decision(owner,'ACKNOWLEDGE','LOCAL_ACKNOWLEDGED');keep('owner-checks-corrected-third-version',ack)
    open_from_list(owner,goal);verify(owner,'P4')
    keep('new-current-cycle1-revalidation',local(owner,goal,'REVALIDATE','READY'))
    open_from_list(owner,goal);verify(owner,'P5')
    current=results(owner,goal);assert current['state']=='LOCAL_OUTPUTS_VERIFIED';keep('corrected-six-local-outputs',current)
    p4=next(x['actual_output'] for x in current['results'] if x['adapter_id']=='P4')
    assert p4['receipt_step_id']==step_id and p4['receipt_id']==third['current_receipt']['id']
    assert p4['receipt_version']==3 and p4['receipt_sha256']==third['current_receipt']['source_sha256']
    assert p4['kind']=='MANUAL_SYNTHETIC_TEXT_ACKNOWLEDGEMENT' and p4['execution_id'] is None
    closed=local(owner,goal,'CLOSE_LOCAL_RECORD','LOCAL_RECORD_CLOSED');keep('explicit-local-close',closed)
    assert closed['cycle']==1 and closed['case_state']=='WAITING_CONFIRMATION'
    after_close=results(owner,goal);keep('closed-record-needs-new-P5-proof',after_close)
    assert next(x for x in after_close['results'] if x['adapter_id']=='P5')['state']=='NEEDS_RECHECK'
    opened=local(owner,goal,'REOPEN','REOPENED');keep('explicit-cycle2-reopen',opened)
    assert opened['cycle']==2 and opened['case_state']=='REOPENED'
    assert opened['verified_snapshot_sha256'] is None and not opened['can_close_local_record']
    cycle2=local(owner,goal,'REVALIDATE','READY');keep('explicit-cycle2-current-revalidation',cycle2)
    open_from_list(owner,goal);verify(owner,'P5')
    final=results(owner,goal);keep('cycle2-six-local-outputs',final)
    assert final['state']=='LOCAL_OUTPUTS_VERIFIED' and len(final['results'])==6 and not final['case_goal_completed']
    assert final['case_id']==initial['case_id'] and final['run_id']==initial['run_id'] and final['plan_id']==initial['plan_id']
    p5=next(x['actual_output'] for x in final['results'] if x['adapter_id']=='P5')
    assert p5['cycle']==2 and p5['source_sha256']==cycle2['verified_snapshot_sha256']
    after=case_history(f[1],parent['preparation_id'])
    for table in ('preparation_evidence','preparation_events','service_dispatch_events','service_step_receipts','service_receipt_events','case_local_events'):
        assert all(row in after[table] for row in before[table]),table
    for table in ('synthetic_resource_holds','resource_case_claims','case_resource_links','service_dispatch_offers'):
        assert after[table]==before[table],table
    revalidation=next(e for e in after['case_local_events'] if str(e['id'])==p5['revalidation_event_id'])
    assert revalidation['action']=='REVALIDATE' and revalidation['cycle']==2
    owner_id=before['preparations'][0]['owner_id']
    executor_id=next(row['executor_id'] for row in after['service_receipt_steps'] if str(row['id'])==step_id)
    ledger=next(row for row in after['case_local_lifecycles'] if str(row['preparation_id'])==parent['preparation_id'])
    assert revalidation['actor_id']==owner_id and revalidation['snapshot']==ledger['verified_snapshot']
    local_sha=hashlib.sha256(json.dumps({'cycle':2,'sources':revalidation['snapshot']},
        sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    assert local_sha==ledger['verified_sha256']==p5['source_sha256']
    assert revalidation['payload']['verified_snapshot_sha256']==p5['source_sha256']
    assert [e['action'] for e in sorted(after['case_local_events'],key=lambda e:e['revision'])]==[
        'REVALIDATE','REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN','REVALIDATE']
    assert sorted(r['version'] for r in after['service_step_receipts'])==[1,2,3]
    submit_events=[e for e in after['service_receipt_events'] if e['action']=='SUBMIT' and e['payload'].get('receipt_id')==p4['receipt_id']]
    ack_events=[e for e in after['service_receipt_events'] if e['action']=='ACKNOWLEDGE' and e['payload'].get('receipt_id')==p4['receipt_id']]
    assert len(submit_events)==len(ack_events)==1
    assert str(submit_events[0]['id']) in p4['submit_event_ids'] and str(ack_events[0]['id']) in p4['ack_event_ids']
    assert submit_events[0]['actor_id']==executor_id and ack_events[0]['actor_id']==owner_id
    assert submit_events[0]['revision']<ack_events[0]['revision']
    assert submit_events[0]['payload']['receipt_sha256']==ack_events[0]['payload']['receipt_sha256']==p4['receipt_sha256']
    assert owner.evaluate('document.documentElement.scrollWidth<=innerWidth')
    owner.screenshot(path=str(tmp_path/'cycle2-revalidated.png'))
    return final


@pytest.mark.parametrize('width',[1200,320])
def test_original_ordinary_DOM_same_case_feedback_close_reopen_and_cold_read(demo_inputs,tmp_path,width):
    run_existing_assigned_chain(demo_inputs,tmp_path,width,continuation=feedback_close_reopen)
