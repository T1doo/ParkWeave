"""Quoted CSV field line endings remain data across import and original save."""
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright,expect

from parkweave import material_file_import as files
from test_preparation import preparation_fixture,create,command,headers
from test_material_file_import import encoded,body,path,ordinary
from test_material_file_import_browser import browser_page,open_record,select_file
from test_native_preparation_entry_browser import ordinary_process
from test_native_preparation_entry import snapshot


def cells(text):return list(csv.reader(io.StringIO(text,newline=''),strict=True))


@pytest.mark.parametrize('ending',[b'\r\n',b'\r'])
def test_csv_quoted_field_line_ending_is_data_not_a_record_separator(ending):
    raw=b'h,v\r\nSYNTHETIC,"line1'+ending+b'line2 "\r\n'
    candidate=files.parse('SYNTHETIC.csv',encoded(raw))['candidate_text']
    assert cells(candidate)==cells(raw.decode())
    assert candidate.endswith('"') and '\n"SYNTHETIC"' in candidate


def test_csv_literal_backslashes_quotes_unicode_and_mixed_field_endings_are_not_double_decoded():
    cell='字面\\r与\\n，"引号"和\\路径\r\n第二行😀\r第三行\n第四行 '
    raw=('h,v\r\nSYNTHETIC,"'+cell.replace('"','""')+'"\r\n').encode()
    candidate=files.parse('SYNTHETIC.csv',encoded(raw))['candidate_text']
    assert cells(candidate)==[['h','v'],['SYNTHETIC',cell]]==cells(raw.decode())


def test_csv_actual_api_original_add_and_factory_restart_preserve_all_field_values(preparation_fixture,monkeypatch):
    f=preparation_fixture;p,_,_=create(f)
    raw=b'h,v\r\nSYNTHETIC,"first\r\nsecond\rthird "\r\n'
    with TestClient(ordinary(f,monkeypatch)) as api:
        r=api.post(path(p),json=body(p,'SYNTHETIC.csv',raw),headers=headers(f[2]));assert r.status_code==200;x=r.json()
    saved=command(f,p,'ADD_EVIDENCE',slot='need_summary',text=x['candidate_text'],source_kind=x['source_kind'],source_label=x['source_label'])
    assert saved.status_code==200
    with TestClient(ordinary(f,monkeypatch)) as restarted:
        r=restarted.get('/api/preparations/'+p['preparation_id'],headers=headers(f[2]));assert r.status_code==200
        material=r.json()['current_materials'][0]
    assert cells(material['text'])==cells(raw.decode())
    assert material['text']==x['candidate_text'] and material['source_sha256']==hashlib.sha256(material['text'].encode()).hexdigest()


@pytest.mark.parametrize('variant',['unchanged','edited','lost-reply','boundary'])
def test_csv_actual_file_chooser_original_add_and_ordinary_process_restart_preserve_field_cr(preparation_fixture,tmp_path,variant):
    f=preparation_fixture;p,_,_=create(f)
    cell='first\r\nsecond\rthird\n字面\\r和"quote"与😀 '
    if variant=='boundary':cell='x'*(4000-len('"h","v"\n"SYNTHETIC",""')-1)+'\r'
    raw=('h,v\r\nSYNTHETIC,"'+cell.replace('"','""')+'"\r\n').encode();expected=cells(raw.decode())
    with ordinary_process(f,tmp_path/'first') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p)
        select_file(page,'SYNTHETIC.csv',raw)
        assert cells(json.loads(page.locator('#material-file-text').input_value()))==expected
        page.locator('#material-file-use').click()
        expect(page.locator('#material-file-editing')).to_be_visible()
        hint=page.locator('#material-file-editing').text_content()
        assert r'\r代表CR、\n代表LF' in hint and r'\\r代表CR' not in hint
        editor=page.locator('#prep-text');display=editor.input_value();decoded=json.loads(display)
        assert '\r' not in display and cells(decoded)==expected
        if variant=='boundary':assert len(decoded)==4000
        if variant=='edited':
            display=display.replace('first','edited');editor.fill(display);expected[1][1]=expected[1][1].replace('first','edited')
        expected_body=json.loads(display);sent=[];lost=[]
        page.on('request',lambda r:sent.append((r.post_data_json,r.headers.get('idempotency-key'))) if r.method=='POST' and r.url.endswith('/commands') else None)
        if variant=='lost-reply':
            def lose(route):
                if lost:route.continue_();return
                lost.append(route.fetch());route.abort('failed')
            page.route('**/api/preparations/*/commands',lose)
        page.locator('#prep-evidence button').click()
        if variant=='lost-reply':
            expect(page.locator('#prep-command-retry')).to_be_visible();assert lost[0].status==200
            # Real controls stay disabled under the original UNKNOWN gate.
            # Client-side fault injection cannot alter the immutable retry body.
            expect(editor).to_be_disabled();changed=display.replace('first','new draft only')
            editor.evaluate('(e,value)=>{e.value=value;}',changed)
            page.locator('#prep-command-retry').click()
        expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件',timeout=15000)
        assert sent and all(body['text']==expected_body for body,key in sent)
        assert len(sent)==(2 if variant=='lost-reply' else 1)
        assert len({key for body,key in sent})==1
        if variant=='lost-reply':assert editor.input_value()==changed;expect(page.locator('#material-file-editing')).to_be_visible()
        else:assert editor.input_value()=='' and editor.get_attribute('maxlength')=='4000';expect(page.locator('#material-file-editing')).to_be_hidden()
        material=api.get('/api/preparations/'+p['preparation_id'],headers=headers(f[2])).json()['current_materials'][0]
        assert cells(material['text'])==expected
        exact=material['text'];assert exact==expected_body and material['source_sha256']==hashlib.sha256(exact.encode()).hexdigest()
        if variant=='unchanged':
            page.locator('#material-pack-generate').click();expect(page.locator('#material-pack-status')).to_contain_text('已生成当前读取快照')
            packed=page.locator('#material-pack-text').input_value()
            body_line=next(line for line in packed.splitlines() if line.startswith('原已分享正文：'))
            assert json.loads(body_line.split('：',1)[1])==exact
            with page.expect_download() as download:page.locator('#material-pack-download').click()
            payload=Path(download.value.path()).read_bytes();assert payload==packed.encode()
            (tmp_path/'actual-downloaded-material-pack.txt').write_bytes(payload)
            page.set_viewport_size({'width':390,'height':900});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(tmp_path/'csv-field-cr-download-390.png'))
        context.close();b.close()
    with ordinary_process(f,tmp_path/'restarted') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p)
        material=api.get('/api/preparations/'+p['preparation_id'],headers=headers(f[2])).json()['current_materials'][0]
        assert material['text']==exact and cells(material['text'])==expected
        assert page.locator('#prep-materials article p').first.evaluate('(e)=>e.textContent')==exact
        assert page.locator('#prep-text').get_attribute('maxlength')=='4000'
        expect(page.locator('#material-file-editing')).to_be_hidden()
        if variant=='unchanged':
            page.locator('#material-pack-generate').click();expect(page.locator('#material-pack-status')).to_contain_text('已生成当前读取快照')
            assert page.locator('#material-pack-text').input_value()==packed
        context.close();b.close()


