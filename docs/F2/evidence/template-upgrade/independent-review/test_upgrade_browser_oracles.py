"""Independent real HTTP/PG/Chromium unknown and late generation oracles."""
from pathlib import Path
import json,threading
import pytest
from conftest import pg, fixture
from playwright.sync_api import sync_playwright
from test_template_upgrade import (upgrade_case,link_fixture,receipt_fixture,preparation_fixture,instance,publication,
    check,choose,snapshot,headers)
from test_template_upgrade_browser import server,open_page

OUT=Path('/workspace/ParkWeave/.runtime/independent-template-upgrade-fixed-review/browser-oracles')

def save(name,data):
    OUT.mkdir(parents=True,exist_ok=True);(OUT/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')

def count_events(u):
    with u['repository'].connect() as c:return c.execute('SELECT count(*) FROM upgrade_events').fetchone()[0]

def browser(pw,width=1200):
    return pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])

@pytest.mark.parametrize('width',[320,1200])
def test_actual_inflight_not_observed_hot_and_cold_get_only_then_late_commit(upgrade_case,monkeypatch,width):
    u=upgrade_case;row,_=instance(u);publication(u);before=snapshot(u);release=threading.Event();entered=threading.Event()
    original=u['checker'].select
    def hold(*args):
        entered.set();assert release.wait(10);return original(*args)
    with server(u) as base,sync_playwright() as pw:
        b=browser(pw);page=b.new_page(viewport={'width':width,'height':900});requests=[]
        try:
            open_page(page,base,u,row);monkeypatch.setattr(u['checker'],'select',hold)
            page.on('request',lambda r:requests.append((r.method,r.url)))
            page.evaluate('''()=>{const actual=fetch;window.lateStatus=null;window.fetch=(...args)=>{
                if(String(args[0]).endsWith('/choices')){actual(...args).then(r=>window.lateStatus=r.status);return Promise.reject(new TypeError('SYNTHETIC response unknown'));}
                return actual(...args);};}''')
            page.locator('#reason').fill('SYNTHETIC independent explicit decision');page.locator('[data-choice="KEEP_CURRENT"]').click()
            page.wait_for_function('()=>pending!==null&&!busy&&document.querySelector("#error").textContent.includes("未知")')
            assert entered.wait(1);key=page.locator('#key').input_value()
            page.locator('#recover').click();page.wait_for_function('()=>!busy&&document.querySelector("#receipt").textContent.includes("NOT_OBSERVED")')
            assert page.evaluate('pending!==null') and page.locator('#key').is_disabled()
            assert page.locator('#check').is_disabled() and page.locator('[data-choice="KEEP_CURRENT"]').is_disabled()
            assert count_events(u)==0 and snapshot(u)==before
            cold=b.new_page(viewport={'width':width,'height':900});cold_requests=[];cold.on('request',lambda r:cold_requests.append((r.method,r.url)))
            cold.goto(base+'/template-upgrade');assert cold.locator('#token').input_value()==''
            cold.locator('#token').fill(u['f'][2]['fixture-a']);cold.locator('#instance').fill(row['instance_id']);cold.locator('#key').fill(key)
            cold.locator('#recover').click();cold.wait_for_function('()=>!busy&&document.querySelector("#receipt").textContent.includes("NOT_OBSERVED")')
            assert cold.locator('[data-choice="KEEP_CURRENT"]').is_disabled() and count_events(u)==0
            release.set();page.wait_for_function('()=>window.lateStatus===200')
            cold.locator('#recover').click();cold.wait_for_function('()=>!busy&&document.querySelector("#receipt").textContent.includes("COMMITTED")')
            assert count_events(u)==1 and snapshot(u)==before
            assert sum(m=='POST' and url.endswith('/choices') for m,url in requests)==1
            assert all(m=='GET' for m,url in cold_requests)
            assert cold.evaluate('JSON.stringify({...localStorage})')=='{}' and cold.evaluate('JSON.stringify({...sessionStorage})')=='{}'
            assert cold.evaluate('document.documentElement.scrollWidth<=innerWidth')
            save('late-unknown-'+str(width),dict(width=width,actual_http=True,pg=True,chromium=True,
                 not_observed_before_actual_late_commit=True,choice_posts=1,cold_all_get=True,audit_events=1,business_unchanged=True))
            cold.screenshot(path=str(OUT/('cold-get-'+str(width)+'.png')))
        finally:release.set();b.close()

