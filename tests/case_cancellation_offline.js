// Execute the actual cancellation UI in NodeVM; never launch a browser.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('src/parkweave/web.html','utf8');
const code=html.slice(html.indexOf('// Case cancellation: opaque'),html.indexOf('// Internal offers share'));
const requestedMode=process.argv[2],after=requestedMode.startsWith('after_'),mode=after?requestedMode.slice(6):requestedMode,id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',cid='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',key='cccccccc-cccc-4ccc-8ccc-cccccccccccc';
let checks=0;const check=v=>{checks++;assert(v);};
class Element{constructor(){const classes=new Set();this.classList={add:(...names)=>names.forEach(n=>classes.add(n)),remove:(...names)=>names.forEach(n=>classes.delete(n)),contains:n=>classes.has(n)};this.hidden=false;this.disabled=false;this.checked=false;this.value='';this.textContent='';}closest(){return null;}replaceChildren(){}append(){}reset(){}}
const elements=new Map(),$=name=>{if(!elements.has(name))elements.set(name,new Element());return elements.get(name);};
const storage={},calls=[],events=[];
const context=vm.createContext({$,console,Date,Map,Set,JSON,Number,String,Error,encodeURIComponent,crypto:{randomUUID:()=>key},
 localStorage:{getItem:n=>storage[n]??null,setItem:(n,v)=>{storage[n]=v;},removeItem:n=>{delete storage[n];},},
 document:{querySelectorAll:()=>[],addEventListener:(...args)=>events.push(args)},
 prepContext:()=>({id,token:'PRIVATE_TOKEN',generation:context.generation}),prepCurrent:c=>c.id===id&&c.generation===context.generation,
 prepCall:(path,method,body,key,c)=>new Promise((resolve,reject)=>calls.push({path,method,body,key,c,resolve,reject})),
 clearPreparation:()=>{context.preparationView=null;vm.runInContext('clearCaseCancellation()',context);},
 preparationView:{preparation:{case_id:cid},case_cancelled:false},generation:1,
 prepCommandPending:null,prepRecoveryHandle:null,prepRecoveryChecking:false,caseFactPending:null,materialReusePending:null,
 objectionLock:()=>false,localCaseLocked:()=>false,dispatchPending:null,servicePlanPending:null,servicePlanRecoveryHandle:null});
