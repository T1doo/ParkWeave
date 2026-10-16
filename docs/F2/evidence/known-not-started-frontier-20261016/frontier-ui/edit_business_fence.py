from pathlib import Path
p=Path(__file__).parent/'candidate/src/parkweave/web.html';s=p.read_text()
def edit(a,b):
 global s
 assert a in s,a[:100]
 s=s.replace(a,b,1)
marker='// Internal offers share no private material response or authority with receipt views.'
helper="""// Capture original business CAS only from the observed GET/view; never refresh on submit.
function captureBusinessFrontier(value,preparationId){
 if(value===undefined)return undefined;
 const keys=['generation','preparation_id','plan_id','plan_revision','epoch'],uuid=v=>typeof v==='string'&&/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(v);
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).sort().join(',')!==keys.slice().sort().join(',')||!['generation','preparation_id','plan_id'].every(k=>uuid(value[k]))||value.preparation_id!==preparationId||!Number.isSafeInteger(value.plan_revision)||value.plan_revision<1||value.plan_revision>64||!Number.isSafeInteger(value.epoch)||value.epoch<0||value.epoch>4096)throw Error('原业务前沿无法核对；请先读取当前已采用计划及原业务入口');
 return Object.freeze({generation:value.generation,preparation_id:value.preparation_id,plan_id:value.plan_id,plan_revision:value.plan_revision,epoch:value.epoch});
}
function sameBusinessFrontier(a,b){return a===undefined&&b===undefined||!!a&&!!b&&['generation','preparation_id','plan_id','plan_revision','epoch'].every(k=>a[k]===b[k]);}
"""
edit(marker,helper+marker)
edit("function renderDispatch(x,catalog){\n  dispatchView=x;", "function renderDispatch(x,catalog){\n  if(catalog&&(x.business_frontier!==undefined||catalog.business_frontier!==undefined)&&!sameBusinessFrontier(captureBusinessFrontier(x.business_frontier,x.preparation_id),captureBusinessFrontier(catalog.business_frontier,x.preparation_id)))throw Error('分派与目录的原业务前沿不同，请重新读取');\n  dispatchView=x;")
edit("offerId:x.current_offer?.id||null};", "offerId:x.current_offer?.id||null,...(x.business_frontier!==undefined?{businessFrontier:captureBusinessFrontier(x.business_frontier,x.preparation_id)}:{})};")
edit("if(catalog.preparation_revision!==x.preparation_revision||catalog.dispatch_revision!==x.revision)throw Error", "if(catalog.preparation_revision!==x.preparation_revision||catalog.dispatch_revision!==x.revision||((x.business_frontier!==undefined||catalog.business_frontier!==undefined)&&!sameBusinessFrontier(captureBusinessFrontier(x.business_frontier,preparationId),captureBusinessFrontier(catalog.business_frontier,preparationId))))throw Error")
edit("if(offer&&dispatchCatalog?.can_reassign){", "if(c.businessFrontier!==undefined)body.expected_business_frontier=c.businessFrontier;\n  if(offer&&dispatchCatalog?.can_reassign){")
edit("expected_receipt_revision:p.predecessor_receipt_revision,executor_id:target,reason};", "expected_receipt_revision:p.predecessor_receipt_revision,executor_id:target,reason,...(c.businessFrontier!==undefined?{expected_business_frontier:c.businessFrontier}:{})};")
edit("sha:x.current_receipt?.source_sha256||null};", "sha:x.current_receipt?.source_sha256||null,...(x.business_frontier!==undefined?{businessFrontier:captureBusinessFrontier(x.business_frontier,s.preparation_id)}:{})};")
edit("const body={expected_revision:receiptContext.revision,reason},path=", "const body={expected_revision:receiptContext.revision,reason,...(receiptContext.businessFrontier!==undefined?{expected_business_frontier:receiptContext.businessFrontier}:{})},path=")
edit("body={action,expected_revision:c.revision};if(action==='SUBMIT')", "body={action,expected_revision:c.revision,...(c.businessFrontier!==undefined?{expected_business_frontier:c.businessFrontier}:{})};if(action==='SUBMIT')")
edit("receiptCreateContext={...c,revision:preparationView.preparation.revision};", "receiptCreateContext={...c,revision:preparationView.preparation.revision,...(x.business_frontier!==undefined?{businessFrontier:captureBusinessFrontier(x.business_frontier,c.id)}:{})};")
edit("executor_id:$('receipt-executor').value};const x=await retryWrite", "executor_id:$('receipt-executor').value,...(c.businessFrontier!==undefined?{expected_business_frontier:c.businessFrontier}:{})};const x=await retryWrite")
edit("sha:x.current_snapshot_sha256};$('local-case-detail')", "sha:x.current_snapshot_sha256,...(x.business_frontier!==undefined?{businessFrontier:captureBusinessFrontier(x.business_frontier,x.preparation_id)}:{})};$('local-case-detail')")
edit("expected_cycle:c.cycle,reason:draft};if(action!=='REOPEN')", "expected_cycle:c.cycle,reason:draft,...(c.businessFrontier!==undefined?{expected_business_frontier:c.businessFrontier}:{})};if(action!=='REOPEN')")
# New issued protocol availability is separate from the existing completed-prefix profile.
edit('planReplacementEnabled=false;','planReplacementEnabled=false,knownNotStartedEnabled=false;')
edit("$('delivery-frontier-option').hidden=!planReplacementEnabled||!$('delivery-plan-replacement').checked;$('delivery-frontier').disabled=locked||!planReplacementEnabled||!$('delivery-plan-replacement').checked;", "$('delivery-frontier-option').hidden=!knownNotStartedEnabled||!$('delivery-plan-replacement').checked;$('delivery-frontier').disabled=locked||!knownNotStartedEnabled||!$('delivery-plan-replacement').checked;")
edit("sourceReapprovalEnabled=false;planReplacementEnabled=false;", "sourceReapprovalEnabled=false;planReplacementEnabled=false;knownNotStartedEnabled=false;")
edit('planReplacementEnabled=planApprovalEnabled&&status.plan_replacement_enabled===true;', 'planReplacementEnabled=planApprovalEnabled&&status.plan_replacement_enabled===true;knownNotStartedEnabled=planReplacementEnabled&&status.known_not_started_enabled===true;')
edit("if(c.frontierProfile&&!c.planReplacement)throw Error('有限资格须明确选择整计划替换模式');", "if(c.frontierProfile&&(!c.planReplacement||!knownNotStartedEnabled))throw Error('有限资格须明确选择当前已启用的整计划替换模式');")
edit("if(!planApprovalEnabled)throw Error('当前环境未启用合成方案批准');let data;", "if(!planApprovalEnabled)throw Error('当前环境未启用合成方案批准');if(c.frontierProfile&&!knownNotStartedEnabled)throw Error('原有限资格协议当前未启用，请保留原句柄只读核对');let data;")
edit("deliveryBusy=true;deliveryBusyContext=c;bundleControls();try{await bundleIdentify(c.resource);requireDeliveryCurrent(c);const hs=deliveryHandles();", "deliveryBusy=true;deliveryBusyContext=c;bundleControls();try{await bundleIdentify(c.resource);requireDeliveryCurrent(c);if(c.frontierProfile&&!knownNotStartedEnabled)throw Error('原有限资格协议当前未启用，请只读核对');const hs=deliveryHandles();")
p.write_text(s)