@pytest.mark.parametrize('kind',['check','recovery'])
def test_late_old_get_cannot_clear_new_case_inspection(upgrade_case,kind):
    u=upgrade_case;row,_=instance(u);r2,_=instance(u);target=publication(u);key='independent-original-recovery'
    x=check(u,row,target).json();assert choose(u,row,x,key=key).status_code==200;before=snapshot(u)
    with server(u) as base,sync_playwright() as pw:
        b=browser(pw);page=b.new_page()
        try:
            open_page(page,base,u,row)
            page.evaluate('''kind=>{const actual=fetch;window.delayed=null;window.arrived=false;window.held=false;window.fetch=async(...args)=>{
              const r=await actual(...args);if(!window.held&&String(args[0]).includes(kind==='check'?'/check?':'/requests/')){window.held=true;window.arrived=true;await new Promise(resolve=>window.delayed=resolve);}return r;};}''',kind)
            if kind=='check':page.locator('#check').click()
            else:page.locator('#key').fill(key);page.locator('#recover').click()
            page.wait_for_function('()=>window.arrived')
            page.locator('#instance').fill(r2['instance_id']);page.locator('#catalog').click();page.wait_for_function('()=>document.querySelector("#target").options.length===1&&!busy')
            page.locator('#check').click();page.wait_for_function('()=>inspection!==null&&!busy')
            expected=page.evaluate('JSON.stringify(inspection)');result=page.locator('#result').inner_text();receipt=page.locator('#receipt').inner_text()
            page.evaluate('()=>window.delayed()');page.wait_for_timeout(150)
            assert page.evaluate('JSON.stringify(inspection)')==expected and page.evaluate('inspection.check.scope.instance_id')==r2['instance_id']
            assert page.locator('#result').inner_text()==result and page.locator('#receipt').inner_text()==receipt
            assert snapshot(u)==before
        finally:b.close()

@pytest.mark.parametrize('scope',['identity','instance'])
def test_late_committed_post_does_not_replace_new_context(upgrade_case,scope):
    u=upgrade_case;row,_=instance(u);r2,_=instance(u);publication(u);before=snapshot(u)
    with server(u) as base,sync_playwright() as pw:
        b=browser(pw);page=b.new_page()
        try:
            open_page(page,base,u,row)
            page.evaluate('''()=>{const actual=fetch;window.delayed=null;window.arrived=false;window.fetch=async(...args)=>{
              const r=await actual(...args);if(String(args[0]).endsWith('/choices')){window.arrived=true;await new Promise(resolve=>window.delayed=resolve);}return r;};}''')
            page.locator('#reason').fill('SYNTHETIC PRIVATE_LATE_ORIGINAL_REASON');page.locator('[data-choice="KEEP_CURRENT"]').click();page.wait_for_function('()=>window.arrived')
            assert count_events(u)==1
            if scope=='identity':
                page.locator('#token').fill(u['f'][2]['fixture-b']);expected=None
            else:
                page.locator('#instance').fill(r2['instance_id']);page.locator('#catalog').click();page.wait_for_function('()=>document.querySelector("#target").options.length===1&&!busy')
                page.locator('#check').click();page.wait_for_function('()=>inspection!==null&&!busy');expected=page.evaluate('JSON.stringify(inspection)')
            current_receipt=page.locator('#receipt').inner_text();page.evaluate('()=>window.delayed()');page.wait_for_timeout(150)
            assert page.locator('#receipt').inner_text()==current_receipt
            assert 'PRIVATE_LATE_ORIGINAL_REASON' not in page.locator('body').inner_text()
            assert page.evaluate('inspection===null') if expected is None else page.evaluate('JSON.stringify(inspection)')==expected
            assert snapshot(u)==before and count_events(u)==1
        finally:b.close()

def test_revoked_unknown_get_clears_private_view_without_post_or_business_change(upgrade_case):
    u=upgrade_case;row,_=instance(u);publication(u)
    with server(u) as base,sync_playwright() as pw:
        b=browser(pw);page=b.new_page()
        try:
            open_page(page,base,u,row)
            def lose(route):
                response=route.fetch();assert response.status==200;route.abort('failed')
            page.route('**/api/template-upgrade/*/choices',lose)
            page.locator('#reason').fill('SYNTHETIC PRIVATE_REVOKED_REASON');page.locator('[data-choice="KEEP_CURRENT"]').click()
            page.wait_for_function('()=>pending!==null&&!busy')
            with u['f'][1].connect() as c:
                u['f'][1].lock_principal(c,'fixture-a',exclusive=True)
                c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
            before=snapshot(u);requests=[];page.on('request',lambda r:requests.append(r.method))
            page.locator('#recover').click();page.wait_for_function('()=>!busy&&document.querySelector("#error").textContent.includes("无权")')
            assert page.locator('#receipt').inner_text()=='' and page.locator('#result').inner_text()=='' and page.locator('#reason').input_value()==''
            assert 'PRIVATE_REVOKED_REASON' not in page.locator('body').inner_text() and set(requests)=={'GET'}
            assert snapshot(u)==before and count_events(u)==1
        finally:b.close()
