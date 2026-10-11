// Independent actual-source VM probes. No browser, listener or network implementation.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('/workspace/ParkWeave/src/parkweave/web.html','utf8');
const code=html.slice(html.indexOf('let dispatchView=null'),html.indexOf('// Narrow assigned-executor receipts;'));
const mode=process.argv[2],pid='11111111-1111-1111-1111-111111111111',did='22222222-2222-2222-2222-222222222222';
const storageKey='parkweave.pending-receipt-handoff.v1',storage=new Map();let clock=1800000000000;
const handle=()=>({actor:'reviewer-test',dispatch:did,preparation:pid,key:'33333333-3333-3333-3333-333333333333',expires:clock+86400000});
const row={scope:'SYNTHETIC_INTERNAL_DISPATCH_ONLY',role:'park_specialist',preparation_id:pid,dispatch_id:did,preparation_revision:4,revision:2,goal:'SYNTHETIC ORIGINAL',current_offer:{id:'44444444-4444-4444-4444-444444444444',executor_id:'old-party',state:'ACCEPTED',reason:'SYNTHETIC'},dependency:'CURRENT',is_current_offer:true,current_receipt_step_id:'55555555-5555-5555-5555-555555555555',history:[]};
const catalog={preparation_revision:4,dispatch_revision:2,ready:false,can_reassign:true,reassignment_actor_id:'reviewer-test',executors:[{id:'new-party'}],reassignment_executors:[{id:'new-party'}],reassignment_predecessor:{predecessor_offer_id:row.current_offer.id,predecessor_receipt_step_id:row.current_receipt_step_id,predecessor_receipt_revision:1},has_receipt_step:true};
class Node{constructor(){this.children=[];this.elements=[];this.value='';this.hidden=false;this.disabled=false;this.textContent='';this.dataset={};}append(...v){this.children.push(...v);}replaceChildren(...v){this.children=[...v];this.textContent='';}reset(){for(const x of this.elements)x.value='';}scrollIntoView(){}}
function app(){const nodes=new Map(),calls=[],$=id=>{if(!nodes.has(id))nodes.set(id,new Node());return nodes.get(id);};$('token').value='SYNTHETIC_TOKEN_A';$('dispatch-offer').elements=[$('dispatch-executor'),$('dispatch-offer-reason'),$('dispatch-offer-button')];$('dispatch-decision').elements=[$('dispatch-accept'),$('dispatch-decline'),$('dispatch-withdraw')];
 const ctx=vm.createContext({$,Date:{now:()=>clock},crypto:{randomUUID:()=> '66666666-6666-6666-6666-666666666666'},localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},textElement:(t,s)=>Object.assign(new Node(),{textContent:s}),clearLocalCase:()=>{},clearNotices:()=>{},clearReceipts:()=>{},clearPreparation:()=>vm.runInContext('clearDispatch()',ctx),requirePlan:()=>{},requireServicePlan:()=>{},receiptError:()=>{},loadReceipt:()=>{throw Error('forbidden automatic receipt navigation');},fetch:(path,options)=>new Promise((resolve,reject)=>calls.push({path,options,resolve,reject}))});
 vm.runInContext(code,ctx);const run=s=>vm.runInContext(s,ctx);
 function render(goal='SYNTHETIC ORIGINAL',actor='reviewer-test'){ctx.row=structuredClone({...row,goal});ctx.catalog=structuredClone({...catalog,reassignment_actor_id:actor});run('dispatchPreparationId=row.preparation_id;dispatchId=row.dispatch_id;renderDispatch(row,catalog)');$('dispatch-executor').value='new-party';$('dispatch-offer-reason').value='SYNTHETIC explicit private reason';}
 function response(i,status,body){calls[i].resolve({ok:status<400,status,json:async()=>body});}
 return {$,ctx,calls,run,render,response};}
