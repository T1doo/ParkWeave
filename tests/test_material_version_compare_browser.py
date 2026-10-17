"""Actual ordinary process, authorized existing synthetic materials, and original writes."""
import hashlib,json,time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright,expect

from test_preparation import preparation_fixture,command,read,headers,add
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
        assert page.evaluate('!materialVersionRequired&&materialVersionOrigin===null')
        page.locator('#prep-slot').select_option('need_summary');page.locator('#prep-text').fill('SYNTHETIC next manual source');page.locator('#prep-source-kind').select_option('USER_STATEMENT');page.locator('#prep-source-label').fill('SYNTHETIC manual follow-up')
        page.locator('#prep-evidence button').click();expect(page.locator('#prep-materials')).to_contain_text('SYNTHETIC next manual source',timeout=15000);expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件',timeout=15000);assert len(posts)==2
        q=api.get('/api/preparations/'+p['preparation_id']+'/material-corrections',headers=headers(f[2])).json();assert q['active_targets'][0]['status']=='SUBMITTED_FOR_REVIEW'
        current=api.get('/api/preparations/'+p['preparation_id'],headers=headers(f[2])).json();assert current['preparation']['review_sha256'] is None;assert any(m['text']==original['text'] for m in current['material_history'])
        assert next(m for m in current['current_materials'] if m['slot']=='material_outline')['version']==2
        open_record(page,api,f,p,'prep-specialist-fixture-a');expect(page.locator('#material-version-panel')).to_be_hidden();expect(page.locator('#prep-history')).to_contain_text('REVIEW');expect(page.locator('#prep-materials')).to_contain_text(text)
        page.locator('#prep-reason').fill('SYNTHETIC independently reviews current complete two-slot pack');page.locator('#prep-review').click();expect(page.locator('#prep-summary')).to_contain_text('待企业确认');expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件',timeout=15000)
        open_record(page,api,f,p);page.locator('#prep-reason').fill('SYNTHETIC owner confirms current source pack');page.locator('#prep-confirm').click();expect(page.locator('#prep-summary')).to_contain_text('本地资料准备已确认')
        assert not errors and authority(f)==auth;context.close();b.close()
    persisted=snapshot(f[1])
    with ordinary_process(f,tmp_path/'restarted') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);seen=[];page.on('request',lambda r:seen.append(r.method));open_record(page,api,f,p)
        expect(page.locator('#prep-materials')).to_contain_text(text);expect(page.locator('#material-version-output')).to_be_hidden();assert page.evaluate('materialVersionView===null&&!materialVersionRequired')
        assert set(seen)=={'GET'} and snapshot(f[1])==persisted;context.close();b.close()
    (tmp_path/'proof.json').write_text(json.dumps({'ordinary_process_restart':True,'original_ADD_REVIEW_CONFIRM_only':True,'old_body_history_retained':True,'comparison_read_only':True,'source_authority_tables_unchanged':True,'case_goal_completed':False},indent=2)+'\n')


def saved(page):
    page.locator('#prep-evidence button').click()
    expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件',timeout=15000)


def held_response(page,held):
    until=time.monotonic()+5
    while not held and time.monotonic()<until:page.wait_for_timeout(20)
    assert held


@pytest.mark.parametrize('source_changed',[False,True])
def test_identical_body_is_explicit_new_version_never_automatic_correction_resolution(preparation_fixture,tmp_path,source_changed):
    f=preparation_fixture;p=correction_case(f);old=next(m for m in checked(read(f,p))['current_materials'] if m['slot']=='material_outline')
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p);fill_file(page,old['text'].encode())
        page.locator('#prep-source-label').fill('SYNTHETIC changed source label' if source_changed else old['source_label'])
        compare_candidate(page);expect(page.locator('#material-version-output')).to_contain_text('正文逐字一致')
        expect(page.locator('#material-version-output')).to_contain_text('来源类型/标签为本次新选择或有变化' if source_changed else '来源类型/标签一致')
        saved(page);x=checked(read(f,p));m=next(m for m in x['current_materials'] if m['slot']=='material_outline')
        assert m['version']==2 and m['text']==old['text'] and m['source_sha256']==old['source_sha256'] and x['preparation']['review_sha256'] is None
        q=api.get('/api/preparations/'+p['preparation_id']+'/material-corrections',headers=headers(f[2])).json();assert q['active_targets'][0]['status']=='SUBMITTED_FOR_REVIEW'
        context.close();b.close()


