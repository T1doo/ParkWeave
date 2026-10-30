// Actual page handlers with controlled async/DOM seams. Not a browser or pixel check.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const crypto=require('node:crypto').webcrypto;
const page=fs.readFileSync('src/parkweave/local_preparation_web.html','utf8');
const part=(start,end)=>{const a=page.indexOf(start),b=page.indexOf(end,a);assert(a>=0&&b>a);return page.slice(a,b)};
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}};
function context(){
 const nodes=new Map();
 function node(id){return {id,value:'',hidden:false,disabled:false,textContent:'',children:[],
  replaceChildren(){this.children=[]},append(...items){this.children.push(...items)},setAttribute(){},
  classList:{toggle(){}},focus(){},querySelector(){return nodes.get('evidence-submit')}}}
 for(const match of page.matchAll(/\bid="([^"]+)"/g))nodes.set(match[1],node(match[1]));
 nodes.set('login-submit',node('login-submit'));nodes.set('evidence-submit',node('evidence-submit'));
 const $=id=>{assert(nodes.has(id),'actual page element missing: '+id);return nodes.get(id)};
 const document={createElement:()=>node('new'),querySelectorAll:selector=>{
  const result=[...nodes.values()].filter(n=>!['role','password','login-submit'].includes(n.id));
  if(selector.includes('#login '))result.push($('role'),$('password'),$('login-submit'));
  return result;
 }};
 const c=vm.createContext({assert,crypto,TextEncoder,AbortSignal,$,document,
  localStorage:{},navigator:{locks:{}},ParkWeavePending:{journal(){return {read:()=>null}}},
  feedback:()=>{},showPanel:()=>{},api:async()=>{throw Error('unexpected API call')},list:async()=>{}});
 vm.runInContext(`let bearer='',role='',actor='',actorScope=null,selected=null,current=null,run=null,catalog=null,
 busy=false,unknown=null,pendingJournal=null,credentialHash=null,epoch=0,runCursor=null,activePanel='materials',
 pageCursors=[null],pageIndex=0,nextPage=null;
 const states={},slots={need_summary:'Summary',material_outline:'Outline'},actions={};
 ${part('function el(','function clearPrivate(')}
 ${part('function clearPrivate(','async function secretDigest(')}
 async function secretDigest(){return 'b'.repeat(64)}
 ${part('async function perform(','async function list(')}
 ${part('async function open(',"$('submit-case').onsubmit=")}
 const realPerform=perform;let activeTask;perform=fn=>(activeTask=realPerform(fn));`,c);
 const resetStart=page.indexOf("$('clear-run').onclick=");
 if(resetStart>=0){const end=page.indexOf("$('read-run').onclick=",resetStart);vm.runInContext(page.slice(resetStart,end),c)}
 return {c,$};
}
const identity={bearer:'PUBLIC_TEST_LOGIN_ONLY',role:'enterprise_operator',actor_id:'test-a',
 actor:{id:'test-a',role:'enterprise_operator',park_id:'test-p',org_id:'test-o'},installation_id:'a'.repeat(64)};
const submit=c=>vm.runInContext("$('login').onsubmit({preventDefault(){}})",c);
const task=c=>vm.runInContext('activeTask',c);
const settle=()=>new Promise(resolve=>setImmediate(resolve));
async function duplicateLogin(){
 const {c,$}=context(),gate=deferred();let calls=0;
 c.api=async()=>{calls++;return gate.promise};$('role').value='enterprise';$('password').value='PUBLIC_NEGATIVE_PASSWORD';
 submit(c);const first=task(c),epoch=vm.runInContext('epoch',c);
 try{
  submit(c);assert.equal(vm.runInContext('epoch',c),epoch,'duplicate submit changed active login epoch');
  assert.equal(calls,1);assert($('password').disabled&&$('role').disabled&&$('login-submit').disabled);
 }finally{gate.resolve(identity);await first}
 assert.equal(vm.runInContext('bearer',c),identity.bearer);assert.equal($('workspace').hidden,false);
}
async function staleLogin(){
 const {c,$}=context(),digest=deferred();let reads=0;
 c.api=async()=>identity;c.secretDigest=()=>digest.promise;c.list=async()=>{reads++};
 $('role').value='enterprise';$('password').value='PUBLIC_NEGATIVE_PASSWORD';submit(c);const first=task(c);
 await settle();vm.runInContext("$('logout').onclick()",c);digest.resolve('b'.repeat(64));await first;
 assert.equal(vm.runInContext('bearer',c),'');assert.equal($('workspace').hidden,true);
 assert.equal($('login-card').hidden,false);assert.equal(reads,0,'stale login read private workspace');
}
async function itemDrafts(){
 const {c,$}=context();
 c.api=async path=>({preparation:{id:path.split('/').pop(),goal:'SYNTHETIC case',case_id:'test-case',revision:1,state:'IN_PREPARATION'},current_materials:[],history:[]});
 vm.runInContext("role='enterprise_operator'",c);
 const a='00000000-0000-0000-0000-000000000001',b='00000000-0000-0000-0000-000000000002';c.a=a;c.b=b;
 await vm.runInContext('open(a)',c);
 for(const id of ['material-text','source-label','reason'])$(id).value='SYNTHETIC private draft for A';
 $('slot').value='material_outline';$('source-kind').value='DOCUMENT_EXCERPT';
 await vm.runInContext('open(a)',c);assert.equal($('material-text').value,'SYNTHETIC private draft for A');
 await vm.runInContext('open(b)',c);
 for(const id of ['material-text','source-label','reason'])assert.equal($(id).value,'','A draft carried into B: '+id);
 assert.equal($('slot').value,'need_summary');assert.equal($('source-kind').value,'USER_STATEMENT');
 assert.equal(vm.runInContext('selected',c),b);
}
async function clearRun(){
 const {c,$}=context();let calls=0;c.api=async()=>{calls++;throw Error('local reset must not call API')};
 for(const state of ['FAILED','CANCELLED','SUCCEEDED']){
  c.state=state;vm.runInContext("role='enterprise_operator';run={id:'original-run',state};unknown=null;renderControls()",c);
  assert.equal($('clear-run').hidden,false);$('goal').value='SYNTHETIC prior request';
  vm.runInContext("unknown={action:'CREATE_RUN',request_key:'original-key'};renderControls()",c);
  assert.equal($('clear-run').disabled,true);vm.runInContext("$('clear-run').onclick()",c);
  assert.equal(vm.runInContext('run.id',c),'original-run');assert.equal(vm.runInContext('unknown.request_key',c),'original-key');
  vm.runInContext("unknown=null;renderControls();$('clear-run').onclick()",c);
  assert.equal(vm.runInContext('run',c),null);assert.equal($('create-case').disabled,false);
  assert.equal($('goal').value,'');assert.equal($('run-status').textContent,'');
 }
 assert.equal(calls,0);
}
(async()=>{
 const cases={duplicateLogin,staleLogin,itemDrafts,clearRun},results=[];
 for(const [name,check] of Object.entries(cases)){
  try{await check();results.push({name,status:'PASS'})}
  catch(error){results.push({name,status:'FAIL',reason:error.message})}
 }
 process.stdout.write(JSON.stringify({scope:'ACTUAL_PAGE_HANDLER_CONTRACT_WITH_CONTROLLED_ASYNC_AND_DOM_NOT_BROWSER',results})+'\n');
 if(results.some(row=>row.status!=='PASS'))process.exitCode=1;
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1});
