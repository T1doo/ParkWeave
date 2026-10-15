// Pure isolated function probe: no browser, HTTP, PostgreSQL or business action.
const fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('src/parkweave/web.html','utf8');
const checker=html.slice(html.indexOf('async function employeesFactProvenanceCheck('),html.indexOf('function renderEmployeesFactProvenance('));
const handler=html.match(/function opportunityPlanError\(e\)\{[^\n]+/)[0];
let rejectDigest,cleared=0,errors=0;
const state={Error,Object,Array,Number,Date,Set,
 coldDigest:()=>new Promise((_,reject)=>{rejectDigest=reject}),
 uuidHandle:()=>true,oppCurrent:()=>false,servicePlanCurrent:()=>false,
 clearOpportunityPlan:()=>{cleared++},oppError:()=>{errors++},servicePlanError:()=>{errors++}};
vm.createContext(state);vm.runInContext(checker+'\n'+handler,state);
const node={};
const p={version:1,scope:'EMPLOYEES_USER_ASSERTION_V1',before:node,current:node,
 selected_changed:false,aggregate_changed:false,authenticity:'USER_ASSERTED_UNVERIFIED',new_grants:false,sha256:'a'.repeat(64)};
const pending=state.employeesFactProvenanceCheck({scope:'EMPLOYEES_FACT_PROVENANCE_PREVIEW',fact_provenance:p});
// Identity/Case switch is represented by oppCurrent/servicePlanCurrent false.
rejectDigest(new Error('controlled crypto failure after Case switch'));
pending.catch(error=>{state.opportunityPlanError(error);process.stdout.write(JSON.stringify({
 evidence_kind:'PURE_FUNCTION_PROBE_NO_HTTP_NO_BROWSER',
 error_has_original_context:!!(error.opportunityContext||error.servicePlanContext),
 new_case_clear_calls:cleared,new_case_generic_error_calls:errors})+'\n')});
