// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync(process.argv[3]||'src/parkweave/web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.id='';this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.options=[];this.listeners={};}
 append(...x){for(const e of x)if(e&&typeof e==='object')e.parentElement=this;this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 reset(){}addEventListener(n,f){this.listeners[n]=f;}setAttribute(){}removeAttribute(){}
 closest(selector){let e=this;while(e){for(const part of selector.split(',')){const t=part.trim();if((t.startsWith('#')&&e.id===t.slice(1))||['button','form','a'].includes(t)&&e.tagName.toLowerCase()===t)return e;}e=e.parentElement;}return null;}querySelectorAll(){return [];}scrollIntoView(){this.scrolled=true;}
 get firstElementChild(){return this.children[0];}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
const elements=new Map(),$=name=>{if(!elements.has(name))elements.set(name,new Element());elements.get(name).id=name;return elements.get(name);};
const store={},calls=[],events=[];
const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},
 {ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
const context=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,
 crypto:{randomUUID:()=>id(99)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},
 Element,document:{getElementById:$,createElement:t=>new Element(t),querySelectorAll:()=>[],body:new Element('body'),addEventListener:(...a)=>events.push(a),execCommand:()=>false},
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
 if(mode==='dynamic_notice_capture'){
  const x=receipt();x.step.state='RECEIPT_RECORDED';x.current_receipt={version:1,text:'SYNTHETIC',source_sha256:'f'.repeat(64),source_kind:'SYNTHETIC',source_label:'SYNTHETIC',actor_id:'fixture-a'};
  const read=run("loadReceipt('"+id(4)+"')");finish(calls.at(-1),200,x);await read;
  const notices=run('loadNoticeList()');finish(calls.at(-1),200,{scope:'SYNTHETIC_INTERNAL_DISPATCH_NOTICES_ONLY',items:[{event_id:id(71),action:'OFFER',revision:1,historical:false,read_at:null}],check_limit:100,page_limit:20,next_cursor:null});await notices;
  const card=$('notice-items').children[0],button=card.children.find(e=>e.tagName==='button');check(!!button);check(button.parentElement===card);
  // Boundary fixture: original snapshot was read by real loadReceipt; restore
  // it through actual render after notice's mutually exclusive loader clearing.
  run("receiptId='"+id(4)+"';renderReceipt("+JSON.stringify(x)+")");$('receipt-reason').value='SYNTHETIC_ACK';const command=$('receipt-ack').onclick(),post=calls.at(-1);check(post.options.method==='POST');
  const count=calls.length,e={target:button,type:'click',prevented:false,stopped:false,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;}};
  for(const [type,handler,options] of events){if(type==='click'&&(options===true||options?.capture)){handler(e);if(e.stopped)break;}}
  if(!e.prevented)button.onclick();await tick();check(e.prevented);check(calls.length===count);
  finish(post,200,{event:{revision:2}});await tick();x.step.revision=2;x.step.state='LOCAL_ACKNOWLEDGED';finish(calls.at(-1),200,x);await command;check(run('entryWriteRequests.size===0&&activeEntryWriteFlow===null'));
 }else
 if(mode==='readiness_not_prep_proof'){
  run("preparationId='"+id(3)+"';preparationView={preparation:{id:'"+id(3)+"',revision:1,state:'IN_PREPARATION'}};preparationContext={...prepContext(),caseId:'"+id(1)+"',revision:1};prepRole='enterprise_operator'");
  const view={preparation_id:id(3),case_id:id(1),preparation_revision:1,source_sha256:'f'.repeat(64),material_checklist:{preparation_revision:1,source_sha256:'f'.repeat(64),source_available:false,requirements:[],conditions:[]},state:'NOT_ASSESSED',current_truth:'UNKNOWN',current_inputs:{conditions:[{id:'current_manual_material_review',truth:'UNKNOWN',reason:'SYNTHETIC'}],missing_slots:[],next_actions:[]},sources:{service:null,rule:{revision:1,sha256:'f'.repeat(64)},materials:[],manual_review:{decision:null,state:'IN_PREPARATION',current_authority:true}},history:[]};
  const load=run('loadReadiness(preparationContext)');finish(calls.at(-1),200,view);await load;if(run('readinessView===null'))console.error('HARNESS_SETUP_ERROR:'+ $('readiness-error').textContent);check(run('readinessView!==null'));
  const write=$('readiness-assess').onclick();check(calls.at(-1).options.method==='POST');const record={id:id(66),sequence:1,actor_id:'fixture-a',request_key:calls.at(-1).options.headers['Idempotency-Key'],fingerprint:'f'.repeat(64),created_at:'2026-10-13T00:00:00+00:00',source_sha256:view.source_sha256,preparation_revision:1,sources:view.sources,result:{...view.current_inputs,local_preparation_truth:'UNKNOWN'}};finish(calls.at(-1),200,record);await tick();finish(calls.at(-1),500,{});await write;check(run('entryWriteRequests.size===1'));
  const reload=run("loadPreparation('"+id(3)+"',{role:'enterprise_operator'})");finish(calls.at(-1),200,material());calls.at(-1).finished=true;await flushOtherGets();await reload;
  check(run('readinessView===null'));check(run('entryWriteRequests.size===1'));
  const old=run('loadReadiness(preparationContext)');finish(calls.at(-1),200,view);await old;check(run('readinessView!==null'));check(run('entryWriteRequests.size===1'));
  const forged=run('loadReadiness(preparationContext)');finish(calls.at(-1),200,{...view,state:'CURRENT',history:[{...record,fingerprint:'0'.repeat(64)}]});await forged;check(run('entryWriteRequests.size===1'));
  const exact=run('loadReadiness(preparationContext)');finish(calls.at(-1),200,{...view,state:'CURRENT',history:[record]});await exact;check(run('entryWriteRequests.size===0'));

 }else
 if(mode==='dispatch_failed_readback_refresh'){
  const view={dispatch_id:id(20),preparation_id:id(3),preparation_revision:1,revision:1,goal:'SYNTHETIC',role:'service_executor',dependency:'CURRENT',current_offer:{id:id(21),state:'OFFERED',executor_id:'executor-a',reason:'SYNTHETIC'},is_current_offer:true,current_receipt_step_id:null,history:[]};
  const load=run("loadDispatch('"+id(3)+"')");finish(calls.at(-1),200,view);await load;$('dispatch-decision-reason').value='SYNTHETIC_DECLINE';
  const first=$('dispatch-decline').onclick();finish(calls.at(-1),200,{dispatch_id:id(20),event:{revision:2}});await tick();calls.at(-1).reject(Error('SYNTHETIC_LOST_READBACK'));await first;check(run('dispatchPending===null'));check(run('entryWriteRequests.size===1'));
  const refresh=run("loadDispatch('"+id(3)+"')");view.revision=2;view.current_offer.state='DECLINED';finish(calls.at(-1),200,view);await refresh;check(run('dispatchView.revision===2'));check(run('entryWriteRequests.size===0'));
 }else if(mode==='link_failed_readback_refresh'){
  run("preparationId='"+id(3)+"';preparationView={preparation:{id:'"+id(3)+"',revision:1,state:'LOCAL_CONFIRMED'}};preparationContext={...prepContext(),caseId:'"+id(1)+"',revision:1};prepRole='enterprise_operator'");
  const load=run('loadCaseResources()');finish(calls.at(-1),200,resourceView());await tick();finish(calls.at(-1),200,resourceCatalog());await load;$('case-resource-choice').value=id(11);$('case-resource-reason').value='SYNTHETIC_LINK';
  const first=$('case-resource-form').onsubmit({preventDefault(){}});finish(calls.at(-1),200,{link_revision:1});await tick();calls.at(-1).reject(Error('SYNTHETIC_LOST_READBACK'));await first;check(run('entryWriteRequests.size===1'));
  const refresh=$('case-resource-load').onclick(),view=resourceView();view.link_revision=1;finish(calls.at(-1),200,view);await tick();finish(calls.at(-1),200,resourceCatalog());await refresh;check(run('caseResourceView.link_revision===1'));check(run('entryWriteRequests.size===0'));
 }else if(mode==='unknown_ack_get'){
  const x=receipt();x.step.state='RECEIPT_RECORDED';x.current_receipt={version:1,text:'SYNTHETIC',source_sha256:'f'.repeat(64),source_kind:'SYNTHETIC',source_label:'SYNTHETIC',actor_id:'fixture-a'};
  const load=run("loadReceipt('"+id(4)+"')");finish(calls.at(-1),200,x);await load;$('receipt-reason').value='SYNTHETIC_ACK';
  const first=$('receipt-ack').onclick();calls.at(-1).reject(Error('SYNTHETIC_LOST_POST'));await first;check(run('entryWriteRequests.size===1'));
  const refresh=$('receipt-refresh').onclick();x.step.revision=2;x.step.state='LOCAL_ACKNOWLEDGED';finish(calls.at(-1),200,x);await refresh;check(run('receiptView.step.revision===2'));check(run('entryWriteRequests.size===1'));check(calls.filter(c=>c.options.method==='POST').length===1);
 }else
 if(mode==='cross_plan_row_proof'){
  const plan={preparation_id:id(3),run_id:id(2),preparation_revision:1,plan_id:id(32),revision:20,template_sha256:'f'.repeat(64),role:'enterprise_operator',state:'IN_PROGRESS',steps:[],history:[],request_intent:{original_request:'SYNTHETIC',current_request:'SYNTHETIC',required_goals:['LOCAL_SYNTHETIC_COORDINATION_RECORDS'],recorded:true,revision:1,coverage:{state:'CURRENT',items:[]}}};
  const load=run("loadPlan('"+id(3)+"')");finish(calls.at(-1),200,plan);await load;$('request-current').value='SYNTHETIC_NEW_REQUEST';
  const write=$('request-intent-form').onsubmit({preventDefault(){}});check(calls.at(-1).options.method==='POST');check(calls.at(-1).path.endsWith('/request-intent'));finish(calls.at(-1),200,{revision:2});await tick();calls.at(-1).reject(Error('SYNTHETIC_LOST_PLAN_READBACK'));await write;check(run('entryWriteRequests.size===1'));
  // Same preparation UUID, stale request-intent row (v1), unrelated plan v20.
  const refresh=run("loadPlan('"+id(3)+"')");finish(calls.at(-1),200,plan);await refresh;check(run('planView.request_intent.revision===1'));check(run('entryWriteRequests.size===1'));const matched=run("loadPlan('"+id(3)+"')");plan.request_intent.revision=2;plan.request_intent.current_request='SYNTHETIC_NEW_REQUEST';finish(calls.at(-1),200,plan);await matched;check(run('entryWriteRequests.size===0'));
 }else
 if(mode==='ack_failed_readback_refresh'){
  const x=receipt();x.step.state='RECEIPT_RECORDED';x.current_receipt={version:1,text:'SYNTHETIC',source_sha256:'f'.repeat(64),source_kind:'SYNTHETIC',source_label:'SYNTHETIC',actor_id:'fixture-a'};
  const load=run("loadReceipt('"+id(4)+"')");finish(calls.at(-1),200,x);await load;$('receipt-reason').value='SYNTHETIC_ACK';
  const command=$('receipt-ack').onclick();finish(calls.at(-1),200,{event:{revision:2}});await tick();calls.at(-1).reject(Error('SYNTHETIC_LOST_READBACK'));await command;
  check(run('entryWriteRequests.size===1'));x.step.state='LOCAL_ACKNOWLEDGED';x.step.revision=2;
  const refresh=$('receipt-refresh').onclick();finish(calls.at(-1),200,x);await refresh;
  check($('receipt-summary').textContent.includes('企业本地核对')||run('receiptView.step.revision===2'));
  check(run('entryWriteRequests.size===0'));
 }else
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
  $('receipt-history-preparation').value=id(3);$('receipt-history-key').value=id(90);const before=calls.length;await Promise.resolve($('receipt-history-read').onclick()).catch(()=>{});check(calls.length===before);check($('page-feedback').textContent.includes('原'));
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
