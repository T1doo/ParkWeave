// Execute the whole shipped page in the existing DOM/transport harness.
// Inputs are the actual owned API preview and original plan response; no browser claim.
const support=require('fs').readFileSync('tests/typed_source_impact_real_html.js','utf8').split('\n(async () => {')[0];
const scenario=String.raw`
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const original=page({token:'SYNTHETIC_NO_NETWORK_ORACLE'}, {}, [], {});
original.context.fixture=fixture;
original.run("servicePlanView=fixture.plan; preparationView={preparation:{run_id:fixture.preview.run_id}}; oppView={revision:fixture.preview.opportunity_revision,cards:[{id:fixture.preview.card_id,version:fixture.preview.card_version,basis_sha256:fixture.preview.basis_sha256}]};");
const context={id:fixture.preview.preparation_id,caseId:fixture.preview.case_id};original.context.originalContext=context;
original.run('opportunityPlanCheck(fixture.preview,originalContext)');checks++;
original.run('typedSourceImpactCheck(fixture.preview.source_impact,fixture.plan.steps,fixture.plan.plan_id)');checks++;
original.run("renderTypedSourceImpact($('case-source-impact-items'),fixture.preview.source_impact,fixture.plan.steps)");
const text=textOf(original.$('case-source-impact-items'));
check(text.includes('差异观察')&&text.includes('不等于步骤已VERIFY'),'observation is not VERIFY');
check(!text.includes('未发现相对原核验基线'),'no false original verification caption');
for(const schema of [true,'2',3,null]){
 const value=JSON.parse(JSON.stringify(fixture.preview));value.source_impact.schema=schema;original.context.bad=value;
 assert.throws(()=>original.run('opportunityPlanCheck(bad,originalContext)'));checks++;
}
for(const fault of ['validator','producer','plan','prep','case','run','candidate','steps','profile','facet','scope']){
 const value=JSON.parse(JSON.stringify(fixture)),proof=value.plan.candidate_consumption,seal=proof.difference_observation;
 if(fault==='validator')proof.verification_basis.validator_version='LOCAL_SYNTHETIC_DEMO_V1';
 else if(fault==='producer')proof.producer.schema_version='local-synthetic-demo-producer/1';
 else if(fault==='profile')value.plan.binding.service_selection.profile='TRUSTED_SERVICE_SELECTION_V4';
 else if(fault==='steps')seal.steps.pop();
 else if(fault==='scope')value.preview.scope='BOUNDED_MULTI_SOURCE_REVISION_PREVIEW';
 else if(fault==='facet')value.preview.source_impact.nodes.find(n=>n.facet==='CASE_STEP_ASSIGNMENT').fields=['unexpected'];
 else seal[({plan:'plan_id',prep:'preparation_id',case:'case_id',run:'run_id',candidate:'candidate_id'})[fault]]='00000000-0000-0000-0000-000000000000';
 original.context.bad=value;original.run('servicePlanView=bad.plan');
 assert.throws(()=>original.run('opportunityPlanCheck(bad.preview,originalContext)'));checks++;
}
console.log(JSON.stringify({scope:'ORIGINAL_PAGE_DIFFERENCE_OBSERVATION_ORACLE',checks,actual_server_schema:fixture.preview.source_impact.schema,completeOriginalHTML:true,real_browser:false,HTTP_writes:0}));
process.exit(0);
`;
require('vm').runInNewContext(support+scenario,{require,console,process,fetch,URL,URLSearchParams,Blob,TextEncoder,setTimeout});
