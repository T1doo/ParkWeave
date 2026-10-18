// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let nextRequestKey=99;const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.style={};this.listeners={};this.className='';const tokens=()=>new Set(this.className.split(/\s+/).filter(Boolean));this.classList={add:(...names)=>{const t=tokens();for(const n of names)t.add(n);this.className=[...t].join(' ');}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 prepend(...x){this.children.unshift(...x);}reset(){}addEventListener(n,f){this.listeners[n]=f;}setAttribute(){}removeAttribute(name){delete this[name];}
 closest(){return null;}querySelectorAll(){return [];}scrollIntoView(){this.scrolled=true;}
 get options(){return this.children.filter(x=>x.tagName==='option');}get selectedOptions(){return this.options.filter(x=>x.value===this.value);}get firstElementChild(){return this.children[0];}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
const classProbe=new Element();classProbe.className='keep';classProbe.classList.add('case-cancel-recovery-only');check(classProbe.classList.contains('keep')&&classProbe.classList.contains('case-cancel-recovery-only'));classProbe.classList.remove('case-cancel-recovery-only');check(classProbe.className==='keep');
const lines=require('readline').createInterface({input:process.stdin}),replies=[],calls=[];
lines.on('line',line=>{replies.shift()?.(JSON.parse(line));});
async function fetchAPI(path,options={}){calls.push({path,options});const response=new Promise(resolve=>replies.push(resolve));console.log(JSON.stringify({request:{path,options}}));const x=await response;if(x.lost)throw Error('SYNTHETIC response lost after actual server commit');return {status:x.status,ok:x.status>=200&&x.status<300,json:async()=>x.body};}
function page(file,search='',seed={}){
 const elements=new Map(),get=id=>{if(!elements.has(id)){const e=new Element();e.id=id;elements.set(id,e);}return elements.get(id);},store={...seed},events=[];
 const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},{ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
 get('run-access-valid-until').parentElement={firstChild:{textContent:''}};
 const ctx=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,URLSearchParams,structuredClone,TextEncoder,
  Option:function(text,value){const o=new Element('option');o.textContent=text;o.value=value;return o;},
  crypto:{randomUUID:()=>id(nextRequestKey++)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},location:{search},
  document:{getElementById:get,createElement:t=>new Element(t),querySelectorAll:()=>[],body:new Element('body'),addEventListener:(...a)=>events.push(a)},window:{addEventListener(){}},fetch:fetchAPI});
 vm.runInContext(fs.readFileSync(file,'utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1],ctx);return {get,read:s=>vm.runInContext(s,ctx),events,storageKeys:()=>Object.keys(store),snapshot:()=>({...store})};
}
function nested(root,predicate){for(const child of root.children){if(predicate(child))return child;const found=nested(child,predicate);if(found)return found;}return null;}
async function waitFor(predicate){const end=Date.now()+10000;while(!predicate()){if(Date.now()>end)throw Error('page response not ready');await new Promise(r=>setTimeout(r,10));}}
(async()=>{
 const file='src/parkweave/web.html',preparation=process.argv[3];
 const p=page(file);p.get('token').value='SYNTHETIC_fixture-a';
 await p.read(`loadPreparation('${preparation}',{role:'enterprise_operator'})`);
 await p.get('plan-prepare').onclick();await p.get('bounded-planning-read').onclick();
 check(p.read('boundedView.current.state')==='PARTIAL');check(p.read('boundedView.current.required_goals.length')===2);
 check(p.read('boundedView.current.partial_offer.step_ids.join(",")')==='P1');check(!p.get('bounded-planning-confirm').disabled);
 const sha=p.read('boundedView.current.source_sha256'),posts=()=>calls.filter(x=>x.options.method==='POST').length;
 const before=posts();await p.get('bounded-planning-confirm').onclick();check(posts()===before);
 check(p.read('servicePlanView.current_preview.source_sha256')===sha);check(!p.get('service-plan-adopt').hidden);
 p.get('service-plan-reason').value='SYNTHETIC explicitly adopt independent part and keep manual goal';
 await p.get('service-plan-adopt').onclick();check(posts()===before);check(p.get('service-plan-error').textContent.includes('PARTIAL'));
 p.get('service-plan-partial-confirm').checked=true;await p.get('service-plan-adopt').onclick();
 check(posts()===before+1);check(p.read('servicePlanPending.stage')==='UNCERTAIN');check(p.storageKeys().some(x=>x.startsWith('parkweave.service-plan-recovery')));
 const cold=page(file,'',p.snapshot());cold.get('token').value='SYNTHETIC_fixture-a';
 await cold.read(`loadServiceCasePlan('${preparation}')`);check(posts()===before+1);
 check(cold.read('servicePlanView.read_only')===true);check(cold.read('servicePlanView.overall_goal_state')==='PARTIAL');
 check(cold.get('service-plan-feedback').textContent.includes('已保存'));check(cold.read('servicePlanView.steps.length')===1);
 await cold.get('service-plan-release').onclick();check(posts()===before+1);check(cold.read('servicePlanView.read_only')!==true);
 cold.get('service-plan-reason').value='SYNTHETIC verify actual original material review and owner confirmation';
 const verify=nested(cold.get('service-plan-steps'),x=>x.dataset.serviceAction==='VERIFY');check(!!verify);await verify.onclick();
 check(cold.read('servicePlanView.steps[0].state')==='VERIFIED');check(cold.read('servicePlanView.overall_goal_state')==='PARTIAL');
 await cold.get('goal-results-read').onclick();check(cold.read('goalResultView.state')==='PARTIAL');
 check(cold.read('goalResultView.results.map(x=>x.state).join(",")')==='LOCAL_OUTPUT_VERIFIED,UNSUPPORTED');
 check(cold.get('goal-results-status').textContent.includes('PARTIAL'));
 await cold.get('case-worklist-read').onclick();const button=nested(cold.get('case-worklist-items'),x=>!!x.dataset.partialPlan);check(!!button);
 await button.onclick();check(cold.read('servicePlanView.preparation_id')===preparation);check(cold.read('servicePlanView.overall_goal_state')==='PARTIAL');
 check(cold.read('servicePlanView.required_goals.length')===2);check(cold.read('servicePlanView.steps.length')===1);
 console.log(JSON.stringify({mode:'partial_original_entry',checks,http:calls.length,posts:posts(),adopts:calls.filter(x=>x.options.method==='POST'&&x.path.endsWith('/service-case-plan')).length,scope:'ORIGINAL_HTML_OWNED_PG_EXPLICIT_PARTIAL_LOST_RESPONSE_COLD_READ_ONLY_RECOVERY_RESULTS_WORKLIST_NO_BROWSER'}));process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1);});
