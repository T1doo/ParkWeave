// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync(process.argv[3]||'src/parkweave/web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
let nextRequestKey=99;const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.options=[];this.listeners={};}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 reset(){}addEventListener(n,f){this.listeners[n]=f;}setAttribute(){}removeAttribute(){}
 closest(){return null;}querySelectorAll(){return [];}scrollIntoView(){this.scrolled=true;}
 get firstElementChild(){return this.children[0];}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
const elements=new Map(),$=name=>{if(!elements.has(name)){const e=new Element();e.id=name;elements.set(name,e);}return elements.get(name);};
const store={},calls=[],events=[];
const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},
 {ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
const context=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,
 crypto:{randomUUID:()=>id(nextRequestKey++)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},
 document:{getElementById:$,createElement:t=>new Element(t),querySelectorAll:()=>[],body:new Element('body'),addEventListener:(...a)=>events.push(a),execCommand:()=>false},
 window:{addEventListener:(...a)=>events.push(a)},
 fetch:(path,options)=>new Promise((resolve,reject)=>calls.push({path,options,resolve,reject}))});
vm.runInContext(code,context);$('token').value='[REDACTED_SYNTHETIC_SESSION]';
const run=s=>vm.runInContext(s,context),tick=()=>new Promise(r=>setImmediate(r));
function finish(call,status,value){call.resolve({status,ok:status>=200&&status<300,json:async()=>value});}
function projection(target,prep=id(3),receipt=id(4)){
 return {scope:'CURRENT_OWNER_SYNTHETIC_CASE_WORKLIST',read_only:true,automatically_replayed:false,recorded_states_only:true,next_after:null,
 items:[{case_id:id(1),run_id:id(2),preparation_id:prep,receipt_step_id:target==='receipt'?receipt:null,title:'SYNTHETIC item',label:'recorded',attention:'WAITING_RECEIPT',waiting_on:'OWNER',open_target:target,evidence_verified:false,case_goal_completed:false,resource_release_required_separately:false}]};
}
async function queue(target,prep,receipt){const p=$('case-worklist-read').onclick();finish(calls.at(-1),200,projection(target,prep,receipt));await p;return $('case-worklist-items').children[0].children.find(e=>e.tagName==='button');}
function material(){return {preparation:{id:id(3),case_id:id(1),run_id:id(2),owner_id:'fixture-a',state:'IN_PREPARATION',revision:1,goal:'PRIVATE_MATERIAL_A'},current_materials:[{id:id(6),slot:'need_summary',version:1,text:'PRIVATE_BODY_A',source_kind:'USER_STATEMENT',source_label:'SYNTHETIC'}],material_history:[],history:[]};}
function receipt(){return {step:{id:id(4),preparation_id:id(5),case_id:id(7),run_id:id(8),state:'AWAITING_RECEIPT',revision:1,goal:'CURRENT_RECEIPT_B'},role:'enterprise_operator',dependency:'CURRENT',is_current_step:true,current_receipt:null,receipt_history:[],history:[],local_execution:{}};}
async function flushOtherGets(){for(let i=0;i<12;i++){for(const c of calls){if(!c.finished){c.finished=true;finish(c,500,{});}}await tick();}}


