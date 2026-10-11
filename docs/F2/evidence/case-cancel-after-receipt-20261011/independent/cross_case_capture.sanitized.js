// Actual owner cancellation UI in an offline NodeVM; browser never started.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('src/parkweave/web.html','utf8'),code=html.slice(html.indexOf('// Case cancellation: opaque'),html.indexOf('// Internal offers share'));
const mode=process.argv[2],id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',cid='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',key='cccccccc-cccc-4ccc-8ccc-cccccccccccc',rid='dddddddd-dddd-4ddd-8ddd-dddddddddddd',scope='SYNTHETIC_MANUAL_RECEIPT_CASE_CANCELLATION_RECONCILIATION';
let checks=0;const check=v=>{checks++;assert(v);};
class Element{constructor(){this.hidden=false;this.disabled=false;this.checked=false;this.value='';this.textContent='';this.children=[];}closest(){return null;}replaceChildren(){this.children=[];}append(...c){this.children.push(...c);}reset(){}}
const captureCallbacks={};const elements=new Map(),$=n=>{if(!elements.has(n))elements.set(n,new Element());return elements.get(n);};
const storage={},calls=[];const context=vm.createContext({$,console,Date,Map,Set,JSON,Number,String,Error,encodeURIComponent,crypto:{randomUUID:()=>key},generation:1,
 localStorage:{getItem:n=>storage[n]??null,setItem:(n,v)=>storage[n]=v,removeItem:n=>delete storage[n]},document:{querySelectorAll:()=>[],addEventListener:(kind,fn)=>captureCallbacks[kind]=fn},
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
 storage[name]=JSON.stringify(h);run('caseReconHydrate({...preparationView.preparation,owner_id:\'fixture-a\'})');check(run('caseReconHandle.key')===key);
 const otherPrep='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',otherCase='ffffffff-ffff-4fff-8fff-ffffffffffff';let buttonId,expectedBlock=false,isForm=false;
 if(mode==='controlled_plan_other_case'){
  context.planView={preparation_id:otherPrep,source_snapshots:{P1:{case_id:otherCase,preparation_id:otherPrep}}};buttonId='plan-P1';
 }else if(mode==='delivery_other_case'||mode==='approval_propose_other_case'){
  context.deliveryQuote={context:{id:otherPrep},view:{context:{preparation_id:otherPrep,case_id:otherCase}}};context.planApprovalView=null;$('delivery-case').value=otherPrep;buttonId=mode==='delivery_other_case'?'delivery-confirm':'plan-approval-propose';
 }else if(mode==='receipt_create_uses_current_preparation'){
  context.receiptView={step:{case_id:otherCase,preparation_id:otherPrep}};context.receiptCreateContext={id,caseId:cid};buttonId='receipt-create';expectedBlock=true;isForm=true;
 }else throw Error('unknown cross-case mode');
 let prevented=false,stopped=false;const element={id:buttonId,closest:selector=>selector==='button'?element:selector.split(',').includes('#'+buttonId)?element:null};
 captureCallbacks[isForm?'submit':'click']({target:element,preventDefault:()=>prevented=true,stopImmediatePropagation:()=>stopped=true});
 const actualTarget=run('caseCancelWriteTarget') (element);
 process.stdout.write(JSON.stringify({mode,buttonId,expectedBlock,prevented,stopped,actualTarget,currentPrepCase:cid,otherCase,browser_attempts:0})+'\n');
 check(prevented===expectedBlock&&stopped===expectedBlock);
})().catch(e=>{console.error(e);process.exit(1);});
