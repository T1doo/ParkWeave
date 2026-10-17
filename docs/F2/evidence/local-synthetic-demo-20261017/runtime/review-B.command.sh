node <<'JS'
const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const html=fs.readFileSync('src/parkweave/web.html','utf8');
function actual(name){const prefix='function '+name+'(';const start=html.indexOf(prefix);assert(start>=0,name);const rest=html.slice(start);const next=rest.slice(prefix.length).search(/\n(?:async )?function /);assert(next>=0,name+' terminator');return rest.slice(0,prefix.length+next);}
const names=['uuidHandle','serviceSelectionPlanID','serviceSelectionIdentity','localDemoProducerValid','serviceSelectionCandidateProfile','serviceSelectionListProfile','serviceSelectionCatalogProfile','serviceSelectionMetadata','serviceSelectionTraceMetadata','serviceSelectionPreviewValidate'];
const wire={"producer":{"schema_version":"local-synthetic-demo-producer/1","origin":"LOCAL_SYNTHETIC_DEMO_NO_MODEL_V1","mode":"NO_MODEL","model":null,"provider_enabled":false,"real_model_calls":0,"executed":false,"selection_sha256":"d444dafe650900334524e029410fdaf24ff0e709e81535017c65165d7ddc3d79","pack_sha256":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","journal_sha256":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee","base_sha256":"6d4e30c50b70a26c5575ed30625776e21af25d76d87191b2b4ff86b8f299dda0","attempt_sha256":"4fc520ca4eae60fed508ebca13424ab98fb113f9b0928fa84b96b3e522955a4c"},"producer_sha256":"88d84268b66bafde92968eba55b5d448b9ff39667af8759ff87ea175986b2c59"};
const script=names.map(actual).join('\n')+'\n'+String.raw`
const copy=x=>JSON.parse(JSON.stringify(x)),hash='a'.repeat(64);
const canonical=x=>JSON.stringify(Object.fromEntries(Object.keys(x).sort().map(k=>[k,x[k]])));
assert.equal(crypto.createHash('sha256').update(canonical(wire.producer)).digest('hex'),wire.producer_sha256);
assert.equal(Boolean(localDemoProducerValid(wire.producer)),true);
let rejected=0;
for(const patch of [{usage:{}},{model:'fake'},{mode:'OFFLINE_HTTP_FIXTURE'},{real_model_calls:false},{real_model_calls:1},{provider_enabled:true},{executed:true},{pack_sha256:'A'.repeat(64)}]){const p={...wire.producer,...patch};assert.equal(Boolean(localDemoProducerValid(p)),false);rejected++;}
const demo={profile:'LOCAL_SYNTHETIC_DEMO',scope:'LOCAL_SYNTHETIC_DEMO_SELECTION_CANDIDATE',validator_version:'LOCAL_SYNTHETIC_DEMO_V1',producer:wire.producer};
const old={profile:'TRUSTED_SERVICE_SELECTION_V4',scope:'SYNTHETIC_SERVICE_SELECTION_CANDIDATE',validator_version:4};
assert.equal(Boolean(serviceSelectionCandidateProfile(demo)),true);assert.equal(Boolean(serviceSelectionCandidateProfile(old)),true);
for(const patch of [{profile:old.profile},{scope:old.scope},{validator_version:4}])assert.equal(Boolean(serviceSelectionCandidateProfile({...demo,...patch})),false);
assert.equal(Boolean(serviceSelectionListProfile(demo)),true);assert.equal(Boolean(serviceSelectionListProfile(old)),true);
const r={schema_version:'local-synthetic-demo-release/1',service_id:'synthetic-material-preparation',release_id:'release-a',revision:1,release_sha256:hash,demo_source:{kind:'SYNTHETIC',publication:false,approval:false}};
const i={instance_id:'instance-a',park_id:'park-a',release_id:r.release_id,release_sha256:hash,config_revision:1,config_sha256:hash,roles:{},resources:{},fields:{}};
const ref={release_id:r.release_id,revision:1,release_sha256:hash,instance_id:i.instance_id,config_revision:1,config_sha256:hash};
const selection={schema_version:1,binding:{capability_catalog_sha256:hash},selections:[ref]};
let serviceSelectionCatalog={profile:demo.profile,source_sha256:hash,capability_catalog_sha256:hash,catalog_snapshot:{scope:demo.profile,demo_pack:{kind:'SYNTHETIC'},releases:[r],instances:[i]}};
assert.equal(Boolean(serviceSelectionCatalogProfile(serviceSelectionCatalog)),true);
for(const mutate of [x=>x.catalog_snapshot.scope='TRUSTED_SERVICE_SELECTION_V4',x=>x.catalog_snapshot.demo_pack.kind='AUTHORIZED_REAL',x=>x.catalog_snapshot.releases[0].demo_source.publication=true,x=>x.catalog_snapshot.releases[0].demo_source.approval=true,x=>x.catalog_snapshot.releases[0].source_review={}]){const x=copy(serviceSelectionCatalog);mutate(x);assert.equal(Boolean(serviceSelectionCatalogProfile(x)),false);}
const c={id:'00000000-0000-4000-8000-000000000001',caseId:'00000000-0000-4000-8000-000000000002',runId:'00000000-0000-4000-8000-000000000003',actor:'actor-a',prepareRevision:1,requestRevision:1};
const x={...demo,preparation_id:c.id,case_id:c.caseId,run_id:c.runId,actor_ref:c.actor,preparation_revision:1,request_revision:1,candidate_id:'00000000-0000-4000-8000-000000000004',candidate_sha256:hash,verification_sha256:hash,current_source_sha256:hash,capability_catalog_sha256:hash,read_only:true,provider_enabled:false,execution_enabled:false,new_grants:false,case_goal_completed:false,required_goals:['LOCAL_MATERIAL_PREPARATION'],steps:[],selection};
serviceSelectionPreviewValidate(x,c);
const saved=serviceSelectionCatalog;serviceSelectionCatalog={...saved,profile:old.profile};assert.throws(()=>serviceSelectionPreviewValidate(x,c));serviceSelectionCatalog=saved;
assert.throws(()=>serviceSelectionPreviewValidate({...x,current_source_sha256:'b'.repeat(64)},c));
assert.throws(()=>serviceSelectionPreviewValidate({...x,actor_ref:'other'},c));
const trace={candidate:{validator_version:demo.validator_version,producer:wire.producer},service_selection:{profile:demo.profile,capability_catalog_sha256:hash,selection},service_capabilities:[r],park_instances:[i]};
assert.equal(serviceSelectionTraceMetadata(trace).length,1);
const bad=copy(trace);bad.service_selection.profile=old.profile;assert.throws(()=>serviceSelectionTraceMetadata(bad));
const extra=copy(trace);extra.service_capabilities.push({...r,release_id:'unselected-release'});assert.throws(()=>serviceSelectionTraceMetadata(extra));
const mismatch=copy(trace);mismatch.park_instances[0].config_sha256='b'.repeat(64);assert.throws(()=>serviceSelectionTraceMetadata(mismatch));
console.log('actual_frontend_functions='+names.length+'; honest_producer=true; malformed_producers_rejected='+rejected);
console.log('old_profile_preserved=true; cross_profile_scope_validator_rejected=true; synthetic_catalog_boundaries=5');
console.log('preview_catalog_profile_source_identity_gates=true; frozen_trace_exact_refs_and_selected_only=true');
console.log('python_node_producer_sha256='+wire.producer_sha256);
console.log('probe_scope=memory-only actual extracted functions; DOM_fetch_writer_DB_browser_network=NOT_RUN; file_writes=0');
`;
vm.runInNewContext(script,{assert,crypto,wire,names,console},{timeout:5000});
JS