const [route,variant]=mode.split(':'),fence={generation:id(90),preparation_id:id(3),plan_id:id(80),plan_revision:3,epoch:2},recon=route.startsWith('reconcile'),after=route==='before_receipt';
const reconScope='SYNTHETIC_MANUAL_RECEIPT_CASE_CANCELLATION_RECONCILIATION';
const makeView=(epoch=2)=>{
 const x={scope:recon?reconScope:after?'SYNTHETIC_CASE_CANCEL_AFTER_ACCEPT_BEFORE_FIRST_RECEIPT':'SYNTHETIC_CASE_CANCEL_BEFORE_FIRST_ACCEPT',actor_id:'fixture-a',preparation_id:id(3),case_id:id(1),preparation_revision:4,lifecycle_revision:0,source_sha256:(epoch===2?'a':'b').repeat(64),case_state:route==='reconcile_request'||!recon?'NEEDS_INPUT':'RECONCILING',blockers:[],resource_release_automatic:false,restore_supported:false,can_cancel:!recon,can_request:route==='reconcile_request',can_reconcile:route==='reconcile_record',can_confirm:route==='reconcile_finish',request_event_id:id(20),reconciliation_event_id:id(21),receipts:[],history:[],source:{}};
 if(route==='reconcile_record')x.receipts=[{step_id:id(4),receipt_id:id(5),version:1,receipt_sha256:'c'.repeat(64)}];
 if(variant!=='ordinary')x.business_frontier={...fence,epoch};
 return x;
};
function setup(){run(`preparationId='${id(3)}';prepRole='enterprise_operator';preparationView={preparation:{id:'${id(3)}',case_id:'${id(1)}',owner_id:'fixture-a',state:'LOCAL_CONFIRMED',revision:4}};preparationContext=prepContext()`);}
async function read(x){
 const pending=run(recon?'readCaseReconciliation()':'readCaseCancellation()');const first=calls.at(-1);
 if(after){finish(first,200,{...x,scope:'SYNTHETIC_CASE_CANCEL_BEFORE_FIRST_ACCEPT',can_cancel:false,blockers:['HISTORICAL_ACCEPTANCE_NOT_SUPPORTED']});await tick();check(calls.at(-1).path.endsWith('/case-cancellation-before-receipt'));}
 finish(calls.at(-1),200,x);await pending;
}
function choose(){if(recon){$('case-reconcile-confirm').checked=true;$('case-reconcile-reason').value='SYNTHETIC explicit cancellation review';run("caseReconChoices.forEach(s=>s.value='KNOWN_LOCAL_RESULT')");}else{$('case-cancel-confirm').checked=true;$('case-cancel-reason').value='SYNTHETIC explicit cancellation';}}
function submit(){return run(recon?`submitCaseReconciliation('${route==='reconcile_request'?'REQUEST_CANCEL':route==='reconcile_record'?'RECONCILE':'CONFIRM_CANCEL'}')`:'submitCaseCancellation()');}
(async()=>{
 setup();const x=makeView();
 if(variant==='malformed'){x.business_frontier={...fence,epoch:-1};await read(x);check(run(recon?'caseReconReadContext===null':'caseCancelReadContext===null'));choose();await submit();check(calls.every(c=>(c.options.method||'GET')==='GET'));}
 else{
 await read(x);choose();const contextName=recon?'caseReconReadContext':'caseCancelReadContext',viewName=recon?'caseReconView':'caseCancelView';
 if(variant==='stale_context'||variant==='stale_source'){
  if(variant==='stale_context')run('prepGeneration++');else run(viewName+".source_sha256='b'.repeat(64)");
  await assert.rejects(submit());check(calls.every(c=>(c.options.method||'GET')==='GET'));check(Object.keys(store).length===0);
 }else{
  if(variant!=='ordinary'){check(run('Object.isFrozen('+contextName+'.businessFrontier)'));run(viewName+'.business_frontier.epoch=9');}
  const pending=submit(),post=calls.at(-1),payload=JSON.parse(post.options.body);check(post.options.method==='POST');
  check(payload.expected_source_sha256==='a'.repeat(64));check(recon?post.path.endsWith('/case-cancellation-reconciliation'):post.path.endsWith(after?'/case-cancellation-before-receipt':'/case-cancellation'));
  if(variant==='ordinary'){check(!Object.hasOwn(payload,'expected_business_frontier'));check(!Object.hasOwn(run(contextName),'businessFrontier'));}
  else check(JSON.stringify(payload.expected_business_frontier)===JSON.stringify(fence));
  const handles=Object.entries(store).filter(([k])=>k.startsWith(recon?'parkweave.case-reconcile.v1.':'parkweave.case-cancel.v1.'));check(handles.length===1);const handle=JSON.parse(handles[0][1]);check(!Object.hasOwn(handle,'expected_business_frontier')&&!JSON.stringify(handle).includes('SYNTHETIC explicit'));
  if(variant==='classification'){
   context.probeOptions=post.options;context.probePath=post.path;const detail='captured original business frontier changed; fresh original GET required';context.exactDetail=detail;
   check(run('cancelFrontierExplicitlyRejected(probePath,409,{detail:exactDetail},probeOptions)'));
   for(const status of [400,403,422,500]){context.probeStatus=status;check(!run('cancelFrontierExplicitlyRejected(probePath,probeStatus,{detail:exactDetail},probeOptions)'));}
   for(const changed of [detail+' extra','prefix '+detail,'stale source',null]){context.probeDetail=changed;check(!run('cancelFrontierExplicitlyRejected(probePath,409,{detail:probeDetail},probeOptions)'));}
   context.foreignPath=post.path.replace(id(3),id(999));check(!run('cancelFrontierExplicitlyRejected(foreignPath,409,{detail:exactDetail},probeOptions)'));context.foreignPath=post.path+'/recovery/'+id(999);check(!run('cancelFrontierExplicitlyRejected(foreignPath,409,{detail:exactDetail},probeOptions)'));context.foreignPath='/api/preparations/'+id(3)+'/local-case/commands';check(!run('cancelFrontierExplicitlyRejected(foreignPath,409,{detail:exactDetail},probeOptions)'));
   check(!run('cancelFrontierExplicitlyRejected(probePath,409,{detail:exactDetail},{...probeOptions})'));
   const oldBody=post.options.body,oldMethod=post.options.method;post.options.method='GET';check(!run('cancelFrontierExplicitlyRejected(probePath,409,{detail:exactDetail},probeOptions)'));post.options.method=oldMethod;
   for(const mutate of [x=>delete x.expected_business_frontier,x=>x.expected_business_frontier.epoch=3,x=>x.case_id=id(999),x=>x.expected_source_sha256='b'.repeat(64)]){const copy=JSON.parse(oldBody);mutate(copy);post.options.body=JSON.stringify(copy);check(!run('cancelFrontierExplicitlyRejected(probePath,409,{detail:exactDetail},probeOptions)'));}post.options.body=oldBody;
   context.mutableOptions={...post.options};run('capturedCancelFrontierRequests.set(mutableOptions,{...capturedCancelFrontierRequests.get(probeOptions)})');check(!run('cancelFrontierExplicitlyRejected(probePath,409,{detail:exactDetail},mutableOptions)'));
   run('capturedCancelFrontierRequests.set(mutableOptions,Object.freeze({...capturedCancelFrontierRequests.get(probeOptions),fence:{...capturedCancelFrontierRequests.get(probeOptions).fence}}))');check(!run('cancelFrontierExplicitlyRejected(probePath,409,{detail:exactDetail},mutableOptions)'));
  }else if(variant==='stale_retry'){
   finish(post,409,{detail:'captured original business frontier changed; fresh original GET required'});await pending;check(run('entryWriteRequests.size')===0);check(Object.keys(store).length===0);
   await read(makeView(3));choose();submit();const fresh=calls.at(-1);check(fresh.options.method==='POST');check(JSON.parse(fresh.options.body).expected_business_frontier.epoch===3);check(fresh.options.headers['Idempotency-Key']!==post.options.headers['Idempotency-Key']);
  }else if(variant==='other_conflict'){
   finish(post,409,{detail:'SYNTHETIC unrelated ambiguous conflict'});await pending;check(run('entryWriteRequests.size')===1);
  }else if(variant==='unknown'){
   post.reject(Error('SYNTHETIC response lost'));await tick();const recovery=calls.at(-1);check(recovery.options.method==='GET');check(recovery.path.endsWith('/recovery/'+handle.key));finish(recovery,200,{scope:x.scope,status:'NOT_OBSERVED',historical_only:true,automatically_replayed:false,current:makeView(),event:null});await pending;check(Object.keys(store).length===1);check(calls.filter(c=>c.options.method==='POST').length===1);check(run(contextName+'.businessFrontier.epoch')===2);
  }
 }
 }
 console.log(JSON.stringify({scope:'ACTUAL_FULL_HTML_CONTROLLED_CANCEL_PREFLIGHT_AND_FETCH_DOUBLES',route,variant,checks,actual_http:false,real_browser:'NOT_RUN',backend_no_effect_proof:'SEPARATE_ACTUAL_BACKEND_TEST_REQUIRED',eligibility:'CONTROLLED_ALLOW_FLAGS_ONLY_TRACKED33_BEFORE_RECEIPT_RECONCILIATION_REMAIN_REJECTED'}));process.exit(0);
})().catch(error=>{console.error(JSON.stringify({message:error.message,stack:error.stack,calls:calls.map(c=>({path:c.path,method:c.options.method,body:c.options.body}))}));process.exit(1);});
