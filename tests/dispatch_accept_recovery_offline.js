// Actual narrow production functions under controlled promises; no HTTP/browser claims.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('src/parkweave/web.html','utf8'),mode=process.argv[2];
const start=html.indexOf('// ACCEPT recovery owns'),end=html.indexOf('// Explicit pending manual handoff.',start);assert(start>=0&&end>start);
const block=html.slice(start,end),now=1792238400000,id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');
const h={v:1,action:'ACCEPT',actor:'a'.repeat(64),preparation:id(1),case:id(2),run:id(3),dispatch:id(4),offer:id(5),key:id(6),revision:1,preparation_revision:4,expires:now+1000};
const name='parkweave.dispatch-accept.v1.'+h.actor+'.'+h.dispatch,raw=JSON.stringify(h),store={},nodes={};
Object.defineProperties(store,{getItem:{value:n=>Object.hasOwn(store,n)?store[n]:null},setItem:{value:(n,v)=>store[n]=v},removeItem:{value:n=>{removed.push(n);delete store[n];}}});
const removed=[],requests=[],view={actor_ref:h.actor,preparation_id:h.preparation,case_id:h.case,run_id:h.run,dispatch_id:h.dispatch,current_offer:{executor_id:'executor-a'}},c={generation:1,token:'PRIVATE',id:h.dispatch};
const context=vm.createContext({URLSearchParams,JSON,Number,Object,Error,Date:{now:()=>now},localStorage:store,
 $:n=>nodes[n]??(nodes[n]={value:'PRIVATE',textContent:'',hidden:false,disabled:false}),
 uuidHandle:x=>typeof x==='string'&&/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(x),
 dispatchView:view,entryWriteRequests:new Map(),dispatchCtx:()=>({...c}),
 dispatchCurrent:x=>x.generation===c.generation&&x.token===c.token,
 requireDispatch:x=>{if(x.generation!==c.generation||x.token!==c.token){const e=Error('stale');e.staleDispatch=true;throw e;}},
 dispatchPendingUI:()=>{},dispatchError:()=>{},renderDispatch:()=>{},
 dispatchCall:(...args)=>new Promise((resolve,reject)=>requests.push({args,resolve,reject}))});
