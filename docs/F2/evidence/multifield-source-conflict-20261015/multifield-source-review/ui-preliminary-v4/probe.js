'use strict';
const fs=require('fs'),vm=require('vm'),crypto=require('crypto'),assert=require('assert');
const P=__dirname,read=n=>fs.readFileSync(P+'/'+n,'utf8');
const results=[],hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');
function handler(code,name,e){
  const s={clears:0,message:'CURRENT_B_PRIVATE_STATUS',materialPackageCurrent:c=>c?.generation===2,
    servicePlanCurrent:c=>c?.generation===2,oppCurrent:c=>c?.generation===2};
  s.clearDeniedPrivateViews=()=>s.clears++;s.$=()=>({set textContent(v){s.message=v;}});
  vm.createContext(s);vm.runInContext(code,s);s.materialPackageError(e);
  return {name,clears:s.clears,status_unchanged:s.message==='CURRENT_B_PRIVATE_STATUS'};
}
const stale=[
 ['stale_service_plan_flag',{status:403,staleServicePlan:true}],
 ['late_service_plan_context',{status:403,servicePlanContext:{generation:0}}],
 ['stale_opportunity_flag',{status:403,staleOpportunity:true}],
 ['late_opportunity_context',{status:403,opportunityContext:{generation:0}}],
 ['identity_ABA_service_plan_context',{status:403,servicePlanContext:{generation:0,actor:'SYNTHETIC_SAME_ACTOR'}}],
 ['late_json_or_fetch_material_context',{status:403,materialPackageContext:{generation:0}}],
];
for(const [name,e] of stale){
  const before=handler(read('old-error-handler.js'),name,e),after=handler(read('new-error-handler.js'),name,e);
  assert.equal(after.clears,0);assert(after.status_unchanged);
  results.push({kind:'EXTRACTED_HANDLER_VM_NOT_HTTP',name,before,after,expected_after_clear:0});
}
for(const [name,e,clears] of [['current403',{status:403,materialPackageContext:{generation:2}},1],['current_original_loader403',{status:403,servicePlanContext:{generation:2}},1],['current409',{status:409,message:'SYNTHETIC_CURRENT_REFUSAL',materialPackageContext:{generation:2}},0]]){
 const after=handler(read('new-error-handler.js'),name,e);assert.equal(after.clears,clears);results.push({kind:'EXTRACTED_HANDLER_VM_NOT_HTTP',name,after});
}
function dto(manual='SYNTHETIC current manual'){
 const material=(slot,n,text)=>({id:id(n),slot,version:1,text,source_kind:'USER_STATEMENT',source_label:'SYNTHETIC fake DTO',source_sha256:hash(text),authenticity:'UNVERIFIED'});
 const pkg=[material('need_summary',20,'SYNTHETIC summary'),material('material_outline',21,'SYNTHETIC outline')];
 const note={version:1,revision:1,text:manual,text_sha256:hash(manual),origin:'MANUAL',source_ref:Object.fromEntries(['id','slot','version','source_sha256'].map(k=>[k,pkg[1][k]])),source_package:structuredClone(pkg),verified_package_sha256:null,event_id:id(9),plan_id:id(4),step_id:id(5)};
 const c={actor:'a'.repeat(64),id:id(1),caseId:id(2),planId:id(4),selection:id(8),generation:2};
 const v={scope:'OWNER_NOTE_MATERIAL_PACKAGE',schema:1,continuation:null,can_edit:false,can_resolve:true,allowed_choices:[],history:[],actor_ref:c.actor,preparation_id:c.id,case_id:c.caseId,run_id:id(3),plan_id:c.planId,plan_revision:7,step_id:id(5),card_id:c.selection,opportunity_revision:1,preview_sha256:'b'.repeat(64),note,source:structuredClone(pkg[1]),state:'NO_CHANGE',read_only:true,new_grants:false,automatic_execution:false,case_goal_completed:false,blocking_reasons:[],material_diffs:pkg.map(m=>({slot:m.slot,before:structuredClone(m),current:structuredClone(m),changed:false,proof_kind:'SYNTHETIC_FAKE_DTO'})),affected:[],preserved:[5,6,7,10,11].map(id),action_requests:{}};
 v.package_confirmation={schema:1,scope:'OWNER_NOTE_MATERIAL_PACKAGE_CONFIRMATION',mode:'LEGACY_OUTLINE_ONLY',active:false,outline_carriage_required:false,semantic_evaluated:false,manual_preserved:true,policy:{need_summary:'CONTEXT_ACK_ONLY',material_outline:'EXACT_LINE_CARRIAGE_WHEN_REQUIRED_V1'},blocking_reasons:[],can_keep_and_continue:true,can_merge:true,preview_sha256:v.preview_sha256,baseline_package:structuredClone(pkg),current_package:structuredClone(pkg),manual:Object.fromEntries(['text','text_sha256','revision','event_id'].map(k=>[k,note[k]])),coverage:{required:false,coverage_known:true,coverage_satisfied:true,conditions:[]}};
 for(const action of ['KEEP_AND_CONTINUE','MERGE_NOTE'])v.action_requests[action]={schema:2,action,expected_plan_id:v.plan_id,expected_plan_revision:7,expected_note_revision:1,expected_ledger_revision:1,expected_preview_sha256:v.preview_sha256,card_id:v.card_id,text:action==='MERGE_NOTE'?'':null,reason:'',confirm_package:true};
 return {v,c};
}
function env(v,c){
 const s={console,JSON,Math,Number,String,Array,Object,TextEncoder,crypto:crypto.webcrypto,structuredClone,
   servicePlanView:{revision:7,steps:[5,6,7,10,11].map((n,i)=>({id:id(n),adapter_id:'P'+(i+1)}))},
   preparationView:{preparation:{run_id:id(3)}},planSourceConflictActions:['EDIT_NOTE','KEEP_MANUAL','ACCEPT_SOURCE','DEFER','KEEP_AND_CONTINUE','MERGE_NOTE']};
 vm.createContext(s);vm.runInContext(read('helpers.js')+'\n'+read('current-check.js'),s);return s;
}
{
 const {v,c}=dto(),s=env(v,c);s.materialPackageCheck(v,c);results.push({kind:'SYNTHETIC_DTO_VM_NOT_HTTP',name:'consistent_two_slot_DTO_accepted'});
 for(const [name,change] of [
  ['baseline_summary_text_differs_from_note',x=>{x.package_confirmation.baseline_package[0].text+=' changed';}],
  ['current_summary_label_differs_from_material_diff',x=>{x.package_confirmation.current_package[0].source_label+=' changed';}],
  ['current_outline_label_differs_from_original_source',x=>{x.package_confirmation.current_package[1].source_label+=' changed';}],
  ['manual_text_differs_from_note',x=>{x.package_confirmation.manual.text+=' changed';}],
 ]){
  const x=structuredClone(v);change(x);assert.throws(()=>s.materialPackageCheck(x,c));results.push({kind:'SYNTHETIC_DTO_VM_NOT_HTTP',name,expected_rejected:true,actual_rejected:true});
 }
}
{
 const {v,c}=dto(),s=env(v,c),unknown=structuredClone(v);
 unknown.state='UNKNOWN';unknown.can_resolve=false;unknown.action_requests={};unknown.preview_sha256=null;
 unknown.affected=unknown.preserved;unknown.preserved=[];
 Object.assign(unknown.package_confirmation,{baseline_package:null,preview_sha256:null,can_keep_and_continue:false,can_merge:false});
 Object.assign(unknown.package_confirmation.coverage,{coverage_known:false,coverage_satisfied:false});
 s.materialPackageCheck(unknown,c);results.push({kind:'SYNTHETIC_DTO_VM_NOT_HTTP',name:'UNKNOWN_false_false_no_actions_accepted',expected_accepted:true});
 const inherited=structuredClone(unknown);inherited.package_confirmation.outline_carriage_required=true;inherited.package_confirmation.coverage.required=true;s.materialPackageCheck(inherited,c);results.push({kind:'SYNTHETIC_DTO_VM_NOT_HTTP',name:'UNKNOWN_inherited_required_no_actions_accepted',expected_accepted:true});
 for(const [name,change] of [
 ['top_can_resolve_not_matching_requests',x=>{x.can_resolve=false;}],
 ['can_keep_not_matching_request',x=>{x.package_confirmation.can_keep_and_continue=false;}],
 ['can_merge_not_matching_request',x=>{x.package_confirmation.can_merge=false;}],
 ['UNKNOWN_inconsistent_coverage_booleans',x=>{x.state='UNKNOWN';x.can_resolve=false;x.action_requests={};x.package_confirmation.can_keep_and_continue=false;x.package_confirmation.can_merge=false;x.package_confirmation.coverage.coverage_known=false;}],
 ]){const x=structuredClone(v);change(x);assert.throws(()=>s.materialPackageCheck(x,c));results.push({kind:'SYNTHETIC_DTO_VM_NOT_HTTP',name,expected_rejected:true,actual_rejected:true});}
 const smuggled=structuredClone(v);smuggled.state='UNKNOWN';let rejected=false;try{s.materialPackageCheck(smuggled,c);}catch{rejected=true;}
 results.push({kind:'SYNTHETIC_DTO_VM_NOT_HTTP',name:'UNKNOWN_consistent_capabilities_and_actions_must_be_refused',expected_rejected:true,actual_rejected:rejected,review_finding:!rejected?'WIP_UI_UNKNOWN_ACTIONS_ACCEPTED':null,backend_authorization_bypass_proven:false});
}

