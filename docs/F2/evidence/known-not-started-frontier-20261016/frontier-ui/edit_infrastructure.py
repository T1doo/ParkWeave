from pathlib import Path
p=Path(__file__).parent/'candidate/src/parkweave/web.html';s=p.read_text()
def edit(a,b):
 global s
 assert a in s,a[:120]
 s=s.replace(a,b,1)
edit('<p>重新批准保留旧资源占用和历史；整计划替换须先明确采纳新计划，','<label id="delivery-frontier-option" hidden><input id="delivery-frontier" type="checkbox" disabled>请求按原完整协议核对旧 P1/P2 已核验、P3–P5 尚未启动的有限资格</label><p>资格请求不是事实或批准；缺少原签发标记、完整历史或当前核对时不能接续。</p><p>重新批准保留旧资源占用和历史；整计划替换须先明确采纳新计划，')
edit("planReplacement:Boolean($('delivery-plan-replacement').checked),members:","planReplacement:Boolean($('delivery-plan-replacement').checked),frontierProfile:$('delivery-frontier').checked?'KNOWN_NOT_STARTED_V1':null,members:")
edit('c.planReplacement===now.planReplacement;','c.planReplacement===now.planReplacement&&c.frontierProfile===now.frontierProfile;')
edit("if(c.reapproval&&c.planReplacement)throw Error('请明确选择一种交付模式');const body={members};", "if(c.reapproval&&c.planReplacement)throw Error('请明确选择一种交付模式');if(c.frontierProfile&&!c.planReplacement)throw Error('有限资格须明确选择整计划替换模式');const body={members};if(c.frontierProfile)body.replacement_frontier_profile=c.frontierProfile;")
# Other dispatch/profile validation waits for the exact qualification shape.
edit("'reason','expected_link_revision','expected_previous_plan_id'].every", "'reason','expected_link_revision','expected_previous_plan_id','replacement_frontier_profile'].every")
edit("$('delivery-plan-replacement').disabled=locked||!planReplacementEnabled;", "$('delivery-plan-replacement').disabled=locked||!planReplacementEnabled;$('delivery-frontier-option').hidden=!planReplacementEnabled||!$('delivery-plan-replacement').checked;$('delivery-frontier').disabled=locked||!planReplacementEnabled||!$('delivery-plan-replacement').checked;")
edit("$('delivery-plan-replacement').checked=false;$('delivery-reapproval-option').hidden=true;", "$('delivery-plan-replacement').checked=false;$('delivery-frontier').checked=false;$('delivery-frontier-option').hidden=true;$('delivery-reapproval-option').hidden=true;")
edit("Boolean(item.delivery?.expected_link_revision!==undefined)!==Boolean(c.reapproval||c.planReplacement)", "Boolean(item.delivery?.expected_link_revision!==undefined)!==Boolean(c.reapproval||c.planReplacement)||(item.delivery?.replacement_frontier_profile??null)!==(c.frontierProfile??null)")
edit("...(d.expected_previous_plan_id!==undefined?{expected_previous_plan_id:d.expected_previous_plan_id}:{})", "...(d.expected_previous_plan_id!==undefined?{expected_previous_plan_id:d.expected_previous_plan_id}:{}),...(d.replacement_frontier_profile!==undefined?{replacement_frontier_profile:d.replacement_frontier_profile}:{})")
edit("if($('delivery-reapproval').checked)$('delivery-plan-replacement').checked=false;deliveryGeneration++;", "if($('delivery-reapproval').checked){$('delivery-plan-replacement').checked=false;$('delivery-frontier').checked=false;}deliveryGeneration++;")
edit("if($('delivery-plan-replacement').checked)$('delivery-reapproval').checked=false;deliveryGeneration++;", "if($('delivery-plan-replacement').checked)$('delivery-reapproval').checked=false;else $('delivery-frontier').checked=false;deliveryGeneration++;")
marker="$('delivery-case').addEventListener('input',()=>{planApprovalView=null;"
edit(marker,"$('delivery-frontier').onchange=()=>{deliveryGeneration++;deliveryQuote=null;planApprovalView=null;planApprovalSelected=null;$('delivery-result').replaceChildren();$('plan-approval-result').replaceChildren();bundleControls();};\n"+marker)
p.write_text(s)
