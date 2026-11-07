/* Startup inside the shipped workspace. No HTTP or business calls before startup. */
(() => {
  'use strict';
  const make=(tag,text,cls)=>{const node=document.createElement(tag);if(text)node.textContent=text;if(cls)node.className=cls;return node;};
  const dialog=make('dialog','','desktop-startup-panel');
  dialog.setAttribute('aria-labelledby','desktop-startup-heading');
  const title=make('h2','打开园合工作台');title.id='desktop-startup-heading';
  const intro=make('p','使用已有数据继续办理，或在此电脑创建新的工作台。','subtitle');
  const modes=make('div','','actions'),open=make('button','打开已有工作台'),create=make('button','创建新工作台');
  open.type=create.type='button';modes.append(open,create);
  const form=make('form'),location=make('label','数据目录'),path=make('input');
  path.required=true;path.maxLength=2048;path.autocomplete='off';location.append(path);
  const passwordFields=make('fieldset'),legend=make('legend','设置独立角色密码');
  passwordFields.append(legend);const passwords=[];
  const accounts=[['fixture-a','企业'],['prep-specialist-fixture-a','专员'],['sample-executor-a','执行者'],['sample-resource-admin-a','资源管理员']];
  for(const [account,label] of accounts){const row=make('label',label),input=make('input');input.type='password';input.autocomplete='new-password';input.required=true;input.minLength=12;input.maxLength=512;row.append(input);passwordFields.append(row);passwords.push([account,input]);}
  const advanced=make('details'),advancedTitle=make('summary','高级设置');
  const ports=make('div','','actions'),dbLabel=make('label','数据库端口'),apiLabel=make('label','应用端口');
  const db=make('input'),api=make('input');for(const node of [db,api]){node.type='number';node.min='1';node.max='65535';node.step='1';}
  db.value='55432';api.value='58761';dbLabel.append(db);apiLabel.append(api);ports.append(dbLabel,apiLabel);
  const profileLabel=make('label',' 首次为已有工作台建立桌面配置'),profile=make('input');profile.type='checkbox';profileLabel.prepend(profile);
  advanced.append(advancedTitle,ports,profileLabel);
  const notice=make('p','','status');notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');
  const submit=make('button','打开工作台','primary');submit.type='submit';
  form.append(location,passwordFields,advanced,notice,submit);
  dialog.append(title,intro,modes,form,make('p','本地合成工作台 · 创建并不代表真实园区受理或履约。','boundary-note'));
  let mode='reopen',pending=false;
  function select(next){if(pending)return;mode=next;const isNew=mode==='new';passwordFields.hidden=!isNew;passwordFields.disabled=!isNew;ports.hidden=!isNew;for(const input of [db,api]){input.disabled=!isNew;input.required=isNew;}profileLabel.hidden=isNew;submit.textContent=isNew?'创建工作台':'打开工作台';open.setAttribute('aria-pressed',String(!isNew));create.setAttribute('aria-pressed',String(isNew));open.classList.toggle('primary',!isNew);create.classList.toggle('primary',isNew);for(const [,input] of passwords)input.value='';notice.textContent='';}
  open.onclick=()=>select('reopen');create.onclick=()=>select('new');
  form.addEventListener('invalid',event=>{if(advanced.contains(event.target))advanced.open=true;},true);
  form.onsubmit=event=>{
    event.preventDefault();if(pending||!form.reportValidity())return;
    const data={action:mode,instance:path.value.trim(),database_port:0,api_port:0,passwords:{},initialize_profile:mode==='new'||profile.checked,sample_collaboration:true};
    if(!data.instance){notice.textContent='请选择或填写数据目录。';path.focus();return;}
    if(mode==='new'){
      data.database_port=Number(db.value);data.api_port=Number(api.value);
      if(![data.database_port,data.api_port].every(n=>Number.isInteger(n)&&n>0&&n<=65535)||data.database_port===data.api_port){notice.textContent='两个端口须为不同的 1–65535 整数。';advanced.open=true;api.focus();return;}
      const values=passwords.map(([,input])=>input.value);
      if(values.some(v=>[...v].length<12||[...v].length>256)||new Set(values).size!==values.length){notice.textContent='各角色密码须不同，长度为 12–256 个字符。';return;}
      passwords.forEach(([key,input])=>{data.passwords[key]=input.value;});
    }
    const bridge=window.chrome?.webview;
    if(!bridge){notice.textContent='当前是页面预览，尚未连接桌面启动器。';return;}
    pending=true;submit.disabled=true;notice.textContent='正在核对工作台启动条件…';
    try{bridge.postMessage(JSON.stringify({protocol:'PARKWEAVE_STARTUP_V1',request:data}));}
    catch{notice.textContent='启动请求是否送达尚未确认，请保留当前目录，不要重复提交。';}
    finally{for(const [,input] of passwords)input.value='';}
  };
  dialog.addEventListener('cancel',event=>event.preventDefault());
  window.chrome?.webview?.addEventListener('message',event=>{
    const data=event.data;
    if(!data||data.protocol!=='PARKWEAVE_STARTUP_V1'||!['REFUSED','UNKNOWN','STARTING'].includes(data.state)||typeof data.message!=='string')return;
    notice.textContent=data.message.slice(0,2000);
    // Unknown work must be resolved by the host; never auto-resubmit.
    if(data.state==='REFUSED'){pending=false;submit.disabled=false;}
  });
  const style=make('style');style.textContent='.desktop-startup-panel{width:min(620px,calc(100vw - 32px));max-height:calc(100dvh - 48px);padding:28px;border:1px solid var(--edge);border-radius:var(--container-radius);background:var(--surface-reading);color:var(--ink);box-shadow:var(--shadow-panel)}.desktop-startup-panel::backdrop{background:rgb(225 234 250 / .65)}.desktop-startup-panel input:not([type=checkbox]){width:100%}.desktop-startup-panel fieldset{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 16px}.desktop-startup-panel legend{font-size:16px}.desktop-startup-panel .actions>label{flex:1;min-width:120px}@media(max-width:480px){.desktop-startup-panel{padding:20px}.desktop-startup-panel fieldset{grid-template-columns:1fr}}';
  document.head.append(style);document.body.append(dialog);select('reopen');dialog.showModal();
})();
