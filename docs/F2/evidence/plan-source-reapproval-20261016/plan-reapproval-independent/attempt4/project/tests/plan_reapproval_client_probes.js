'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync('src/parkweave/web.html','utf8');
function section(a,b){const start=html.indexOf(a);assert(start>=0);const end=html.indexOf(b,start+1);assert(end>start);return html.slice(start,end);}
const mode=process.argv[2];
if(mode==='aba'){
 const nodes=new Map(),context={deliveryGeneration:0,deliveryQuote:null,planApprovalView:null,planApprovalSelected:null,combinationSelection:new Map(),resourceContext:()=>({}),resourceCurrent:()=>true,bundleControls:()=>{},$:id=>{if(!nodes.has(id))nodes.set(id,{value:'',checked:false,replaceChildren(){}});return nodes.get(id);}};
 context.$('delivery-case').value='case-a';vm.createContext(context);vm.runInContext(section('function deliveryContext(){','async function deliveryCall('),context);
 for(const marker of ["$('delivery-case').oninput=","$('delivery-reapproval').onchange="]){const start=html.indexOf(marker);assert(start>=0);vm.runInContext(html.slice(start,html.indexOf('\n',start)),context);}
 const original=context.deliveryContext();assert.equal(context.deliveryCurrent(original),true);
 context.$('delivery-reapproval').checked=true;context.$('delivery-reapproval').onchange();assert.equal(context.deliveryCurrent(original),false);
 context.$('delivery-reapproval').checked=false;context.$('delivery-reapproval').onchange();assert.equal(context.deliveryCurrent(original),false);
 const current=context.deliveryContext();context.$('delivery-case').value='case-b';context.$('delivery-case').oninput();context.$('delivery-case').value='case-a';context.$('delivery-case').oninput();assert.equal(context.deliveryCurrent(current),false);
 process.stdout.write(JSON.stringify({scope:'ACTUAL_DELIVERY_CONTEXT_AND_HANDLERS',checks:4,HTTP:'NOT_RUN'})+'\n');
}else if(mode==='body'){
 const context={};vm.createContext(context);vm.runInContext(section('function approvalBaseDeliveryBody(', 'function planApprovalControls('),context);
 const id='11111111-1111-4111-8111-111111111111',hash='a'.repeat(64);
 const c={reapproval:true,members:'[]'},q={synthetic_plan_approval_required:true,expected_link_revision:1,expected_preparation_revision:2,expected_plan_revision:9,source_sha256:hash,valid_until:'2099-01-01T00:00:00Z',context:{plan_id:id,source_reapproval:{link_id:id,link_revision:1,snapshot_sha256:hash,previous_delivery_context:{plan_id:id},previous_approved_plan_revision:3,approved_plan_revision:9,source_adoption_event_id:id,source_adoption_revision:8,source_adoption_sha256:hash,source_change_sha256:hash}}};
 let checks=0;assert.equal(context.approvalBaseDeliveryBody(c,q).expected_link_revision,1);checks++;
 const mutations=[x=>x.expected_link_revision=2,x=>x.context.source_reapproval.previous_delivery_context.plan_id='22222222-2222-4222-8222-222222222222',x=>x.context.source_reapproval.source_adoption_revision=3,x=>x.context.source_reapproval.source_change_sha256=null,x=>x.synthetic_plan_approval_required=false,x=>x.context.source_reapproval.approved_plan_revision=10];
 for(const mutate of mutations){const copy=structuredClone(q);mutate(copy);assert.throws(()=>context.approvalBaseDeliveryBody(c,copy));checks++;}
 assert.throws(()=>context.approvalBaseDeliveryBody({...c,reapproval:false},q));checks++;
 const first=structuredClone(q);delete first.expected_link_revision;delete first.context.source_reapproval;assert.equal(Object.hasOwn(context.approvalBaseDeliveryBody({...c,reapproval:false},first),'expected_link_revision'),false);checks++;
 Object.assign(context,{bundleActor:'owner',planApprovalView:null,planApprovalSelected:null,deliveryQuote:null,bundleControls:()=>{},$:()=>({replaceChildren(){},append(){}}),document:{createElement:()=>({append(){}})}});
 vm.runInContext(section('function planApprovalRender(', 'async function recoverPlanApproval('),context);
 const data=context.approvalBaseDeliveryBody(c,q),item={id,valid_until:q.valid_until,current:true,current_available:true,state:'APPROVED',purpose:'CASE_RESOURCE_REAPPROVAL',delivery:data,context:q.context,execution_identity:{actor_id:'owner',run:{id}},service_id:'service',service_version:1,plan_sha256:hash,materials:[],members:[]};
 context.planApprovalRender({actor_id:'owner',preparation_id:id,scope:'ISOLATED_SYNTHETIC_CASE_RESOURCE_APPROVAL_V1',revision:4,items:[item]},{...c,id});assert.equal(context.deliveryQuote.view.expected_link_revision,1);checks++;
 assert.equal(context.approvalDeliveryBody(c,context.deliveryQuote.view).approval_id,id);checks++;
 assert.throws(()=>context.planApprovalRender({actor_id:'owner',preparation_id:id,scope:'ISOLATED_SYNTHETIC_CASE_RESOURCE_APPROVAL_V1',revision:4,items:[{...item,purpose:'CASE_RESOURCE_DELIVERY'}]},{...c,id}));checks++;
 for(const state of ['PROPOSED','APPROVED']){context.deliveryQuote=null;context.planApprovalRender({actor_id:'owner',preparation_id:id,scope:'ISOLATED_SYNTHETIC_CASE_RESOURCE_APPROVAL_V1',revision:4,items:[{...item,state}]},{...c,id,reapproval:false});assert.equal(context.deliveryQuote,null);assert.equal(context.planApprovalSelected.current,false);checks+=2;}
 process.stdout.write(JSON.stringify({scope:'CONTROLLED_ACTUAL_CLIENT_FUNCTIONS_ONLY',checks,HTTP:'NOT_RUN',real_browser:'NOT_RUN'})+'\n');
}else{
 const button={disabled:false},elements=new Map();const context={oppBusy:mode==='busy',oppBusyContext:null,opportunityPlanBusy:mode==='plan_busy',preparationId:'case-a',oppView:{can_write:mode!=='readonly',actor_id:'owner',current_basis:{catalog:[1]}},oppCurrent:()=>true,opportunityPlanControls:()=>{},oppHandles:()=>mode==='corrupt'?null:mode==='recovery'?[{id:'case-a',actor:'owner'}]:[],$:id=>{if(!elements.has(id))elements.set(id,{});return elements.get(id);},document:{querySelectorAll:selector=>selector.split(',').includes('[data-opp-dependency-preview]')?[button]:[]}};
 vm.createContext(context);vm.runInContext(section('function oppLocked(){','async function oppCall('),context);context.oppControls();assert.equal(button.disabled,mode!=='idle');
 process.stdout.write(JSON.stringify({scope:'ACTUAL_OPPORTUNITY_CONTROL_FUNCTION',mode,disabled:button.disabled,HTTP:'NOT_RUN'})+'\n');
}
