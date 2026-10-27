'use strict';
// Controlled actual handler execution; no browser, HTTP, SQL or synthetic authority.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync('src/parkweave/web.html','utf8'),mode=process.argv[2];
function section(a,b){const start=html.indexOf(a),end=html.indexOf(b,start+1);assert(start>=0&&end>start);return html.slice(start,end);}
const id='11111111-1111-4111-8111-111111111111',hash='a'.repeat(64);
const c={id,reapproval:true,planReplacement:false,frontierProfile:null,members:'[]',resource:{}},q={synthetic_plan_approval_required:true,expected_link_revision:1,expected_preparation_revision:2,expected_plan_revision:9,source_sha256:hash,valid_until:'2099-01-01T00:00:00Z',context:{preparation_id:id,case_id:'case',run_id:'run',plan_id:id,source_reapproval:{link_id:id,link_revision:1,snapshot_sha256:hash,previous_delivery_context:{plan_id:id},previous_approved_plan_revision:3,approved_plan_revision:9,source_adoption_event_id:id,source_adoption_revision:8,source_adoption_sha256:hash,source_change_sha256:hash}}};
if(mode==='first'){c.reapproval=false;delete q.expected_link_revision;delete q.context.source_reapproval;}
let live=true;const posts=[],reads=[],errors=[],recovered=[],storage=new Map(),nodes=new Map();
const ledger={actor_id:'owner',preparation_id:id,case_id:'case',run_id:'run',scope:'LOCAL_CASE_RESOURCE_APPROVAL_V1',revision:mode==='first'?0:3,items:[]};
if(mode==='actor_mismatch')ledger.actor_id='other';if(mode==='case_mismatch')ledger.case_id='other';if(mode==='run_mismatch')ledger.run_id='other';if(mode==='scope_mismatch')ledger.scope='ISOLATED_SYNTHETIC_CASE_RESOURCE_APPROVAL_V1';if(mode==='bad_revision')ledger.revision=-1;if(mode==='oversize_revision')ledger.revision=65;
const context={planApprovalBusy:false,planApprovalBusyContext:null,planApprovalEnabled:true,planApprovalScope:ledger.scope==='ISOLATED_SYNTHETIC_CASE_RESOURCE_APPROVAL_V1'?'LOCAL_CASE_RESOURCE_APPROVAL_V1':ledger.scope,planApprovalView:null,planApprovalSelected:null,bundleActor:'owner',deliveryQuote:{context:c,view:q},planApprovalStorage:'approval.',
 bundleLocked:()=>false,deliveryContext:()=>c,deliveryCurrent:()=>live,requireDeliveryCurrent:()=>{if(!live)throw Error('stale context');},bundleControls:()=>{},bundleIdentify:async()=>{if(mode==='identify_quote_change')context.deliveryQuote={context:c,view:{...q,source_sha256:'b'.repeat(64)}};},replacementFrontierProfileEnabled:()=>true,planApprovalHandles:()=>[],crypto:{randomUUID:()=>id},Date,
 localStorage:{setItem:(k,v)=>storage.set(k,v),getItem:k=>storage.get(k),removeItem:k=>storage.delete(k)},
 $:id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',replaceChildren(){}});return nodes.get(id);},resourceError:e=>errors.push(e),
 deliveryCall:async(path,method,body,key)=>{
  if(method==='GET'){
   reads.push(path);if(mode==='read403')throw Object.assign(Error('denied'),{status:403});
   if(mode==='quote_change')context.deliveryQuote={context:c,view:{...q,source_sha256:'b'.repeat(64)}};
   if(mode==='ABA')live=false;
   return ledger;
  }
  posts.push({path,body:structuredClone(body),key});
  if(mode==='concurrent409'||body.expected_revision!==ledger.revision)throw Object.assign(Error('ledger CAS conflict'),{status:409});
  return {event:{request_key:key}};
 },recoverPlanApproval:async(c,h)=>recovered.push(h)};
vm.createContext(context);vm.runInContext(section('function approvalBaseDeliveryBody(','function planApprovalControls('),context);vm.runInContext(section('async function writePlanApproval(',"$('plan-approval-read').onclick="),context);
(async()=>{
 const original=JSON.stringify(context.approvalBaseDeliveryBody(c,q));await context.writePlanApproval('PROPOSE');
 const reject=['actor_mismatch','case_mismatch','run_mismatch','scope_mismatch','bad_revision','oversize_revision','read403','quote_change','identify_quote_change','ABA'].includes(mode);
 if(reject){assert.equal(posts.length,0);assert.equal(errors.length,1);assert.equal(storage.size,0);assert.equal(recovered.length,0);}
 else{
  assert.equal(posts.length,1);assert.equal(posts[0].body.expected_revision,ledger.revision);assert.equal(JSON.stringify(posts[0].body.delivery),original);assert.equal(reads.length,1);assert.equal(posts[0].key,id);
  if(mode==='concurrent409'){assert.equal(errors.length,1);assert.equal(storage.size,0);assert.equal(recovered.length,0);}
  else{assert.equal(errors.length,0);assert.equal(recovered.length,1);assert.equal(recovered[0].key,posts[0].key);assert.equal(JSON.parse([...storage.values()][0]).revision,ledger.revision);}
 }
 process.stdout.write(JSON.stringify({scope:'ACTUAL_PROPOSE_HANDLER_CONTROLLED_ORACLE',mode,GET:reads.length,POST:posts.length,HTTP:'NOT_RUN',real_browser:'NOT_RUN',automatic_APPROVE:0,automatic_retry:0})+'\n');
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