const tick=()=>new Promise(r=>setImmediate(r));
function committed(h){return {scope:row.scope,dispatch_id:h.dispatch,preparation_id:h.preparation,request_key:h.key,status:'COMMITTED',historical_only:true,automatically_replayed:false,event:{dispatch_id:h.dispatch,actor_id:h.actor,handoff_kind:'PENDING_MANUAL_RECEIPT',action:'REOFFER'}};}
function unknown(h){return {...committed(h),status:'NOT_OBSERVED',event:null};}
(async()=>{let a=app(),checks=0;const check=v=>{assert(v);checks++;};
 if(mode.startsWith('malicious_')){
  let raw;
  if(mode==='malicious_json')raw='{';
  if(mode==='malicious_object')raw='{}';
  if(mode==='malicious_extra'){const h={...handle(),reason:'SYNTHETIC_PRIVATE_TEXT'};raw=JSON.stringify([h]);}
  if(mode==='malicious_actor_type')raw=JSON.stringify([{...handle(),actor:1}]);
  if(mode==='malicious_future')raw=JSON.stringify([{...handle(),expires:clock+86400001}]);
  if(mode==='malicious_nine')raw=JSON.stringify(Array.from({length:9},()=>handle()));
  storage.set(storageKey,raw);let denied=false;try{a.render();}catch{denied=true;}check(denied);check(a.calls.length===0);check(storage.get(storageKey)===raw);
 }else if(mode==='eight_absolute_capacity'){
  storage.set(storageKey,JSON.stringify(Array.from({length:8},(_,i)=>({...handle(),dispatch:'22222222-2222-2222-2222-'+String(i).padStart(12,'0')}))));a.render();await a.run("dispatchWrite('OFFER').catch(dispatchError)");check(a.calls.length===0);check(JSON.parse(storage.get(storageKey)).length===8);check(a.$('dispatch-error').textContent.includes('上限'));
 }else if(mode==='expiry_absolute_no_renew'){
  const h=handle();storage.set(storageKey,JSON.stringify([h]));a.render();clock+=10000;const p=a.run('recoverHandoff().catch(dispatchError)');check(a.calls.length===1);a.response(0,200,unknown(h));await p;
  check(JSON.parse(storage.get(storageKey))[0].expires===h.expires);check(a.$('dispatch-offer-button').disabled);clock=h.expires;check(a.run('handoffHandles().length')===0);check(!storage.has(storageKey));check(a.calls.length===1);
 }else if(mode==='late_recovery_json_identity_aba'||mode==='late_recovery_403_identity_aba'){
  const h=handle();storage.set(storageKey,JSON.stringify([h]));a.render();const p=a.run('recoverHandoff().catch(dispatchError)');let body;
  a.calls[0].resolve({ok:mode==='late_recovery_json_identity_aba',status:mode==='late_recovery_json_identity_aba'?200:403,json:()=>new Promise(r=>body=r)});await tick();
  a.run('clearDispatch()');a.$('token').value='SYNTHETIC_TOKEN_B';a.render('SYNTHETIC B','reviewer-other');a.run('clearDispatch()');a.$('token').value='SYNTHETIC_TOKEN_A';a.render('SYNTHETIC NEWEST A');body(committed(h));await p;
  check(a.$('dispatch-summary').textContent.includes('NEWEST A'));check(a.$('dispatch-error').textContent==='');check(storage.has(storageKey));check(a.$('dispatch-offer-button').disabled);check(a.calls.length===1);
 }else if(mode.startsWith('wrong_proof_')){
  const h=handle();storage.set(storageKey,JSON.stringify([h]));a.render();const p=a.run('recoverHandoff().catch(dispatchError)'),x=committed(h),field=mode.slice('wrong_proof_'.length);
  if(field==='event_actor')x.event.actor_id='other';else if(field==='event_dispatch')x.event.dispatch_id=pid;else if(field==='scope')x.scope='OTHER';else if(field==='key')x.request_key='other';
  a.response(0,200,x);await p;check(storage.has(storageKey));check(a.$('dispatch-offer-button').disabled);check(a.calls.length===1);check(a.$('dispatch-error').textContent.includes('证明'));
 }else if(mode==='storage_changed_during_recovery'){
  const h=handle();storage.set(storageKey,JSON.stringify([h]));a.render();const p=a.run('recoverHandoff().catch(dispatchError)');storage.set(storageKey,JSON.stringify([{...h,key:'77777777-7777-7777-7777-777777777777'}]));a.response(0,200,committed(h));await p;
  check(storage.has(storageKey));check(a.$('dispatch-offer-button').disabled);check(a.calls.length===1);check(a.$('dispatch-error').textContent.includes('句柄'));
 }else throw Error('unknown probe mode');
 for(const c of a.calls){check(c.options.method==='GET');check(c.options.body===undefined);check(c.options.cache==='no-store');check(c.path.includes('/reassignment-recovery/'));}
 console.log(JSON.stringify({mode,checks,scope:'NEW_ACTUAL_JS_VM_STORAGE_DOM_FETCH_DOUBLES'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