@pytest.mark.parametrize('field,value',[('prep-text','SYNTHETIC edited body'),('prep-source-kind','USER_STATEMENT'),('prep-source-label','SYNTHETIC edited label'),('prep-slot','need_summary')])
def test_edit_invalidates_comparison_and_cannot_post_until_actual_body_recompared(preparation_fixture,tmp_path,field,value):
    f=preparation_fixture;p=correction_case(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p);fill_file(page);compare_candidate(page)
        control=page.locator('#'+field)
        if field in ('prep-slot','prep-source-kind'):control.select_option(value)
        else:control.fill(value)
        expect(page.locator('#material-version-output')).to_be_hidden();posts=[];page.on('request',lambda r:posts.append(r.post_data_json) if r.method=='POST' else None);before=snapshot(f[1])
        page.locator('#prep-evidence button').click();expect(page.locator('#prep-error')).to_contain_text('尚未核对');assert not posts and snapshot(f[1])==before and control.input_value()==value
        compare_candidate(page);candidate=page.evaluate('materialVersionView.data.candidate');saved(page)
        assert len(posts)==1 and all(posts[0][k]==candidate[k] for k in ('slot','text','source_kind','source_label'))
        m=next(m for m in checked(read(f,p))['current_materials'] if m['slot']==candidate['slot']);assert m['text']==candidate['text'] and m['source_sha256']==candidate['text_sha256']
        context.close();b.close()


@pytest.mark.parametrize('change',['material','target','same_revision_metadata'])
def test_actual_concurrent_original_write_invalidates_pre_submit_comparison_without_post(preparation_fixture,tmp_path,change):
    f=preparation_fixture;p=correction_case(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p);draft=fill_file(page);compare_candidate(page)
        if change=='material':checked(add(f,p,'need_summary',text='SYNTHETIC concurrent other-slot source'))
        elif change=='target':checked(request(f,p,['material_outline'],reason='SYNTHETIC changed current correction target'))
        else:
            # Isolated owner fault injection: metadata changes without a revision bump.
            # The source snapshot must still invalidate the pending comparison.
            with f[1].connect() as c:c.execute("UPDATE preparation_evidence SET source_label='SYNTHETIC same-revision metadata damage' WHERE preparation_id=%s AND slot='material_outline'",(p['preparation_id'],))
            assert checked(read(f,p))['preparation']['revision']==p['revision']
        before=snapshot(f[1]);posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
        page.locator('#prep-evidence button').click();expect(page.locator('#material-version-status')).to_contain_text('差异已失效')
        assert not posts and snapshot(f[1])==before;expect(page.locator('#material-version-output')).to_be_hidden();assert page.locator('#prep-text').input_value()==draft
        assert page.evaluate('prepCommandPending===null&&prepRetries.size===0&&prepRecoveryHandle===null');context.close();b.close()


