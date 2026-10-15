// Controlled client function probes only: no browser, HTTP or PostgreSQL.
const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
const html=fs.readFileSync('src/parkweave/web.html','utf8');
const preview=html.slice(html.indexOf('async function previewOpportunityPlan('),html.indexOf('function opportunityAdoptionBody('));
const checker=html.slice(html.indexOf('async function employeesFactProvenanceCheck('),html.indexOf('function renderEmployeesFactProvenance('));
const handler=html.match(/function opportunityPlanError\(e\)\{[^\n]+/)[0];
const canonical=x=>Array.isArray(x)?'['+x.map(canonical).join(',')+']':x&&typeof x==='object'?'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',')+'}':JSON.stringify(x);
const hash=x=>crypto.createHash('sha256').update(canonical(x)).digest('hex');
function assert(ok,message){if(!ok)throw Error(message)}
function harness(){
 let settle,fail,entered=false,clears=0,errors=0;
 const deferred=new Promise((resolve,reject)=>{settle=resolve;fail=reject});
 const elements=new Map();
 const state={Error,Object,Array,Number,Date,Set,Promise,
 opportunityPlanGeneration:0,opportunityPlanDraftGeneration:0,opportunityPlanBusy:false,
 opportunityPlanView:null,identity:0,planGeneration:0,
 oppView:{cards:[{id:'card',state:'PENDING_REVIEW',is_latest_generation:true}]},
 servicePlanView:{steps:[{id:'step',adapter_id:'P1'}]},
 $:id=>{if(!elements.has(id))elements.set(id,{checked:false,hidden:true,append(){},replaceChildren(){}});return elements.get(id)},
 requireOriginalEntriesSettled(){},oppControls(){},opportunityPlanCheck(){},
 textElement:()=>({}),renderTypedSourceImpact(){},renderEmployeesFactProvenance(){},
 clearOpportunityPlan(){clears++;state.opportunityPlanGeneration++;state.opportunityPlanView=null;state.opportunityPlanBusy=false},
 oppCtx:()=>({id:'prep',caseId:'case',identity:state.identity}),
 oppCurrent:c=>c.identity===state.identity,
 oppRequire(c){if(!state.oppCurrent(c)){const e=Error('stale original Case');e.staleOpportunity=true;throw e}},
 servicePlanCtx:()=>({id:'prep',generation:state.planGeneration}),
 servicePlanCurrent:c=>c.generation===state.planGeneration&&(!c.callerCurrent||c.callerCurrent()),
 loadServiceCasePlan:async()=>{},
 servicePlanCall:async()=>({plan_id:'plan',plan_revision:1,opportunity_revision:1,card_version:1,directly_changed:[],affected:[],preserved:[],blocking_reasons:[],can_adopt:false}),
 employeesFactProvenanceCheck:async()=>{entered=true;return deferred},
 oppError(){errors++},servicePlanError(){errors++},
 };
 vm.createContext(state);vm.runInContext(preview+'\n'+handler,state);
 return {state,settle,fail,get entered(){return entered},get clears(){return clears},get errors(){return errors}};
}
async function clientScenario(kind){
 const h=harness(),s=h.state;
 const pending=s.previewOpportunityPlan('card',true).catch(s.opportunityPlanError);
 for(let i=0;i<20&&!h.entered;i++)await Promise.resolve();
 assert(h.entered,'controlled checker seam was not reached');
 const baseline=h.clears;
 if(kind==='late_reject_after_case_switch'){
  s.identity++;s.opportunityPlanView={new_case:true};h.fail(Error('controlled digest rejection'));
 }else if(kind==='late_success_after_sequence_switch'){
  s.opportunityPlanGeneration++;s.opportunityPlanView={new_preview:true};h.settle();
 }else{
  s.opportunityPlanDraftGeneration++;h.settle();
 }
 await pending;
 if(kind==='draft_changed_current_sequence')assert(h.clears===baseline+1&&s.opportunityPlanView===null,'current changed draft should clear its own preview');
 else assert(h.clears===baseline&&h.errors===0&&s.opportunityPlanView!==null,'stale result cleared or errored against new view');
 return {scenario:kind,status:'PASS',post_seam_clear_calls:h.clears-baseline};
}
async function flagScenario(flag){
 const node={field:'employees',assertion_ref:'00000000-0000-0000-0000-000000000001',assertion_revision:1,
 assertion_fingerprint:'a'.repeat(64),assertion_sha256:'b'.repeat(64),source_kind:'USER_ASSERTED_SYNTHETIC',
 source_ref_sha256:'c'.repeat(64),valid_from:'2026-10-11T00:00:00+00:00',valid_until:'2026-10-12T00:00:00+00:00',
 decision_ref:'00000000-0000-0000-0000-000000000002',decision_revision:2,
 decision_sha256:'d'.repeat(64),source_sha256:'e'.repeat(64),descriptor_sha256:'f'.repeat(64),
 ledger_prefix_sha256:'1'.repeat(64),receipt_bindings_sha256:'2'.repeat(64),authenticity:'USER_ASSERTED_UNVERIFIED'};
 node.sha256=hash(node);
 const p={version:1,scope:'EMPLOYEES_USER_ASSERTION_V1',before:node,current:structuredClone(node),selected_changed:false,aggregate_changed:false,authenticity:'USER_ASSERTED_UNVERIFIED',new_grants:false};
 p[flag]=true;p.sha256=hash(p);
 const state={Error,Object,Array,Number,Date,Set,coldDigest:async x=>hash(x),uuidHandle:x=>/^[0-9a-f-]{36}$/.test(x)};
 vm.createContext(state);vm.runInContext(checker,state);
 let error;
 try{await state.employeesFactProvenanceCheck({scope:'EMPLOYEES_FACT_PROVENANCE_PREVIEW',fact_provenance:p})}catch(e){error=e}
 assert(error&&error.message==='员工来源变化标志与原节点不一致','rehashing contradictory flag should fail specifically on independent consistency check');
 return {scenario:'rehashed_'+flag+'_mismatch',status:'PASS'};
}
(async()=>{
 const results=[];
 for(const kind of ['late_reject_after_case_switch','late_success_after_sequence_switch','draft_changed_current_sequence'])results.push(await clientScenario(kind));
 for(const flag of ['selected_changed','aggregate_changed'])results.push(await flagScenario(flag));
 process.stdout.write(JSON.stringify({evidence_kind:'CONTROLLED_CLIENT_FUNCTION_PROBES_NO_HTTP_BROWSER_PG',results})+'\n');
})().catch(e=>{process.stderr.write(String(e.stack)+'\n');process.exitCode=1});
