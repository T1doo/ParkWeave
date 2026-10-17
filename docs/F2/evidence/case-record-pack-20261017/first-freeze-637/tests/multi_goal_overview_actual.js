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
 const caseId=process.argv[2],actor=process.argv[3],A=process.argv[4],B=process.argv[5],mode=process.argv[6]||'exact',p=page('src/parkweave/web.html');p.get('token').value='SYNTHETIC_'+actor;
 async function load(){await p.read('loadServiceCasePlan('+JSON.stringify(caseId)+')');await p.get('goal-results-read').onclick();}
 function button(goal){const card=p.get('goal-results-items').children.find(c=>c.dataset.goalName===goal);return card?.children.find(c=>c.dataset.goalOpen===goal||c.tagName==='button');}
 await load();check(p.read('goalResultView.results.length')===(['dispatch','localcase','receipt_blocked'].includes(mode)?7:['resource','late_resource'].includes(mode)?4:3));let open=button(mode==='dispatch'?'LOCAL_INTERNAL_ACCEPTANCE':mode==='localcase'?'LOCAL_CASE_RECORD_RECHECK':mode==='receipt_blocked'?'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT':['resource','late_resource'].includes(mode)?'LOCAL_CASE_RESOURCE_ASSOCIATION':mode==='supported'||mode==='late_aux'||(mode.startsWith('support_deny')||mode==='support_field_denied')?'LOCAL_MATERIAL_PREPARATION':B);check(!!open);
 if(mode.includes('deny')||mode==='support_field_denied'){
  const opaqueName='parkweave.manual-goal-original-key.v1.'+actor+'.'+id(888),opaque=JSON.stringify({actor,id:caseId,key:id(888)});
  onDenied=()=>p.read('localStorage.setItem('+JSON.stringify(opaqueName)+','+JSON.stringify(opaque)+')');
  delayPath=(mode.startsWith('support_deny')||mode==='support_field_denied')?(mode.includes('fact')||mode==='support_field_denied'?'/fact-clarifications':mode.includes('aux')?'/readiness':'/api/preparations/'+caseId):'/manual-goal-requests';
  const late=mode.includes('late');delayNext=late;const pending=open.onclick();
  if(late){await waitFor(()=>delayedResponse);console.log(JSON.stringify({restore_and_new_case:mode.includes('newcase'),restore:!mode.includes('newcase')}));const reply=await new Promise(r=>replies.push(r));
   if(mode.includes('identity')){p.get('token').value='SYNTHETIC_'+reply.actor;p.get('token').trigger('input');p.get('manual-goal-id').value=caseId;await p.read('mgRead()');check(p.read('mgView.actor_id')===reply.actor);}
   else{if(reply.preparation_id){p.get('service-plan-id').value=reply.preparation_id;await p.read('loadServiceCasePlan('+JSON.stringify(reply.preparation_id)+')');await p.get('goal-results-read').onclick();}else await p.get('goal-results-read').onclick();}
   p.get('manual-goal-reason').value='SYNTHETIC new authorized draft';const plan=p.read('servicePlanView'),goal=p.read('goalResultView'),manual=p.read('mgView'),n=calls.length,snapshot=JSON.stringify(p.snapshot());releaseDelayed();await pending;
   check(p.read('servicePlanView')===plan);check(p.read('goalResultView')===goal);check(p.read('mgView')===manual);check(calls.length===n);check(p.get('manual-goal-reason').value==='SYNTHETIC new authorized draft');check(JSON.stringify(p.snapshot())===snapshot);
  }else if(mode==='support_field_denied'){await pending;check(p.read('goalResultView')!==null);check(p.read('servicePlanView')!==null);check(p.read('preparationView')!==null);check(p.read('caseFactView')===null);check(calls.some(x=>x.path.endsWith('/case-cancellation')));check(p.get('case-fact-error').textContent.length>0);}else{await pending;if(mode.includes('fact'))check(!calls.some(x=>x.path.endsWith('/case-cancellation')));console.log(JSON.stringify({checkpoint:{goalResultRetained:p.read('goalResultView')!==null,servicePlanRetained:p.read('servicePlanView')!==null,goalCards:p.get('goal-results-items').children.length,stepCards:p.get('service-plan-steps').children.length,manualRetained:p.read('mgView')!==null,opaqueRetained:p.snapshot()[opaqueName]===opaque}}));
   check(p.read('goalResultView')===null);check(p.read('servicePlanView')===null);check(p.get('goal-results-items').children.length===0);check(p.get('service-plan-steps').children.length===0);check(p.read('mgView')===null);check(p.get('manual-goal-form').hidden);check(p.get('goal-results-panel').hidden);check(p.get('service-case-plan-detail').hidden);
  }
  check(p.snapshot()[opaqueName]===opaque);
 }
 else if(mode==='switch_goal'){delayPath='/manual-goal-requests';delayNext=true;const pending=open.onclick();await waitFor(()=>delayedResponse);await button(A).onclick();check(p.get('manual-goal-name').value===A);p.get('manual-goal-reason').value='SYNTHETIC new exact A draft';const n=calls.length;releaseDelayed();await pending;check(calls.length===n);check(p.get('manual-goal-name').value===A);check(p.get('manual-goal-reason').value==='SYNTHETIC new exact A draft');}
 else if(mode==='exact'){await open.onclick();check(p.read('mgView.case_id')===p.read('servicePlanView.case_id'));check(p.get('manual-goal-name').value===B);check(p.get('manual-goal-name').value!==A);}
 else if(mode==='dispatch'){await open.onclick();check(p.read('dispatchView.case_id')===p.read('servicePlanView.case_id'));check(!p.get('dispatch-detail').hidden);}
 else if(mode==='localcase'){await open.onclick();check(p.read('localCaseView.case_id')===p.read('servicePlanView.case_id'));check(!p.get('local-case-detail').hidden);}
 else if(mode==='receipt_blocked'){await open.onclick();check(p.read('receiptView')===null);check(p.get('goal-results-error').textContent.includes('尚无'));}
 else if(mode==='resource'){await open.onclick();check(p.read('caseResourceView.case_id')===p.read('servicePlanView.case_id'));check(!p.get('case-resource-panel').hidden);}
 else if(mode==='supported'){await open.onclick();check(p.read('preparationView.preparation.case_id')===p.read('servicePlanView.case_id'));check(p.get('goal-results-navigation').textContent.includes('材料'));}
 else if(mode==='saved_button'){await p.get('goal-results-read').onclick();const n=calls.length;await open.onclick();check(calls.length===n);}
 else if(mode==='source_switch'||mode==='revoke'){console.log(JSON.stringify({change_source:mode==='source_switch',revoke:mode==='revoke'}));await new Promise(r=>replies.push(r));await open.onclick();check(p.read('mgView')===null);check(p.get('manual-goal-form').hidden);}
 else{
  delayPath=mode==='late_list'?'/goal-results':mode==='late_resource'?'/resource-link-candidates':mode==='late_aux'?'/readiness':'/manual-goal-requests';delayNext=true;const pending=mode==='late_list'?p.get('goal-results-read').onclick():open.onclick();await waitFor(()=>delayedResponse);
  if(mode==='plan_switch'){console.log(JSON.stringify({replace_plan:true}));await new Promise(r=>replies.push(r));await load();}else await p.get('goal-results-read').onclick();
  if(['late_aux','late_resource'].includes(mode)){await button(B).onclick();check(p.get('manual-goal-name').value===B);}
  p.get('manual-goal-reason').value='SYNTHETIC fresh overview draft';const snapshot=JSON.stringify(p.snapshot()),n=calls.length;releaseDelayed();await pending;check(calls.length===n);check(p.get('manual-goal-reason').value==='SYNTHETIC fresh overview draft');check(JSON.stringify(p.snapshot())===snapshot);
  if(['late_aux','late_resource'].includes(mode))check(p.get('manual-goal-name').value===B);else if(mode!=='late_list'){check(p.read('mgView')===null);check(p.get('manual-goal-form').hidden);check(p.read('mgBusy')===false);}
 }
 check(calls.every(x=>!x.options.method||x.options.method==='GET'));
 console.log(JSON.stringify({result:'PASS',checks,http:calls.length,posts:calls.filter(x=>x.options.method==='POST').length,mode}));process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1);});
