from pathlib import Path
p=Path('src/parkweave/web.html');s=p.read_text()
def replace(a,b):
 global s
 assert s.count(a)==1,(a[:80],s.count(a))
 s=s.replace(a,b)
replace('<button id="receipt-refresh" class="secondary">刷新当前回执</button>','<button id="receipt-refresh" class="secondary">刷新当前回执</button><p id="receipt-submit-status" class="notice" aria-live="polite"></p><button id="receipt-submit-recover" type="button" class="secondary" hidden>只读核对原人工提交</button><button id="receipt-submit-release" type="button" class="secondary" hidden>核对后读取当前回执</button>')
replace('caseCancelHandle||caseReconHandle||dispatchAcceptStoredPending()','caseCancelHandle||caseReconHandle||receiptSubmitStoredPending()||dispatchAcceptStoredPending()')
replace("if(dispatchAcceptStoredPending()){const e=Error('原接单结果待只读核对，禁止另一写入');", "if(receiptSubmitStoredPending()){const e=Error('原人工回执结果待只读核对，禁止另一写入');e.independentEntryRefusal=true;if(handler){args[0]?.preventDefault?.();pageError(e);return;}throw e;}\n if(dispatchAcceptStoredPending()){const e=Error('原接单结果待只读核对，禁止另一写入');")
replace("owns('receiptLocalExecute',receiptLocalPending)","owns('receiptCommand',receiptSubmitHandle)||owns('receiptLocalExecute',receiptLocalPending)")
replace("function clearReceipts(preservePlan=false){clearReceiptHistory();", "function clearReceipts(preservePlan=false){receiptSubmitHandle=null;receiptSubmitProof=null;receiptSubmitBusy=false;$('receipt-submit-status').textContent='';receiptSubmitControls();clearReceiptHistory();")
# Hydration never releases the persisted unknown request.
replace("$('receipt-error').textContent='';$('page-feedback').textContent='';}\nasync function loadReceipt", "$('receipt-error').textContent='';$('page-feedback').textContent='';receiptSubmitHandle=receiptSubmitRead(x);receiptSubmitControls();}\nasync function loadReceipt")
# Only the manual submission path gets the new lifecycle. Decisions retain their original path.
replace("const path='/api/executor-receipts/'+encodeURIComponent(c.id)+'/commands',signature=path+JSON.stringify(body);let key=receiptRetries.get(signature);", "if(action==='SUBMIT'){await sendReceiptSubmit(c,body);return;}const path='/api/executor-receipts/'+encodeURIComponent(c.id)+'/commands',signature=path+JSON.stringify(body);let key=receiptRetries.get(signature);")
replace("async function receiptCommand(action){if(receiptLocalPending)","async function receiptCommand(action){if(receiptSubmitHandle||receiptSubmitStoredPending())throw Error('原人工回执结果待只读核对');if(receiptLocalPending)")
replace("if(['dispatch-accept-recover','dispatch-accept-release'].includes(id))", "if(['receipt-submit-recover','receipt-submit-release'].includes(id))return [...entryWriteRequests.values()].every(op=>entryWriteDomain(op.path)==='receipt');\n if(['dispatch-accept-recover','dispatch-accept-release'].includes(id))")
block='''// Manual SUBMIT recovery retains only original coordinates, never text or token.
let receiptSubmitHandle=null,receiptSubmitProof=null,receiptSubmitBusy=false;
const receiptSubmitStorage='parkweave.receipt-submit.v1.';
function receiptSubmitStoredPending(){try{return Object.keys(localStorage).some(n=>n.startsWith(receiptSubmitStorage));}catch{return true;}}
function receiptSubmitHandles(actor){
  try{
    if(!/^[a-f0-9]{64}$/.test(actor))return null;
    const names=Object.keys(localStorage).filter(n=>n.startsWith(receiptSubmitStorage+actor+'.'));
    if(names.length>8)return null;
    const now=Date.now(),rows=[];
    for(const name of names){
      const raw=localStorage.getItem(name);if(typeof raw!=='string'||raw.length>640)return null;
      const h=JSON.parse(raw);
      if(!h||typeof h!=='object'||Array.isArray(h)||Object.keys(h).sort().join(',')!=='action,actor,case,expires,key,preparation,preparation_revision,revision,run,step,v'||h.v!==1||h.action!=='SUBMIT'||h.actor!==actor||name!==receiptSubmitStorage+h.actor+'.'+h.step||!['case','step','preparation','run'].every(k=>uuidHandle(h[k]))||!uuidHandle(h.key)||!Number.isInteger(h.revision)||h.revision<1||h.revision>63||!Number.isInteger(h.preparation_revision)||h.preparation_revision<1||h.preparation_revision>64||!Number.isFinite(h.expires)||h.expires<=now||h.expires>now+86400000)return null;
      rows.push(Object.freeze({...h,name,raw}));
    }
    return rows;
  }catch{return null;}
}
function receiptSubmitRead(x){
  const rows=receiptSubmitHandles(x.actor_ref);if(rows===null)return Object.freeze({invalid:true});
  const h=rows.find(h=>h.step===x.step.id);if(!h)return rows.length?Object.freeze({invalid:true}):null;
  if(h.preparation!==x.step.preparation_id||h.case!==x.step.case_id||h.run!==x.step.run_id||h.preparation_revision!==x.step.preparation_revision)return Object.freeze({invalid:true});
  return h;
}
function receiptSubmitControls(){
  const h=receiptSubmitHandle;
  $('receipt-submit-recover').hidden=!h;$('receipt-submit-recover').disabled=receiptSubmitBusy||!!h?.invalid;
  $('receipt-submit-release').hidden=!receiptSubmitProof;$('receipt-submit-release').disabled=receiptSubmitBusy;
  if(h){
    for(const id of ['receipt-submit-button','receipt-ack','receipt-correct','receipt-reopen','receipt-local-execution-button'])$(id).disabled=true;
    $('receipt-submit-status').textContent=h.invalid?'原人工回执句柄损坏、过期或属于其他事项；保留记录，停止新写入并人工核对。':receiptSubmitProof?'原人工提交已记录；请明确读取当前回执后继续。':'原人工回执结果待核对；只GET原编号，不自动重发提交。';
  }
}
function receiptSubmitBound(c,h){
  requireReceipt(c);
  const s=receiptView?.step;
  if(!h||h.invalid||receiptSubmitHandle!==h||receiptView?.actor_ref!==h.actor||s?.id!==h.step||s.preparation_id!==h.preparation||s.case_id!==h.case||s.run_id!==h.run||s.preparation_revision!==h.preparation_revision||c.id!==h.step||receiptSubmitHandles(h.actor)===null||localStorage.getItem(h.name)!==h.raw)throw Error('原人工回执上下文或保存句柄已变化；保留记录重新核对');
}
async function receiptSubmitGet(c,h){
  receiptSubmitBound(c,h);
  const q=new URLSearchParams({preparation_id:h.preparation,case_id:h.case,run_id:h.run,expected_revision:String(h.revision),preparation_revision:String(h.preparation_revision)});
  const x=await receiptCall('/api/executor-receipts/'+h.step+'/submit-recovery?'+q,'GET',undefined,h.key,c);
  receiptSubmitBound(c,h);
  const expected={scope:'SYNTHETIC_ASSIGNED_EXECUTOR_RECEIPT_ONLY',actor_ref:h.actor,step_id:h.step,preparation_id:h.preparation,case_id:h.case,run_id:h.run,expected_revision:h.revision,preparation_revision:h.preparation_revision,request_key:h.key,historical_only:true,read_only:true,automatically_replayed:false,case_goal_completed:false};
  if(!x||!Object.entries(expected).every(([k,v])=>typeof x[k]===typeof v&&x[k]===v)||!['COMMITTED','NOT_OBSERVED'].includes(x.status)||(x.status==='NOT_OBSERVED'?x.event!==null:!x.event||!uuidHandle(x.event.id)||!uuidHandle(x.event.receipt_id)||x.event.action!=='SUBMIT'||x.event.revision!==h.revision+1||!Number.isInteger(x.event.receipt_version)||x.event.receipt_version<1||x.event.receipt_version>63||!/^[a-f0-9]{64}$/.test(x.event.receipt_sha256)))throw Error('原人工回执只读证明不匹配；保留句柄');
  return x;
}
async function receiptSubmitRecover(release=false){
  const c=receiptCtx(),h=receiptSubmitHandle,executor=receiptView?.step.executor_id;if(receiptSubmitBusy)return;
  receiptSubmitBound(c,h);receiptSubmitBusy=true;receiptSubmitControls();
  try{
    const x=await receiptSubmitGet(c,h);receiptSubmitBound(c,h);receiptSubmitProof=x.status==='COMMITTED'?x:null;
    if(!receiptSubmitProof){$('receipt-submit-status').textContent='尚未观察到原人工提交；结果仍未知，原请求可能稍后到达。不重发、不另提回执。';return;}
    if(!release)return;
    const current=await receiptCall('/api/executor-receipts/'+h.step,'GET',undefined,undefined,c);receiptSubmitBound(c,h);
    const s=current?.step,e=x.event;
    if(typeof executor!=='string'||current.scope!=='SYNTHETIC_ASSIGNED_EXECUTOR_RECEIPT_ONLY'||current.role!=='service_executor'||current.actor_ref!==h.actor||s?.id!==h.step||s.executor_id!==executor||s.preparation_id!==h.preparation||s.case_id!==h.case||s.run_id!==h.run||s.preparation_revision!==h.preparation_revision||!Number.isInteger(s.revision)||s.revision<e.revision||s.revision>64||!['AWAITING_RECEIPT','RECEIPT_RECORDED','CHANGES_REQUESTED','LOCAL_ACKNOWLEDGED'].includes(s.state)||!Array.isArray(current.history)||!Array.isArray(current.receipt_history)||!current.history.some(t=>t.action==='SUBMIT'&&t.revision===e.revision&&t.payload?.step_id===h.step&&t.payload.receipt_id===e.receipt_id&&t.payload.receipt_sha256===e.receipt_sha256&&!t.payload.adapter_execution&&!t.payload.record_mode)||!current.receipt_history.some(r=>r.id===e.receipt_id&&r.step_id===h.step&&r.version===e.receipt_version&&r.source_sha256===e.receipt_sha256&&r.actor_id===executor&&r.source_kind==='SYNTHETIC'&&!r.adapter_execution))throw Error('当前回执与原人工提交证明不匹配；保留句柄');
    renderReceipt(current);requireReceipt(c);
    if(localStorage.getItem(h.name)!==h.raw)throw Error('原人工回执句柄已替换，保留新记录');
    localStorage.removeItem(h.name);if(localStorage.getItem(h.name)!==null)throw Error('原人工回执句柄尚未清除，保持只读核对');
    for(const op of entryWriteRequests.values())if(op.key===h.key&&op.path==='/api/executor-receipts/'+h.step+'/commands'&&op.token==='Bearer '+c.token){op.verified=true;entryWriteRequests.delete(op.signature);}
    receiptSubmitHandle=null;receiptSubmitProof=null;renderReceipt(current);
    $('receipt-submit-status').textContent='已核对原人工提交并读取当前回执；未重发提交、核对或步骤验证。';
  }catch(e){e.receiptContext=c;if(receiptCurrent(c)&&e.status===403)receiptError(e);throw e;}
  finally{if(receiptCurrent(c)){receiptSubmitBusy=false;receiptSubmitControls();}}
}
async function sendReceiptSubmit(c,body){
  requireReceipt(c);const x=receiptView,s=x.step;
  if(x.role!=='service_executor'||x.can_submit!==true||x.is_current_step!==true||receiptSubmitHandles(x.actor_ref)?.length!==0||!body.text.trim()||!body.source_label.trim())throw Error('请先读取本人当前合法回执并填写合成内容和来源，核对所有原人工提交');
  const h={v:1,action:'SUBMIT',actor:x.actor_ref,preparation:s.preparation_id,case:s.case_id,run:s.run_id,step:s.id,key:crypto.randomUUID(),revision:c.revision,preparation_revision:s.preparation_revision,expires:Date.now()+86400000},name=receiptSubmitStorage+h.actor+'.'+h.step,raw=JSON.stringify(h),draft=receiptDraft();
  localStorage.setItem(name,raw);if(localStorage.getItem(name)!==raw)throw Error('原人工回执编号保存失败，尚未发送请求');
  receiptSubmitHandle=receiptSubmitRead(x);receiptSubmitBound(c,receiptSubmitHandle);receiptSubmitBusy=true;receiptSubmitControls();
  let received=false;
  try{await receiptCall('/api/executor-receipts/'+c.id+'/commands','POST',body,h.key,c);received=true;}
  catch(e){if(!receiptCurrent(c))throw e;if(e.status===403){receiptError(e);throw e;}$('receipt-submit-status').textContent='原人工提交响应未核实；句柄保留，只读核对原编号。';}
  finally{if(receiptCurrent(c)){receiptSubmitBusy=false;receiptSubmitControls();}}
  requireReceipt(c);
  if(received){await receiptSubmitRecover(true);requireReceipt(c);if(receiptDraft()===draft)resetReceiptDraft();}
}
$('receipt-submit-recover').onclick=()=>receiptSubmitRecover().catch(receiptError);
$('receipt-submit-release').onclick=()=>receiptSubmitRecover(true).catch(receiptError);

'''
replace('async function receiptCommand(action){',block+'async function receiptCommand(action){')
p.write_text(s)
