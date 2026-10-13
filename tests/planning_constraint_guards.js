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
function legacy(){return {preparation_id:id(3),case_id:id(1),role:'enterprise_operator',plan_id:null,template_sha256:'a'.repeat(64),state:'NOT_STARTED',can_create:false,creation_blockers:[],preparation_revision:1,request_intent:{recorded:true,original_request:'SYNTHETIC PRIVATE REQUEST',current_request:'SYNTHETIC PRIVATE REQUEST',revision:1,required_goals:['LOCAL_MATERIAL_PREPARATION'],coverage:{state:'PARTIAL',items:[]}},steps:[],history:[]};}
async function loadLegacy(){const r=run("loadPlan('"+id(3)+"')");finish(calls.at(-1),200,legacy());await r;}
async function loadPreview(){await loadLegacy();const r=$('bounded-planning-read').onclick();finish(calls.at(-1),200,{current:{preparation_id:id(3),case_id:id(1),run_id:id(2),preparation_revision:1,source_sha256:'f'.repeat(64),state:'COVERED_PREVIEW_ONLY',required_goals:['LOCAL_MATERIAL_PREPARATION'],goal_coverage:[],steps:[]},history:[]});await r;check(run('boundedView!==null'));}
async function oldService(){const x={preparation_id:id(3),case_id:id(1),run_id:id(2),plan_id:id(9),actor_ref:'a'.repeat(64),role:'enterprise_operator',state:'ACTIVE',revision:1,preparation_revision:1,request_revision:1,steps:[],history:[],events:[{id:id(22),revision:1,action:'ADOPT',reason:'SYNTHETIC PRIVATE OLD PLAN HISTORY'}],required_goals:['LOCAL_MATERIAL_PREPARATION'],can_adopt:false,read_only:false};const r=run("loadServiceCasePlan('"+id(3)+"')");finish(calls.at(-1),200,{status:'NO_REQUEST',read_only:true,automatically_replayed:false,actor_ref:x.actor_ref,case_id:x.case_id,run_id:x.run_id,current:x});await tick();finish(calls.at(-1),200,x);await r;}
(async()=>{
 if(mode==='pending_fields'){
  await loadLegacy();$('resource-binding-choice').value=id(40);const r=$('resource-binding-read').onclick();finish(calls.at(-1),200,{preparation_id:id(3),case_id:id(1),preparation_revision:1,association_blockers:[],checkpoints:{},history:[],required_rechecks:[],candidate:{changes:[],issues:[],combination:{id:id(40)},comparison:{can_confirm:true,preparation_revision:1,link_revision:1,sha256:'b'.repeat(64),blockers:[]}}});await tick();finish(calls.at(-1),200,{preparation_revision:1,items:[{reason:'CURRENT',combination:{id:id(40),members:[]}}]});await r;$('resource-binding-confirm-reason').value='SYNTHETIC exact pending substitution';const submit=$('resource-binding-confirm-form').onsubmit({preventDefault(){}}),post=calls.at(-1);check(post.options.method==='POST');const pending=run('resourceBindingPending');check(pending!==null);
  for(const name of ['request-exclude-owner','request-exclude-specialist','request-exclude-executor','request-additional-requirements'])check($(name).disabled);
  post.reject(Error('SYNTHETIC RESPONSE LOST'));await submit;check(run('resourceBindingPending.stage')==='UNCERTAIN');const count=calls.length;for(const name of ['request-exclude-owner','request-exclude-specialist','request-exclude-executor']){$(name).checked=true;$(name).oninput();check($(name).checked===false);check(run('resourceBindingPending')===pending);}$('request-additional-requirements').value='SYNTHETIC late private edit';$('request-additional-requirements').oninput();check($('request-additional-requirements').value==='');check(run('resourceBindingPending')===pending);check(calls.length===count);check(pending.key===post.options.headers['Idempotency-Key']);check(JSON.stringify(pending.body)===post.options.body);
 }else if(mode==='dirty_constraint'){
  await loadPreview();const before=calls.length;$('request-exclude-executor').checked=true;$('request-exclude-executor').oninput();check(run('boundedView')===null);check($('bounded-planning-confirm').disabled);await $('bounded-planning-read').onclick();check(calls.length===before);check($('bounded-planning-error').textContent.includes('保存'));
 }else{
  await oldService();check($('service-plan-history').children.length>0);await loadPreview();const r=$('bounded-planning-confirm').onclick(),request=calls.at(-1);check(request.path.endsWith('/command-recovery'));
  if(mode==='late403'){$('token').value='SYNTHETIC_SESSION_B';$('token').oninput();$('token').value='SYNTHETIC_SESSION_A';$('token').oninput();await oldService();finish(request,403,{detail:'SYNTHETIC OLD DENIAL'});await r;check(run('servicePlanView.plan_id')===id(9));check($('service-plan-history').children.length>0);}
  else{let parses=0;if(mode==='read500')finish(request,500,{detail:'SYNTHETIC temporary refusal'});else request.resolve({status:403,ok:false,json:async()=>{parses++;throw new SyntaxError(mode==='empty403'?'Unexpected end':'Unexpected token <');}});await r;check(parses===0);check(run('servicePlanView')===null);check($('service-plan-history').children.length===0);check($('service-plan-adopt').hidden);if(mode!=='read500'){check(run('planView')===null);check($('request-current').value==='');check(!$('page-feedback').textContent.includes('Unexpected'));}}
 }
 console.log(JSON.stringify({mode,checks,result:'PASS',scope:'FULL_ORIGINAL_HTML_HANDLERS_HTTPDOM_PENDING_CREATED_BY_ORIGINAL_SUBSTITUTION_POST_AND_GENERATION_GUARDS'}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
