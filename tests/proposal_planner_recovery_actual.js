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
let onDenied=null;let delayMethod='GET',delayPath='';let delayedResponse=false,releaseDelayed=null,delayNext=false,delayedPost=false,releasePost=null,holdMaterialPost=false;
const lines=require('readline').createInterface({input:process.stdin}),replies=[],calls=[];
lines.on('line',line=>{replies.shift()?.(JSON.parse(line));});
async function fetchAPI(path,options={}){calls.push({path,options});const response=new Promise(resolve=>replies.push(resolve));console.log(JSON.stringify({request:{path,options}}));const x=await response;if(holdMaterialPost&&path.endsWith('/commands')&&options.method==='POST'){holdMaterialPost=false;delayedPost=true;await new Promise(r=>releasePost=r);}if(x.status===403&&onDenied)onDenied();if(delayNext&&path.endsWith(delayPath)&&(options.method||'GET')===delayMethod){delayNext=false;delayedResponse=true;await new Promise(r=>releaseDelayed=r);}if(x.lost)throw Error('SYNTHETIC actual committed reply lost');return {status:x.status,ok:x.status>=200&&x.status<300,json:async()=>x.body};}
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
 const prep=process.argv[2],actor=process.argv[3],mode=process.argv[4];let p=page('src/parkweave/web.html');p.get('token').value='SYNTHETIC_'+actor;
 await p.read('loadServiceCasePlan('+JSON.stringify(prep)+')');
 await p.get('plan-candidate-generate').onclick();
 const originalPost=calls.find(c=>c.options.method==='POST');check(!!originalPost);
 const originalKey=originalPost.options.headers['Idempotency-Key'];
 const handleName=p.storageKeys().find(n=>n.startsWith('parkweave.plan-candidate-original-key'));
 check(!!handleName);const handleRaw=p.snapshot()[handleName];
 check(Object.keys(JSON.parse(handleRaw)).sort().join(',')==='actor,case,id,key,run,v');
 check(p.read('planCandidateView')===null);check(p.read('entryWriteRequests.size')===0);
 const initialPosts=calls.filter(c=>c.options.method==='POST').length;check(initialPosts===1);
 if(mode!=='failed_same'){
  p=page('src/parkweave/web.html','',p.snapshot());p.get('token').value='SYNTHETIC_'+actor;
  await p.read('loadServiceCasePlan('+JSON.stringify(prep)+')');
  check(p.snapshot()[handleName]===handleRaw);
  check(calls.filter(c=>c.options.method==='POST').length===initialPosts);
 }
 if(mode==='revoke_read'){
  console.log(JSON.stringify({revoke_read:true}));await new Promise(r=>replies.push(r));
 }
 if(mode==='backend_bad_outcome'){
  console.log(JSON.stringify({corrupt_outcome_state:true}));await new Promise(r=>replies.push(r));
 }
 await p.get('plan-candidate-recover').onclick();
 check(calls.filter(c=>c.options.method==='POST').length===initialPosts);
 check(calls.filter(c=>c.path.endsWith('/service-plan-candidates/recovery')).every(c=>c.options.method==='GET'&&c.options.headers['Idempotency-Key']===originalKey));
 if(mode.startsWith('failed_')){
  check(p.storageKeys().filter(n=>n.startsWith('parkweave.plan-candidate-original-key')).length===0);
  check(p.read('entryWriteRequests.size')===0);check(p.read('activeEntryWriteFlow')===null);
  check(p.get('plan-candidate-generate').disabled===false);
  const before=calls.filter(c=>c.options.method==='POST').length;
  await p.get('plan-candidate-generate').onclick();
  check(calls.filter(c=>c.options.method==='POST').length===before+1);
  const newer=calls.filter(c=>c.options.method==='POST').at(-1);
  check(newer.options.headers['Idempotency-Key']!==originalKey);
  check(!!p.read('planCandidateView.candidate_id'));
  check(p.read('entryWriteRequests.size')===0);
  check(p.storageKeys().filter(n=>n.startsWith('parkweave.plan-candidate-original-key')).length===0);
 }else{
  check(p.snapshot()[handleName]===handleRaw);
  if(mode==='revoke_read'){
   check(p.read('servicePlanView')===null);check(p.read('planCandidateView')===null);
   check(p.get('plan-candidate-result').children.length===0);
  }else{
   check(p.get('plan-candidate-generate').disabled===true);
   await p.get('plan-candidate-generate').onclick();
   check(calls.filter(c=>c.options.method==='POST').length===initialPosts);
   check(p.snapshot()[handleName]===handleRaw);
   await p.get('plan-candidate-recover').onclick();
   check(calls.filter(c=>c.options.method==='POST').length===initialPosts);
   check(p.snapshot()[handleName]===handleRaw);
  }
 }
 console.log(JSON.stringify({result:'PASS',mode,checks,http:calls.length,posts:calls.filter(c=>c.options.method==='POST').length,cold:mode!=='failed_same',exactOriginalKeyOnly:true}));process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1);});
