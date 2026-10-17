"""Actual file chooser -> ordinary API -> original material workflow -> download.

All files/identities are synthetic fixtures; source/import metadata is never a
real-business authority proof. API/worker setup precedes the browser workflow.
"""
import hashlib
from pathlib import Path
import time
import pytest
from playwright.sync_api import sync_playwright,expect

from test_preparation import preparation_fixture,create
from test_native_preparation_entry import snapshot
from test_native_preparation_entry_browser import ordinary_process


def browser_page(pw):
    b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    context=b.new_context(accept_downloads=True);return b,context,context.new_page()


def open_record(page,api,f,p,actor='fixture-a'):
    page.goto(str(api.base_url)+'?preparation_id='+p['preparation_id'])
    page.locator('#token').fill(f[2][actor]);page.locator('#existing-preparation-read').click()
    expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录')


def select_file(page,name,raw):
    page.locator('#material-file-input').set_input_files({'name':name,'mimeType':'application/octet-stream','buffer':raw})
    page.locator('#material-file-synthetic').check();page.locator('#material-file-read').click()
    expect(page.locator('#material-file-status')).to_contain_text('已整理候选全文')
    return page.locator('#material-file-text').input_value()


def save_candidate(page,slot):
    page.locator('#prep-slot').select_option(slot);page.locator('#material-file-use').click()
    expect(page.locator('#material-file-status')).to_contain_text('已填入原表单，尚未保存')
    page.locator('#prep-evidence button').click()


@pytest.mark.parametrize('formats',['txt-csv','md-json'])
def test_file_to_original_review_confirmation_actual_download_and_process_restart(preparation_fixture,tmp_path,formats):
    f=preparation_fixture;p,_,_=create(f)
    first=(('SYNTHETIC-request.txt','SYNTHETIC imported request 中文\r\n第二行'.encode()) if formats=='txt-csv' else ('SYNTHETIC-request.md',b'# SYNTHETIC imported request\n<script>window.fileImportInjection=true</script>'))
    second=(('SYNTHETIC-outline.csv',b'material,source\r\nSYNTHETIC-outline,user-statement\r\n') if formats=='txt-csv' else ('SYNTHETIC-outline.json',b'{"material":"SYNTHETIC-outline","source":"user-statement"}'))
    with f[1].connect() as c:grants_before=c.execute('SELECT to_jsonb(t) r FROM preparation_grants t ORDER BY principal_id,capability').fetchall()
    with ordinary_process(f,tmp_path/'first') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);errors=[];page.on('pageerror',lambda e:errors.append(str(e)));open_record(page,api,f,p)
        before=snapshot(f[1]);text=select_file(page,*first);assert snapshot(f[1])==before
        assert not page.evaluate('Boolean(window.fileImportInjection)')
        page.locator('#prep-text').fill('SYNTHETIC existing manual candidate');page.locator('#prep-source-label').fill('SYNTHETIC manual source')
        page.locator('#material-file-use').click();expect(page.locator('#material-file-status')).to_contain_text('不会覆盖你的内容')
        assert page.locator('#prep-text').input_value()=='SYNTHETIC existing manual candidate'
        page.locator('#prep-text').fill('');page.locator('#prep-source-label').fill('')
        lost=[]
        if formats=='md-json':
            def lose_after_commit(route):
                if lost:route.continue_();return
                lost.append(route.fetch());route.abort('failed')
            page.route('**/api/preparations/*/commands',lose_after_commit)
        save_candidate(page,'need_summary')
        if formats=='md-json':
            expect(page.locator('#prep-command-retry')).to_be_visible()
            assert lost and lost[0].status==200
            page.locator('#prep-command-retry').click()
        expect(page.locator('#prep-materials')).to_contain_text('SYNTHETIC imported request')
        assert page.locator('#material-file-input').input_value()==''
        text2=select_file(page,*second);save_candidate(page,'material_outline')
        expect(page.locator('#prep-materials')).to_contain_text('SYNTHETIC-outline')
        assert not page.evaluate('Boolean(window.fileImportInjection)')
        with f[1].connect() as c:
            materials=c.execute('SELECT text,source_label,source_sha256,authenticity FROM preparation_evidence WHERE preparation_id=%s ORDER BY slot',(p['preparation_id'],)).fetchall()
            assert {m['text'] for m in materials}=={text,text2}
            assert all(m['authenticity']=='UNVERIFIED' and m['source_sha256']==hashlib.sha256(m['text'].encode()).hexdigest() for m in materials)
            assert len(materials)==2
        open_record(page,api,f,p,'prep-specialist-fixture-a');expect(page.locator('#material-file-panel')).to_be_hidden()
        page.locator('#prep-reason').fill('SYNTHETIC specialist checks both imported material versions');page.locator('#prep-review').click()
        expect(page.locator('#prep-summary')).to_contain_text('待企业确认')
        open_record(page,api,f,p);page.locator('#prep-reason').fill('SYNTHETIC owner explicitly confirms current imported material pack');page.locator('#prep-confirm').click()
        expect(page.locator('#prep-summary')).to_contain_text('本地资料准备已确认')
        page.locator('#material-pack-generate').click();expect(page.locator('#material-pack-status')).to_contain_text('已生成当前读取快照')
        packed=page.locator('#material-pack-text').input_value();assert 'SYNTHETIC imported request' in packed and 'SYNTHETIC-outline' in packed and 'Case目标未完成' in packed
        with page.expect_download() as got:page.locator('#material-pack-download').click()
        downloaded=got.value;payload=Path(downloaded.path()).read_bytes();assert payload==packed.encode()
        (tmp_path/'actual-downloaded-material-pack.txt').write_bytes(payload)
        for width in (1200,390,320):
            page.set_viewport_size({'width':width,'height':900});page.locator('#material-pack-panel').scroll_into_view_if_needed()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(tmp_path/('material-file-flow-'+str(width)+'.png')))
        assert not errors;context.close();b.close()
    before_restart=snapshot(f[1])
    with ordinary_process(f,tmp_path/'restarted') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);seen=[];page.on('request',lambda r:seen.append(r.method));open_record(page,api,f,p)
        expect(page.locator('#prep-materials')).to_contain_text('SYNTHETIC-outline')
        expect(page.locator('#material-file-output')).to_be_hidden();assert page.locator('#material-file-input').input_value()==''
        page.locator('#material-pack-generate').click();expect(page.locator('#material-pack-status')).to_contain_text('已生成当前读取快照')
        assert page.locator('#material-pack-text').input_value()==packed
        assert all(method=='GET' for method in seen) and snapshot(f[1])==before_restart;context.close();b.close()
    with f[1].connect() as c:
        assert c.execute('SELECT state FROM cases WHERE id=%s',(p['case_id'],)).fetchone()['state']=='NEEDS_INPUT'
        assert c.execute("SELECT count(*) n FROM preparation_events WHERE preparation_id=%s AND action='ADD_EVIDENCE'",(p['preparation_id'],)).fetchone()['n']==2
        assert c.execute('SELECT to_jsonb(t) r FROM preparation_grants t ORDER BY principal_id,capability').fetchall()==grants_before


