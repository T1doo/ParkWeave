'use strict';
// Full served page script, actual HTTP, controlled DOM/storage only. Not a browser.
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const crypto=require('node:crypto').webcrypto;
const input=JSON.parse(fs.readFileSync(0,'utf8'));let phase='LOAD_PAGE';
(async()=>{
 const page=await (await fetch(input.base+'/')).text();
 const pending=await (await fetch(input.base+'/local-command-pending.js')).text();
 const nodes=new Map();
 const node=id=>({id,value:'',hidden:false,disabled:false,textContent:'',children:[],dataset:{},attributes:{},
  replaceChildren(){this.children=[]},append(...items){this.children.push(...items)},setAttribute(k,v){this.attributes[k]=v},
  removeAttribute(k){delete this.attributes[k]},classList:{toggle(){}},focus(){},reportValidity(){return true},
  querySelector(){return nodes.get('evidence-submit')}});
 for(const match of page.matchAll(/\bid="([^"]+)"/g))nodes.set(match[1],node(match[1]));
 nodes.set('evidence-submit',node('evidence-submit'));
 const $=id=>{assert(nodes.has(id));return nodes.get(id)};
 const actionIds=['request-changes','review','confirm','reopen'];
 for(const id of actionIds)$(id).dataset.action={'request-changes':'REQUEST_CHANGES',review:'REVIEW',confirm:'CONFIRM',reopen:'REOPEN'}[id];
 const document={getElementById:$,createElement:()=>node('new'),querySelectorAll:selector=>selector==='[data-action]'?actionIds.map($):[...nodes.values()]};
 const disk=new Map(),localStorage={getItem:k=>disk.get(k)??null,setItem:(k,v)=>disk.set(k,v),removeItem:k=>disk.delete(k)};
 let queue=Promise.resolve();const locks={request:(key,options,fn)=>{const p=queue.then(fn);queue=p.catch(()=>{});return p}};
 let requests=[];
 const c=vm.createContext({crypto,TextEncoder,AbortSignal,document,localStorage,navigator:{locks},window:{innerWidth:1440,addEventListener(){}},setTimeout,clearTimeout,
  fetch:async(path,options={})=>{requests.push({method:options.method||'GET',path});return fetch(input.base+path,{...options,headers:{...options.headers,...(path==='/api/local/session'?{Origin:input.base}:{})}})}});
 vm.runInContext(pending,c);vm.runInContext(page.match(/<script>([\s\S]*?)<\/script>/)[1],c);
 vm.runInContext('const actualPerform=perform;let activeTask;perform=fn=>(activeTask=actualPerform(fn));',c);
 const task=async code=>{vm.runInContext(code,c);await vm.runInContext('activeTask',c);assert.equal(vm.runInContext('unknown',c),null);assert(!/失败|未知|不正确|不可用|未完成|条件已变化/.test($('feedback').textContent));};
 async function login(role){
  $('role').value=role;$('password').value=input.passwords[role];
  await task("$('login').onsubmit({preventDefault(){}})");assert.equal($('workspace').hidden,false);
  assert.equal($('password').value,'');assert.equal(vm.runInContext('role',c),role==='enterprise'?'enterprise_operator':'park_specialist');
 }
 function logout(){vm.runInContext("$('logout').onclick()",c);assert.equal(vm.runInContext('bearer',c),'');assert.equal($('workspace').hidden,true);assert.equal($('materials').children.length,0);}
 async function choose(id){const b=$('items').children.find(n=>n.dataset.preparationId===id);assert(b);b.onclick();await vm.runInContext('activeTask',c);assert.equal(vm.runInContext('selected',c),id);}
 async function evidence(slot,text,label){$('slot').value=slot;$('source-kind').value='DOCUMENT_EXCERPT';$('material-text').value=text;$('source-label').value=label;await task("$('evidence-form').onsubmit({preventDefault(){}})");}
 async function decision(id,reason){$('reason').value=reason;await task("$('"+id+"').onclick()");}
 phase='LOGIN_ENTERPRISE';await login('enterprise');
 if(input.reopen){
  phase='READ_PERSISTED';await choose(input.preparation_id);
  const snapshot=JSON.parse(vm.runInContext('JSON.stringify(current)',c));
  logout();await login('specialist');await choose(input.preparation_id);
  const reviewerSnapshot=JSON.parse(vm.runInContext('JSON.stringify(current)',c));
  const assignedView=JSON.parse(JSON.stringify(snapshot));
  assert.equal(assignedView.preparation.request_intent,null);delete assignedView.preparation.request_intent;
  assert.deepEqual(reviewerSnapshot,assignedView);logout();
  assert.equal(requests.filter(r=>r.method==='POST'&&r.path!=='/api/local/session').length,0);
  process.stdout.write(JSON.stringify({scope:'FULL_SERVED_PAGE_JS_OVER_REAL_HTTP_NOT_BROWSER',snapshot,readonly_reopen:true,role_logout_private_cleared:true,write_requests_after_restart:0})+'\n');return;
 }
 phase='SUBMIT';$('goal').value='SYNTHETIC normal CLI installation · 培训资料';
 await task("$('submit-case').onsubmit({preventDefault(){}})");assert.equal(vm.runInContext('run.state',c),'SUCCEEDED');
 phase='BEGIN_PREPARATION';await task("$('begin-materials').onclick()");
 const id=vm.runInContext('selected',c);assert(id);
 phase='FIRST_EVIDENCE';await evidence('need_summary','\u0085SYNTHETIC 申请初稿\u0085','SYNTHETIC v1');logout();
 phase='REQUEST_CHANGES';await login('specialist');await choose(id);await decision('request-changes','SYNTHETIC 补充材料目录并修订摘要');logout();
 phase='CORRECTIONS';await login('enterprise');await choose(id);
 await evidence('need_summary','\ufeffSYNTHETIC 修订摘要\ufeff','SYNTHETIC v2');await evidence('material_outline','SYNTHETIC 培训方案、人员目录','SYNTHETIC outline v1');logout();
 phase='REVIEW';await login('specialist');await choose(id);await decision('review','SYNTHETIC 专员核对当前资料');logout();
 phase='CONFIRM';await login('enterprise');await choose(id);await decision('confirm','SYNTHETIC 申请人确认当前核对资料');
 const snapshot=JSON.parse(vm.runInContext('JSON.stringify(current)',c));
 assert.equal(snapshot.preparation.state,'LOCAL_CONFIRMED');assert.equal(snapshot.preparation.revision,7);
 assert.deepEqual(snapshot.history.map(e=>e.action),['CREATE','ADD_EVIDENCE','REQUEST_CHANGES','ADD_EVIDENCE','ADD_EVIDENCE','REVIEW','CONFIRM']);
 logout();assert.equal(disk.size,0);
 process.stdout.write(JSON.stringify({scope:'FULL_SERVED_PAGE_JS_OVER_REAL_HTTP_NOT_BROWSER',preparation_id:id,snapshot,
  source_page_bytes:Buffer.byteLength(page),source_page_sha256:require('node:crypto').createHash('sha256').update(page).digest('hex'),role_logout_private_cleared:true,pending_nonsecret_storage_empty:true,
  writes:requests.filter(r=>r.method==='POST'&&r.path!=='/api/local/session').length})+'\n');
})().catch(e=>{process.stderr.write(JSON.stringify({phase,error_type:e.name,reason:'ASSERTION_OR_HTTP_FAILURE_NO_ARGUMENTS'})+'\n');process.exitCode=1});
