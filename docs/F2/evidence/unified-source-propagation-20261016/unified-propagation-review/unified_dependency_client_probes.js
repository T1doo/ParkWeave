// Controlled original client checker only; no browser, HTTP or PostgreSQL.
const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
const html=fs.readFileSync('src/parkweave/web.html','utf8');
const code=html.slice(html.indexOf('async function unifiedDependencyPropagationCheck('),html.indexOf('function renderUnifiedDependencyPropagation('));
const canonical=x=>Array.isArray(x)?'['+x.map(canonical).join(',')+']':x&&typeof x==='object'?'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',')+'}':JSON.stringify(x);
const hash=x=>crypto.createHash('sha256').update(canonical(x)).digest('hex');
const base=JSON.parse(fs.readFileSync(0,'utf8'));
const ctx={crypto:crypto.webcrypto,TextEncoder,receiptHistoryCanonical:canonical,boundedCaseHash:x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x)};
vm.createContext(ctx);vm.runInContext(code,ctx);
async function scenario(label,mutate,expectedAccepted){
 const v=structuredClone(base);mutate(v.dependency_propagation);const g=v.dependency_propagation;delete g.sha256;g.sha256=hash(g);
 let accepted=true,error=null;try{await ctx.unifiedDependencyPropagationCheck(v)}catch(e){accepted=false;error=e.message}
 if(accepted!==expectedAccepted)throw Error(label+': expected accepted='+expectedAccepted+', observed '+accepted);
 if(!accepted&&error!=='统一来源传播与原观察、类型边或受影响分区无法核对')throw Error(label+': rejection was an incidental exception '+error);
 return{scenario:label,status:'PASS',accepted,expected_accepted:expectedAccepted};
}
(async()=>{
 const results=[];
 results.push(await scenario('original_valid_graph',()=>{},true));
 results.push(await scenario('rehashed_extra_graph_field',g=>{g.arbitrary='NOT_COMPILED'},false));
 results.push(await scenario('rehashed_extra_node_field',g=>{g.nodes[0].arbitrary='NOT_COMPILED'},false));
 results.push(await scenario('consistent_noncanonical_node_id',g=>{const n=g.nodes[0],old=n.id,nid='f'.repeat(64);n.id=nid;for(const o of g.observations)if(o.source_node_id===old)o.source_node_id=nid;for(const e of g.edges)if(e.upstream===old)e.upstream=nid;for(const p of g.propagation_paths)if(p.source_node_id===old)p.source_node_id=nid;g.changed_node_ids=g.nodes.filter(n=>n.changed).map(n=>n.id)},false));
 results.push(await scenario('duplicate_facet_type_group',g=>{const n=g.nodes.find(n=>n.observation_ids.length>1),m=structuredClone(n),oid=n.observation_ids.pop();m.id='e'.repeat(64);m.observation_ids=[oid];g.nodes.push(m);g.observations.find(o=>o.id===oid).source_node_id=m.id;for(const e of g.edges)if(e.observation_id===oid)e.upstream=m.id;for(const p of g.propagation_paths)if(p.observation_id===oid)p.source_node_id=m.id;for(const node of [n,m]){const own=g.observations.filter(o=>o.source_node_id===node.id);node.changed=own.some(o=>o.changed);node.known=own.every(o=>o.known)}g.changed_node_ids=g.nodes.filter(n=>n.changed).map(n=>n.id)},false));
 results.push(await scenario('consistent_noncanonical_observation_id',g=>{const o=g.observations[0],old=o.id,id='d'.repeat(64);o.id=id;for(const n of g.nodes)n.observation_ids=n.observation_ids.map(v=>v===old?id:v);for(const e of g.edges)if(e.observation_id===old)e.observation_id=id;for(const p of g.propagation_paths)if(p.observation_id===old)p.observation_id=id;g.changed_observation_ids=g.changed_observation_ids.map(v=>v===old?id:v)},false));
 results.push(await scenario('consistent_noncanonical_edge_id',g=>{const e=g.edges[0],old=e.id,id='c'.repeat(64);e.id=id;for(const p of g.propagation_paths)p.edge_ids=p.edge_ids.map(v=>v===old?id:v)},false));
 results.push(await scenario('rehashed_invented_unknown_reason',g=>{g.unknown_reasons=['UNRECORDED_PRIVATE_REASON']},false));
 process.stdout.write(JSON.stringify({evidence_kind:'CONTROLLED_ORIGINAL_CLIENT_CHECKER_NO_HTTP_BROWSER_PG',results})+'\n');
})().catch(e=>{process.stderr.write(String(e.stack)+'\n');process.exitCode=1});
