// Explicit in-memory hold DTOs exercise original selection renderers, never writes.
async page=>{
  const check=(ok,message)=>{if(!ok)throw Error(message)};
  const writes=[];page.on('request',r=>{if(r.method()!=='GET')writes.push(r.url())});
  await page.emulateMedia({forcedColors:'none',reducedMotion:'no-preference'});
  await page.setViewportSize({width:1440,height:900});
  await page.goto('http://127.0.0.1:8876/web.html');
  await page.locator('#token').fill('SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY');
  await page.locator('[data-tab=resource]').click();await page.locator('#resource-catalog').click();await page.locator('#resource-form').waitFor();
  const form=await page.locator('#resource-form').evaluate(e=>({owners:[...e.querySelectorAll('input,select,button')].every(n=>n.form===e),required:document.querySelector('#resource-start').required&&document.querySelector('#resource-end').required,quantityWidth:document.querySelector('#resource-quantity').getBoundingClientRect().width,start:document.querySelector('#resource-start').getBoundingClientRect().y,end:document.querySelector('#resource-end').getBoundingClientRect().y}));
  check(form.owners&&form.required&&form.start===form.end&&form.quantityWidth>=120&&form.quantityWidth<=160,'form ownership/date alignment/quantity width');
  await page.evaluate(()=>{
    const target=document.createElement('div');target.id='synthetic-selection-fixture';document.querySelector('#resource').append(target);
    for(let i=1;i<=2;i++)renderResourceHold({id:'visual-hold-'+i,state:'HELD',resource_name:'合成长资源名称 · 场地和设备 '+i,purpose:'仅测试原选择渲染器',starts_at:'2026-10-26T13:00:00Z',ends_at:'2026-10-26T14:00:00Z',expires_at:'2026-10-26T12:02:00Z',quantity:i,resource_revision:1},target);
  });
  const selection=[];
  for(let count=0;count<=2;count++){
    if(count)await page.locator('#synthetic-selection-fixture input[type=checkbox]').nth(count-1).check();
    await page.waitForTimeout(40);
    const title=await page.locator('#park-resource-summary .resource-summary-details>h4').innerText();
    check(title.includes(count+' 项'),'selection count mismatch');selection.push(title);
  }
  await page.locator('#token').fill('SYNTHETIC_DIFFERENT_IDENTITY');
  check((await page.locator('#park-resource-summary').innerText()).includes('0 项'),'identity change retained private selection');
  await page.locator('#synthetic-selection-fixture').evaluate(e=>e.remove());
  await page.locator('[data-tab=service]').click();
  const effects=page.getByRole('combobox',{name:'显示效果',exact:true});
  await page.locator('.appearance-menu>summary').click();await effects.selectOption('low');
  check(await page.locator('.app-sidebar').evaluate(e=>getComputedStyle(e).backdropFilter)==='none','real low-effects control failed');
  await effects.selectOption('glass');await page.keyboard.press('Escape');
  const material=await page.evaluate(()=>({blur:getComputedStyle(document.querySelector('.app-sidebar')).backdropFilter,background:getComputedStyle(document.body,'::before').animationName}));
  check(material.blur.includes('18px'),'standard material lost real blur');
  const performance=await page.evaluate(async()=>{
    const samples=[],longTasks=[];let previous=performance.now();
    const observer=new PerformanceObserver(list=>longTasks.push(...list.getEntries().map(e=>e.duration)));observer.observe({type:'longtask',buffered:false});
    const main=document.querySelector('#park-main');
    await new Promise(resolve=>{let frames=0;function step(now){samples.push(now-previous);previous=now;main.scrollTop=(frames%40)*12;if(++frames<120)requestAnimationFrame(step);else resolve();}requestAnimationFrame(step)});
    observer.disconnect();main.scrollTop=0;samples.shift();samples.sort((a,b)=>a-b);
    return {samples:samples.length,p50Ms:samples[Math.floor(samples.length*.5)],p95Ms:samples[Math.floor(samples.length*.95)],maxMs:Math.max(...samples),longTasksMs:longTasks,note:'One automated Chromium rAF/scroll sample, not an FPS or device performance certification'};
  });
  check(!writes.length,'unexpected business write');
  return {scope:'read-only HTTP catalog + explicit in-memory synthetic hold fixtures',form,selection,identityClearsSelection:true,material,performance,writes};
}
