// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let nextRequestKey=99;const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.style={};this.listeners={};}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 prepend(...x){this.children.unshift(...x);}reset(){}addEventListener(n,f){(this.listeners[n]??=[]).push(f);}trigger(n){for(const f of this.listeners[n]||[])f({target:this});}setAttribute(){}removeAttribute(name){delete this[name];}
 closest(){return null;}querySelectorAll(selector){const out=[];function visit(e){for(const c of e.children){if((selector==='select[data-fact-field]'&&c.dataset.factField)||(selector==='input[data-manual-material]'&&c.dataset.manualMaterial))out.push(c);visit(c);}}visit(this);return out;}scrollIntoView(){this.scrolled=true;}
 get options(){return this.children.filter(x=>x.tagName==='option');}get selectedOptions(){return this.options.filter(x=>x.value===this.value);}get firstElementChild(){return this.children[0];}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
let onDenied=null;let delayPath='';let delayedResponse=false,releaseDelayed=null,delayNext=false,delayedPost=false,releasePost=null;
const lines=require('readline').createInterface({input:process.stdin}),replies=[],calls=[];
lines.on('line',line=>{replies.shift()?.(JSON.parse(line));});
async function fetchAPI(path,options={}){calls.push({path,options});const response=new Promise(resolve=>replies.push(resolve));console.log(JSON.stringify({request:{path,options}}));const x=await response;if(x.status===403&&onDenied)onDenied();if(delayNext&&path.endsWith(delayPath)&&(!options.method||options.method==='GET')){delayNext=false;delayedResponse=true;await new Promise(r=>releaseDelayed=r);}if(x.lost){delayedPost=true;await new Promise(r=>releasePost=r);}if(x.lost)throw Error('SYNTHETIC actual committed reply lost');return {status:x.status,ok:x.status>=200&&x.status<300,json:async()=>x.body};}
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
 const pid=process.argv[2],actor=process.argv[3],B=process.argv[4],mode=process.argv[5],p=page('src/parkweave/web.html');p.get('token').value='SYNTHETIC_'+actor;
 await p.read('loadServiceCasePlan('+JSON.stringify(pid)+')');await p.get('goal-results-read').onclick();
 const goal=mode.startsWith('fact')?'LOCAL_MATERIAL_PREPARATION':B,card=p.get('goal-results-items').children.find(c=>c.dataset.goalName===goal),open=card?.children.find(c=>c.dataset.goalOpen===goal);check(!!open);
 const opaqueName='parkweave.manual-goal-original-key.v1.'+actor+'.'+id(889),opaque=JSON.stringify({actor,id:pid,key:id(889)});onDenied=()=>p.read('localStorage.setItem('+JSON.stringify(opaqueName)+','+JSON.stringify(opaque)+')');
 const late=mode.includes('late');delayPath=mode.startsWith('fact')?'/fact-clarifications':'/manual-goal-requests';delayNext=late;const pending=open.onclick();
 if(late){
  await waitFor(()=>delayedResponse);console.log(JSON.stringify({ind_restore:true,newcase:mode.endsWith('newcase')}));const reply=await new Promise(r=>replies.push(r));
  if(mode.endsWith('identity')){p.get('token').value='SYNTHETIC_'+reply.actor;p.get('token').trigger('input');p.get('manual-goal-id').value=pid;await p.read('mgRead()');check(p.read('mgView.actor_id')===reply.actor);}
  else{await p.read('loadServiceCasePlan('+JSON.stringify(reply.pid)+')');await p.get('goal-results-read').onclick();p.get('manual-goal-id').value=reply.pid;await p.read('mgRead()');check(p.read('mgView.preparation_id')===reply.pid);}
  p.get('manual-goal-reason').value='SYNTHETIC newer permitted draft';const plan=p.read('JSON.stringify(servicePlanView)'),view=p.read('JSON.stringify(goalResultView)'),manual=p.read('JSON.stringify(mgView)'),n=calls.length,stored=JSON.stringify(p.snapshot());releaseDelayed();await pending;
  check(p.read('JSON.stringify(servicePlanView)')===plan);check(p.read('JSON.stringify(goalResultView)')===view);check(p.read('JSON.stringify(mgView)')===manual);check(p.get('manual-goal-reason').value==='SYNTHETIC newer permitted draft');check(calls.length===n);check(JSON.stringify(p.snapshot())===stored);check(p.read('mgBusy')===false);
 }else{
  await pending;
  if(mode==='fact_field'){check(p.read('goalResultView')!==null);check(p.read('servicePlanView')!==null);check(p.read('preparationView')!==null);check(p.read('caseFactView')===null);check(p.get('case-fact-fields').children.length===0);check(calls.some(c=>c.path.endsWith('/case-cancellation')));check(p.get('case-fact-error').textContent.length>0);}
  else{check(p.read('goalResultView')===null);check(p.read('servicePlanView')===null);check(p.read('mgView')===null);check(p.read('preparationView')===null);check(p.get('goal-results-items').children.length===0);check(p.get('service-plan-steps').children.length===0);check(p.get('manual-goal-form').hidden);check(p.get('goal-results-panel').hidden);check(p.get('service-case-plan-detail').hidden);if(mode==='fact_global')check(!calls.some(c=>c.path.endsWith('/case-cancellation')));}
 }
 check(p.snapshot()[opaqueName]===opaque);check(calls.every(c=>!c.options.method||c.options.method==='GET'));console.log(JSON.stringify({result:'PASS',checks,http:calls.length,posts:0,mode}));process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1)});
