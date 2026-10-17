"""Owned synthetic resource response faults; preserve exact original request keys.

Existing isolated resource fixtures are setup only. All tested writes/retries use
visible ordinary-page controls; no assignments or application JS are injected.
"""
import json
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from playwright.sync_api import sync_playwright, expect

from test_resource_combinations import pair_fixture, pair, write
from test_native_preparation_entry_browser import ordinary_process
from test_material_file_import_browser import browser_page


@pytest.mark.parametrize('action',['hold','confirm','release','combination','cancel'])
def test_invalid_resource_binding_retains_original_key_until_explicit_retry(pair_fixture,tmp_path,action):
    f=pair_fixture;hs=[];g=None
    if action!='hold':
        hs,body=pair(f)
        if action=='cancel':
            result=write(f,body);assert result.status_code==201
            g=result.json()['combination']
    posts=[];fault=[]
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        browser,context,page=browser_page(pw)
        page.goto(str(api.base_url));page.locator('#token').fill(f[2]['fixture-a'])
        page.locator('[data-tab="resource"]').click();page.locator('#resource-catalog').click()
        expect(page.locator('#resource-form')).to_be_visible()
        if action=='hold':
            page.locator('#resource-purpose').fill('SYNTHETIC original binding retry')
            page.locator('#resource-preview').click();expect(page.locator('#resource-hold')).to_be_enabled()
            button=page.locator('#resource-hold');path='/api/synthetic-resources/'+page.locator('#resource-select').input_value()+'/holds'
        elif action in ('confirm','release'):
            page.locator('#resource-mine').click()
            button=page.locator('[data-hold-id="'+hs[0]['id']+'"] [data-resource-action="'+action+'"]')
            expect(button).to_be_visible();path='/api/resource-holds/'+hs[0]['id']+'/'+action
        elif action=='combination':
            page.locator('#resource-mine').click()
            for h in hs:page.locator('[data-combination-hold="'+h['id']+'"]').check()
            button=page.locator('#combination-confirm');path='/api/resource-combinations'
        else:
            page.locator('#combination-mine').click()
            button=page.locator('[data-combination-cancel="'+g['id']+'"]')
            expect(button).to_be_visible();path='/api/resource-combinations/'+g['id']+'/cancel'
        def corrupt_first_response(route):
            if route.request.method!='POST':route.continue_();return
            posts.append({'path':urlparse(route.request.url).path,'key':route.request.headers['idempotency-key'],
                          'body':route.request.post_data_json})
            response=route.fetch();assert response.status in (200,201)
            if fault:route.fulfill(response=response);return
            x=response.json();fault.append(response.status)
            if action=='hold':x['hold']['resource_id']=str(uuid4())
            elif action in ('confirm','release'):x['hold']['id']=str(uuid4())
            elif action=='combination':x['combination']['members'][0]['id']=str(uuid4())
            else:x['combination']['id']=str(uuid4())
            route.fulfill(response=response,json=x)
        page.route('**'+path,corrupt_first_response)
        button.click();expect(page.locator('#resource-error')).to_contain_text('响应不匹配')
        expect(button).to_be_enabled();button.click()
        # Retry the original visible action, never a new operation or a JS unlock.
        expect(page.locator('#resource-error')).to_be_empty()
        assert len(posts)==2 and posts[0]==posts[1]
        with f[1].connect() as c:
            holds=c.execute('SELECT count(*) n FROM synthetic_resource_holds').fetchone()['n']
            singles=c.execute('SELECT count(*) n FROM synthetic_resource_receipts').fetchone()['n']
            combinations=c.execute('SELECT count(*) n FROM synthetic_resource_combinations').fetchone()['n']
            grouped=c.execute('SELECT count(*) n FROM synthetic_resource_combination_receipts').fetchone()['n']
        assert holds==(1 if action=='hold' else 2)
        assert singles==({'hold':1,'confirm':3,'release':3,'combination':2,'cancel':2}[action])
        assert combinations==(1 if action in ('combination','cancel') else 0)
        assert grouped==({'combination':1,'cancel':2}.get(action,0))
        (tmp_path/'resource-binding-proof.json').write_text(json.dumps(dict(action=action,posts=posts,
            exact_original_key_preserved=True,hold_count=holds,single_receipts=singles,
            combination_count=combinations,combination_receipts=grouped,synthetic_only=True))+'\n')
        context.close();browser.close()
