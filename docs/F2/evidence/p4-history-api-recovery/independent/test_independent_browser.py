"""Original read-only page: exact request correlation, cold client, late context."""
from pathlib import Path
from uuid import uuid4
import json
import pytest
from playwright.sync_api import sync_playwright
from test_independent_api import issuer,api_process,get,business,bytes_all,note,PRIVATE,helper
from parkweave.store import Store
from parkweave import preparation as prep

def fill(page,d,key=None):
 page.locator('#token').fill(d['tokens']['fixture-a']);page.locator('#receipt-history-preparation').fill(d['preparation']['preparation_id']);page.locator('#receipt-history-key').fill(key or d['key']);page.locator('#receipt-history-read').click();page.wait_for_function('()=>!document.getElementById("receipt-history-read").disabled')

@pytest.mark.parametrize('issuer',['REQUEST_CHANGES'],indirect=True)
def test_wrong_key_legitimate_history_response_is_not_claimed_for_unknown_request(issuer):
 base,d,authority,case=issuer;before=business(d);saved=bytes_all(d);unknown='independent-never-sent'
 with api_process(issuer) as (client,api,port,network),sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   assert get(client,d,unknown).json()['status']=='NOT_OBSERVED'
   def other_original_request(route):
    # Actual loopback GET for another existing request; no forged body/hash/proof.
    response=route.fetch(url=route.request.url.rsplit('/',1)[0]+'/'+d['key']);assert response.status==200 and response.json()['result']['request_key']==d['key']!=unknown;route.fulfill(response=response)
   page.route('**/receipt-execution-history/recovery/'+unknown,other_original_request);page.goto(f'http://127.0.0.1:{port}/');fill(page,d,unknown)
   rendered=page.locator('#receipt-history-result').inner_text();error=page.locator('#receipt-history-error').inner_text();page.set_viewport_size({'width':320,'height':1000});page.locator('#receipt-history-panel').screenshot(path=str(PRIVATE/'wrong-key-response-320.png'))
   note(case,'wrong-key-response-observation',dict(actual_http=True,actual_chromium=True,requested_unknown_key=unknown,server_unknown_key='NOT_OBSERVED',actual_other_key_response=True,body_or_proof_fabrication=False,current_input_remains_unknown=page.locator('#receipt-history-key').input_value()==unknown,other_saved_report_rendered=bool(rendered),safe_error_present=bool(error),only_recovery_get=True,formal_business_and_five_logs_unchanged=business(d)==before and bytes_all(d)==saved))
   assert rendered=='' and error and not errors,'another original request result must not be claimed for unknown current key'
  finally:context.close();browser.close()
 assert business(d)==before and bytes_all(d)==saved

@pytest.mark.parametrize('issuer',['REQUEST_CHANGES'],indirect=True)
def test_cold_different_api_pid_same_live_issuer_exact_old_changes_after_source_version(issuer):
 base,d,authority,case=issuer;errors=[];requests=[]
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.method))
  try:
   with api_process(issuer) as (client,old,port,_):page.goto(f'http://127.0.0.1:{port}/');fill(page,d);assert 'CHANGES_REQUESTED' in page.locator('#receipt-history-result').inner_text()
   assert not Path('/proc',str(old.pid)).exists() and authority.poll() is None
   p=d['preparation'];prep.command(Store(d['app_dsn']),d['tokens']['fixture-a'],p['preparation_id'],uuid4().hex,prep.PreparationCommand(action='ADD_EVIDENCE',expected_revision=p['revision'],slot='need_summary',text='SYNTHETIC independent cold history material version2',source_kind='USER_STATEMENT',source_label='SYNTHETIC independent version2'))
   before=business(d);saved=bytes_all(d);requests.clear()
   with api_process(issuer,port) as (client,new,_,_):
    assert len({old.pid,new.pid,authority.pid})==3;page.reload();assert page.locator('#token').input_value()=='';fill(page,d)
    text=page.locator('#receipt-history-result').inner_text();assert all(x in text for x in ('CHANGES_REQUESTED','STALE','尚未核对','元数据报告','未消费','P5','Case未完成')) and d['result']['artifact']['p4_receipts'][0]['adapter_execution']['report']['execution_id'] in text
    assert get(client,d,d['key']).json()['result']==d['result'] and set(requests)=={'GET'} and not errors and d['tokens']['fixture-a'] not in page.evaluate('JSON.stringify({...localStorage})')
    for width in (1200,390,320):
     page.set_viewport_size({'width':width,'height':1000});panel=page.locator('#receipt-history-panel');panel.scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');panel.screenshot(path=str(PRIVATE/('changes-stale-'+str(width)+'.png')))
   assert business(d)==before and bytes_all(d)==saved
   note(case,'independent-cold-page',dict(old_api_pid=old.pid,new_api_pid=new.pid,issuer_pid=authority.pid,old_api_gone_before_new=True,issuer_alive=True,source_state='STALE',decision='REQUEST_CHANGES',original_result_execution_id_exact=True,network_after_api_client_replacement=['GET'],no_automatic_execution=True,five_logs_and_formal_business_unchanged=True,viewports=[1200,390,320],sensitive_storage_absent=True))
  finally:context.close();browser.close()