async function writeCase(name,text,reason,manual,expectedPost){
 const {v,c}=dto(manual),s=env(v,c),store={},elements={'material-package-reason':{value:reason},'material-package-note':{value:text},'material-package-confirm':{checked:true}};
 Object.assign(s,{materialPackageStorage:'parkweave.material-package.v1.',materialPackageView:{...v,uiContext:c},materialPackageBusy:false,materialPackageCurrent:()=>true,planSourceConflictPending:()=>false,materialPackageHandles:()=>[],materialPackageControls:()=>{},$:(n)=>elements[n],localStorage:{getItem:k=>store[k]??null,setItem:(k,v)=>store[k]=v,removeItem:k=>delete store[k]},coldDigest:async x=>hash(JSON.stringify(x)),materialPackageReceipt:async()=>{},materialPackageRejected:()=>false});
 const calls=[];s.materialPackageCall=async(c,path,method,body,key)=>{calls.push({method,path,text:body.text,reason:body.reason});return {};};
 vm.runInContext(read('current-write.js'),s);
 let failure=null;try{await s.materialPackageWrite('MERGE_NOTE');}catch(e){failure=e.message;}
 assert.equal(calls.length,expectedPost,name+':'+failure);
 if(expectedPost){assert.equal(calls[0].text,text);assert.equal(calls[0].reason,reason);assert.equal(Object.keys(store).length,1);}
 else assert.equal(Object.keys(store).length,0);
 results.push({kind:'EXTRACTED_WRITE_VM_STUB_POST_NOT_HTTP',name,expected_POSTs:expectedPost,actual_POSTs:calls.length,text_codepoints:Array.from(text).length,text_UTF16_units:text.length,reason_codepoints:Array.from(reason).length,body_or_text_preserved:expectedPost===1,failure});
}
async function receiptRefreshFailure(status){
 const {v,c}=dto(),s=env(v,c),store={},elements={'material-package-reason':{value:'SYNTHETIC explicit reason'},'material-package-note':{value:v.note.text},'material-package-confirm':{checked:true},'material-package-status':{textContent:'CURRENT_PRIVATE_A'}};
 c.planGeneration=1;c.actor=hash(JSON.stringify({actor_id:'SYNTHETIC owner'}));v.actor_ref=c.actor;
 Object.assign(s,{materialPackageStorage:'parkweave.material-package.v1.',servicePlanGeneration:1,materialPackageView:{...v,uiContext:c},materialPackageBusy:false,
 materialPackageCurrent:x=>x&&x.planGeneration===s.servicePlanGeneration,servicePlanCurrent:x=>x?.generation===s.servicePlanGeneration,oppCurrent:()=>true,planSourceConflictPending:()=>false,
 materialPackageHandles:()=>Object.keys(store).map(name=>({name,...JSON.parse(store[name])})),materialPackageControls:()=>{},$:(n)=>elements[n],
 localStorage:{getItem:k=>store[k]??null,setItem:(k,v)=>store[k]=v,removeItem:k=>delete store[k]},coldDigest:async x=>hash(JSON.stringify(x)),materialPackageRejected:()=>false,
 oppCtx:()=>({id:c.id,caseId:c.caseId,prepGeneration:1}),oppRequire:()=>{},loadOpportunities:async()=>{},clears:0});
 s.clearDeniedPrivateViews=()=>{s.clears++;s.materialPackageBusy=false;elements['material-package-status'].textContent='CLEARED_PRIVATE';};
 s.loadServiceCasePlan=async()=>{s.servicePlanGeneration++;throw Object.assign(Error('SYNTHETIC current original-plan refresh failure'),{status,servicePlanContext:{generation:s.servicePlanGeneration}});};
 s.materialPackageCall=async(ctx,path,method,body,key)=>{const r={id:id(50),plan_id:c.planId,request_key:key,fingerprint:hash(JSON.stringify({preparation_id:c.id,...body})),action:body.action,coordination_only:true,actor_id:'SYNTHETIC owner',plan_note:{version:3,request:body}};return {schema:1,scope:'OWNER_NOTE_MATERIAL_PACKAGE',actor_ref:c.actor,preparation_id:c.id,case_id:c.caseId,run_id:id(3),plan_id:c.planId,automatically_replayed:false,status:'COMMITTED',receipt:r,current:{history:[r],card_id:c.selection}};};
 vm.runInContext(read('current-receipt.js')+'\n'+read('new-error-handler.js')+'\n'+read('current-write.js'),s);
 let caught;try{await s.materialPackageWrite('KEEP_AND_CONTINUE');}catch(e){caught=e;s.materialPackageError(e);}
 assert(caught);assert.equal(Object.keys(store).length,1,'opaque handle must remain');
 const correct=!s.materialPackageBusy&&(status!==403||s.clears===1);
 results.push({kind:'EXTRACTED_RECEIPT_REFRESH_VM_NOT_HTTP',name:'same_case_self_refresh_failure_'+status,expected_busy:false,actual_busy:s.materialPackageBusy,expected_current403_clears:status===403?1:0,actual_clears:s.clears,opaque_handle_retained:true,old_generation:c.planGeneration,new_generation:s.servicePlanGeneration,review_finding:correct?null:'WIP_SELF_REFRESH_ERROR_STUCK_BUSY_OR_CURRENT403_IGNORED',backend_authorization_bypass_proven:false});
}

