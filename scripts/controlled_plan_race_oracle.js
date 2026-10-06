(async()=>{
const pending=[],checks={},tick=()=>new Promise(resolve=>setTimeout(resolve,0));
window.fetch=(path,options)=>new Promise(resolve=>pending.push({path,options,resolve}));
const take=path=>{const i=pending.findIndex(q=>q.path===path);if(i<0)throw Error('Missing '+path);return pending.splice(i,1)[0];},last=path=>{const i=pending.findLastIndex(q=>q.path===path);if(i<0)throw Error('Missing latest '+path);return pending.splice(i,1)[0];};
const response=(q,data,status=200)=>q.resolve({ok:status<400,status,json:async()=>data});
const path=id=>'/api/preparations/'+id+'/controlled-plan';
const item=(id,revision=1,role='enterprise_operator',started=true)=>({preparation_id:id,plan_id:started?'plan-'+id:null,template_sha256:'a'.repeat(64),role,revision:started?revision:undefined,preparation_revision:started?undefined:4,state:started?'IN_PROGRESS':'NOT_STARTED',can_create:!started,steps:started?[{id:'P1',state:'PENDING',source_sha256:'b'.repeat(64),issues:[],can_check:role==='enterprise_operator'}]:[],history:[]});
const token=t=>{$('token').value=t;$('token').dispatchEvent(new Event('input'));},load=id=>loadPlan(id).catch(planError);
const ready=async(id,rev=1,role='enterprise_operator',started=true)=>{const p=load(id);response(last(path(id)),item(id,rev,role,started));await p;};
const send=step=>planWrite(step).catch(planError);
token('SYNTHETIC-owner');let late=load('A');await ready('B');response(take(path('A')),item('A'));await late;checks.late_GET_keeps_selection=planId==='B'&&planView.preparation_id==='B';
late=load('A');token('another');response(take(path('A')),item('A'));await late;checks.token_clears=planView===null&&$('plan-detail').hidden;
await ready('A');late=load('A');await ready('B');await ready('A',3);response(take(path('A')),item('A',1));await late;checks.ABA_keeps_revision=planView.revision===3;
await ready('A');$('plan-reason').value='SYNTHETIC draft';let command=send('P1');await tick();let q=take(path('A')+'/commands');const body=JSON.parse(q.options.body);checks.CHECK_binds_snapshot=body.step==='P1'&&body.expected_revision===1&&body.expected_source_sha256==='b'.repeat(64);await ready('B');response(q,item('A',2));await command;checks.late_POST_no_followup=planId==='B'&&!pending.length;
await ready('A');$('plan-reason').value='SYNTHETIC draft';command=send('P1');await tick();q=take(path('A')+'/commands');clearPlan();response(q,item('A',2));await command;checks.back_invalidates_write=planView===null&&!pending.length;
await ready('A');$('plan-reason').value='SYNTHETIC draft';command=send('P1');await tick();q=take(path('A')+'/commands');await ready('B');response(q,{},403);await command;checks.stale_403_ignored=planId==='B';
await ready('A');$('plan-reason').value='SYNTHETIC draft';command=send('P1');await tick();q=take(path('A')+'/commands');response(q,{},403);await command;checks.current_403_clears=planView===null&&preparationView===null&&dispatchView===null&&receiptView===null&&$('page-feedback').textContent.length>0;
await ready('A');$('plan-reason').value='old';command=send('P1');await tick();q=take(path('A')+'/commands');$('plan-reason').value='new';response(q,{},409);await command;checks.new_draft_error_ignored=$('plan-reason').value==='new'&&$('plan-error').textContent==='';
await ready('A');$('plan-reason').value='old';command=send('P1');await tick();q=take(path('A')+'/commands');$('plan-reason').value='new';response(q,item('A',2));await tick();response(take(path('A')),item('A',2));await command;checks.new_draft_success_preserved=$('plan-reason').value==='new'&&planView.revision===2;
await ready('A',1,'enterprise_operator',false);$('plan-reason').value='not submitted with CREATE';command=send(null);await tick();q=take(path('A'));checks.CREATE_explicit_local_goal=JSON.parse(q.options.body).required_goals[0]==='LOCAL_SYNTHETIC_COORDINATION_RECORDS';response(q,item('A',1));await tick();response(take(path('A')),item('A',1));await command;checks.CREATE_preserves_unused_draft=$('plan-reason').value==='not submitted with CREATE';
await ready('A',1,'enterprise_operator',false);$('plan-reason').value='old';command=send(null);await tick();q=take(path('A'));$('plan-reason').value='new';response(q,item('A',1));await tick();response(take(path('A')),item('A',1));await command;checks.CREATE_new_draft_preserved=$('plan-reason').value==='new';
await ready('A',1,'service_executor');checks.executor_no_material_route=$('plan-materials').hidden&&$('plan-P1').hidden&&!$('plan-dispatch').hidden;
await ready('A');late=load('B');document.querySelector('[data-tab=resource]').click();response(take(path('B')),item('B'));await late;checks.navigation_clears=planView===null&&$('plan-detail').hidden;
for(const [name,mutate] of [['id',()=>planView.preparation_id='other'],['revision',()=>planView.revision=3],['template',()=>planView.template_sha256='c'.repeat(64)]]){await ready('A');$('plan-reason').value='SYNTHETIC';mutate();let caught=false;try{await planWrite('P1');}catch(e){caught=true;}checks[name+'_guard']=caught&&!pending.length;}
return JSON.stringify({scope:'CONTROLLED_RESPONSE_ORDER_ONLY',checks});
})()
