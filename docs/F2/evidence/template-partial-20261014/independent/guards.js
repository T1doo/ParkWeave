// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync(process.argv[3]||'src/parkweave/template_candidate_web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.id='';this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.options=[];this.listeners={};this.style={};}
 append(...x){for(const e of x)if(e&&typeof e==='object')e.parentElement=this;this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 reset(){}addEventListener(n,f){this.listeners[n]=f;}setAttribute(){}removeAttribute(name){delete this[name];}
 closest(selector){let e=this;while(e){for(const part of selector.split(',')){const t=part.trim();if((t.startsWith('#')&&e.id===t.slice(1))||['button','form','a'].includes(t)&&e.tagName.toLowerCase()===t)return e;}e=e.parentElement;}return null;}querySelectorAll(){return [];}scrollIntoView(){this.scrolled=true;}
 get firstElementChild(){return this.children[0];}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
const elements=new Map(),$=name=>{if(!elements.has(name))elements.set(name,new Element());elements.get(name).id=name;return elements.get(name);};
const store={},calls=[],events=[];
const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},
 {ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
const context=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,
 crypto:{randomUUID:()=>id(99)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},
 structuredClone,Element,document:{getElementById:$,createElement:t=>new Element(t),querySelectorAll:selector=>{const all=[];function visit(e){if(e.dataset?.consumerGoal&&(!selector.includes(':checked')||e.checked))all.push(e);for(const c of e.children||[])visit(c);}for(const e of elements.values())visit(e);return selector.includes('data-consumer-goal')?all:[];},body:new Element('body'),addEventListener:(...a)=>events.push(a),execCommand:()=>false},
 window:{addEventListener:(...a)=>events.push(a)},
 fetch:(path,options)=>new Promise((resolve,reject)=>calls.push({path,options,resolve,reject}))});
vm.runInContext(code,context);$('token').value='SYNTHETIC_SESSION_A';
const run=s=>vm.runInContext(s,context),tick=()=>new Promise(r=>setImmediate(r));
function finish(call,status,value){call.resolve({status,ok:status>=200&&status<300,json:async()=>value});}
Object.defineProperty(Element.prototype,'selectedOptions',{get(){return this.children.filter(x=>x.tagName==='option'&&x.value===this.value);}});
function instance(n=70){return {actor_ref:'d'.repeat(64),instance_id:id(n),state:'PLAN_ADOPTED',run_id:id(2),case_id:id(1),preparation_id:id(3),plan_id:id(9),release_available:true,binding:{source:'SYNTHETIC'}};}

function planning(hash='a',bad=null){const current={preparation_id:id(3),case_id:id(1),run_id:id(2),preparation_revision:4,source_sha256:hash.repeat(64),required_goals:['LOCAL_MATERIAL_PREPARATION'],state:'COVERED_PREVIEW_ONLY',steps:[]};const x={actor_ref:'d'.repeat(64),instance_id:id(70),preparation_id:id(3),case_id:id(1),run_id:id(2),plan_id:null,request_intent:{revision:2,current_request:'SYNTHETIC private need',required_goals:current.required_goals,planning_constraints:{excluded_roles:['service_executor'],additional_requirements:[]}},current,service_case_plan:{...current,actor_ref:'d'.repeat(64),plan_id:null,request_revision:2,current_preview:structuredClone(current),can_adopt:true}};if(bad==='nested_case')x.current.case_id=id(8);if(bad==='nested_sha')x.service_case_plan.current_preview.source_sha256='b'.repeat(64);if(bad==='nested_goals')x.request_intent.required_goals=['LOCAL_CASE_RECORD_RECHECK'];return x;}

