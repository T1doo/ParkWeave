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
 const reviewer=process.argv[2],owner=process.argv[3],caseId=process.argv[4],mode=process.argv[5];
 function init(actor,seed={}){const p=page('src/parkweave/web.html','',seed);p.get('token').value='SYNTHETIC_'+actor;p.get('manual-goal-id').value=caseId;return p;}
 async function explicit(p,action){p.get('manual-goal-action').value=action;p.get('manual-goal-action').onchange();p.get('manual-goal-reason').value='SYNTHETIC explicit '+action;p.get('manual-goal-purpose').checked=true;if(['REQUEST_RECHECK','TAKE_RECHECK'].includes(action)){const n=calls.length;await p.get('manual-goal-form').onsubmit({preventDefault(){}});check(calls.length===n);p.get('manual-goal-recheck-confirm').checked=true;p.get('manual-goal-recheck-confirm').onchange();}if(action==='REPLY'){p.get('manual-goal-reply-kind').value='INFORMATION';for(const e of p.get('manual-goal-materials').querySelectorAll('input[data-manual-material]'))e.checked=true;}if(action==='ACKNOWLEDGE_REPLY'){p.get('manual-goal-reply-confirm').checked=true;p.get('manual-goal-reply-confirm').onchange();}await p.get('manual-goal-form').onsubmit({preventDefault(){}});}
 let o=init(owner);await o.get('manual-goal-read').onclick();const oldReply=o.read('mgView.items[0].reply.id');check(o.read('mgView.items[0].state')===(mode==='ended'?'COORDINATION_ENDED':'WAITING_OWNER_ACKNOWLEDGEMENT'));await explicit(o,'REQUEST_RECHECK');
 if(mode==='lost_request'){check(o.read('mgHandles().length')===1);o=init(owner,o.snapshot());await o.get('manual-goal-recover').onclick();check(o.read('mgHandles().length')===0);}
 check(o.read('mgView.items[0].state')==='RECHECK_REQUESTED');check(o.read('mgView.items[0].responsible_actor_id')===null);check(!o.read('mgView.items[0].allowed_actions.includes("REPLY")'));
 let p=init(reviewer);await p.get('prep-tasks').onclick();const card=p.get('prep-task-items').children.find(x=>x.dataset.taskKind==='MANUAL_ACCEPT_RECHECK');check(!!card);const open=card.children.find(x=>x.dataset.personalTask);
 if(mode==='late'){delayNext=true;const pending=open.onclick();await waitFor(()=>delayedResponse);await p.get('prep-tasks').onclick();p.get('manual-goal-reason').value='SYNTHETIC new recheck draft';releaseDelayed();await pending;check(p.read('mgView')===null);check(p.get('manual-goal-form').hidden);check(p.get('manual-goal-reason').value==='SYNTHETIC new recheck draft');}
 else{await open.onclick();check(p.get('manual-goal-recheck-binding').textContent.includes(p.read('mgView.items[0].recheck.fingerprint')));
  if(mode==='cancel'){console.log(JSON.stringify({cancel_case:true}));await new Promise(r=>replies.push(r));await p.get('manual-goal-read').onclick();check(p.read('mgView.items[0].allowed_actions.length')===0);check(p.read('mgView.items[0].state')==='RECHECK_REQUESTED');}
  else{await explicit(p,'TAKE_RECHECK');if(mode==='lost_take'){check(p.read('mgHandles().length')===1);p=init(reviewer,p.snapshot());await p.get('manual-goal-recover').onclick();check(p.read('mgHandles().length')===0);}check(p.read('mgView.items[0].state')==='UNDER_MANUAL_RECHECK');check(p.read('mgView.items[0].responsible_actor_id')===reviewer);await explicit(p,'REPLY');check(p.read('mgView.items[0].reply.id')!==oldReply);const latest=init(owner);await latest.get('manual-goal-read').onclick();await explicit(latest,'ACKNOWLEDGE_REPLY');check(latest.read('mgView.items[0].state')==='COORDINATION_ENDED');await latest.get('prep-tasks').onclick();check(!latest.get('prep-task-items').children.some(x=>x.dataset.taskKind?.startsWith('MANUAL_')));}
 }
 const final=init(owner);await final.get('manual-goal-read').onclick();check(final.read('mgView.overall_goal_state')==='PARTIAL');check(final.read('mgView.case_goal_completed')===false);check(final.read('mgView.items[0].goal_state')==='UNSUPPORTED');check(final.read('mgView.new_grants')===false);
 console.log(JSON.stringify({result:'PASS',checks,http:calls.length,posts:calls.filter(x=>x.options.method==='POST').length,mode}));process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1);});
