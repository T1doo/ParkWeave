(async()=>{
const pending=[], writes=[];const tick=()=>new Promise(r=>setTimeout(r,0));
window.fetch=(path,options)=>new Promise(resolve=>pending.push({path,options,resolve}));
const response=(q,x,status=200)=>q.resolve({ok:status<400,status,json:async()=>x});
const take=path=>{const i=pending.findIndex(q=>q.path===path);if(i<0)throw Error('Missing synthetic request '+path);return pending.splice(i,1)[0];};
const detail=id=>({preparation:{id,case_id:'case-'+id,goal:'SYNTHETIC '+id,state:'IN_PREPARATION',revision:1},current_materials:[],material_history:[],history:[]});
const switchRole=token=>{$('token').value=token;$('token').dispatchEvent(new Event('input'));prepRole=token==='enterprise'?'enterprise_operator':'service_specialist';};
const load=id=>loadPreparation(id).catch(prepError);
const ready=async id=>{const p=load(id);const i=pending.findLastIndex(q=>q.path==='/api/preparations/'+id);response(pending.splice(i,1)[0],detail(id));await p;};
const fill=text=>{$('prep-text').value=text;$('prep-source-label').value='SYNTHETIC v1';};
const checks={};switchRole('enterprise');
await ready('A');fill('A draft');$('prep-reason').value='A reason';await ready('B');const carried=$('prep-text').value==='A draft'&&$('prep-source-label').value==='SYNTHETIC v1'&&$('prep-reason').value==='A reason';switchRole('enterprise');
const old=load('A');await ready('B');fill('B draft');response(take('/api/preparations/A'),detail('A'));await old;
const oldCase=preparationId==='A';
const write=prepCommand('ADD_EVIDENCE').catch(prepError);await tick();
let q=pending.find(x=>x.path.endsWith('/commands'));const wrongWrite=!!q&&q.path==='/api/preparations/A/commands';
if(q){writes.push({path:q.path,body:JSON.parse(q.options.body)});pending.splice(pending.indexOf(q),1);response(q,{});await tick();q=pending.find(x=>x.path.startsWith('/api/preparations/'));if(q){pending.splice(pending.indexOf(q),1);response(q,detail(q.path.split('/').pop()));}}await write;
checks.selection_and_write_target=!oldCase&&!wrongWrite&&writes[0]?.path==='/api/preparations/B/commands';
switchRole('enterprise');const identity=load('A');switchRole('specialist');response(take('/api/preparations/A'),detail('A'));await identity;
const oldIdentity=preparationView!==null;checks.identity_clears_pending=!oldIdentity&&$('prep-detail').hidden;
switchRole('enterprise');await ready('A');fill('A original');const delayedWrite=prepCommand('ADD_EVIDENCE').catch(prepError);await tick();q=take('/api/preparations/A/commands');await ready('B');fill('B preserved');response(q,{});await tick();let stale=pending.find(x=>x.path.startsWith('/api/preparations/'));if(stale){pending.splice(pending.indexOf(stale),1);response(stale,detail(stale.path.split('/').pop()));}await delayedWrite;
checks.late_write_preserves_new_draft=preparationId==='B'&&$('prep-text').value==='B preserved';
switchRole('enterprise');await ready('A');fill('first');const editing=prepCommand('ADD_EVIDENCE').catch(prepError);await tick();q=take('/api/preparations/A/commands');fill('edited while pending');response(q,{});await tick();stale=pending.find(x=>x.path==='/api/preparations/A');if(stale){pending.splice(pending.indexOf(stale),1);response(stale,detail('A'));}await editing;
checks.late_write_preserves_same_case_edit=$('prep-text').value==='edited while pending';
// Current failure keeps its draft and identical retries reuse the key.
await ready('B');fill('retry');const failed=prepCommand('ADD_EVIDENCE').catch(prepError);await tick();q=take('/api/preparations/B/commands');const key=q.options.headers['Idempotency-Key'];response(q,{},409);await failed;
checks.failure_preserves_draft=$('prep-text').value==='retry'&&$('prep-error').textContent.length>0;
const repeated=prepCommand('ADD_EVIDENCE').catch(prepError);await tick();q=take('/api/preparations/B/commands');checks.retry_key=q.options.headers['Idempotency-Key']===key;response(q,{});await tick();response(take('/api/preparations/B'),detail('B'));await repeated;
checks.normal_success=$('prep-text').value===''&&preparationId==='B';
// Delayed forbidden must not clear a newer selection.
const denied=load('A');await ready('B');fill('safe B');response(take('/api/preparations/A'),{},403);await denied;checks.stale_failure_ignored=preparationId==='B'&&$('prep-text').value==='safe B';
// Returning to A does not revive its previous response (ABA).
const aba=load('A');await ready('B');await ready('A');fill('new A');response(take('/api/preparations/A'),{...detail('A'),preparation:{...detail('A').preparation,goal:'OLD A'}});await aba;checks.return_generation=$('prep-summary').textContent.startsWith('SYNTHETIC A')&&$('prep-text').value==='new A';
if(expectVulnerable)return JSON.stringify({old_case_overwrites_selection:oldCase,wrong_case_write:wrongWrite,old_identity_restored:oldIdentity,cross_case_draft_carried:carried,checks,synthetic_writes:writes});
// Cross-case drafts (including source and human reason) are never carried over.
await ready('A');fill('A-only');$('prep-source-kind').value='DOCUMENT_EXCERPT';$('prep-reason').value='A reason';await ready('B');checks.cross_case_drafts_cleared=$('prep-text').value===''&&$('prep-source-label').value===''&&$('prep-reason').value===''&&$('prep-source-kind').value==='USER_STATEMENT';
fill('refresh draft');const refresh=load('B');response(take('/api/preparations/B'),detail('B'));await refresh;checks.refresh_preserves_current_draft=$('prep-text').value==='refresh draft';
preparationView.preparation.id='A';let mismatch=false;try{await prepCommand('ADD_EVIDENCE');}catch(e){mismatch=true;}checks.submit_id_guard=mismatch&&!pending.length;
await ready('B');preparationView.preparation.revision=null;mismatch=false;try{await prepCommand('ADD_EVIDENCE');}catch(e){mismatch=true;}checks.submit_revision_guard=mismatch&&!pending.length;
await ready('B');preparationView.preparation.case_id='case-A';mismatch=false;try{await prepCommand('ADD_EVIDENCE');}catch(e){mismatch=true;}checks.submit_case_guard=mismatch&&!pending.length;
await ready('B');preparationView.preparation.revision=2;mismatch=false;try{await prepCommand('ADD_EVIDENCE');}catch(e){mismatch=true;}checks.submit_snapshot_revision_guard=mismatch&&!pending.length;
// Catalogue/list requests from a departed identity cannot populate the new role UI.
switchRole('enterprise');$('prep-catalog').click();const catalog=take('/api/preparation-catalog');switchRole('specialist');response(catalog,{services:[{name:'OLD',version:1,source:{kind:'SYNTHETIC',statement:'old'}}],reviewers:[]});await tick();checks.stale_catalog_ignored=prepCatalog===null&&$('prep-catalog-view').textContent==='';
$('prep-list').click();const listing=take('/api/preparations');switchRole('enterprise');response(listing,{role:'service_specialist',items:[{id:'A',goal:'OLD',state:'IN_PREPARATION'}]});await tick();checks.stale_list_ignored=$('prep-items').textContent===''&&prepRole==='enterprise_operator';
// Tab cancellation and New catalogue navigation invalidate detail reads.
const cancelled=load('A');$('resource').hidden=false;document.querySelector('[data-tab=resource]').click();response(take('/api/preparations/A'),detail('A'));await cancelled;checks.cancel_navigation=preparationView===null&&$('prep-detail').hidden;
switchRole('enterprise');const newer=load('A');$('prep-catalog').click();response(take('/api/preparations/A'),detail('A'));await newer;response(take('/api/preparation-catalog'),{services:[],reviewers:[]});await tick();checks.new_navigation=preparationView===null;
// A pending create is tied to the originating identity/navigation too.
switchRole('enterprise');prepCatalog={services:[{service_id:'synthetic',version:1}],reviewers:[]};$('prep-goal').value='SYNTHETIC pending new';const creating=$('prep-create').onsubmit({preventDefault(){}});const runCreate=take('/api/runs');switchRole('specialist');response(runCreate,{run_id:'synthetic-run'});await creating;checks.cancelled_create_no_followup=preparationView===null&&!pending.length;
return JSON.stringify({old_case_overwrites_selection:oldCase,wrong_case_write:wrongWrite,old_identity_restored:oldIdentity,checks,synthetic_writes:writes});
})()
