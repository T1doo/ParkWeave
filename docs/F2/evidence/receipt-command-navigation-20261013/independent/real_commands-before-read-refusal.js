// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('src/parkweave/web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.options=[];this.listeners={};}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 reset(){}addEventListener(n,f){this.listeners[n]=f;}setAttribute(){}removeAttribute(){}
 closest(){return null;}querySelectorAll(){return [];}scrollIntoView(){this.scrolled=true;}
 get firstElementChild(){return this.children[0];}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
const elements=new Map(),$=name=>{if(!elements.has(name))elements.set(name,new Element());elements.get(name).id=name;return elements.get(name);};
const store={},calls=[],events=[];
const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},
 {ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
const context=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,
 crypto:{randomUUID:()=>id(99)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},
 document:{getElementById:$,createElement:t=>new Element(t),querySelectorAll:()=>[],body:new Element('body'),addEventListener:(...a)=>events.push(a),execCommand:()=>false},
 window:{addEventListener:(...a)=>events.push(a)},
 fetch:(path,options)=>new Promise((resolve,reject)=>calls.push({path,options,resolve,reject}))});
vm.runInContext(code,context);$('token').value='SYNTHETIC_SESSION_A';
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

function resourceView(){return {case_id:id(1),case_state:'NEEDS_INPUT',preparation_id:id(3),preparation_revision:1,link_revision:0,current:null,history:[]};}
function resourceCatalog(){return {preparation_revision:1,ready:true,items:[{eligible:true,combination:{id:id(11),members:[{resource_name:'SYNTHETIC_ROOM',starts_at:'2026-10-14',ends_at:'2026-10-15'}]}}]};}
(async()=>{
 const phase=mode.split('_').at(-1);
 if(mode==='dispatch_unknown_retry'){
  const view={dispatch_id:id(20),preparation_id:id(3),preparation_revision:1,revision:1,goal:'SYNTHETIC',role:'service_executor',dependency:'CURRENT',current_offer:{id:id(21),state:'OFFERED',executor_id:'executor-a',reason:'SYNTHETIC'},is_current_offer:true,current_receipt_step_id:null,history:[]};
  const load=run("loadDispatch('"+id(3)+"')");finish(calls.at(-1),200,view);await load;$('dispatch-decision-reason').value='SYNTHETIC_DECLINE';
  const first=$('dispatch-decline').onclick(),original=calls.at(-1);check(original.options.method==='POST');const body=original.options.body,key=original.options.headers['Idempotency-Key'];original.reject(Error('SYNTHETIC_LOST_RESPONSE'));await first;
  check(run('dispatchPending!==null'));check(run('entryWriteRequests.size===0'));
  const retry=$('dispatch-retry').onclick(),post=calls.at(-1);check(post.options.method==='POST');check(post.options.body===body);check(post.options.headers['Idempotency-Key']===key);finish(post,200,{dispatch_id:id(20),event:{revision:2}});await tick();view.revision=2;view.current_offer.state='DECLINED';finish(calls.at(-1),200,view);await retry;
  check(run('dispatchPending===null'));check(run('entryWriteRequests.size===0&&activeEntryWriteFlow===null'));check(calls.filter(c=>c.options.method==='POST').length===2);
 }else
 if(mode==='pure_resource_preview'){
  $('resource-select').value=id(11);$('resource-start').value='2026-10-14T10:00';$('resource-end').value='2026-10-14T11:00';$('resource-quantity').value='1';const nav=await queue('run');
  const preview=$('resource-preview').onclick(),old=calls.at(-1);check(old.options.method==='POST');check(old.path.endsWith('/preview'));check(run('activeEntryWriteFlow===null&&entryWriteRequests.size===0'));
  const before=calls.length;const navigation=nav.onclick();await tick();check(calls.length===before+1);check(calls.at(-1).options.method==='GET');finish(calls.at(-1),200,{state:'SUCCEEDED'});await navigation;
  finish(old,200,{resource_id:id(11),available:true,occupied_peak:0,capacity:1,available_quantity:1,server_time:'SYNTHETIC'});await preview;check(run('resourcePreview===null'));
 }else
 if(mode==='unrelated_get_failure'){
  const load=run("loadReceipt('"+id(4)+"')"),x=receipt();x.step.state='RECEIPT_RECORDED';x.current_receipt={version:1,text:'SYNTHETIC',source_sha256:'f'.repeat(64),source_kind:'SYNTHETIC',source_label:'SYNTHETIC',actor_id:'fixture-a'};finish(calls.at(-1),200,x);await load;
  $('receipt-reason').value='SYNTHETIC_ACK';const command=$('receipt-ack').onclick(),post=calls.at(-1);check(post.options.method==='POST');
  $('receipt-history-preparation').value=id(3);$('receipt-history-key').value=id(90);const unrelated=$('receipt-history-read').onclick();finish(calls.at(-1),500,{});await unrelated;
  finish(post,200,{event:{revision:2}});await tick();x.step.revision=2;x.step.state='LOCAL_ACKNOWLEDGED';finish(calls.at(-1),200,x);await command;
  check(run('activeEntryWriteFlow===null'));check(run('entryWriteRequests.size===0'));
 }else
 if(mode==='concurrent_ack_link'||mode==='concurrent_complete'){
  run("preparationId='"+id(3)+"';preparationView={preparation:{id:'"+id(3)+"',revision:1,state:'LOCAL_CONFIRMED'}};preparationContext={...prepContext(),caseId:'"+id(1)+"',revision:1};prepRole='enterprise_operator'");
  const res=run('loadCaseResources()');finish(calls.at(-1),200,resourceView());await tick();finish(calls.at(-1),200,resourceCatalog());await res;
  const load=run("loadReceipt('"+id(4)+"')"),x=receipt();x.step.state='RECEIPT_RECORDED';x.current_receipt={version:1,text:'SYNTHETIC',source_sha256:'f'.repeat(64),source_kind:'SYNTHETIC',source_label:'SYNTHETIC',actor_id:'fixture-a'};finish(calls.at(-1),200,x);await load;
  $('receipt-reason').value='SYNTHETIC_ACK';$('case-resource-choice').value=id(11);$('case-resource-reason').value='SYNTHETIC_LINK';
  const first=run("receiptCommand('ACKNOWLEDGE').catch(receiptError)");finish(calls.at(-1),200,{event:{revision:2}});await tick();const readback=calls.at(-1);check(readback.options.method==='GET');
  const before=calls.length;const second=$('case-resource-form').onsubmit({preventDefault(){}}).catch(e=>e);await tick();
  if(mode==='concurrent_complete'){
   check(calls.at(-1).options.method==='POST');const linkPost=calls.at(-1);x.step.revision=2;x.step.state='LOCAL_ACKNOWLEDGED';finish(readback,200,x);await first;
   finish(linkPost,200,{link_revision:1});await tick();const v=resourceView();v.link_revision=1;finish(calls.at(-1),200,v);await tick();finish(calls.at(-1),200,resourceCatalog());await second;
   check(run('activeEntryWriteFlow===null'));check(run('entryWriteRequests.size===0'));
  }else{check(calls.length===before);check(calls.filter(c=>c.options.method==='POST').length===1);const refusal=await second;check(refusal.message.includes('原入口'));x.step.revision=2;x.step.state='LOCAL_ACKNOWLEDGED';finish(readback,200,x);await first;check(run('activeEntryWriteFlow===null&&entryWriteRequests.size===0'));}
 }else
 if(mode.startsWith('history_')){
  $('receipt-history-preparation').value=id(3);$('receipt-history-key').value=id(90);const request=$('receipt-history-read').onclick(),old=calls.at(-1);
  $('receipt-history-result').append(new Element('p'));$('receipt-history-result').children[0].textContent='SYNTHETIC_PRIVATE_HISTORY';
  $('prep-summary').textContent='SYNTHETIC_PRIVATE_CURRENT';run('preparationView={privateMarker:true}');
  if(mode==='history_late'){
   const denial=run("apiCall('/api/runs/x').catch(pageError)");finish(calls.at(-1),403,{});await denial;
   check($('receipt-history-result').children.length===0);
   finish(old,200,{read_only:true,history_transport:'ISOLATED_P4_LIVE_ISSUER_HISTORY_GET_V1',preparation_id:id(3),scope:'ISOLATED_REGISTERED_P4_RECEIPT_EXECUTION_PREVIEW',formal_writes:0,automatically_replayed:false,status:'NOT_OBSERVED',result:null});await request;
   check($('receipt-history-result').children.length===0);
  }else{
   if(mode==='history_json403')old.resolve({status:403,ok:false,json:async()=>{throw Error('SYNTHETIC_INVALID_JSON');}});else finish(old,403,{});await request;
   check($('receipt-history-result').children.length===0);check($('prep-summary').textContent==='');check(run('preparationView===null'));check($('page-feedback').textContent.includes('权限'));
  }
 }else
 if(mode.startsWith('ack_')){
  const load=run("loadReceipt('"+id(4)+"')"),x=receipt();x.step.state='RECEIPT_RECORDED';x.current_receipt={version:1,text:'SYNTHETIC_RECEIPT',source_sha256:'f'.repeat(64),source_kind:'SYNTHETIC',source_label:'SYNTHETIC',actor_id:'fixture-a'};finish(calls.at(-1),200,x);await load;
  $('receipt-reason').value='SYNTHETIC_OWNER_ACK';const nav=await queue('run'),draft=run('receiptDraft()');
  const command=run("receiptCommand('ACKNOWLEDGE').catch(receiptError)"),post=calls.at(-1);check(post.options.method==='POST');check(JSON.parse(post.options.body).action==='ACKNOWLEDGE');const key=post.options.headers['Idempotency-Key'];check(!!key);
  if(phase==='unknown'){post.reject(Error('SYNTHETIC_LOST_RESPONSE'));await command;}
  if(phase==='verify'){finish(post,200,{event:{revision:2}});await tick();check(calls.at(-1).options.method==='GET');}
  const count=calls.length;const navigation=nav.onclick();await tick();check(calls.length===count);check(run('receiptDraft()')===draft);check(run('[...receiptRetries.values()].includes("'+key+'")'));
  check($('page-feedback').textContent.includes('原入口'));
  if(phase==='pending'){post.reject(Error('SYNTHETIC_LOST_RESPONSE'));await command;}
  if(phase==='verify'){calls.at(-1).reject(Error('SYNTHETIC_LOST_READBACK'));await command;}
  check(calls.filter(c=>c.options.method==='POST').length===1);
 }else if(mode.startsWith('link_')){
  run("preparationId='"+id(3)+"';preparationView={preparation:{id:'"+id(3)+"',revision:1,state:'LOCAL_CONFIRMED'}};preparationContext={...prepContext(),caseId:'"+id(1)+"',revision:1};prepRole='enterprise_operator'");
  const load=run('loadCaseResources()');finish(calls.at(-1),200,resourceView());await tick();finish(calls.at(-1),200,resourceCatalog());await load;
  $('case-resource-choice').value=id(11);$('case-resource-reason').value='SYNTHETIC_EXPLICIT_LINK';const nav=await queue('run'),draft=run('caseResourceDraft()');
  const command=$('case-resource-form').onsubmit({preventDefault(){}}),post=calls.at(-1);check(post.options.method==='POST');check(post.path==='/api/preparations/'+id(3)+'/resource-link');const key=post.options.headers['Idempotency-Key'];check(!!key);
  if(phase==='unknown'){post.reject(Error('SYNTHETIC_LOST_RESPONSE'));await command;}
  if(phase==='verify'){finish(post,200,{link_revision:1});await tick();check(calls.at(-1).options.method==='GET');}
  const count=calls.length;const navigation=nav.onclick();await tick();check(calls.length===count);check(run('caseResourceDraft()')===draft);check(run('[...caseResourceRetries.values()].includes("'+key+'")'));check($('page-feedback').textContent.includes('原入口'));
  if(phase==='pending'){post.reject(Error('SYNTHETIC_LOST_RESPONSE'));await command;}
  if(phase==='verify'){calls.at(-1).reject(Error('SYNTHETIC_LOST_READBACK'));await command;}
  check(calls.filter(c=>c.options.method==='POST').length===1);
 }else if(mode==='dispatch_ref'){
  run("dispatchPending={preparationId:'"+id(3)+"',key:'"+id(99)+"',body:{reason:'SYNTHETIC_PRIVATE_REASON'},token:'SYNTHETIC_SESSION_A'}");const p=run("apiCall('/api/runs/x').catch(pageError)");finish(calls.at(-1),403,{});await p;
  check(run("deniedOperationReferences.get('DISPATCH:"+id(99)+"').id")===id(3));check(!run('JSON.stringify([...deniedOperationReferences.values()])').includes('SYNTHETIC_PRIVATE_REASON'));check(run('dispatchPending===null'));
 }
 console.log(JSON.stringify({mode,checks,scope:'ACTUAL_ORIGINAL_COMMANDS_NO_ENTRY_MOCKS_SYNTHETIC_HTTP'}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
