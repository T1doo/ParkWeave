"""Actual original page: opaque never-sent and immutable declined history."""
from pathlib import Path
import json
from conftest import pg,fixture
from test_dispatch_execution_preview_browser import dispatch_page,open_page,lost,recovered
from test_isolated_execution_preview_browser import preview_page
from test_dispatch_execution_preview import preparation_fixture,read,snapshot,add
PRIVATE_EVIDENCE=Path('/workspace/ParkWeave/.runtime/independent-p3-dispatch-execution-preview-review')
def note(name,data):(PRIVATE_EVIDENCE/(name+'-safe.json')).write_text(json.dumps(data,indent=2)+'\n')

def test_never_sent_original_p3_key_cold_reload_does_not_auto_offer_or_accept(dispatch_page):
 f,p,e,page,errors=dispatch_page;open_page(page,f,p);before=snapshot(f);posts=[];requests=[]
 def stop(route):
  if route.request.method!='POST':route.continue_();return
  posts.append(route.request.headers['idempotency-key']);route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/dispatch-execution-preview',stop);page.locator('#dispatch-execution-preview-run').click();page.wait_for_function('()=>dispatchExecutionPreviewHandle!==null&&!dispatchExecutionPreviewSubmitting&&document.getElementById("dispatch-execution-preview-error").textContent!==""');assert len(posts)==1
 storage=page.evaluate('JSON.stringify({...localStorage})');page.on('request',lambda r:requests.append(r.method));page.reload();open_page(page,f,p);page.wait_for_function('()=>dispatchExecutionPreviewView?.status==="NOT_OBSERVED"')
 assert set(requests)=={'GET'} and len(posts)==1 and page.evaluate('dispatchExecutionPreviewView.history.length')==0 and page.locator('#dispatch-execution-preview-run').is_disabled()
 assert page.evaluate('JSON.stringify({...localStorage})')==storage and read(f,p,posts[0]).json()['status']=='NOT_OBSERVED' and snapshot(f)==before and not errors
 note('page-never-sent',dict(actual_http=True,actual_chromium=True,status='NOT_OBSERVED',server_post_count=0,network_after_cold_reload=['GET'],automatic_offer_or_accept=0,opaque_handle_retained=True,all_public_values_unchanged=True))

def test_decline_stays_declined_after_material_change_and_cold_page_get_320(dispatch_page):
 f,p,e,page,errors=dispatch_page;open_page(page,f,p);page.locator('#dispatch-execution-preview-decision').select_option('DECLINE');storage,posted=lost(page,f,p);old=posted['result'];assert old['decision']=='DECLINE' and old['artifact']['p3_state']=='DECLINED' and old['artifact']['steps']==[]
 p=add(f,p,text='SYNTHETIC independent new original material version').json();before=snapshot(f);data=e.path.read_bytes();requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();open_page(page,f,p);recovered(page)
 assert page.evaluate('dispatchExecutionPreviewView.result')==old and page.evaluate('dispatchExecutionPreviewView.history[0].source_state')=='STALE' and set(requests)=={'GET'} and e.path.read_bytes()==data and snapshot(f)==before
 assert page.evaluate('JSON.stringify({...localStorage})')==storage and page.locator('#dispatch-execution-preview-run').is_disabled()
 page.set_viewport_size({'width':320,'height':1000});panel=page.locator('#dispatch-execution-preview-panel');panel.scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 text=page.locator('#dispatch-execution-preview-result').inner_text();assert 'DECLINED' in text and 'STALE' in text and '尚未接单' in text and 'P4、P5' in text and '外部正式成果' in text and 'PRIVATE_PREVIEW' not in text and f[2]['fixture-a'] not in text
 panel.screenshot(path=str(PRIVATE_EVIDENCE/'declined-stale-320.png'));assert not errors
 note('page-declined-cold-stale',dict(actual_http=True,actual_chromium=True,explicit_decision='DECLINE',old_decision_state='DECLINED',receipt_steps=0,current_material_version_changed_by_original_command=True,source_state='STALE',old_document_exact=True,network_after_cold_reload=['GET'],automatic_new_accept=0,sqlite_bytes_unchanged=True,all_public_values_unchanged_by_preview=True,opaque_handle_retained=True,full_goals_retained=True,not_executed=['P4','P5'],viewport=320,token_and_private_material_absent=True))
