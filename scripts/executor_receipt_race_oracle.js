(async()=>{
const pending=[],checks={};const tick=()=>new Promise(r=>setTimeout(r,0));
window.fetch=(path,options)=>new Promise(resolve=>pending.push({path,options,resolve}));
const take=path=>{const i=pending.findIndex(q=>q.path===path);if(i<0)throw Error('Missing synthetic request '+path);return pending.splice(i,1)[0];};
const response=(q,x,status=200)=>q.resolve({ok:status<400,status,json:async()=>x});
const detail=(id,revision=1,role='service_executor')=>({role,step:{id,goal:'SYNTHETIC '+id,state:'AWAITING_RECEIPT',revision},current_receipt:null,history:[],receipt_history:[],dependency:'CURRENT'});
const switchToken=token=>{$('token').value=token;$('token').dispatchEvent(new Event('input'));};
const load=id=>loadReceipt(id).catch(receiptError);
const ready=async(id,revision=1)=>{const p=load(id),i=pending.findLastIndex(q=>q.path==='/api/executor-receipts/'+id);response(pending.splice(i,1)[0],detail(id,revision));await p;};
const fill=t=>{$('receipt-text').value=t;$('receipt-source').value='SYNTHETIC v1';};
switchToken('synthetic-executor');await ready('A');fill('A draft');$('receipt-reason').value='A reason';await ready('B');checks.cross_step_drafts_cleared=$('receipt-text').value===''&&$('receipt-source').value===''&&$('receipt-reason').value==='';
const delayed=load('A');await ready('B');fill('B draft');response(take('/api/executor-receipts/A'),detail('A'));await delayed;checks.late_detail_preserves_selection=receiptId==='B'&&$('receipt-text').value==='B draft';
const post=receiptCommand('SUBMIT').catch(receiptError);await tick();let q=take('/api/executor-receipts/B/commands');checks.write_target_snapshot=JSON.parse(q.options.body).expected_revision===1&&JSON.parse(q.options.body).text==='B draft';response(q,{},409);await post;checks.failure_preserves_draft=$('receipt-text').value==='B draft'&&$('receipt-error').textContent.length>0;
const key=q.options.headers['Idempotency-Key'],body=q.options.body;const retry=receiptCommand('SUBMIT').catch(receiptError);await tick();q=take('/api/executor-receipts/B/commands');checks.same_input_retry_frozen=q.options.headers['Idempotency-Key']===key&&q.options.body===body;response(q,{});await tick();response(take('/api/executor-receipts/B'),detail('B',2));await retry;checks.normal_success_clears_draft=$('receipt-text').value==='';
await ready('A');fill('A send');const lateWrite=receiptCommand('SUBMIT').catch(receiptError);await tick();q=take('/api/executor-receipts/A/commands');await ready('B');fill('safe B');response(q,{});await lateWrite;checks.late_write_no_followup=receiptId==='B'&&$('receipt-text').value==='safe B'&&!pending.length;
await ready('A');fill('first');const edited=receiptCommand('SUBMIT').catch(receiptError);await tick();q=take('/api/executor-receipts/A/commands');fill('new edit');response(q,{});await tick();response(take('/api/executor-receipts/A'),detail('A',2));await edited;checks.pending_edit_preserved=$('receipt-text').value==='new edit';
const staleDenied=load('A');await ready('B');fill('safe B');response(take('/api/executor-receipts/A'),{},403);await staleDenied;checks.late_forbidden_ignored=receiptId==='B'&&$('receipt-text').value==='safe B';
const oldIdentity=load('A');switchToken('synthetic-owner');response(take('/api/executor-receipts/A'),detail('A'));await oldIdentity;checks.identity_pending_cleared=receiptView===null&&$('receipt-detail').hidden&&$('receipt-history').textContent==='';
await ready('A');const aba=load('A');await ready('B');await ready('A',3);fill('new A');response(take('/api/executor-receipts/A'),detail('A',1));await aba;checks.return_generation=receiptView.step.revision===3&&$('receipt-text').value==='new A';
const refreshed=load('A');response(take('/api/executor-receipts/A'),detail('A',3));await refreshed;checks.refresh_preserves_draft=$('receipt-text').value==='new A';
receiptView.step.id='B';let caught=false;try{await receiptCommand('SUBMIT');}catch(e){caught=true;}checks.id_guard=caught&&!pending.length;
await ready('A');receiptView.step.revision=2;caught=false;try{await receiptCommand('SUBMIT');}catch(e){caught=true;}checks.revision_guard=caught&&!pending.length;
await ready('A');receiptView.current_receipt={source_sha256:'0'.repeat(64)};caught=false;try{await receiptCommand('ACKNOWLEDGE');}catch(e){caught=true;}checks.receipt_hash_guard=caught&&!pending.length;
$('receipt-list').click();q=take('/api/executor-receipts');switchToken('other');response(q,{role:'service_executor',items:[{id:'A',goal:'OLD A',state:'AWAITING_RECEIPT'}]});await tick();checks.late_list_ignored=$('receipt-items').textContent==='';
const nav=load('A');document.querySelector('[data-tab=resource]').click();response(take('/api/executor-receipts/A'),detail('A'));await nav;checks.navigation_clears_receipt=receiptView===null&&$('receipt-detail').hidden;
// A creation catalogue cannot repopulate a different preparation or identity.
switchToken('enterprise');prepRole='enterprise_operator';preparationId='P';preparationView={preparation:{id:'P',state:'LOCAL_CONFIRMED',revision:5}};preparationContext={...prepContext(),revision:5};const catalog=$('receipt-prepare').onclick();q=take('/api/executor-receipts/catalog?preparation_id=P');switchToken('executor');response(q,{ready:true,executors:[{id:'old-executor'}]});await catalog;checks.late_create_catalog_ignored=$('receipt-create').hidden&&$('receipt-executor').textContent==='';
return JSON.stringify({checks});
})()
