// Real browser rendering of original handlers with explicitly synthetic input.
// The preparation read intentionally fails its secondary HTTP checks: no READY
// state, permission or business success is fabricated to obtain the screenshot.
async (page) => {
  const check=(value,message)=>{if(!value)throw Error(message);};
  const writes=[],errors=[];
  page.on('request',r=>{if(r.method()!=='GET')writes.push(r.url());});
  page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width:1440,height:900});
  await page.goto('http://127.0.0.1:8876/web.html');
  await page.locator('#token').fill('SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY');
  await page.locator('[data-tab=collaboration]').click();
  await page.waitForTimeout(250);
  await page.screenshot({path:'E:/Github/ParkWeave/docs/design/evidence/frontend-polish-20261104/workspace-after-collaboration.png'});
  const snapshot={
    preparation:{id:'11111111-1111-4111-8111-111111111111',case_id:'22222222-2222-4222-8222-222222222222',run_id:'33333333-3333-4333-8333-333333333333',goal:'合成视觉测试 · 企业活动场地与设备协调',state:'IN_PREPARATION',revision:3,owner_id:'synthetic-enterprise',reviewer_id:'synthetic-specialist',service_id:'synthetic-material-preparation',service_version:1,required_goals:['核对活动资料'],planning_constraints:[]},
    current_materials:[{id:'material-a',slot:'need_summary',version:2,text:'计划安排一场企业交流活动，需协调会议空间与展示设备。\n时间、容量及责任安排仍待核对。',source_kind:'USER_STATEMENT',source_label:'合成企业自述 · 仅用于视觉测试'},{id:'material-b',slot:'material_outline',version:1,text:'活动议程.txt\n设备需求.csv\n文件可读，不代表条件已满足。',source_kind:'DOCUMENT_EXCERPT',source_label:'合成资料目录 · 真实性尚未核实'}],
    material_history:[],history:[{revision:3,action:'ADD_EVIDENCE',payload:{actor_id:'synthetic-enterprise',reason:'合成视觉测试：追加活动说明'}}]
  };
  const readError=await page.evaluate(async snapshot=>{try{await loadPreparation(snapshot.preparation.id,{role:'park_specialist',verifiedSnapshot:snapshot});return null;}catch(e){return e.message;}},snapshot);
  check(!!readError,'fixture must not claim a completed read');
  check(await page.locator('#prep-read-status').getAttribute('data-state')==='INVALID','invalid read not retained');
  check(await page.locator('#prep-materials > article').count()===2,'original renderer did not render both materials');
  check(await page.locator('#prep-review').isDisabled(),'incomplete read enabled a business action');
  await page.locator('#park-main').evaluate(e=>e.scrollTop=0);
  await page.locator('#prep-detail').evaluate(e=>e.scrollTop=0);
  await page.waitForTimeout(250);
  await page.waitForFunction(()=>{
    const a=document.querySelector('.v2-master').getBoundingClientRect();
    const b=document.querySelector('.v2-detail-stack').getBoundingClientRect();
    return Math.abs(a.y-b.y)<1;
  });
  const list=await page.locator('.v2-master').boundingBox(),detail=await page.locator('.v2-detail-stack').boundingBox(),utility=await page.locator('.atelier-utilities').boundingBox();
  check(detail.x>=list.x+list.width,'list and detail overlap');
  check(Math.abs(detail.y-list.y)<2,'list and detail do not share top alignment');
  check(utility===null,'inactive global utility panel distracts from the current detail');
  await page.screenshot({path:'E:/Github/ParkWeave/docs/design/evidence/frontend-polish-20261104/workspace-after-detail-synthetic.png'});
  const reader=page.locator('#prep-materials .design-preview-trigger').first();
  await reader.click();
  check(await page.locator('#park-material-preview').isVisible(),'material preview not visible');
  check((await page.locator('#park-material-preview').innerText()).includes('时间、容量及责任安排仍待核对'),'material context missing');
  check((await page.locator('#park-material-preview').innerText()).includes('来源有效期'),'full provenance metadata missing from reader');
  await page.keyboard.press('Escape');
  check(await reader.evaluate(e=>e===document.activeElement),'reader did not return focus');
  await page.locator('#prep-detail .design-detail-nav a[href="#prep-history"]').click();
  check(await page.locator('#prep-history').isVisible(),'history view not visible');
  check(!await page.locator('#prep-materials').isVisible(),'materials leak into history view');
  await page.locator('#prep-detail .design-detail-nav a[href="#prep-summary"]').click();
  check(await page.locator('#service-plan-prepare').isVisible(),'overview does not expose original plan entry');
  check(await page.locator('#prep-review').isDisabled(),'tab change bypassed read guard');
  await page.locator('#prep-detail .design-detail-nav a[href="#prep-materials"]').click();
  check(await page.locator('#prep-materials > article').count()===2,'view changes lost material content');
  await page.locator('#manual-goal-status').evaluate(e=>e.textContent='SYNTHETIC: 原请求结果待核对');
  await page.waitForTimeout(200);
  check(await page.locator('.atelier-utilities').isVisible(),'active recovery tool is hidden');
  const recoveryBox=await page.locator('.atelier-utilities').boundingBox();
  check(recoveryBox.width>list.width*2,'recovery tool squeezed into left column');
  for(const width of [1024,768,375,320]){
    await page.setViewportSize({width,height:900});
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'detail horizontal overflow at '+width);
  }
  await page.emulateMedia({reducedMotion:'reduce'});
  check(await page.locator('body').evaluate(e=>getComputedStyle(e,'::before').animationName)==='none','ambient animation ignores reduced motion');
  await page.emulateMedia({reducedMotion:'no-preference'});
  check(!writes.length,'visual fixture sent a write');
  check(!errors.length,'uncaught browser error '+errors.join(', '));
  return {scope:'original HTML and original preparation renderer; explicitly synthetic snapshot; secondary HTTP reads fail by design',readError,materials:2,readState:'INVALID',businessReviewDisabled:true,masterDetailAligned:true,focusedViews:true,recoveryToolRevealsFullWidth:true,readerEscapeFocus:true,widths:[1440,1024,768,375,320],writes,errors};
}