function handle(){return {v:1,actor:'d'.repeat(64),instance:id(70),case:id(1),run:id(2),preparation:id(3),key:id(99),source:'a'.repeat(64),preparationRevision:4,requestRevision:2,partial:true};}
function pendingInstance(){return {...instance(),stages:[{name:'CONFIRM_PLAN_SYNTHETIC',state:'UNKNOWN',request_key:'original-key'}],service_case_plan:{partial_adoption:true}};}
function proof(){return {instance_id:id(70),actor_ref:'d'.repeat(64),consumer_request_key:id(99),original_request_key:'original-key',automatically_replayed:false,product_read_only:true,journal_read_only:true,case_goal_completed:false,status:'COMMITTED',original_request:{expected_source_sha256:'a'.repeat(64),expected_preparation_revision:4,expected_request_revision:2,partial_adoption:true},receipt:{actor_ref:'d'.repeat(64),preparation_id:id(3),case_id:id(1),run_id:id(2),status:'COMMITTED',event:{action:'ADOPT',request_key:'original-key',plan_id:id(9),current_plan:true}},instance:pendingInstance()};}
(async()=>{
 finish(calls[0],200,{enabled_for_isolated_tests:true,isolated_personas:[],registered_goals:['LOCAL_MATERIAL_PREPARATION']});await tick();$('consumer-token').value='SYNTHETIC_A';
 const h=handle(),name='parkweave.template-adoption-recovery.v1.'+h.actor+'.'+h.instance;
 store[name]=JSON.stringify(h);
 run('renderInstance('+JSON.stringify(pendingInstance())+')');
 check(run('adoptionHandle.key')===h.key);check($('product-link').hidden);check($('consumer-adopt').disabled);
 if(mode==='cold_committed'){
   const p=$('consumer-adoption-recover').onclick();check(calls.at(-1).options.method==='GET');check(calls.at(-1).options.headers['Idempotency-Key']===h.key);finish(calls.at(-1),200,proof());await p;
   check(!$('product-link').hidden);check(run('adoptionHandle===null'));check(store[name]===JSON.stringify(h));check(run('instance.stages[0].state')==='UNKNOWN');
   run('clearConsumer()');$('consumer-token').value='SYNTHETIC_A';run('renderInstance('+JSON.stringify(pendingInstance())+')');check($('product-link').hidden);check(run('adoptionHandle.key')===h.key);
   const p2=$('consumer-adoption-recover').onclick();finish(calls.at(-1),200,proof());await p2;check(!$('product-link').hidden);
 }else if(mode==='late_get'){
   const p=$('consumer-adoption-recover').onclick(),old=calls.at(-1);run('clearConsumer()');$('consumer-token').value='SYNTHETIC_B';run('renderInstance('+JSON.stringify({...instance(71),actor_ref:'e'.repeat(64)})+')');finish(old,200,proof());await p;
   check(run('instance.instance_id')===id(71));check(run('instance.actor_ref')==='e'.repeat(64));check(store[name]===JSON.stringify(h));check(run('adoptionHandle===null'));check(run('adoptionRecovering===false'));
 }else if(mode==='current403'){
   const p=$('consumer-adoption-recover').onclick();let parses=0;calls.at(-1).resolve({status:403,ok:false,json:async()=>{parses++;throw Error('EMPTY');}});await p;
   check(parses===0);check(run('instance===null&&cp===null&&adoptionHandle===null'));check($('product-link').hidden);check(store[name]===JSON.stringify(h));check($('consumer-error').textContent.includes('无权访问'));
 }else if(mode==='damaged_handle'){
   store[name]=JSON.stringify({...h,token:'SYNTHETIC_UNEXPECTED'});run('renderInstance('+JSON.stringify(pendingInstance())+')');check(run('adoptionHandle.invalid'));const n=calls.length;await $('consumer-adoption-recover').onclick();await $('consumer-adopt').onclick();await $('consumer-retry').onclick();check(calls.length===n);check($('product-link').hidden);check($('consumer-error').textContent.includes('未决'));
 }else if(mode==='storage_denial'){
   for(const k of Object.keys(store))delete store[k];run('clearConsumer()');run('renderInstance('+JSON.stringify({...instance(),state:'PLAN_CONFIRMATION_REQUIRED',plan_id:null})+')');run('renderPlanning('+JSON.stringify(planning())+')');run('confirmed=planningView');$('consumer-plan-reason').value='SYNTHETIC reason';
   for(const k of Object.keys(store))delete store[k];context.localStorage=new Proxy(storage,{get:(a,k)=>k==='setItem'?()=>{throw Error('SYNTHETIC storage denied');}:a[k]});
   const n=calls.length;await $('consumer-adopt').onclick();check(calls.length===n);check(run('cp===null&&adoptionHandle===null'));check($('consumer-error').textContent.includes('尚未发送'));check($('product-link').hidden);
 }else throw Error('unknown mode');
 check(calls.filter(c=>c.options?.method==='POST').length===0);
 console.log(JSON.stringify({mode,checks,result:'PASS',scope:'ORIGINAL_HTML_NODEVM_NO_BROWSER_NO_BACKEND_AUTHORITY_PROOF'}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
