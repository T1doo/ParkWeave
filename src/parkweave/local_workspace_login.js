/* Existing local password provider; no new identities or persisted secrets. */
(function () {
 'use strict';
 const get=id=>document.getElementById(id),form=get('local-workspace-login'),
  password=get('local-workspace-password'),account=get('local-workspace-account'),
  submit=get('local-workspace-submit'),logout=get('local-workspace-logout'),
  back=get('local-workspace-materials'),status=get('local-workspace-status'),token=get('token');
 let busy=false,generation=0,journal=null;
 const originalFetch=globalThis.fetch.bind(globalThis);
 const locked=()=>{document.body.dataset.localWorkspace='locked';form.hidden=false;logout.hidden=true;};
 function pendingMaterial(){
  if(journal&&journal.read())throw Error('原资料操作仍待只读核对。请返回资料工作台，以原账号核对；不会重发。');
 }
 function canLeave(){
  if(busy)throw Error('登录请求尚未结束，请等待。');
  pendingMaterial();
  const refusal=preparationClearRefusal();if(refusal)throw Error(refusal);
  if(activeEntryWriteFlow||entryWriteRequests.size||originalStoredWritePending())
   throw Error('原操作仍在处理或待核对，请留在原入口只读核对后再退出。');
 }
 function erase(){
  generation++;token.value='';password.value='';journal=null;
  // Run oninput and every original registered identity invalidation listener.
  token.dispatchEvent(new Event('input',{bubbles:true}));locked();
 }
 // A material UNKNOWN created in another tab also pauses this entry's writes.
 // Original GET recovery remains available. Never settle or replay its handle.
 const originalEntryFetch=entryFetch;
 entryFetch=function(path,options={}){
  // Check before the original tracker reserves a business request key.
  if((options.method||'GET').toUpperCase()!=='GET')pendingMaterial();
  return originalEntryFetch(path,options);
 };
 globalThis.fetch=function(path,options={}){
  if((options.method||'GET').toUpperCase()!=='GET')pendingMaterial();
  return originalFetch(path,options);
 };
 form.onsubmit=async event=>{
  event.preventDefault();if(busy||token.value)return;
  busy=true;submit.disabled=true;account.disabled=true;const own=++generation;
  const selected=account.value,secret=password.value;password.value='';
  try{
   const response=await originalFetch('/api/local/session',{method:'POST',redirect:'error',
    credentials:'omit',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:selected,password:secret})});
   const value=await response.json();if(own!==generation)return;
   if(!response.ok){
    if(response.status===503&&value.code==='LOCAL_IDENTITY_STORAGE_UNAVAILABLE')
     throw Error('本地账户资料暂不可读取。请停止工作台，保留原安装；有原备份时恢复原受保护身份文件后重开，没有备份请交维护方处理，不要新建安装覆盖。');
    if(response.status>=500)throw Error('本地登录未完成，原因或结果待核对。请保留原安装并停止工作台，不要反复尝试或重建账号。');
    throw Error(response.status===429?'尝试较多，请稍后再试。':'账号不可用或密码不正确。');
   }
   if(typeof value.bearer!=='string'||value.bearer.length<1||value.bearer.length>512||/[\x00-\x20\x7f]/.test(value.bearer))
    throw Error('本地登录响应不完整，请返回资料工作台。');
   const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value.bearer));
   if(own!==generation)return;
   const credential=[...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('');
   journal=ParkWeavePending.journal(localStorage,value.installation_id,value.actor,credential,navigator.locks);
   pendingMaterial();token.value=value.bearer;token.dispatchEvent(new Event('input',{bubbles:true}));
   document.body.dataset.localWorkspace='active';form.hidden=true;logout.hidden=false;
   status.textContent='已登录。服务、资源与协同按本安装现有配置和授权开放；不会自动办理。';
  }catch(error){
   if(own===generation){token.value='';locked();status.textContent=error.message;}
  }finally{if(own===generation){busy=false;submit.disabled=false;account.disabled=false;}}
 };
 logout.onclick=()=>{try{canLeave();erase();status.textContent='已退出；会话未保存。';}catch(error){status.textContent=error.message;}};
 back.onclick=()=>{
  try{
   // A refused login with an existing material UNKNOWN must allow returning
   // to its original recovery page; no business session was activated here.
   if(token.value)canLeave();else if(busy)throw Error('登录请求尚未结束，请等待。');
   if(token.value)erase();location.assign('/');
  }catch(error){status.textContent=error.message;}
 };
 window.addEventListener('pagehide',()=>{generation++;token.value='';password.value='';journal=null;});
})();