vm.runInContext(block,context);const run=x=>vm.runInContext(x,context);
store[name]=raw;
const expires={past:now-1,now:now,one_ms:now+1,max:now+86400000,over:now+86400001,zero:0,far:999999999999999,null:null,string:String(now+1000),boolean:true};
(async()=>{
 if(Object.hasOwn(expires,mode)||['extra','oversize','malformed','storage_error','limit','other_actor'].includes(mode)){
  const changed={...h};if(Object.hasOwn(expires,mode))changed.expires=expires[mode];
  if(mode==='extra')changed.reason='FORBIDDEN';
  store[name]=mode==='malformed'?'{':mode==='oversize'?'x'.repeat(641):JSON.stringify(changed);
  if(mode==='limit')for(let i=10;i<18;i++)store[name+i]=raw;
  if(mode==='storage_error')Object.defineProperty(store,name,{enumerable:true,get:()=>{throw Error('storage refused');}});
  const before=mode==='storage_error'?null:JSON.stringify({...store}),result=run('dispatchAcceptHandles('+JSON.stringify(h.actor)+')');
  assert(['one_ms','max','other_actor'].includes(mode)?result.length===1:result===null);
  assert(run('dispatchAcceptStoredPending()'));if(mode!=='storage_error')assert.equal(JSON.stringify({...store}),before);
  if(mode==='other_actor')assert.equal(run('dispatchAcceptHandles('+JSON.stringify('b'.repeat(64))+')').length,0);
 }else{
  run('dispatchAcceptHandle=dispatchAcceptRead(dispatchView)');
  const proof={scope:'SYNTHETIC_INTERNAL_DISPATCH_ONLY',actor_ref:h.actor,dispatch_id:h.dispatch,preparation_id:h.preparation,case_id:h.case,run_id:h.run,offer_id:h.offer,expected_revision:1,preparation_revision:4,request_key:h.key,historical_only:true,read_only:true,automatically_replayed:false,case_goal_completed:false,status:'COMMITTED',event:{id:id(7),action:'ACCEPT',revision:2,receipt_step_id:id(8)}};
  if(mode.startsWith('outer_')){
   // Keep the actual inner implementation in source; inject only its resolved
   // boundary to place navigation between inner completion and caller resume.
   context.originalGet=run('dispatchAcceptGet');context.proof=proof;
   run('dispatchAcceptGet=async()=>proof');
   const pending=run('dispatchAcceptRecover()');
   if(mode==='outer_case_ABA'){c.generation+=2;view.case_id=id(9);}
   else if(mode==='outer_identity_ABA'){c.generation+=2;c.token='PRIVATE';}
   else if(mode==='outer_replacement')store[name]=JSON.stringify({...h,key:id(10)});
   else throw Error(mode);
   nodes['dispatch-accept-status']={textContent:'NEW_STATUS'};
   await assert.rejects(pending);assert(run('dispatchAcceptProof===null'));assert.equal(nodes['dispatch-accept-status'].textContent,'NEW_STATUS');
  }else{
   const release=mode.startsWith('current_bad_')||mode==='render_failure';
   const pending=run('dispatchAcceptRecover('+release+')');assert.equal(requests.length,1);assert.equal(requests[0].args[1],'GET');
   if(mode==='wrong_proof')proof.case_id=id(9);
   else if(mode==='replacement')store[name]=JSON.stringify({...h,key:id(10)});
   else if(mode==='late_200'||mode==='late_403'){c.generation+=2;nodes['dispatch-accept-status']={textContent:'NEW_STATUS'};}
   else if(mode==='not_observed'){proof.status='NOT_OBSERVED';proof.event=null;}
   else if(mode!=='committed'&&!release)throw Error(mode);
   if(mode==='late_403'){const e=Error('denied');e.status=403;requests[0].reject(e);}else requests[0].resolve(proof);
   if(release){
    for(let i=0;requests.length<2&&i<10;i++)await Promise.resolve();
    assert.equal(requests.length,2);
    const offer={id:h.offer,dispatch_id:h.dispatch,state:'ACCEPTED',executor_id:'executor-a',receipt_step_id:id(8)};
    const current={...view,scope:proof.scope,role:'service_executor',revision:2,preparation_revision:4,offers:[offer],current_offer:offer,history:[]};
    if(mode==='current_bad_history')current.history=null;
    if(mode==='current_bad_role')current.role='park_specialist';
    if(mode==='current_bad_revision')current.revision=65;
    if(mode==='current_bad_executor'){offer.executor_id='executor-b';}
    if(mode==='current_bad_offer')current.current_offer={...offer,id:id(10)};
    if(mode==='render_failure')context.renderDispatch=()=>{throw Error('actual renderer failure boundary');};
    requests[1].resolve(current);await assert.rejects(pending);
   }else if(['wrong_proof','replacement','late_200','late_403'].includes(mode))await assert.rejects(pending);else await pending;
   assert.equal(run('dispatchAcceptProof!==null'),(mode==='committed'||release));
   if(mode.startsWith('late_'))assert.equal(nodes['dispatch-accept-status'].textContent,'NEW_STATUS');
  }
  assert(store[name]);assert(run('dispatchAcceptStoredPending()'));
 }
 assert.deepEqual(removed,[]);assert(requests.every(r=>r.args[1]==='GET'));
 console.log(JSON.stringify({mode,actual_production_functions:true,HTTP_requests:0,GET_stubs:requests.length,POST_stubs:0,removals:0}));
})().catch(e=>{console.error(e);process.exitCode=1;});
