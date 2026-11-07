// Real browser constraint validation; explicit fake host, no backend or database.
const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PW_BROWSER_EXE});
 try{
  const page=await browser.newPage();const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<!doctype html><html><head></head><body></body></html>');
  await page.evaluate(()=>{window.sent=[];window.chrome={webview:{postMessage:raw=>sent.push(JSON.parse(raw)),addEventListener:()=>{}}};});
  await page.addScriptTag({content:fs.readFileSync('src/parkweave/desktop_startup.js','utf8')});
  const dialog=page.locator('.desktop-startup-panel');
  await dialog.getByLabel('数据目录',{exact:true}).fill('E:\\synthetic-not-created');
  await dialog.getByRole('button',{name:'创建新工作台',exact:true}).click();
  const passwords=dialog.locator('input[type=password]');
  for(let i=0;i<4;i++)await passwords.nth(i).fill('SYNTHETIC_ONLY_'+i);
  await dialog.locator('summary').click();
  await dialog.getByLabel('数据库端口',{exact:true}).fill('0');
  await dialog.locator('summary').click();
  await dialog.getByRole('button',{name:'创建工作台',exact:true}).click();
  assert.equal(await dialog.locator('details').getAttribute('open')!==null,true,'invalid advanced field stays hidden');
  assert.equal(await dialog.getByLabel('数据库端口',{exact:true}).evaluate(e=>e===document.activeElement),true,'invalid field not focused');
  assert.equal(await page.evaluate(()=>sent.length),0);
  await dialog.getByLabel('数据库端口',{exact:true}).fill('55600');
  await dialog.getByLabel('应用端口',{exact:true}).fill('55600');
  await dialog.locator('summary').click();
  await dialog.getByRole('button',{name:'创建工作台',exact:true}).click();
  assert.equal(await dialog.locator('details').getAttribute('open')!==null,true,'same-port error hidden');
  assert.equal(await dialog.getByLabel('应用端口',{exact:true}).evaluate(e=>e===document.activeElement),true);
  assert.match(await dialog.locator('[role=status]').textContent(),/两个端口/);
  assert.equal(await page.evaluate(()=>sent.length),0);
  await dialog.getByLabel('应用端口',{exact:true}).fill('');
  await dialog.locator('summary').click();
  await dialog.getByRole('button',{name:'创建工作台',exact:true}).click();
  assert.equal(await dialog.getByLabel('应用端口',{exact:true}).evaluate(e=>e===document.activeElement),true);
  assert.equal(await page.evaluate(()=>sent.length),0);
  await dialog.getByRole('button',{name:'打开已有工作台',exact:true}).click();
  assert.equal(await dialog.getByLabel('数据库端口',{exact:true}).isDisabled(),true,'hidden port still validates on reopen');
  await dialog.getByRole('button',{name:'打开工作台',exact:true}).click();
  const sent=await page.evaluate(()=>window.sent);
  assert.equal(sent.length,1);assert.equal(sent[0].request.action,'reopen');
  assert.equal(sent[0].request.database_port,0);assert.equal(sent[0].request.api_port,0);
  assert.deepEqual(sent[0].request.passwords,{});assert.deepEqual(errors,[]);
  console.log(JSON.stringify({scope:'REAL_BROWSER_VALIDATION_FAKE_HOST_NO_BUSINESS',hiddenInvalidPortCannotBlockReopen:true,advancedInvalidFieldRevealedAndFocused:true,samePortsRejectedAndFocused:true,emptyPortRejectedAndFocused:true,implicitBusinessRequests:0}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
