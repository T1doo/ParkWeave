"""Chromium -> ordinary configured_app -> original material review workflow."""
import json,time,hashlib

import pytest
from playwright.sync_api import sync_playwright,expect

from test_preparation import preparation_fixture,command,read,headers,add
from test_material_corrections import fresh,checked,authority
from test_material_review_comparison import correction_pending,old_review,REVIEWER,same_value_reader_ABA
from test_material_version_compare_browser import fill_file,saved
from test_material_file_import_browser import browser_page,open_record,compare_candidate
from test_native_preparation_entry_browser import ordinary_process
from test_native_preparation_entry import snapshot


def compare_review(page):
    page.locator('#material-review-read').click()
    expect(page.locator('#material-review-status')).to_contain_text('已只读核对本次专员材料对照',timeout=15000)
    return page.evaluate('materialReviewView.data')


def wait_held(page,held):
    until=time.monotonic()+5
    while not held and time.monotonic()<until:page.wait_for_timeout(20)
    assert held


def submitted(f):
    p,old=correction_pending(f)
    return checked(add(f,p,'material_outline',text='SYNTHETIC current corrected v3')),old


def test_ordinary_owner_corrects_specialist_reads_exact_old_review_then_original_review_confirm_restart(preparation_fixture,tmp_path):
    f=preparation_fixture;p,old=correction_pending(f);auth=authority(f)
    with ordinary_process(f,tmp_path/'first') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);errors=[];page.on('pageerror',lambda e:errors.append(str(e)));open_record(page,api,f,p)
        expect(page.locator('#material-review-panel')).to_be_hidden();text=fill_file(page);compare_candidate(page);saved(page)
        open_record(page,api,f,p,REVIEWER);expect(page.locator('#material-version-panel')).to_be_hidden();expect(page.locator('#material-review-panel')).to_be_visible()
        before=snapshot(f[1]);methods=[];page.on('request',lambda r:methods.append(r.method));x=compare_review(page)
        assert set(methods)=={'GET'} and snapshot(f[1])==before and x['baseline_state']=='MATCHED'
        r=next(r for r in x['slots'] if r['slot']=='material_outline');assert r['baseline']['version']==1 and r['current']['version']==3 and r['current']['text']==text and r['baseline']['text']!= 'SYNTHETIC unreviewed v2 outline'
        assert x['review_event']['snapshot_sha256']==old['snapshot_sha256'] and x['current_snapshot_sha256']==checked(read(f,p))['snapshot_sha256']
        expect(page.locator('#material-review-output')).to_contain_text('当前补正');expect(page.locator('#material-review-output')).to_contain_text(text);assert page.locator('#material-review-output script').count()==0 and not page.evaluate('window.versionInjection||false')
        for width in (1200,390,320):
            page.set_viewport_size({'width':width,'height':1000});page.locator('#material-review-panel').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(tmp_path/f'specialist-review-{width}.png'))
        page.locator('#prep-reason').fill('SYNTHETIC independently checks both current slots and correction sufficiency');page.locator('#prep-review').click();expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件',timeout=15000);expect(page.locator('#material-review-output')).to_be_hidden();expect(page.locator('#material-review-read')).to_be_enabled();latest=compare_review(page);assert all(r['baseline']==r['current'] for r in latest['slots'])
        open_record(page,api,f,p);page.locator('#prep-reason').fill('SYNTHETIC enterprise separately confirms reviewed pack');page.locator('#prep-confirm').click();expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件',timeout=15000);expect(page.locator('#prep-summary')).to_contain_text('本地资料准备已确认')
        assert not errors and authority(f)==auth;context.close();b.close()
    before=snapshot(f[1])
    with ordinary_process(f,tmp_path/'restarted') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);seen=[];page.on('request',lambda r:seen.append(r.method));open_record(page,api,f,p,REVIEWER);assert page.evaluate('materialReviewView===null');x=compare_review(page)
        assert x['baseline_state']=='MATCHED' and all(r['baseline']==r['current'] for r in x['slots']) and set(seen)=={'GET'} and snapshot(f[1])==before;context.close();b.close()
    (tmp_path/'proof.json').write_text(json.dumps({'ordinary_configured_app_restart':True,'exact_old_review_v1_not_request_v2':True,'current_v3':True,'read_only_comparison_no_business_writes':True,'original_REVIEW_then_separate_owner_CONFIRM':True,'authority_tables_unchanged':True,'real_business_or_Windows_AT':False},indent=2)+'\n')


