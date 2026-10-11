// Actual owner cancellation UI in an offline NodeVM; browser never started.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('src/parkweave/web.html','utf8'),code=html.slice(html.indexOf('// Case cancellation: opaque'),html.indexOf('// Internal offers share'));
const mode=process.argv[2],id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',cid='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',key='cccccccc-cccc-4ccc-8ccc-cccccccccccc',rid='dddddddd-dddd-4ddd-8ddd-dddddddddddd',scope='SYNTHETIC_MANUAL_RECEIPT_CASE_CANCELLATION_RECONCILIATION';
let checks=0;const check=v=>{checks++;assert(v);};
class Element{constructor(){this.hidden=false;this.disabled=false;this.checked=false;this.value='';this.textContent='';this.children=[];}closest(){return null;}replaceChildren(){this.children=[];}append(...c){this.children.push(...c);}reset(){}}
const elements=new Map(),$=n=>{if(!elements.has(n))elements.set(n,new Element());return elements.get(n);};
const storage={},calls=[];const context=vm.createContext({$,console,Date,Map,Set,JSON,Number,String,Error,encodeURIComponent,crypto:{randomUUID:()=>key},generation:1,
 localStorage:{getItem:n=>storage[n]??null,setItem:(n,v)=>storage[n]=v,removeItem:n=>delete storage[n]},document:{querySelectorAll:()=>[],addEventListener:()=>{}},
 textElement:(tag,text)=>Object.assign(new Element(),{textContent:text}),prepContext:()=>({id,token:'PRIVATE_TOKEN',generation:context.generation}),prepCurrent:c=>c.id===id&&c.generation===context.generation,
 prepCall:(path,method,body,key,c)=>new Promise((resolve,reject)=>calls.push({path,method,body,key,c,resolve,reject})),
 clearPreparation:()=>{context.preparationView=null;vm.runInContext('clearCaseCancellation()',context);},preparationView:{preparation:{id,case_id:cid},case_cancelled:false},
 prepCommandPending:null,prepRecoveryHandle:null,prepRecoveryChecking:false,caseFactPending:null,materialReusePending:null,receiptLocalPending:null,
 objectionLock:()=>false,localCaseLocked:()=>false,dispatchPending:null,servicePlanPending:null,servicePlanRecoveryHandle:null});
context.localStorage=new Proxy(context.localStorage,{ownKeys:()=>Object.keys(storage),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
vm.runInContext(code,context);const run=s=>vm.runInContext(s,context),tick=()=>new Promise(r=>setImmediate(r));
const x={scope,actor_id:'fixture-a',preparation_id:id,case_id:cid,preparation_revision:5,lifecycle_revision:0,source_sha256:'a'.repeat(64),blockers:[],receipts:[{step_id:id,receipt_id:rid,version:1,receipt_sha256:'b'.repeat(64)}],history:[],can_request:true,can_reconcile:false,can_confirm:false,case_state:'NEEDS_INPUT',resource_release_automatic:false,restore_supported:false,request_event_id:rid,reconciliation_event_id:rid};
const action=mode.startsWith('record_')?'RECONCILE':mode.startsWith('finish_')?'CONFIRM_CANCEL':'REQUEST_CANCEL';
if(action!=='REQUEST_CANCEL')Object.assign(x,{case_state:'RECONCILING',lifecycle_revision:action==='RECONCILE'?1:2,can_request:false,can_reconcile:true,can_confirm:action==='CONFIRM_CANCEL'});
const h={v:1,action,actor:'fixture-a',id,case:cid,key,revision:x.lifecycle_revision,expires:Date.now()+86400000},name='parkweave.case-reconcile.v1.'+id+'.fixture-a';
const result=()=>{const event={scope,actor_id:h.actor,preparation_id:id,case_id:cid,request_key:key,revision:h.revision+1,action,case_state:action==='CONFIRM_CANCEL'?'CANCELLED':'RECONCILING',resource_release_automatic:false};return {scope,status:'COMMITTED',historical_only:true,automatically_replayed:false,event_id:key,event,current:{...x,can_request:false,can_reconcile:action!=='CONFIRM_CANCEL',can_confirm:false,case_state:event.case_state,lifecycle_revision:event.revision,history:[{event_id:key,event}]}};};
async function read(){const p=run('readCaseReconciliation()');calls.at(-1).resolve(x);await p;}
function confirm(){ $('case-reconcile-reason').value='PRIVATE_REASON';$('case-reconcile-confirm').checked=true;run("caseReconChoices.forEach(s=>s.value='KNOWN_LOCAL_RESULT')");}
(async()=>{
 if(['eight_handles','ninth_corrupt_set','future_handle'].includes(mode)){
  const n=mode==='ninth_corrupt_set'?9:mode==='future_handle'?1:8;
  for(let i=0;i<n;i++){const actor='opaque-other-'+i,handle={...h,actor,expires:mode==='future_handle'?Date.now()+86460000:Date.now()+86400000};storage['parkweave.case-reconcile.v1.'+id+'.'+actor]=JSON.stringify(handle);}
  await read();confirm();let failed=false;try{await run("submitCaseReconciliation('REQUEST_CANCEL')");}catch(e){failed=true;}
  check(!calls.some(c=>c.method==='POST'));check(Object.keys(storage).length===n);check(failed||run('caseReconView')===null);
  check(!Object.values(storage).some(v=>v.includes('PRIVATE_TOKEN')||v.includes('PRIVATE_REASON')));
 }else if(mode==='terminal_old_request'){
  storage[name]=JSON.stringify(h);const r=result();r.current.case_state='CANCELLED';r.current.lifecycle_revision=64;r.current.can_reconcile=false;
  const p=run('readCaseReconciliation()');calls.at(-1).resolve(r.current);await p;check(!!storage[name]);
  const recovery=run('recoverCaseReconciliation()');check(calls.at(-1).method==='GET');calls.at(-1).resolve(r);await recovery;
  check(!storage[name]&&!calls.some(c=>c.method==='POST')&&context.preparationView.case_cancelled===true);
  check(!$('case-reconcile-confirm').checked&&$('case-reconcile-reason').value==='');
 }else if(mode==='known_is_not_confirmation'){
  Object.assign(x,{case_state:'RECONCILING',lifecycle_revision:2,can_request:false,can_reconcile:true,can_confirm:true});
  await read();check(!$('case-reconcile-confirm').checked&&$('case-reconcile-reason').value==='');
  await run("submitCaseReconciliation('CONFIRM_CANCEL')");check(!calls.some(c=>c.method==='POST')&&!storage[name]);
  check($('case-reconcile-finish').disabled===true);
 }else throw Error('unknown independent mode');
 process.stdout.write(JSON.stringify({mode,checks,browser_attempts:0})+'\n');
})().catch(e=>{console.error(e);process.exit(1);});
