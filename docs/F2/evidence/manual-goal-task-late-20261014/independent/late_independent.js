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
async function fetchAPI(path,options={}){calls.push({path,options});const response=new Promise(resolve=>replies.push(resolve));console.log(JSON.stringify({request:{path,options}}));const x=await response;if(delayNext&&path.endsWith('/manual-goal-requests')&&(!options.method||options.method==='GET')){delayNext=false;delayedResponse=true;await new Promise(r=>releaseDelayed=r);}if(x.lost){delayedPost=true;await new Promise(r=>releasePost=r);}if(x.lost)throw Error('SYNTHETIC actual committed reply lost');return {status:x.status,ok:x.status>=200&&x.status<300,json:async()=>x.body};}
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
 const actor=process.argv[2],mode=process.argv[3],p=page('src/parkweave/web.html');p.get('token').value='SYNTHETIC_'+actor;
 const btn=()=>{const card=p.get('prep-task-items').children.find(x=>x.dataset.taskKind==='MANUAL_ACCEPT_REQUEST');return card?.children.find(x=>x.dataset.personalTask)};
 await p.get('prep-tasks').onclick();check(!!btn());p.read('var indRenders=0;const indOriginalRender=mgRender;mgRender=(...a)=>{indRenders++;return indOriginalRender(...a)}');
 delayNext=true;const old=btn().onclick();await waitFor(()=>delayedResponse);
 await p.get('prep-tasks').onclick();check(p.read('mgBusy')===false);check(p.get('manual-goal-read').disabled===false);
 if(mode==='page'){check(!p.get('prep-tasks-next').hidden);await p.get('prep-tasks-next').onclick();check(p.read('mgBusy')===false);}
 if(mode==='newer'){check(!!btn());await btn().onclick();check(p.read('mgView!==null'));}
 p.get('manual-goal-reason').value='SYNTHETIC independent newer draft';p.get('manual-goal-purpose').checked=true;
 p.read('localStorage.setItem(mgStorage+'+JSON.stringify(actor)+'+"."+'+JSON.stringify(id(887))+',JSON.stringify({actor:'+JSON.stringify(actor)+',id:$("manual-goal-id").value,key:'+JSON.stringify(id(887))+'}))');
 const expectedView=p.read('JSON.stringify(mgView)'),renderCount=p.read('indRenders'),keys=JSON.stringify(p.snapshot()),reason=p.get('manual-goal-reason').value,purpose=p.get('manual-goal-purpose').checked,disabled=p.get('manual-goal-submit').disabled,error=p.get('manual-goal-error').textContent;
 releaseDelayed();await old;check(p.read('indRenders')===renderCount);check(p.read('JSON.stringify(mgView)')===expectedView);check(p.get('manual-goal-reason').value===reason);check(p.get('manual-goal-purpose').checked===purpose);check(p.get('manual-goal-submit').disabled===disabled);check(p.get('manual-goal-error').textContent===error);check(JSON.stringify(p.snapshot())===keys);check(p.read('mgBusy')===false);check(calls.every(x=>!x.options.method||x.options.method==='GET'));
 console.log(JSON.stringify({result:'PASS',checks,http:calls.length,posts:0,mode}));process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1)});
