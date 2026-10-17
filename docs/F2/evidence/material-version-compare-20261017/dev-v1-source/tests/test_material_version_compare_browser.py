"""Actual ordinary process, authorized existing synthetic materials, and original writes."""
import hashlib,json
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright,expect

from test_preparation import preparation_fixture,command,read,headers
from test_material_corrections import fresh,checked,request,authority
from test_native_preparation_entry import snapshot
from test_native_preparation_entry_browser import ordinary_process
from test_material_file_import_browser import browser_page,open_record,select_file,compare_candidate


def correction_case(f):
    p=fresh(f,label='VERSION_COMPARE')
    p=checked(command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC prior whole pack review'))
    p=checked(command(f,p,'CONFIRM',reason='SYNTHETIC prior owner confirmation'))
    p=checked(command(f,p,'REOPEN',reason='SYNTHETIC updated material requested'))
    return checked(request(f,p,['material_outline'],reason='SYNTHETIC please correct the material outline'))


def fill_file(page,raw=b'SYNTHETIC updated outline\n<script>window.versionInjection=true</script>',name='SYNTHETIC-v2.txt',slot='material_outline'):
    text=select_file(page,name,raw)
    page.locator('#prep-slot').select_option(slot);page.locator('#material-file-use').click()
    expect(page.locator('#material-file-status')).to_contain_text('已填入原表单，尚未保存')
    return text


def test_file_v2_compare_original_correction_review_confirm_and_cold_restart(preparation_fixture,tmp_path):
    f=preparation_fixture;p=correction_case(f);auth=authority(f);before=checked(read(f,p));original=next(m for m in before['current_materials'] if m['slot']=='material_outline')
    with ordinary_process(f,tmp_path/'first') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);errors=[];page.on('pageerror',lambda e:errors.append(str(e)));open_record(page,api,f,p)
        text=fill_file(page);posts=[];page.on('request',lambda r:posts.append(r.post_data_json) if r.method=='POST' and r.url.endswith('/commands') else None)
        unchanged=snapshot(f[1]);page.locator('#prep-evidence button').click();expect(page.locator('#prep-error')).to_contain_text('尚未核对');assert not posts and snapshot(f[1])==unchanged
        compare_candidate(page);v=page.evaluate('materialVersionView.data');assert v['baseline']['id']==original['id'] and v['baseline']['version']==1 and v['baseline']['text']==original['text'];assert v['candidate']['text']==text and v['candidate']['text_sha256']==hashlib.sha256(text.encode()).hexdigest()
        assert v['corrections'][0]['status']=='REQUESTED' and 'please correct' in v['corrections'][0]['reason'];assert snapshot(f[1])==unchanged
        expect(page.locator('#material-version-output')).to_contain_text(original['text']);expect(page.locator('#material-version-output')).to_contain_text(text)
        assert page.locator('#material-version-output script').count()==0 and not page.evaluate('window.versionInjection||false')
        for width in (1200,390,320):
            page.set_viewport_size({'width':width,'height':1000});page.locator('#material-version-panel').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(tmp_path/f'material-version-{width}.png'))
        page.locator('#prep-evidence button').click();expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件',timeout=15000)
        assert len(posts)==1 and posts[0]['text']==text
        q=api.get('/api/preparations/'+p['preparation_id']+'/material-corrections',headers=headers(f[2])).json();assert q['active_targets'][0]['status']=='SUBMITTED_FOR_REVIEW'
        current=api.get('/api/preparations/'+p['preparation_id'],headers=headers(f[2])).json();assert current['preparation']['review_sha256'] is None;assert any(m['text']==original['text'] for m in current['material_history'])
        assert next(m for m in current['current_materials'] if m['slot']=='material_outline')['version']==2
        open_record(page,api,f,p,'prep-specialist-fixture-a');expect(page.locator('#material-version-panel')).to_be_hidden();expect(page.locator('#prep-history')).to_contain_text('REVIEW');expect(page.locator('#prep-materials')).to_contain_text(text)
        page.locator('#prep-reason').fill('SYNTHETIC independently reviews current complete two-slot pack');page.locator('#prep-review').click();expect(page.locator('#prep-summary')).to_contain_text('待企业确认')
        open_record(page,api,f,p);page.locator('#prep-reason').fill('SYNTHETIC owner confirms current source pack');page.locator('#prep-confirm').click();expect(page.locator('#prep-summary')).to_contain_text('本地资料准备已确认')
        assert not errors and authority(f)==auth;context.close();b.close()
    persisted=snapshot(f[1])
    with ordinary_process(f,tmp_path/'restarted') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);seen=[];page.on('request',lambda r:seen.append(r.method));open_record(page,api,f,p)
        expect(page.locator('#prep-materials')).to_contain_text(text);expect(page.locator('#material-version-output')).to_be_hidden();assert page.evaluate('materialVersionView===null&&!materialVersionRequired')
        assert set(seen)=={'GET'} and snapshot(f[1])==persisted;context.close();b.close()
    (tmp_path/'proof.json').write_text(json.dumps({'ordinary_process_restart':True,'original_ADD_REVIEW_CONFIRM_only':True,'old_body_history_retained':True,'comparison_read_only':True,'source_authority_tables_unchanged':True,'case_goal_completed':False},indent=2)+'\n')