@pytest.mark.parametrize('stage,damage',[('compare','READ'),('submit','READ'),('compare','catalog'),('submit','reviewer')])
def test_current_original_entry_refusal_preserves_status_contract_without_any_write(preparation_fixture,tmp_path,stage,damage):
    f=preparation_fixture;p=correction_case(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p);fill_file(page)
        if stage=='submit':compare_candidate(page)
        with f[1].connect() as c:
            if damage=='READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
            elif damage=='reviewer':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a' AND capability='REVIEW_ASSIGNED'")
            else:c.execute("UPDATE preparation_catalog SET source='{}'::jsonb WHERE park_id='park-a'")
        before=snapshot(f[1]);posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
        draft=page.locator('#prep-text').input_value()
        with page.expect_response(lambda r:r.url.endswith('/'+p['preparation_id']+'/entry')) as observed:
            page.locator('#material-version-compare' if stage=='compare' else '#prep-evidence button').click()
        assert observed.value.status==(409 if damage=='catalog' else 403)
        if damage=='catalog':
            expect(page.locator('#material-version-status')).to_contain_text('资料已变化或状态不允许');expect(page.locator('#prep-detail')).to_be_visible();assert page.locator('#prep-text').input_value()==draft and page.evaluate('materialVersionRequired')
        else:
            expect(page.locator('#prep-detail')).to_be_hidden();expect(page.locator('#prep-text')).to_have_value('');assert page.evaluate('!materialVersionRequired')
        expect(page.locator('#material-version-output')).to_be_hidden()
        assert page.evaluate('materialVersionView===null') and not posts and snapshot(f[1])==before;context.close();b.close()


@pytest.mark.parametrize('late_status',[200,403])
@pytest.mark.parametrize('change',['draft','identity_case_ABA'])
def test_late_comparison_reply_cannot_replace_or_clear_new_current_context(preparation_fixture,tmp_path,late_status,change):
    f=preparation_fixture;p=correction_case(f);other=fresh(f,label='OTHER_VERSION_COMPARE');before=snapshot(f[1])
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p);fill_file(page);held=[]
        def hold(route):
            if held:route.continue_();return
            held.append((route,route.fetch()))
        page.route('**/api/preparations/'+p['preparation_id'],hold);page.locator('#material-version-compare').click();held_response(page,held)
        if change=='identity_case_ABA':
            page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').fill(f[2]['fixture-a'])
            for row in (other,p):
                page.locator('#existing-preparation-id').fill(row['preparation_id']);page.locator('#existing-preparation-read').click();expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录',timeout=15000)
            fill_file(page,b'SYNTHETIC new context body')
        else:page.locator('#prep-text').fill('SYNTHETIC new context body')
        compare_candidate(page);current=page.evaluate('materialVersionView.data');route,response=held[0]
        if late_status==200:route.fulfill(response=response)
        else:route.fulfill(status=403,json={'detail':'record unavailable or authorization denied'})
        page.wait_for_timeout(150);assert page.evaluate('materialVersionView.data')==current;expect(page.locator('#prep-detail')).to_be_visible();assert page.locator('#prep-text').input_value()=='SYNTHETIC new context body' and snapshot(f[1])==before
        context.close();b.close()


@pytest.mark.parametrize('boundary',['unicode_whitespace','FEFF'])
def test_actual_pydantic_normalization_matches_compared_body_and_saved_hash(preparation_fixture,tmp_path,boundary):
    from parkweave.preparation import PreparationCommand
    f=preparation_fixture;p=correction_case(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p);fill_file(page)
        # Invalid label/control candidates are refused locally without a key or POST.
        posts=[];page.on('request',lambda r:posts.append(r.post_data_json) if r.method=='POST' else None);before=snapshot(f[1])
        for bad in (0x1c,0x1f,0xd800):
            page.locator('#prep-source-label').evaluate('(e,x)=>{e.value=String.fromCharCode(x);e.dispatchEvent(new Event("input",{bubbles:true}));}',bad)
            page.locator('#material-version-compare').click();expect(page.locator('#material-version-status')).to_contain_text('有效正文与来源');assert not posts and snapshot(f[1])==before
        pad='\u0085\u00a0\u2007\u202f\u3000' if boundary=='unicode_whitespace' else '\ufeff'
        body=pad+'SYNTHETIC normalized body'+pad;label=pad+'SYNTHETIC normalized label'+pad
        page.locator('#prep-text').fill(body);page.locator('#prep-source-label').fill(label);compare_candidate(page)
        actual=PreparationCommand(action='ADD_EVIDENCE',expected_revision=p['revision'],slot='material_outline',text=body,source_kind='DOCUMENT_EXCERPT',source_label=label)
        candidate=page.evaluate('materialVersionView.data.candidate');assert candidate['text']==actual.text and candidate['source_label']==actual.source_label
        saved(page);m=next(m for m in checked(read(f,p))['current_materials'] if m['slot']=='material_outline')
        assert posts[0]['text']==actual.text==m['text'] and posts[0]['source_label']==actual.source_label==m['source_label'] and m['source_sha256']==candidate['text_sha256'];context.close();b.close()