(async()=>{
 await receiptRefreshFailure(403);
 await receiptRefreshFailure(503);
 await writeCase('2100_emoji_merge_codepoints_under4000','SYNTHETIC manual\n'+'😀'.repeat(2100),'SYNTHETIC explicit reason','SYNTHETIC manual',1);
 await writeCase('600_emoji_reason_under1000','SYNTHETIC manual','😀'.repeat(600),'SYNTHETIC manual',1);
 await writeCase('Python_nonempty_BOM_preserved','\ufeff','\ufeff','\ufeff',1);
 await writeCase('4001_actual_codepoints_refused_before_storage','SYNTHETIC manual'+'x'.repeat(4001),'SYNTHETIC reason','SYNTHETIC manual',0);
 await writeCase('1001_reason_codepoints_refused_before_storage','SYNTHETIC manual','x'.repeat(1001),'SYNTHETIC manual',0);
 await writeCase('legal_codepoints_but_over16KiB_body_refused','SYNTHETIC manual'+'😀'.repeat(3980),'x'.repeat(1000),'SYNTHETIC manual',0);
 fs.writeFileSync(P+'/probe-result.json',JSON.stringify({status:results.some(r=>r.review_finding)?'WIP_FINDING_OBSERVED_NOT_FROZEN':'PASS_WIP_VM_ONLY_NOT_FROZEN',units:results.length,results,real_HTTP:false,owned_PG:false,real_browser:false,business_or_Git_writes:false,API_permission_or_history_safety_proven:false},null,2)+'\n');
 console.log(JSON.stringify({status:results.some(r=>r.review_finding)?'WIP_FINDING_OBSERVED_NOT_FROZEN':'PASS_WIP_VM_ONLY_NOT_FROZEN',units:results.length,real_HTTP:false,owned_PG:false}));
})().catch(e=>{fs.writeFileSync(P+'/probe-failure.json',JSON.stringify({status:'FAIL_WIP_PROBE_NO_FINAL_PASS',error:e.message,stack:e.stack,results},null,2)+'\n');console.error(e.stack);process.exitCode=1;});
