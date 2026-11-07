
const {chromium}=require('C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const out=path.resolve('submission/03-截图与成果/05-审阅修订实录');fs.mkdirSync(out,{recursive:true});
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
const context=await browser.newContext({viewport:{width:1920,height:1080},timezoneId:'Asia/Shanghai',acceptDownloads:true});
const page=await context.newPage();const errors=[],requests=[],shots=[];
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push({url:r.url(),method:r.method()}));
const state=()=>page.evaluate(()=>ParkWeaveDemo.state());
const click=a=>page.locator('[data-action="'+a+'"]').click();
const role=r=>page.locator('#demo-role').selectOption(r);
const shot=async(name,caseId)=>{
 await page.evaluate(()=>document.fonts.ready);
 await page.locator('#demo-toast').evaluate(e=>{e.hidden=true});
 const file=path.join(out,name+'.png');await page.screenshot({path:file,animations:'disabled'});
 shots.push({name:name+'.png',case_id:caseId,state:await state(),sha256:crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'),width:1920,height:1080,source:'ACTUAL_BROWSER_INTERACTION_LOCAL_PRESET'});
};
try{
 await page.goto('http://127.0.0.1:8897/demo.html');await page.waitForFunction(()=>document.body.dataset.demoReady==='true');
 await page.getByRole('button',{name:'组织办理方案',exact:true}).click();await page.waitForFunction(()=>ParkWeaveDemo.state().generated);
 await click('next-service');await page.getByLabel('我已核对本次事项资料',{exact:true}).check();await page.getByRole('button',{name:'确认资料并采用方案',exact:true}).click();
 await page.locator('[data-view=resource]').click();await click('recommend-resources');await click('check-resources');await click('confirm-resources');
 assert.equal((await state()).resourcesConfirmed,true);await shot('N01-主事项资源已确认','PW-20261108-001');
 await page.locator('[data-view=collaboration]').click();await role('specialist');await click('dispatch');await role('executor');await click('accept');await click('receipt');
 await page.getByLabel('我已核对执行事项与检查结果',{exact:true}).check();await page.getByRole('button',{name:'提交回执供企业核对',exact:true}).click();await role('enterprise');
 await shot('N05-活动保障准备回执待核对','PW-20261108-001');await click('complete');await page.locator('[data-view=detail]').click();
 await shot('N06-活动保障准备已归档','PW-20261108-001');
 for(const artifact of await page.evaluate(()=>ParkWeaveDemo.artifacts()))fs.writeFileSync(path.join(out,artifact.name),artifact.content);
 await page.locator('[data-view=revision]').click();await click('revision-start');
 assert.equal((await state()).revision.preferenceConfirmed,false);
 await page.locator('#revision-action-form').evaluate(f=>f.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
 assert.equal((await state()).revision.step,0);
 await shot('N00-企业费用偏好待确认','PW-20261108-003');
 await page.locator('input[name=costPreference]').check();await page.locator('#revision-action-form button[type=submit]').click();
 assert.equal((await state()).revision.preferenceConfirmed,true);await shot('N07-偏好与方案比较','PW-20261108-003');
 const roles={1:'enterprise',2:'enterprise',3:'executor',4:'enterprise',5:'executor',6:'enterprise',7:'enterprise',8:'executor',9:'enterprise'};
 for(let step=1;step<10;step++){
  assert.equal((await state()).revision.step,step);
  await role(roles[step]);await page.locator('#revision-action-form button[type=submit]').click();
  const next=(await state()).revision.step;assert.equal(next,step+1);
  if(next===2)await shot('N09-修订资源待确认','PW-20261108-003');
  if(next===5)await shot('N10-回执退回与纠正','PW-20261108-003');
  if(next===6)await shot('N11-修订回执v2待核对','PW-20261108-003');
  if(next===8)await shot('N12-重开事项待补充','PW-20261108-003');
  if(next===3)await shot('N02-修订资源已确认','PW-20261108-003');
  if(next===7)await shot('N03-首次归档-v1-回执v2','PW-20261108-003');
  if(next===9){await role('enterprise');await shot('N04-回执v3待企业核对','PW-20261108-003');}
 }
 await shot('N08-再次归档与历史','PW-20261108-003');
 await page.locator('[data-action=revision-archive][data-version="1"]').click();await shot('N13-原归档依据','PW-20261108-003');await click('close-dialog');
 await page.reload();await page.waitForFunction(()=>document.body.dataset.demoReady==='true');assert.equal((await state()).revision.preferenceConfirmed,true);assert.equal((await state()).revision.step,10);
 const final=await page.evaluate(()=>ParkWeaveDemo.snapshot());fs.writeFileSync(path.join(out,'修订事项记录.json'),JSON.stringify(final,null,2));
 const legacy=await state();delete legacy.revision.preferenceConfirmed;delete legacy.revision.preference;legacy.revision.step=1;
 await page.evaluate(value=>localStorage.setItem('parkweave.product-demo.v1',JSON.stringify(value)),legacy);await page.reload();await page.waitForFunction(()=>document.body.dataset.demoReady==='true');
 assert.match(await page.locator('#demo-content').innerText(),/历史方案未记录费用偏好/);assert.doesNotMatch(await page.locator('.revision-history').innerText(),/企业确认费用偏好/);
 assert.equal(final.success_scope,'活动保障准备');assert.equal(final.revision.receipts.length,3);assert.deepEqual(errors,[]);
 assert(requests.every(r=>r.method==='GET'&&r.url.startsWith('http://127.0.0.1:8897/')));
 fs.writeFileSync(path.join(out,'本轮验证.json'),JSON.stringify({scope:'LOCAL_PRESET_BROWSER_ONLY',real_model_call:false,real_backend_execution:false,external_booking_confirmed:false,checks:['unchecked preference refused','enterprise preference persisted','main preparation completion','revised resource confirmation','archive1 binds receipt2','receipt3 awaits enterprise','archive2 and reload','legacy revision not assigned new preference'],source_sha256:crypto.createHash('sha256').update(fs.readFileSync('src/parkweave/demo-workspace.js')).digest('hex'),shots,errors,requests},null,2));
 console.log(JSON.stringify({screenshots:shots.length,errors,preference:final.revision.preference,finalStep:final.revision.step}));
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
