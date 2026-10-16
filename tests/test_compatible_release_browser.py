"""Actual Chromium publication + new cold input + explicit ADOPT.

Downstream independent approval/capacity is separately tested by ASGI module.
"""
import json, os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4
import pytest
from playwright.sync_api import sync_playwright
from release_new_case_support import (release_case,cancel33_case,capability_resource_catalog,capability_catalog,
    preparation_fixture,receipt_fixture,admit_new,path,ok)
from test_new_enterprise_local_chain import actual_http, ALL_GOALS
from test_preparation import headers,command as material
from service_release_acceptance_support import case_history
OUT=Path(os.environ.get('RELEASE_BROWSER_ARTIFACT_ROOT','.runtime/release-new-root/browser-artifacts'))


def test_actual_chromium_reviewed_compatible_release_and_independent_fresh_adoption(release_case):
    t=release_case;f=t['f'];calls=[];errors=[];proven={}
    with actual_http(t['app']) as (api,python_requests),sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx=browser.new_context();page=ctx.new_page()
        page.on('request',lambda r:calls.append(dict(method=r.method,path=urlsplit(r.url).path)))
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            base=str(api.base_url).rstrip('/');page.goto(base+'/template')
            page.wait_for_function('()=>status!==null')
            scope=t['a']['scope']
            page.locator('#template-park').fill(scope.park_id);page.locator('#template-park').dispatch_event('change')
            page.locator('#template-id').fill(scope.template_id);page.locator('#template-id').dispatch_event('change')
            def actor(name):
                page.locator('#template-actor').select_option(name)
                page.locator('#template-refresh').click();page.wait_for_function('()=>view!==null')
            def action(name,state):
                page.locator('#template-reason').fill('SYNTHETIC actual browser explicit '+name)
                page.locator('[data-template-action="'+name+'"]').click()
                page.wait_for_function('(state)=>!tp&&view?.state===state',arg=state)
            actor('template-author');action('RETURN_DRAFT','DRAFT')
            page.locator('#template-name').fill('SYNTHETIC actual browser compatible definition title')
            action('SAVE_DRAFT','DRAFT');action('SUBMIT','SUBMITTED')
            actor('template-reviewer');action('REVIEW','REVIEWED')
            actor('template-publisher')
            assert page.locator('[data-template-action="CANDIDATE_PUBLISH"]').is_disabled()
            page.locator('#template-reason').fill('SYNTHETIC actual publisher confirms compatible new release only')
            page.locator('#publication-preflight-read').click();page.wait_for_function('()=>!publicationReading&&publicationCheck!==null')
            assert page.evaluate('publicationCheck.can_publish===true&&publicationCheck.preflight.classification==="COMPATIBLE"')
            assert page.locator('[data-template-action="CANDIDATE_PUBLISH"]').is_disabled()
            # Commit succeeds at the real API; intentionally lose only the response transport.
            def lose(route):
                response=route.fetch();assert response.status==200;route.abort('failed')
            page.route('**/compatible-publications',lose)
            page.locator('#publication-confirm').check()
            page.locator('[data-template-action="CANDIDATE_PUBLISH"]').click()
            page.wait_for_function('()=>tp?.state==="UNKNOWN"&&publicationPending()!==null')
            key=page.evaluate('publicationPending().key')
            page.unroute('**/compatible-publications',lose)
            page.reload();page.wait_for_function('()=>status!==null')
            page.locator('#template-park').fill(scope.park_id);page.locator('#template-park').dispatch_event('change')
            page.locator('#template-id').fill(scope.template_id);page.locator('#template-id').dispatch_event('change')
            actor('template-publisher')
            assert page.evaluate('publicationPending().key')==key
            assert page.locator('[data-template-action="CANDIDATE_PUBLISH"]').is_disabled()
            before=len(calls);page.locator('#publication-recover').click()
            page.wait_for_function('()=>!publicationReading&&publicationPending()===null&&view?.state==="PUBLISHED"')
            assert all(c['method']=='GET' for c in calls[before:])
            assert len([c for c in calls if c['method']=='POST' and c['path'].endswith('/compatible-publications')])==1
            published=next(r for r in page.evaluate('view.releases') if r['state']=='PUBLISHED')
            release_id=published['release_id'];proven['real_dom_review_preflight_confirm_publish_and_cold_get']=True
            # Existing owned catalog-owner admission is an explicit fixture, not an end-user HTTP action.
            refs=admit_new(t,release_id);proven['catalog_admission_fixture']=True
            assert case_history(f[1],t['x']['p']['preparation_id'])==t['old']
            page.goto(base+'/');page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('change')
            page.locator('[data-tab="service"]').click()
            page.locator('#cold-directory-read').click();page.wait_for_function('()=>!coldBusy&&coldDirectory!==null')
            chosen=page.evaluate('coldDirectory.instances.find(i=>i.service_id==="synthetic-material-preparation").instance_id')
            page.locator('#cold-instance').select_option(chosen)
            for name,text in [('cold-goal','SYNTHETIC browser NEW_RELEASE independent request'),('cold-need','SYNTHETIC new release fresh need'),('cold-outline','SYNTHETIC new release fresh outline'),('cold-reason','SYNTHETIC explicit new release independent input')]:page.locator('#'+name).fill(text)
            for box in page.locator('input[data-cold-goal]').all():box.check()
            page.locator('#cold-prepare-confirm').check();page.locator('#cold-prepare').click()
            page.wait_for_function('()=>!coldBusy&&coldView!==null')
            for name in ['CREATE_RUN','CREATE_PREPARATION','SAVE_REQUEST','ADD_need_summary','ADD_material_outline']:
                assert page.locator('#cold-stage').input_value()==name
                if name!='CREATE_RUN':page.locator('#cold-stage-prepare').click();page.wait_for_function('()=>!coldBusy')
                assert page.locator('#cold-stage-send').is_disabled()
                page.locator('#cold-send-confirm').check();page.locator('#cold-stage-send').click();page.wait_for_function('()=>!coldBusy')
                if name=='CREATE_RUN':
                    work=f[0].claim('SYNTHETIC new Release browser original worker fixture');assert work;f[0].finish(work)
                    page.locator('#cold-recover').click();page.wait_for_function('()=>!coldBusy')
                assert page.evaluate('(name)=>coldCommitted(name)',name)
            prep_id=page.evaluate('coldView.product_observations.find(o=>o.name==="CREATE_PREPARATION").result.preparation_id')
            row=ok(api.get('/api/preparations/'+prep_id,headers=headers(f[2])));p={**row['preparation'],'preparation_id':prep_id}
            for k in ('run_id','case_id','preparation_id'):assert p[k]!=t['x']['p'][k]
            f[1].assign_status('executor-a',UUID(p['run_id']),active=True)
            http_f=f[:3]+(api,)
            for a,user in [('REVIEW','prep-specialist-fixture-a'),('CONFIRM','fixture-a')]:
                p=ok(material(http_f,p,a,user,reason='SYNTHETIC new Release browser input prerequisites'))
            page.locator('#cold-open').click();page.wait_for_function('(id)=>servicePlanId===id&&servicePlanView!==null',arg=prep_id)
            page.locator('#service-selection-read').click();page.wait_for_function('()=>!serviceSelectionBusy&&serviceSelectionCatalog!==null')
            page.locator('#service-selection-generate').click();page.wait_for_function('()=>!serviceSelectionBusy&&serviceSelectionView!==null')
            page.locator('#service-plan-reason').fill('SYNTHETIC independent adoption of new Release selection')
            assert not page.locator('#service-selection-confirm').is_checked()
            before=len(calls);page.locator('#service-plan-adopt').click()
            page.wait_for_function('()=>!servicePlanPending&&!activeEntryWriteFlow')
            assert not any(c['method']=='POST' for c in calls[before:])
            page.locator('#service-selection-confirm').check();page.locator('#service-plan-adopt').click()
            page.wait_for_function('()=>!servicePlanPending&&servicePlanView?.revision===1')
            with f[1].connect() as c:
                parent=c.execute('SELECT * FROM preparations WHERE id=%s',(prep_id,)).fetchone()
                assert not c.execute('SELECT 1 FROM case_resource_links WHERE preparation_id=%s',(prep_id,)).fetchone()
            from parkweave.service_selection_candidates import find
            plan=parent['service_case_plan'];saved=find(parent,plan['candidate_consumption']['candidate_id'])
            assert {r['release_id'] for r in saved['selection']['selections']}=={r['release_id'] for r,i in refs}
            assert len(plan['steps'])==5 and set(plan['required_goals'])==set(ALL_GOALS)
            assert case_history(f[1],t['x']['p']['preparation_id'])==t['old']
            proven['real_dom_five_cold_stages_generate_and_explicit_adopt']=True
            assert not errors
        finally:
            OUT.mkdir(parents=True,exist_ok=True)
            (OUT/('release-'+uuid4().hex[:10]+'.json')).write_text(json.dumps(dict(proven=proven,calls=calls,page_errors=errors,
                browser=browser.version,actual_html_http_asgi_owned_pg=True,python_requests=python_requests,
                fixture_steps=['catalog register/bind','local worker','new Run assignment','material REVIEW/CONFIRM','offline selection planner'],
                browser_scope='candidate revision to new Case ADOPT only; no downstream fulfillment or approval',real_model_calls=0),indent=2)+'\n')
            ctx.close();browser.close()


