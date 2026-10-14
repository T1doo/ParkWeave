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



async function start(seed={},n=0){
 const t=page('src/parkweave/template_candidate_web.html','',seed);await waitFor(()=>t.read('status!==null'));t.get('consumer-token').value='SYNTHETIC_'+process.argv[3];await t.get('consumer-catalog').onclick();
 t.get('consumer-release').value=t.get('consumer-release').options[0].value;t.get('consumer-release').onchange();t.get('consumer-reviewer').value=t.get('consumer-reviewer').options[0].value;
 for(const [id,value] of Object.entries({'consumer-goal':'SYNTHETIC independent goal '+n,'consumer-need-summary':'SYNTHETIC need '+n,'consumer-need-source':'SYNTHETIC user','consumer-material-outline':'SYNTHETIC outline '+n,'consumer-outline-source':'SYNTHETIC document'}))t.get(id).value=value;
 const goal=nested(t.get('consumer-goals'),x=>x.dataset.consumerGoal==='SYNTHETIC_EXTERNAL_AUTHORITY_APPROVAL');goal.checked=true;goal.onchange();
 await t.get('consumer-create').onclick();await t.get('consumer-resume').onclick();await confirm(t);return t;
}
async function confirm(t){await t.get('consumer-preview').onclick();await t.get('consumer-confirm').onclick();t.get('consumer-plan-reason').value='SYNTHETIC exact explicit partial adoption';t.get('consumer-partial-confirm').checked=true;t.get('consumer-partial-confirm').onchange();}
async function cold(seed,id){const p=page('src/parkweave/template_candidate_web.html','',seed);await waitFor(()=>p.read('status!==null'));p.get('consumer-token').value='SYNTHETIC_'+process.argv[3];p.get('consumer-instance-id').value=id;await p.get('consumer-read').onclick();return p;}
const count=p=>p.storageKeys().filter(x=>x.startsWith('parkweave.template-adoption-recovery')).length;
const adopts=()=>calls.filter(x=>x.options.method==='POST'&&x.path.endsWith('/adopt')).length;
(async()=>{
 let seed={},rows=[];
 for(let n=0;n<8;n++){const t=await start(seed,n);await t.get('consumer-adopt').onclick();check(adopts()===n+1);check(count(t)===n+1);rows.push(t.read('instance.instance_id'));seed=t.snapshot();}
 const ninth=await start(seed,9),id=ninth.read('instance.instance_id');await ninth.get('consumer-adopt').onclick();check(adopts()===8);check(count(ninth)===8);check(ninth.get('consumer-error').textContent.includes('句柄'));
 const p=await cold(ninth.snapshot(),rows[0]);await p.get('consumer-adoption-recover').onclick();check(p.read('adoptionVerified.status')==='COMMITTED');check(count(p)===8);
 p.get('consumer-finalize-reason').value='SYNTHETIC explicitly close first original key';await p.get('consumer-adoption-finalize').onclick();check(p.read('adoptionFinalizeUnknown')===true);check(count(p)===8);check(p.read('adoptionHandle.finishPending')===true);
 const old=p.snapshot(),q=await cold(old,rows[0]);check(q.read('adoptionFinalizeUnknown')===true);check(q.get('consumer-adoption-finalize').disabled);await q.get('consumer-adoption-recover').onclick();check(count(q)===7);check(q.read('adoptionHandle')===null);check(!q.get('product-link').hidden);
 const removed=Object.keys(old).filter(k=>!(k in q.snapshot()));check(removed.length===1);check(removed[0].includes(rows[0]));check(q.get('consumer-adoption-handles').children.length===7);
 const retry=await cold(q.snapshot(),id);await confirm(retry);await retry.get('consumer-adopt').onclick();check(adopts()===9);check(retry.read('instance.state')==='PLAN_ADOPTED');check(count(retry)===8);
 const one=await cold(retry.snapshot(),rows[1]);await one.get('consumer-adoption-recover').onclick();one.get('consumer-finalize-reason').value='SYNTHETIC individually close second successful original';await one.get('consumer-adoption-finalize').onclick();check(count(one)===7);check(one.read('adoptionHandle')===null);
 check(calls.filter(x=>x.options.method==='POST'&&x.path.endsWith('/planning-finalization')).length===2);
 console.log(JSON.stringify({mode:'template_terminal_actual_capacity',checks,http:calls.length,adopts:adopts(),cases:9,remaining_handles:count(one),finalizes:2,scope:'ORIGINAL_TEMPLATE_HTML_ASGI_OWNED_PG_8_REAL_KEYS_NINTH_BLOCKED_EXPLICIT_FINALIZE_LOST_RESPONSE_COLD_GET_SINGLE_DELETE_NINTH_ADOPT'}));process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1);});