@pytest.mark.parametrize('source_changed',[False,True])
def test_same_body_new_record_and_source_changes_are_shown_separately(preparation_fixture,tmp_path,source_changed):
    f=preparation_fixture;p,old=old_review(f);p=checked(command(f,p,'REOPEN',reason='SYNTHETIC new source'));m=next(m for m in old['current_materials'] if m['slot']=='material_outline');p=checked(command(f,p,'ADD_EVIDENCE',slot=m['slot'],text=m['text'],source_kind=m['source_kind'],source_label='SYNTHETIC new metadata' if source_changed else m['source_label']))
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p,REVIEWER);x=compare_review(page);r=next(r for r in x['slots'] if r['slot']=='material_outline');assert r['baseline']['text']==r['current']['text'] and r['baseline']['id']!=r['current']['id'];card=page.locator('[data-material-review-slot="material_outline"]');expect(card).to_contain_text('正文逐字一致');expect(card).to_contain_text('来源类型/标签有变化' if source_changed else '来源类型/标签一致');expect(card).to_contain_text('材料版本/记录有变化');context.close();b.close()


@pytest.mark.parametrize('late_status',[200,403])
@pytest.mark.parametrize('change',['refresh','identity_case_ABA'])
def test_late_old_comparison_does_not_replace_or_clear_new_context(preparation_fixture,tmp_path,late_status,change):
    f=preparation_fixture;p,old=submitted(f);other=fresh(f,label='OTHER_REVIEW_CASE');before=snapshot(f[1])
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p,REVIEWER);held=[]
        def hold(route):
            if held:route.continue_();return
            held.append((route,route.fetch()))
        page.route('**/material-review-comparison',hold);page.locator('#material-review-read').click();wait_held(page,held)
        if change=='refresh':page.locator('#prep-refresh').click();page.wait_for_function('()=>preparationView!==null&&!materialReviewBusy')
        else:
            page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').fill(f[2][REVIEWER])
            for row in (other,p):
                page.locator('#existing-preparation-id').fill(row['preparation_id']);page.locator('#existing-preparation-read').click();expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录',timeout=15000)
        current=compare_review(page);route,response=held[0]
        if late_status==200:route.fulfill(response=response)
        else:route.fulfill(status=403,json={'detail':'record unavailable or authorization denied'})
        page.wait_for_timeout(150);assert page.evaluate('materialReviewView.data')==current;expect(page.locator('#prep-detail')).to_be_visible();assert snapshot(f[1])==before;context.close();b.close()


@pytest.mark.parametrize('damage',['READ','reassigned'])
def test_current_actual_denial_clears_specialist_private_comparison(preparation_fixture,tmp_path,damage):
    f=preparation_fixture;p,old=submitted(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p,REVIEWER);compare_review(page)
        with f[1].connect() as c:
            if damage=='READ':c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',(REVIEWER,'READ'))
            else:c.execute("UPDATE preparations SET reviewer_id='prep-specialist-fixture-b' WHERE id=%s",(p['preparation_id'],))
        before=snapshot(f[1]);page.locator('#material-review-read').click();expect(page.locator('#prep-detail')).to_be_hidden();expect(page.locator('#material-review-output')).to_be_hidden();assert page.evaluate('materialReviewView===null') and snapshot(f[1])==before;context.close();b.close()


