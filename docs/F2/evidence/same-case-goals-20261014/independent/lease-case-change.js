// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let nextRequestKey=99;const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.style={};this.listeners={};}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 prepend(...x){this.children.unshift(...x);}reset(){}addEventListener(n,f){(this.listeners[n]??=[]).push(f);}trigger(n){for(const f of this.listeners[n]||[])f({target:this});}setAttribute(){}removeAttribute(name){delete this[name];}
 closest(){return null;}querySelectorAll(selector){const out=[];function visit(e){for(const c of e.children){if(selector==='select[data-fact-field]'&&c.dataset.factField)out.push(c);visit(c);}}visit(this);return out;}scrollIntoView(){this.scrolled=true;}
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
const p=page('src/parkweave/web.html');p.get('token').value='SYNTHETIC original actor';p.get('manual-goal-id').value=id(1);
p.read("mgView={actor_id:'actor-a',preparation_id:document.getElementById('manual-goal-id').value,plan_id:'00000000-0000-4000-8000-000000000003',revision:0,source_sha256:'a'.repeat(64),items:[{goal:'UNSUPPORTED_GOAL',allowed_actions:['REQUEST']}],materials:[]};fetch=()=>new Promise((resolve,reject)=>{globalThis.rejectPost=reject;});");
p.get('manual-goal-name').value='UNSUPPORTED_GOAL';p.get('manual-goal-action').value='REQUEST';p.get('manual-goal-reason').value='SYNTHETIC reason';p.get('manual-goal-purpose').checked=true;
const run=p.read('manualGoalWrite()');await new Promise(r=>setImmediate(r));p.get('manual-goal-id').value=id(2);p.get('manual-goal-id').trigger('input');p.read("rejectPost(Error('SYNTHETIC dropped response')); ");await run;
const result={pending_handles:p.read('mgHandles().length'),entry_requests:p.read('entryWriteRequests.size'),recover_button_allowed:p.read("entryReadAllowed('manual-goal-recover')")};console.log(JSON.stringify(result));assert.equal(result.pending_handles,1);assert.equal(result.recover_button_allowed,true,'original GET recovery must remain reachable after Case input invalidates a dropped response');process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1)});
