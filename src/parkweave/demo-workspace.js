/* Local concept demo. No API, model, external booking or authority. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const KEY='parkweave.product-demo.v1';
  const roles={enterprise:'企业负责人',specialist:'园区专员',executor:'执行人员','resource-admin':'资源管理员'};
  const views={service:'服务工作台',resource:'资源与空间',collaboration:'协同待办',detail:'事项档案'};
  const catalog=[
    {id:'venue-a',name:'多功能厅 A',type:'场地',number:'A01',tone:'',capacity:48,price:1200,description:'可容纳 48 人 · 灵活桌椅 · 有线网络'},
    {id:'venue-b',name:'共享会议室 B',type:'场地',number:'B02',tone:'violet',capacity:24,price:600,description:'可容纳 24 人 · 圆桌讨论 · 白板'},
    {id:'projector',name:'投影与音响套装',type:'设备',number:'AV',tone:'teal',capacity:1,price:300,description:'投影设备 · 无线麦克风 · 现场联调'}
  ];
  const defaults=()=>({
    schema:'parkweave-concept-demo/1',view:'service',role:'enterprise',scenario:'exchange',caseId:'PW-20261108-001',title:'企业技术交流活动',
    goal:'为 40 人的企业技术交流活动安排场地、投影与音响，并协调现场接待。周日下午 14:00 开始，预算控制在 3,000 元以内。',
    starts:'2026-11-08T14:00',ends:'2026-11-08T16:00',resourceStarts:'2026-11-08T14:00',resourceEnds:'2026-11-08T16:00',people:40,budget:3000,
    generated:false,materials:false,adopted:false,resourcesConfirmed:false,dispatched:false,accepted:false,receipted:false,completed:false,
    selected:[],equipmentQuantity:1,preview:'UNREAD',previewMessage:'',conflict:false,
    agenda:'活动主题：企业技术交流\n参加人数：40 人\n安排：14:00 开场交流，15:00 主题分享，15:40 自由讨论。',
    reception:'由企业负责人核对名单；园区协助引导入场，并在活动前完成设备联调。',
    receipt:'已按办理方案完成会场布置、设备联调和接待准备，现提交企业核对。',events:[],origin:'LOCAL_INTERACTIVE_DEMO'
  });
  function readState(){
    try{
      const s=JSON.parse(localStorage.getItem(KEY));
      if(!s||s.schema!=='parkweave-concept-demo/1'||!Object.hasOwn(roles,s.role)||!Object.hasOwn(views,s.view))return defaults();
      const base=defaults();
      if(s.caseId==='PW-DEMO-20261108-01')s.caseId='PW-20261108-001';
      if(s.caseId==='PW-DEMO-20261108-02')s.caseId='PW-20261108-002';
      if(Array.isArray(s.events))s.events=s.events.map(e=>e&&typeof e.label==='string'?{...e,label:e.label.replace('提交演示执行回执','提交执行回执').replace('确认本地资源组合','确认资源组合')}:e);
      if(typeof s.receipt==='string'&&s.receipt.startsWith('已按演示方案'))s.receipt=s.receipt.replace('已按演示方案','已按办理方案');
      for(const key of ['generated','materials','adopted','resourcesConfirmed','dispatched','accepted','receipted','completed','conflict'])if(typeof s[key]!=='boolean')return base;
      for(const key of ['goal','agenda','reception','receipt','title','starts','ends'])if(typeof s[key]!=='string'||s[key].length>4000)return base;
      if(!/^PW-20261108-00[12]$/.test(s.caseId)||!['exchange','training'].includes(s.scenario)||!['LOCAL_INTERACTIVE_DEMO','PRESET_FRAME_FOR_VIDEO'].includes(s.origin))return base;
      if(!['starts','ends'].every(key=>/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(s[key])&&Number.isFinite(Date.parse(s[key])))||Date.parse(s.ends)<=Date.parse(s.starts))return base;
      if(!Array.isArray(s.selected)||s.selected.some(id=>!catalog.some(r=>r.id===id))||new Set(s.selected).size!==s.selected.length)return base;
      if(!Array.isArray(s.events)||s.events.length>40||!Number.isInteger(s.people)||s.people<1||s.people>1000||!Number.isFinite(s.budget)||s.budget<0)return base;
      if(s.events.some(e=>!e||!Number.isInteger(e.sequence)||typeof e.label!=='string'||e.label.length>160||typeof e.actor!=='string'||e.actor.length>60))return base;
      if(s.materials&&!s.generated||s.adopted&&!s.materials||s.resourcesConfirmed&&!s.adopted||s.dispatched&&!s.resourcesConfirmed||s.accepted&&!s.dispatched||s.receipted&&!s.accepted||s.completed&&!s.receipted)return base;
      return {...base,...s,equipmentQuantity:Math.max(1,Math.min(5,Number(s.equipmentQuantity)||1))};
    }catch{return defaults();}
  }
  let state=readState(),busy=false,toastTimer;
  const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(state));}catch{}};
  const status=()=>state.completed?'已归档':state.receipted?'待企业确认':state.accepted?'执行中':state.dispatched?'待执行人员接单':state.resourcesConfirmed?'待派单':state.adopted?'待确认资源':state.materials?'待采用方案':state.generated?'待核对资料':'尚未建单';
  const timeText=()=>`${state.starts.slice(0,10)} ${state.starts.slice(11)}—${state.ends.slice(11)}`;
  const money=v=>Number(v).toLocaleString('zh-CN');
  const chosen=()=>catalog.filter(r=>state.selected.includes(r.id));
  const subtotal=()=>chosen().reduce((sum,r)=>sum+r.price*(r.type==='设备'?state.equipmentQuantity:1),0);
  const badge=(text,tone='')=>`<span class="badge ${tone}">${esc(text)}</span>`;
  const button=(action,text,{primary=false,disabled=false,extra=''}={})=>`<button type="button" data-action="${action}" ${extra} ${disabled?'disabled':''} class="${primary?'primary':''}">${text}</button>`;
  const heading=(title,copy)=>`<div class="page-heading"><div><h1 tabindex="-1" id="demo-view-heading">${title}</h1><p>${copy}</p></div><div class="heading-right">当前事项<strong>${state.generated?state.caseId:'等待创建'}</strong></div></div>`;
  const card=(title,body,{tag='',foot='',bodyClass=''}={})=>`<section class="demo-card"><div class="demo-card-head"><h2>${title}</h2>${tag}</div><div class="demo-card-body ${bodyClass}">${body}</div>${foot?`<div class="demo-card-foot">${foot}</div>`:''}</section>`;
  function event(text){state.events.push({sequence:state.events.length+1,label:text,actor:roles[state.role],at:new Date().toISOString(),demo:true});if(state.events.length>40)state.events.shift();}
  function toast(text){clearTimeout(toastTimer);$('demo-toast').textContent=text;$('demo-toast').hidden=false;toastTimer=setTimeout(()=>$('demo-toast').hidden=true,2800);}
  function roleNeeded(role){if(state.role===role)return true;toast(`请先切换到${roles[role]}当前角色。`);return false;}
  function navigate(view){if(!Object.hasOwn(views,view))return;state.view=view;save();render();$('demo-main').scrollTop=0;$('demo-view-heading')?.focus({preventScroll:true});}
  function journey(){
    const steps=[['明确服务目标','企业发起本次需求',state.generated],['核对材料与方案','保留输入来源和确认',state.adopted],['组合园区资源','检查时间、数量与预算',state.resourcesConfirmed],['协同执行与回执','角色分工与结果核对',state.receipted],['企业确认归档','汇总本次事项的办理记录',state.completed]];
    const done=steps.filter(x=>x[2]).length;
    return card('本次办理进度',`<div class="summary-row"><span>当前阶段</span><strong>${status()}</strong></div><div class="progress-track"><span data-progress="${done}"></span></div>${steps.map(([name,copy,ok],i)=>`<div class="journey-row ${ok?'done':i===done?'current':''}"><span class="journey-dot">${ok?'✓':i+1}</span><div><strong>${name}</strong><small>${copy}</small></div><span class="journey-state">${ok?'已完成':i===done?'当前':''}</span></div>`).join('')}`);
  }
  function caseSummary(){return card(state.generated?'继续本次事项':'本次事项',`<div class="case-title">${esc(state.title)}</div><p class="case-note">以一个活动目标，串起资料、空间、设备和现场协同。</p><dl class="case-meta"><div><dt>申请企业</dt><dd>澄光智能</dd></div><div><dt>参加人数</dt><dd>${state.people} 人</dd></div><div><dt>活动日期</dt><dd>${esc(state.starts.slice(5,10))}</dd></div><div><dt>预算上限</dt><dd>¥ ${money(state.budget)}</dd></div></dl>${state.generated?`<div class="soft-line"></div>${button('view-detail','查看事项档案')}`:''}`,{tag:badge(state.generated?status():'待发起','purple')});}
  function artifacts(){
    const list=[['plan','办理方案','目标、服务步骤与责任分工','MD'],['materials','材料清单','输入内容、来源和核对状态','MD'],['resources','资源组合','资源、时段与检查结果','JSON'],['record','办理记录','协同事件与办理状态快照','JSON']];
    return card('本次事项输出',list.map(([key,name,copy,ext])=>`<div class="artifact-row"><div class="artifact-label"><span class="file-tile">${ext}</span><div><strong>${name}</strong><small>${copy}</small></div></div>${button('download','导出',{disabled:!state.generated,extra:`data-kind="${key}"`})}</div>`).join(''));
  }
  function quickExports(){return card('方案与资料',`<div class="artifact-row"><div class="artifact-label"><span class="file-tile">MD</span><strong>办理方案</strong></div>${button('download','导出',{extra:'data-kind="plan"'})}</div><div class="artifact-row"><div class="artifact-label"><span class="file-tile">MD</span><strong>材料清单</strong></div>${button('download','导出',{extra:'data-kind="materials"'})}</div>`);}
  function planRows(){
    return [['01','活动资料准备','活动安排、人员规模与接待要求','企业负责人',state.materials?'已核对':'待核对',state.materials?'success':'warning'],['02','场地与设备组合','将空间、设备与活动时段一起核对','资源协调',state.resourcesConfirmed?'已确认':'待确认',state.resourcesConfirmed?'success':'neutral'],['03','现场执行协同','派单、接单与执行回执留在同一事项','园区专员',state.receipted?'已回执':state.accepted?'执行中':state.dispatched?'待接单':'待派单',state.receipted?'success':'neutral']].map(([n,title,copy,owner,text,tone])=>`<div class="plan-row"><span class="plan-number">${n}</span><div><h3>${title}</h3><p>${copy}</p></div><span class="plan-owner">${owner}</span>${badge(text,tone)}</div>`).join('');
  }
  function serviceView(){
    if(!state.generated){
      const form=`<form id="demo-goal-form"><label for="demo-goal">本次目标</label><textarea id="demo-goal" class="goal-input" required maxlength="2000">${esc(state.goal)}</textarea><div class="scenario-chips">${button('scenario','技术交流活动',{extra:'data-scenario="exchange"'})}${button('scenario','企业培训',{extra:'data-scenario="training"'})}</div><div class="field-grid three"><label>开始时间<input id="demo-start" type="datetime-local" required value="${state.starts}"></label><label>结束时间<input id="demo-end" type="datetime-local" required value="${state.ends}"></label><label>参加人数<input id="demo-people" type="number" min="1" max="1000" required value="${state.people}"></label></div><div class="field-grid"><label>预算上限（元）<input id="demo-budget" type="number" min="0" max="1000000" required value="${state.budget}"></label><label>申请企业<input value="澄光智能科技" readonly></label></div><div id="demo-form-error" class="demo-error" role="alert"></div><div class="form-actions"><span class="subdued"></span><button type="submit" class="primary" ${busy?'disabled':''}>${busy?'<span class="busy-dot"></span>正在组织方案':'组织办理方案'}</button></div></form>`;
      return heading('服务工作台','从一个目标开始，组织本次园区服务。')+`<div class="demo-grid"><div>${card('这次想办什么？',form,{tag:badge('目标导向')})}</div><aside>${caseSummary()}${journey()}</aside></div>`;
    }
    const next=!state.adopted?'核对资料并采用方案':!state.resourcesConfirmed?'前往资源组合':!state.completed?'前往协同办理':'查看归档事项';
    const body=`<p class="detail-goal">${esc(state.goal)}</p><div class="detail-summary"><div><small>活动时间</small><strong>${esc(state.starts.slice(0,10))}</strong></div><div><small>参加人数</small><strong>${state.people} 人</strong></div><div><small>预算上限</small><strong>¥ ${money(state.budget)}</strong></div></div><div class="soft-line"></div>${planRows()}`;
    return heading('服务工作台','把目标拆成可核对、有责任人的服务步骤。')+`<div class="demo-grid"><div>${card(esc(state.title)+' · 办理方案',body,{tag:badge(state.adopted?'方案已采用':'待核对后采用',state.adopted?'success':'warning'),foot:`<small>园合助手</small>${button('next-service',next,{primary:true})}`})}</div><aside>${journey()}${quickExports()}</aside></div>`;
  }
  function resourceView(){
    const locked=state.dispatched||state.role!=='enterprise';
    const basket=chosen().map(r=>`<div class="bundle-row"><div><strong>${r.name}</strong>${r.type==='设备'?`<input class="bundle-quantity" id="demo-equipment-quantity" aria-label="设备套数" type="number" min="1" max="5" value="${state.equipmentQuantity}" ${locked?'disabled':''}>`:badge('1 场','neutral')}</div><p>${r.type==='设备'?'投影、音响与联调':'场地使用'} · 参考 ¥ ${money(r.price)}</p></div>`).join('');
    const preview=state.preview==='PASS'?'<div class="info-strip success">时段、数量和预算检查通过。</div>':state.preview==='CONFLICT'?`<div class="info-strip warning" role="alert">${esc(state.previewMessage)}</div>`:'';
    const cards=catalog.map(r=>`<article class="resource-choice ${state.selected.includes(r.id)?'selected':''}"><div class="resource-visual ${r.tone}"><strong>${r.number}</strong><span>${r.type}</span></div><div class="resource-copy"><h3>${r.name}</h3><p>${r.description}</p><div class="resource-action"><span>参考 ¥ ${money(r.price)} / ${r.type==='场地'?'场':'套'}</span>${button('toggle-resource',state.selected.includes(r.id)?'已加入组合':'加入组合',{disabled:locked,extra:`data-resource="${r.id}"`})}</div></div></article>`).join('');
    const directory=`<div class="resource-toolbar"><label>开始时间<input id="resource-demo-start" type="datetime-local" value="${state.resourceStarts}" ${locked?'disabled':''}></label><label>结束时间<input id="resource-demo-end" type="datetime-local" value="${state.resourceEnds}" ${locked?'disabled':''}></label></div><div class="resource-cards">${cards}</div>`;
    const summary=`${basket||'<div class="empty-state"><strong>尚未选择资源</strong>从目录加入一个场地和设备。</div>'}<div class="bundle-total"><span>参考金额</span><span>¥ ${money(subtotal())}</span></div>${preview}<div class="demo-stack">${button('check-resources','检查时间与数量',{disabled:locked||!state.selected.length})}${button('confirm-resources',state.resourcesConfirmed?'组合已确认':'确认资源组合',{primary:true,disabled:locked||!state.adopted||state.preview!=='PASS'||state.resourcesConfirmed})}${state.resourcesConfirmed?button('view-collaboration','前往协同办理'):''}</div>`;
    return heading('资源与空间','把场地、设备与活动条件放在一起核对。')+`<div class="demo-grid"><div>${!state.adopted?'<div class="info-strip">可先浏览资源；采用办理方案后再确认资源组合。</div>':''}${card('资源目录',directory,{tag:button('recommend-resources','使用推荐组合',{disabled:locked})})}<div class="form-actions"><span class="subdued">当前人数 ${state.people} 人 · 预算 ¥ ${money(state.budget)}</span></div></div><aside>${card('本次资源组合',summary,{tag:badge(`${state.selected.length} 项`)})}</aside></div>`;
  }
  function roleNudge(role,text){return `<div class="role-nudge"><span>${text}</span>${button('switch-role',`切换至${roles[role]}`,{extra:`data-role="${role}"`})}</div>`;}
  function collaborationView(){
    if(!state.generated)return heading('协同待办','让责任人、执行动作与回执围绕同一事项协作。')+card('本次事项协同',`<div class="empty-state"><strong>还没有待办事项</strong>先从服务工作台提出本次目标。<div class="form-actions">${button('view-service','前往服务工作台',{primary:true})}</div></div>`);
    let action='';
    if(!state.adopted||!state.resourcesConfirmed)action='<div class="info-strip">请先采用方案并确认资源组合，再派发执行任务。</div>'+button('view-service','查看办理方案',{primary:true});
    else if(!state.dispatched)action=state.role==='specialist'?`<label>执行任务说明<textarea id="demo-dispatch-note">根据已确认的活动安排，完成会场布置、设备联调与现场接待，并提交执行回执。</textarea></label><div class="form-actions"><span class="subdued">现场服务组</span>${button('dispatch','派发任务',{primary:true})}</div>`:roleNudge('specialist','资源组合已确认，等待园区专员派单。');
    else if(!state.accepted)action=state.role==='executor'?`<div class="info-strip">请核对活动时间、场地与执行要求，再确认接单。</div>${button('accept','确认接单',{primary:true})}`:roleNudge('executor','任务已派发，等待执行人员接单。');
    else if(!state.receipted)action=state.role==='executor'?`<div class="info-strip success">已接单。完成执行步骤后，提交本次回执。</div>${button('receipt','填写执行回执',{primary:true})}`:roleNudge('executor','执行人员已接单，当前处于执行阶段。');
    else if(!state.completed)action=`<div class="receipt-block"><h3>执行回执已提交</h3><p>${esc(state.receipt)}</p></div>`+(state.role==='enterprise'?`<div class="form-actions"><span class="subdued">由企业明确核对结果，保留确认记录。</span>${button('complete','核对并确认完成',{primary:true})}</div>`:roleNudge('enterprise','回执已到达，等待企业负责人核对。'));
    else action=`<div class="receipt-block"><h3>本次事项已确认完成</h3><p>方案、资料、资源组合与协同事件已汇总到事项档案。</p></div><div class="form-actions">${button('view-detail','查看完整档案',{primary:true})}${button('download','导出办理记录',{extra:'data-kind="record"'})}</div>`;
    const task=`<p class="case-note">${esc(state.goal)}</p><div class="collab-task"><div><small>活动时段</small><strong>${esc(timeText())}</strong></div><div><small>资源组合</small><strong>${state.resourcesConfirmed?chosen().map(r=>r.name).join('＋'):'尚未确认'}</strong></div><div><small>协调角色</small><strong>园区专员</strong></div><div><small>执行角色</small><strong>现场服务组 · 执行人员</strong></div></div>${action}`;
    return heading('协同待办','让责任分工与结果核对留在同一条办理链中。')+`<div class="collab-grid"><div>${card('与本次事项相关',`<div class="collab-list"><button data-action="focus-task"><strong>${esc(state.title)}</strong><p>澄光智能 · ${state.caseId}<br>${esc(state.starts.slice(0,10))} · ${state.people} 人</p>${badge(status(),state.completed?'success':'purple')}</button></div>`,{tag:badge('1 项')})}</div><div>${card(esc(state.title)+' · 现场执行',task,{tag:badge(status(),state.completed?'success':state.accepted?'purple':'warning')})}</div></div>`;
  }
  function detailView(){
    if(!state.generated)return heading('事项档案','把目标、过程与结果放在一起查看。')+card('本次事项档案','<div class="empty-state"><strong>尚未创建事项</strong>从服务工作台开始本次办理。</div>');
    const overview=`<p class="detail-goal">${esc(state.goal)}</p><div class="detail-summary"><div><small>申请企业</small><strong>澄光智能科技</strong></div><div><small>活动时间</small><strong>${esc(timeText())}</strong></div><div><small>参加规模</small><strong>${state.people} 人</strong></div></div>`;
    const materials=`<article class="material-card"><div><h3>活动安排</h3>${badge(state.materials?'已核对 · v1':'待核对',state.materials?'success':'warning')}</div><p>${esc(state.agenda)}</p><small>来源：企业填写</small></article><article class="material-card"><div><h3>接待与执行要求</h3>${badge('企业提供','neutral')}</div><p>${esc(state.reception)}</p><small>来源：企业填写</small></article>`;
    const trail=`<ol class="timeline">${state.events.map(e=>`<li><strong>${esc(e.label)}</strong><small>${esc(e.actor)}</small></li>`).join('')}</ol>`;
    return heading(esc(state.title),'一份事项档案，连接目标、来源、资源与协同记录。')+`<div class="detail-grid"><div class="demo-stack">${card('事项概览',overview,{tag:badge(status(),state.completed?'success':'purple')})}${card('材料与来源',`<div class="material-grid">${materials}</div>`,{foot:state.adopted?'':`<small>核对本次事项输入与来源。</small>${button('materials','核对并采用方案',{primary:true})}`})}${state.receipted?card('执行回执',`<div class="receipt-block"><p>${esc(state.receipt)}</p></div>`,{tag:badge(state.completed?'企业已确认':'待企业确认',state.completed?'success':'warning')}):''}</div><aside>${card('办理时间线',trail,{tag:badge(`${state.events.length} 条`)})}${card('本次事项成果',`<div class="demo-exports-inline">${button('download','成果页 HTML',{primary:true,extra:'data-kind="report"'})}${button('download','办理记录 JSON',{extra:'data-kind="record"'})}</div>`)}</aside></div>`;
  }
  function render(){
    document.querySelectorAll('[data-view]').forEach(node=>{node.disabled=busy;if(node.dataset.view===state.view)node.setAttribute('aria-current','page');else node.removeAttribute('aria-current');});
    $('demo-role').value=state.role;$('demo-role-name').textContent=roles[state.role];$('demo-avatar').textContent=({enterprise:'企',specialist:'园',executor:'执','resource-admin':'资'})[state.role];
    $('demo-page-title').textContent=views[state.view];
    $('demo-content').innerHTML=`<div class="view-enter">${({service:serviceView,resource:resourceView,collaboration:collaborationView,detail:detailView})[state.view]()}</div>`;
    $('demo-role').disabled=busy;$('demo-reset').disabled=busy;
    if(busy)$('demo-goal-form')?.querySelectorAll('input,textarea,button').forEach(node=>node.disabled=true);
    document.querySelectorAll('[data-progress]').forEach(node=>node.style.width=(Number(node.dataset.progress)*20)+'%');
  }
  function openDialog(title,body,actions){
    const dialog=$('demo-dialog');
    dialog.innerHTML=`<div class="dialog-heading"><h2 id="demo-dialog-title">${title}</h2>${button('close-dialog','关闭')}</div>${body}${actions||''}`;
    dialog.showModal();
  }
  function materialsDialog(){
    if(!state.generated){toast('先组织本次办理方案。');return;}
    if(!roleNeeded('enterprise'))return;
    const readonly=state.adopted;
    const form=`<form id="demo-material-form"><div class="dialog-body"><div class="info-strip">逐项核对本次事项输入，再明确采用方案。</div><label>活动安排<textarea id="demo-agenda" required maxlength="3000" ${readonly?'readonly':''}>${esc(state.agenda)}</textarea></label><label>接待与执行要求<textarea id="demo-reception" required maxlength="3000" ${readonly?'readonly':''}>${esc(state.reception)}</textarea></label>${readonly?'<p class="subdued">本次事项资料已核对；原文保留在事项档案中。</p>':'<div class="soft-line"></div><label class="demo-check"><input type="checkbox" id="demo-material-confirm" required>我已核对本次事项资料</label>'}</div><div class="dialog-actions">${readonly?button('close-dialog','返回事项'):'<button type="submit" class="primary">确认资料并采用方案</button>'}</div></form>`;
    openDialog('核对活动资料',form);
  }
  function receiptDialog(){
    if(!state.accepted||state.receipted||!roleNeeded('executor'))return;
    openDialog('提交执行回执',`<form id="demo-receipt-form"><div class="dialog-body"><div class="collab-task"><div><small>执行事项</small><strong>${esc(state.title)}</strong></div><div><small>本次资源</small><strong>${chosen().map(r=>r.name).join('＋')}</strong></div></div><label>完成说明<textarea id="demo-receipt-text" required maxlength="2000">${esc(state.receipt)}</textarea></label><div class="soft-line"></div><label class="demo-check"><input type="checkbox" required>我已核对执行事项与检查结果</label></div><div class="dialog-actions"><button type="submit" class="primary">提交回执供企业核对</button></div></form>`);
  }
  function invalidateResources(){state.preview='UNREAD';state.previewMessage='';state.resourcesConfirmed=false;}
  function checkResources(){
    if(state.dispatched)return;
    const start=$('resource-demo-start'),end=$('resource-demo-end');
    if(start)state.resourceStarts=start.value;if(end)state.resourceEnds=end.value;
    const quantity=$('demo-equipment-quantity');if(quantity)state.equipmentQuantity=Number(quantity.value);
    const room=chosen().find(r=>r.type==='场地');
    let issue='';
    if(!state.resourceStarts||!state.resourceEnds||!Number.isFinite(Date.parse(state.resourceStarts))||!Number.isFinite(Date.parse(state.resourceEnds))||Date.parse(state.resourceEnds)<=Date.parse(state.resourceStarts))issue='请选择有效时段，结束时间须晚于开始时间。';
    else if(!room||!state.selected.includes('projector'))issue='请在本次事项中选择一个场地和投影音响套装。';
    else if(state.people>room.capacity)issue=`${room.name}的容量为 ${room.capacity} 人，当前 ${state.people} 人。请调整资源或活动规模。`;
    else if(!Number.isInteger(state.equipmentQuantity)||state.equipmentQuantity!==1)issue='本次事项可用的投影音响套装为 1 套，请调整数量。';
    else if(Date.parse(state.resourceStarts)>Date.parse(state.starts)||Date.parse(state.resourceEnds)<Date.parse(state.ends))issue='资源使用时段须覆盖活动时间，请调整开始或结束时间。';
    else if(room.id==='venue-a'&&Date.parse(state.resourceStarts)<Date.parse('2026-11-08T14:00')&&Date.parse(state.resourceEnds)>Date.parse('2026-11-08T12:00'))issue='多功能厅 A 在 12:00—14:00 已有安排。请将资源开始时间调整至 14:00，或重新选择场地。';
    else if(subtotal()>state.budget)issue=`参考金额 ¥ ${money(subtotal())} 超过预算 ¥ ${money(state.budget)}，请调整组合。`;
    state.preview=issue?'CONFLICT':'PASS';state.previewMessage=issue;state.resourcesConfirmed=false;save();render();
    toast(issue?'条件尚未满足，组合没有确认。':'本次事项的资源条件检查通过。');
  }
  function requireResourceEditor(){if(state.role==='enterprise'&&!state.dispatched)return true;toast('当前角色或办理阶段仅可查看资源。');return false;}
  function act(action,node){
    if(action.startsWith('view-')){navigate(action.slice(5));return;}
    if(action==='close-dialog'){$('demo-dialog').close();return;}
    if(action==='switch-role'){state.role=node.dataset.role;save();render();toast(`已切换至：${roles[state.role]}`);return;}
    if(action==='download'){download(node.dataset.kind);return;}
    if(action==='scenario'){
      state=defaults();state.scenario=node.dataset.scenario;
      if(state.scenario==='training'){state.caseId='PW-20261108-002';state.title='企业新员工培训';state.people=20;state.budget=2000;state.goal='为 20 人的新员工培训安排会议室和投影设备，活动 14:00 开始，安排入场引导与设备联调。';state.agenda='培训主题：新员工协作与业务流程\n参加人数：20 人\n安排：14:00 培训说明，15:00 分组练习，15:40 交流答疑。';}
      save();render();return;
    }
    if(action==='next-service'){
      if(!state.adopted)materialsDialog();else navigate(!state.resourcesConfirmed?'resource':state.completed?'detail':'collaboration');return;
    }
    if(action==='materials'){materialsDialog();return;}
    if(action==='toggle-resource'){
      if(!requireResourceEditor())return;
      const id=node.dataset.resource,r=catalog.find(r=>r.id===id);if(!r)return;
      if(state.selected.includes(id))state.selected=state.selected.filter(x=>x!==id);
      else{if(r.type==='场地')state.selected=state.selected.filter(x=>catalog.find(c=>c.id===x)?.type!=='场地');state.selected.push(id);}
      invalidateResources();save();render();return;
    }
    if(action==='recommend-resources'){
      if(!requireResourceEditor())return;state.selected=[state.people<=24?'venue-b':'venue-a','projector'];state.equipmentQuantity=1;invalidateResources();save();render();toast('已按参加人数加入推荐场地与设备，确认前请检查条件。');return;
    }
    if(action==='check-resources'){if(requireResourceEditor())checkResources();return;}
    if(action==='confirm-resources'){
      if(!requireResourceEditor()||!state.adopted||state.preview!=='PASS'||state.resourcesConfirmed)return;
      state.resourcesConfirmed=true;event('确认资源组合');save();render();toast('资源组合已确认，下一步由专员派单。');return;
    }
    if(action==='dispatch'){
      if(!roleNeeded('specialist')||!state.resourcesConfirmed||state.dispatched)return;
      state.dispatched=true;event('园区专员派发现场任务');save();render();toast('任务已派发，等待执行人员接单。');return;
    }
    if(action==='accept'){
      if(!roleNeeded('executor')||!state.dispatched||state.accepted)return;
      state.accepted=true;event('执行人员确认接单');save();render();toast('已接单，完成执行后可提交回执。');return;
    }
    if(action==='receipt'){receiptDialog();return;}
    if(action==='complete'){
      if(!roleNeeded('enterprise')||!state.receipted||state.completed)return;
      state.completed=true;event('企业核对回执并确认归档');save();render();toast('本次事项已归档，可导出方案与办理记录。');return;
    }
    if(action==='focus-task')document.querySelector('.collab-grid>div:last-child')?.scrollIntoView({block:'nearest'});
  }
  function snapshot(){
    const utc=value=>{const parsed=new Date(value+':00+08:00');return Number.isFinite(parsed.valueOf())?parsed.toISOString():null;};
    return {schema:'parkweave-demo-export/1',scope:'SYNTHETIC_CONCEPT_DEMO',origin:state.origin,case_id:state.caseId,title:state.title,goal:state.goal,
      demonstration_only:true,real_backend_execution:false,real_model_call:false,external_booking_confirmed:false,actual_fulfillment_evidence:false,
      enterprise:'澄光智能科技',park:'星澜创新园',status:status(),people:state.people,budget_reference:state.budget,
      starts_at:utc(state.starts),ends_at:utc(state.ends),resource_starts_at:utc(state.resourceStarts),resource_ends_at:utc(state.resourceEnds),timezone:'Asia/Shanghai',
      materials:{agenda:state.agenda,reception:state.reception,confirmed_in_demo:state.materials,source:'DEMO_ENTERPRISE_INPUT'},
      resources:chosen().map(r=>({id:r.id,name:r.name,kind:r.type,quantity:r.type==='设备'?state.equipmentQuantity:1,price_reference:r.price})),
      resource_check:state.preview,combination_confirmed_in_demo:state.resourcesConfirmed,receipt:state.receipted?state.receipt:null,events:state.events,
      exported_at:new Date().toISOString()};
  }
  const mdText=text=>String(text).replace(/</g,'&lt;').replace(/>/g,'&gt;');
  function artifact(kind){
    const x=snapshot(),boundary='合成案例与本地预设流程演示；未调用真实模型，非真实预约、报价或履约证明。';
    const base=`# 园合 ParkWeave · ${mdText(state.title)}\n\n事项：${state.caseId}\n企业：澄光智能科技\n园区：星澜创新园\n当前状态：${status()}\n\n`;
    if(kind==='plan')return {name:'01-办理方案.md',mime:'text/markdown',content:base+`## 本次目标\n\n${mdText(state.goal)}\n\n## 办理条件\n\n- 时间：${timeText()}（Asia/Shanghai）\n- 参加人数：${state.people} 人\n- 预算上限：${money(state.budget)} 元（参考）\n\n## 服务步骤\n\n| 步骤 | 责任角色 | 核对内容 |\n| --- | --- | --- |\n| 活动资料准备 | 企业负责人 | 活动安排、人员规模、接待要求 |\n| 场地与设备组合 | 企业确认、园区协调 | 时间、数量、容量及预算 |\n| 现场执行协同 | 专员 / 执行人员 | 派单、接单、回执与企业核对 |\n\n方案整理：园合助手。\n`};
    if(kind==='materials')return {name:'02-材料清单.md',mime:'text/markdown',content:base+`## 活动安排\n\n${mdText(state.agenda)}\n\n## 接待与执行要求\n\n${mdText(state.reception)}\n\n来源：企业填写。\n核对状态：${state.materials?'已核对':'尚未核对'}。\n`};
    if(kind==='resources')return {name:'03-资源组合.json',mime:'application/json',content:JSON.stringify({schema:x.schema,scope:x.scope,boundary,case_id:x.case_id,starts_at:x.resource_starts_at,ends_at:x.resource_ends_at,timezone:x.timezone,resources:x.resources,price_reference_total:subtotal(),check:x.resource_check,confirmed_in_demo:x.combination_confirmed_in_demo,external_booking_confirmed:false},null,2)};
    if(kind==='report')return {name:'05-案例成果.html',mime:'text/html',content:reportHTML(x,boundary)};
    return {name:'04-办理记录.json',mime:'application/json',content:JSON.stringify(x,null,2)};
  }
  function reportHTML(x,boundary){
    return `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>园合 · 办理成果</title><style>body{font:15px/1.8 'Microsoft YaHei','Segoe UI',sans-serif;color:#253950;background:#f1f5fc;margin:0;padding:36px}.report{max-width:920px;margin:auto;background:white;padding:38px 44px;border:1px solid #b4c6df;border-radius:12px}h1{font-size:27px;margin:0 0 8px}h2{font-size:18px;border-bottom:1px solid #cfdbec;padding-bottom:8px;margin-top:28px}.brand{color:#315fc4;font-weight:700;margin-bottom:24px}.scope{font-size:12px;color:#6b7d94}.summary{display:flex;gap:30px;padding:18px 0;border-block:1px solid #d7e2f0;margin-top:20px}.summary strong{display:block;color:#385b8b}table{width:100%;border-collapse:collapse}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #dfe7f1;font-size:14px}th{background:#f2f6fd}.text{white-space:pre-wrap}li{margin-bottom:6px}@media print{body{padding:0;background:white}.report{border:0;padding:0;max-width:none}h2{break-after:avoid}tr{break-inside:avoid}}@page{size:A4;margin:18mm}</style><article class="report"><div class="brand">园合 ParkWeave · 办理成果</div><h1>${esc(x.title)}</h1><div class="summary"><div>事项编号<strong>${esc(x.case_id)}</strong></div><div>办理状态<strong>${esc(x.status)}</strong></div><div>参加人数<strong>${x.people} 人</strong></div></div><h2>从目标到服务</h2><p>${esc(x.goal)}</p><table><tr><th>服务步骤</th><th>责任角色</th><th>本次事项状态</th></tr><tr><td>活动资料准备</td><td>企业负责人</td><td>${state.materials?'已核对':'待核对'}</td></tr><tr><td>场地与设备组合</td><td>企业确认、园区协调</td><td>${state.resourcesConfirmed?'已确认资源组合':'待确认'}</td></tr><tr><td>现场执行与回执</td><td>园区专员 / 执行人员</td><td>${state.receipted?'已提交执行回执':'待执行'}</td></tr></table><h2>资源组合</h2><p>${esc(timeText())} · Asia/Shanghai</p><table><tr><th>资源</th><th>类型</th><th>数量</th><th>参考金额</th></tr>${x.resources.map(r=>`<tr><td>${esc(r.name)}</td><td>${esc(r.kind)}</td><td>${r.quantity}</td><td>¥ ${money(r.price_reference*r.quantity)}</td></tr>`).join('')}</table><h2>材料与来源</h2><p class="text">${esc(state.agenda)}</p><p class="text">${esc(state.reception)}</p><p class="scope">来源：企业填写；资料核对与办理状态同步保留。</p>${state.receipted?`<h2>执行回执</h2><p>${esc(state.receipt)}</p>`:''}<h2>办理留痕</h2><ol>${state.events.map(e=>`<li>${esc(e.label)} · ${esc(e.actor)}</li>`).join('')}</ol></article></html>`;
  }
  function download(kind){
    if(!state.generated){toast('先组织本次办理方案。');return;}
    const file=artifact(kind),url=URL.createObjectURL(new Blob([file.content],{type:file.mime+';charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download='ParkWeave-'+file.name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),15000);toast('文件已生成，请选择保存位置。');
  }
  function exportDialog(){
    if(!state.generated){toast('先创建事项，再导出办理文件。');return;}
    openDialog('导出办理文件',`<div class="dialog-body">${[['plan','办理方案','MD'],['materials','材料清单','MD'],['resources','资源组合','JSON'],['record','办理记录','JSON'],['report','案例成果页','HTML']].map(([kind,name,format])=>`<div class="artifact-row"><div class="artifact-label"><span class="file-tile">${format}</span><strong>${name}</strong></div>${button('download','导出',{extra:`data-kind="${kind}"`})}</div>`).join('')}</div>`);
  }
  document.addEventListener('click',e=>{
    const nav=e.target.closest('[data-view]');if(nav){if(!busy)navigate(nav.dataset.view);return;}
    const target=e.target.closest('[data-action]');if(target&&!target.disabled){if(busy)return;if(target.dataset.action==='reset-confirm'){state=defaults();save();$('demo-dialog').close();render();toast('已新建事项，可以输入本次目标。');return;}act(target.dataset.action,target);}
  });
  document.addEventListener('submit',async e=>{
    const form=e.target;if(!['demo-goal-form','demo-material-form','demo-receipt-form'].includes(form.id))return;e.preventDefault();
    if(busy||!form.reportValidity())return;
    if(form.id==='demo-goal-form'){
      if(!roleNeeded('enterprise'))return;
      const goal=$('demo-goal').value.trim(),starts=$('demo-start').value,ends=$('demo-end').value;
      if(!goal||Date.parse(ends)<=Date.parse(starts)){$('demo-form-error').textContent='请填写本次目标，并确保结束时间晚于开始时间。';return;}
      state.goal=goal;state.starts=starts;state.ends=ends;state.resourceStarts=starts;state.resourceEnds=ends;state.people=Number($('demo-people').value);state.budget=Number($('demo-budget').value);
      busy=true;render();await new Promise(resolve=>setTimeout(resolve,480));busy=false;state.generated=true;event('企业提出活动目标');save();render();toast('办理方案已生成，下一步核对资料。');
    }else if(form.id==='demo-material-form'){
      if(!roleNeeded('enterprise')||state.adopted||!state.generated)return;
      state.agenda=$('demo-agenda').value.trim();state.reception=$('demo-reception').value.trim();
      if(!state.agenda||!state.reception)return;state.materials=true;event('核对活动资料与来源');state.adopted=true;event('明确采用办理方案');save();$('demo-dialog').close();render();toast('资料与方案已确认，下一步组合园区资源。');
    }else{
      if(!roleNeeded('executor')||!state.accepted||state.receipted)return;
      state.receipt=$('demo-receipt-text').value.trim();if(!state.receipt)return;
      state.receipted=true;event('提交执行回执');save();$('demo-dialog').close();render();toast('回执已提交，等待企业负责人核对。');
    }
  });
  document.addEventListener('change',e=>{
    if(e.target.id==='demo-role'){if(busy)return;state.role=e.target.value;save();render();return;}
  });
  document.addEventListener('input',e=>{
    if(['resource-demo-start','resource-demo-end','demo-equipment-quantity'].includes(e.target.id)){
      if(!requireResourceEditor())return;
      if(e.target.id==='resource-demo-start')state.resourceStarts=e.target.value;
      if(e.target.id==='resource-demo-end')state.resourceEnds=e.target.value;
      if(e.target.id==='demo-equipment-quantity')state.equipmentQuantity=Number(e.target.value);
      invalidateResources();save();const confirm=document.querySelector('[data-action="confirm-resources"]');if(confirm)confirm.disabled=true;
      document.querySelectorAll('.demo-grid>aside .info-strip').forEach(node=>node.remove());
    }
  });
  $('demo-reset').onclick=()=>{if(!busy)openDialog('新建事项','<div class="dialog-body"><p>将新建事项并清空当前工作区。已导出的文件会保留。</p></div>',`<div class="dialog-actions">${button('close-dialog','保留当前事项')}${button('reset-confirm','新建事项',{primary:true})}</div>`);};
  $('demo-export-menu').onclick=exportDialog;
  function replay(name){
    const levels={goal:0,plan:1,materials:2,resources:3,conflict:3,dispatch:4,offer:4,accepted:5,receipt:6,complete:7};
    if(!Object.hasOwn(levels,name))throw Error('UNKNOWN_DEMO_FRAME');
    const level=levels[name];state=defaults();state.origin='PRESET_FRAME_FOR_VIDEO';
    state.generated=level>=1;state.materials=state.adopted=level>=2;
    if(level>=3){state.selected=['venue-a','projector'];state.preview='PASS';}
    state.resourcesConfirmed=level>=4;state.dispatched=level>=5||name==='offer';state.accepted=level>=5;state.receipted=level>=6;state.completed=level>=7;
    if(name==='conflict'){state.resourceStarts='2026-11-08T13:00';state.preview='CONFLICT';state.previewMessage='多功能厅 A 在 12:00—14:00 已有安排。请将资源开始时间调整至 14:00，或重新选择场地。';}
    state.view=level===0||name==='plan'?'service':name==='materials'||name==='complete'?'detail':level===3?'resource':'collaboration';
    state.role=name==='dispatch'?'specialist':['offer','accepted'].includes(name)?'executor':'enterprise';
    const logs=[['generated','企业提出活动目标','企业负责人'],['materials','核对活动资料与来源','企业负责人'],['adopted','明确采用办理方案','企业负责人'],['resourcesConfirmed','确认资源组合','企业负责人'],['dispatched','园区专员派发现场任务','园区专员'],['accepted','执行人员确认接单','执行人员'],['receipted','提交执行回执','执行人员'],['completed','企业核对回执并确认归档','企业负责人']];
    for(const [flag,label,actor] of logs)if(state[flag])state.events.push({sequence:state.events.length+1,label,actor,at:new Date(Date.UTC(2026,10,6,1,30+state.events.length*3)).toISOString(),demo:true});
    save();render();$('demo-main').scrollTop=0;return snapshot();
  }
  window.ParkWeaveDemo=Object.freeze({snapshot:()=>JSON.parse(JSON.stringify(snapshot())),state:()=>JSON.parse(JSON.stringify(state)),replay,artifacts:()=>['plan','materials','resources','record','report'].map(artifact)});
  render();document.body.dataset.demoReady='true';
})();
