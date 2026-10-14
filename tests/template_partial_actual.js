// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let nextRequestKey=99;const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.style={};this.listeners={};}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 prepend(...x){this.children.unshift(...x);}reset(){}addEventListener(n,f){this.listeners[n]=f;}setAttribute(){}removeAttribute(name){delete this[name];}
 closest(){return null;}querySelectorAll(){return [];}scrollIntoView(){this.scrolled=true;}
 get options(){return this.children.filter(x=>x.tagName==='option');}get selectedOptions(){return this.options.filter(x=>x.value===this.value);}get firstElementChild(){return this.children[0];}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
const lines=require('readline').createInterface({input:process.stdin}),replies=[],calls=[];
lines.on('line',line=>{replies.shift()?.(JSON.parse(line));});
async function fetchAPI(path,options={}){calls.push({path,options});const response=new Promise(resolve=>replies.push(resolve));console.log(JSON.stringify({request:{path,options}}));const x=await response;if(x.lost)throw Error('SYNTHETIC actual committed reply lost');return {status:x.status,ok:x.status>=200&&x.status<300,json:async()=>x.body};}
function page(file,search='',seed={}){
 const elements=new Map(),get=id=>{if(!elements.has(id)){const e=new Element();e.id=id;elements.set(id,e);}return elements.get(id);},store={...seed},events=[];
 const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},{ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
 get('run-access-valid-until').parentElement={firstChild:{textContent:''}};
 const ctx=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,URLSearchParams,structuredClone,TextEncoder,
  Option:function(text,value){const o=new Element('option');o.textContent=text;o.value=value;return o;},
  crypto:{randomUUID:()=>id(nextRequestKey++)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},location:{search},
  document:{getElementById:get,createElement:t=>new Element(t),querySelectorAll:selector=>{const all=[];function visit(e){if(e.dataset?.consumerGoal&&(!selector.includes(':checked')||e.checked))all.push(e);for(const c of e.children||[])visit(c);}for(const e of elements.values())visit(e);return selector.includes('data-consumer-goal')?all:[];},body:new Element('body'),addEventListener:(...a)=>events.push(a)},window:{addEventListener(){}},fetch:fetchAPI});
 vm.runInContext(fs.readFileSync(file,'utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1],ctx);return {get,read:s=>vm.runInContext(s,ctx),events,storageKeys:()=>Object.keys(store),snapshot:()=>({...store})};
}
function nested(root,predicate){for(const child of root.children){if(predicate(child))return child;const found=nested(child,predicate);if(found)return found;}return null;}
async function waitFor(predicate){const end=Date.now()+10000;while(!predicate()){if(Date.now()>end)throw Error('page response not ready');await new Promise(r=>setTimeout(r,10));}}


(async()=>{
 const file='src/parkweave/template_candidate_web.html',actor='SYNTHETIC_'+process.argv[3];
 const t=page(file);await waitFor(()=>t.read('status!==null'));t.get('consumer-token').value=actor;
 await t.get('consumer-catalog').onclick();t.get('consumer-release').value=t.get('consumer-release').options[0].value;t.get('consumer-release').onchange();t.get('consumer-reviewer').value=t.get('consumer-reviewer').options[0].value;
 for(const [id,value] of Object.entries({'consumer-goal':'SYNTHETIC independent preparation and external approval','consumer-need-summary':'SYNTHETIC explicit need','consumer-need-source':'SYNTHETIC user','consumer-material-outline':'SYNTHETIC outline','consumer-outline-source':'SYNTHETIC document'}))t.get(id).value=value;
 const external=nested(t.get('consumer-goals'),x=>x.dataset.consumerGoal==='SYNTHETIC_EXTERNAL_AUTHORITY_APPROVAL');check(!!external);external.checked=true;external.onchange();
 await t.get('consumer-create').onclick();await t.get('consumer-resume').onclick();await t.get('consumer-preview').onclick();
 check(t.read('planningView.current.state')==='PARTIAL');check(t.read('planningView.current.partial_offer.can_adopt')===true);check(t.read('planningView.current.partial_offer.manual_goals.length')===1);
 await t.get('consumer-confirm').onclick();check(t.read('confirmed!==null'));check(t.get('consumer-adopt').disabled);
 t.get('consumer-plan-reason').value='SYNTHETIC explicit partial approval all goals retained';let before=calls.length;await t.get('consumer-adopt').onclick();check(calls.length===before);
 t.get('consumer-partial-confirm').checked=true;t.get('consumer-partial-confirm').onchange();check(!t.get('consumer-adopt').disabled);await t.get('consumer-adopt').onclick();
 check(t.read('cp.state')==='UNKNOWN');check(t.get('product-link').hidden);check(calls.filter(x=>x.options.method==='POST'&&x.path.endsWith('/adopt')).length===1);
 const original=t.read('cp.key'),instance=t.read('instance.instance_id'),preparation=t.read('instance.preparation_id');
 const cold=page(file,'',t.snapshot());await waitFor(()=>cold.read('status!==null'));cold.get('consumer-token').value=actor;cold.get('consumer-instance-id').value=instance;
 await cold.get('consumer-read').onclick();check(cold.read('adoptionHandle.key')===original);check(cold.get('product-link').hidden);
 await cold.get('consumer-adoption-recover').onclick();check(cold.read('adoptionHandle')===null);check(!cold.get('product-link').hidden);check(cold.read('instance.service_case_plan.overall_goal_state')==='PARTIAL');
 check(cold.snapshot()[cold.storageKeys().find(x=>x.startsWith('parkweave.template-adoption-recovery'))]!==undefined);
 check(calls.filter(x=>x.options.method==='POST'&&x.path.endsWith('/adopt')).length===1);
 const again=page(file,'',cold.snapshot());await waitFor(()=>again.read('status!==null'));again.get('consumer-token').value=actor;again.get('consumer-instance-id').value=instance;await again.get('consumer-read').onclick();check(again.get('product-link').hidden);await again.get('consumer-adoption-recover').onclick();check(!again.get('product-link').hidden);
 const p=page('src/parkweave/web.html','?template_instance='+instance);p.get('token').value=actor;await p.get('template-instance-read').onclick();
 check(p.read('servicePlanView.preparation_id')===preparation);check(p.read('servicePlanView.overall_goal_state')==='PARTIAL');check(p.read('servicePlanView.required_goals.length')===2);
 console.log(JSON.stringify({prepare_review:{preparation_id:preparation}}));await new Promise(resolve=>replies.push(resolve));
 await p.read(`loadServiceCasePlan('${preparation}')`);p.get('service-plan-reason').value='SYNTHETIC verify original confirmed independent output';const verify=nested(p.get('service-plan-steps'),x=>x.dataset.serviceAction==='VERIFY');check(!!verify);await verify.onclick();check(p.read('servicePlanView.steps[0].state')==='VERIFIED');check(p.read('servicePlanView.overall_goal_state')==='PARTIAL');
 await p.get('goal-results-read').onclick();check(p.read('goalResultView.state')==='PARTIAL');check(p.read('goalResultView.results.map(x=>x.state).join(",")')==='LOCAL_OUTPUT_VERIFIED,UNSUPPORTED');
 await p.get('case-worklist-read').onclick();const link=nested(p.get('case-worklist-items'),x=>!!x.dataset.partialPlan);check(!!link);await link.onclick();check(p.read('servicePlanView.preparation_id')===preparation);check(p.read('servicePlanView.required_goals.length')===2);
 console.log(JSON.stringify({mode:'template_partial_actual',checks,http:calls.length,adopts:1,lost:1,instance,preparation,key:original,scope:'ORIGINAL_TEMPLATE_AND_HANDLING_HTML_NODEVM_ASGI_OWNED_PG_COLD_RECOVERY_REVIEW_VERIFY_RESULTS_WORKLIST'}));process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1);});
