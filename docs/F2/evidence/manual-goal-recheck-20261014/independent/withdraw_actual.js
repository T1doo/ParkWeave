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
let delayedResponse=false,releaseDelayed=null,delayNext=false,delayedPost=false,releasePost=null;
const lines=require('readline').createInterface({input:process.stdin}),replies=[],calls=[];
lines.on('line',line=>{replies.shift()?.(JSON.parse(line));});
async function fetchAPI(path,options={}){calls.push({path,options});const response=new Promise(resolve=>replies.push(resolve));console.log(JSON.stringify({request:{path,options}}));const x=await response;if(delayNext&&path.endsWith('/manual-goal-requests')&&(!options.method||options.method==='GET')){delayNext=false;delayedResponse=true;await new Promise(r=>releaseDelayed=r);}if(x.lost){delayedPost=true;}if(x.lost)throw Error('SYNTHETIC actual committed reply lost');return {status:x.status,ok:x.status>=200&&x.status<300,json:async()=>x.body};}
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
 const reviewer=process.argv[2],owner=process.argv[3],pid=process.argv[4],oldKey=process.argv[5];
 const init=(actor,seed={})=>{const p=page('src/parkweave/web.html','',seed);p.get('token').value='SYNTHETIC_'+actor;p.get('manual-goal-id').value=pid;return p};
 const p=init(owner);await p.get('manual-goal-read').onclick();check(p.read('mgView.items[0].state')==='RECHECK_REQUESTED');p.get('manual-goal-action').value='WITHDRAW';p.get('manual-goal-action').onchange();p.get('manual-goal-reason').value='SYNTHETIC owner explicitly withdraws only human recheck';p.get('manual-goal-purpose').checked=true;await p.get('manual-goal-form').onsubmit({preventDefault(){}});check(p.read('mgView.items[0].state')==='WITHDRAWN');check(p.read('mgHandles().length')===0);
 const name='parkweave.manual-goal-original-key.v1.'+owner+'.'+oldKey,seed={[name]:JSON.stringify({actor:owner,id:pid,key:oldKey})};const cold=init(owner,seed);await cold.get('manual-goal-recover').onclick();check(cold.read('mgView.items[0].state')==='WITHDRAWN');check(cold.read('mgHandles().length')===0);check(cold.read('mgView.items[0].allowed_actions.length')===0);
 for(const actor of [owner,reviewer]){const current=init(actor);await current.get('prep-tasks').onclick();check(!current.get('prep-task-items').children.some(c=>c.dataset.taskKind?.startsWith('MANUAL_')));await current.get('manual-goal-read').onclick();check(current.read('mgView.items[0].state')==='WITHDRAWN');check(current.read('mgView.items[0].allowed_actions.length')===0);check(current.read('mgView.overall_goal_state')==='PARTIAL');check(current.read('mgView.case_goal_completed')===false);}
 check(calls.filter(c=>c.options.method==='POST').length===1);check(calls.filter(c=>c.options.method==='POST').every(c=>JSON.parse(c.options.body).action==='WITHDRAW'));check(!calls.some(c=>c.path.includes('case-cancellation')));
 console.log(JSON.stringify({result:'PASS',checks,http:calls.length,posts:1,scope:'FULL_ORIGINAL_HTML_ASGI_OWNED_PG_EXPLICIT_HUMAN_RECHECK_WITHDRAWAL_NOT_CASE_CANCEL'}));process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1)});
