"""P2 in the original page, real loopback HTTP/PG/Chromium, explicit recovery only."""
import json,os,socket,subprocess,sys,time
from pathlib import Path
from parkweave.process_env import minimal_environment
import pytest
from test_isolated_execution_preview_browser import preview_page,wait_held
OUT=Path('.runtime/p2-resource-execution-preview/browser')
from test_resource_execution_preview import preparation_fixture,setup,snapshot,read,execute,body,rc,rh


@pytest.fixture
def resource_page(preview_page,tmp_path):
    f,_,_,page,errors=preview_page;p,p1,e=setup(f,tmp_path);return f,p,e,page,errors


def open_page(page,f,p):
    page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('input')
    page.evaluate('(id)=>loadPlan(id)',p['preparation_id']);page.wait_for_function('()=>planView!==null')
    page.locator('#bounded-planning-read').click();page.wait_for_function('()=>resourceExecutionPreviewView!==null')
    assert page.locator('#resource-execution-preview-panel').is_visible()


def lost(page,f,p):
    posted=[]
    def lose(route):
        if route.request.method!='POST':route.continue_();return
        r=route.fetch();assert r.status==201;posted.append(dict(key=route.request.headers['idempotency-key'],result=r.json()['result']));route.abort('failed')
    page.route('**/api/preparations/'+p['preparation_id']+'/resource-execution-preview',lose)
    page.locator('#resource-execution-preview-run').click()
    page.wait_for_function('()=>resourceExecutionPreviewHandle!==null&&!resourceExecutionPreviewSubmitting&&document.getElementById("resource-execution-preview-error").textContent!==""')
    assert len(posted)==1
    storage=page.evaluate('JSON.stringify({...localStorage})')
    assert f[2]['fixture-a'] not in storage and 'PRIVATE_PREVIEW' not in storage
    rows=json.loads(page.evaluate('localStorage.getItem(resourceExecutionPreviewStorage)'))
    assert set(rows[0])=={'preparation','key','revision','source','expires'}
    return storage,posted[0]


def recovered(page):page.wait_for_function('()=>resourceExecutionPreviewView?.status==="COMMITTED"')


def test_original_page_lost_reply_cold_recovery_no_post_all_goals_three_widths(resource_page):
    f,p,e,page,errors=resource_page;open_page(page,f,p);before=snapshot(f);storage,post=lost(page,f,p);requests=[]
    page.on('request',lambda r:requests.append(r.method));page.reload();assert page.locator('#token').input_value()==''
    open_page(page,f,p);recovered(page)
    assert set(requests)=={'GET'} and page.evaluate('resourceExecutionPreviewView.result')==post['result'] and snapshot(f)==before
    assert page.evaluate('JSON.stringify({...localStorage})')==storage
    text=page.locator('#resource-execution-preview-result').inner_text()
    assert 'P3、P4、P5' in text and '外部正式成果' in text and 'SNAPSHOT_MATCH' in text and '正式Case/资源/Approval/通知写入0' in text
    assert 'PRIVATE_PREVIEW' not in text and page.locator('#resource-execution-preview-run').is_disabled()
    for width in (1200,390,320):
        page.set_viewport_size({'width':width,'height':1000});page.locator('#resource-execution-preview-panel').scroll_into_view_if_needed()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.locator('#resource-execution-preview-release').click();page.wait_for_function('()=>resourceExecutionPreviewHandle===null&&resourceExecutionPreviewView!==null')
    assert page.evaluate('JSON.stringify({...localStorage})')=='{}' and set(requests)=={'GET'} and snapshot(f)==before and not errors


