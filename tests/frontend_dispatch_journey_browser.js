// Presentation verification only: explicit DTOs passed to the original renderer.
// No dispatch/accept request and no authentication/authorization success claim.
async page=>{
  const errors=[],writes=[],results=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()!=='GET')writes.push(r.url())});
  await page.setViewportSize({width:1440,height:900});
  await page.goto('http://127.0.0.1:8876/web.html');
  await page.locator('[data-tab=collaboration]').click();
  const check=(ok,message)=>{if(!ok)throw Error(message)};
  for(const state of ['executor-offered','executor-stale','specialist-offered','specialist-no-executor','cancelled']){
    await page.evaluate(state=>{
      clearPreparation();clearReceipts();
      const specialist=state.startsWith('specialist');
      const x={actor_ref:'e'.repeat(64),run_id:'55555555-5555-4555-8555-555555555555',dispatch_id:'11111111-1111-4111-8111-111111111111',preparation_id:'22222222-2222-4222-8222-222222222222',case_id:'33333333-3333-4333-8333-333333333333',revision:1,preparation_revision:3,goal:'合成渲染测试 · 场地与设备协作',role:specialist?'park_specialist':'service_executor',dependency:state==='executor-stale'?'STALE':'CURRENT',is_current_offer:true,case_cancelled:state==='cancelled',history:[],current_offer:state==='specialist-no-executor'?null:{id:'44444444-4444-4444-8444-444444444444',state:'OFFERED',executor_id:'synthetic-executor',reason:'原角色动作展示核对'}};
      renderDispatch(x,specialist?{executors:state==='specialist-no-executor'?[]:[{id:'synthetic-executor'}],ready:false}:null);
    },state);
    await page.waitForTimeout(60);
    const value={state,acceptVisible:await page.locator('#dispatch-accept').isVisible(),acceptDisabled:await page.locator('#dispatch-accept').isDisabled(),withdrawVisible:await page.locator('#dispatch-withdraw').isVisible(),offerVisible:await page.locator('#dispatch-offer').isVisible(),message:await page.locator('#dispatch-current').innerText()};
    if(state==='executor-offered')check(value.acceptVisible&&!value.acceptDisabled&&!value.withdrawVisible,'executor original offer controls');
    if(state==='executor-stale')check(value.acceptDisabled,'stale source permits acceptance');
    if(state==='specialist-offered')check(!value.acceptVisible&&value.withdrawVisible,'specialist can accept another role offer');
    if(state==='specialist-no-executor')check(!value.offerVisible&&value.message.includes('没有可分派'),'missing assignment lacks safe explanation');
    if(state==='cancelled')check(!value.acceptVisible&&!value.offerVisible,'cancelled case retains write entry');
    results.push(value);
  }
  check(!errors.length&&!writes.length,'page error or business write');
  return {scope:'original renderDispatch with explicit synthetic DTOs; not real backend or role authorization',results,errors,writes};
}
