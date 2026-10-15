const vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const BASE=__dirname,source=fs.readFileSync(BASE+'/freeze-5a7eee8-ui-functions.js','utf8');
const uuid=n=>String(n).padStart(8,'0')+'-0000-4000-8000-000000000001';
const canonical=x=>Array.isArray(x)?'['+x.map(canonical).join(',')+']':x&&typeof x==='object'?'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',')+'}':JSON.stringify(x);
const hash=x=>crypto.createHash('sha256').update(canonical(x)).digest('hex');
const results=[];
function setup(){
  const elements=new Map(),store={};let cleared=0,rendered=null;
  const env={console,Error,Set,Map,JSON,Object,Array,Number,String,encodeURIComponent,TextEncoder,crypto,
    planSourceConflictStorage:'parkweave.plan-source-conflict.v1.',planSourceConflictActions:['EDIT_NOTE','KEEP_MANUAL','ACCEPT_SOURCE','DEFER'],
    planSourceConflictGeneration:31,servicePlanGeneration:9,prepGeneration:17,oppGeneration:12,token:'SYNTHETIC_PROBE_TOKEN',
    preparationId:uuid(1),preparationView:{preparation:{case_id:uuid(2),run_id:uuid(3)}},
    servicePlanView:{plan_id:uuid(4),actor_ref:hash({actor_id:'synthetic-owner'}),revision:4,steps:[{adapter_id:'P1',id:uuid(5)}]},
    $:id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:'',replaceChildren(){}});return elements.get(id)},
    uuidHandle:x=>typeof x==='string'&&/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(x),
    boundedCaseHash:x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x),
    coldKeys:(x,keys)=>x&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).sort().join(',')===keys.slice().sort().join(','),
    localStorage:store,coldDigest:async x=>hash(x),receiptHistoryCanonical:canonical,
    clearDeniedPrivateViews:()=>{cleared++},servicePlanCurrent:()=>true,
    clearOpportunityPlan:()=>{},renderPlanSourceConflict:v=>{rendered=v.state},planSourceConflictControls:()=>{},entryWriteRequests:new Map(),activeEntryWriteFlow:{requests:new Set()}
  };
  Object.defineProperties(store,{getItem:{enumerable:false,value:k=>Object.hasOwn(store,k)?store[k]:null},setItem:{enumerable:false,value:(k,v)=>{store[k]=v}},removeItem:{enumerable:false,value:k=>{delete store[k]}}});
  env.oppCtx=()=>({generation:env.prepGeneration,oppGeneration:env.oppGeneration,token:env.token,id:env.preparationId,caseId:env.preparationView.preparation.case_id});
  env.oppCurrent=c=>c.generation===env.prepGeneration&&c.oppGeneration===env.oppGeneration&&c.token===env.token&&c.id===env.preparationId&&c.caseId===env.preparationView.preparation.case_id;
  env.oppRequire=c=>{if(!env.oppCurrent(c))throw Object.assign(Error('synthetic stale'),{staleOpportunity:true})};
  env.loadServiceCasePlan=async()=>{env.servicePlanGeneration++;env.servicePlanView.revision=5};
  env.loadOpportunities=async()=>{env.planSourceConflictGeneration++};
  vm.createContext(env);vm.runInContext(source,env);
  env.entryFetch=async()=>({ok:true,status:200,json:async()=>env.freshReadDto});
  const current=()=>env.planSourceConflictContext();
  const dto=()=>({scope:'OWNER_PLAN_SOURCE_CONFLICT',schema:1,actor_ref:env.servicePlanView.actor_ref,preparation_id:uuid(1),case_id:uuid(2),run_id:uuid(3),plan_id:uuid(4),plan_revision:env.servicePlanView.revision,step_id:uuid(5),card_id:null,opportunity_revision:0,preview_sha256:'a'.repeat(64),can_edit:true,can_resolve:false,allowed_choices:['EDIT_NOTE'],blocking_reasons:[],material_diffs:[],history:[],read_only:true,new_grants:false,automatic_execution:false,case_goal_completed:false,action_requests:{EDIT_NOTE:{}},state:'NO_NOTE',affected:[],preserved:[],source:{slot:'material_outline',id:uuid(6),version:1,text:'SYNTHETIC material',source_sha256:'b'.repeat(64),source_kind:'USER_STATEMENT',source_label:'SYNTHETIC'},note:null});
  const saved=()=>{const request={schema:1,action:'EDIT_NOTE',expected_plan_id:uuid(4),expected_plan_revision:4,expected_note_revision:0,expected_ledger_revision:0,expected_preview_sha256:'a'.repeat(64),card_id:null,text:'SYNTHETIC manual note',reason:'SYNTHETIC explicit edit'};
    const h={schema:1,id:uuid(1),actor:env.servicePlanView.actor_ref,plan:uuid(4),key:uuid(7),action:'EDIT_NOTE',fingerprint:hash({preparation_id:uuid(1),...request}),card:null};
    const name=env.planSourceConflictStorage+h.actor+'.'+h.key;store.setItem(name,JSON.stringify(h));
    const r={id:uuid(8),plan_id:h.plan,request_key:h.key,fingerprint:h.fingerprint,action:h.action,revision:5,coordination_only:true,actor_id:'synthetic-owner',reason:request.reason,plan_note:{request}};
    const x={scope:'OWNER_PLAN_SOURCE_CONFLICT',schema:1,actor_ref:h.actor,preparation_id:h.id,case_id:uuid(2),run_id:uuid(3),plan_id:h.plan,automatically_replayed:false,status:'COMMITTED',receipt:r,current:dto()};
    Object.assign(x.current,{plan_revision:5,history:[r],state:'UNKNOWN',preview_sha256:null,can_edit:false,can_resolve:false,allowed_choices:[],action_requests:{},source:null});
    env.freshReadDto=x.current;return {h:{name,...h},x,name};
  };
  return {env,current,dto,saved,store,cleared:()=>cleared,rendered:()=>rendered};
}
function test(name,fn){return Promise.resolve().then(fn).then(()=>results.push({name,status:'PASS'}))}
(async()=>{
 await test('separate_prep_conflict_generations_current',()=>{const s=setup();assert(s.env.planSourceConflictCurrent(s.current()))});
 await test('service_plan_reload_rejects_old_context',()=>{const s=setup(),c=s.current();s.env.servicePlanGeneration++;assert(!s.env.planSourceConflictCurrent(c))});
 await test('identity_ABA_rejects_old_context',()=>{const s=setup(),c=s.current();s.env.prepGeneration+=2;assert(!s.env.planSourceConflictCurrent(c))});
 await test('normal_nocard_edit_DTO_accepted_without_claiming_partition',()=>{const s=setup();s.env.planSourceConflictCheck(s.dto(),s.current())});
 await test('legal_nonactionable_UNKNOWN_DTO_accepted',()=>{const s=setup(),v=s.dto();Object.assign(v,{state:'UNKNOWN',can_edit:false,can_resolve:false,preview_sha256:null,action_requests:{},allowed_choices:[],source:null});s.env.planSourceConflictCheck(v,s.current())});
 await test('UNKNOWN_with_action_even_hash_refused',()=>{const s=setup(),v=s.dto();v.state='UNKNOWN';assert.throws(()=>s.env.planSourceConflictCheck(v,s.current()))});
 await test('need_summary_not_outline_candidate_refused',()=>{const s=setup(),v=s.dto();v.source.slot='need_summary';assert.throws(()=>s.env.planSourceConflictCheck(v,s.current()))});
 await test('late_transport403_cannot_clear_new_context',async()=>{const s=setup(),c=s.current();let reject;s.env.entryFetch=()=>new Promise((a,b)=>{reject=b});const p=s.env.planSourceConflictCall(c).catch(e=>s.env.planSourceConflictError(e));s.env.planSourceConflictGeneration++;reject(Object.assign(Error('SYNTHETIC late transport'),{status:403}));await p;assert.equal(s.cleared(),0)});
 await test('late_json403_cannot_clear_new_context',async()=>{const s=setup(),c=s.current();let reject,started;const ready=new Promise(r=>{started=r});s.env.entryFetch=async()=>({ok:false,status:403,json:()=>{started();return new Promise((a,b)=>{reject=b})}});const p=s.env.planSourceConflictCall(c).catch(e=>s.env.planSourceConflictError(e));await ready;s.env.servicePlanGeneration++;reject(Object.assign(Error('SYNTHETIC late JSON'),{status:403}));await p;assert.equal(s.cleared(),0)});
 await test('current403_clears_current_private_view',async()=>{const s=setup();s.env.entryFetch=async()=>({ok:false,status:403,json:async()=>({detail:'SYNTHETIC denied'})});await s.env.planSourceConflictCall(s.current()).catch(e=>s.env.planSourceConflictError(e));assert.equal(s.cleared(),1)});
 await test('COMMITTED_current_null_keeps_handle',async()=>{const s=setup(),v=s.saved();v.x.current=null;await assert.rejects(()=>s.env.planSourceConflictReceipt(v.x,s.current(),v.h));assert(s.store.getItem(v.name))});
 await test('NOT_OBSERVED_keeps_handle',async()=>{const s=setup(),v=s.saved();v.x.status='NOT_OBSERVED';v.x.receipt=null;await assert.rejects(()=>s.env.planSourceConflictReceipt(v.x,s.current(),v.h));assert(s.store.getItem(v.name))});
 await test('COMMITTED_current_UNKNOWN_releases_exact_handle_after_fresh_GETs',async()=>{const s=setup(),v=s.saved();await s.env.planSourceConflictReceipt(v.x,s.current(),v.h);assert.equal(s.store.getItem(v.name),null);assert.equal(s.rendered(),'UNKNOWN')});

 await test('clear_reenables_read_and_recovery_while_old_generation_is_invalid',()=>{const s=setup(),c=s.current();s.env.$('plan-source-conflict-read').disabled=true;s.env.$('plan-source-conflict-recover').disabled=true;s.env.clearPlanSourceConflict();assert.equal(s.env.$('plan-source-conflict-read').disabled,false);assert.equal(s.env.$('plan-source-conflict-recover').disabled,false);assert(!s.env.planSourceConflictCurrent(c))});
 function writable(s){const e=s.env,v=s.dto();v.uiContext=s.current();v.action_requests.EDIT_NOTE={schema:1,action:'EDIT_NOTE',expected_plan_id:v.plan_id,expected_plan_revision:v.plan_revision,expected_note_revision:0,expected_ledger_revision:v.opportunity_revision,expected_preview_sha256:v.preview_sha256,card_id:null,text:'',reason:''};e.planSourceConflictView=v;e.$('plan-source-conflict-note').value='SYNTHETIC original note';e.$('plan-source-conflict-reason').value='SYNTHETIC original reason';e.$('plan-source-conflict-confirm').checked=true;return e}
 for(const field of ['note','reason','confirm'])await test('digest_wait_changed_'+field+'_sends_no_request_or_handle',async()=>{const s=setup(),e=writable(s);let release,posts=0;e.coldDigest=x=>new Promise(r=>{release=()=>r(hash(x))});e.planSourceConflictCall=async()=>{posts++;throw Error('unexpected')};const p=e.planSourceConflictWrite('EDIT_NOTE');e.$('plan-source-conflict-'+field)[field==='confirm'?'checked':'value']=field==='confirm'?false:'SYNTHETIC changed';release();await p;assert.equal(posts,0);assert.equal(Object.keys(s.store).length,0)});
 await test('digest_wait_identity_ABA_sends_no_request_or_handle',async()=>{const s=setup(),e=writable(s);let release,posts=0;e.coldDigest=x=>new Promise(r=>{release=()=>r(hash(x))});e.planSourceConflictCall=async()=>{posts++};const p=e.planSourceConflictWrite('EDIT_NOTE');e.prepGeneration+=2;release();await p;assert.equal(posts,0);assert.equal(Object.keys(s.store).length,0)});
 await test('generic409_without_definitive_proof_keeps_exact_handle',async()=>{const s=setup(),e=writable(s);e.planSourceConflictCall=async()=>{throw Object.assign(Error('synthetic 409'),{status:409})};await assert.rejects(()=>e.planSourceConflictWrite('EDIT_NOTE'));assert.equal(Object.keys(s.store).length,1);assert.equal(e.planSourceConflictHandles().length,1)});
 await test('exact_definitive_refusal_releases_only_exact_verified_lease',async()=>{const s=setup(),e=writable(s);const other={key:'unrelated',stage:'PENDING',verified:false};e.entryWriteRequests.set('unrelated',other);e.activeEntryWriteFlow.requests.add(other);let observed;e.planSourceConflictCall=async(c,suffix,method,body,key)=>{const path='/api/preparations/'+encodeURIComponent(c.id)+'/plan-source-conflicts/commands',op={key,path,token:'Bearer '+c.token,stage:'POST',verified:false};observed=op;e.entryWriteRequests.set(JSON.stringify([path,op.token,key,JSON.stringify(body)]),op);e.activeEntryWriteFlow.requests.add(op);throw Object.assign(Error('exact synthetic refusal'),{status:409,rejection:{scope:'OWNER_PLAN_SOURCE_CONFLICT',schema:1,status:'DEFINITIVELY_REJECTED',preparation_id:c.id,case_id:c.caseId,run_id:e.preparationView.preparation.run_id,actor_ref:c.actor,request_key:key,fingerprint:hash({preparation_id:c.id,...body}),action:body.action,plan_id:body.expected_plan_id,definitively_rejected:true,business_writes:false,automatically_replayed:false}})};await assert.rejects(()=>e.planSourceConflictWrite('EDIT_NOTE'));assert.equal(Object.keys(s.store).length,0);assert.equal(e.entryWriteRequests.size,1);assert.equal(e.entryWriteRequests.get('unrelated'),other);assert.equal(other.verified,false);assert.equal(observed.stage,'REJECTED');assert.equal(observed.verified,true);assert.equal(e.$('plan-source-conflict-note').value,'SYNTHETIC original note')});
 const result={status:'PASS_EXTRACTED_FROZEN_FUNCTION_PROBES_ONLY',checks:results.length,results,source_snapshot:'freeze-5a7eee8-ui-source.json',source_sha:'5a7eee826564426a4c36607ac038bd61e00665d7',scope:'Actual extracted frozen functions in synthetic NodeVM with transport/DOM stubs. Separate supplemental probes, not fullHTML/HTTP/ASGI/PG, real browser or complete regression.'};
 fs.writeFileSync(BASE+'/freeze-5a7eee8-ui-probe-result.json',JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