@pytest.mark.parametrize('late_status',[200,403])
def test_late_old_file_response_cannot_replace_new_file_candidate_or_clear_it(preparation_fixture,tmp_path,late_status):
    f=preparation_fixture;p,_,_=create(f);before=snapshot(f[1])
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p);pending=[]
        def hold(route):
            if pending:route.continue_();return
            pending.append((route,route.fetch()))
        page.route('**/material-file-candidate',hold)
        page.locator('#material-file-input').set_input_files({'name':'SYNTHETIC-old.txt','mimeType':'text/plain','buffer':b'SYNTHETIC old file private text'})
        page.locator('#material-file-synthetic').check();page.locator('#material-file-read').click()
        until=time.monotonic()+5
        while not pending and time.monotonic()<until:page.wait_for_timeout(20)
        assert pending
        text=select_file(page,'SYNTHETIC-new.json',b'{"note":"SYNTHETIC current new file"}')
        route,response=pending[0]
        if late_status==200:route.fulfill(response=response)
        else:route.fulfill(status=403,json={'detail':'record unavailable or authorization denied'})
        page.wait_for_timeout(150)
        assert page.locator('#material-file-text').input_value()==text and 'current new file' in text
        expect(page.locator('#material-file-use')).to_be_enabled();expect(page.locator('#prep-detail')).to_be_visible()
        assert snapshot(f[1])==before;context.close();b.close()


def test_case_and_identity_aba_clear_selected_file_and_ignore_old_response(preparation_fixture,tmp_path):
    f=preparation_fixture;p,_,_=create(f);other,_,_=create(f);before=snapshot(f[1])
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p);pending=[]
        def hold(route):pending.append((route,route.fetch()))
        page.route('**/material-file-candidate',hold)
        page.locator('#material-file-input').set_input_files({'name':'SYNTHETIC-old.txt','mimeType':'text/plain','buffer':b'SYNTHETIC old case candidate'})
        page.locator('#material-file-synthetic').check();page.locator('#material-file-read').click()
        until=time.monotonic()+5
        while not pending and time.monotonic()<until:page.wait_for_timeout(20)
        assert pending
        page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').fill(f[2]['fixture-a'])
        page.locator('#existing-preparation-id').fill(other['preparation_id']);page.locator('#existing-preparation-read').click()
        expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录')
        page.locator('#existing-preparation-id').fill(p['preparation_id']);page.locator('#existing-preparation-read').click()
        expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录')
        route,response=pending[0];route.fulfill(response=response);page.wait_for_timeout(150)
        expect(page.locator('#material-file-output')).to_be_hidden();expect(page.locator('#material-file-use')).to_be_disabled()
        assert page.locator('#material-file-text').input_value()=='' and page.locator('#material-file-input').input_value()==''
        assert snapshot(f[1])==before;context.close();b.close()


def test_use_candidate_rechecks_current_read_authority_before_filling_original_form(preparation_fixture,tmp_path):
    f=preparation_fixture;p,_,_=create(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p);select_file(page,'SYNTHETIC.txt',b'SYNTHETIC candidate before revocation')
        with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        before=snapshot(f[1]);page.locator('#material-file-use').click()
        expect(page.locator('#prep-detail')).to_be_hidden();assert page.locator('#material-file-text').input_value()=='' and page.locator('#prep-text').input_value()==''
        expect(page.locator('#page-feedback')).not_to_be_empty();assert snapshot(f[1])==before;context.close();b.close()
