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
 if(mode==='receipt_form_pending_list'||mode==='receipt_form_unknown_list'){
  const view=receipt();view.role='service_executor';const load=run("loadReceipt('"+id(4)+"')");finish(calls.at(-1),200,view);await load;$('receipt-text').value='SYNTHETIC_ORIGINAL_SUBMIT';$('receipt-source').value='SYNTHETIC_DOC';
  const draft=run('receiptDraft()'),write=$('receipt-submit').onsubmit({preventDefault(){}}),post=calls.at(-1);check(post.options.method==='POST');check(JSON.parse(post.options.body).action==='SUBMIT');const key=post.options.headers['Idempotency-Key'];
  if(mode==='receipt_form_unknown_list'){post.reject(Error('SYNTHETIC_LOST_POST'));await write;}
  const before=calls.length;await Promise.resolve($('receipt-list').onclick()).catch(()=>{});await tick();check(calls.length===before);check(run('receiptId')===id(4));check(run('receiptDraft()')===draft);check(run('[...receiptRetries.values()].includes("'+key+'")'));
  if(mode==='receipt_form_pending_list'){post.reject(Error('SYNTHETIC_LOST_POST'));await write;}
  check(run('entryWriteRequests.size===1'));
  const refresh=$('receipt-refresh').onclick();finish(calls.at(-1),200,view);await refresh;check(run('receiptView.step.id')===id(4));check(run('entryWriteRequests.size===1'));check(calls.filter(c=>c.options.method==='POST').length===1);
 }else
 if(mode==='link_revision_mismatch'){
  run("preparationId='"+id(3)+"';preparationView={preparation:{id:'"+id(3)+"',revision:1,state:'LOCAL_CONFIRMED'}};preparationContext={...prepContext(),caseId:'"+id(1)+"',revision:1};prepRole='enterprise_operator'");
  const load=run('loadCaseResources()');finish(calls.at(-1),200,resourceView());await tick();finish(calls.at(-1),200,resourceCatalog());await load;$('case-resource-choice').value=id(11);$('case-resource-reason').value='SYNTHETIC_LINK';
  const button=await queue('run'),write=$('case-resource-form').onsubmit({preventDefault(){}}),post=calls.at(-1);check(post.options.method==='POST');const key=post.options.headers['Idempotency-Key'];finish(post,200,{link_revision:1});await tick();const view=resourceView();view.link_revision=1;finish(calls.at(-1),200,view);await tick();const changed=resourceCatalog();changed.preparation_revision=2;finish(calls.at(-1),200,changed);await write;
  check(run('caseResourceView===null'));check(run('entryWriteRequests.size===1'));check(run('[...caseResourceRetries.values()].includes("'+key+'")'));
  const before=calls.length;await button.onclick();check(calls.length===before);
  const refresh=$('case-resource-load').onclick();finish(calls.at(-1),200,view);await tick();finish(calls.at(-1),200,resourceCatalog());await refresh;check(run('entryWriteRequests.size===0'));
 }else if(mode==='ack_stale_revision'){
  const x=receipt();x.step.state='RECEIPT_RECORDED';x.current_receipt={version:1,text:'SYNTHETIC',source_sha256:'f'.repeat(64),source_kind:'SYNTHETIC',source_label:'SYNTHETIC',actor_id:'fixture-a'};const load=run("loadReceipt('"+id(4)+"')");finish(calls.at(-1),200,x);await load;$('receipt-reason').value='SYNTHETIC_ACK';
  const write=$('receipt-ack').onclick(),post=calls.at(-1);check(post.options.method==='POST');finish(post,200,{event:{revision:2}});await tick();finish(calls.at(-1),200,x);await write;check(run('receiptView.step.revision===1'));check(run('entryWriteRequests.size===1'));
  const refresh=$('receipt-refresh').onclick();x.step.revision=2;x.step.state='LOCAL_ACKNOWLEDGED';finish(calls.at(-1),200,x);await refresh;check(run('entryWriteRequests.size===0'));
 }else if(mode==='intent_wrong_binding'){
  const plan={preparation_id:id(3),run_id:id(2),preparation_revision:1,plan_id:id(32),revision:20,template_sha256:'f'.repeat(64),role:'enterprise_operator',state:'IN_PROGRESS',steps:[],history:[],request_intent:{original_request:'SYNTHETIC',current_request:'SYNTHETIC',required_goals:['LOCAL_SYNTHETIC_COORDINATION_RECORDS'],recorded:true,revision:1,coverage:{state:'CURRENT',items:[]}}};const load=run("loadPlan('"+id(3)+"')");finish(calls.at(-1),200,plan);await load;$('request-current').value='SYNTHETIC_NEW_REQUEST';
  const write=$('request-intent-form').onsubmit({preventDefault(){}});check(calls.at(-1).options.method==='POST');finish(calls.at(-1),200,{revision:2});await tick();finish(calls.at(-1),200,{...plan,preparation_id:id(76)});await write;check(run('entryWriteRequests.size===1'));
  const refresh=run("loadPlan('"+id(3)+"')");plan.request_intent.revision=2;plan.request_intent.current_request='SYNTHETIC_NEW_REQUEST';finish(calls.at(-1),200,plan);await refresh;check(run('entryWriteRequests.size===0'));
 }else if(mode==='readiness_wrong_revision'){
  run("preparationId='"+id(3)+"';preparationView={preparation:{id:'"+id(3)+"',revision:1,state:'IN_PREPARATION'}};preparationContext={...prepContext(),caseId:'"+id(1)+"',revision:1};prepRole='enterprise_operator'");
  const view={preparation_id:id(3),case_id:id(1),preparation_revision:1,source_sha256:'f'.repeat(64),material_checklist:{preparation_revision:1,source_sha256:'f'.repeat(64),source_available:false,requirements:[],conditions:[]},state:'NOT_ASSESSED',current_truth:'UNKNOWN',current_inputs:{conditions:[{id:'current_manual_material_review',truth:'UNKNOWN',reason:'SYNTHETIC'}],missing_slots:[],next_actions:[]},sources:{service:null,rule:{revision:1,sha256:'f'.repeat(64)},materials:[],manual_review:{decision:null,state:'IN_PREPARATION',current_authority:true}},history:[]};const load=run('loadReadiness(preparationContext)');finish(calls.at(-1),200,view);await load;check(run('readinessView!==null'));
  const write=$('readiness-assess').onclick(),post=calls.at(-1);check(post.options.method==='POST');const record={id:id(66),sequence:1,actor_id:'fixture-a',request_key:post.options.headers['Idempotency-Key'],fingerprint:'f'.repeat(64),created_at:'2026-10-13T00:00:00+00:00',source_sha256:view.source_sha256,preparation_revision:1,sources:view.sources,result:{...view.current_inputs,local_preparation_truth:'UNKNOWN'}};finish(post,200,record);await tick();finish(calls.at(-1),200,{...view,preparation_revision:2,history:[record]});await write;check(run('readinessView===null'));check(run('entryWriteRequests.size===1'));
  const refresh=run('loadReadiness(preparationContext)');finish(calls.at(-1),200,{...view,state:'CURRENT',history:[record]});await refresh;check(run('entryWriteRequests.size===0'));
 }
 console.log(JSON.stringify({mode,checks,scope:'ACTUAL_ORIGINAL_COMMANDS_SEMANTIC_READBACK_AND_RECOVERY_NO_ENTRY_MOCKS'}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
