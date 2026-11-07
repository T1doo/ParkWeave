// Browser integration for the shipped v2 module. List/detail fixtures below are
// explicit HTTP mocks; resource states use the real read-only loopback server.
// No database, authenticated user, committed mutation or business success claim.
async (page) => {
  const results=[],errors=[],writes=[];
  const check=(ok,message)=>{if(!ok)throw Error(message);};
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{if(request.method()!=='GET')writes.push({method:request.method(),url:request.url()});});
  const base='http://127.0.0.1:8876';
  const output='E:/Github/ParkWeave/docs/product-closure-20261105/evidence/g1b/';
  const desktopSizes=[{width:1280,height:800},{width:1440,height:900},{width:1920,height:1080}];
  const pageLayouts=[];
  const inspectDesktop=async name=>{
    for(const viewport of desktopSizes){
      await page.setViewportSize(viewport);
      check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),name+' overflows at '+viewport.width);
      pageLayouts.push({page:name,...viewport});
    }
    await page.setViewportSize({width:1440,height:900});
  };
  await page.setViewportSize({width:1440,height:900});
  await page.goto(base+'/web.html');
  await page.evaluate(()=>{for(const [key,value] of Object.entries({theme:'ink',density:'comfortable',ambient:'off',effects:'glass'}))localStorage.setItem('parkweave.appearance.'+key,value);});await page.reload();
  check(await page.locator('body').getAttribute('data-workspace-design')==='2','v2 module did not initialize');
  const goal=page.locator('#prep-goal');
  await goal.fill('合成测试：安排交流活动，场地和设备需在同一时间可用。');
  await page.locator('#prep-catalog').click();
  await page.waitForFunction(()=>['ERROR','UNAVAILABLE'].includes(document.querySelector('#prep-catalog-status').dataset.state));
  check((await goal.inputValue()).includes('同一时间'),'catalog failure lost the goal');
  check(await goal.evaluate(e=>e.form.id)==='prep-create','goal lost original form ownership');
  await goal.fill('');
  await page.reload();
  await inspectDesktop('service');
  await page.mouse.move(1400,30);await page.waitForTimeout(180);
  await page.screenshot({path:output+'after-service.png'});
  results.push('Service: original catalog failure retains goal; goal still belongs to original form');

  await page.locator('#token').fill('SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY');
  await page.locator('[data-tab=resource]').click();
  await page.locator('#resource-catalog').click();
  await page.locator('#resource-form').waitFor();
  await inspectDesktop('resource');
  check(await page.locator('.v2-constraints').isVisible(),'resource constraints are not visible');
  check(!await page.locator('#resource-catalog-view').isVisible(),'technical catalog metadata competes with form');
  check(await page.locator('#resource-select').evaluate(e=>e.labels[0].textContent)==='资源','resource picker has no correct label');
  check(await page.locator('#resource-hold').evaluate(e=>e.form.id)==='resource-form','hold lost original form');
  check(await page.locator('#resource-hold').isDisabled(),'catalog read enabled holding without precheck');
  check((await page.locator('#park-resource-summary').innerText()).includes('正在填写（未计入组合）'),'draft is presented as selection');
  check((await page.locator('#park-resource-summary').innerText()).includes('已选占位组合 0 项'),'draft changed selected hold count');
  await page.locator('#resource-quantity').fill('2');
  check((await page.locator('#park-resource-summary').innerText()).includes('2 份'),'draft summary did not update');
  await page.locator('#resource-quantity').fill('1');
  await page.getByRole('button',{name:'资源详情与完整名称',exact:true}).focus();
  await page.keyboard.press('Enter');
  await page.locator('#resource-catalog-view').waitFor();
  check((await page.locator('#resource-catalog-view').innerText()).includes('不是可用性或真实预约证明'),'full resource name not available');
  await page.getByRole('button',{name:'返回资源表单',exact:true}).click();
  check(await page.locator('#resource-select').evaluate(e=>e===document.activeElement),'resource detail return lost focus');
  await page.locator('.v2-resource-details>summary').click();
  await page.getByRole('button',{name:'选择开始日期',exact:true}).click();
  await page.keyboard.press('ArrowRight');await page.keyboard.press('Escape');
  check(await page.getByRole('button',{name:'选择开始日期',exact:true}).evaluate(e=>e===document.activeElement),'calendar Escape did not return focus');
  await page.locator('#park-main').evaluate(e=>e.scrollTop=0);await page.mouse.move(1400,30);
  await page.screenshot({path:output+'after-resource.png'});
  results.push('Resource: visible constraints, keyboard-accessible full name, UTC unchanged, draft/selected holds separated, precheck required');

  const p={id:'11111111-1111-4111-8111-111111111111',case_id:'22222222-2222-4222-8222-222222222222',run_id:'33333333-3333-4333-8333-333333333333',goal:'合成测试 · 企业交流活动资料核对',state:'IN_PREPARATION',revision:3,owner_id:'synthetic-enterprise',reviewer_id:'synthetic-specialist',service_id:'synthetic-material-preparation',service_version:1};
  const p2={...p,id:'44444444-4444-4444-8444-444444444444',case_id:'55555555-5555-4555-8555-555555555555',run_id:'66666666-6666-4666-8666-666666666666',goal:'合成测试 · 展示设备需求资料准备'};
  const snapshot={preparation:p,current_materials:[
    {id:'material-a',slot:'need_summary',version:2,text:'计划组织企业交流活动，需要协调会议空间和展示设备。\n期望时段：待确认。\n必要条件：场地和设备须同时可用。',source_kind:'USER_STATEMENT',source_label:'合成企业提供 · 视觉测试'},
    {id:'material-b',slot:'material_outline',version:1,text:'活动议程.txt\n设备需求.csv\n材料可读，真实性和资格仍待核验。',source_kind:'DOCUMENT_EXCERPT',source_label:'合成资料目录 · 视觉测试'}
  ],material_history:[],history:[{revision:3,action:'ADD_EVIDENCE',payload:{actor_id:'synthetic-enterprise',reason:'合成测试：追加活动说明'}}]};
  const listRoute=base+'/api/preparations';
  let listMode='ready';
  await page.route(listRoute,route=>{
    if(listMode==='error')return route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'SYNTHETIC_LIST_FAILURE'})});
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({role:'park_specialist',items:listMode==='empty'?[]:[p,p2]})});
  });
  for(const record of [p,p2])await page.route(base+'/api/preparations/'+record.id,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...snapshot,preparation:record})}));
  await page.locator('[data-tab=collaboration]').click();
  check(await page.locator('.v2-category-panel:visible').count()===1,'categories are still a card wall');
  check((await page.locator('.v2-category-panel:visible').innerText()).includes('尚未读取'),'unread state absent');
  await page.locator('#workspace-category-tab-preparation').focus();await page.keyboard.press('ArrowRight');
  check(await page.locator('#workspace-category-tab-dispatch').getAttribute('aria-selected')==='true','category keyboard navigation failed');
  await page.keyboard.press('Home');
  await page.locator('#prep-list').click();
  await page.locator('#prep-items>button').first().waitFor();
  check(await page.locator('#prep-items>button').count()===2,'original preparation list did not render fixtures');
  await page.locator('#park-collaboration-search').fill('不会匹配的条件');
  await page.waitForFunction(()=>[...document.querySelectorAll('#prep-items>button')].every(e=>e.classList.contains('design-filtered')));
  check((await page.locator('.v2-category-panel:visible .v2-empty').innerText()).includes('没有匹配'),'filtered-empty state is not explained');
  await page.locator('#park-collaboration-search').fill('');
  await inspectDesktop('collaboration');
  await page.mouse.move(1400,30);await page.waitForTimeout(200);
  await page.screenshot({path:output+'after-collaboration.png'});
  const firstRecordY=(await page.locator('#prep-items>button').first().boundingBox()).y;
  results.push('Collaboration: classified original lists; unread/filtered states; keyboard category navigation; scoped read buttons');
  await page.locator('#park-collaboration-search').fill('合成测试');

  await page.locator('#prep-items>button').first().click();
  await page.waitForFunction(()=>document.querySelector('#prep-read-status').dataset.state==='INVALID');
  check(await page.locator('body').getAttribute('data-v2-detail')==='true','detail mode did not open');
  check(!await page.locator('#collaboration').isVisible(),'full workspace was squeezed into detail sidebar');
  check(await page.locator('.v2-master-list>button').count()===2,'dedicated master list did not retain loaded records');
  check(await page.locator('#prep-review').isDisabled(),'failed secondary read enabled review');
  check(await page.locator('#prep-summary .workspace-case-goal').evaluate(e=>e===document.activeElement),'opening detail did not move focus into the current case');
  check(await page.locator('#prep-refresh').isVisible(),'refresh missing next to invalid-read warning');
  check(await page.locator('#prep-refresh').evaluate(e=>e.closest('.v2-read-state')===document.querySelector('#prep-read-status').closest('.v2-read-state')),'refresh is not adjacent to read warning');
  const master=await page.locator('.v2-master').boundingBox(),stack=await page.locator('.v2-detail-stack').boundingBox();
  check(stack.x>=master.x+master.width && Math.abs(stack.y-master.y)<2,'master/detail alignment failed');
  check(await page.locator('#prep-detail').evaluate(e=>getComputedStyle(e).overflowY)==='visible','nested card scroll remains inside detail stack');
  await page.locator('.v2-detail-stack').evaluate(e=>e.scrollTop=0);await page.mouse.move(1400,30);
  await page.screenshot({path:output+'after-detail.png'});
  const refreshEvidence=[];
  for(const state of [null,'SUBMITTING','UNKNOWN']){
    await page.evaluate(state=>{prepCommandPending=state?{state}:null;renderPrepCommandPending();renderPreparationReadControls();},state);
    await page.evaluate(()=>document.fonts.ready);await page.mouse.move(1400,30);await page.waitForTimeout(300);
    const evidence=await page.locator('#prep-refresh').evaluate(button=>{
      const style=getComputedStyle(button),ancestors=[];
      for(let node=button;node;node=node.parentElement)ancestors.push({tag:node.tagName,id:node.id,opacity:getComputedStyle(node).opacity,filter:getComputedStyle(node).filter});
      return {disabled:button.disabled,matchesDisabled:button.matches(':disabled'),ariaDisabled:button.getAttribute('aria-disabled'),fieldset:button.closest('fieldset')?.disabled??null,busy:button.getAttribute('aria-busy'),foreground:style.color,background:style.backgroundColor,backgroundImage:style.backgroundImage,reason:document.querySelector('#workspace-refresh-reason').textContent,ancestors};
    });
    check(evidence.disabled===!!state&&evidence.matchesDisabled===!!state,'original state guard changed');
    check(evidence.ancestors.every(a=>Number(a.opacity)===1),'ancestor opacity dims recovery');
    await page.screenshot({path:output+'refresh-'+(state||'INVALID-available')+'.png'});
    refreshEvidence.push({pending:state,settledMs:300,...evidence});
  }
  await page.evaluate(()=>{prepCommandPending=null;renderPrepCommandPending();renderPreparationReadControls();});
  const checks=[];
  for(const size of [{width:720,height:450},{width:1024,height:640},{width:320,height:700}]){
    await page.setViewportSize(size);
    await page.locator('.v4-session-disclosure>summary').click();
    await page.locator('#token').focus();
    check(await page.locator('#token').isVisible(),'session input unreachable');
    await page.locator('.v4-session-disclosure>summary').click();
    await page.locator('.v4-current-item').click();
    check(await page.locator('.workspace-case-goal').evaluate(e=>e===document.activeElement),'jump does not focus title');
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'compact shell overflow');
    checks.push(size);
  }
  return {refreshEvidence,compactTasks:checks,errors,writes};
}
