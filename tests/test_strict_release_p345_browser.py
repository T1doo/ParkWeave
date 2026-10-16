"""Real Chromium P2 -> P3-P5; earlier strict Release/P2 are explicit API fixtures."""
import json,os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from playwright.sync_api import sync_playwright
from release_p345_support import (strict_p2,release_case,cancel33_case,capability_resource_catalog,
    capability_catalog,preparation_fixture,receipt_fixture,ok)
from test_new_enterprise_local_chain import actual_http
from test_new_enterprise_local_chain_browser import verify_page
from test_preparation import headers
from service_release_acceptance_support import case_history
OUT=Path(os.environ.get('STRICT_P345_ARTIFACT_ROOT','.runtime/release-p345-root/browser'))


def test_actual_chromium_new_strict_release_offer_accept_manual_receipt_close_verify_outputs(strict_p2):
    x=strict_p2;t=x['t'];p=x['p'];f=x['f'];calls=[];errors=[];contexts=[];result=None
    with actual_http(t['app']) as (api,python_requests),sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        base=str(api.base_url).rstrip('/')
        def open_role(actor):
            ctx=browser.new_context();contexts.append(ctx);page=ctx.new_page()
            def requested(r):calls.append(dict(actor=actor,method=r.method,path=urlsplit(r.url).path,
                request_key=r.header_value('idempotency-key'),body=r.post_data_json if r.method=='POST' else None))
            page.on('request',requested);page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'/');assert page.evaluate('localStorage.length')==0
            page.locator('#token').fill(f[2][actor]);page.locator('#token').dispatch_event('change')
            page.locator('[data-tab="collaboration"]').click()
            return page
        try:
            owner=open_role('fixture-a');reviewer=open_role('prep-specialist-fixture-a');executor=open_role('executor-a')
            reviewer.evaluate('(id)=>loadDispatch(id)',p['preparation_id']);reviewer.wait_for_function('()=>dispatchView!==null')
            reviewer.locator('#dispatch-executor').select_option('executor-a')
            reviewer.locator('#dispatch-offer-reason').fill('SYNTHETIC explicitly offer new strict Release responsibility')
            reviewer.locator('#dispatch-offer-button').click();reviewer.wait_for_function('()=>dispatchView?.current_offer?.state==="OFFERED"&&!dispatchPending')
            executor.evaluate('(id)=>loadDispatch(id)',p['preparation_id']);executor.wait_for_function('()=>dispatchView!==null')
            executor.locator('#dispatch-decision-reason').fill('SYNTHETIC assigned executor explicitly ACCEPT new Case')
            executor.locator('#dispatch-accept').click();executor.wait_for_function('()=>dispatchView?.current_offer?.state==="ACCEPTED"&&!dispatchPending')
            dispatch=executor.evaluate('dispatchView')
            assert dispatch['dispatch_id']!=t['x']['accepted']['dispatch_id']
            verify_page(owner,p,'P3')
            executor.locator('#dispatch-receipt').click();executor.wait_for_function('()=>receiptView!==null')
            executor.locator('#receipt-text').fill('SYNTHETIC manual actual local receipt for independent strict Release Case')
            executor.locator('#receipt-source').fill('SYNTHETIC executor current manual work log')
            with executor.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path.endswith('/commands')) as submitted:
                executor.locator('#receipt-submit-button').click()
            assert submitted.value.status==200,submitted.value.text()
            executor.wait_for_function('()=>receiptView?.step.state==="RECEIPT_RECORDED"')
            owner.evaluate('(id)=>loadReceipt(id)',dispatch['receipt_step_id']);owner.wait_for_function('()=>receiptView!==null')
            owner.locator('#receipt-reason').fill('SYNTHETIC owner acknowledges current new Case manual receipt hash')
            owner.locator('#receipt-ack').click();owner.wait_for_function('()=>receiptView?.step.state==="LOCAL_ACKNOWLEDGED"')
            verify_page(owner,p,'P4')
            owner.evaluate('(id)=>loadLocalCase(id)',p['preparation_id']);owner.wait_for_function('()=>localCaseView!==null')
            owner.locator('#local-case-reason').fill('SYNTHETIC explicit current independent local REVALIDATE')
            owner.locator('#local-case-validate').click();owner.wait_for_function('()=>localCaseView?.local_record_state==="READY"&&!localCaseRecoveryBusy&&localCaseHandles().length===0')
            # Explicit new GET, then use its new revision/hash/frontier for CLOSE.
            before=len(calls)
            with owner.expect_response(lambda r:r.request.method=='GET' and urlsplit(r.url).path.endswith('/local-case')) as refreshed:
                owner.locator('#local-case-refresh').click()
            assert refreshed.value.status==200
            fresh_local=refreshed.value.json()
            owner.wait_for_function('()=>localCaseView?.local_record_state==="READY"&&!localCaseRecoveryBusy')
            owner.locator('#local-case-reason').fill('SYNTHETIC explicitly CLOSE_LOCAL_RECORD only after fresh GET')
            owner.locator('#local-case-close').click();owner.wait_for_function('()=>localCaseView?.local_record_state==="LOCAL_RECORD_CLOSED"&&!localCaseRecoveryBusy&&localCaseHandles().length===0')
            assert any(c['method']=='GET' and c['path'].endswith('/local-case') for c in calls[before:])
            verify_page(owner,p,'P5')
            assert owner.evaluate('servicePlanView.steps.every(s=>s.state==="VERIFIED")')
            # Fresh role context reads actual current proof, not prior in-memory DTOs.
            cold=open_role('fixture-a');before=len(calls)
            cold.evaluate('(id)=>loadServiceCasePlan(id)',p['preparation_id']);cold.wait_for_function('()=>servicePlanView!==null')
            cold.locator('#goal-results-read').click();cold.wait_for_function('()=>goalResultView!==null')
            result=cold.evaluate('goalResultView')
            assert result['state']=='LOCAL_OUTPUTS_VERIFIED' and len(result['results'])==6 and not result['case_goal_completed']
            assert cold.locator('[data-goal-state="LOCAL_OUTPUT_VERIFIED"]').count()==6
            assert all(c['method']=='GET' for c in calls[before:])
            cold.locator('[data-tab="collaboration"]').click()
            with cold.expect_response(lambda r:urlsplit(r.url).path=='/api/cases/worklist') as work:
                cold.locator('#case-worklist-read').click()
            assert work.value.status==200
            assert next(i for i in work.value.json()['items'] if i['case_id']==p['case_id'])['attention']=='LOCAL_CLOSED'
            assert case_history(f[1],t['x']['p']['preparation_id'])==t['old']
            with f[1].connect() as c:
                parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
            from parkweave.service_selection_candidates import find
            saved=find(parent,parent['service_case_plan']['candidate_consumption']['candidate_id'])
            assert {r['release_id'] for r in saved['selection']['selections']}=={r['release_id'] for r,i in x['refs']}
            posts=[c for c in calls if c['method']=='POST'];assert len(posts)==9,posts
            fences=[c['body']['expected_business_frontier'] for c in posts if 'expected_business_frontier' in c['body']]
            assert len(fences)==6 and all(v['preparation_id']==p['preparation_id'] for v in fences)
            assert all(a['epoch']<b['epoch'] for a,b in zip(fences,fences[1:]))
            checks=[c for c in posts if c['body'].get('action')=='VERIFY']
            assert len(checks)==3 and [c['body']['expected_revision'] for c in checks]==sorted(set(c['body']['expected_revision'] for c in checks))
            assert all(len(c['body']['expected_source_sha256'])==64 for c in checks)
            assert all(any(r['method']=='GET' and r['path'].endswith('/command-recovery') and r['request_key']==c['request_key'] for r in calls) for c in checks)
            close=next(c['body'] for c in posts if c['body'].get('action')=='CLOSE_LOCAL_RECORD')
            assert close['expected_revision']==fresh_local['revision']
            assert close['expected_snapshot_sha256']==fresh_local['current_snapshot_sha256']
            assert close['expected_business_frontier']==fresh_local['business_frontier']
            assert all(t['x']['p']['preparation_id'] not in c['path'] for c in posts)
            assert not errors,errors
        finally:
            OUT.mkdir(parents=True,exist_ok=True)
            (OUT/('strict-p345-'+uuid4().hex[:10]+'.json')).write_text(json.dumps(dict(
                actual_browser='INSTALLED_CHROMIUM',browser_version=browser.version,actual_html_http_asgi_owned_pg=True,
                browser_scope='P2 initial state -> offer/ACCEPT -> VERIFY P3 -> manual SUBMIT/ACK -> VERIFY P4 -> REVALIDATE/fresh GET/CLOSE -> VERIFY P5 -> cold six outputs/worklist',
                fixture_scope='strict revision publication/catalog retirement/register/bind/new inputs/assignment/material REVIEW+CONFIRM/ADOPT/P1/approval/resource delivery/P2 before browser',
                calls=calls,python_requests=python_requests,result=result,page_errors=errors,real_model_calls=0,
                no_generic_dispatch_receipt_key_get=True,case_goal_completed=False),indent=2)+'\n')
            for ctx in contexts:ctx.close()
            browser.close()
