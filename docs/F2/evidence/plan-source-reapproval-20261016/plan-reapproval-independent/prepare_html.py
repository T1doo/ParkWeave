from pathlib import Path
r=Path('/workspace/ParkWeave');d=r/'.runtime/plan-reapproval-independent/candidate/tests'
s=(r/'tests/unified_dependency_propagation_real_html.js').read_text();s=s[:s.index('// Flow body will be bound')]
s=s.replace("  append(...values) { this.children.push(...values); }","  append(...values) { this.children.push(...values); }\n  prepend(...values) { this.children.unshift(...values); }")
s=s.replace("path.includes('dependency_scope=BOUNDED_MULTI_SOURCE_V1')","path.endsWith('/plan-approval')")
s+='''
(async()=>{
 const config=await initialized,storage={},calls=[],transport={};diagnostics={calls};
 let p=page(config,storage,calls,transport),{$,run}=p;
 const output=()=>console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_PLAN_SOURCE_REAPPROVAL_ACTUAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,calls,real_browser:'NOT_RUN',fake_dto:false}));
 const load=async row=>{await run(`loadPreparation(${JSON.stringify(row.preparation_id)},{role:'enterprise_operator'})`);await $('opp-read').onclick();};
 const resource=async(row,ids=[])=>{await $('resource-catalog').onclick();await $('resource-mine').onclick();for(const id of ids){const box=run("document.querySelectorAll('[data-combination-hold]')").find(e=>e.dataset.combinationHold===id);check(!!box,'actual original held member checkbox');box.checked=true;box.onchange();}$('delivery-case').value=row.preparation_id;$('delivery-case').emit('input');};
 if(['current_403','late_403'].includes(config.mode)){
   await resource(config.A);await $('plan-approval-read').onclick();check(!!run('planApprovalView'),'original actual old approved history read');
   transport.revokeBeforeRead=true;
   if(config.mode==='current_403'){
     await $('plan-approval-read').onclick();check(calls.at(-1).status===403,'actual current original read403');
     check(run('planApprovalView')===null&&run('planApprovalSelected')===null&&run('deliveryQuote')===null,'current denial clears original private approval and quote');
   }else{
     transport.ready=new Promise(resolve=>transport.held=resolve);transport.release=new Promise(resolve=>transport.resume=resolve);transport.hold=c=>c.path.endsWith('/plan-approval');
     const old=$('plan-approval-read').onclick();check((await transport.ready).status===403,'held actual old403');
     $('token').value='SYNTHETIC_REAPPROVAL_OTHER';$('token').emit('input');$('token').value=config.token;$('token').emit('input');
     await control('restore');await resource(config.B);await $('plan-approval-read').onclick();const now=run('planApprovalView');check(now?.preparation_id===config.B.preparation_id,'new Case actual original approval view');
     transport.resume();await old;check(run('planApprovalView')===now,'late403 afteridentityABA preservesnewCase');
   }
   check(calls.every(c=>c.method==='GET'),'authority modes have reads only');output();process.exit(0);
 }
 await load(config.A);
 $('opp-generation').value='1';$('opp-kind').value='LOCAL_CASE_DATA';$('opp-catalog').value=String(run('oppView.current_basis.catalog[0].version'));
 $('opp-title').value='SYNTHETIC actual source change needs new capacity approval';$('opp-note').value='Hint alone is no fact or authority';$('opp-purpose').checked=true;$('opp-reason').value='SYNTHETIC original explicit import';await $('opp-import').onsubmit({preventDefault(){}});
 const card=run('oppView.cards.find(c=>c.is_latest_generation).id');await control('change_sources');await $('opp-read').onclick();$('opp-reason').value='SYNTHETIC explicit actual source refresh';await $('opp-refresh').onclick();
 const preview=run("document.querySelectorAll('[data-opp-plan-preview]')").find(e=>e.dataset.oppPlanPreview===card);check(!!preview,'original source revision preview button');await preview.onclick();
 check(run('opportunityPlanView.can_adopt')===true,'actual source local revision admissible');check(run('opportunityPlanView.affected.length')===5,'literal all5 source invalidation');
 $('service-plan-reason').value='SYNTHETIC explicit original source ADOPT';$('opp-plan-confirm').checked=true;await $('opp-plan-adopt').onclick();check(calls.some(c=>c.method==='POST'&&c.path.endsWith('/service-case-plan')&&c.status===201),'actual original source ADOPT');
 await control('repair_material');await run(`loadServiceCasePlan(${JSON.stringify(config.A.preparation_id)})`);let step=run("servicePlanView.steps.find(s=>s.adapter_id==='P1').id");$('service-plan-reason').value='SYNTHETIC actual original P1 VERIFY';await run(`servicePlanWrite('VERIFY',${JSON.stringify(step)})`);check(run("servicePlanView.steps[0].state")==='VERIFIED','original P1 reverified before new approval');
 const hs=await control('fresh_holds');await resource(config.A,hs.holds);
 check($('delivery-reapproval').disabled===false,'explicit isolated source reapproval enabled');check(!$('delivery-reapproval').checked,'new mode needs explicit checkbox');
 $('delivery-reapproval').checked=true;$('delivery-reapproval').emit('change');await $('plan-approval-read').onclick();await $('delivery-preview').onclick();check(!!run('deliveryQuote'),'actual explicit reapproval quote');check(run('deliveryQuote.view.expected_link_revision')===1,'literal oldlink revision1 bound');
 const n=calls.filter(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery')).length;await $('delivery-confirm').onclick();check(calls.filter(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery')).length===n,'unapproved quote cannot commit resources');
 // The guarded original onclick may clear only an unapproved quote; reread it.
 if(!run('deliveryQuote'))await $('delivery-preview').onclick();
 await $('plan-approval-propose').onclick();check(run('planApprovalSelected.state')==='PROPOSED','actual original proposal');check(run('planApprovalSelected.purpose')==='CASE_RESOURCE_REAPPROVAL','explicit bounded reapproval purpose');
 await $('plan-approval-approve').onclick();check(run('planApprovalSelected.current_available')===true,'actual original explicit APPROVE');
 await control('before_commit');if(config.mode==='lost_ack')transport.dropPath='/resource-delivery';await $('delivery-confirm').onclick();
 if(config.mode==='lost_ack'){
   check(Object.keys(storage).some(k=>k.startsWith('parkweave.case-resource-delivery.v1.')),'lost commit keeps original opaque handle');
   for(const [key,value] of Object.entries(storage)){check(!value.includes(config.token),'storage has no token');if(key.startsWith('parkweave.case-resource-delivery.v1.'))check(Object.keys(JSON.parse(value)).sort().join(',')==='actor,id,key','deliveryhandle excludes bodies sourcevalues and approvals');}
   const n=calls.length;p=page(config,storage,calls,transport);({$,run}=p);await resource(config.A);await $('delivery-recover').onclick();
   check(calls.slice(n).every(c=>c.method==='GET'),'cold original delivery recovery sends GET only');
   const post=calls.find(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery'));check(calls.slice(n).some(c=>c.path.endsWith('/resource-delivery/recovery/'+post.request_key)&&c.status===200),'cold GET exact original committed key');
 }
 check(calls.filter(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery')&&c.status===201).length===1,'one actual resource reapproval COMMIT');await control('after_commit');
 await load(config.A);
 for(const adapter of ['P2','P3','P4','P5']){
   if(adapter!=='P2')await control({P3:'reoffer_accept',P4:'new_report_ack',P5:'revalidate_local'}[adapter]);
   await run(`loadServiceCasePlan(${JSON.stringify(config.A.preparation_id)})`);step=run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).id`);$('service-plan-reason').value='SYNTHETIC actual original '+adapter+' VERIFY';await run(`servicePlanWrite('VERIFY',${JSON.stringify(step)})`);check(run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).state`)==='VERIFIED','actual original '+adapter+' VERIFIED');
 }
 await $('goal-results-read').onclick();check(run('goalResultView.results.length')===6&&run('goalResultView.state')==='LOCAL_OUTPUTS_VERIFIED','all original six local outputs');await $('case-worklist-read').onclick();
 for(let i=0;i<4&&!$('case-worklist-next').hidden;i++)await $('case-worklist-next').onclick();
 check(calls.some(c=>c.worklist_items?.some(r=>r.case_id===config.A.case_id&&r.case_goal_completed===false)),'actual current Case in original worklist');await control('final_evidence');output();process.exit(0);
})().catch(error=>{console.error(JSON.stringify({message:error.message,stack:error.stack,diagnostics}));process.exit(1);});
'''
(d/'plan_source_reapproval_real_html.js').write_text(s)
