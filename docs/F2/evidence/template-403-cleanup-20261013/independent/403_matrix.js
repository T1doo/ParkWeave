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



function instance(n=70,state='PLAN_ADOPTED'){return {instance_id:id(n),state,run_id:id(n+100),case_id:id(n+200),preparation_id:id(n+300),plan_id:id(n+400),release_available:true,binding:{private:'SYNTHETIC_PRIVATE_'+n}};}
async function initialConsumer(state='PLAN_ADOPTED'){$('consumer-token').value='SYNTHETIC_A';$('consumer-instance-id').value=id(70);const read=$('consumer-read').onclick();finish(calls.at(-1),200,instance(70,state));await read;check(run('instance!==null'));$('consumer-goal').value='SYNTHETIC_PRIVATE_GOAL';$('consumer-need-summary').value='SYNTHETIC_PRIVATE_NEED';$('consumer-material-outline').value='SYNTHETIC_PRIVATE_OUTLINE';}
async function newConsumer(aba=false){$('consumer-token').value='SYNTHETIC_B';$('consumer-token').oninput();if(aba){$('consumer-token').value='SYNTHETIC_A';$('consumer-token').oninput();}$('consumer-instance-id').value=id(71);const read=$('consumer-read').onclick();finish(calls.at(-1),200,instance(71));await read;$('consumer-goal').value='SYNTHETIC_NEW_PRIVATE_GOAL';}
async function initialTemplate(){$('template-actor').value='SYNTHETIC_AUTHOR';$('template-park').value='park-a';$('template-id').value='SYNTHETIC_TEMPLATE';const load=$('template-refresh').onclick();finish(calls.at(-1),200,{state:'DRAFT',revision:1,content_version:1,definition_sha256:'f'.repeat(64),draft:{name:'SYNTHETIC_PRIVATE_NAME',source:{revision:'1',statement:'SYNTHETIC_PRIVATE_SOURCE'},required_goals:[]},history:[{reason:'SYNTHETIC_PRIVATE_HISTORY'}],releases:[]});await load;check(run('view!==null'));$('template-reason').value='SYNTHETIC_PRIVATE_REASON';}
let parses=0;
function deny(call){call.resolve({status:403,ok:false,json:async()=>{parses++;throw new SyntaxError(mode.includes('empty')?'SYNTHETIC EMPTY403':'SYNTHETIC NONJSON403');}});}
(async()=>{
 finish(calls[0],200,{enabled_for_isolated_tests:true,isolated_personas:[],registered_goals:[]});await tick();
 if(mode==='template_post403'){
  await initialTemplate();const post=run("writeTemplate('SUBMIT')");check(calls.at(-1).options.method==='POST');deny(calls.at(-1));await post;check(parses===0);check(run('tp===null'));check(run('view===null'));check($('template-retry').hidden);check($('template-reason').value==='');check($('template-history').children.length===0);
 }else if(mode==='consumer_post403'){
  await initialConsumer('PENDING_PREPARATION');const post=$('consumer-resume').onclick();check(calls.at(-1).options.method==='POST');deny(calls.at(-1));await post;check(parses===0);check(run('cp===null'));check(run('instance===null'));check($('consumer-retry').hidden);check($('consumer-goal').value==='');check($('consumer-result').children.length===0);check(calls.filter(c=>c.options?.method==='POST').length===1);
 }else{
  await initialConsumer();const old=$('consumer-read').onclick(),request=calls.at(-1);
  if(mode==='json_generation'){
   let resolveJSON;request.resolve({status:200,ok:true,json:()=>{parses++;return new Promise(r=>resolveJSON=r);}});await tick();check(parses===1);await newConsumer();resolveJSON(instance(70));await old;check(run('instance.instance_id')===id(71));check($('consumer-goal').value==='SYNTHETIC_NEW_PRIVATE_GOAL');check($('product-link').href==='/?template_instance='+id(71));check($('consumer-error').textContent==='');
  }else if(mode.startsWith('late_')){
   await newConsumer(mode.endsWith('aba'));deny(request);await old;check(parses===0);check(run('instance.instance_id')===id(71));check($('consumer-goal').value==='SYNTHETIC_NEW_PRIVATE_GOAL');check($('product-link').href==='/?template_instance='+id(71));check($('consumer-error').textContent==='');
  }else{
   deny(request);await old;check(parses===0);check(run('instance===null'));check(run('catalog===null'));check($('consumer-result').children.length===0);check($('consumer-goal').value==='');check($('consumer-need-summary').value==='');check($('consumer-material-outline').value==='');check($('product-link').hidden);check(!$('product-link').href);check($('consumer-error').textContent.includes('无权'));
  }
 }
 console.log(JSON.stringify({mode,checks,result:'PASS',scope:'FULL_ORIGINAL_TEMPLATE_HTML_REAL_CALLERS_NO_PENDING_OR_ENTRY_MOCK_HTTPDOM_ONLY'}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
