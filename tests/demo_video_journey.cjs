// Real browser interaction with explicit local concept-demo state, no backend.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const base='http://127.0.0.1:8896',output=path.resolve(process.env.DEMO_EVIDENCE_DIR||'docs/demo-delivery-20261106/interactive-r1');
const profile=path.join(output,'_test-profile');fs.mkdirSync(output,{recursive:true});
const recording=process.env.DEMO_RECORD==='1';
const options={headless:true,executablePath:process.env.PW_BROWSER_EXE||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',viewport:{width:1440,height:900},deviceScaleFactor:1,timezoneId:'Asia/Shanghai',acceptDownloads:true,...(recording?{slowMo:90,recordVideo:{dir:path.join(output,'_recording'),size:{width:1440,height:900}}}:{})};
(async()=>{
 let context=await chromium.launchPersistentContext(profile,options),page=await context.newPage();const errors=[],writes=[],external=[],checks=[];
 function observe(p){p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.method()!=='GET')writes.push(r.url());if(!r.url().startsWith(base)&&!r.url().startsWith('blob:'+base))external.push(r.url());});}
 observe(page);
 const state=()=>page.evaluate(()=>ParkWeaveDemo.state());
 const click=action=>page.locator('[data-action="'+action+'"]').click();
 const waitPaint=async()=>{await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(260);};
 const shot=async name=>{await waitPaint();if(recording)await page.waitForTimeout(1100);await page.screenshot({path:path.join(output,name+'.png'),animations:'disabled'});};
 try{
  await page.goto(base+'/demo.html');await page.waitForFunction(()=>document.body.dataset.demoReady==='true');
  await page.evaluate(()=>{localStorage.removeItem('parkweave.product-demo.v1');location.reload();});await page.waitForFunction(()=>document.body.dataset.demoReady==='true');
  await shot('01-表达目标');
  await page.locator('#demo-end').fill('2026-11-08T13:00');await page.getByRole('button',{name:'组织办理方案',exact:true}).click();
  assert.match(await page.locator('#demo-form-error').textContent(),/结束时间/);assert.equal((await state()).generated,false);
  await page.locator('#demo-end').fill('2026-11-08T16:00');
  await page.getByRole('button',{name:'组织办理方案',exact:true}).click();
  await page.evaluate(()=>document.querySelector('#demo-goal-form')?.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
  await page.waitForFunction(()=>ParkWeaveDemo.state().generated);assert.equal((await state()).events.length,1);checks.push('invalid interval refused; duplicate plan submission suppressed');
  await shot('02-组织方案');await click('next-service');
  await page.keyboard.press('Escape');assert.equal(await page.locator('#demo-dialog').evaluate(e=>e.open),false);assert.equal((await state()).adopted,false);
  await click('next-service');await page.getByRole('button',{name:'确认资料并采用方案',exact:true}).click();assert.equal((await state()).adopted,false);
  await page.getByLabel('我已核对本次事项资料',{exact:true}).check();await page.getByRole('button',{name:'确认资料并采用方案',exact:true}).click();
  assert.equal((await state()).adopted,true);assert.equal((await state()).events.length,3);checks.push('modal Escape and explicit material acknowledgement');
  await page.locator('[data-view=detail]').click();await shot('03-资料与来源');
  await page.locator('[data-view=resource]').click();await click('recommend-resources');
  assert.equal((await state()).selected.length,2);await page.locator('#resource-demo-start').fill('2026-11-08T13:00');await click('check-resources');assert.equal((await state()).preview,'CONFLICT');assert.equal(await page.locator('[data-action=confirm-resources]').isDisabled(),true);await shot('04-资源冲突');
  await page.locator('#resource-demo-start').fill('2026-11-08T14:00');await click('check-resources');assert.equal((await state()).preview,'PASS');
  await page.locator('[data-resource=venue-b]').click();await click('check-resources');assert.match((await state()).previewMessage,/容量/);
  await click('recommend-resources');await page.locator('#demo-equipment-quantity').fill('2');await click('check-resources');assert.match((await state()).previewMessage,/1 套/);
  await page.locator('#demo-equipment-quantity').fill('1');await click('check-resources');assert.equal((await state()).preview,'PASS');
  await page.locator('#demo-role').selectOption('resource-admin');assert.equal(await page.locator('[data-action=confirm-resources]').isDisabled(),true);assert.equal((await state()).resourcesConfirmed,false);
  await page.locator('#demo-role').selectOption('enterprise');await shot('05-资源组合');await click('confirm-resources');assert.equal((await state()).resourcesConfirmed,true);checks.push('conflict, capacity, quantity and read-only admin concept guards');
  await page.locator('[data-view=collaboration]').click();await page.getByRole('button',{name:'切换至园区专员',exact:true}).click();await shot('06-专员派单');await click('dispatch');
  await page.getByRole('button',{name:'切换至执行人员',exact:true}).click();await shot('07-执行人员接单');await click('accept');await click('receipt');
  await page.getByLabel('我已核对执行事项与检查结果',{exact:true}).check();await page.getByRole('button',{name:'提交回执供企业核对',exact:true}).click();
  await page.getByRole('button',{name:'切换至企业负责人',exact:true}).click();await shot('08-回执待确认');await click('complete');
  assert.equal((await state()).completed,true);assert.equal((await state()).events.length,8);checks.push('specialist dispatch -> executor accept/receipt -> enterprise confirmation');
  await page.locator('[data-view=detail]').click();await shot('09-事项归档');
  fs.writeFileSync(path.join(output,'interactive-case.json'),JSON.stringify(await page.evaluate(()=>ParkWeaveDemo.snapshot()),null,2));
  await page.reload();await page.waitForFunction(()=>document.body.dataset.demoReady==='true');assert.equal((await state()).completed,true);assert.equal((await state()).events.length,8);checks.push('local demo state retained on reload');
  await page.locator('#demo-export-menu').click();fs.mkdirSync(path.join(output,'outputs'),{recursive:true});
  for(const kind of ['plan','materials','resources','record','report']){
   const pending=page.waitForEvent('download');await page.locator('#demo-dialog [data-kind="'+kind+'"]').click();const download=await pending;
   await download.saveAs(path.join(output,'outputs',download.suggestedFilename()));
  }
  await click('close-dialog');checks.push('five actual Blob exports downloaded');
  await page.locator('#demo-reset').click();await click('reset-confirm');await page.locator('[data-scenario=training]').click();
  await page.getByRole('button',{name:'组织办理方案',exact:true}).click();await page.waitForFunction(()=>ParkWeaveDemo.state().generated);
  assert.equal((await state()).caseId,'PW-20261108-002');assert.equal((await state()).people,20);assert.equal((await state()).events.length,1);assert.equal((await state()).receipted,false);checks.push('second scenario clears prior case outputs and receipt');
  const firstVideo=recording?page.video():null;
  if(firstVideo){await page.close();await firstVideo.saveAs(path.join(output,'ParkWeave-交互操作参考.webm'));}
  await context.close();
  context=await chromium.launchPersistentContext(profile,{...options,recordVideo:undefined});page=await context.newPage();observe(page);
  await page.goto(base+'/demo.html');await page.waitForFunction(()=>document.body.dataset.demoReady==='true');assert.equal((await state()).caseId,'PW-20261108-002');assert.equal((await state()).generated,true);checks.push('demo state retained across actual browser process restart');
  await click('next-service');await page.getByLabel('我已核对本次事项资料',{exact:true}).check();await page.getByRole('button',{name:'确认资料并采用方案',exact:true}).click();
  await page.locator('[data-view=resource]').click();await click('recommend-resources');assert.deepEqual((await state()).selected,['venue-b','projector']);await click('check-resources');assert.equal((await state()).preview,'PASS');checks.push('20-person training recommends B room and equipment within reference budget');
  await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator('.view-enter').evaluate(e=>getComputedStyle(e).animationName),'none');
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);assert.deepEqual(external,[]);
  const result={scope:'REAL_BROWSER_LOCAL_DEMO_INTERACTION_NOT_BUSINESS_BACKEND_ACCEPTANCE',checks,errors,writes,external,scenario1Events:8,scenario2People:20,exportCount:5};
  fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await context.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
