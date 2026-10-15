from pathlib import Path
p=Path('src/parkweave/web.html');s=p.read_text()
needle='<div id="case-worklist-items"></div>'
assert s.count(needle)==1
s=s.replace(needle,needle+'<section id="case-source-impact" hidden><h4>此事项的实际来源与影响</h4><p id="case-source-impact-status" role="status"></p><div id="case-source-impact-items"></div><button id="case-source-impact-open" type="button" class="secondary">打开此事项的原材料与机会入口</button></section>')
s=s.replace('function clearCaseWorklist(){caseWorklistGeneration++;','function clearCaseWorklist(){clearCaseSourceImpact();caseWorklistGeneration++;')
s=s.replace('function clearServiceCasePlan(){clearOpportunityPlan();','function clearServiceCasePlan(){clearCaseSourceImpact();clearOpportunityPlan();')
needle="   card.append(button);if(row.partial_plan)"
assert s.count(needle)==1
s=s.replace(needle,"   if(row.preparation_id){const impact=textElement('button','只读查看此事项来源变化');impact.type='button';impact.className='secondary';impact.dataset.caseSourceImpact=row.preparation_id;impact.onclick=()=>{if(current())return loadCaseSourceImpact(row);};card.append(impact);}\n"+needle)
needle='// End owner Case worklist.'
assert s.count(needle)==1
s=s.replace(needle,'''// Per-Case source lookup keeps its own epoch; a read never imports or adopts.
let caseSourceImpactGeneration=0,caseSourceImpactView=null;
function clearCaseSourceImpact(){caseSourceImpactGeneration++;caseSourceImpactView=null;$('case-source-impact').hidden=true;$('case-source-impact-status').textContent='';$('case-source-impact-items').replaceChildren();$('case-source-impact-open').disabled=true;}
function typedSourceImpactCheck(graph,steps,planId){
 const hash=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v),ids=steps.map(s=>s.id);
 if(!graph||graph.schema!==1||graph.scope!=='REGISTERED_CASE_TYPED_SOURCE_IMPACT'||graph.plan_id!==planId||!hash(graph.sha256)||!Array.isArray(graph.nodes)||graph.nodes.length>128||!Array.isArray(graph.edges)||graph.edges.length>256||!Array.isArray(graph.changed_node_ids)||!Array.isArray(graph.affected)||!Array.isArray(graph.preserved)||!Array.isArray(graph.unknown_reasons)||![null,'THIS_CASE'].includes(graph.unknown_scope))throw Error('来源依赖证明无法核对，请重新读取');
 const nodes=graph.nodes.map(n=>n.id),all=[...graph.affected,...graph.preserved];
 if(new Set(nodes).size!==nodes.length||all.length!==ids.length||new Set(all).size!==ids.length||all.some(id=>!ids.includes(id))||graph.changed_node_ids.some(id=>!nodes.includes(id))||graph.nodes.some(n=>typeof n.id!=='string'||typeof n.type!=='string'||typeof n.facet!=='string'||typeof n.known!=='boolean'||typeof n.changed!=='boolean')||graph.edges.some(e=>typeof e.kind!=='string'))throw Error('来源与步骤分区不完整，请重新读取');
 return graph;
}
function renderTypedSourceImpact(target,graph,steps){
 const names=ids=>ids.map(id=>steps.find(s=>s.id===id)?.adapter_id||id).join('、')||'无';
 const types={REQUEST:'诉求',FACT:'事实用途绑定',SOURCE:'来源集合',SERVICE_RULE:'服务规则',RESOURCE:'资源规则',CAPACITY_SNAPSHOT:'容量快照',PLAN_STEP:'办理步骤',RESERVATION:'预约',MATERIAL:'材料聚合',RECEIPT:'回执',CHECK:'检查',RELEASE:'定义版本'};
 target.append(textElement('p','本次需重验：'+names(graph.affected)+'；本次保持：'+names(graph.preserved)),textElement('p','只比较原核验与当前实际读取的有限来源。聚合证明不等于逐份材料真实性；适用日期缺证据时保持未知。'));
 if(graph.unknown_scope)target.append(textElement('p','来源关系或旧基线不完整，扩大到本 Case 全部步骤重验；此图不能授权采纳。'));
 const changed=new Set(graph.changed_node_ids);
 for(const n of graph.nodes.filter(n=>changed.has(n.id)||!n.known)){
  const direct=graph.edges.filter(e=>e.upstream===n.id).map(e=>e.downstream).filter(id=>steps.some(s=>s.id===id));
  target.append(textElement('p',(types[n.type]||n.type)+' · '+n.facet+' → '+names(direct)+' · '+(n.known?'来源证明已变化':'来源证明未知')));
 }
 if(!graph.changed_node_ids.length&&!graph.unknown_scope)target.append(textElement('p','未发现相对原核验基线的来源变化；办理权限与产物仍须原入口核对。'));
 const edges=graph.edges.filter(e=>e.kind==='PRECEDES');
 if(edges.length)target.append(textElement('p','原前置传播：'+edges.map(e=>names([e.upstream])+' → '+names([e.downstream])).join('；')));
}
async function loadCaseSourceImpact(row){
 try{beginCaseWorklistEntry();}catch(e){pageError(e);return;}
 clearCaseWorklist();const c={generation:caseSourceImpactGeneration,token:$('token').value,page:pageGeneration,prep:prepGeneration,plan:servicePlanGeneration};
 const current=()=>c.generation===caseSourceImpactGeneration&&c.token===$('token').value&&c.page===pageGeneration&&c.prep===prepGeneration&&c.plan===servicePlanGeneration;
 $('case-source-impact').hidden=false;$('case-source-impact-status').textContent='正在只读核对此事项当前有权来源…';
 try{
  const r=await entryFetch('/api/preparations/'+encodeURIComponent(row.preparation_id)+'/source-impact',{headers:{Authorization:'Bearer '+c.token},cache:'no-store'});if(!current())return;
  if(r.status===403){clearDeniedPrivateViews();return;}
  const x=await r.json();if(!current())return;if(!r.ok)throw Error('此事项来源暂时无法一致核对，请从原入口处理后重读');
  if(x.scope!=='CURRENT_OWNER_CASE_SOURCE_IMPACT'||x.read_only!==true||x.automatically_replayed!==false||x.preparation_id!==row.preparation_id||x.case_id!==row.case_id||x.run_id!==row.run_id||x.new_grants!==false||x.automatic_execution!==false||x.case_goal_completed!==false||!Array.isArray(x.steps)||x.steps.length>5||!['NO_PLAN','UNKNOWN','CHANGED','UNCHANGED'].includes(x.state))throw Error('当前身份与事项来源响应不匹配');
  if(x.state==='NO_PLAN'){if(x.plan_id!==null||x.source_impact!==null)throw Error('尚未采用的计划证明不一致');$('case-source-impact-status').textContent='此事项尚未采用计划；请从原入口核对全部目标。';}
  else{typedSourceImpactCheck(x.source_impact,x.steps,x.plan_id);if(x.source_impact.binding?.preparation_id!==row.preparation_id||x.source_impact.binding?.case_id!==row.case_id)throw Error('来源图绑定不属于此事项');renderTypedSourceImpact($('case-source-impact-items'),x.source_impact,x.steps);$('case-source-impact-status').textContent='事项 '+x.case_id+' · 计划版本 '+x.plan_revision+' · '+({UNKNOWN:'来源尚待核对',CHANGED:'发现来源变化',UNCHANGED:'本次未见来源变化'}[x.state]);}
  caseSourceImpactView={row,current};$('case-source-impact-open').disabled=false;$('case-source-impact').scrollIntoView({block:'start'});
 }catch(e){if(current()){$('case-source-impact-items').replaceChildren();$('case-source-impact-status').textContent=e.message;}}
}
$('case-source-impact-open').onclick=async()=>{const v=caseSourceImpactView;if(!v?.current())return;try{beginCaseWorklistEntry();await loadPreparation(v.row.preparation_id,{role:'enterprise_operator'});}catch(e){prepError(e);}};
// End owner Case worklist.''')
needle=" const card=oppView.cards.find(card=>card.id===v.card_id);"
assert s.count(needle)==1
s=s.replace(needle," typedSourceImpactCheck(v.source_impact,servicePlanView.steps,v.plan_id);\n"+needle)
needle="  for(const reason of v.blocking_reasons)"
assert s.count(needle)==1
s=s.replace(needle,"  renderTypedSourceImpact($('opp-plan-impact'),v.source_impact,servicePlanView.steps);\n"+needle)
p.write_text(s)
