"""Independent old-request context oracles on the actual original page."""
from pathlib import Path
from uuid import uuid4
import json
from conftest import pg,fixture
from test_preparation import preparation_fixture
from test_isolated_execution_preview_browser import preview_page,open_page,lost,recovered
from test_isolated_execution_preview import read,snapshot
from test_request_intents import save
PRIVATE_EVIDENCE=Path('/workspace/ParkWeave/.runtime/independent-isolated-execution-preview-v2-review')

def test_never_observed_original_key_cold_page_does_not_repeat_post(preview_page):
 f,p,e,page,errors=preview_page;open_page(page,f,p);before=snapshot(f);requests=[];posts=[]
 def never_send(route):
  if route.request.method!='POST':route.continue_();return
  posts.append(route.request.headers['idempotency-key']);route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/execution-preview',never_send)
 page.locator('#execution-preview-run').click();page.wait_for_function('()=>executionPreviewHandle!==null&&!executionPreviewSubmitting&&document.getElementById("execution-preview-error").textContent!==""')
 storage=page.evaluate('JSON.stringify({...localStorage})');assert len(posts)==1
 page.on('request',lambda r:requests.append(r.method));page.reload();open_page(page,f,p)
 page.wait_for_function('()=>executionPreviewView?.status==="NOT_OBSERVED"')
 assert requests and set(requests)=={'GET'} and len(posts)==1 and page.evaluate('executionPreviewView.history.length')==0
 assert page.locator('#execution-preview-run').is_disabled() and page.evaluate('JSON.stringify({...localStorage})')==storage
 assert read(f,p,posts[0]).json()['status']=='NOT_OBSERVED' and snapshot(f)==before and not errors
 (PRIVATE_EVIDENCE/'browser-never-observed-safe.json').write_text(json.dumps(dict(cold_actual_original_page=True,status='NOT_OBSERVED',network_after_reload=['GET'],server_post_count=0,automatic_retry_count=0,opaque_handle_kept=True,run_disabled=True,formal_values_unchanged=True),indent=2)+'\n')

def test_original_committed_goal_proof_kept_after_real_goal_change_cold_320(preview_page):
 f,p,e,page,errors=preview_page
 p={**p,'revision':save(f,p,goals=['LOCAL_CASE_RECORD_RECHECK','SYNTHETIC original mandatory goal']).json()['revision']}
 open_page(page,f,p);_,post=lost(page,f,p);original=post['result']
 p={**p,'revision':save(f,p,goals=['LOCAL_MATERIAL_PREPARATION','SYNTHETIC changed mandatory goal']).json()['revision']}
 before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();open_page(page,f,p);recovered(page)
 assert page.evaluate('executionPreviewView.result')==original and page.evaluate('executionPreviewView.history[0].source_state')=='STALE'
 assert original['required_goals']==['LOCAL_CASE_RECORD_RECHECK','SYNTHETIC original mandatory goal']
 assert original['not_previewed']==['P2','P3','P4','P5'] and set(requests)=={'GET'} and snapshot(f)==before
 page.set_viewport_size({'width':320,'height':900});page.locator('#execution-preview-panel').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 text=page.locator('#execution-preview-result').inner_text();assert 'original mandatory goal' in text and 'P2、P3、P4、P5' in text and 'changed mandatory goal' not in text and 'PRIVATE_PREVIEW' not in text and f[2]['fixture-a'] not in text
 page.locator('#execution-preview-panel').screenshot(path=str(PRIVATE_EVIDENCE/'independent-history-320.png'))
 assert not errors
 (PRIVATE_EVIDENCE/'browser-stale-original-goals-safe.json').write_text(json.dumps(dict(cold_actual_original_page=True,status='COMMITTED',source_state='STALE',full_old_goals_kept=2,other_steps_kept=['P2','P3','P4','P5'],network_after_reload=['GET'],viewport=320,private_material_and_token_absent=True,formal_values_unchanged=True,model_calls=0),indent=2)+'\n')
