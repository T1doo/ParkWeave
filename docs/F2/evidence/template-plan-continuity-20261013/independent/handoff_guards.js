// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync(process.argv[3]||'src/parkweave/web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0,nextNonce=1300;
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
const context=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,TextEncoder,URLSearchParams,location:{search:"?template_instance="+id(70)},
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


function plan(p=id(3),c=id(1),r=id(2)){return {preparation_id:p,case_id:c,run_id:r,plan_id:id(9),actor_ref:'a'.repeat(64),role:'enterprise_operator',state:'ACTIVE',revision:1,preparation_revision:1,request_revision:1,steps:[],history:[],required_goals:['LOCAL_MATERIAL_PREPARATION'],can_adopt:false,read_only:false};}
function instance(){return {instance_id:id(70),state:'PLAN_ADOPTED',run_id:id(2),case_id:id(1),preparation_id:id(3),plan_id:id(9),new_grants:false,automatic_execution:false,case_goal_completed:false,release_available:true,preparation:{preparation:{id:id(3),case_id:id(1),run_id:id(2)}},service_case_plan:plan()};}
async function originalPlan(){const x=plan(),load=run("loadServiceCasePlan('"+id(3)+"')");finish(calls.at(-1),200,{status:'NO_REQUEST',read_only:true,automatically_replayed:false,actor_ref:x.actor_ref,case_id:x.case_id,run_id:x.run_id,current:x});await tick();finish(calls.at(-1),200,x);await load;return x;}
(async()=>{
 check(calls.length===0);check($('template-instance-id').value===id(70));
 if(mode==='pending_preserved'){
  const x=plan();x.can_adopt=true;x.current_preview={source_sha256:'f'.repeat(64),required_goals:x.required_goals};const load=run("loadServiceCasePlan('"+id(3)+"')");finish(calls.at(-1),200,{status:'NO_REQUEST',read_only:true,automatically_replayed:false,actor_ref:x.actor_ref,case_id:x.case_id,run_id:x.run_id,current:x});await tick();finish(calls.at(-1),200,x);await load;
  $('service-plan-reason').value='SYNTHETIC explicit adopt';const write=$('service-plan-adopt').onclick(),post=calls.at(-1);check(post.options.method==='POST');post.reject(Error('SYNTHETIC LOST PLAN POST'));await write;check(run('servicePlanPending.stage')==='UNCERTAIN');const pending=run('servicePlanPending'),handle=run('servicePlanRecoveryHandle'),before=calls.length;
  await $('template-instance-read').onclick();check(calls.length===before);check(run('servicePlanPending')===pending);check(run('servicePlanRecoveryHandle')===handle);check($('service-plan-reason').value==='SYNTHETIC explicit adopt');
 }else if(mode==='late_catalog'){
  const handoff=$('template-instance-read').onclick(),old=calls.at(-1);check(old.path.endsWith('/'+id(70)));const catalog=$('prep-catalog').onclick();finish(calls.at(-1),200,{services:[],reviewers:[]});await catalog;const before=calls.length;finish(old,200,instance());await tick();check(calls.length===before);await handoff;check(run('servicePlanView===null'));check(run('prepCatalog!==null'));
 }else if(mode==='late_error_new_plan'){
  const handoff=$('template-instance-read').onclick(),old=calls.at(-1);await originalPlan();check(run('servicePlanView.plan_id')===id(9));finish(old,500,{detail:'SYNTHETIC OLD ERROR'});await handoff;check(run('servicePlanView?.plan_id')===id(9));
 }else if(mode==='identity_aba'){
  const handoff=$('template-instance-read').onclick(),old=calls.at(-1);const event=events.find(a=>a[0]==='input');$('token').value='SYNTHETIC_SESSION_B';$('token').oninput();for(const a of events.filter(a=>a[0]==='input'))a[1]();$('token').value='SYNTHETIC_SESSION_A';$('token').oninput();for(const a of events.filter(a=>a[0]==='input'))a[1]();const before=calls.length;finish(old,200,instance());await handoff;check(calls.length===before);check(run('servicePlanView===null'));
 }else if(mode==='terminal_wrong_plan'){
  const handoff=$('template-instance-read').onclick();finish(calls.at(-1),200,instance());await tick();check(calls.at(-1).path.endsWith('/command-recovery'));const x=plan();x.plan_id=id(19);finish(calls.at(-1),200,{status:'NO_REQUEST',read_only:true,automatically_replayed:false,actor_ref:x.actor_ref,case_id:x.case_id,run_id:x.run_id,current:x});await tick();finish(calls.at(-1),200,x);await handoff;check(run('servicePlanView===null'));check($('result').textContent==='');check($('template-instance-status').textContent.includes('变化'));
 }else if(mode==='late403_new_plan'){
  const handoff=$('template-instance-read').onclick(),old=calls.at(-1);await originalPlan();check(run('servicePlanView.plan_id')===id(9));finish(old,403,{detail:'SYNTHETIC OLD DENIAL'});await handoff;check(run('servicePlanView?.plan_id')===id(9));check($('template-instance-status').textContent!=='当前身份无此实例访问权，私有计划已清除。');
 }else if(mode==='denied403'){
  const handoff=$('template-instance-read').onclick();finish(calls.at(-1),403,{detail:'SYNTHETIC NOT OWNER'});await handoff;check(run('servicePlanView===null'));check(!$('result').textContent.includes('SYNTHETIC NOT OWNER'));check($('template-instance-status').textContent.includes('无此实例'));
 }else if(mode==='wrong_binding'){
  const handoff=$('template-instance-read').onclick();const bad=instance();bad.case_id=id(8);finish(calls.at(-1),200,bad);await handoff;check(run('servicePlanView===null'));check($('result').textContent==='');check($('template-instance-status').textContent.includes('绑定'));
 }else throw Error('unknown mode');
 console.log(JSON.stringify({mode,checks,result:'PASS',scope:'FULL_ORIGINAL_HTML_REAL_HANDLERS_HTTPDOM_NO_PENDING_OR_ENTRY_MOCK'}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
