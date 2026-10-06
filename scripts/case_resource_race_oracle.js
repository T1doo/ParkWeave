(async()=>{
const pending=[],checks={},tick=()=>new Promise(r=>setTimeout(r,0));
window.fetch=(path,options)=>new Promise(resolve=>pending.push({path,options,resolve}));
const take=path=>{const i=pending.findIndex(q=>q.path===path);if(i<0)throw Error('Missing synthetic request '+path);return pending.splice(i,1)[0];};
const response=(q,x,status=200)=>q.resolve({ok:status<400,status,json:async()=>x});
const base=id=>'/api/preparations/'+id+'/resource-link';
const switchToken=t=>{$('token').value=t;$('token').dispatchEvent(new Event('input'));};
const select=id=>{clearPreparation();prepRole='enterprise_operator';preparationId=id;preparationView={preparation:{id,state:'LOCAL_CONFIRMED',revision:5}};preparationContext={...prepContext(),revision:5};};
const view=(id,revision=0)=>({case_id:'case-'+id,case_state:'NEEDS_INPUT',preparation_revision:5,link_revision:revision,current:null,history:[]});
const catalog=()=>({ready:true,preparation_revision:5,items:['A','B'].map(id=>({eligible:true,reason:'CURRENT',combination:{id,members:[{resource_name:'SYNTHETIC '+id,starts_at:'2030-01-01',ends_at:'2030-01-02'}]}}))});
const finishRead=async(id,p,revision=0)=>{response(take(base(id)),view(id,revision));await tick();response(take(base(id)+'-candidates'),catalog());await p;};
const ready=async(id='P',revision=0)=>{select(id);const p=loadCaseResources().catch(caseResourceError);await finishRead(id,p,revision);};
const fill=(choice='A',reason='SYNTHETIC first')=>{$('case-resource-choice').value=choice;$('case-resource-reason').value=reason;};
const submit=()=>$('case-resource-form').onsubmit({preventDefault(){}});
switchToken('synthetic-owner');await ready();fill();let p=submit(),q=take(base('P'));const firstBody=q.options.body,firstKey=q.options.headers['Idempotency-Key'];checks.frozen_write=JSON.parse(firstBody).combination_id==='A'&&JSON.parse(firstBody).expected_preparation_revision===5&&JSON.parse(firstBody).expected_link_revision===0;response(q,{detail:'stale Case resource link revision; refresh required'},409);await p;checks.failure_preserves_input=$('case-resource-reason').value==='SYNTHETIC first'&&$('case-resource-error').textContent.includes('关联版本');
p=submit();q=take(base('P'));checks.same_input_same_key=q.options.body===firstBody&&q.options.headers['Idempotency-Key']===firstKey;fill('B','SYNTHETIC first');response(q,{});await tick();await finishRead('P',p,1);checks.late_success_keeps_new_selection_and_same_reason=$('case-resource-choice').value==='B'&&$('case-resource-reason').value==='SYNTHETIC first';
fill('B','new text');p=submit();q=take(base('P'));fill('A','changed after send');response(q,{});await tick();await finishRead('P',p,2);checks.late_success_keeps_new_text=$('case-resource-choice').value==='A'&&$('case-resource-reason').value==='changed after send';
p=submit();q=take(base('P'));response(q,{});await tick();await finishRead('P',p,3);checks.normal_success_clears_reason=$('case-resource-reason').value==='';
for(const status of [409,422]){fill('A','sending '+status);p=submit();q=take(base('P'));fill('B','new '+status);response(q,{detail:'RESOURCE_CANCELLED'},status);await p;checks['late_error_ignores_new_draft_'+status]=$('case-resource-choice').value==='B'&&$('case-resource-reason').value==='new '+status&&!$('case-resource-panel').hidden&&$('case-resource-error').textContent==='';}
fill('B','manual refresh');p=loadCaseResources().catch(caseResourceError);checks.pending_refresh_disables_form=$('case-resource-form').hidden;await finishRead('P',p,3);checks.manual_refresh_preserves_full_draft=$('case-resource-choice').value==='B'&&$('case-resource-reason').value==='manual refresh';
p=loadCaseResources().catch(caseResourceError);q=take(base('P'));await ready('Q',2);fill('B','safe Q');response(q,view('P'));await p;checks.late_case_read_ignored=caseResourceContext.id==='Q'&&$('case-resource-reason').value==='safe Q'&&!pending.length;
p=submit();q=take(base('Q'));await ready('R');fill('A','safe R');response(q,{});await p;checks.late_case_write_no_reload=caseResourceContext.id==='R'&&$('case-resource-reason').value==='safe R'&&!pending.length;
p=loadCaseResources().catch(caseResourceError);q=take(base('R'));switchToken('new-identity');response(q,view('R'));await p;checks.identity_clears_private_view=caseResourceView===null&&$('case-resource-panel').hidden&&$('case-resource-reason').value==='';
await ready('P');fill();preparationView.preparation.revision=6;await submit();checks.preparation_revision_guard=!pending.length&&$('case-resource-error').textContent.includes('版本');
await ready('P');p=loadCaseResources().catch(caseResourceError);q=take(base('P'));document.querySelector('[data-tab=resource]').click();response(q,view('P'));await p;checks.navigation_clears_link=caseResourceView===null&&$('case-resource-panel').hidden&&!pending.length;
await ready('P');fill();p=submit();q=take(base('P'));fill('B','new draft after authorization revoked');response(q,{},403);await p;checks.current_forbidden_clears_private_view=caseResourceView===null&&$('case-resource-panel').hidden&&$('case-resource-reason').value===''&&$('prep-error').textContent.includes('授权');
return JSON.stringify({checks});
})()
