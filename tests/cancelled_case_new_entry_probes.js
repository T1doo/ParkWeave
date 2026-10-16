// Run actual candidate HTML functions with NodeVM DOM/fetch doubles only.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(process.env.NEW_CASE_HTML||'src/parkweave/web.html','utf8');
const mode=process.argv[2]||'positive';let checks=0;const check=(v,m)=>{checks++;assert(v,m);};
const id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',cid='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',other='dddddddd-dddd-4ddd-8ddd-dddddddddddd';
class Element{constructor(id){this.id=id;this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.textContent='';this.dataset={};const c=new Set();this.classList={add:x=>c.add(x),remove:x=>c.delete(x),contains:x=>c.has(x)};}replaceChildren(){}append(){}reset(){this.value='';}closest(){return null;}setAttribute(n,v){this[n]=v;}scrollIntoView(){this.scrolled=true;}focus(){this.focused=true;}click(){if(this.disabled)return;return this.onclick?.();}}
const els=new Map(),$=id=>{if(!els.has(id))els.set(id,new Element(id));return els.get(id);};
const tabs=['service','collaboration','resource'].map(id=>{const e=new Element('tab-'+id);e.dataset.tab=id;return e;});
const storage={},storageWrites=[],calls=[],clears=[],listeners=[];
const storageApi={getItem:k=>storage[k]??null,setItem:(k,v)=>{storageWrites.push(['set',k]);storage[k]=v;},removeItem:k=>{storageWrites.push(['remove',k]);delete storage[k];}};
const localStorage=new Proxy(storageApi,{ownKeys:()=>Object.keys(storage),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
const context=vm.createContext({$,console,Date,Map,Set,JSON,Number,String,Error,encodeURIComponent,crypto:{randomUUID:()=>other},localStorage,
 document:{body:{dataset:{workspace:'collaboration'}},querySelector:s=>s==='[data-tab="service"]'?tabs[0]:null,querySelectorAll:s=>s==='[data-tab]'?tabs:[],addEventListener:(...a)=>listeners.push(a)},
 window:{addEventListener:()=>{}},preparationId:id,preparationView:{preparation:{id,case_id:cid,owner_id:'fixture-a'},case_cancelled:true},preparationContext:{caseId:cid},prepGeneration:1,prepRole:'enterprise_operator',prepCatalog:null,prepRetries:new Map(),pageGeneration:0,
 prepContext:()=>({id:context.preparationId,generation:context.prepGeneration,token:$('token').value}),prepCurrent:c=>c.id===context.preparationId&&c.generation===context.prepGeneration&&c.token===$('token').value,
 prepCall:(path,method,body,key,c)=>new Promise((resolve,reject)=>calls.push({path,method,body,key,c,resolve,reject})),
 fetch:async(path,options)=>{calls.push({path,method:options?.method||'GET',fetch:true});return {ok:false,status:403};},
 entryWriteRequests:new Map(),activeEntryWriteFlow:null,originalPending:false,originalStoredWritePending:()=>context.originalPending,
 prepCommandPending:null,prepRecoveryHandle:null,prepRecoveryChecking:false,caseFactPending:null,materialReusePending:null,dispatchPending:null,servicePlanPending:null,servicePlanRecoveryHandle:null,
 objectionLock:()=>false,localCaseLocked:()=>false,uuidHandle:v=>/^[a-f0-9-]{36}$/.test(v),
 clearDeniedPrivateViews:()=>{context.denied=true;context.preparationView=null;vm.runInContext('clearCaseCancellation()',context);},denied:false,
 sendClarification:()=>{},receiptView:null,dispatchView:null});
for(const n of ['clearRecordDirectory','clearPersonalTaskList','mgClear','clearDeadline','clearOpportunities','clearFactBundle','clearObjections','clearRunAccess','clearCaseFacts','clearMaterialReuse','clearMaterialDraft','clearMaterialCorrections','renderPrepCommandPending','resetPreparationDraft','clearReadiness','clearPlanMaterialNavigation','clearNotices','clearLocalCase','clearDispatch','clearCaseResources','clearReceiptHistory'])context[n]=()=>clears.push(n);
context.clearReceipts=()=>{clears.push('receipts');context.receiptView=null;};context.clearResources=()=>clears.push('resources');
const line=name=>{const s=html.split('\n').find(s=>s.startsWith('function '+name+'(')||s.startsWith('async function '+name+'('));assert(s,name);return s;};
vm.runInContext(html.slice(html.indexOf('function requireOriginalEntriesSettled(){'),html.indexOf('\nfunction beginCaseWorklistEntry')),context);
vm.runInContext(line('clearGeneric')+'\n'+line('clearPreparation'),context);
vm.runInContext(html.slice(html.indexOf('// Case cancellation: opaque'),html.indexOf('// Internal offers share')),context);
vm.runInContext(html.split('\n').filter(s=>s.startsWith('const coldStorage=')||s.startsWith('const coldGoalLabels=')||s.startsWith('let coldDirectory=')).join('\n')+'\n'+['coldKeys','coldText','coldHandle','coldContext','coldCurrent','coldCommitted','coldWritable','coldNext','coldControls','coldClear','coldError','coldCall','coldReadDirectory'].map(line).join('\n'),context);
vm.runInContext(html.split('\n').find(s=>s.startsWith("document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=")),context);
$('token').value='PRIVATE_CURRENT_TOKEN';$('service').hidden=true;$('cold-form').hidden=true;
const run=s=>vm.runInContext(s,context),tick=()=>new Promise(r=>setImmediate(r));
const x={scope:'SYNTHETIC_CASE_CANCEL_AFTER_ACCEPT_BEFORE_FIRST_RECEIPT',actor_id:'fixture-a',preparation_id:id,case_id:cid,preparation_revision:5,lifecycle_revision:1,source_sha256:'a'.repeat(64),case_state:'CANCELLED',blockers:['CASE_ALREADY_CANCELLED'],can_cancel:false,resource_release_automatic:false,restore_supported:false};
const handle={v:2,stage:'BEFORE_RECEIPT',actor:'fixture-a',id,case:cid,key:other,revision:0,expires:Date.now()+60000};
const snapshot=()=>JSON.stringify(storage);
(async()=>{
 if(mode==='not_cancelled')x.case_state='NEEDS_INPUT';
 if(mode==='foreign_owner')x.actor_id='fixture-b';
 if(mode==='foreign_case')x.case_id=other;
 if(mode==='wrong_scope')x.scope='SYNTHETIC_CASE_CANCEL_BEFORE_FIRST_ACCEPT';
 if(mode==='not_owner')context.prepRole='park_specialist';
 run('caseReconHydrate(preparationView.preparation)');run('renderCaseCancellation('+JSON.stringify(x)+')');
 if(['not_cancelled','foreign_owner','foreign_case','wrong_scope','not_owner'].includes(mode)){
  check($('case-cancel-new-entry').hidden);$('case-cancel-new-confirm').checked=true;await run('openNewCaseAfterCancellation()');check(!calls.length);check(context.preparationId===id);
 }else{
  check(!$('case-cancel-new-entry').hidden);check($('case-cancel-new-open').disabled);
  await run('openNewCaseAfterCancellation()');check(!calls.length,'missing explicit confirmation must not fetch');
  $('case-cancel-new-confirm').checked=true;run('caseCancelNewControls()');
  if(mode==='unknown_handle')storage['parkweave.case-cancel.v1.'+id+'.fixture-a']=JSON.stringify(handle);
  if(mode==='corrupt_handle')storage['parkweave.case-cancel.v1.bad']='{';
  if(mode==='cold_unknown')storage['parkweave.cold-input-original-key.v1']=JSON.stringify({v:1,actor:'opaque-original',key:other,sent:['PREPARE']});
  if(mode==='pending')context.prepCommandPending={state:'UNKNOWN'};
  if(mode==='lease')context.entryWriteRequests.set('original',{key:'opaque-original'});
  if(mode==='original_unknown')context.originalPending=true;
  for(const n of ['cold-goal','cold-need','cold-outline','cold-extra','cold-reason'])$(n).value='PRIVATE_OLD_DRAFT';
  const before=snapshot(),p=run('openNewCaseAfterCancellation()');
  if(['unknown_handle','corrupt_handle','cold_unknown','pending','lease','original_unknown'].includes(mode)){
   await p;check(calls.length===0);check(context.preparationId===id);check(snapshot()===before);check(!storageWrites.length);
  }else{
   check(calls.length===1&&calls[0].method==='GET');check(calls[0].path.endsWith('/case-cancellation-before-receipt'));check(calls[0].body===undefined&&calls[0].key===undefined);
   if(mode==='stale_context')context.prepGeneration++;
   if(mode==='token_change')$('token').value='PRIVATE_DIFFERENT_TOKEN';
   if(mode==='read_replaced')run('renderCaseCancellation('+JSON.stringify(x)+')');
   if(mode==='unconfirmed_after_get')$('case-cancel-new-confirm').checked=false;
   if(mode==='pending_after_get')context.prepRecoveryHandle={key:'new-unknown'};
   if(mode==='unknown_after_get')storage['parkweave.case-cancel.v1.'+id+'.fixture-a']=JSON.stringify(handle);
   const fresh={...x};
   if(mode==='fresh_not_cancelled')fresh.case_state='NEEDS_INPUT';
   if(mode==='fresh_foreign_owner')fresh.actor_id='fixture-b';
   if(mode==='fresh_foreign_case')fresh.case_id=other;
   if(mode==='fresh_stale_source')fresh.source_sha256='b'.repeat(64);
   if(mode==='fresh_stale_revision')fresh.preparation_revision++;
   if(mode==='revoked')calls[0].reject(Object.assign(Error('actual GET 403 double'),{status:403}));else calls[0].resolve(fresh);
   await p;check(calls.every(c=>c.method==='GET'));check(!storageWrites.length);
   if(mode==='positive'||mode==='cold_disabled'){
    check(context.preparationId===null&&context.preparationView===null);check(context.document.body.dataset.workspace==='service');check(!$('service').hidden);check($('cold-directory-read').focused);check($('cold-entry').scrolled);check($('cold-status').textContent.includes(cid)&&$('cold-status').textContent.includes('CANCELLED'));
    for(const n of ['cold-goal','cold-need','cold-outline','cold-extra','cold-reason'])check($(n).value==='');
    check(snapshot()===before);check(!storageWrites.length);check(run('caseReconBlocked('+JSON.stringify(cid)+')'),'old Case stop guard remains');
    if(mode==='cold_disabled'){await run('coldReadDirectory()');check(context.denied);check($('cold-form').hidden);check(calls.every(c=>c.method==='GET'));}
   }else if(mode==='revoked'){check(context.preparationView===null);check(context.document.body.dataset.workspace==='collaboration');}
   else{check(context.preparationId===id);check(context.document.body.dataset.workspace==='collaboration');check(!$('cold-directory-read').focused);}
  }
 }
 check(!calls.some(c=>c.method==='POST'));console.log(JSON.stringify({mode,checks,actual_http:false,real_browser:'NOT_RUN',scope:'ACTUAL_CANDIDATE_HTML_FUNCTIONS_NODE_VM_DOM_FETCH_DOUBLES'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