// Object.keys(storage interface) uses enumerable native localStorage entries.
context.localStorage=new Proxy(context.localStorage,{ownKeys:()=>Object.keys(storage),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
vm.runInContext(code,context);
const x={scope:after?'SYNTHETIC_CASE_CANCEL_AFTER_ACCEPT_BEFORE_FIRST_RECEIPT':'SYNTHETIC_CASE_CANCEL_BEFORE_FIRST_ACCEPT',actor_id:'fixture-a',preparation_id:id,case_id:cid,
 preparation_revision:5,lifecycle_revision:0,source_sha256:'a'.repeat(64),blockers:[],can_cancel:true,case_state:'NEEDS_INPUT',resource_release_automatic:false,restore_supported:false};
const h={v:1,actor:'fixture-a',id,case:cid,key,revision:0,expires:Date.now()+86400000},name='parkweave.case-cancel.v1.'+id+'.fixture-a';
if(after){h.v=2;h.stage='BEFORE_RECEIPT';}
const result=()=>({scope:x.scope,status:'COMMITTED',historical_only:true,automatically_replayed:false,event_id:key,
 event:{scope:x.scope,actor_id:h.actor,preparation_id:id,case_id:cid,request_key:key,revision:1,action:after?'CANCEL_BEFORE_RECEIPT':'CANCEL_BEFORE_ACCEPT',case_state:'CANCELLED',resource_release_automatic:false},current:{...x,can_cancel:false,case_state:'CANCELLED',lifecycle_revision:1,blockers:['CASE_ALREADY_CANCELLED']}});
const run=s=>vm.runInContext(s,context),tick=()=>new Promise(r=>setImmediate(r));
async function read(){const p=run('readCaseCancellation()');calls.at(-1).resolve(after?{...x,scope:'SYNTHETIC_CASE_CANCEL_BEFORE_FIRST_ACCEPT',can_cancel:false,blockers:['HISTORICAL_ACCEPTANCE_NOT_SUPPORTED']}:x);if(after){await tick();check(calls.at(-1).path.endsWith('/case-cancellation-before-receipt'));calls.at(-1).resolve(x);}await p;}
(async()=>{
 if(mode==='lost_response'){
  await read();$('case-cancel-reason').value='PRIVATE_REASON';$('case-cancel-confirm').checked=true;
  const p=run('submitCaseCancellation()');check(calls.at(-1).method==='POST');const raw=storage[name];check(raw&&!raw.includes('PRIVATE_REASON')&&!raw.includes('PRIVATE_TOKEN'));
  calls.at(-1).reject(Error('dropped response after commit'));await tick();check(calls.at(-1).method==='GET'&&calls.at(-1).path.endsWith('/recovery/'+key));calls.at(-1).resolve(result());await p;
  check(!storage[name]&&context.preparationView.case_cancelled&&$('case-cancel-form').hidden);check(calls.filter(c=>c.method==='POST').length===1);
 }else if(mode==='cold_recovery'||mode==='unknown_not_observed'||mode==='corrupt_proof'||mode==='revoked'){
  storage[name]=JSON.stringify(h);await read();check($('case-cancel-recover').hidden===false&&$('case-cancel-submit').disabled);
  const p=run('recoverCaseCancellation()');check(calls.at(-1).method==='GET'&&calls.at(-1).path.endsWith(key));
  if(mode==='revoked')calls.at(-1).reject(Object.assign(Error('403'),{status:403}));
  else if(mode==='unknown_not_observed')calls.at(-1).resolve({scope:x.scope,status:'NOT_OBSERVED',historical_only:true,automatically_replayed:false,current:x});
  else {const r=result();if(mode==='corrupt_proof')r.event.actor_id='fixture-b';calls.at(-1).resolve(r);}
  await p;
  if(mode==='cold_recovery')check(!storage[name]&&context.preparationView.case_cancelled);
  else check(!!storage[name]&&$('case-cancel-form').hidden);
  check(!calls.some(c=>c.method==='POST'));
 }else if(mode==='late_read'){
  const p=run('readCaseCancellation()');run('clearCaseCancellation()');context.generation++;
  calls.at(-1).resolve(x);await p;check(run('caseCancelView')===null&&$('case-cancel-form').hidden);check(calls.length===1);
 }else if(mode==='late_post'){
  await read();$('case-cancel-reason').value='reason';$('case-cancel-confirm').checked=true;
  const p=run('submitCaseCancellation()');check(calls.at(-1).method==='POST');run('clearCaseCancellation()');context.generation++;
  calls.at(-1).resolve(result());await p;check(!!storage[name]&&run('caseCancelView')===null);check(calls.length===(after?3:2));
 }else if(mode==='pending_other_operation'){
  await read();context.prepRecoveryHandle={key:'other'};$('case-cancel-reason').value='reason';$('case-cancel-confirm').checked=true;
  let error=false;try{await run('submitCaseCancellation()');}catch(e){error=true;}check(error&&calls.length===(after?2:1)&&!storage[name]);
 }else if(mode==='late_recovery'){
  storage[name]=JSON.stringify(h);await read();const p=run('recoverCaseCancellation()');run('clearCaseCancellation()');context.generation++;calls.at(-1).resolve(result());await p;check(!!storage[name]&&run('caseCancelView')===null);check(!calls.some(c=>c.method==='POST'));
 }else if(mode==='wrong_scope'){
  storage[name]=JSON.stringify(h);await read();const p=run('recoverCaseCancellation()');const r=result();r.scope='SYNTHETIC_CASE_CANCEL_BEFORE_FIRST_ACCEPT';calls.at(-1).resolve(r);await p;check(!!storage[name]&&run('caseCancelView').case_state!=='CANCELLED');check(calls.at(-1).path.includes('/case-cancellation-before-receipt/recovery/'));
 }else if(mode==='late_receipt'){
  await read();run('renderCaseCancellation('+JSON.stringify(result().current)+')');
  const renderer=html.split('\n').find(line=>line.startsWith('function renderReceipt('));
  Object.assign(context,{receiptCtx:()=>({}),receiptLabels:{AWAITING_RECEIPT:'等待执行者回执'},runAccessStatusView:null,receiptLocalPending:null,textElement:()=>new Element(),renderLocalExecution:le=>{$('receipt-local-execution-button').disabled=le.can_execute!==true;}});
  context.rx={step:{id,case_id:cid,preparation_id:id,state:'AWAITING_RECEIPT',revision:1,goal:'SYNTHETIC'},case_cancelled:false,role:'service_executor',dependency:'CURRENT',is_current_step:true,current_receipt:null,local_execution:{enabled:true,can_execute:true},receipt_history:[],history:[]};
  vm.runInContext(renderer,context);run('renderReceipt(rx)');check($('receipt-submit').hidden&&$('receipt-submit-button').disabled&&$('receipt-local-execution-button').disabled&&$('receipt-summary').textContent.includes('已取消'));
 }else if(mode==='cancelled_dispatch'||mode==='late_dispatch'){
  const dcode=html.slice(html.indexOf('function renderDispatch('),html.indexOf('async function loadDispatch('));
  // Use only this renderer's function; following unrelated functions are excluded.
  const start=dcode.indexOf('function renderDispatch(');let brace=dcode.indexOf('{',start),depth=1,end=brace+1;for(;depth&&end<dcode.length;end++){if(dcode[end]==='{')depth++;if(dcode[end]==='}')depth--;}
  Object.assign(context,{dispatchCtx:()=>({}),textElement:()=>new Element(),dispatchLabels:{OFFERED:'等待执行者决定'},dispatchPendingUI:()=>{},dispatchDraft:()=>'',handoffControls:()=>{}});
  if(mode==='late_dispatch'){context.preparationView.preparation.id=id;context.preparationView.case_cancelled=true;}
  context.dx={preparation_id:id,case_cancelled:mode!=='late_dispatch',goal:'Case',role:'service_executor',dispatch_id:id,revision:1,preparation_revision:5,current_offer:{id:key,state:'OFFERED',executor_id:'executor-a',reason:'history'},is_current_offer:true,dependency:'CURRENT',history:[]};
  vm.runInContext(dcode.slice(start,end),context);run('renderDispatch(dx,null)');check($('dispatch-decision').hidden&&$('dispatch-summary').textContent.includes('已取消'));
 }
 console.log(JSON.stringify({mode:requestedMode,checks,scope:'NODE_VM_DOM_FETCH_DOUBLES_ONLY'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