def test_bad_escaped_csv_edits_refuse_before_key_or_any_original_post(preparation_fixture,tmp_path):
    f=preparation_fixture;p,_,_=create(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p)
        select_file(page,'SYNTHETIC.csv',b'h,v\nSYNTHETIC,"a\rb"');page.locator('#material-file-use').click()
        expect(page.locator('#material-file-editing')).to_be_visible()
        before=snapshot(f[1]);sent=[];page.on('request',lambda r:sent.append(r.url) if r.method=='POST' else None)
        for bad in ('broken JSON','{}','[]','""',json.dumps('x'*4001),'"\\u0000"','"\\ud800"','"\\u000b"'):
            page.locator('#prep-error').evaluate('(e)=>{e.textContent="";}')
            page.locator('#prep-text').fill(bad);page.locator('#prep-evidence button').click()
            expect(page.locator('#prep-error')).not_to_be_empty()
            assert not sent and page.locator('#prep-text').input_value()==bad
            assert page.evaluate('prepCommandPending===null&&prepRetries.size===0&&prepRecoveryHandle===null')
        assert snapshot(f[1])==before;context.close();b.close()


def test_escaped_csv_editor_refresh_identity_and_revocation_follow_original_draft_lifecycle(preparation_fixture,tmp_path):
    f=preparation_fixture;p,_,_=create(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p)
        raw=b'h,v\nSYNTHETIC,"a\r\nb\rc"'
        select_file(page,'SYNTHETIC.csv',raw);page.locator('#material-file-use').click()
        expect(page.locator('#material-file-editing')).to_be_visible();display=page.locator('#prep-text').input_value()
        page.locator('#prep-refresh').click();expect(page.locator('#prep-detail')).to_be_visible()
        assert page.locator('#prep-text').input_value()==display;expect(page.locator('#material-file-editing')).to_be_visible()
        page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').fill(f[2]['fixture-a'])
        assert page.locator('#prep-text').input_value()=='' and page.locator('#prep-text').get_attribute('maxlength')=='4000'
        expect(page.locator('#material-file-editing')).to_be_hidden()
        open_record(page,api,f,p);select_file(page,'SYNTHETIC.csv',raw);page.locator('#material-file-use').click()
        expect(page.locator('#material-file-editing')).to_be_visible()
        with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        before=snapshot(f[1]);page.locator('#prep-refresh').click();expect(page.locator('#prep-detail')).to_be_hidden()
        assert page.locator('#prep-text').input_value()=='' and page.locator('#prep-text').get_attribute('maxlength')=='4000'
        expect(page.locator('#material-file-editing')).to_be_hidden();assert snapshot(f[1])==before
        context.close();b.close()
