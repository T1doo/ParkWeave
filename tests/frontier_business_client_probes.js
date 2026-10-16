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

const fence={generation:id(90),preparation_id:id(3),plan_id:id(80),plan_revision:3,epoch:2};
function assertPostFence(){const post=calls.at(-1);check(post.options.method==='POST');const body=JSON.parse(post.options.body);check(JSON.stringify(body.expected_business_frontier)===JSON.stringify(fence));check(calls.filter(c=>(c.options.method||'GET')==='POST').length===1);return post;}
(async()=>{
 if(mode==='capture_shape'){
  context.fixture=fence;const captured=run('captureBusinessFrontier(fixture,fixture.preparation_id)');check(Object.isFrozen(captured));check(JSON.stringify(captured)===JSON.stringify(fence));context.fixture.epoch=9;check(captured.epoch===2);
  const mutations=[x=>x.extra='unknown',x=>delete x.epoch,x=>x.epoch=-1,x=>x.epoch=4097,x=>x.epoch=true,x=>x.plan_revision=0,x=>x.plan_revision=65,x=>x.plan_revision='3',x=>x.plan_id=null,x=>x.generation='UNKNOWN',x=>x.preparation_id=id(99)];
  for(const mutate of mutations){context.fixture=structuredClone(fence);mutate(context.fixture);assert.throws(()=>run(`captureBusinessFrontier(fixture,'${id(3)}')`));checks++;}
  assert.throws(()=>run(`captureBusinessFrontier(null,'${id(3)}')`));checks++;check(run(`captureBusinessFrontier(undefined,'${id(3)}')`)===undefined);check(run('sameBusinessFrontier(undefined,undefined)'));check(!run('sameBusinessFrontier(undefined,{})'));
 }else if(['dispatch_offer','dispatch_accept','dispatch_reassign'].includes(mode)){
  const reassign=mode==='dispatch_reassign',accept=mode==='dispatch_accept';
  const x={scope:'SYNTHETIC_INTERNAL_DISPATCH_ONLY',role:accept?'service_executor':'park_specialist',preparation_id:id(3),case_id:id(1),run_id:id(2),dispatch_id:id(10),preparation_revision:4,revision:2,goal:'SYNTHETIC business',current_offer:{id:id(11),executor_id:'executor-a',state:accept?'OFFERED':'ACCEPTED',reason:'SYNTHETIC old'},dependency:'CURRENT',is_current_offer:true,current_receipt_step_id:id(12),history:[],business_frontier:structuredClone(fence)};
  const catalog={preparation_revision:4,dispatch_revision:2,ready:true,executors:[{id:'executor-a'},{id:'executor-new'}],business_frontier:structuredClone(fence),can_reassign:reassign,reassignment_actor_id:'reviewer-a',reassignment_executors:[{id:'executor-new'}],reassignment_predecessor:{predecessor_offer_id:id(11),predecessor_receipt_step_id:id(12),predecessor_receipt_revision:1}};
  const loading=run(`loadDispatch('${id(3)}')`);finish(calls.at(-1),200,x);await tick();if(!accept){finish(calls.at(-1),200,catalog);}await loading;check(run('Object.isFrozen(dispatchContext.businessFrontier)'));
  run('dispatchView.business_frontier.epoch=9');$('dispatch-executor').value='executor-new';$('dispatch-offer-reason').value='SYNTHETIC explicit current offer';$('dispatch-decision-reason').value='SYNTHETIC explicit accept';run(`dispatchWrite('${accept?'ACCEPT':'OFFER'}')`);const post=assertPostFence();check(post.path.endsWith(reassign?'/reassign':accept?'/commands':'/dispatch'));check(calls.filter(c=>(c.options.method||'GET')==='GET').length===(accept?1:2));
  if(reassign){const h=JSON.parse(store['parkweave.pending-receipt-handoff.v1'])[0];check(!Object.hasOwn(h,'expected_business_frontier'));check(Object.keys(h).sort().join(',')==='actor,dispatch,expires,key,preparation');}
 }else if(mode==='receipt_create'){
  run(`preparationId='${id(3)}';preparationView={preparation:{id:'${id(3)}',state:'LOCAL_CONFIRMED',revision:4}};preparationContext=prepContext()`);
  const loading=$('receipt-prepare').onclick();finish(calls.at(-1),200,{ready:true,executors:[{id:'executor-a'}],business_frontier:structuredClone(fence)});await loading;check(run('Object.isFrozen(receiptCreateContext.businessFrontier)'));$('receipt-executor').value='executor-a';run(`preparationView.business_frontier={...receiptCreateContext.businessFrontier,epoch:9}`);$('receipt-create').onsubmit({preventDefault(){}});const post=assertPostFence();check(post.path==='/api/executor-receipts');check(calls.filter(c=>(c.options.method||'GET')==='GET').length===1);
 }else if(['receipt_submit','receipt_ack','receipt_local','ordinary_receipt'].includes(mode)){
  const x=receipt(),ordinary=mode==='ordinary_receipt';x.step.preparation_id=id(3);x.role=mode==='receipt_ack'?'enterprise_operator':'service_executor';x.business_frontier=structuredClone(fence);if(ordinary)delete x.business_frontier;if(mode==='receipt_ack'){x.step.state='RECEIPT_RECORDED';x.current_receipt={source_sha256:'a'.repeat(64),version:1,text:'SYNTHETIC',source_kind:'SYNTHETIC',source_label:'SYNTHETIC',actor_id:'executor-a',created_at:'SYNTHETIC'};}if(mode==='receipt_local')x.local_execution={enabled:true,can_execute:true};
  const loading=run(`loadReceipt('${id(4)}')`);finish(calls.at(-1),200,x);await loading;
  if(!ordinary){check(run('Object.isFrozen(receiptContext.businessFrontier)'));run('receiptView.business_frontier.epoch=9');}
  $('receipt-text').value='SYNTHETIC new manual report';$('receipt-source').value='SYNTHETIC source';$('receipt-reason').value='SYNTHETIC explicit decision';$('receipt-local-execution-reason').value='SYNTHETIC explicit local report';run(mode==='receipt_local'?"receiptLocalExecute(false)":`receiptCommand('${mode==='receipt_ack'?'ACKNOWLEDGE':'SUBMIT'}')`);
  if(ordinary){const post=calls.at(-1);check(post.options.method==='POST');check(!Object.hasOwn(JSON.parse(post.options.body),'expected_business_frontier'));check(!Object.hasOwn(run('receiptContext'),'businessFrontier'));}else assertPostFence();check(calls.filter(c=>(c.options.method||'GET')==='GET').length===1);
 }else if(mode==='lifecycle'){
  const x={scope:'SYNTHETIC_LOCAL_CASE_RECORD_ONLY',actor_id:'fixture-a',role:'enterprise_operator',preparation_id:id(3),case_id:id(1),run_id:id(2),preparation_revision:4,revision:0,cycle:1,current_snapshot_sha256:'a'.repeat(64),goal:'SYNTHETIC case',local_record_state:'PENDING',case_state:'NEEDS_INPUT',can_revalidate:true,can_close_local_record:false,can_reopen:false,history:[],checks:{},business_frontier:structuredClone(fence)};
  const loading=run(`loadLocalCase('${id(3)}')`);finish(calls.at(-1),200,x);await loading;check(run('Object.isFrozen(localCaseContext.businessFrontier)'));run('localCaseView.business_frontier.epoch=9');$('local-case-reason').value='SYNTHETIC explicit local recheck';run("localCaseCommand('REVALIDATE')");const post=assertPostFence();check(post.path.endsWith('/local-case/commands'));check(calls.filter(c=>(c.options.method||'GET')==='GET').length===1);const h=JSON.parse(Object.entries(store).find(([k])=>k.startsWith('parkweave.local-case-recovery.v1.'))[1]);check(Object.keys(h).sort().join(',')==='actor,id,key');
 }else throw Error('unknown mode');
 console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_CONTROLLED_GET_AND_FETCH_DOUBLES_ONLY',mode,checks,actual_http:false,real_browser:'NOT_RUN',automatic_fresh_get:false}));process.exit(0);
})().catch(error=>{console.error(JSON.stringify({message:error.message,stack:error.stack,calls:calls.map(c=>({path:c.path,options:c.options}))}));process.exit(1);});
