// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync(process.argv[3]||'src/parkweave/web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0,nextNonce=1200;
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
 const catalog=$('prep-catalog').onclick();finish(calls.at(-1),200,{services:[],reviewers:[]});await catalog;check(run('prepRole')==='enterprise_operator');
 const load=run("loadPreparation('"+id(3)+"')"),initial=material();initial.current_materials=[];finish(calls.at(-1),200,initial);await flushOtherGets();await load;check(run('preparationContext.id')===id(3));
 $('prep-slot').value='need_summary';$('prep-text').value='SYNTHETIC ORIGINAL BODY';$('prep-source-kind').value='DOCUMENT_EXCERPT';$('prep-source-label').value='SYNTHETIC ORIGINAL SOURCE';
 const submit=$('prep-evidence').onsubmit({preventDefault(){}}),post=calls.at(-1);check(post.options.method==='POST');check(JSON.parse(post.options.body).action==='ADD_EVIDENCE');const key=post.options.headers['Idempotency-Key'];post.reject(Error('SYNTHETIC LOST POST RESPONSE'));await submit;
 check(run('prepCommandPending.state')==='UNKNOWN');check(run('prepRecoveryHandle.key')===key);check(!run('prepRecoveryHandle.observed'));const storageBefore=store['parkweave.evidence-recovery.v1.'+id(3)];check(!!storageBefore);
 const pending=run('prepCommandPending'),before=calls.length,recovery=$('prep-recovery-read').onclick();if(calls.length!==before+1)console.error(JSON.stringify({diagnostic:'RECOVERY_NO_FETCH',leases:run('[...entryWriteRequests.values()].map(op=>({kind:op.kind,path:op.path}))'),error:$('page-feedback').textContent,prepError:$('prep-error').textContent,role:run('prepRole')}));check(calls.length===before+1);check(calls.at(-1).path.endsWith('/command-recovery'));check(calls.at(-1).options.headers['Idempotency-Key']===key);check(calls.at(-1).options.method==='GET');
 if(mode==='denied403'){finish(calls.at(-1),403,{detail:'SYNTHETIC REVOKED'});await recovery;check(run('preparationView===null'));check(run('prepCommandPending===null'));check(store['parkweave.evidence-recovery.v1.'+id(3)]===storageBefore);}
 else{
  const event={action:mode==='wrong_action'?'REVIEW':'ADD_EVIDENCE',revision:mode==='wrong_revision'?3:2,actor_id:'fixture-a',preparation_id:id(3),case_id:id(1),evidence_id:id(44),text:'SYNTHETIC ORIGINAL BODY'};
  const found={preparation_id:mode==='wrong_preparation'?id(8):id(3),status:mode==='not_observed'?'NOT_OBSERVED':'COMMITTED',event:mode==='not_observed'?null:event,current_revision:mode==='not_observed'?1:event.revision,historical_only:mode!=='not_historical',automatically_replayed:mode==='automatic_replay'};
  finish(calls.at(-1),200,found);await tick();
  if(!['wrong_preparation','not_historical','automatic_replay'].includes(mode)){
   check(calls.at(-1).path==='/api/preparations/'+id(3));const snapshot=material();snapshot.preparation.revision=found.current_revision;snapshot.history=found.event?[{action:event.action,revision:event.revision,payload:mode==='missing_exact_history'?{...event,text:'SYNTHETIC DIFFERENT BODY'}:event}]:[];finish(calls.at(-1),200,snapshot);
  }
  await recovery;check(run('prepCommandPending')===pending);check(run('prepCommandPending.state')==='UNKNOWN');check(!run('prepRecoveryHandle.observed'));check(store['parkweave.evidence-recovery.v1.'+id(3)]===storageBefore);check($('prep-recovery-release').hidden);check($('prep-text').value==='SYNTHETIC ORIGINAL BODY');
 }
 check(calls.filter(c=>c.options.method==='POST').length===1);console.log(JSON.stringify({mode,checks,result:'PASS',scope:'FULL_ORIGINAL_HTML_REAL_ADD_EVIDENCE_UNKNOWN_AND_RECOVERY_NEGATIVE_HTTPDOM_DOUBLES; initial secondary reads intentionally500; no business/pending mock'}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
