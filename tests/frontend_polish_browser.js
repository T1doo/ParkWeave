// Execute this async function with the Playwright browser tool, against the
// original frontend and frontend_preview_server.py historical read-only DTOs.
// It does not claim a database, authenticated product or native host run.
async (page) => {
  const results = [], requests = [], errors = [];
  const check = (ok, message) => { if (!ok) throw Error(message); };
  page.on('request', request => requests.push({method: request.method(), url: request.url()}));
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({width:1440,height:900});
  await page.goto('http://127.0.0.1:8876/web.html');
  for (const viewport of [{width:1366,height:768},{width:1440,height:900}]) {
    await page.setViewportSize(viewport);
    const primary=await page.locator('#prep-catalog').boundingBox();check(primary&&primary.y+primary.height<=viewport.height,'primary service action is below first viewport at '+viewport.width);
  }
  const icon = await page.request.get('http://127.0.0.1:8876/parkweave-mark.png');
  check(icon.ok() && icon.headers()['content-type']==='image/png', 'bundled raster brand asset unavailable');
  const support = page.locator('.atelier-support').last();
  await support.locator('summary').focus();
  await page.keyboard.press('Enter');
  check(await support.evaluate(e=>e.open), 'support disclosure not keyboard operable');
  await page.keyboard.press('Enter');
  results.push('Service primary action fits 1366x768 and 1440x900; PNG brand asset responds; support tools open by keyboard');
  const goal = page.locator('#prep-goal');
  await goal.fill('合成核对：保留目标、时间与必须满足的条件');
  await page.locator('#prep-catalog').click();
  await page.waitForFunction(() => ['ERROR','UNAVAILABLE'].includes(document.querySelector('#prep-catalog-status').dataset.state));
  check(await goal.inputValue() === '合成核对：保留目标、时间与必须满足的条件', 'catalog failure lost goal');
  check(await page.locator('.design-goal-count').innerText() === (await goal.inputValue()).length+' / 2000', 'catalog restore left a stale character count');
  results.push('Original catalog GET failure retains the goal');
  await page.locator('.appearance-menu summary').click();
  const count = requests.length;
  await page.locator('#park-theme').selectOption('sage');
  await page.locator('#park-density').selectOption('compact');
  check(requests.length === count, 'appearance caused a request');
  check((await goal.inputValue()).includes('合成核对'), 'appearance lost goal');
  await page.keyboard.press('Escape');
  check(await page.locator('.appearance-menu summary').evaluate(e=>e===document.activeElement), 'appearance Escape focus');
  results.push('Theme/density retain draft, cause no requests, Escape restores focus');
  await page.locator('.appearance-menu summary').click();
  await page.locator('#park-theme').selectOption('ink');
  await page.locator('#park-density').selectOption('comfortable');
  await page.keyboard.press('Escape');
  await goal.fill('');
  await page.locator('#token').fill('SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY');
  await page.locator('[data-tab=resource]').click();
  check(!await page.locator('.entry-workbench').isVisible(), 'service utility rail leaked into resource workspace');
  check(await page.locator('.shell-toolbar > strong').innerText()==='资源工作空间', 'workspace heading is stale');
  await page.locator('#resource-catalog').click();
  await page.locator('.resource-catalog-card').first().waitFor({state:'attached'});
  check(await page.locator('#park-resource-summary .workspace-facts > div').count()===5, 'resource input summary lacks field rows');
  const quantityRow=page.locator('#park-resource-summary .workspace-facts > div').filter({has:page.locator('dt',{hasText:'使用数量'})});
  await page.locator('#resource-quantity').fill('2');
  check(await quantityRow.locator('dd').innerText()==='2 份','summary quantity did not follow the form');
  await page.locator('#resource-quantity').fill('1');
  await page.locator('#resource-start').fill('2026-10-26T13:00');
  await page.locator('#resource-end').fill('2026-10-26T14:00');
  const trigger = page.getByRole('button',{name:'选择开始日期',exact:true});
  await trigger.click();
  check(await page.locator('[data-day="2026-10-26"]').evaluate(e=>e===document.activeElement), 'calendar opening focus');
  await page.keyboard.press('ArrowRight');
  check(await page.locator('[data-day="2026-10-27"]').getAttribute('aria-disabled')==='true','unavailable date semantics');
  await page.keyboard.press('Enter');
  check(await page.locator('#resource-start').inputValue()==='2026-10-26T13:00','unavailable date changed input');
  await page.keyboard.press('PageDown');
  check(await page.locator('#resource-start').inputValue()==='2026-10-26T13:00','month browsing changed input');
  await page.keyboard.press('Escape');
  check(await trigger.evaluate(e=>e===document.activeElement),'calendar cell Escape focus');
  await trigger.click();
  await page.locator('.design-calendar').getByRole('button',{name:'上个月',exact:true}).focus();
  await page.keyboard.press('Escape');
  check(await trigger.evaluate(e=>e===document.activeElement),'calendar heading Escape focus');
  check(await page.locator('#resource-end').inputValue()==='2026-10-26T14:00','calendar lost end time');
  results.push('Real browser calendar arrows, unavailable Enter, PageDown, cell/header Escape preserve values and restore focus');
  const widths = [1440,1366,1280,1024,768,720,320];
  for (const width of widths) {
    await page.setViewportSize({width,height:width===1366?768:900});
    await trigger.click();
    await page.locator('.design-calendar').scrollIntoViewIfNeeded();
    const overflow = await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth || document.querySelector('#park-main').scrollWidth>document.querySelector('#park-main').clientWidth+1);
    check(!overflow,'horizontal overflow at '+width);
    const bounds = await page.locator('.design-calendar').boundingBox();
    check(bounds.width<=width,'calendar width at '+width);
    await page.keyboard.press('Escape');
  }
  results.push('Resource/calendar reflow without horizontal overflow at '+widths.join(', ')+' CSS px (720 is a 200% equivalent viewport, not native browser zoom)');
  await page.emulateMedia({reducedMotion:'reduce',forcedColors:'active'});
  await trigger.click();
  check(await page.locator('.design-calendar').isVisible(),'high contrast calendar missing');
  check(await page.locator('.design-calendar').evaluate(e=>getComputedStyle(e).animationName)==='none','reduced motion');
  await page.keyboard.press('Escape');
  await page.emulateMedia({reducedMotion:'no-preference',forcedColors:'none'});
  results.push('Forced colors and reduced motion retain keyboard calendar');
  for(const [port,state] of [[8877,'EMPTY'],[8878,'ERROR'],[8879,'DENIED']]) {
    await page.goto('http://127.0.0.1:'+port+'/web.html');
    await page.locator('#token').fill('SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY');
    await page.locator('[data-tab=resource]').click();
    await page.locator('#resource-catalog').click();
    await page.waitForFunction(s=>document.querySelector('#resource-catalog-status').dataset.state===s,state);
    check(await page.locator('.resource-catalog-card').count()===0,'stale cards in '+state);
    results.push('Original HTTP response renders '+state+' without stale resources');
  }
  await page.goto('http://127.0.0.1:8876/local_preparation_web.html');
  check(await page.locator('#login-card').isVisible(),'compact login shell');
  check(errors.length===0,'browser errors: '+errors.join(', '));
  check(requests.every(r=>r.method==='GET'),'unexpected write request');
  return {scope:'Windows Chromium, original HTML + historical read-only synthetic HTTP fixture',results,pageErrors:errors,writeRequests:requests.filter(r=>r.method!=='GET'),requestCount:requests.length};
}