@pytest.mark.parametrize('mode',['late_edit','late_actor','storage_set','bad_receipt','not_observed','read_revoked','recovery_replaced'])
def test_current_publication_page_refuses_late_unknown_or_unrecoverable_confirmation(release_case,mode):
    t=release_case
    from release_new_case_support import reviewed_revision
    with actual_http(t['app']) as (api,_),sync_playwright() as pw:
        reviewed_revision(api,t)
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page();calls=[];page.on('request',lambda r:calls.append((r.method,urlsplit(r.url).path)))
        try:
            page.goto(str(api.base_url).rstrip('/')+'/template');page.wait_for_function('()=>status!==null')
            for id,value in [('template-park',t['a']['scope'].park_id),('template-id',t['a']['scope'].template_id)]:
                page.locator('#'+id).fill(value);page.locator('#'+id).dispatch_event('change')
            page.locator('#template-actor').select_option('template-publisher');page.locator('#template-refresh').click()
            page.wait_for_function('()=>view?.state==="REVIEWED"')
            page.locator('#template-reason').fill('SYNTHETIC explicit negative publication probe')
            if mode.startswith('late_'):
                page.evaluate('''()=>{const original=fetch;window.holdPreflight=null;window.preflightArrived=false;window.fetch=async(...args)=>{const response=await original(...args);if(String(args[0]).endsWith('/publication-preflight')){window.preflightArrived=true;await new Promise(resolve=>window.holdPreflight=resolve);}return response;};}''')
                page.locator('#publication-preflight-read').click();page.wait_for_function('()=>window.preflightArrived')
                if mode=='late_edit':page.locator('#template-name').fill('SYNTHETIC changed unsaved display')
                else:page.locator('#template-actor').select_option('template-reader')
                page.evaluate('()=>window.holdPreflight()')
                page.wait_for_function('()=>!publicationReading')
                # Wait for actual delayed continuation, not a fabricated backend DTO.
                page.wait_for_timeout(80)
                assert page.evaluate('publicationCheck===null')
                assert page.locator('[data-template-action="CANDIDATE_PUBLISH"]').is_disabled()
            else:
                page.locator('#publication-preflight-read').click();page.wait_for_function('()=>!publicationReading&&publicationCheck!==null')
                if mode=='not_observed':
                    page.evaluate('''()=>{const c=publicationCheck;localStorage.setItem(publicationLocation(),JSON.stringify({key:crypto.randomUUID(),definition:view.definition_sha256,revision:view.revision,preflight:c.preflight_sha256}));buttons();}''')
                    page.locator('#publication-recover').click();page.wait_for_function('()=>!publicationReading')
                    assert page.evaluate('publicationPending()!==null')
                else:
                    page.locator('#publication-confirm').check()
                    if mode=='storage_set':
                        page.evaluate('''()=>{Storage.prototype.setItem=function(){};}''')
                        page.locator('[data-template-action="CANDIDATE_PUBLISH"]').click()
                        page.wait_for_function('()=>document.getElementById("template-error").textContent.includes("未发送")')
                    else:
                        def lose(route):
                            response=route.fetch();assert response.status==200;route.abort('failed')
                        page.route('**/compatible-publications',lose)
                        page.locator('[data-template-action="CANDIDATE_PUBLISH"]').click()
                        page.wait_for_function('()=>tp?.state==="UNKNOWN"')
                        page.unroute('**/compatible-publications',lose)
                        if mode=='bad_receipt':
                            def damaged(route):
                                response=route.fetch();assert response.status==200
                                body=response.json();body['event']['action']='UNKNOWN_ACTION'
                                route.fulfill(response=response,json=body)
                            page.route('**/compatible-publications/*',damaged)
                        elif mode=='read_revoked':
                            config=t['engine'].config;config.revision+=1
                            for permit in config.permits:
                                if permit.principal_id=='template-publisher' and 'READ' in permit.actions:permit.actions.remove('READ')
                            t['engine'].replace_contract(config)
                        if mode=='recovery_replaced':
                            page.evaluate('''()=>{const original=fetch;window.recoveryArrived=false;window.holdRecovery=null;window.fetch=async(...args)=>{const response=await original(...args);if(String(args[0]).includes('/compatible-publications/')){window.recoveryArrived=true;await new Promise(resolve=>window.holdRecovery=resolve);}return response;};}''')
                        before=len(calls);page.locator('#publication-recover').click()
                        if mode=='recovery_replaced':
                            page.wait_for_function('()=>window.recoveryArrived')
                            replaced=page.evaluate('''()=>{const h=publicationPending();h.key=crypto.randomUUID();localStorage.setItem(publicationLocation(),JSON.stringify(h));window.holdRecovery();return h.key;}''')
                        page.wait_for_function('()=>!publicationReading')
                        if mode=='recovery_replaced':assert page.evaluate('publicationPending().key')==replaced
                        assert all(method=='GET' for method,path in calls[before:])
                        assert page.evaluate('publicationPending()!==null')
                    assert page.locator('[data-template-action="CANDIDATE_PUBLISH"]').is_disabled() or mode=='storage_set'
            posts=[p for m,p in calls if m=='POST']
            assert len(posts)==(1 if mode in ('bad_receipt','read_revoked','recovery_replaced') else 0)
            assert case_history(t['f'][1],t['x']['p']['preparation_id'])==t['old']
        finally:
            page.unroute_all(behavior='wait');browser.close()