def test_concurrent_actual_original_add_invalidates_comparison_before_display(preparation_fixture,tmp_path):
    f=preparation_fixture;p,old=submitted(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p,REVIEWER);held=[]
        def hold(route):held.append((route,route.fetch()))
        page.route('**/material-review-comparison',hold);page.locator('#material-review-read').click();wait_held(page,held);checked(add(f,p,'need_summary',text='SYNTHETIC concurrent current material'))
        before=snapshot(f[1]);route,response=held[0];route.fulfill(response=response);expect(page.locator('#material-review-status')).to_contain_text('不匹配');expect(page.locator('#material-review-output')).to_be_hidden();assert page.evaluate('materialReviewView===null') and snapshot(f[1])==before;context.close();b.close()


@pytest.mark.parametrize('denied',[False,True])
def test_read_interleaved_with_actual_committed_lost_REVIEW_preserves_original_UNKNOWN(preparation_fixture,tmp_path,denied):
    f=preparation_fixture;p,old=submitted(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p,REVIEWER);held=[];lost=[]
        def hold(route):held.append((route,None if denied else route.fetch()))
        page.route('**/material-review-comparison',hold);page.locator('#material-review-read').click();wait_held(page,held)
        def lose(route):
            response=route.fetch();assert response.status==200;lost.append(response);route.abort('failed')
        page.route('**/commands',lose);reason='SYNTHETIC PRIVATE_REVIEW_UNKNOWN';page.locator('#prep-reason').fill(reason);page.locator('#prep-review').click();page.wait_for_function('()=>prepCommandPending?.state==="UNKNOWN"');assert lost
        pending=page.evaluate('({key:prepCommandPending.key,body:prepCommandPending.body})');stored=page.evaluate('JSON.stringify({...localStorage})')
        if denied:
            with f[1].connect() as c:c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',(REVIEWER,'READ'))
        before=snapshot(f[1]);route,response=held[0]
        if denied:response=route.fetch();assert response.status==403
        route.fulfill(response=response);page.wait_for_timeout(150);expect(page.locator('#material-review-output')).to_be_hidden();assert snapshot(f[1])==before and page.evaluate('JSON.stringify({...localStorage})')==stored
        if denied:expect(page.locator('#prep-detail')).to_be_hidden();assert page.locator('#prep-reason').input_value()==''
        else:assert page.evaluate('({key:prepCommandPending.key,body:prepCommandPending.body})')==pending and page.locator('#prep-reason').input_value()==reason;expect(page.locator('#material-review-read')).to_be_disabled()
        context.close();b.close()


@pytest.mark.parametrize('unverifiable',[False,True])
def test_no_review_and_unverifiable_latest_review_do_not_invent_old_body(preparation_fixture,tmp_path,unverifiable):
    f=preparation_fixture
    if unverifiable:
        p,old=old_review(f);p=checked(command(f,p,'REOPEN',reason='SYNTHETIC changed material'));p=checked(add(f,p,'material_outline',text='SYNTHETIC newer current body'))
        with f[1].connect() as c:c.execute("UPDATE preparation_evidence SET source_label='SYNTHETIC damaged old baseline' WHERE preparation_id=%s AND slot='material_outline' AND version=1",(p['preparation_id'],))
    else:p=fresh(f,label='FIRST_REVIEW')
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p,REVIEWER);x=compare_review(page);assert x['baseline_state']==('UNVERIFIED' if unverifiable else 'NO_PREVIOUS_REVIEW');expect(page.locator('#material-review-output')).to_contain_text('基线无法核实' if unverifiable else '首次材料核对');assert all(r['baseline'] is None for r in x['slots']);context.close();b.close()


def test_original_request_changes_releases_flow_and_readonly_compare_button_recovers(preparation_fixture,tmp_path):
    f=preparation_fixture;p=fresh(f,label='READ_AFTER_CORRECTION')
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p,REVIEWER);compare_review(page);posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
        page.locator('[data-correction-slot="need_summary"]').check();page.locator('#prep-reason').fill('SYNTHETIC request original owner correction');page.locator('#prep-correction').click();expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件',timeout=15000)
        expect(page.locator('#material-review-output')).to_be_hidden();expect(page.locator('#material-review-read')).to_be_enabled();before=snapshot(f[1]);x=compare_review(page);assert x['baseline_state']=='NO_PREVIOUS_REVIEW' and len(posts)==1 and snapshot(f[1])==before;context.close();b.close()


