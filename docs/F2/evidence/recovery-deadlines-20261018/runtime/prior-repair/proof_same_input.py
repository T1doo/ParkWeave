"""Defect reproduction only: passing means the old bad behavior was observed."""
from pathlib import Path
import json,hashlib
from uuid import uuid4
from urllib.parse import urlparse
import pytest
from playwright.sync_api import sync_playwright,expect
from test_service_plan_recovery_browser import prep,link_fixture,receipt_fixture,preparation_fixture,read,step,snapshot
from test_native_preparation_entry_browser import ordinary_process
from test_material_file_import_browser import browser_page
R=Path('/workspace/ParkWeave/.runtime/ttl-template-repair-20261017')

@pytest.mark.parametrize('expires',[0,999999999999999],ids=['expired','future'])
def test_reproduce_same_original_handle_on_exact_baseline_and_current(link_fixture,tmp_path,expires):
 f=link_fixture;p=prep(f,'VERIFY');x=read(f,p).json()
 h=dict(v=1,id=p['preparation_id'],key=str(uuid4()),actor=x['actor_ref'],case=x['case_id'],run=x['run_id'],
        action='VERIFY',plan=x['plan_id'],step=step(x,'P1')['id'],revision=x['revision'],expires=expires)
 raw=json.dumps(h,separators=(',',':'));name='parkweave.service-plan-recovery.v1.'+h['id']+'.'+h['actor'];before=snapshot(f);records=[]
 with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
  for version in ['baseline','current']:
   html=(R/(version+'-web.html')).read_bytes();browser,context,page=browser_page(pw);calls=[];errors=[]
   def route_document(route):
    if urlparse(route.request.url).path=='/':route.fulfill(status=200,content_type='text/html',body=html)
    else:route.continue_()
   page.route('**/*',route_document);page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('request',lambda q:calls.append({'path':urlparse(q.url).path,'method':q.method,'key':q.headers.get('idempotency-key')}))
   page.goto(str(api.base_url)+'?preparation_id='+h['id']);page.evaluate('([name,raw])=>localStorage.setItem(name,raw)',[name,raw])
   page.locator('#token').fill(f[2]['fixture-a']);page.locator('#existing-preparation-read').click()
   expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录',timeout=15000)
   page.locator('#service-plan-prepare').click();expect(page.locator('#service-plan-feedback')).to_contain_text('尚未观察到',timeout=15000)
   observed=page.evaluate('servicePlanRecoveryHandle');stored=page.evaluate('(name)=>localStorage.getItem(name)',name)
   assert observed is not None and observed['key']==h['key'] and observed['expires']==expires
   assert stored==raw and any(q['key']==h['key'] and q['method']=='GET' for q in calls)
   assert all(q['method']=='GET' for q in calls) and snapshot(f)==before and not errors
   records.append(dict(version=version,html_sha256=hashlib.sha256(html).hexdigest(),same_input_sha256=hashlib.sha256(raw.encode()).hexdigest(),handle=h,
                       defect_observed='expired_or_future_handle_accepted_and_keyed_recovery_GET_sent',requests=calls,business_snapshot_unchanged=True,POSTs=0))
   context.close();browser.close()
 assert records[0]['same_input_sha256']==records[1]['same_input_sha256']
 (R/('same-input-ttl-'+str(expires)+'.json')).write_text(json.dumps(records,indent=2)+'\n')
