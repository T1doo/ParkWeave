// Actual shipped rendering/guide handlers; mechanical DOM only, no HTTP/browser claim.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),cp=require('child_process');
const baseline=cp.execFileSync('git',['show','82db2929f4b3e7ec9f0065c42febfff6a9be9a37:src/parkweave/web.html'],{encoding:'utf8'});
const support=fs.readFileSync('tests/ordinary_case_goal_record_pack_html.js','utf8').split('const until=')[0];
const fixture=JSON.parse(fs.readFileSync('docs/F2/evidence/again-role-readback-20261022/run23/result.json','utf8')).fresh_roles[0].plans[0];
let networkCalls=0;
function mechanicalPage(before=false){
 const adaptedFS={...fs,readFileSync:(name,...args)=>before&&name==='src/parkweave/web.html'?baseline:fs.readFileSync(name,...args)};
 const scope={require:name=>name==='fs'?adaptedFS:require(name),console:{log(){},error(){}},process,URL,URLSearchParams,Blob,TextEncoder,setTimeout,clearTimeout,
  fetch:async()=>{networkCalls++;throw Error('No real HTTP permitted by this presentation check');}};
 return vm.runInNewContext(support+`;page({base:'http://127.0.0.1',token:''},{},[],{});`,scope);
}
const walk=e=>[e,...(e.children||[]).filter(v=>typeof v==='object').flatMap(walk)];
const text=e=>(e.textContent||'')+(e.children||[]).map(v=>typeof v==='object'?text(v):v).join(' ');
const outside=e=>(e.textContent||'')+(e.children||[]).filter(v=>typeof v!=='object'||v.tagName!=='details').map(v=>typeof v==='object'?outside(v):v).join(' ');
function render(p,value,pending=false){p.context.fixture=structuredClone(value);p.context.pending=pending;p.run("servicePlanId=fixture.preparation_id;servicePlanPending=pending?{stage:'SUBMITTING'}:null;renderServiceCasePlan(fixture)");}
const summary=p=>p.$('service-plan-steps').children.map(card=>({id:card.dataset.serviceStepId,adapter:card.dataset.serviceAdapter,buttons:walk(card).filter(e=>e.tagName==='button').map(e=>({text:e.textContent,disabled:e.disabled,...e.dataset}))}));
async function bindings(p){p.context.invoked=[];p.run("servicePlanWrite=async(...args)=>{invoked.push(['action',...args])};servicePlanOpen=async(...args)=>{invoked.push(['open',...args])}");for(const e of walk(p.$('service-plan-steps')).filter(e=>e.tagName==='button'&&!e.disabled))await e.onclick();return JSON.parse(p.run('JSON.stringify(invoked)'));}
async function main(){
 const results=[];
 for(const role of ['enterprise_operator','park_specialist','service_executor'])for(const pending of [false,true]){
  const old=mechanicalPage(true),current=mechanicalPage(),value={...structuredClone(fixture),role};render(old,value,pending);render(current,value,pending);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(summary(current))),JSON.parse(JSON.stringify(summary(old))));assert.deepStrictEqual(await bindings(current),await bindings(old));
  assert.strictEqual(current.run('JSON.stringify(servicePlanView)'),old.run('JSON.stringify(servicePlanView)'));
  for(const card of current.$('service-plan-steps').children){
   const ref=card.children.find(e=>e.className==='service-step-reference'),actions=card.children.find(e=>e.className==='service-step-actions');
   assert(ref&&actions);assert.strictEqual(ref.children.find(e=>e.tagName==='code').textContent,card.dataset.serviceStepId);
   assert(walk(ref).every(e=>e.tagName!=='button'));assert(actions.children.every(e=>e.tagName==='button'));
   assert(walk(card).filter(e=>e.tagName==='button').every(e=>actions.children.includes(e)));
  }
  const detail=current.$('service-plan-coverage').children.find(e=>e.tagName==='details');assert(detail&&!detail.open);
  assert.strictEqual(detail.children[0].tagName,'summary');assert(text(detail).includes('LOCAL_MATERIAL_PREPARATION'));
  assert(!outside(current.$('service-plan-coverage')).includes('必需目标 LOCAL_MATERIAL_PREPARATION'));
  results.push({case:'original_render_and_action_binding_'+role+(pending?'_pending':''),status:'PASS'});
 }
 const current=mechanicalPage(),value=structuredClone(fixture);value.partial_adoption=true;value.binding_issues=['CHANGED'];value.owner_note_blockers=['MANUAL'];value.local_revision_required=true;value.required_goals=['SYNTHETIC_NEW_CURRENT_GOAL'];value.change_impact.unknown_scope=true;
 value.current_preview.constraint_evaluation={state:'UNKNOWN',unsupported_requirements:['SYNTHETIC_UNSUPPORTED_CONDITION']};value.current_preview.steps[0].issues=['MISSING'];value.current_preview.steps[0].constraint_impact={state:'CONFLICT'};
 value.current_preview.goal_coverage.push({goal:'SYNTHETIC_UNSUPPORTED_GOAL',status:'UNSUPPORTED'},{goal:'SYNTHETIC_FUTURE_GOAL',status:'FUTURE_STATUS'});value.steps[0].manually_locked=true;
 render(current,value);const visible=outside(current.$('service-plan-coverage'));
 for(const warning of ['受限步骤核对接单','PARTIAL','明确约束核对：UNKNOWN','SYNTHETIC_UNSUPPORTED_CONDITION','须在原入口补齐','与当前角色或前置约束冲突','SYNTHETIC_UNSUPPORTED_GOAL','SYNTHETIC_FUTURE_GOAL','旧采纳目标（历史）','原采用版本已变化','原人工协调说明仍须明确处理','依赖集合或旧依赖合同已变化','绑定变化须扩大','正式服务发布、审批及原Case真实目标完成仍未证明'])assert(visible.includes(warning),warning);
 const steps=outside(current.$('service-plan-steps'));assert(steps.includes('人工锁定')&&steps.includes('当前业务来源尚未满足'));
 assert(current.$('service-plan-history-summary').textContent.endsWith(' 条'));current.$('service-plan-history-details').open=true;current.run('clearServiceCasePlan()');
 assert.strictEqual(current.$('service-plan-history-details').open,false);assert.strictEqual(current.$('service-plan-history-summary').textContent,'计划和步骤历史');assert.strictEqual(current.$('service-plan-steps').children.length,0);assert.strictEqual(current.$('service-plan-coverage').children.length,0);assert.strictEqual(current.$('service-plan-history').children.length,0);
 results.push({case:'warnings_unknown_status_and_context_clear',status:'PASS'});
 const html=fs.readFileSync('src/parkweave/park_demo_web.html','utf8'),elements=new Map(),events={};
 for(const m of html.split('<script')[0].matchAll(/<([a-z][\w-]*)\b([^>]*)>/gi)){
  const attrs=m[2],id=attrs.match(/\bid="([^"]+)"/)?.[1],role=attrs.match(/data-role="([^"]+)"/)?.[1];if(!id&&!role)continue;
  elements.set(id||role,{id:id||role,tagName:m[1],textContent:'',disabled:attrs.includes('disabled'),dataset:{...(role?{role}:{}),...(id==='status'?{tone:'neutral'}:{})}});
 }
 const get=id=>elements.get(id),scope=vm.createContext({JSON,Error,location:{origin:'http://127.0.0.1'},document:{getElementById:get,querySelectorAll:s=>[...elements.values()].filter(e=>s==='button'?e.tagName==='button':s==='[data-role]'&&e.dataset.role)},window:{addEventListener:(e,fn)=>events[e]=fn,open:()=>null}});
 vm.runInContext(html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1],scope);
 get('sessions').files=[];await get('sessions').onchange();assert.strictEqual(get('status').dataset.tone,'neutral');assert(get('status').textContent.includes('等待选择'));
 get('sessions').files=[{size:2,text:async()=>'{}'}];await get('sessions').onchange();assert.strictEqual(get('status').dataset.tone,'error');assert(get('status').textContent.includes('未上传或使用'));assert(get('workspace-open').disabled);
 const file=JSON.stringify(Object.fromEntries(['enterprise','specialist','executor','second_enterprise','second_specialist','second_executor'].map((name,i)=>[name,String(i).repeat(43)])));
 let release;get('sessions').files=[{size:file.length,text:()=>new Promise(r=>release=r)}];const late=get('sessions').onchange();assert.strictEqual(get('status').dataset.tone,'neutral');assert(get('status').textContent.includes('正在本页核对'));assert(get('workspace-open').disabled);
 get('sessions').files=[{size:2,text:async()=>'{}'}];await get('sessions').onchange();release(file);await late;assert.strictEqual(get('status').dataset.tone,'error');assert(get('workspace-open').disabled);
 get('sessions').files=[{size:file.length,text:async()=>file}];await get('sessions').onchange();assert.strictEqual(get('status').dataset.tone,'success');assert(get('status').textContent.includes('本页内存')&&get('status').textContent.includes('不会自动办理'));assert(!get('workspace-open').disabled);assert(get('enterprise').disabled);
 get('workspace-open').onclick();assert.strictEqual(get('status').dataset.tone,'error');assert(get('status').textContent.includes('没有提交业务'));events.pagehide();assert(get('workspace-open').disabled);assert.strictEqual(get('status').dataset.tone,'neutral');assert(get('status').textContent.includes('等待选择'));assert.strictEqual(networkCalls,0);
 results.push({case:'guide_neutral_loading_error_success_late_read_and_popup_refusal',status:'PASS'});
 return {status:'PASS',paired_render_cases:6,preservation_and_guide_cases:2,results,actual_HTTP:0,business_POSTs:0,browser_runs:0,model_calls:0};
}
main().then(x=>{console.log(JSON.stringify(x,null,2));process.exit(0)}).catch(e=>{console.error(e.stack);process.exit(1)});
