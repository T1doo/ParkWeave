"""Quoted CSV field line endings remain data across import and original save."""
import csv
import hashlib
import io

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright,expect

from parkweave import material_file_import as files
from test_preparation import preparation_fixture,create,command,headers
from test_material_file_import import encoded,body,path,ordinary
from test_material_file_import_browser import browser_page,open_record,select_file,save_candidate
from test_native_preparation_entry_browser import ordinary_process


def cells(text):return list(csv.reader(io.StringIO(text,newline=''),strict=True))


@pytest.mark.parametrize('ending',[b'\r\n',b'\r'])
def test_csv_quoted_field_line_ending_is_data_not_a_record_separator(ending):
    raw=b'h,v\r\nSYNTHETIC,"line1'+ending+b'line2 "\r\n'
    candidate=files.parse('SYNTHETIC.csv',encoded(raw))['candidate_text']
    assert cells(candidate)==cells(raw.decode())
    assert candidate.endswith('"') and '\n"SYNTHETIC"' in candidate


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


def test_csv_actual_file_chooser_original_add_and_ordinary_process_restart_preserve_field_cr(preparation_fixture,tmp_path):
    f=preparation_fixture;p,_,_=create(f)
    raw=b'h,v\r\nSYNTHETIC,"first\r\nsecond\rthird "\r\n';expected=cells(raw.decode())
    with ordinary_process(f,tmp_path/'first') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p)
        select_file(page,'SYNTHETIC.csv',raw);save_candidate(page,'need_summary')
        expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件',timeout=15000)
        material=api.get('/api/preparations/'+p['preparation_id'],headers=headers(f[2])).json()['current_materials'][0]
        assert cells(material['text'])==expected
        exact=material['text'];assert material['source_sha256']==hashlib.sha256(exact.encode()).hexdigest()
        context.close();b.close()
    with ordinary_process(f,tmp_path/'restarted') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p)
        material=api.get('/api/preparations/'+p['preparation_id'],headers=headers(f[2])).json()['current_materials'][0]
        assert material['text']==exact and cells(material['text'])==expected
        assert page.locator('#prep-materials article p').first.evaluate('(e)=>e.textContent')==exact
        context.close();b.close()