def test_CRLF_exact_body_and_bounded_line_fallback_preserve_full_old_and_current_text(preparation_fixture,tmp_path):
    f=preparation_fixture;p=fresh(f,label='LINE_BOUND');old='A\r\n'*1000+'尾😀';p=checked(add(f,p,'material_outline',text=old));p=checked(command(f,p,'REVIEW',REVIEWER,reason='SYNTHETIC exact CRLF prior review'));p=checked(command(f,p,'REOPEN',reason='SYNTHETIC new lines'));new='B\r'*1000+'尾😀';p=checked(add(f,p,'material_outline',text=new))
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p,REVIEWER);x=compare_review(page);r=next(r for r in x['slots'] if r['slot']=='material_outline');assert r['baseline']['text']==old and r['current']['text']==new and r['baseline']['source_sha256']==hashlib.sha256(old.encode()).hexdigest()
        card=page.locator('[data-material-review-slot="material_outline"]');expect(card).to_contain_text('仅提供上方完整新旧正文');assert card.locator('[data-material-review-diff]').count()==0 and card.locator('pre').all_text_contents()==[json.dumps(old,ensure_ascii=False,separators=(',',':')),json.dumps(new,ensure_ascii=False,separators=(',',':'))];context.close();b.close()


@pytest.mark.parametrize('damage',['REVIEW_ASSIGNED','reassigned'])
def test_inflight_actual_revocation_or_reassignment_clears_captured_authorized_response(preparation_fixture,tmp_path,damage):
    f=preparation_fixture;p,old=submitted(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p,REVIEWER);held=[];methods=[];page.on('request',lambda r:methods.append(r.method))
        def hold(route):
            if held:route.continue_();return
            held.append((route,route.fetch()))
        page.route('**/material-review-comparison',hold);page.locator('#material-review-read').click();wait_held(page,held)
        with f[1].connect() as c:
            if damage=='REVIEW_ASSIGNED':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability='REVIEW_ASSIGNED'",(REVIEWER,))
            else:c.execute("UPDATE preparations SET reviewer_id='prep-specialist-fixture-b' WHERE id=%s",(p['preparation_id'],))
        before=snapshot(f[1]);route,response=held[0];route.fulfill(response=response)
        expect(page.locator('#prep-detail')).to_be_hidden();expect(page.locator('#material-review-output')).to_be_hidden();assert page.evaluate('materialReviewView===null') and snapshot(f[1])==before and set(methods)=={'GET'};context.close();b.close()


@pytest.mark.parametrize('kind',['READ','REVIEW_ASSIGNED','assignment','catalog'])
def test_inflight_same_value_reader_ABA_discards_stale_projection_even_after_authority_restored(preparation_fixture,tmp_path,kind):
    f=preparation_fixture;p,old=submitted(f);auth=authority(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,context,page=browser_page(pw);open_record(page,api,f,p,REVIEWER);held=[];methods=[];page.on('request',lambda r:methods.append(r.method))
        def hold(route):
            if held:route.continue_();return
            held.append((route,route.fetch()))
        page.route('**/material-review-comparison',hold);page.locator('#material-review-read').click();wait_held(page,held)
        same_value_reader_ABA(f,p,kind);before=snapshot(f[1]);route,response=held[0];route.fulfill(response=response)
        expect(page.locator('#material-review-status')).to_contain_text('已变化');expect(page.locator('#material-review-output')).to_be_hidden();assert page.evaluate('materialReviewView===null') and snapshot(f[1])==before and authority(f)==auth and set(methods)=={'GET'};context.close();b.close()
