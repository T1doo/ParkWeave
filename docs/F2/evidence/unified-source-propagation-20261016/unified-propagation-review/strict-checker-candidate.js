async function unifiedDependencyPropagationCheck(v){
 const g=v?.dependency_propagation,old=v?.source_impact,scope='BOUNDED_MULTI_SOURCE_V1',same=(a,b)=>receiptHistoryCanonical(a)===receiptHistoryCanonical(b);
 const fail=()=>{throw Error('统一来源传播与原观察、类型边或受影响分区无法核对');};
 const exact=(x,keys)=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&same(Object.keys(x).sort(),keys.slice().sort());
 if(!exact(g,['schema','scope','binding','plan_id','original_graph_sha256','nodes','observations','edges','step_endpoints','changed_node_ids','changed_observation_ids','propagation_paths','affected','preserved','unknown_scope','unknown_reasons','new_grants','automatic_execution','sha256']))fail();
 if(v.scope!=='BOUNDED_MULTI_SOURCE_REVISION_PREVIEW'||!g||g.schema!==2||g.scope!==scope||g.plan_id!==v.plan_id||!same(g.binding,old.binding)||g.original_graph_sha256!==old.sha256||g.new_grants!==false||g.automatic_execution!==false||!boundedCaseHash(g.sha256))fail();
 const digest=async x=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(receiptHistoryCanonical(x))))).map(x=>x.toString(16).padStart(2,'0')).join('');
 const body={...g};delete body.sha256;if(await digest(body)!==g.sha256)fail();
 if(!Array.isArray(g.step_endpoints)||!Array.isArray(g.nodes)||!Array.isArray(g.observations)||!Array.isArray(g.edges)||!Array.isArray(g.propagation_paths)||g.nodes.length+g.step_endpoints.length>96||g.observations.length>96||g.edges.length>128||g.propagation_paths.length>480||!same(g.step_endpoints,old.step_endpoints)||g.observations.length!==old.nodes.length||g.edges.length!==old.edges.length)fail();
 const nodes=new Map(),groups=new Set(),observations=new Map(),originals=new Map(old.nodes.map(n=>[n.id,n])),edges=new Map(),steps=new Set(g.step_endpoints.map(s=>s.id));
 for(const n of g.nodes){const key=receiptHistoryCanonical([n.facet,n.type]);if(!exact(n,['id','type','facet','aggregate','observation_ids','changed','known'])||groups.has(key)||n.id!==await digest({scope,binding:g.binding,plan_id:g.plan_id,facet:n.facet,type:n.type}))fail();groups.add(key);if(!boundedCaseHash(n.id)||nodes.has(n.id)||n.aggregate!==true||!Array.isArray(n.observation_ids)||!n.observation_ids.length||typeof n.changed!=='boolean'||typeof n.known!=='boolean')fail();nodes.set(n.id,n);}
 for(const o of g.observations){
  const original=originals.get(o.original_node_id),n=nodes.get(o.source_node_id);if(!boundedCaseHash(o.id)||observations.has(o.id)||o.id!==await digest({scope,source_node_id:o.source_node_id,original_node_id:o.original_node_id})||!original||!n||n.type!==original.type||n.facet!==original.facet)fail();
  const expected={...original};delete expected.id;delete expected.type;delete expected.facet;
  const actual={...o};delete actual.id;delete actual.source_node_id;delete actual.original_node_id;if(!same(actual,expected))fail();
  observations.set(o.id,o);originals.delete(o.original_node_id);
 }
 if(originals.size)fail();
 for(const n of g.nodes){const own=g.observations.filter(o=>o.source_node_id===n.id);if(!same(n.observation_ids,own.map(o=>o.id))||n.changed!==own.some(o=>o.changed)||n.known!==own.every(o=>o.known))fail();}
 const expectedEdges=old.edges.map(e=>{const o=g.observations.find(o=>o.original_node_id===e.upstream);return o?{...e,upstream:o.source_node_id,observation_id:o.id}:{...e};});
 for(let i=0;i<g.edges.length;i++){const e=g.edges[i],actual={...e};delete actual.id;if(!boundedCaseHash(e.id)||e.id!==await digest({scope,edge:expectedEdges[i]})||edges.has(e.id)||!same(actual,expectedEdges[i])||!steps.has(e.downstream))fail();edges.set(e.id,e);}
 const reached=new Set(),paths=[];
 for(const edge of g.edges){
  if(!observations.get(edge.observation_id)?.changed)continue;
  const queue=[[edge.downstream,[edge.id]]],seen=new Set();
  while(queue.length){const [target,path]=queue.shift();if(seen.has(target))continue;seen.add(target);reached.add(target);paths.push({observation_id:edge.observation_id,source_node_id:edge.upstream,step_id:target,reason:path.length===1?'DIRECT_SOURCE_CHANGE':'REGISTERED_PREDECESSOR_CHANGE',edge_ids:path});for(const next of g.edges)if(!next.observation_id&&next.upstream===target)queue.push([next.downstream,[...path,next.id]]);}
 }
 const ids=g.step_endpoints.map(s=>s.id),affected=g.unknown_scope?ids:ids.filter(id=>reached.has(id)),preserved=g.unknown_scope?[]:ids.filter(id=>!reached.has(id));
 if(!same(paths,g.propagation_paths)||!same(g.changed_node_ids,g.nodes.filter(n=>n.changed).map(n=>n.id))||!same(g.changed_observation_ids,g.observations.filter(o=>o.changed).map(o=>o.id))||!same(g.affected,affected)||!same(g.preserved,preserved)||!same(g.affected,v.affected)||!same(g.preserved,v.preserved)||!same(g.affected,old.affected)||!same(g.preserved,old.preserved)||!Array.isArray(g.unknown_reasons)||g.unknown_scope!==null&&g.unknown_scope!=='THIS_CASE')fail();
 if(g.unknown_scope&&(v.can_adopt||v.adoption!==null||g.preserved.length)||!g.unknown_scope&&g.unknown_reasons.length)fail();
 if(v.adoption&&v.adoption.dependency_scope!==scope)fail();
 return g;
}