@pytest.mark.parametrize('target',['case','identity','draft'])
def test_late_response_cannot_restore_changed_context(resource_page,tmp_path,target):
    f,p,e,page,errors=resource_page;open_page(page,f,p);other,_,_=setup(f,tmp_path);held=[]
    def hold(route):
        if route.request.method!='POST':route.continue_();return
        r=route.fetch();assert r.status==201;held.append((route,r))
    page.route('**/api/preparations/'+p['preparation_id']+'/resource-execution-preview',hold)
    page.locator('#resource-execution-preview-run').click();wait_held(page,held)
    if target=='case':open_page(page,f,other)
    elif target=='identity':page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input')
    else:page.locator('#request-current').fill('SYNTHETIC NEW DRAFT');page.locator('#request-current').dispatch_event('input')
    page.locator('#resource-execution-preview-result').evaluate('(e)=>e.textContent="SYNTHETIC NEW CONTEXT"');before=snapshot(f)
    held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(150)
    assert page.locator('#resource-execution-preview-result').inner_text()=='SYNTHETIC NEW CONTEXT' and snapshot(f)==before and not errors


def test_resource_revocation_on_unknown_clears_private_view_retains_only_opaque_handle(resource_page):
    f,p,e,page,errors=resource_page;open_page(page,f,p);storage,_=lost(page,f,p)
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND resource_id=%s AND capability='HOLD'",(rh.RESOURCE_ID,))
    before=snapshot(f);page.locator('#resource-execution-preview-recover').click();page.wait_for_function('()=>resourceExecutionPreviewView===null&&planView===null')
    assert page.locator('#resource-execution-preview-panel').is_hidden() and page.locator('#resource-execution-preview-result').inner_text()==''
    assert page.evaluate('JSON.stringify({...localStorage})')==storage and snapshot(f)==before and not errors


def test_owned_new_api_pid_recovers_original_artifact_without_reissuing_permissions(resource_page,tmp_path):
 f,p,e,page,errors=resource_page
 factory=tmp_path/'preview_factory.py';factory.write_text('import os\nfrom parkweave.api import create_app\nfrom parkweave.store import Store\nfrom parkweave.resource_execution_preview import ResourceExecutionPreview\ndef app():\n s=Store(os.environ["PARKWEAVE_DSN"])\n ResourceExecutionPreview(s,os.environ["PARKWEAVE_PREVIEW_ROOT"],enabled_for_synthetic_preview=True).attach_store(s)\n return create_app(s)\n')
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PARKWEAVE_PREVIEW_ROOT=str(e.root),PYTHONPATH=os.pathsep.join([str(tmp_path),str(Path.cwd()/'src')]))
 cmd=[sys.executable,'-m','uvicorn','preview_factory:app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log'];pids=[];active=None
 with (tmp_path/'owned-preview-api.log').open('w') as log:
  def start():
   proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=log);pids.append(proc.pid);end=time.monotonic()+10
   while proc.poll() is None and time.monotonic()<end:
    try:
     r=page.request.get(f'http://127.0.0.1:{port}/health',timeout=500)
     if r.ok and r.json()['process_id']==proc.pid:return proc
    except Exception:pass
    time.sleep(.05)
   proc.terminate();proc.wait(5);raise AssertionError('owned preview API readiness deadline')
  try:
   active=start();page.goto(f'http://127.0.0.1:{port}/');open_page(page,f,p);storage,post=lost(page,f,p);before=snapshot(f);active.terminate();active.wait(5);active=None;active=start();assert pids[0]!=pids[1]
   page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));open_page(page,f,p);recovered(page)
   assert page.evaluate('resourceExecutionPreviewView.result')==post['result'] and snapshot(f)==before and set(requests)=={'GET'} and page.evaluate('JSON.stringify({...localStorage})')==storage and not errors
   OUT.mkdir(parents=True,exist_ok=True);(OUT/'actual-api-restart.json').write_text(json.dumps(dict(different_api_pids=pids,actual_http=True,same_postgresql=True,original_namespace=True,original_artifact_hash=True,original_key_get_only=True,no_permission_reissued=True,formal_writes=0,model_calls=0),indent=2)+'\n')
  finally:
   if active is not None and active.poll() is None:active.terminate();active.wait(5)
