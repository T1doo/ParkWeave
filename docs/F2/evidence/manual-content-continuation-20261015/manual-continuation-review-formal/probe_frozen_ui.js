const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const path=require('node:path');
const here=__dirname;
const functions=fs.readFileSync(path.join(here,'frozen-ui-functions.js'),'utf8');
const source=JSON.parse(fs.readFileSync(path.join(here,'frozen-ui-source.json'),'utf8'));
const results=[];

async function run(action){
 const dto=JSON.parse(fs.readFileSync(path.join(here,'probes/freeze-ef16f7c-probes-'+action.toLowerCase()+'-dto.json'),'utf8'));
 const storage={};let removals=0,posts=0;
 Object.defineProperties(storage,{
  getItem:{value(key){return Object.hasOwn(this,key)?this[key]:null;}},
  setItem:{value(key,value){this[key]=String(value);}},
  removeItem:{value(key){removals++;delete this[key];}}
 });
 const nodes={
  'plan-source-conflict-note':{value:dto.note.text+(action==='MERGE_NOTE'?'\nSYNTHETIC explicit merged draft':'')},
  'plan-source-conflict-reason':{value:'SYNTHETIC explicit continuation'},
  'plan-source-conflict-confirm':{checked:true}
 };
 const c={id:dto.preparation_id,caseId:dto.case_id,planId:dto.plan_id,actor:dto.actor_ref,token:'OFFLINE_SYNTHETIC_VM_TRANSPORT_ONLY'};
 const sandbox={TextEncoder,crypto:webcrypto,localStorage:storage,console,
  $:id=>{assert(nodes[id],id);return nodes[id];},
  servicePlanView:{revision:dto.plan_revision},
  preparationView:{preparation:{run_id:dto.run_id}},
  planSourceConflictCurrent:()=>true,
  planSourceConflictControls:()=>{},
  entryFetch:async(url,options)=>{posts++;assert.equal(options.method,'POST');return {ok:false,status:409,json:async()=>({detail:'SYNTHETIC bounded final source unavailable'})};},
  dto,c
 };
 const context=vm.createContext(sandbox);
 vm.runInContext(`const planSourceConflictStorage='parkweave.plan-source-conflict.v1.';const planSourceConflictActions=['EDIT_NOTE','KEEP_MANUAL','ACCEPT_SOURCE','DEFER','KEEP_AND_CONTINUE','MERGE_NOTE'];var planSourceConflictView=dto,planSourceConflictBusy=false;dto.uiContext=c;\n`+functions,context);
 let failure;
 try{await context.planSourceConflictWrite(action);}catch(error){failure=error;}
 assert.equal(failure?.status,409,failure?.stack);
 const handles=context.planSourceConflictHandles();
 assert.equal(posts,1);assert.equal(removals,0);assert.equal(handles.length,1);assert.equal(handles[0].action,action);
 const original=JSON.stringify(handles);
 const notObserved={scope:'OWNER_PLAN_SOURCE_CONFLICT',schema:1,actor_ref:c.actor,preparation_id:c.id,case_id:c.caseId,run_id:dto.run_id,plan_id:c.planId,automatically_replayed:false,status:'NOT_OBSERVED',receipt:null};
 let coldFailure;
 try{await context.planSourceConflictReceipt(notObserved,c,handles[0]);}catch(error){coldFailure=error;}
 assert(coldFailure);assert.equal(JSON.stringify(context.planSourceConflictHandles()),original);assert.equal(removals,0);assert.equal(posts,1);
 results.push({action,generic_HTTP409_retains_exact_opaque_handle:true,NOT_OBSERVED_retains_same_handle:true,POST_count:posts,automatic_rePOST:false,body_or_reason_or_token_in_handle:false});
 const stored=JSON.parse(storage.getItem(handles[0].name));
 assert.deepEqual(Object.keys(stored).sort(),['schema','id','actor','plan','key','action','fingerprint','card'].sort());
}

(async()=>{
 for(const action of ['KEEP_AND_CONTINUE','MERGE_NOTE'])await run(action);
 const result={status:'PASS_FROZEN_EXTRACTED_FUNCTIONS_WITH_SYNTHETIC_DOM_CONTEXT_TRANSPORT_ONLY',web_sha256:source.web_sha256,results,checks:4,actual_browser:false,full_HTML_HTTP_ASGI_PG:false,actual_authority_gate_tested_here:false};
 fs.writeFileSync(path.join(here,'frozen-ui-probe-result.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
})().catch(error=>{console.error(error);process.exitCode=1;});
