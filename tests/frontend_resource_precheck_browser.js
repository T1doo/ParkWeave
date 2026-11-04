// Original precheck handler with a synthetic read-only POST response. No holds.
async (page) => {
  const check=(ok,message)=>{if(!ok)throw Error(message);};
  const requests=[];
  page.on('request',r=>{if(r.method()!=='GET')requests.push({method:r.method(),path:new URL(r.url()).pathname});});
  await page.setViewportSize({width:1440,height:900});
  await page.goto('http://127.0.0.1:8876/web.html');
  await page.locator('#token').fill('SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY');
  await page.locator('[data-tab=resource]').click();
  await page.locator('#resource-catalog').click();
  await page.locator('#resource-form').waitFor();
  const id=await page.locator('#resource-select').inputValue();
  let available=true;
  const url='http://127.0.0.1:8876/api/synthetic-resources/'+id+'/preview';
  await page.route(url,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
    resource_id:id,resource_revision:1,resource_name:'合成测试资源',scope:'SYNTHETIC_LOCAL_RESOURCE_HOLD_ONLY',namespace:'SYNTHETIC',preview_only:true,authority:'LOCAL_AUTHORITY',timezone:'UTC',external_availability:'UNKNOWN',confirmation_required:true,reservation:'NOT_CONFIRMED',external_acceptance:'NOT_SUBMITTED',offline_fulfillment:'NO_EVIDENCE',available,occupied_peak:available?0:3,capacity:3,available_quantity:available?3:0,source:{kind:'SYNTHETIC',id:'ui-precheck-fixture',revision:1,statement:'仅用于只读预检界面回归'},server_time:'2026-10-26T12:00:00Z'
  })}));
  await page.locator('#resource-preview').click();
  await page.waitForFunction(()=>!document.querySelector('#resource-hold').disabled);
  check((await page.locator('#resource-preview-result').innerText()).includes('尚未占位'),'available preview is presented as a hold');
  check((await page.locator('#park-resource-summary').innerText()).includes('已选组合 0 项'),'preview changed hold selection');
  await page.locator('.v2-precheck-evidence>summary').click();
  check((await page.locator('.v2-precheck-evidence').innerText()).includes('NOT_CONFIRMED'),'source reservation boundary lost');
  await page.locator('#resource-quantity').fill('2');
  check(await page.locator('#resource-hold').isDisabled(),'edit did not invalidate hold eligibility');
  check(await page.locator('.v2-precheck-evidence').isHidden(),'old precheck evidence remains current after edit');
  available=false;
  await page.locator('#resource-preview').click();
  await page.waitForFunction(()=>document.querySelector('#resource-preview-result').textContent.includes('当前区间容量不足'));
  check(await page.locator('#resource-hold').isDisabled(),'unavailable interval enabled holding');
  await page.unroute(url);
  check(requests.length===2 && requests.every(r=>r.method==='POST'&&r.path.endsWith('/preview')),'unexpected mutation path');
  return {scope:'synthetic responses to original read-only precheck POST',availableDoesNotHold:true,selectedHolds:0,editInvalidatesPreview:true,unavailableDisablesHold:true,readOnlyRequests:requests,holdRequests:0};
}
