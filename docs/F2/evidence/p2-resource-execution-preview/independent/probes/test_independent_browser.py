"""Own cold page oracles: never sent versus partial failed immutable result."""
from pathlib import Path
import json
from conftest import pg,fixture
from test_resource_execution_preview_browser import resource_page,open_page,lost,recovered
from test_isolated_execution_preview_browser import preview_page
from test_resource_execution_preview import preparation_fixture,read,snapshot,rp
PRIVATE_EVIDENCE=Path('/workspace/ParkWeave/.runtime/independent-p2-resource-execution-preview-review')
def note(name,data):(PRIVATE_EVIDENCE/(name+'-safe.json')).write_text(json.dumps(data,indent=2)+'\n')

def test_never_sent_p2_key_cold_original_page_is_only_get_not_auto_retry(resource_page):
 f,p,e,page,errors=resource_page;open_page(page,f,p);before=snapshot(f);posts=[];requests=[]
 def abort(route):
  if route.request.method!='POST':route.continue_();return
  posts.append(route.request.headers['idempotency-key']);route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/resource-execution-preview',abort)
 page.locator('#resource-execution-preview-run').click();page.wait_for_function('()=>resourceExecutionPreviewHandle!==null&&!resourceExecutionPreviewSubmitting&&document.getElementById("resource-execution-preview-error").textContent!==""');assert len(posts)==1
 storage=page.evaluate('JSON.stringify({...localStorage})');page.on('request',lambda r:requests.append(r.method));page.reload();open_page(page,f,p);page.wait_for_function('()=>resourceExecutionPreviewView?.status==="NOT_OBSERVED"')
 assert set(requests)=={'GET'} and len(posts)==1 and page.evaluate('resourceExecutionPreviewView.history.length')==0 and page.locator('#resource-execution-preview-run').is_disabled()
 assert page.evaluate('JSON.stringify({...localStorage})')==storage and read(f,p,posts[0]).json()['status']=='NOT_OBSERVED' and snapshot(f)==before and not errors
 note('page-never-sent',dict(actual_chromium=True,actual_http=True,status='NOT_OBSERVED',network_after_cold_reload=['GET'],server_post_count=0,automatic_retry=0,opaque_handle_retained=True,run_disabled=True,all_public_values_unchanged=True))

def test_actual_partial_failed_result_not_replaced_by_repaired_source_cold_320(resource_page):
 f,p,e,page,errors=resource_page;second=sorted(rp.RESOURCES,key=str)[1]
 with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET enabled=false WHERE id=%s',(second,))
 open_page(page,f,p);storage,posted=lost(page,f,p);old=posted['result'];assert old['state']=='FAILED' and len(old['artifact']['holds'])==1
 with f[1].connect() as c:c.execute("UPDATE synthetic_resources SET enabled=true,revision=revision+1,source=jsonb_set(source,'{revision}','\"cold-repaired-2\"') WHERE id=%s",(second,))
 before=snapshot(f);data=e.path.read_bytes();requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();open_page(page,f,p);recovered(page)
 assert page.evaluate('resourceExecutionPreviewView.result')==old and page.evaluate('resourceExecutionPreviewView.history[0].source_state')=='STALE' and set(requests)=={'GET'} and e.path.read_bytes()==data and snapshot(f)==before
 assert page.evaluate('JSON.stringify({...localStorage})')==storage and page.locator('#resource-execution-preview-run').is_disabled()
 page.set_viewport_size({'width':320,'height':1000});panel=page.locator('#resource-execution-preview-panel');panel.scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 text=page.locator('#resource-execution-preview-result').inner_text();assert 'FAILED' in text and 'STALE' in text and 'P3、P4、P5' in text and '外部正式成果' in text and 'PRIVATE_PREVIEW' not in text and f[2]['fixture-a'] not in text
 panel.screenshot(path=str(PRIVATE_EVIDENCE/'failed-history-320.png'));assert not errors
 note('page-failed-cold-stale',dict(actual_chromium=True,actual_http=True,actual_partial_holds=1,old_state='FAILED',old_failed_document_exact=True,current_source_changed_explicitly=True,source_state='STALE',network_after_cold_reload=['GET'],automatic_retry=0,sqlite_bytes_unchanged=True,all_public_values_unchanged=True,viewport=320,private_material_and_token_absent=True,complete_goals_retained=True,p3_to_p5_not_executed=True))
