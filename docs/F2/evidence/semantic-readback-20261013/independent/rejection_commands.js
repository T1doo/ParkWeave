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
let nextNonce=900;
const context=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,
 crypto:{randomUUID:()=>id(nextNonce++)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},
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
 if(mode==='closed_contract'){
  const path='/api/executor-receipts/'+id(4)+'/commands',allowed=['stale receipt step revision; refresh required','current receipt hash required','receipt step not awaiting executor','recorded receipt required for local acknowledgement','recorded receipt required for correction','recorded receipt required for reopen'];
  for(const detail of allowed)check(run('receiptCommandExplicitlyRejected('+JSON.stringify(path)+',409,'+JSON.stringify({detail})+')')===true);
  for(const detail of allowed){check(run('receiptCommandExplicitlyRejected('+JSON.stringify(path)+',500,'+JSON.stringify({detail})+')')===false);check(run('receiptCommandExplicitlyRejected('+JSON.stringify(path.replace('/commands','/execute-local'))+',409,'+JSON.stringify({detail})+')')===false);}
  check(run('receiptCommandExplicitlyRejected('+JSON.stringify(path)+',409,{detail:"'+allowed[0]+' "})')===false);
  check(run('receiptCommandExplicitlyRejected('+JSON.stringify(path)+',422,{detail:[{loc:["path","step_id"],msg:"bad",type:"uuid_parsing"}]})')===false);
  check(run('receiptCommandExplicitlyRejected('+JSON.stringify(path)+',422,{detail:"validation"})')===false);
 }else{
  const view=receipt();view.step.state='RECEIPT_RECORDED';view.current_receipt={version:1,text:'SYNTHETIC',source_sha256:'f'.repeat(64),source_kind:'SYNTHETIC',source_label:'SYNTHETIC',actor_id:'fixture-a'};const initial=run("loadReceipt('"+id(4)+"')");finish(calls.at(-1),200,view);await initial;$('receipt-reason').value=mode==='reject422_correct'?'':'SYNTHETIC_ACK';
  const first=$('receipt-ack').onclick(),post=calls.at(-1),firstKey=post.options.headers['Idempotency-Key'];check(post.options.method==='POST');
  if(mode==='independent_read_refusal'){
   const count=calls.length;await Promise.resolve($('receipt-history-read').onclick()).catch(()=>{});check(calls.length===count);check(run('activeEntryWriteFlow.failed===false'));
   finish(post,200,{event:{revision:2}});await tick();view.step.revision=2;view.step.state='LOCAL_ACKNOWLEDGED';finish(calls.at(-1),200,view);await first;check(run('entryWriteRequests.size===0'));
  }else if(mode==='reject409_refresh'||mode==='reject422_correct'){
   const status=mode==='reject409_refresh'?409:422,value=status===409?{detail:'stale receipt step revision; refresh required'}:{detail:[{type:'string_too_short',loc:['body','reason'],msg:'String should have at least 1 character',input:'',ctx:{min_length:1}}]};finish(post,status,value);await first;check(run('entryWriteRequests.size===0'));check(run('[...deniedOperationReferences.values()].some(x=>x.key==="'+firstKey+'")'));check(calls.filter(c=>c.options.method==='POST').length===1);
   if(status===409){view.step.revision=2;const refresh=$('receipt-refresh').onclick();finish(calls.at(-1),200,view);await refresh;}
   check(calls.filter(c=>c.options.method==='POST').length===1);$('receipt-reason').value='SYNTHETIC_EXPLICIT_CORRECTED_ACK';
   const second=$('receipt-ack').onclick(),next=calls.at(-1);check(next.options.method==='POST');check(next.options.headers['Idempotency-Key']!==firstKey);check(JSON.parse(next.options.body).expected_revision===view.step.revision);
   view.step.revision++;view.step.state='LOCAL_ACKNOWLEDGED';finish(next,200,{event:{revision:view.step.revision}});await tick();finish(calls.at(-1),200,view);await second;check(run('entryWriteRequests.size===0'));check(calls.filter(c=>c.options.method==='POST').length===2);
  }else if(['case_guard409','unknown500','unmatched422'].includes(mode)){
   const status=mode==='case_guard409'?409:mode==='unknown500'?500:422,value=mode==='case_guard409'?{detail:'cancelled Case is historical; mutations not allowed'}:mode==='unknown500'?{detail:'stale receipt step revision; refresh required'}:{detail:'body validation uncertain'};finish(post,status,value);await first;check(run('entryWriteRequests.size===1'));
   const refresh=$('receipt-refresh').onclick();view.step.revision=2;view.step.state='LOCAL_ACKNOWLEDGED';finish(calls.at(-1),200,view);await refresh;check(run('entryWriteRequests.size===1'));check(calls.filter(c=>c.options.method==='POST').length===1);check(run('[...receiptRetries.values()].includes("'+firstKey+'")'));
  }
 }
 console.log(JSON.stringify({mode,checks,scope:'ACTUAL_ORDINARY_RECEIPT_REJECTION_AND_EXPLICIT_CORRECTION_NO_ENTRY_MOCKS'}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
