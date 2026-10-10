"""Original page recovery after explicit changes decision, never auto ACK."""
from pathlib import Path
import json
from conftest import pg,fixture
from test_receipt_execution_preview_browser import receipt_page,receipt_preview_fixture,access_fixture,receipt_fixture,preparation_fixture,open_page,recovered
from test_receipt_execution_preview import snapshot,read
from test_isolated_execution_preview import add
PRIVATE=Path('/workspace/ParkWeave/.runtime/independent-p4-receipt-execution-preview-review')
def note(name,data):(PRIVATE/(name+'-safe.json')).write_text(json.dumps(data,indent=2)+'\n')

def test_explicit_changes_lost_reply_then_source_change_cold_get_never_ack(receipt_page):
 f,p,e,page,errors,a=receipt_page;open_page(page,f,p);page.locator('#receipt-execution-preview-decision').select_option('REQUEST_CHANGES');posted=[]
 def lose(route):
  if route.request.method!='POST':route.continue_();return
  response=route.fetch();assert response.status==201;posted.append(dict(key=route.request.headers['idempotency-key'],result=response.json()['result']));route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/receipt-execution-preview',lose);page.locator('#receipt-execution-preview-run').click();page.wait_for_function('()=>receiptExecutionPreviewHandle!==null&&!receiptExecutionPreviewSubmitting&&document.getElementById("receipt-execution-preview-error").textContent!==""');assert len(posted)==1
 old=posted[0]['result'];assert old['review_decision']=='REQUEST_CHANGES' and old['artifact']['p4_state']=='CHANGES_REQUESTED' and old['artifact']['local_current_at_execution'] is False
 assert [x['action'] for x in old['artifact']['p4_events']]==['CREATE','SUBMIT','REQUEST_CHANGES'] and len(old['artifact']['p4_receipts'])==1
 storage=page.evaluate('JSON.stringify({...localStorage})');handle=json.loads(page.evaluate('localStorage.getItem(receiptExecutionPreviewStorage)'));assert len(handle)==1 and set(handle[0])=={'preparation','key','revision','source','expires'} and f[2]['fixture-a'] not in storage
 p=add(f,p,text='SYNTHETIC independent original material newer than changes request').json();before=snapshot(f);data=e.path.read_bytes();requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();assert page.locator('#token').input_value()=='';open_page(page,f,p);recovered(page)
 assert page.evaluate('receiptExecutionPreviewView.result')==old and page.evaluate('receiptExecutionPreviewView.history[0].source_state')=='STALE' and set(requests)=={'GET'} and len(posted)==1 and e.path.read_bytes()==data and snapshot(f)==before
 assert page.locator('#receipt-execution-preview-run').is_disabled() and page.locator('#receipt-execution-preview-decision').is_disabled() and page.evaluate('JSON.stringify({...localStorage})')==storage
 panel=page.locator('#receipt-execution-preview-panel');text=page.locator('#receipt-execution-preview-result').inner_text();assert all(x in text for x in ('CHANGES_REQUESTED','尚未核对','STALE','P5','外部正式成果','材料服务交付')) and f[2]['fixture-a'] not in text and 'PRIVATE_PREVIEW' not in text
 for width in (1200,390,320):
  page.set_viewport_size({'width':width,'height':1000});panel.scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');panel.screenshot(path=str(PRIVATE/('changes-stale-'+str(width)+'.png')))
 assert not errors
 note('page-changes-stale',dict(actual_http=True,actual_chromium=True,explicit_review_decision='REQUEST_CHANGES',old_state='CHANGES_REQUESTED',receipt_versions=1,event_actions=['CREATE','SUBMIT','REQUEST_CHANGES'],cold_network=['GET'],old_document_exact=True,new_original_material_source='STALE',auto_ack_or_regenerate=0,sqlite_and_public_business_unchanged=True,opaque_fields=5,viewports=[1200,390,320],token_private_material_absent=True))

def test_never_sent_cold_page_and_unknown_original_key_only_get(receipt_page):
 f,p,e,page,errors,a=receipt_page;open_page(page,f,p);before=snapshot(f);posts=[]
 def cancel(route):
  if route.request.method!='POST':route.continue_();return
  posts.append(route.request.headers['idempotency-key']);route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/receipt-execution-preview',cancel);page.locator('#receipt-execution-preview-run').click();page.wait_for_function('()=>receiptExecutionPreviewHandle!==null&&!receiptExecutionPreviewSubmitting&&document.getElementById("receipt-execution-preview-error").textContent!==""');assert len(posts)==1
 storage=page.evaluate('JSON.stringify({...localStorage})');requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();open_page(page,f,p);page.wait_for_function('()=>receiptExecutionPreviewView?.status==="NOT_OBSERVED"')
 assert set(requests)=={'GET'} and page.evaluate('receiptExecutionPreviewView.history.length')==0 and page.locator('#receipt-execution-preview-run').is_disabled() and page.evaluate('JSON.stringify({...localStorage})')==storage
 assert read(f,p,posts[0]).json()['status']=='NOT_OBSERVED' and snapshot(f)==before and not errors
 note('page-never-sent',dict(actual_http=True,actual_chromium=True,server_post_count=0,browser_post_attempts=1,status='NOT_OBSERVED',cold_network=['GET'],automatic_retry=0,opaque_handle_kept=True,formal_business_unchanged=True))
