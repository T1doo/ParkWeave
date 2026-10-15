async function planSourceConflictReceipt(x,c,h){
 if(!x||x.scope!=='OWNER_PLAN_SOURCE_CONFLICT'||x.schema!==1||x.actor_ref!==h.actor||x.preparation_id!==h.id||x.case_id!==c.caseId||x.run_id!==preparationView?.preparation.run_id||x.plan_id!==h.plan||x.automatically_replayed!==false||!['COMMITTED','NOT_OBSERVED'].includes(x.status))throw Error('原人工说明请求范围无法核对，恢复引用保留');
 if(x.status==='NOT_OBSERVED'){if(x.receipt!==null)throw Error('未观察响应证明不完整');throw Error('尚未观察到原请求，可能仍在途中；只能继续原 key GET核对。');}
 const r=x.receipt;
 if(!r||!uuidHandle(r.id)||r.plan_id!==h.plan||r.request_key!==h.key||r.fingerprint!==h.fingerprint||r.action!==h.action||!Number.isInteger(r.revision)||r.coordination_only!==true||!r.plan_note||r.plan_note.request?.card_id!==h.card||!Array.isArray(x.current?.history)||x.current.history.filter(e=>receiptHistoryCanonical(e)===receiptHistoryCanonical(r)).length!==1)throw Error('原人工说明保存证明不匹配，恢复引用保留');
 if(await coldDigest({actor_id:r.actor_id})!==h.actor||await coldDigest({preparation_id:h.id,...r.plan_note.request})!==h.fingerprint)throw Error('原请求主体或正文指纹不匹配');
 if(!planSourceConflictCurrent(c))return;
 const anchor=oppCtx(),refreshing=loadServiceCasePlan(c.id),refreshGeneration=servicePlanGeneration;
 try{
  await refreshing;oppRequire(anchor);await loadOpportunities();oppRequire(anchor);
  $('plan-source-conflict-card').value=x.current?.card_id||'';
  const next=planSourceConflictContext();planSourceConflictCheck(x.current,next);
  planSourceConflictBusy=true;planSourceConflictControls();
  // The original plan GET may persist an invalidation observation and advance
  // xmin. Read a fresh proof after those original GETs, before enabling a choice.
  const fresh=await planSourceConflictCall(next,next.selection?'?card_id='+encodeURIComponent(next.selection):'');
  planSourceConflictCheck(fresh,next);
  if(fresh.history.filter(e=>receiptHistoryCanonical(e)===receiptHistoryCanonical(r)).length!==1)throw Error('当前历史未核对到原说明事件，引用保留');
  const saved=planSourceConflictHandles()?.find(v=>v.name===h.name);
  if(!saved||receiptHistoryCanonical(saved)!==receiptHistoryCanonical(h))throw Error('原人工说明恢复引用已变化');
  localStorage.removeItem(h.name);if(localStorage.getItem(h.name)!==null)throw Error('原恢复引用仍待核对');
  clearOpportunityPlan();planSourceConflictBusy=false;renderPlanSourceConflict(fresh,next);
 }finally{if(oppCurrent(anchor)&&servicePlanGeneration===refreshGeneration){planSourceConflictBusy=false;planSourceConflictControls();}}
}
