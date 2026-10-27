"""Original page, loopback HTTP and isolated PostgreSQL; no mocked backend."""
import json
import hashlib
from pathlib import Path
import pytest
from test_material_text_pack_browser import browser_page
from test_preparation import preparation_fixture, command, add, create
from test_material_objections import ready, act, get, checked, body, post, url, SPECIALIST
from test_readiness import rows

OUT=Path(__file__).resolve().parents[1]/'docs/F2/evidence/material-objections'

def open_page(page,f,p,user='fixture-a'):
    page.locator('#token').fill(f[2][user]);page.locator('#token').dispatch_event('change')
    page.evaluate('async id=>{await loadPreparation(id)}',p['preparation_id'])
    page.wait_for_function('()=>objectionView!==null')

def submit(page,action,reason='SYNTHETIC explicit browser decision'):
    page.locator('#objection-reason').fill(reason)
    page.locator('#objection-raise' if action=='RAISE' else '[data-objection-action="'+action+'"]').click()
    page.wait_for_function('()=>!objectionPending&&!objectionBusy')


def test_http_pg_owner_specialist_review_three_widths(browser_page):
    f,page,_=browser_page;p=ready(f);open_page(page,f,p)
    submit(page,'RAISE','SYNTHETIC <script>window.objectionInjection=1</script> objection')
    v=checked(get(f,p));assert v['items'][0]['state']=='OPEN'
    assert not page.evaluate('Boolean(window.objectionInjection)')
    open_page(page,f,p,SPECIALIST);submit(page,'RESPOND','SYNTHETIC original specialist actual response')
    open_page(page,f,p);submit(page,'KEEP_OPEN','SYNTHETIC response insufficient')
    open_page(page,f,p,SPECIALIST);submit(page,'RESPOND','SYNTHETIC corrected actual response')
    open_page(page,f,p);submit(page,'ACCEPT_RESPONSE','SYNTHETIC owner explicit review')
    assert checked(get(f,p))['items'][0]['state']=='RESOLVED'
    shots=[];OUT.mkdir(parents=True,exist_ok=True)
    for width in (1200,390,320):
        page.set_viewport_size({'width':width,'height':900});page.locator('#objection-panel').scroll_into_view_if_needed()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        dest=OUT/('owner-reviewed-'+str(width)+'.png');page.screenshot(path=str(dest));shots.append(dict(file=dest.name,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
    (OUT/'browser-output.json').write_text(json.dumps(dict(scope='SYNTHETIC_MATERIAL_DELIVERY_OBJECTION',states=['OPEN','AWAITING_OWNER_REVIEW','OPEN','AWAITING_OWNER_REVIEW','RESOLVED'],http_pg_verified=True,screenshots=shots),indent=2)+'\n')


def lost_post(page,p):
    def lose(route):
        response=route.fetch();assert response.status==200
        route.abort('failed')
    page.route('**'+url(p),lambda r:lose(r) if r.request.method=='POST' else r.continue_())


def test_lost_reply_cold_reload_recovers_only_get_no_body_storage(browser_page):
    f,page,_=browser_page;p=ready(f);open_page(page,f,p);lost_post(page,p)
    page.locator('#objection-reason').fill('PRIVATE BODY must never be stored')
    page.locator('#objection-raise').click();page.wait_for_function('()=>objectionPending&&!objectionBusy')
    storage=page.evaluate('JSON.stringify({...localStorage})')
    assert 'PRIVATE BODY' not in storage and f[2]['fixture-a'] not in storage and 'binding_sha256' not in storage
    assert page.locator('#objection-raise').is_disabled() and page.locator('#prep-confirm').is_disabled()
    before=rows(f);page.reload();requests=[];page.on('request',lambda r:requests.append((r.method,r.url)))
    open_page(page,f,p)
    assert page.locator('#objection-recover').is_visible()
    page.locator('#objection-recover').click();page.wait_for_function('()=>!objectionPending&&!objectionBusy')
    assert all(method=='GET' for method,_ in requests) and rows(f)==before
    assert len(checked(get(f,p))['items'])==1 and page.locator('#objection-reason').input_value()==''


def test_unobserved_original_key_stays_locked_without_replay(browser_page):
    f,page,_=browser_page;p=ready(f);open_page(page,f,p)
    page.route('**'+url(p),lambda r:r.abort('failed') if r.request.method=='POST' else r.continue_())
    page.locator('#objection-reason').fill('SYNTHETIC request never reached server');page.locator('#objection-raise').click()
    page.wait_for_function('()=>objectionPending&&!objectionBusy');before=rows(f)
    page.locator('#objection-recover').click();page.wait_for_function('()=>!objectionBusy')
    assert page.locator('#objection-raise').is_disabled() and '尚未观察' in page.locator('#objection-error').inner_text()
    assert rows(f)==before


@pytest.mark.parametrize('target',['identity','case'])
def test_late_post_after_identity_or_case_switch_cannot_show_old_private_content(browser_page,target):
    f,page,_=browser_page;p=ready(f);open_page(page,f,p);held=[]
    def hold(route):held.append((route,route.fetch()))
    page.route('**'+url(p),lambda r:hold(r) if r.request.method=='POST' else r.continue_())
    page.locator('#objection-reason').fill('PRIVATE original case');page.locator('#objection-raise').click()
    for _ in range(100):
        page.wait_for_timeout(20)
        if held:break
    assert len(held)==1
    if target=='identity':
        other,_,_=create(f,user='fixture-b');open_page(page,f,other,'fixture-b')
    else:
        other,_,_=create(f);open_page(page,f,other)
    held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(150)
    assert page.evaluate('preparationId')==other['preparation_id']
    assert 'PRIVATE' not in page.locator('#objection-panel').inner_text() and page.locator('#objection-reason').input_value()==''
    assert checked(get(f,p))['items'][0]['state']=='OPEN'


@pytest.mark.parametrize('user',['fixture-a',SPECIALIST])
def test_http_revocation_clears_private_feedback_and_recovery_denies(browser_page,user):
    f,page,_=browser_page;p=ready(f);act(f,p,reason='PRIVATE objection');open_page(page,f,p,user)
    with f[1].connect() as c:
        f[1].lock_principal(c,user,exclusive=True);c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(user,))
    before=rows(f)
    page.evaluate('async()=>{await loadObjections(preparationContext)}')
    assert page.locator('#prep-detail').is_hidden() and 'PRIVATE' not in page.locator('#objection-panel').inner_text()
    assert page.evaluate('objectionView===null&&objectionPending===null') and rows(f)==before


def test_http_concurrent_material_version_change_refuses_stale_owner_decision(browser_page):
    f,page,_=browser_page;p=ready(f);act(f,p);response=act(f,p,'RESPOND',SPECIALIST);open_page(page,f,p)
    newer=checked(add(f,response,text='SYNTHETIC material changed while browser held old view'))
    before=rows(f);page.locator('#objection-reason').fill('SYNTHETIC stale review')
    page.locator('[data-objection-action="ACCEPT_RESPONSE"]').click()
    page.wait_for_function('()=>!objectionBusy&&!objectionPending')
    assert rows(f)==before and checked(get(f,p))['items'][0]['state']=='STALE'
    newer=checked(command(f,newer,'REVIEW',SPECIALIST,reason='SYNTHETIC new material independent review'))
    open_page(page,f,p);submit(page,'REBIND');assert checked(get(f,p))['items'][0]['state']=='OPEN'


def test_real_http_double_submit_has_one_immutable_event(browser_page):
    f,page,_=browser_page;p=ready(f);open_page(page,f,p)
    v=checked(get(f,p));d=body(v);before=rows(f)
    page.evaluate('''async ({id,body})=>{const key=crypto.randomUUID();const h={'Authorization':'Bearer '+document.querySelector('#token').value,'Content-Type':'application/json','Idempotency-Key':key};const send=()=>fetch('/api/preparations/'+id+'/material-objections',{method:'POST',headers:h,body:JSON.stringify(body)}).then(r=>r.json());window.duplicateReplies=await Promise.all([send(),send()]);}''',dict(id=p['preparation_id'],body=d))
    replies=page.evaluate('duplicateReplies');assert replies[0]==replies[1]
    assert len(checked(get(f,p))['items'][0]['history'])==1

@pytest.mark.parametrize('user,action',[('fixture-b','RAISE'),('fixture-c','RAISE'),(SPECIALIST,'RAISE'),('fixture-a','RESPOND')])
def test_actual_http_scope_and_role_negative_without_effect(browser_page,user,action):
    f,page,_=browser_page;p=ready(f);act(f,p);v=checked(get(f,p));before=rows(f)
    d=body(v,action,v['items'][0] if action!='RAISE' else None)
    r=page.request.post(page.url.rstrip('/')+url(p),headers={'Authorization':'Bearer '+f[2][user],'Idempotency-Key':__import__('uuid').uuid4().hex},data=d)
    assert r.status==403 and 'explicit feedback' not in r.text() and rows(f)==before


def test_owned_api_process_restart_recovers_committed_original_request(browser_page,tmp_path):
    import os, socket, subprocess, sys, time
    from parkweave.process_env import minimal_environment
    f,page,_=browser_page;p=ready(f)
    probe=socket.socket();probe.bind(('127.0.0.1',0));port=probe.getsockname()[1];probe.close()
    env=minimal_environment(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'),PARKWEAVE_DSN=f[0].dsn,PARKWEAVE_MODE='LOCAL')
    commands=[sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log']
    active=None;pids=[]
    with (tmp_path/'owned-api.log').open('wb') as log:
        def start():
            proc=subprocess.Popen(commands,env=env,stdout=log,stderr=log);pids.append(proc.pid)
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                assert proc.poll() is None,'owned API exited; private fixture log retained'
                try:
                    r=page.request.get('http://127.0.0.1:'+str(port)+'/health',timeout=300)
                    if r.ok and r.json()['process_id']==proc.pid:return proc
                except Exception:pass
                time.sleep(.05)
            proc.terminate();proc.wait(timeout=5);raise AssertionError('owned API startup deadline')
        try:
            active=start();page.goto('http://127.0.0.1:'+str(port)+'/');open_page(page,f,p);lost_post(page,p)
            page.locator('#objection-reason').fill('SYNTHETIC restart recovery');page.locator('#objection-raise').click()
            page.wait_for_function('()=>objectionPending&&!objectionBusy')
            before=rows(f);active.terminate();active.wait(timeout=5);active=None
            active=start();page.reload();open_page(page,f,p)
            requests=[];page.on('request',lambda r:requests.append(r.method))
            page.locator('#objection-recover').click();page.wait_for_function('()=>!objectionPending&&!objectionBusy')
            assert all(m=='GET' for m in requests) and rows(f)==before and pids[0]!=pids[1]
            (OUT/'api-restart.json').write_text(json.dumps(dict(cold_api_process_restart=True,different_process_ids=True,postgresql_history_retained=True,recovery_requests_all_get=True,duplicate_effects=0),indent=2)+'\n')
        finally:
            if active is not None and active.poll() is None:active.terminate();active.wait(timeout=5)

@pytest.mark.parametrize('target',['identity','case'])
def test_late_read_cannot_restore_other_identity_or_case_private_feedback(browser_page,target):
    f,page,_=browser_page;p=ready(f);act(f,p,reason='PRIVATE delayed ledger');open_page(page,f,p);held=[]
    def hold(route):
        if not held:held.append((route,route.fetch()))
        else:route.continue_()
    page.route('**'+url(p),hold)
    page.evaluate('window.objectionReadTask=loadObjections(preparationContext);void 0')
    for _ in range(100):
        page.wait_for_timeout(20)
        if held:break
    assert len(held)==1
    other,_,_=create(f,user='fixture-b' if target=='identity' else 'fixture-a')
    open_page(page,f,other,'fixture-b' if target=='identity' else 'fixture-a')
    held[0][0].fulfill(response=held[0][1]);page.evaluate('async()=>{await window.objectionReadTask}')
    assert page.evaluate('objectionView.preparation_id')==other['preparation_id']
    assert 'PRIVATE' not in page.locator('#objection-panel').inner_text()


def test_recovery_revoked_after_commit_preserves_minimal_original_handle(browser_page):
    f,page,_=browser_page;p=ready(f);open_page(page,f,p);lost_post(page,p)
    page.locator('#objection-reason').fill('PRIVATE committed before revocation');page.locator('#objection-raise').click()
    page.wait_for_function('()=>objectionPending&&!objectionBusy')
    storage=page.evaluate('JSON.stringify({...localStorage})')
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
    page.locator('#objection-recover').click();page.wait_for_function('()=>document.querySelector("#prep-detail").hidden')
    assert page.evaluate('JSON.stringify({...localStorage})')==storage
    assert 'PRIVATE' not in page.locator('#objection-panel').inner_text()


def test_corrupted_storage_handle_cannot_be_overwritten_or_send_another_write(browser_page):
    f,page,_=browser_page;p=ready(f);open_page(page,f,p)
    page.evaluate("id=>localStorage.setItem(objectionStorage+id+'.fixture-a','{bad json')",p['preparation_id'])
    before=rows(f);page.locator('#objection-reason').fill('SYNTHETIC blocked by unreadable handle');page.locator('#objection-raise').click()
    page.wait_for_function('()=>document.querySelector("#objection-error").textContent.length>0')
    assert rows(f)==before
    assert page.evaluate("id=>localStorage.getItem(objectionStorage+id+'.fixture-a')",p['preparation_id'])=='{bad json'
