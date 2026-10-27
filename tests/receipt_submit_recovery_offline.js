// Narrow actual production code, controlled promises, no actual HTTP or browser.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('src/parkweave/web.html','utf8'),mode=process.argv[2];
const start=html.indexOf('// Manual SUBMIT recovery retains'),end=html.indexOf('async function receiptCommand(action)',start);
assert(start>=0&&end>start);const code=html.slice(start,end),now=1792238400000,id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');
const h={v:1,action:'SUBMIT',actor:'a'.repeat(64),preparation:id(1),case:id(2),run:id(3),step:id(4),key:id(5),revision:1,preparation_revision:4,expires:now+1000};
const name='parkweave.receipt-submit.v1.'+h.actor+'.'+h.step,raw=JSON.stringify(h),store={},removed=[],requests=[],nodes={};
Object.defineProperties(store,{getItem:{value:n=>Object.hasOwn(store,n)?store[n]:null},setItem:{value:(n,v)=>{store[n]=v;}},removeItem:{value:n=>{removed.push(n);delete store[n];}}});
const view={scope:'SYNTHETIC_ASSIGNED_EXECUTOR_RECEIPT_ONLY',role:'service_executor',actor_ref:h.actor,can_submit:true,is_current_step:true,step:{id:h.step,executor_id:'executor-a',preparation_id:h.preparation,case_id:h.case,run_id:h.run,preparation_revision:4,revision:1,state:'AWAITING_RECEIPT'}},c={generation:1,token:'PRIVATE',id:h.step,revision:1};
let draft='ORIGINAL',clears=0;
const context=vm.createContext({URLSearchParams,JSON,Number,Object,Error,Date:{now:()=>now},localStorage:store,
 $:n=>nodes[n]??(nodes[n]={value:'PRIVATE',textContent:'',hidden:false,disabled:false}),
 uuidHandle:x=>typeof x==='string'&&/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(x),
 crypto:{randomUUID:()=>h.key},receiptView:view,entryWriteRequests:new Map(),receiptCtx:()=>({...c}),
 receiptCurrent:x=>x.generation===c.generation&&x.token===c.token&&x.id===c.id,
 requireReceipt:x=>{if(x.generation!==c.generation||x.token!==c.token||x.id!==c.id){const e=Error('stale');e.staleReceipt=true;throw e;}},
 receiptDraft:()=>draft,resetReceiptDraft:()=>{clears++;},receiptError:()=>{},renderReceipt:()=>{},
 receiptCall:(...args)=>new Promise((resolve,reject)=>requests.push({args,resolve,reject}))});