@pytest.mark.parametrize('target',['key','preparation'])
def test_late_reply_after_original_request_context_changed_cannot_restore_view(issuer,target):
 base,d,authority,case=issuer
 with api_process(issuer) as (client,api,port,_),sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();held=[];errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   page.goto(f'http://127.0.0.1:{port}/');fill(page,d);assert page.locator('#receipt-history-result').inner_text()
   def hold(route):held.append((route,route.fetch()))
   page.route('**/receipt-execution-history/recovery/*',hold);page.locator('#receipt-history-read').click()
   for _ in range(200):
    if held:break
    page.wait_for_timeout(20)
   assert held
   page.locator('#receipt-history-'+target).fill('independent-new-key' if target=='key' else str(uuid4()));before=business(d);saved=bytes_all(d);held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(150)
   assert page.locator('#receipt-history-result').inner_text()=='' and business(d)==before and bytes_all(d)==saved and not errors
   note(case,'late-'+target,dict(actual_http=True,actual_chromium=True,changed_original_request_context=target,late_result_rendered=False,formal_business_and_five_logs_unchanged=True))
  finally:context.close();browser.close()


def test_same_original_history_document_object_key_order_is_not_a_value_change(issuer):
 base,d,authority,case=issuer;before=business(d);saved=bytes_all(d)
 with api_process(issuer) as (client,api,port,_),sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   def reorder(value):
    if isinstance(value,dict):return {k:reorder(value[k]) for k in reversed(list(value))}
    if isinstance(value,list):return [reorder(x) for x in value]
    return value
   def ordered(route):
    response=route.fetch();assert response.status==200;view=response.json();original=view['result'];view['history'][0]['document']=reorder(view['history'][0]['document']);assert view['history'][0]['document']==original
    route.fulfill(status=200,content_type='application/json',body=json.dumps(view))
   page.route('**/receipt-execution-history/recovery/*',ordered);page.goto(f'http://127.0.0.1:{port}/');fill(page,d)
   assert d['result']['artifact']['p4_receipts'][0]['adapter_execution']['report']['execution_id'] in page.locator('#receipt-history-result').inner_text() and page.locator('#receipt-history-error').inner_text()=='' and not errors
   assert business(d)==before and bytes_all(d)==saved
   note(case,'object-key-order',dict(actual_http=True,actual_chromium=True,original_history_document_value_types_and_array_order_unchanged=True,only_object_key_order_changed=True,body_hash_proof_values_unchanged=True,legal_exact_request_result_rendered=True,five_log_bytes_and_formal_business_unchanged=True))
  finally:context.close();browser.close()

@pytest.mark.parametrize('fault',['duplicate_same_history','unknown_status','not_observed_with_result'])
def test_correlated_read_only_metadata_fault_keeps_private_view_empty(issuer,fault):
 base,d,authority,case=issuer;before=business(d);saved=bytes_all(d)
 with api_process(issuer) as (client,api,port,_),sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   def invalid(route):
    response=route.fetch();assert response.status==200;view=response.json()
    if fault=='duplicate_same_history':view['history'].append(view['history'][0])
    elif fault=='unknown_status':view['status']='SYNTHETIC_UNKNOWN_STATUS'
    else:view['status']='NOT_OBSERVED'
    # Original document, report, hash and proof values stay untouched.
    route.fulfill(status=200,content_type='application/json',body=json.dumps(view))
   page.route('**/receipt-execution-history/recovery/*',invalid);page.goto(f'http://127.0.0.1:{port}/');fill(page,d)
   assert page.locator('#receipt-history-result').inner_text()=='' and page.locator('#receipt-history-error').inner_text() and not errors
   assert business(d)==before and bytes_all(d)==saved
   note(case,'read-only-metadata-'+fault,dict(actual_http=True,actual_chromium=True,fault=fault,original_document_report_hash_proof_values_untouched=True,private_result_not_rendered=True,safe_error_present=True,automatic_replay=False,five_log_bytes_and_formal_business_unchanged=True))
  finally:context.close();browser.close()
