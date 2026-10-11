// Actual dispatch/handoff code in Node VM. No browser, listener or external fetch.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/parkweave/web.html','utf8');
const actual=source.slice(source.indexOf('let dispatchView=null'),source.indexOf('// Narrow assigned-executor receipts;'));
const mode=process.argv[2],pid='10000000-0000-0000-0000-000000000001',did='20000000-0000-0000-0000-000000000001',oid='30000000-0000-0000-0000-000000000001',sid='40000000-0000-0000-0000-000000000001';
const root={scope:'SYNTHETIC_INTERNAL_DISPATCH_ONLY',role:'park_specialist',preparation_id:pid,dispatch_id:did,preparation_revision:4,revision:2,goal:'SYNTHETIC pending work',current_offer:{id:oid,executor_id:'executor-a',state:'ACCEPTED',reason:'SYNTHETIC original'},dependency:'CURRENT',is_current_offer:true,current_receipt_step_id:sid,history:[]};
const cat={preparation_revision:4,dispatch_revision:2,ready:false,can_reassign:true,reassignment_actor_id:'reviewer-a',executors:[{id:'executor-a'},{id:'executor-new'}],reassignment_executors:[{id:'executor-new'}],reassignment_predecessor:{handoff_kind:'PENDING_MANUAL_RECEIPT',predecessor_offer_id:oid,predecessor_receipt_step_id:sid,predecessor_receipt_revision:1},has_receipt_step:true};
class Element{constructor(){this.children=[];this.value='';this.hidden=false;this.disabled=false;this.textContent='';this.dataset={};this.elements=[];}append(...v){this.children.push(...v);if(!this.value&&v[0]?.value)this.value=v[0].value;}replaceChildren(...v){this.children=[...v];}reset(){for(const x of this.elements)x.value='';}scrollIntoView(){}}
const storage=new Map();let throwStorage=false;
function app(){const nodes=new Map(),calls=[];const $=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};$('token').value='PRIVATE_TOKEN_A';$('dispatch-offer').elements=[$('dispatch-executor'),$('dispatch-offer-reason'),$('dispatch-offer-button')];$('dispatch-decision').elements=[$('dispatch-decision-reason'),$('dispatch-accept'),$('dispatch-decline'),$('dispatch-withdraw')];
const context=vm.createContext({$,console,crypto:{randomUUID:()=> '50000000-0000-0000-0000-000000000001'},localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>{if(throwStorage)throw Error('storage unavailable');storage.set(k,v);},removeItem:k=>storage.delete(k)},textElement:(tag,text)=>{const e=new Element();e.textContent=text;return e;},clearNotices:()=>{},clearLocalCase:()=>{},clearReceipts:()=>{},clearPreparation:()=>vm.runInContext('clearDispatch()',context),requirePlan:()=>{},requireServicePlan:()=>{},receiptError:()=>{},loadReceipt:()=>{throw Error('automatic receipt navigation');},fetch:(path,options)=>new Promise((resolve,reject)=>calls.push({path,options,resolve,reject}))});
vm.runInContext(actual,context);const evalCode=code=>vm.runInContext(code,context);function render(x=root,c=cat){context.x=structuredClone(x);context.catalog=structuredClone(c);evalCode('dispatchPreparationId=x.preparation_id;dispatchId=x.dispatch_id;renderDispatch(x,catalog)');$('dispatch-executor').value='executor-new';$('dispatch-offer-reason').value='PRIVATE_REASON explicit replacement';}
function finish(i,status,json){calls[i].resolve({ok:status<400,status,json:async()=>json});}
return {$,calls,context,evalCode,render,finish};}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function committed(){const h=JSON.parse([...storage.values()][0])[0];return {scope:root.scope,dispatch_id:did,preparation_id:pid,request_key:h.key,status:'COMMITTED',historical_only:true,automatically_replayed:false,event:{dispatch_id:did,actor_id:h.actor,handoff_kind:'PENDING_MANUAL_RECEIPT',action:'REOFFER'}};}
(async()=>{let a=app();a.render();let checks=0;const check=(value)=>{assert(value);checks++;};
if(mode==='explicit_success'){
 const p=a.evalCode("dispatchWrite('OFFER')");check(a.calls.length===1&&a.calls[0].path.endsWith('/reassign'));
 const body=JSON.parse(a.calls[0].options.body);check(body.executor_id==='executor-new'&&body.reason==='PRIVATE_REASON explicit replacement'&&body.predecessor_receipt_step_id===sid&&body.expected_receipt_revision===1);
 const raw=[...storage.values()][0];check(!raw.includes('PRIVATE_REASON')&&!raw.includes('PRIVATE_TOKEN')&&!raw.includes('executor-new')&&!raw.includes(sid));
 a.finish(0,201,{});await tick();check(a.calls[1].options.method==='GET'&&a.calls[1].path.includes('/reassignment-recovery/'));
 a.finish(1,200,committed());await tick();check(storage.size===0);a.finish(2,200,{...root,revision:3,current_offer:{id:'60000000-0000-0000-0000-000000000001',executor_id:'executor-new',state:'OFFERED',reason:'PRIVATE_REASON'},current_receipt_step_id:null});await tick();a.finish(3,200,{...cat,dispatch_revision:3,can_reassign:false,reassignment_predecessor:null});await p;
 check(a.$('dispatch-offer').hidden&&a.$('dispatch-receipt').hidden);check(a.calls.filter(x=>x.options.method==='POST').length===1);
}else if(mode==='lost_response_cold_get_only'){
 const p=a.evalCode("dispatchWrite('OFFER').catch(dispatchError)");a.calls[0].reject(Error('lost response'));await p;check(storage.size===1&&a.$('dispatch-handoff-recover').hidden===false);
 a=app();a.render();const r=a.evalCode('recoverHandoff().catch(dispatchError)');check(a.calls.length===1&&a.calls[0].options.method==='GET');const h=JSON.parse([...storage.values()][0])[0];a.finish(0,200,{scope:root.scope,dispatch_id:did,preparation_id:pid,request_key:h.key,status:'NOT_OBSERVED',event:null,historical_only:true,automatically_replayed:false});await r;
 await a.evalCode("dispatchWrite('OFFER').catch(dispatchError)");check(a.calls.length===1&&storage.size===1&&a.$('dispatch-offer-button').disabled);check(a.$('dispatch-handoff-status').textContent.includes('未知'));
}else if(mode==='storage_failure'){
 throwStorage=true;await a.evalCode("dispatchWrite('OFFER').catch(dispatchError)");check(a.calls.length===0&&storage.size===0);check(a.$('dispatch-error').textContent.includes('无法保存'));
}else if(mode==='duplicate_click'){
 const first=a.evalCode("dispatchWrite('OFFER').catch(dispatchError)");await a.evalCode("dispatchWrite('OFFER').catch(dispatchError)");check(a.calls.length===1);check(a.$('dispatch-offer-button').disabled);a.calls[0].reject(Error('lost'));await first;check(storage.size===1);
}else if(mode==='identity_aba_delayed_json'){
 const first=a.evalCode("dispatchWrite('OFFER').catch(dispatchError)");let resolveBody;a.calls[0].resolve({ok:true,status:201,json:()=>new Promise(r=>resolveBody=r)});await tick();a.evalCode('clearDispatch()');a.$('token').value='PRIVATE_TOKEN_B';a.render({...root,goal:'SYNTHETIC B'},{...cat,reassignment_actor_id:'reviewer-b'});a.evalCode('clearDispatch()');a.$('token').value='PRIVATE_TOKEN_A';a.render({...root,goal:'SYNTHETIC newest A'});resolveBody({});await first;
 check(a.calls.length===1&&storage.size===1);check(a.$('dispatch-summary').textContent.includes('newest A'));check(a.$('dispatch-offer-button').disabled);
}else if(mode==='late_403_new_identity'){
 const first=a.evalCode("dispatchWrite('OFFER').catch(dispatchError)");a.evalCode('clearDispatch()');a.$('token').value='PRIVATE_TOKEN_B';a.render({...root,goal:'SYNTHETIC B'},{...cat,reassignment_actor_id:'reviewer-b'});a.finish(0,403,{});await first;
 check(a.$('dispatch-summary').textContent.includes('SYNTHETIC B'));check(!a.$('dispatch-detail').hidden&&a.$('dispatch-error').textContent==='');check(storage.size===1&&a.calls.length===1);
}else if(mode==='wrong_recovery_proof'){
 const first=a.evalCode("dispatchWrite('OFFER').catch(dispatchError)");a.finish(0,201,{});await tick();const x=committed();x.event.actor_id='someone-else';a.finish(1,200,x);await first;check(storage.size===1&&a.calls.length===2);check(a.$('dispatch-offer-button').disabled);check(a.$('dispatch-error').textContent.includes('证明'));
}else if(mode==='bounded_handles'){
 const h={actor:'reviewer-a',dispatch:did,preparation:pid,key:'50000000-0000-0000-0000-000000000001',expires:Date.now()+3600000};storage.set('parkweave.pending-receipt-handoff.v1',JSON.stringify(Array.from({length:8},(_,i)=>({...h,dispatch:'20000000-0000-0000-0000-'+String(i+10).padStart(12,'0')}))));a.render();await a.evalCode("dispatchWrite('OFFER').catch(dispatchError)");check(a.calls.length===0);check(JSON.parse([...storage.values()][0]).length===8);
}else if(mode==='current_recovery_403_keeps_original_handle'){
 const first=a.evalCode("dispatchWrite('OFFER').catch(dispatchError)");a.finish(0,201,{});await tick();a.finish(1,403,{});await first;check(a.$('dispatch-detail').hidden&&storage.size===1);check(a.calls.length===2);a.render();check(a.$('dispatch-handoff-recover').hidden===false&&a.$('dispatch-offer-button').disabled);
}else throw Error('unknown mode');
for(const call of a.calls){check(!call.path.endsWith('/commands')&&!call.path.includes('/executor-receipts'));if(call.options.method==='GET')check(call.options.body===undefined);}
console.log(JSON.stringify({mode,checks,scope:'NODE_VM_WITH_DOM_FETCH_STORAGE_DOUBLES_ONLY'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
