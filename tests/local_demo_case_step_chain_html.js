// Reuse the original page transport/DOM mechanics; all decisions run shipped HTML.
const supportText = require('fs').readFileSync('tests/ordinary_case_goal_record_pack_html.js','utf8').split('const until=')[0];
const scenario = String.raw`
(async()=>{
 const config=await initialized,calls=[];diagnostics={calls};
 const owner=page({...config,token:config.tokens.owner},{},calls,{});
 await owner.$('prep-list').click();const item=owner.$('prep-items').children.find(e=>e.tagName==='button');check(!!item,'new preparation visible');await item.click();
 check(owner.run('preparationId')===config.preparation_id,'exact new preparation');
 await owner.$('service-plan-prepare').click();check(owner.run('servicePlanView.plan_id')===null,'no pre-adopted plan');
 await owner.$('service-selection-read').click();
 check(textOf(owner.$('service-selection-catalog')).includes('LOCAL_SYNTHETIC_DEMO'),'original directory source visible');
 check(owner.$('service-selection-generate').textContent==='生成合成候选（无模型）','explicit no-model choice');
 await owner.$('service-selection-generate').click();
 const candidate=owner.run('serviceSelectionView');check(!!candidate&&candidate.can_adopt,'original persisted candidate');
 check(candidate.producer.mode==='NO_MODEL'&&candidate.producer.model===null&&candidate.producer.real_model_calls===0,'original producer proof');
 const posts=()=>calls.filter(c=>c.method==='POST');check(posts().length===1,'one explicit generation');
 owner.$('service-plan-reason').value='SYNTHETIC explicit selected service ADOPT';await owner.$('service-plan-adopt').click();check(posts().length===1,'unchecked ADOPT sends nothing');
 owner.$('service-selection-confirm').checked=true;await owner.$('service-plan-adopt').click();
 const plan=owner.run('servicePlanView');check(!!plan.plan_id&&plan.steps.length===5,'selected plan adopted');
 check(posts().length===2&&posts()[1].path.endsWith('/service-case-plan'),'original explicit ADOPT only');
 check(posts()[1].body.candidate_id===candidate.candidate_id,'exact selected candidate consumed');
 check(plan.current_case_step_scope.contract==='CASE_STEP_ASSIGNMENT_V1','ordinary CaseStep source');
 for(const adapter of ['P1','P2','P3','P4','P5']){
  const card=owner.$('service-plan-steps').children.find(e=>e.dataset.serviceAdapter===adapter);
  check(!!card?.children.find(e=>e.dataset.serviceOpen&&!e.disabled),'direct original handling entry '+adapter);
 }
 const key=posts()[0].request_key;check(typeof key==='string'&&key.length>0,'original selection key');
 console.log(JSON.stringify({scope:'LOCAL_DEMO_TO_ORDINARY_CASE_STEP_REAL_HTML',checks,calls,candidate,plan_id:plan.plan_id,selection_key:key,completeOriginalHTML:true,real_browser:false}));process.exit(0);
})().catch(e=>{console.error(e.stack);console.error(JSON.stringify(diagnostics));process.exit(1);});
`;
require('vm').runInNewContext(supportText+scenario,{require,console,process,fetch,URL,URLSearchParams,Blob,TextEncoder,setTimeout});
