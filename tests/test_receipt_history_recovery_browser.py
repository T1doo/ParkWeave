"""Original page through two genuinely separate API PIDs and one live issuer."""
import json
from pathlib import Path
from uuid import uuid4
import pytest
from playwright.sync_api import sync_playwright
from parkweave.store import Store
from parkweave import preparation as prep
from test_receipt_history_recovery import issuer,api_process,get,business,bytes_all,note
OUT=Path('.runtime/p4-history-api-recovery/browser')

def fill(page,d):
    page.locator('#token').fill(d['tokens']['fixture-a'])
    page.locator('#receipt-history-preparation').fill(d['preparation']['preparation_id'])
    page.locator('#receipt-history-key').fill(d['key'])
    page.locator('#receipt-history-read').click()
    page.wait_for_function('()=>!document.getElementById("receipt-history-read").disabled')


@pytest.mark.parametrize('reply',['different_key','reordered_history_keys'])
def test_original_page_rejects_other_saved_key_for_unknown_request(issuer,reply):
    _,d,_,case=issuer;before=business(d);saved=bytes_all(d);unknown='never-sent' if reply=='different_key' else d['key']
    with api_process(issuer) as (client,_,port,_),sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            assert get(client,d,unknown).json()['status']==('NOT_OBSERVED' if reply=='different_key' else 'COMMITTED')
            def other_key(route):
                response=route.fetch(url=route.request.url.rsplit('/',1)[0]+'/'+d['key'])
                assert response.status==200 and response.json()['result']==d['result']
                if reply=='different_key':route.fulfill(response=response)
                else:
                    view=response.json();view['history'][0]['document']=dict(reversed(list(view['history'][0]['document'].items())))
                    route.fulfill(status=response.status,json=view)
            page.route('**/receipt-execution-history/recovery/'+unknown,other_key);page.goto(f'http://127.0.0.1:{port}/');fill(page,{**d,'key':unknown})
            if reply=='different_key':assert page.locator('#receipt-history-result').inner_text()=='' and '编号' in page.locator('#receipt-history-error').inner_text()
            else:assert page.locator('#receipt-history-result').inner_text() and page.locator('#receipt-history-error').inner_text()==''
            assert not errors
            assert page.locator('#receipt-history-key').input_value()==unknown and bytes_all(d)==saved and business(d)==before
            note(case,'response-correlation-page',dict(actual_chromium=True,response_fault=reply,no_forged_body_or_proof=True,wrong_key_rejected=reply=='different_key',same_document_reordered_object_keys_accepted=reply=='reordered_history_keys',five_logs_and_business_unchanged=True))
        finally:context.close();browser.close()

@pytest.mark.parametrize('issuer',['REQUEST_CHANGES'],indirect=True)
def test_original_page_cold_get_after_old_api_pid_exits(issuer):
    _,d,authority,case=issuer;errors=[];requests=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();page.on('pageerror',lambda x:errors.append(str(x)));page.on('request',lambda r:requests.append(r.method))
        try:
            with api_process(issuer) as (client,old,port,_):
                page.goto(f'http://127.0.0.1:{port}/');fill(page,d);assert 'CHANGES_REQUESTED' in page.locator('#receipt-history-result').inner_text()
            assert old.poll() is not None and not Path('/proc',str(old.pid)).exists()
            p=d['preparation'];prep.command(Store(d['app_dsn']),d['tokens']['fixture-a'],p['preparation_id'],uuid4().hex,prep.PreparationCommand(action='ADD_EVIDENCE',expected_revision=p['revision'],slot='need_summary',text='SYNTHETIC browser new material',source_kind='USER_STATEMENT',source_label='SYNTHETIC version2'))
            saved=bytes_all(d);before=business(d);requests.clear()
            with api_process(issuer,port) as (client,new,_,_):
                page.reload();assert page.locator('#token').input_value()=='';fill(page,d)
                text=page.locator('#receipt-history-result').inner_text();assert all(x in text for x in ['CHANGES_REQUESTED','STALE','尚未核对','P5','Case未完成','元数据报告','未消费','正式业务写入0'])
                assert d['result']['artifact']['p4_receipts'][0]['adapter_execution']['report']['execution_id'] in text
                assert get(client,d,d['key']).json()['result']==d['result']
                assert set(requests)=={'GET'} and not errors and 'PRIVATE_PREVIEW' not in text and d['tokens']['fixture-a'] not in page.evaluate('JSON.stringify({...localStorage})')
                OUT.mkdir(parents=True,exist_ok=True)
                for width in (1200,390,320):
                    page.set_viewport_size({'width':width,'height':1000});page.locator('#receipt-history-panel').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.locator('#receipt-history-panel').screenshot(path=str(OUT/('changes-stale-'+str(width)+'.png')))
            assert business(d)==before and bytes_all(d)==saved
            note(case,'cross-pid-page',dict(old_api_pid=old.pid,new_api_pid=new.pid,issuer_pid=authority.pid,old_pid_confirmed_gone_before_new=True,actual_chromium=True,cold_requests=['GET'],source_state='STALE',p4_state='CHANGES_REQUESTED',exact_report_and_decision_preserved=True,viewports=[1200,390,320],sensitive_storage_absent=True,all_log_bytes_and_business_unchanged=True))
        finally:context.close();browser.close()


def test_original_page_current_revoke_and_late_identity_clear(issuer):
    _,d,_,case=issuer;errors=[]
    with api_process(issuer) as (client,_,port,_),sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();page.on('pageerror',lambda x:errors.append(str(x)))
        try:
            page.goto(f'http://127.0.0.1:{port}/');fill(page,d);assert page.locator('#receipt-history-result').inner_text()
            held=[]
            def hold(route):response=route.fetch();held.append((route,response))
            page.route('**/receipt-execution-history/recovery/*',hold);page.locator('#receipt-history-read').click()
            for _ in range(200):
                if held:break
                page.wait_for_timeout(20)
            assert held;page.locator('#token').fill(d['tokens']['fixture-b']);held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(100)
            assert page.locator('#receipt-history-result').inner_text()==''
            page.unroute('**/receipt-execution-history/recovery/*',hold)
            with Store(d['owner_dsn']).connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
            saved=bytes_all(d);before=business(d);fill(page,d);assert '不可读' in page.locator('#receipt-history-error').inner_text() and page.locator('#receipt-history-result').inner_text()==''
            assert business(d)==before and bytes_all(d)==saved and not errors
        finally:context.close();browser.close()
