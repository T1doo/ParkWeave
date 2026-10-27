// The shipped guide + original page handlers; DOM/window mechanics only; CSP and actual popups require the real browser walk.
const supportText=require('fs').readFileSync('tests/ordinary_case_goal_record_pack_html.js','utf8').split('const until=')[0];
const scenario=String.raw`
Element.prototype.dispatchEvent=function(event){this.emit(event.type);return true;};
const settle=async predicate=>{for(let i=0;i<500;i++){if(predicate())return;await new Promise(r=>setTimeout(r,10));}throw Error('original handler did not settle');};
(async()=>{
 const config=await initialized,calls=[];diagnostics={calls};
 const original=page({...config,token:''},{},calls,{});
 original.context.setTimeout=setTimeout;original.context.clearTimeout=clearTimeout;
 const guideHTML=fs.readFileSync('src/parkweave/park_demo_web.html','utf8');
 const guideCode=guideHTML.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1],elements=new Map();
 for(const m of guideHTML.split('<script')[0].matchAll(/<([a-z][\w-]*)\b([^>]*)>/gi)){
  const id=m[2].match(/\bid="([^"]+)"/)?.[1],role=m[2].match(/data-role="([^"]+)"/)?.[1];if(!id&&!role)continue;
  const e=new Element(m[1]);e.id=id||role;if(role)e.dataset.role=role;elements.set(e.id,e);
 }
 const get=id=>elements.get(id),events={};
 const originalWindow={document:original.context.document,location:{origin:new URL(config.base).origin},closed:false,focus(){},Event:class{constructor(type){this.type=type;}}};
 const guide=vm.createContext({console,JSON,Error,location:{origin:new URL(config.base).origin},
  document:{getElementById:get,querySelectorAll:selector=>[...elements.values()].filter(e=>selector==='button'?e.tagName==='button':selector==='[data-role]'&&e.dataset.role)},
  window:{addEventListener:(name,fn)=>events[name]=fn,open:(url,target)=>{check(url==='/'&&target==='_blank','only explicit same-origin business window');return originalWindow;}}});
 vm.runInContext(guideCode,guide);
 get('sessions').files=[{size:2,text:async()=>'{}'}];await get('sessions').onchange();check(get('enterprise').disabled,'invalid session file stays closed');
 const raw=JSON.stringify(config.tokens);get('sessions').files=[{size:Buffer.byteLength(raw),text:async()=>raw}];await get('sessions').onchange();
 check(get('enterprise').disabled&&!get('workspace-open').disabled,'identity waits for explicit business window');get('workspace-open').onclick();check(!get('enterprise').disabled,'six synthetic sessions loaded in browser memory');
 const role=name=>get(name).onclick();role('enterprise');
 const before=calls.filter(c=>c.method==='POST').length;
 get('scenario').value=config.phase==='again'?'again':'first';get('fill-goal').onclick();get('fill-request').onclick();get('fill-need').onclick();get('fill-outline').onclick();
 check(calls.filter(c=>c.method==='POST').length===before,'sample helper has no implicit POST');
 const goal=original.$('prep-goal').value;check(goal.includes('SYNTHETIC')&&goal.includes('云杉智造'),'fictional marked input');
 await original.$('prep-catalog').click();original.$('prep-reviewer').value=config.ids.specialist;get('fill-goal').onclick();
 await original.$('prep-create').onsubmit({preventDefault(){}});
 check(!!original.run('preparationId'),original.$('prep-read-status').textContent);
 const id=original.run('preparationId');
 const ready=()=>settle(()=>original.run('preparationId')===id&&original.$('prep-read-status').textContent.includes('已就绪'));
 const open=async()=>{await original.$('prep-list').click();const e=original.$('prep-items').children.find(e=>e.tagName==='button'&&textOf(e).includes(goal));check(!!e,'exact goal in role-owned list');await e.click();await ready();};
 await original.$('plan-prepare').click();get('fill-request').onclick();await original.$('request-intent-form').onsubmit({preventDefault(){}});
 check(original.run('planView.request_intent.recorded'),'original explicit request saved');
 await original.$('plan-materials').click();await ready();
 if(config.phase==='again'){
  await original.$('material-reuse-read').click();
  const view=original.run('materialReuseView');check(view.items.length===1,'first confirmed same-owner source located');
  original.$('material-reuse-source').value=view.items[0].source_evidence_id;original.$('material-reuse-source').onchange();
  await original.$('material-reuse-preview').click();original.$('material-reuse-purpose').checked=true;original.$('material-reuse-purpose').onchange();
  original.$('material-reuse-reason').value='SYNTHETIC 林岚明确同用途复用通用目录';
  await original.$('material-reuse-form').onsubmit({preventDefault(){}});
  await settle(()=>original.run('preparationView?.current_materials')?.some(x=>x.slot==='material_outline')&&original.$('prep-read-status').textContent.includes('已就绪'));
  check(original.run('preparationView.current_materials').some(x=>x.slot==='material_outline'),'original explicit reuse copied only outline');
 }
 get('fill-need').onclick();await original.$('prep-evidence').onsubmit({preventDefault(){}});
 if(config.phase!=='again'){get('fill-outline').onclick();await original.$('prep-evidence').onsubmit({preventDefault(){}});}
 check(original.run('preparationView.current_materials').length===2,'both explicit material writes read back');
 role('specialist');await open();original.$('prep-reason').value='SYNTHETIC 周禾本人核对虚构资料';await original.$('prep-review').click();
 check(original.run('preparationView.preparation.state')==='REVIEWED','specialist explicit REVIEW');
 role('enterprise');await open();original.$('prep-reason').value='SYNTHETIC 林岚本人确认虚构资料';await original.$('prep-confirm').click();
 check(original.run('preparationView.preparation.state')==='LOCAL_CONFIRMED','owner separate CONFIRM');
 let selected=null;
 if(config.phase==='again'){
  await original.$('case-cancel-read').click();check(original.run('caseCancelView.can_cancel'),'second before-submit Case can cancel');
  original.$('case-cancel-reason').value='SYNTHETIC 林岚取消新增2台设备演示事项，首办保持';original.$('case-cancel-reason').oninput();
  original.$('case-cancel-confirm').checked=true;original.$('case-cancel-confirm').onchange();
  await original.$('case-cancel-form').onsubmit({preventDefault(){}});
  await settle(()=>original.run('preparationView?.case_cancelled')===true);
  check(original.run('preparationView.case_cancelled')===true,'original confirmed cancellation persisted');
 }else{
  await original.$('service-plan-prepare').click();await original.$('service-selection-read').click();
  await original.$('service-selection-generate').click();selected=original.run('serviceSelectionView');
  check(selected.can_adopt&&selected.producer.mode==='NO_MODEL','existing synthetic source adapter generated exact candidate');
  original.$('service-plan-reason').value='SYNTHETIC 林岚明确采纳本次模拟来源方案';original.$('service-selection-confirm').checked=true;
  await original.$('service-plan-adopt').click();check(!!original.run('servicePlanView.plan_id'),'actual explicit original ADOPT');
 }
 const result={preparation_id:id,run_id:original.run('preparationView.preparation.run_id'),revision:original.run('preparationView.preparation.revision'),
  plan_id:config.phase==='again'?null:original.run('servicePlanView.plan_id'),goal,phase:config.phase,checks,calls,selected,
  real_browser:false,scope:'FICTIONAL_DEMO_SHIPPED_GUIDE_AND_ORIGINAL_HTML_REAL_HTTP'};
 events.pagehide();check(get('enterprise').disabled&&original.$('token').value==='','pagehide clears guide and original identity');
 console.log(JSON.stringify(result));process.exit(0);
})().catch(e=>{console.error(e.stack);console.error(JSON.stringify(diagnostics));process.exit(1);});
`;
require('vm').runInNewContext(supportText+scenario,{require,console,process,fetch,URL,URLSearchParams,Blob,TextEncoder,Buffer,setTimeout,clearTimeout});
