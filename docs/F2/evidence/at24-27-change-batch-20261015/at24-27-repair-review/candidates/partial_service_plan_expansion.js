// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let nextRequestKey=99;const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.style={};this.listeners={};}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 prepend(...x){this.children.unshift(...x);}reset(){}addEventListener(n,f){this.listeners[n]=f;}setAttribute(){}removeAttribute(name){delete this[name];}
 closest(){return null;}querySelectorAll(){return [];}scrollIntoView(){this.scrolled=true;}
 get options(){return this.children.filter(x=>x.tagName==='option');}get selectedOptions(){return this.options.filter(x=>x.value===this.value);}get firstChild(){return this.children[0]??null;}get firstElementChild(){return this.children[0];}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
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
 const p=page('src/parkweave/web.html');p.get('token').value='SYNTHETIC_fixture-a';const preparation=process.argv[3],newGoal='SYNTHETIC_SECOND_REQUIRED_NO_SERVICE';
 await p.read(`loadPreparation('${preparation}',{role:'enterprise_operator'})`);await p.get('service-plan-prepare').onclick();
 const oldId=p.read('servicePlanView.plan_id');check(!!oldId);check(p.read('servicePlanView.required_goals.length')===2);
 await p.get('plan-prepare').onclick();p.get('request-current').value='SYNTHETIC explicit third required service goal';
 p.get('plan-required-goals').value=['LOCAL_MATERIAL_PREPARATION','SYNTHETIC_EXTERNAL_AUTHORITY_APPROVAL',newGoal].join('\n');
 await p.get('request-intent-form').onsubmit({preventDefault(){}});check(p.read('planView.request_intent.required_goals.length')===3);
 await p.get('service-plan-prepare').onclick();check(p.read('servicePlanView.current_preview.required_goals.length')===3);
 const text=e=>e.textContent+' '+e.children.map(text).join(' ');
 check(text(p.get('service-plan-coverage')).includes(newGoal));
 check(text(p.get('service-plan-coverage')).includes('旧采纳目标'));
 check(!p.get('service-plan-partial-confirm').checked);check(!p.get('service-plan-adopt').hidden);
 const before=calls.filter(x=>x.options.method==='POST').length;p.get('service-plan-reason').value='SYNTHETIC explicitly keep all current goals and replace independent part';
 await p.get('service-plan-adopt').onclick();check(calls.filter(x=>x.options.method==='POST').length===before);
 p.get('service-plan-partial-confirm').checked=true;await p.get('service-plan-adopt').onclick();
 check(p.read('servicePlanView.plan_id')!==oldId);check(p.read('servicePlanView.required_goals.length')===3);
 check(p.read('servicePlanView.history.length')===1);check(p.read('servicePlanView.overall_goal_state')==='PARTIAL');check(p.read('servicePlanView.history[0].required_goals.length')===2);check(p.read('servicePlanView.case_goal_completed')===false);
 const adoption=calls.find(x=>x.options.method==='POST'&&x.path.endsWith('/service-case-plan'));
 check(JSON.parse(adoption.options.body).required_goals.includes(newGoal));check(JSON.parse(adoption.options.body).partial_adoption===true);
 console.log(JSON.stringify({checks,http:calls.length,posts:calls.filter(x=>x.options.method==='POST').length,adopts:1,scope:'ORIGINAL_HTML_EXISTING_PLAN_CURRENT_ADDED_MANDATORY_GOAL_EXPLICIT_PARTIAL_REPLACEMENT_HISTORY'}));process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1);});
