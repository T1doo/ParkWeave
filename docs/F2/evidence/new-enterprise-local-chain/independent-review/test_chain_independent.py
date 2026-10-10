"""Independent actual HTTP/PG and browser oracles for new local Cases."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import hashlib,json
import pytest
from conftest import fixture,pg
from playwright.sync_api import sync_playwright
from parkweave.api import create_app
from parkweave.store import Store
from test_new_enterprise_local_chain import (fresh_chain,link_fixture,receipt_fixture,preparation_fixture,
    publish,new_case,enable_approval,material_decision,verify,request_access,holds,delivery,acceptance,
    call,parent,original_rows,permission_snapshot,actual_http,ALL_GOALS,headers)
from test_new_enterprise_local_chain_browser import template_page,cold_product,prepare_page

OUT=Path('/workspace/ParkWeave/.runtime/independent-new-enterprise-chain-review/oracles')

def save(name,data):
    OUT.mkdir(parents=True,exist_ok=True);(OUT/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')

def result(u,row,goal):
    view=call(u,'/api/preparations/'+row['preparation_id']+'/goal-results')
    return view,next(x for x in view['results'] if x['goal']==goal)

def test_actual_report_requires_current_ack_and_owner_verify_not_technical_success(fresh_chain):
    u=fresh_chain;release=publish(u);row=new_case(u,release);second=new_case(u,release,number=9)
    enable_approval(u,[row,second]);material_decision(u,row,'REVIEW');material_decision(u,row,'CONFIRM');verify(u,row,'P1')
    request_access(u,row);request_access(u,row,action='APPROVE');_,data=holds(u);sent,key=delivery(u,row,data);verify(u,row,'P2')
    dispatch=acceptance(u,row);verify(u,row,'P3');path='/api/executor-receipts/'+dispatch['receipt_step_id']
    view=call(u,path,actor='executor-a')
    report=call(u,path+'/execute-local',actor='executor-a',data=dict(expected_revision=view['step']['revision'],reason='SYNTHETIC independent actual report'))
    receipt=report['current_receipt'];assert receipt['adapter_execution']['report']['binding']['case_id']==row['case_id']
    assert call(u,'/api/runs/'+row['run_id'])['state']=='SUCCEEDED'
    goal='LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT';before=original_rows(u,row);v,r=result(u,row,goal)
    assert r['state']!='LOCAL_OUTPUT_VERIFIED' and not v['case_goal_completed'] and original_rows(u,row)==before
    call(u,path+'/commands',data=dict(action='ACKNOWLEDGE',expected_revision=report['step']['revision'],receipt_sha256=receipt['source_sha256'],reason='SYNTHETIC independent actual ACK'))
    v,r=result(u,row,goal);assert r['state']!='LOCAL_OUTPUT_VERIFIED'
    verify(u,row,'P4');v,r=result(u,row,goal);assert r['state']=='LOCAL_OUTPUT_VERIFIED'
    assert r['actual_output']['execution_id']==receipt['adapter_execution']['report']['execution_id']
    first=original_rows(u,row);other,missing=result(u,second,goal)
    assert missing['state']!='LOCAL_OUTPUT_VERIFIED' and not other['case_goal_completed']
    assert call(u,'/api/service-dispatches/catalog?preparation_id='+second['preparation_id'],actor='prep-specialist-fixture-a')['executors']==[]
    assert original_rows(u,row)==first and permission_snapshot(u['f'][1])==u['permissions']
    # Source changes retain the historical report, but cannot keep the old current proof.
    material_decision(u,row,'REOPEN');p=parent(u,row)
    call(u,'/api/preparations/'+row['preparation_id']+'/commands',data=dict(action='ADD_EVIDENCE',expected_revision=p['revision'],slot='need_summary',text='SYNTHETIC independent changed current materials',source_kind='USER_STATEMENT',source_label='Explicit current replacement'))
    changed=original_rows(u,row);v,r=result(u,row,goal)
    assert r['state']!='LOCAL_OUTPUT_VERIFIED' and original_rows(u,row)==changed
    assert changed['service_step_receipts']==first['service_step_receipts'] and not v['case_goal_completed']
    save('ack-proof',dict(actual_http=True,actual_pg=True,technical_succeeded_did_not_satisfy_goal=True,
        actual_report_required_current_ack_and_verify=True,new_case_not_authorized_by_old_lease=True,
        old_report_retained_after_new_material=True,permission_rows_unchanged=True))

def test_actual_fresh_store_default_routes_cannot_write_fixture_approval_or_execute(fresh_chain):
    u=fresh_chain;release=publish(u);row=new_case(u,release);before=original_rows(u,row)
    with actual_http(create_app(Store(u['f'][0].dsn))) as (client,requests):
        h=headers(u['f'][2]);assert client.get('/template',headers=h).status_code==404
        assert client.get('/api/template-candidate/status',headers=h).status_code==404
        assert client.get('/api/preparations/'+row['preparation_id']+'/plan-approval',headers=h).status_code==403
        response=client.get('/api/runs/'+row['run_id']+'/access',headers=h);assert response.status_code==403
        # This is a fresh Store/default factory, not a claimed API process restart.
        assert client.get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=h).status_code==200
    assert original_rows(u,row)==before and permission_snapshot(u['f'][1])==u['permissions']

@pytest.mark.parametrize('target,expected',[
 ('LOCAL_MATERIAL_PREPARATION',['P1']),('LOCAL_CASE_RESOURCE_ASSOCIATION',['P1','P2']),
 ('LOCAL_INTERNAL_ACCEPTANCE',['P1','P2','P3']),('LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT',['P1','P2','P3','P4']),
 ('LOCAL_SYNTHETIC_COORDINATION_RECORDS',['P1','P2','P3','P4']),('LOCAL_CASE_RECORD_RECHECK',['P1','P2','P3','P4','P5'])])
def test_each_author_target_has_exact_original_closure_not_hidden_optional_goals(fresh_chain,target,expected):
    u=fresh_chain
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=template_page(browser,u,320)
        try:
            for el in page.locator('[data-template-goal]:checked').all():el.uncheck()
            page.locator('[data-template-goal="'+target+'"]').check();page.locator('[data-template-action="SAVE_DRAFT"]').click()
            page.wait_for_function('()=>tp===null&&view?.revision===1')
            assert page.evaluate('view.draft.required_goals')==[target]
            assert page.evaluate('view.draft.steps.map(s=>s.id)')==expected
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert permission_snapshot(u['f'][1])==u['permissions']
        finally:ctx.close();browser.close()

@pytest.mark.parametrize('damage',['wrong-goal-map','reversed-registry','cycle'])
def test_modified_status_cannot_register_or_drop_actual_dependencies(fresh_chain,damage):
    u=fresh_chain
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=template_page(browser,u)
        try:
            for el in page.locator('[data-template-goal]:checked').all():el.uncheck()
            page.locator('[data-template-goal="LOCAL_CASE_RECORD_RECHECK"]').check();posts=[]
            page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
            if damage=='wrong-goal-map':page.evaluate('()=>status.goal_adapters.LOCAL_CASE_RECORD_RECHECK="P1"')
            elif damage=='reversed-registry':page.evaluate('()=>status.registered_steps.reverse()')
            else:page.evaluate('()=>status.registered_steps[0].depends_on=["P5"]')
            page.locator('[data-template-action="SAVE_DRAFT"]').click()
            page.wait_for_function('()=>tp===null&&document.querySelector("#template-error").textContent.length>0')
            assert len(posts)==(0 if damage=='cycle' else 1) and page.evaluate('view.revision')==0
            assert u['engine'].public_catalog('park-a')['items']==[] and permission_snapshot(u['f'][1])==u['permissions']
        finally:ctx.close();browser.close()

def test_late_old_author_post_cannot_replace_reloaded_new_context_selection(fresh_chain):
    u=fresh_chain
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=template_page(browser,u)
        try:
            for goal in ALL_GOALS:page.locator('[data-template-goal="'+goal+'"]').check()
            page.evaluate('''()=>{const real=fetch;window.releaseOld=null;window.arrived=false;window.fetch=async(...args)=>{const r=await real(...args);if(args[1]?.method==='POST'){window.arrived=true;await new Promise(resolve=>window.releaseOld=resolve);}return r;};}''')
            page.locator('[data-template-action="SAVE_DRAFT"]').click();page.wait_for_function('()=>window.arrived')
            page.locator('#template-actor').select_option('template-reviewer');assert page.locator('[data-template-goal]:checked').count()==0
            page.locator('#template-actor').select_option('template-author');page.locator('#template-refresh').click();page.wait_for_function('()=>view?.revision===1')
            selected=page.evaluate('JSON.stringify(view)');page.evaluate('()=>window.releaseOld()');page.wait_for_timeout(150)
            assert page.evaluate('JSON.stringify(view)')==selected and page.evaluate('tp===null')
            assert len(page.evaluate('view.history'))==1 and page.locator('[data-template-goal]:checked').count()==6
        finally:ctx.close();browser.close()

@pytest.mark.parametrize('damage',['key-reorder','array-order','scalar-type','nested-missing'])
def test_strict_actual_review_pair_preserves_structure_and_array_order(fresh_chain,damage):
    u=fresh_chain;row=new_case(u,publish(u));path='/api/preparations/'+row['preparation_id'];requests=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=cold_product(browser,u,'prep-specialist-fixture-a')
        try:
            prepare_page(page,row,'park_specialist')
            # Fault injection modifies only HTTP views of a committed original event.
            # The synthetic array extension checks the comparator's explicit array rule;
            # it is not claimed to be a new persisted source or allowed domain field.
            def command(route):
                response=route.fetch();assert response.status==200;body=response.json()
                if damage=='array-order':body['delivery_review_source']['oracle_array']=['synthetic-a','synthetic-b']
                route.fulfill(response=response,json=body)
            def saved(route):
                response=route.fetch();assert response.status==200;body=response.json()
                for event in body['history']:
                    if event['action']!='REVIEW':continue
                    source=event['payload']['delivery_review_source']
                    if damage=='key-reorder':event['payload']['delivery_review_source']=dict(reversed(list(source.items())))
                    elif damage=='array-order':source['oracle_array']=['synthetic-b','synthetic-a']
                    elif damage=='scalar-type':event['payload']['revision']=str(event['payload']['revision'])
                    else:source.pop('authority_sha256')
                route.fulfill(response=response,json=body)
            page.route('**'+path+'/commands',command);page.route('**'+path,saved)
            page.on('request',lambda r:requests.append((r.method,r.url)))
            page.locator('#prep-reason').fill('SYNTHETIC independent nested event integrity');page.locator('#prep-review').click()
            if damage=='key-reorder':
                page.wait_for_function('()=>prepCommandPending===null&&preparationView?.preparation.state==="REVIEWED"')
            else:
                page.wait_for_function('()=>prepCommandPending?.state==="UNKNOWN"')
                assert page.locator('#prep-review').is_disabled()
            actual=call(u,path,actor='prep-specialist-fixture-a');reviewed=[e for e in actual['history'] if e['action']=='REVIEW']
            assert len(reviewed)==1 and actual['preparation']['state']=='REVIEWED'
            assert 'oracle_array' not in reviewed[0]['payload']['delivery_review_source']
            assert sum(m=='POST' for m,url in requests)==1 and permission_snapshot(u['f'][1])==u['permissions']
            save('strict-'+damage,dict(actual_http=True,pg=True,chromium=True,committed_review_events=1,
                classification='ACCEPTED_EQUIVALENT' if damage=='key-reorder' else 'UNKNOWN_MISMATCH',
                paired_array_extension_only=damage=='array-order',persistent_source_unchanged=True,automatic_posts=0))
        finally:ctx.close();browser.close()
