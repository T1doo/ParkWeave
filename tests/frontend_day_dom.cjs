// Real DOM behavior in jsdom. No layout engine, browser, screenshot, HTTP or Windows claim.
// Run with NODE_PATH pointing at an isolated jsdom 27 installation.
const fs=require('node:fs'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function run(file){
 const html=fs.readFileSync('src/parkweave/'+file,'utf8');
 const dom=new JSDOM(html,{url:'http://127.0.0.1/',runScripts:'outside-only'}),w=dom.window,d=w.document;
 const requests=[];w.fetch=(...args)=>{requests.push(args);throw Error('Unexpected network request');};
 w.matchMedia=()=>({matches:true,addEventListener(){}});w.HTMLElement.prototype.scrollIntoView=function(){};
 const start=html.indexOf('// Frontend-day presentation.');
 const script=html.slice(start,html.indexOf('</script>',start));
 w.eval('var preparationView=null,current=null,planView=null,servicePlanView=null;var combinationSelection=new Map();function updateCombinationSelection(){parkDesignRefresh();}function resourceCatalogCard(){return document.createElement("article");}\n'+script);
 d.dispatchEvent(new w.Event('DOMContentLoaded'));await tick();
 const get=id=>d.getElementById(id),fire=(node,type)=>node.dispatchEvent(new w.Event(type,{bubbles:true}));
 const full=file==='web.html',list=get(full?'prep-materials':'materials');
 const parent=get(full?'prep-detail':'workspace');parent.hidden=false;
 for(let node=list;node;node=node.parentElement)node.hidden=false;
 const missing=d.createElement(full?'article':'div');missing.className=full?'':'material';const missingTitle=d.createElement('h3');missingTitle.textContent='材料待补充';missing.append(missingTitle);list.append(missing);await tick();assert.equal(missing.querySelector('.design-preview-trigger'),null,'missing material must not offer an available version preview');list.replaceChildren();await tick();
 if(!full){const stages=get('steps');for(const [index,name] of ['准备材料','专员核对','企业确认'].entries()){const span=d.createElement('span');span.textContent=name;if(index===1)span.className='current';stages.append(span);}await tick();await tick();assert.equal(stages.previousElementSibling.className,'design-stage-toggle');assert.equal(stages.querySelector('.design-stage-visible').textContent,'专员核对');assert(stages.nextElementSibling.textContent.includes('其他 2 个阶段'));stages.replaceChildren();await tick();assert.equal(stages.previousElementSibling.hidden,true);}
 const initialForm=get(full?'prep-evidence':'evidence-form'),field=get(full?'prep-text':'material-text');
 field.value='保留的中文草稿 🧭';const originalValue=field.value;
 get('park-theme').value='sage';fire(get('park-theme'),'change');
 assert.equal(d.documentElement.dataset.theme,'sage');assert.equal(field.value,originalValue);
 get('park-density').value='compact';fire(get('park-density'),'change');assert.equal(d.body.dataset.density,'compact');assert.equal(field.value,originalValue);
 if(full){d.body.dataset.workspace='collaboration';await tick();assert.equal(d.body.dataset.density,'compact');d.body.dataset.workspace='resource';await tick();assert.equal(d.body.dataset.density,'comfortable');d.body.dataset.workspace='service';await tick();assert.equal(d.body.dataset.density,'compact');}
 const material=d.createElement(full?'article':'div');material.className=full?'':'material';
 const heading=d.createElement('strong');heading.textContent='申请材料 v2';const text=d.createElement('p');text.textContent='授权文本 <img src=x onerror=alert(1)> · 准备度未知';material.append(heading,text);list.append(material);await tick();
 const button=material.querySelector('.design-preview-trigger');assert(button);button.click();await tick();
 assert.equal(get('park-material-preview').hidden,false);assert(get('park-material-preview').textContent.includes('准备度未知'));assert.equal(get('park-material-preview').querySelector('img'),null);assert.equal(d.activeElement.textContent,'返回材料列表');
 get('park-material-preview').querySelector('button').click();assert.equal(get('park-material-preview').hidden,true);assert.equal(d.activeElement,button);
 get('park-material-filter').value='未匹配';fire(get('park-material-filter'),'input');await tick();assert(material.classList.contains('design-filtered'));assert.equal(text.textContent,'授权文本 <img src=x onerror=alert(1)> · 准备度未知');
 get('park-material-filter').value='未知';fire(get('park-material-filter'),'input');assert(!material.classList.contains('design-filtered'));
 button.click();text.textContent='后台变化的版本 v3';await tick();assert.equal(get('park-material-preview').hidden,true);assert.equal(get('park-material-preview').querySelector('pre').textContent,'');
 button.click();list.replaceChildren();await tick();assert.equal(get('park-material-preview').hidden,true);assert.equal(get('park-material-filter').value,'');
 list.append(material);await tick();material.querySelector('button').click();parent.hidden=true;await tick();assert.equal(get('park-material-preview').hidden,true);parent.hidden=false;
 // Validation summary preserves unrelated values and removes only the repaired field's error.
 field.value='';field.required=true;field.dispatchEvent(new w.Event('invalid'));await tick();assert.equal(field.getAttribute('aria-invalid'),'true');assert(initialForm.querySelector('.design-errors a'));
 field.value=originalValue;fire(field,'input');assert.equal(field.hasAttribute('aria-invalid'),false);assert.equal(initialForm.querySelector('.design-errors').hidden,true);
 const composing=new w.KeyboardEvent('keydown',{key:'Enter',isComposing:true,bubbles:true,cancelable:true});field.dispatchEvent(composing);assert.equal(composing.defaultPrevented,true);
 if(full){
  const check=d.createElement('input');check.type='checkbox';check.dataset.combinationHold='hold-a';check.checked=true;check.onchange=()=>{w.eval("combinationSelection.delete('hold-a');parkDesignRefresh();");};get('resource-hold-items').append(check);
  w.eval("combinationSelection.set('hold-a',{id:'hold-a',resource_name:'场地 A',purpose:'保留用途',starts_at:'2026-11-09T14:00:00Z',ends_at:'2026-11-09T16:00:00Z',quantity:2,resource_revision:3,state:'HELD',expires_at:'2026-11-02T12:00:00Z'});parkDesignRefresh();");
  assert(get('park-resource-summary').textContent.includes('场地 A'));assert(get('park-resource-summary').textContent.includes('本地选择不等于组合确认'));assert(get('park-resource-summary').textContent.includes('UTC'));
  get('park-resource-summary').querySelector('button').click();assert.equal(w.eval('combinationSelection.size'),0);assert(get('park-resource-summary').textContent.includes('已选组合 0'));
  const plan=get('service-case-plan-detail');plan.hidden=false;get('service-plan-summary').textContent='企业原始目标 · 等待核对';const denied=d.createElement('p');denied.hidden=true;denied.textContent='SYNTHETIC_HIDDEN_NOT_FOR_REVIEW';get('service-plan-coverage').append(denied);await tick();
  [...plan.querySelectorAll('button')].find(b=>b.textContent==='核对当前已读方案').click();assert.equal(plan.querySelectorAll('.design-review-section').length,4);assert(plan.querySelector('.design-plan-review').textContent.includes('企业原始目标'));assert(!plan.querySelector('.design-plan-review').textContent.includes('SYNTHETIC_HIDDEN_NOT_FOR_REVIEW'));
  get('service-plan-summary').textContent='新的版本';await tick();assert.equal(plan.querySelector('.design-plan-review').hidden,true);assert.equal(plan.querySelector('.design-plan-review').textContent,'');
 }
 assert.equal(requests.length,0);const persisted=Object.keys(w.localStorage);assert(persisted.every(x=>x.startsWith('parkweave.appearance.')));assert(!Object.values(w.localStorage).join(' ').includes(originalValue));
 await tick();await tick();dom.window.close();return {page:file,status:'PASS',network_requests:0,pixel_engine:false};
}
async function shippedHandlers(){
 const html=fs.readFileSync('src/parkweave/web.html','utf8'),dom=new JSDOM(html,{url:'http://127.0.0.1/',runScripts:'outside-only'}),w=dom.window,d=w.document,requests=[];
 const errors=[];w.addEventListener('error',event=>errors.push(event.error));
 w.matchMedia=()=>({matches:false,addEventListener(){}});w.fetch=(...args)=>{requests.push(args);throw Error('No network in DOM test');};
 w.eval(html.match(/<script>([\s\S]*?)<\/script>/)[1]+`\nwindow.testDesign={selection:()=>combinationSelection.size,pending:value=>activeEntryWriteFlow=value,quote:()=>deliveryQuote,seedQuote:()=>{deliveryQuote={context:deliveryContext(),synthetic:true};planApprovalView={synthetic:true};},approval:()=>planApprovalView};`);
 d.dispatchEvent(new w.Event('DOMContentLoaded'));await tick();
 assert.equal(d.getElementById('prep-goal').form,d.getElementById('prep-create'),'front-positioned goal retains original form owner');
 const hold={id:'synthetic-hold',resource_id:'synthetic-resource',state:'HELD',resource_name:'合成场地',purpose:'原始用途',quantity:1,starts_at:'2026-11-09T09:00:00Z',ends_at:'2026-11-09T10:00:00Z',expires_at:'2026-11-09T08:00:00Z',resource_revision:1};
 w.renderResourceHold(hold,d.getElementById('resource-hold-items'));
 const check=d.querySelector('[data-combination-hold]');check.click();assert.equal(w.testDesign.selection(),1);assert(d.getElementById('park-resource-summary').textContent.includes('合成场地'));
 w.testDesign.seedQuote();d.getElementById('park-resource-summary').querySelector('button').click();assert.equal(w.testDesign.selection(),0);assert.equal(w.testDesign.quote(),null);assert.equal(w.testDesign.approval(),null);
 check.click();w.testDesign.pending({kind:'SYNTHETIC_ACTIVE_ORIGINAL_REQUEST'});d.getElementById('park-resource-summary').querySelector('button').click();assert.equal(w.testDesign.selection(),1,'new action must respect original active request guard');w.testDesign.pending(null);
 assert.equal(requests.length,0);assert.deepEqual(errors,[]);await tick();await tick();dom.window.close();return {page:'whole shipped web.html',status:'PASS',original_change_invalidation:true,original_pending_guard:true,network_requests:0,pixel_engine:false};
}
(async()=>{const results=[];for(const page of ['web.html','local_preparation_web.html'])results.push(await run(page));results.push(await shippedHandlers());console.log(JSON.stringify({kind:'jsdom-only',results},null,2));})().catch(e=>{console.error(e);process.exitCode=1;});
