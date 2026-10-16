from pathlib import Path
p=Path(__file__).parent/'candidate/src/parkweave/web.html'
s=p.read_text()
def edit(old,new):
 global s
 assert old in s,old[:120]
 s=s.replace(old,new,1)
edit('<p>重新批准保留旧资源占用和历史；新容量及关联仅在明确批准后一起提交。</p>','<label id="delivery-plan-replacement-option" hidden><input id="delivery-plan-replacement" type="checkbox" disabled>整计划替换后重新批准并续办此Case资源</label><p>重新批准保留旧资源占用和历史；整计划替换须先明确采纳新计划，再对新计划及本次容量重新批准。新容量及关联在明确批准后一起提交。</p>')
edit('reapproval:Boolean($(\'delivery-reapproval\').checked),members:', 'reapproval:Boolean($(\'delivery-reapproval\').checked),planReplacement:Boolean($(\'delivery-plan-replacement\').checked),members:')
edit('c.reapproval===now.reapproval;','c.reapproval===now.reapproval&&c.planReplacement===now.planReplacement;')
edit('planApprovalEnabled=false,sourceReapprovalEnabled=false;','planApprovalEnabled=false,sourceReapprovalEnabled=false,planReplacementEnabled=false;')
edit("$('delivery-reapproval').disabled=locked||!sourceReapprovalEnabled;", "$('delivery-reapproval').disabled=locked||!sourceReapprovalEnabled;$('delivery-plan-replacement-option').hidden=!planReplacementEnabled;$('delivery-plan-replacement').disabled=locked||!planReplacementEnabled;")
edit("sourceReapprovalEnabled=false;$('delivery-reapproval').checked=false;$('delivery-reapproval-option').hidden=true;", "sourceReapprovalEnabled=false;planReplacementEnabled=false;$('delivery-reapproval').checked=false;$('delivery-plan-replacement').checked=false;$('delivery-reapproval-option').hidden=true;$('delivery-plan-replacement-option').hidden=true;")
edit('sourceReapprovalEnabled=planApprovalEnabled&&status.source_reapproval_enabled===true;', 'sourceReapprovalEnabled=planApprovalEnabled&&status.source_reapproval_enabled===true;planReplacementEnabled=planApprovalEnabled&&status.plan_replacement_enabled===true;')
# Keep legacy handler on one line for original source/client probes.
edit("$('delivery-reapproval').onchange=()=>{deliveryGeneration++;", "$('delivery-reapproval').onchange=()=>{if($('delivery-reapproval').checked)$('delivery-plan-replacement').checked=false;deliveryGeneration++;")
marker="$('delivery-case').addEventListener('input',()=>{planApprovalView=null;"
edit(marker,"$('delivery-plan-replacement').onchange=()=>{if($('delivery-plan-replacement').checked)$('delivery-reapproval').checked=false;deliveryGeneration++;deliveryQuote=null;planApprovalView=null;planApprovalSelected=null;$('delivery-result').replaceChildren();$('plan-approval-result').replaceChildren();bundleControls();};\n"+marker)
p.write_text(s)