vm.runInContext(code,context);const run=x=>vm.runInContext(x,context);store[name]=raw;
const proof={scope:view.scope,actor_ref:h.actor,step_id:h.step,preparation_id:h.preparation,case_id:h.case,run_id:h.run,expected_revision:1,preparation_revision:4,request_key:h.key,historical_only:true,read_only:true,automatically_replayed:false,case_goal_completed:false,status:'COMMITTED',event:{id:id(6),action:'SUBMIT',revision:2,receipt_id:id(7),receipt_version:1,receipt_sha256:'b'.repeat(64)}};
function current(){const r={id:id(7),step_id:h.step,actor_id:'executor-a',source_kind:'SYNTHETIC',source_sha256:'b'.repeat(64),version:1};return {...view,step:{...view.step,revision:2,state:'RECEIPT_RECORDED'},receipt_history:[r],history:[{action:'SUBMIT',revision:2,payload:{step_id:h.step,actor_id:'executor-a',receipt_id:r.id,receipt_sha256:r.source_sha256}}]};}
const tick=async(n=12)=>{for(let i=0;i<n;i++)await Promise.resolve();};
(async()=>{
 const expiry={past:now-1,now,one_ms:now+1,max:now+86400000,over:now+86400001,zero:0,far:999999999999999,null:null,string:String(now+1),boolean:true};
 if(Object.hasOwn(expiry,mode)||['extra','oversize','malformed','storage_error','limit','other_actor'].includes(mode)){
  const changed={...h};if(Object.hasOwn(expiry,mode))changed.expires=expiry[mode];if(mode==='extra')changed.text='FORBIDDEN';
  store[name]=mode==='malformed'?'{':mode==='oversize'?'x'.repeat(641):JSON.stringify(changed);
  if(mode==='limit')for(let i=10;i<18;i++)store[name+i]=raw;
  if(mode==='storage_error')Object.defineProperty(store,name,{enumerable:true,get:()=>{throw Error('storage refused');}});
  const before=mode==='storage_error'?null:JSON.stringify({...store}),rows=run('receiptSubmitHandles('+JSON.stringify(h.actor)+')');
  assert(['one_ms','max','other_actor'].includes(mode)?rows.length===1:rows===null);
  assert(run('receiptSubmitStoredPending()'));if(before)assert.equal(JSON.stringify({...store}),before);
  if(mode==='other_actor')assert.equal(run('receiptSubmitHandles('+JSON.stringify('c'.repeat(64))+')').length,0);
 }else if(mode==='send_storage_failure'||mode==='send_draft_changed'||mode==='send_late_context'||mode==='send_reply_unknown'||mode==='send_replacement'){
  delete store[name];
  if(mode==='send_storage_failure')Object.defineProperty(store,name,{configurable:true,set:()=>{throw Error('full');}});
  const pending=run('sendReceiptSubmit(receiptCtx(),{action:"SUBMIT",expected_revision:1,text:"PRIVATE_TEXT",source_label:"PRIVATE_LABEL",source_kind:"SYNTHETIC"})');
  if(mode==='send_storage_failure'){await assert.rejects(pending);assert.equal(requests.length,0);}
  else{
   assert.equal(requests.length,1);assert.equal(requests[0].args[1],'POST');assert(!store[name].includes('PRIVATE'));
   if(mode==='send_reply_unknown'){requests[0].reject(Error('unknown connection'));await pending;assert(store[name]);assert.equal(nodes['receipt-submit-recover'].disabled,false);}
   else if(mode==='send_replacement'){store[name]=JSON.stringify({...h,key:id(10)});nodes['receipt-submit-status'].textContent='NEW STATUS';requests[0].resolve({});await assert.rejects(pending);assert.equal(nodes['receipt-submit-status'].textContent,'NEW STATUS');assert(store[name]);}
   else if(mode==='send_late_context'){c.generation+=2;requests[0].resolve({});await assert.rejects(pending);assert(store[name]);}
   else{
    draft='NEW DRAFT';requests[0].resolve({});await tick();assert.equal(requests.length,2);requests[1].resolve(proof);await tick();assert.equal(requests.length,3);requests[2].resolve(current());await pending;assert(!store[name]);
   }
  }
 }else{
  run('receiptSubmitHandle=receiptSubmitRead(receiptView)');
  if(mode.startsWith('outer_')){
   context.proof=proof;run('receiptSubmitGet=async()=>proof');const p=run('receiptSubmitRecover()');
   if(mode==='outer_replacement')store[name]=JSON.stringify({...h,key:id(10)});else c.generation+=2;
   nodes['receipt-submit-status']={textContent:'NEW STATUS'};await assert.rejects(p);assert(run('receiptSubmitProof===null'));assert.equal(nodes['receipt-submit-status'].textContent,'NEW STATUS');
  }else{
   const release=mode==='release_success'||mode==='render_failure'||mode.startsWith('current_');
   const p=run('receiptSubmitRecover('+release+')');assert.equal(requests.length,1);assert.equal(requests[0].args[1],'GET');
   if(mode==='wrong_proof')proof.case_id=id(10);
   if(mode==='replacement')store[name]=JSON.stringify({...h,key:id(10)});
   if(mode==='late_200'||mode==='late_403'){c.generation+=2;nodes['receipt-submit-status']={textContent:'NEW STATUS'};}
   if(mode==='not_observed'){proof.status='NOT_OBSERVED';proof.event=null;}
   if(mode==='late_403')requests[0].reject(Object.assign(Error('denied'),{status:403}));else requests[0].resolve(proof);
   if(release){
    await tick();assert.equal(requests.length,2);const x=current();
    if(mode==='current_bad_history')x.history=null;
    if(mode==='current_bad_receipt')x.receipt_history[0].id=id(10);
    if(mode==='current_bad_role')x.role='enterprise_operator';
    if(mode==='current_bad_executor')x.step.executor_id='executor-b';
    if(mode==='current_bad_revision')x.step.revision=true;
    if(mode==='current_replacement')store[name]=JSON.stringify({...h,key:id(10)});
    if(mode==='current_ABA')c.generation+=2;
    if(mode==='render_failure')context.renderReceipt=()=>{throw Error('render failed');};
    requests[1].resolve(x);if(mode==='release_success')await p;else await assert.rejects(p);
   }else if(['wrong_proof','replacement','late_200','late_403'].includes(mode))await assert.rejects(p);else await p;
   if(mode.startsWith('late_'))assert.equal(nodes['receipt-submit-status'].textContent,'NEW STATUS');
   if(mode!=='release_success')assert(store[name]);
  }
 }
 assert.equal(clears,0);assert.equal(removed.length,['release_success','send_draft_changed'].includes(mode)?1:0);
 console.log(JSON.stringify({mode,actual_production_functions:true,HTTP_requests:0,GET_stubs:requests.filter(r=>r.args[1]==='GET').length,POST_stubs:requests.filter(r=>r.args[1]==='POST').length,removals:removed.length}));
})().catch(e=>{console.error(e);process.exitCode=1;});