def test_large_line_budget_retains_both_complete_bodies_and_legacy_non_bmp_baseline(preparation_fixture,tmp_path):
    f=preparation_fixture;p=correction_case(f);old='😀'*2001;p=checked(add(f,p,'need_summary',text=old));outline='A\n'*1100;p=checked(add(f,p,'material_outline',text=outline))
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p);fill_file(page,b'SYNTHETIC new summary',slot='need_summary');compare_candidate(page);assert page.evaluate('materialVersionView.data.baseline.text')==old
        page.locator('#prep-slot').select_option('material_outline');new='B\n'*1100;page.locator('#prep-text').fill(new);compare_candidate(page)
        data=page.evaluate('materialVersionView.data');assert data['baseline']['text']==outline.strip() and data['candidate']['text']==new.strip()
        expect(page.locator('#material-version-output')).to_contain_text('仅提供上方完整新旧正文');assert page.locator('[data-material-version-diff]').count()==0
        bodies=page.locator('#material-version-output article pre').all_text_contents();assert bodies==[outline.strip(),new.strip()];context.close();b.close()


@pytest.mark.parametrize('denied',[False,True])
def test_comparison_read_interleaved_with_real_committed_lost_objection_keeps_original_handle(preparation_fixture,tmp_path,denied):
    f=preparation_fixture;p=fresh(f,label='COMPARISON_UNKNOWN');p=checked(command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC original whole pack review'));p=checked(command(f,p,'CONFIRM',reason='SYNTHETIC owner confirms pack'))
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p);draft=fill_file(page);held=[];lost=[]
        def hold(route):held.append((route,None if denied else route.fetch()))
        page.route('**/api/preparations/'+p['preparation_id'],hold);page.locator('#material-version-compare').click();held_response(page,held)
        def lose(route):
            if route.request.method!='POST':route.continue_();return
            response=route.fetch();assert response.status==200;lost.append(response);route.abort('failed')
        page.route('**/material-objections',lose);page.locator('#objection-reason').fill('SYNTHETIC PRIVATE_VERSION_OBJECTION');page.locator('#objection-raise').click();page.wait_for_function('()=>objectionPending!==null&&!objectionBusy')
        assert lost;stored=page.evaluate('JSON.stringify({...localStorage})');assert stored!='{}' and 'PRIVATE_VERSION' not in stored and f[2]['fixture-a'] not in stored
        if denied:
            with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        before=snapshot(f[1]);route,response=held[0]
        if denied:response=route.fetch();assert response.status==403
        route.fulfill(response=response);page.wait_for_timeout(150);expect(page.locator('#material-version-output')).to_be_hidden();assert page.evaluate('materialVersionView===null') and snapshot(f[1])==before and page.evaluate('JSON.stringify({...localStorage})')==stored
        if denied:expect(page.locator('#prep-detail')).to_be_hidden();assert page.locator('#prep-text').input_value()==''
        else:assert page.locator('#prep-text').input_value()==draft and page.evaluate('objectionPending!==null');expect(page.locator('#material-version-compare')).to_be_disabled()
        context.close();b.close()
