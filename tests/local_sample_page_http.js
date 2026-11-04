/* Entire served app handlers and password adapter over actual HTTP.
 * Controlled DOM mechanics only; no browser/pixels, direct SQL or token fixture. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const input=JSON.parse(fs.readFileSync(0,'utf8')),crypto=require('crypto').webcrypto;
let phase='LOAD',calls=[];
const silence={log(){},error(){},warn(){}};
const until=async(fn)=>{for(let i=0;i<200;i++){if(fn())return;await new Promise(r=>setTimeout(r,25));}throw Error('bounded state not reached');};
(async()=>{
 const response=await fetch(input.base+'/');assert(response.ok);const html=await response.text();
 assert(html.includes('id="local-workspace-login"')&&html.includes('id="local-sample-resource-panel"'));
 const original=fs.readFileSync('tests/ordinary_case_step_real_html.js','utf8');
 let fragment=original.slice(original.indexOf('const html ='),original.indexOf('(async()=>'));
 fragment=fragment.replace("const html = fs.readFileSync('src/parkweave/web.html', 'utf8');",'const html = servedHTML;').replace('setTimeout: () => 1, clearTimeout() {}','setTimeout, clearTimeout');
 const make=new Function('require','fs','vm','assert','control','servedHTML','console','setTimeout','clearTimeout',fragment+';return {page,Element};');
 const {page,Element}=make(require,fs,vm,assert,()=>{throw Error('no developer control');},html,silence,setTimeout,clearTimeout);
 Element.prototype.dispatchEvent=function(e){this['on'+e.type]?.(e);for(const h of this.listeners[e.type]||[])h(e);return true;};
 Element.prototype.prepend=function(...items){this.children.unshift(...items);};
 const pending=await(await fetch(input.base+'/local-command-pending.js')).text();
 const loginJS=await(await fetch(input.base+'/local-workspace-login.js')).text();
 const resourcesJS=await(await fetch(input.base+'/local-sample-resources.js')).text();
 const disk={};const views={};
 async function login(account){
  const p=page({token:'',base:input.base},disk,[],{});p.context.Event=class{constructor(type){this.type=type;}};
  p.context.crypto=crypto;p.context.navigator={locks:{request:async(k,opt,fn)=>fn()}};
  p.context.location={assign(){throw Error('unexpected navigation');}};
  p.context.fetch=async(path,opt={})=>{
   const r=await fetch(input.base+path,{...opt,redirect:'error',headers:{...opt.headers,...(path==='/api/local/session'?{Origin:input.base}:{})}});
   calls.push({method:opt.method||'GET',path,status:r.status,key:opt.headers?.['Idempotency-Key'],action:opt.body&&path!=='/api/local/session'?JSON.parse(opt.body).action:undefined});return r;
  };
  vm.runInContext(pending,p.context);vm.runInContext(loginJS,p.context);vm.runInContext(resourcesJS,p.context);
  p.$('local-workspace-account').value=account;p.$('local-workspace-password').value=input.passwords[account];
  await p.$('local-workspace-login').onsubmit({preventDefault(){}});
  assert.equal(p.context.document.body.dataset.localWorkspace,'active',p.$('local-workspace-status').textContent);
  assert.equal(p.$('local-workspace-password').value,'');views[account]=p;return p;
 }
 const invoke=async(p,id,event='onclick')=>{assert.equal(typeof p.$(id)[event],'function',id);await p.$(id)[event]({preventDefault(){}});};
 async function select(p,id){await invoke(p,'prep-list');const b=p.$('prep-items').children.find(x=>x.tagName==='button'&&x.textContent.includes(id)||x.tagName==='button'&&JSON.stringify(x.children).includes(id));assert(b,'exact preparation');await b.click();assert.equal(p.run('preparationId'),id);}
 async function verify(p,adapter){const card=p.$('service-plan-steps').children.find(e=>e.dataset.serviceAdapter===adapter);assert(card,adapter);const actions=card.children.find(e=>e.className==='service-step-actions');const button=actions.children.find(e=>e.dataset.serviceAction==='VERIFY');assert(button&&!button.disabled,JSON.stringify(p.run('servicePlanView.steps.map(s=>({adapter:s.adapter_id,state:s.state,actions:s.allowed_actions,issues:s.issues}))')));p.$('service-plan-reason').value='SYNTHETIC 核对本次实际记录';await button.click();await until(()=>p.run('servicePlanView.steps.find(s=>s.adapter_id==='+JSON.stringify(adapter)+').state')==='VERIFIED');}
 phase='LOGIN_FOUR_ROLES';const owner=await login('enterprise'),specialist=await login('specialist'),executor=await login('executor'),admin=await login('resource-admin');
 phase='READ_ADMIN_SOURCE';await invoke(admin,'local-sample-resources-read');assert.equal(admin.$('local-sample-resource-items').children.length,2);
 if(input.reopen){
  phase='COLD_ORIGINAL';await select(owner,input.preparation_id);await invoke(owner,'service-plan-prepare');
  assert(owner.run('servicePlanView.steps.every(s=>s.state==="VERIFIED")'));
  const read=await fetch(input.base+'/api/executor-receipts/'+input.step,{headers:{Authorization:'Bearer '+owner.$('token').value}});assert(read.ok);const receipt=await read.json();assert.equal(receipt.step.state,'LOCAL_ACKNOWLEDGED');
  assert.equal(calls.filter(c=>c.method==='POST'&&c.path!=='/api/local/session').length,0);
  process.stdout.write(JSON.stringify({result:'PASS',scope:'NORMAL_SAMPLE_PASSWORD_ENTRY_REAL_HTTP_WITH_NODE_DOM_NOT_BROWSER',plan:owner.run('servicePlanView'),receipt,calls,source_page_sha256:require('crypto').createHash('sha256').update(html).digest('hex'),cold_business_POSTs:0})+'\n');return;
 }
 phase='NORMAL_CREATE';await invoke(owner,'prep-catalog');owner.$('prep-goal').value='SYNTHETIC 本地安装培训服务与资源协同';owner.$('prep-reviewer').value='local-sample-specialist';await invoke(owner,'prep-create','onsubmit');
 const id=owner.run('preparationId');assert(id,owner.$('prep-error').textContent);
 phase='INTENT';await invoke(owner,'plan-prepare');owner.$('request-current').value='SYNTHETIC 服务资料和资源关联';owner.$('plan-required-goals').value='LOCAL_MATERIAL_PREPARATION\nLOCAL_CASE_RESOURCE_ASSOCIATION';owner.$('request-local-goal').checked=false;await invoke(owner,'request-intent-form','onsubmit');
 await select(owner,id);
 async function material(slot,text){owner.$('prep-slot').value=slot;owner.$('prep-text').value=text;owner.$('prep-source-kind').value='USER_STATEMENT';owner.$('prep-source-label').value='SYNTHETIC 本次独立输入 v1';await invoke(owner,'prep-evidence','onsubmit');assert.equal(owner.run('prepCommandPending'),null,owner.$('prep-error').textContent);}
 phase='MATERIALS';await material('need_summary','SYNTHETIC 企业培训协作诉求');await material('material_outline','SYNTHETIC 培训资料目录');
 phase='INDEPENDENT_REVIEW';await select(specialist,id);specialist.$('prep-reason').value='SYNTHETIC 专员独立核对';await invoke(specialist,'prep-review');assert.equal(specialist.run('preparationView.preparation.state'),'REVIEWED');
 phase='OWNER_CONFIRM';await select(owner,id);owner.$('prep-reason').value='SYNTHETIC 本人确认';await invoke(owner,'prep-confirm');assert.equal(owner.run('preparationView.preparation.state'),'LOCAL_CONFIRMED');
 phase='SERVICE_SELECTION';await select(owner,id);await invoke(owner,'service-plan-prepare');await invoke(owner,'service-selection-read');await invoke(owner,'service-selection-generate');assert(owner.run('serviceSelectionView')!==null,owner.$('service-selection-status').textContent);owner.$('service-selection-confirm').checked=true;owner.$('service-plan-reason').value='SYNTHETIC 明确采用NO_MODEL方案';await invoke(owner,'service-plan-adopt');assert(owner.run('servicePlanView.plan_id'),owner.$('service-plan-error').textContent);await verify(owner,'P1');
 phase='RESOURCE_HOLDS';await invoke(owner,'resource-catalog');const opts=owner.$('resource-select').options;assert.equal(opts.length,2);
 for(let i=0;i<3;i++){
  owner.$('resource-select').value=opts[i%2].value;owner.$('resource-select').onchange?.();
  const start=new Date(Date.now()+(18+i*3)*3600000),end=new Date(start.getTime()+3600000);
  owner.$('resource-start').value=start.toISOString().slice(0,16);owner.$('resource-end').value=end.toISOString().slice(0,16);owner.$('resource-quantity').value='1';owner.$('resource-ttl').value='300';owner.$('resource-purpose').value='SYNTHETIC 本次资源 '+i;
  await invoke(owner,'resource-preview');assert(owner.run('resourcePreview')!==null,owner.$('resource-error').textContent);await invoke(owner,'resource-form','onsubmit');assert(owner.$('resource-current').children.length);
 }
 await invoke(owner,'resource-mine');const walk=e=>[e,...e.children.filter(x=>typeof x==='object').flatMap(walk)];const selectors=owner.$('resource-hold-items').children.flatMap(walk).filter(e=>e.dataset.combinationHold);assert.equal(selectors.length,3);
 for(const s of selectors){s.checked=true;s.onchange();}
 phase='RESOURCE_APPROVAL';owner.$('delivery-case').value=id;await invoke(owner,'delivery-preview');assert(owner.run('deliveryQuote')!==null,owner.$('delivery-error').textContent);await invoke(owner,'plan-approval-propose');await invoke(owner,'plan-approval-approve');await invoke(owner,'delivery-confirm');
 assert.equal(owner.run('deliveryHandles().length'),0,owner.$('delivery-error').textContent);
 await select(owner,id);await invoke(owner,'service-plan-prepare');await verify(owner,'P2');
 phase='OFFER';await select(specialist,id);await invoke(specialist,'dispatch-prepare');await until(()=>specialist.run('dispatchView')!==null);specialist.$('dispatch-executor').value='local-sample-executor';specialist.$('dispatch-offer-reason').value='SYNTHETIC 分派本人角色职责';await invoke(specialist,'dispatch-offer','onsubmit');assert.equal(specialist.run('dispatchView.current_offer.state'),'OFFERED');
 phase='INBOX';for(let i=0;i<40;i++){await invoke(executor,'notice-list');if(executor.$('notice-items').children.some(e=>e.dataset.noticeId))break;await new Promise(r=>setTimeout(r,100));}
 const notice=executor.$('notice-items').children.find(e=>e.dataset.noticeId);assert(notice);await notice.children.find(e=>e.tagName==='button').click();await until(()=>executor.run('noticeView')!==null);await invoke(executor,'notice-open');await invoke(executor,'notice-read');
 phase='ACCEPT';executor.$('dispatch-decision-reason').value='SYNTHETIC 执行者本人接受';await invoke(executor,'dispatch-accept');const step=executor.run('dispatchView.receipt_step_id');assert(step);
 phase='RECEIPT';await invoke(executor,'receipt-list');const eb=executor.$('receipt-items').children.find(e=>JSON.stringify(e).includes(step));assert(eb);await eb.click();await until(()=>executor.run('receiptView')!==null);executor.$('receipt-text').value='SYNTHETIC 本次本地人工协作输出';executor.$('receipt-source').value='SYNTHETIC 执行者原始回执';await invoke(executor,'receipt-submit','onsubmit');assert.equal(executor.run('receiptView.step.state'),'RECEIPT_RECORDED');
 await invoke(owner,'receipt-list');const ob=owner.$('receipt-items').children.find(e=>JSON.stringify(e).includes(step));assert(ob);await ob.click();await until(()=>owner.run('receiptView')!==null);owner.$('receipt-reason').value='SYNTHETIC 企业独立核对回执';await invoke(owner,'receipt-ack');assert.equal(owner.run('receiptView.step.state'),'LOCAL_ACKNOWLEDGED');const receiptProjection=JSON.parse(owner.run('JSON.stringify(receiptView)'));
 phase='FINAL_VERIFY';await select(owner,id);await invoke(owner,'service-plan-prepare');await verify(owner,'P3');await verify(owner,'P4');
 const plan=owner.run('servicePlanView');assert(plan.steps.every(s=>s.state==='VERIFIED'));assert.equal(plan.case_goal_completed,false);
 phase='ADMIN_PRIVATE_DENIAL';const denied=await fetch(input.base+'/api/preparations/'+id,{headers:{Authorization:'Bearer '+admin.$('token').value}});assert.equal(denied.status,403);
 process.stdout.write(JSON.stringify({result:'PASS',scope:'NORMAL_SAMPLE_PASSWORD_ENTRY_REAL_HTTP_WITH_NODE_DOM_NOT_BROWSER',preparation_id:id,step,plan,receipt:receiptProjection,calls,source_page_sha256:require('crypto').createHash('sha256').update(html).digest('hex'),admin_private_denied:403,real_model_calls:0})+'\n');
})().catch(e=>{process.stderr.write(JSON.stringify({result:'FAIL',phase,type:e.name,reason:String(e.message).slice(0,400),calls})+'\n');process.exitCode=1;});
