/* Presentation-only workspace composition. Existing handlers own all reads/writes. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const make = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const setText = (node, text) => { if (node && node.textContent !== text) node.textContent = text; };
  const fieldName = (id, text) => {
    const label = $(id)?.closest('label');
    const node = label && [...label.childNodes].find(child => child.nodeType === Node.TEXT_NODE);
    if (node) node.textContent = text;
  };
  const readableTime = value => value ? String(value).replace('T', ' ').replace(/Z$/, '') : '未提供';

  function serviceWorkspace() {
    const heading=document.querySelector('.primary-entry-heading');
    if(heading)$('service').prepend(heading);
    setText(heading?.querySelector('.subtitle'),'先说明本次需要的协助，再核对服务与资料。');
    const hint=make('p','要办什么 · 期望时间 · 必须满足的条件','v3-goal-hint');hint.id='workspace-goal-hint';
    const goal=$('prep-goal');goal.before(hint);goal.placeholder='输入本次目标…';
    goal.setAttribute('aria-describedby',[goal.getAttribute('aria-describedby'),hint.id].filter(Boolean).join(' '));
    fieldName('prep-goal', '本次目标');
    fieldName('existing-preparation-id', '资料事项编号');
    const paths = document.querySelector('.atelier-paths');
    setText(paths?.querySelector('h2'), '本页定位');
    const names = ['目标与条件', '服务方案', '材料与来源'];
    paths?.querySelectorAll('a').forEach((link, index) => {
      link.replaceChildren(document.createTextNode(names[index] || link.textContent));
    });
    setText(document.querySelector('.atelier-utilities > .atelier-section-heading h2'), '工具与记录');
    const info = document.querySelector('.atelier-continuation .atelier-inline-help');
    if (info) setText(info.querySelector('summary'), '只读权限说明');
  }

  function resourceWorkspace() {
    const resource = $('resource'), form = $('resource-form'), view = $('resource-catalog-view');
    if (!resource || !form || !view) return;
    const preparation = resource.querySelector('.resource-preparation');
    const catalogButton = $('resource-catalog');
    setText(catalogButton, '读取资源目录');
    setText(resource.querySelector('.resource-heading h2'), '选择资源与使用时段');
    setText(resource.querySelector('.resource-heading .subtitle'), '读取目录后填写资源、时间和数量，再预检。预检不等于占位或真实预约。');
    fieldName('resource-select', '资源');
    fieldName('resource-quantity', '数量（份）');
    fieldName('resource-ttl', '占位有效期（秒，5–300）');
    const originalLabel = $('resource-select').closest('label');
    const picker = make('div','','v2-resource-picker');
    originalLabel.before(picker);
    const infoButton = make('button', '资源详情与完整名称', 'v2-text-button');
    infoButton.type = 'button';
    const heading = make('div', '', 'v2-picker-heading');
    const label = make('label','资源');
    label.htmlFor='resource-select';
    heading.append(label,infoButton);
    const selectedName=make('p','','v3-selected-resource-name');selectedName.hidden=true;
    picker.append(heading,$('resource-select'),selectedName);
    originalLabel.remove();
    const constraints = make('div', '', 'v2-constraints');
    constraints.hidden = true;
    constraints.setAttribute('aria-label', '所选资源的使用约束');
    picker.after(constraints);
    const calendar = form.querySelector('.design-calendar');
    if (calendar) constraints.after(calendar);

    const details = make('details', '', 'v2-resource-details');
    details.id = 'workspace-resource-details';
    details.append(make('summary', '资源详情与数据来源'));
    infoButton.setAttribute('aria-controls', details.id);
    const returnButton = make('button', '返回资源表单', 'v2-text-button');
    returnButton.type = 'button';
    returnButton.onclick = () => {
      $('resource-select').focus({preventScroll:true});
      picker.scrollIntoView({block:'nearest'});
    };
    view.before(details);
    details.append(returnButton, view);
    const intentions = preparation.querySelector('.design-resource-intentions');
    if (intentions) intentions.before(form);
    preparation.append(details);

    // Precheck uses resource/time/quantity. Hold-specific fields remain in the
    // same original form, so native required validation and submit ownership stay intact.
    const previewActions=make('div','','v2-precheck-actions');
    const preview=$('resource-preview');
    if (preview) previewActions.append(preview);
    const quantity=$('resource-quantity').closest('label');
    quantity.classList.add('v2-resource-quantity');
    const quantityRow=make('div','','v3-quantity-row');quantity.before(quantityRow);quantityRow.append(quantity,previewActions);
    const result=$('resource-preview-result');
    if(result) quantityRow.after(result);
    if(result){
      const evidence=make('details','','v2-precheck-evidence'),caption=make('summary','预检依据与范围');
      evidence.append(caption);evidence.hidden=true;result.after(evidence);
      let renderedView=null;
      const projectPreview=()=>{
        const preview=typeof resourcePreview!=='undefined'?resourcePreview:null;
        const valid=preview&&typeof resourceCurrent==='function'&&resourceCurrent(preview.context);
        if(!valid){renderedView=null;evidence.hidden=true;evidence.open=false;evidence.replaceChildren(caption);return;}
        const value=preview.view;
        if(renderedView===value)return;
        renderedView=value;
        const number=value=>Number.isFinite(value)?String(value):'未提供';
        result.replaceChildren(
          make('strong',value.available?'预检通过，可尝试占位':'当前区间容量不足'),
          make('span','当前占用 '+number(value.occupied_peak)+' / 容量 '+number(value.capacity)+'；可用 '+number(value.available_quantity)+' 份。'),
          make('span','尚未占位；创建与确认仍需明确操作，外部资源可用性未知。')
        );
        evidence.hidden=false;evidence.open=false;
        evidence.replaceChildren(caption,parkFieldList([
          ['本地观察时间',readableTime(value.server_time)+' UTC（非上游更新时间）'],
          ['资源版本',value.resource_revision],
          ['来源',value.source.kind+' / '+value.source.id+' / v'+value.source.revision],
          ['来源说明',value.source.statement],
          ['适用范围','仅本地合成账本（LOCAL_AUTHORITY）'],
          ['外部可用性',value.external_availability],
          ['预约状态',value.reservation],
          ['外部受理',value.external_acceptance],
          ['线下履约',value.offline_fulfillment]
        ]));
      };
      new MutationObserver(projectPreview).observe(result,{childList:true,subtree:true,characterData:true});
    }
    const holdFields=make('div','','v2-hold-fields');
    holdFields.append(make('h3','短期占位'));
    const ttl=$('resource-ttl').closest('label');
    const purpose=form.querySelector('label:has(#resource-purpose)') || [...form.querySelectorAll(':scope > label')].find(label=>label!==picker&&label!==quantity&&label!==ttl&&!label.querySelector('[type=datetime-local]'));
    holdFields.append(ttl);
    if(purpose)holdFields.append(purpose);
    const actions=form.querySelector(':scope > .actions');
    if(actions)holdFields.append(actions);
    const boundary=preparation.querySelector(':scope > .notice');
    if(boundary){boundary.classList.add('v2-action-boundary');holdFields.append(boundary);}
    const alternatives=form.querySelector(':scope > fieldset');
    if(alternatives)alternatives.before(holdFields);else form.append(holdFields);
    $('resource-hold')?.classList.add('secondary');

    const selectedCard = () => [...view.querySelectorAll('.resource-catalog-card')]
      .find(card => card.dataset.resourceId === $('resource-select').value);
    const openDetails = () => {
      const card = selectedCard();
      if (!card || form.hidden) return;
      details.hidden = false;
      details.open = true;
      const name = card.querySelector('strong') || card;
      name.tabIndex = -1;
      name.focus({preventScroll:true});
      name.scrollIntoView({block:'start'});
    };
    infoButton.onclick = openDetails;
    let previous = '';
    function refreshConstraints() {
      const card = selectedCard(), valid = !!card && !form.hidden;
      infoButton.disabled = !valid;
      constraints.hidden = !valid;selectedName.hidden=!valid;
      details.hidden = !view.querySelector('.resource-catalog-card');
      if (!valid) {
        constraints.replaceChildren();selectedName.textContent='';
        previous = '';
        return;
      }
      setText(selectedName,card.dataset.resourceName);
      const option=$('resource-select').selectedOptions[0];if(option&&option.textContent!==card.dataset.resourceName)option.textContent=card.dataset.resourceName;
      const buffer=Number(card.dataset.resourceBuffer),bufferText=Number.isFinite(buffer)&&buffer>=0?buffer+' 秒'+(buffer%60===0?' / '+buffer/60+' 分钟':''):'未提供';
      const fields=[['目录容量',card.dataset.resourceCapacity],['缓冲时间',bufferText],['开放区间（UTC）',readableTime(card.dataset.resourceOpenFrom)+' — '+readableTime(card.dataset.resourceOpenUntil)]];
      const signature = JSON.stringify(fields);
      if (signature !== previous) {
        previous = signature;
        const caption=make('div','','v3-constraint-caption');caption.append(make('strong','目录约束'),make('span','非当前剩余可用量'));constraints.replaceChildren(caption,parkFieldList(fields));
      }
    }
    $('resource-select').addEventListener('change', refreshConstraints);
    form.addEventListener('input', refreshConstraints);
    new MutationObserver(refreshConstraints).observe(view, {childList:true, subtree:true});
    new MutationObserver(refreshConstraints).observe(form, {attributes:true, attributeFilter:['hidden']});
    refreshConstraints();

    // The existing summary always distinguishes a form draft from selected holds.
    const summary = $('park-resource-summary');
    const decorateSummary = () => {
      const draftTitle=summary?.querySelector('.resource-input-summary h4');setText(draftTitle,'正在填写（未计入组合）');
      if(typeof combinationSelection!=='undefined')setText(summary?.querySelector('.resource-summary-details>h4'),'已选占位组合 '+combinationSelection.size+' 项');
      const row = summary?.querySelector('.resource-input-summary .workspace-facts > div');
      const value = row?.querySelector('dd');
      if (value && !value.querySelector('button')) {
        const name = make('button', '查看当前所选资源', 'v2-resource-name');
        name.type = 'button';
        name.setAttribute('aria-label', '查看资源完整名称与来源：' + value.textContent);
        name.onclick = openDetails;
        value.replaceChildren(name);
      }
    };
    if (summary) new MutationObserver(decorateSummary).observe(summary, {childList:true, subtree:true});
    decorateSummary();
    for(const button of form.querySelectorAll('.design-date-trigger')){button.setAttribute('aria-label',button.textContent);setText(button,button.closest('label')?.querySelector('#resource-start')?'开始日期面板':'结束日期面板');}
  }

  function collaborationWorkspace() {
    const root = $('collaboration');
    if (!root) return null;
    setText(root.querySelector('.collaboration-heading h2'), '协同事项');
    setText(root.querySelector('.collaboration-heading .subtitle'), '按当前身份读取事项，核对状态后进入办理。');
    const lanes = [...root.querySelectorAll('.collaboration-lane')];
    const definitions = [
      {key:'preparation',label:'资料事项',panel:root.querySelector('.collaboration-preparation'),buttons:['prep-tasks','prep-list'],lists:['prep-task-items','prep-items'],statuses:['prep-task-status'],hint:'尚未读取资料事项。请选择“读取资料待办”或“读取资料事项”。'},
      {key:'dispatch',label:'派单',panel:lanes[0],buttons:['dispatch-list'],lists:['dispatch-items'],statuses:['dispatch-list-status'],hint:'尚未读取派单。点击“刷新派单”读取当前身份可见记录。'},
      {key:'receipt',label:'执行回执',panel:lanes[1],buttons:['receipt-list'],lists:['receipt-items'],statuses:['receipt-list-status'],hint:'尚未读取回执。点击“刷新回执”读取当前身份可见记录。'},
      {key:'notice',label:'通知',panel:root.querySelector('.collaboration-notices'),buttons:['notice-list'],lists:['notice-items'],statuses:['notice-error'],hint:'尚未读取通知。点击“刷新通知”读取当前身份可见记录。'},
      {key:'progress',label:'办理进度',panel:$('case-worklist'),buttons:['case-worklist-read'],lists:['case-worklist-items'],statuses:['case-worklist-status'],hint:'通过“读取我的事项进度”查看当前有权范围。'},
      {key:'runtime',label:'运行核对',panel:root.querySelector('.collaboration-controls'),buttons:['record-directory-read'],lists:['record-directory-items'],statuses:['record-directory-status'],hint:'尚未读取运行记录。点击“读取运行记录”找回本人已有记录。'}
    ].filter(item => item.panel);
    const buttonNames = {'prep-tasks':'读取资料待办','prep-list':'读取资料事项','dispatch-list':'刷新派单','receipt-list':'刷新回执','notice-list':'刷新通知','record-directory-read':'读取运行记录'};
    for (const [id, label] of Object.entries(buttonNames)) setText($(id), label);
    const categories = make('nav', '', 'v2-categories');
    categories.setAttribute('role', 'tablist');
    categories.setAttribute('aria-label', '协同记录分类');
    const filter = root.querySelector('.design-list-filters');
    if (filter) filter.after(categories); else root.querySelector('header').after(categories);
    root.querySelector('header').after(categories);
    const readingSurface=make('div','','v4-collaboration-surface');
    categories.after(readingSurface);
    if(filter)readingSurface.append(filter);
    for(const item of definitions)readingSurface.append(item.panel);
    const shortcuts=root.querySelector('.design-collaboration-tabs');
    if(shortcuts){shortcuts.classList.add('v3-locate');shortcuts.prepend(make('span','定位入口'));root.querySelector('header').append(shortcuts);}
    const actionSlot=make('div','','v3-category-actions');filter?.querySelector(':scope > p')?.before(actionSlot);
    let active = 'preparation';
    let lastReadCategory=null, serial=0;
    const reading=new Map();
    for (const item of definitions) {
      const panel = item.panel;
      panel.classList.add('v2-category-panel');
      panel.setAttribute('role','tabpanel');
      if (!panel.id) panel.id = 'workspace-category-' + item.key;
      const tab = make('button', item.label);
      tab.type = 'button'; tab.id = 'workspace-category-tab-' + item.key;
      tab.setAttribute('role','tab'); tab.setAttribute('aria-controls', panel.id);
      panel.setAttribute('aria-labelledby', tab.id);
      tab.onclick = () => select(item.key);
      item.tab = tab; categories.append(tab);
      const toolbar = make('div', '', 'v2-list-toolbar');
      const title = panel.querySelector(':scope > h2,:scope > h3');
      toolbar.append(title || make('h3', item.label));
      const actions = make('div', '', 'v2-list-actions');
      for (const id of item.buttons) {
        const button = $(id);
        if (button && panel.contains(button) && !button.form) actions.append(button);
        if(button && typeof button.onclick==='function'){
          const original=button.onclick;
          button.onclick=function(...args){
            const sequence=++serial,identity=$('token')?.value;
            lastReadCategory=item.key;reading.set(item.key,sequence);refreshHints();
            const finish=()=>{if(reading.get(item.key)===sequence&&$('token')?.value===identity){reading.delete(item.key);refreshHints();}};
            try{return Promise.resolve(original.apply(this,args)).finally(finish);}catch(error){finish();throw error;}
          };
        }
      }
      toolbar.append(actions); panel.prepend(toolbar);item.actions=actions;item.toolbar=toolbar;
      if (item.hint && item.lists.some(id => $(id))) {
        const empty = make('div', item.hint, 'v2-empty');
        item.empty = empty; toolbar.after(empty);
      }
    }
    function select(key, focus=false) {
      active = key;
      for (const item of definitions) {
        item.panel.classList.toggle('v2-category-hidden', item.key !== key);
        item.tab.setAttribute('aria-selected', String(item.key === key));
        item.tab.tabIndex = item.key === key ? 0 : -1;
        if(item.actions)(item.key===key?actionSlot:item.toolbar).append(item.actions);
      }
      if (focus) definitions.find(item => item.key === key)?.tab.focus();
      refreshHints();
    }
    categories.addEventListener('keydown', event => {
      const index = definitions.findIndex(item => item.tab === event.target);
      if (index < 0 || !['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key==='Home' ? 0 : event.key==='End' ? definitions.length-1 : (index+(event.key==='ArrowRight'?1:-1)+definitions.length)%definitions.length;
      select(definitions[next].key, true);
    });
    function refreshHints() {
      for (const item of definitions) {
        if (!item.empty) continue;
        const rows = item.lists.flatMap(id => [...($(id)?.children || [])]);
        const status = item.statuses.map(id => $(id)).filter(Boolean);
        const hasResponse = rows.length || status.some(node => node.textContent.trim());
        const failed = lastReadCategory===item.key && $('page-feedback')?.dataset.tone==='error' && $('page-feedback').textContent.trim();
        const loading=reading.has(item.key);
        const buttons=rows.filter(node=>node.tagName==='BUTTON');
        const filtered=buttons.length>0&&buttons.every(node=>node.classList.contains('design-filtered'));
        const nativeLoading=status.some(node=>node.dataset.state==='LOADING');
        item.empty.classList.toggle('v2-list-loading',loading);
        setText(item.empty,loading?'正在读取此分类…':filtered?'当前分类没有匹配记录，请调整或清除筛选。':item.hint);
        item.empty.hidden = nativeLoading || (!loading && !filtered && !!hasResponse) || !!failed;
      }
    }
    const refinePreparationRows=()=>{
      for(const button of $('prep-items')?.querySelectorAll(':scope > button')||[]){
        if(button.querySelector('.v2-record-title')||!button.hasAttribute('data-preparation-goal'))continue;
        const text=[...button.childNodes].find(node=>node.nodeType===Node.TEXT_NODE&&node.textContent.trim());if(!text)continue;
        const state=typeof prepLabels!=='undefined'?(prepLabels[button.dataset.preparationState]||'状态待核对'):'状态待核对';
        const title=make('span',button.dataset.preparationGoal,'v2-record-title'),status=make('span',state,'collaboration-record-status v2-record-state'),open=make('span','查看 ›','v3-row-open');open.setAttribute('aria-hidden','true');text.replaceWith(title,status,open);
      }
    };
    new MutationObserver(refinePreparationRows).observe($('prep-items'),{childList:true,subtree:true});
    refinePreparationRows();
    document.addEventListener('click', event => {
      const link = event.target.closest?.('a[href^="#"]');
      if (!link) return;
      const target = $(link.hash.slice(1));
      const item = target && definitions.find(item => item.panel.contains(target));
      if (item) select(item.key);
    }, true);
    new MutationObserver(refreshHints).observe(root,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['class']});
    new MutationObserver(refreshHints).observe($('page-feedback'),{childList:true,characterData:true,subtree:true});
    $('token')?.addEventListener('input',()=>{reading.clear();lastReadCategory=null;queueMicrotask(refreshHints);});
    select(active);
    return {definitions, select};
  }

  function preparationViews(detail) {
    const navigation = detail.querySelector(':scope > .design-detail-nav');
    if (!navigation) return;
    const summary = $('prep-summary'), read = $('prep-read-status'), refresh = $('prep-refresh');
    const identifiers=make('details','','v2-case-identifiers');
    const identifierTitle=make('summary','事项编号与版本');
    identifiers.append(identifierTitle);identifiers.hidden=true;
    const genericTitle = detail.querySelector(':scope > h2');
    if (genericTitle) genericTitle.hidden = true;
    detail.prepend(summary, navigation);
    summary.after(identifiers);
    const readState = make('div', '', 'v2-read-state');
    const recoveryActions=make('div','','v3-recovery-actions'),recoveryReason=make('p','','v3-recovery-reason');recoveryReason.id='workspace-refresh-reason';recoveryReason.hidden=true;
    recoveryActions.append(refresh);for(const id of ['prep-command-retry','prep-recovery-read','prep-recovery-release']){const button=$(id);if(button&&!button.form)recoveryActions.append(button);}
    refresh.setAttribute('aria-describedby',[refresh.getAttribute('aria-describedby'),recoveryReason.id].filter(Boolean).join(' '));setText(refresh,'刷新当前资料');
    navigation.after(readState); readState.append(read,recoveryActions,recoveryReason);
    for(const id of ['prep-command-feedback','prep-recovery-status']){const node=$(id);if(node)readState.append(node);}
    const materials = $('prep-materials'), filter = materials.previousElementSibling;
    readState.after(...[filter?.classList.contains('design-filter')?filter:null,materials].filter(Boolean));
    if(filter?.classList.contains('design-filter')){
      const labels=[...filter.children].filter(node=>node.tagName==='LABEL'&&node.querySelector('select'));
      if(labels.length){
        const options=make('details','','workspace-filter-options'),fields=make('div');
        options.append(make('summary','材料分类筛选'),fields);
        for(const label of labels)fields.append(label);
        const note=filter.querySelector(':scope > p:not(.design-filter-count)');if(note)fields.append(note);
        filter.querySelector('.design-filter-count')?.before(options);
      }
    }
    const refineMaterialText=()=>{
      for(const note of materials.querySelectorAll('article>small')){
        const kind=note.textContent.split(' · ')[0],names={USER_STATEMENT:'企业自述',DOCUMENT_EXCERPT:'文档摘录'};
        if(names[kind])note.textContent=names[kind]+note.textContent.slice(kind.length);
      }
      const records=typeof preparationView!=='undefined'?preparationView?.current_materials:null;
      const rows=[...materials.querySelectorAll(':scope > article')];
      if(records?.length===rows.length)rows.forEach((row,index)=>{const item=records[index],heading=row.querySelector(':scope > strong');if(!heading||row.querySelector(':scope > p')?.textContent!==item.text)return;
        const names={need_summary:'诉求摘要',material_outline:'材料目录'},name=names[item.slot];if(name&&Number.isInteger(item.version)&&!heading.querySelector('.v3-material-version'))heading.replaceChildren(make('span',name),document.createTextNode(' '),make('span','材料版本 '+item.version,'v3-material-version'));
      });
      for(const button of materials.querySelectorAll('.design-preview-trigger'))setText(button,'查看全文与来源');
      for(const summary of materials.querySelectorAll('.design-material-menu>summary'))setText(summary,'材料操作');
    };
    new MutationObserver(refineMaterialText).observe(materials,{childList:true,subtree:true});
    // The original menu handler focuses this exact metadata node. Reveal it
    // before that handler runs; keep its current-version and clipboard guards.
    materials.addEventListener('click',event=>{
      const action=event.target.closest('button');
      if(action?.closest('.design-material-menu')&&action.textContent==='查看来源与版本'){
        action.closest('article')?.querySelector('.design-file-meta')?.classList.add('v3-meta-visible');
      }
    },true);
    const more = make('details', '', 'v2-secondary-tools');
    more.append(make('summary','关联资源与办理工具'));
    const toolIds = ['ordinary-runtime-entry','handling-deadline-panel','simulation-rule-panel','case-time-panel','case-fact-panel','fact-bundle-panel','material-reuse-panel','opportunity-panel'];
    for (const id of toolIds) { const node=$(id); if (node?.parentElement===detail) more.append(node); }
    detail.append(more);
    const materialIds = new Set(['prep-materials','material-draft-panel','material-file-panel','material-version-panel','prep-evidence','material-review-panel','material-corrections-panel','prep-decision']);
    const historyIds = new Set(['prep-history']);
    const commonIds = new Set(['prep-summary','prep-error','prep-command-feedback','prep-command-retry','prep-recovery-status','prep-recovery-read','prep-recovery-release']);
    let active='materials';
    const group = node => {
      if (node===navigation || node===readState || node===identifiers || commonIds.has(node.id) || node===genericTitle || node.classList.contains('eyebrow') || node.getAttribute('role')==='alert') return 'common';
      if (materialIds.has(node.id) || node.classList.contains('design-filter') || node.tagName==='P'&&node.textContent.startsWith('核对仅表示')) return 'materials';
      if (historyIds.has(node.id) || node.tagName==='H3'&&node.textContent==='材料版本与人工记录') return 'history';
      return 'overview';
    };
    const links=[...navigation.querySelectorAll('a')];
    function show(view) {
      active=view;
      for (const node of detail.children) {
        const recovery=detail.classList.contains('case-cancel-recovery-only')&&node.id==='case-cancel-panel';
        node.classList.toggle('workspace-tab-hidden',!recovery&&group(node)!=='common'&&group(node)!==view);
      }
      for (const link of links) {
        const key=link.hash==='#prep-materials'?'materials':link.hash==='#prep-history'?'history':'overview';
        link.setAttribute('aria-current',key===view?'page':'false');
      }
    }
    navigation.addEventListener('click',event=>{
      const link=event.target.closest('a'); if (!link) return;
      show(link.hash==='#prep-materials'?'materials':link.hash==='#prep-history'?'history':'overview');
    },true);
    document.addEventListener('click',event=>{
      const link=event.target.closest?.('a[href^="#"]');
      if (!link || navigation.contains(link)) return;
      const target=$(link.hash.slice(1)); if (!target || !detail.contains(target)) return;
      let section=target; while(section.parentElement!==detail) section=section.parentElement;
      if (group(section)!=='common') show(group(section));
      if (more.contains(target)) more.open=true;
    },true);
    let recordId=null;
    function projectSummary() {
      const p=typeof preparationView!=='undefined'?preparationView?.preparation:null;
      if (!p || !p.goal || detail.hidden || !summary.textContent.trim()) {
        identifiers.hidden=true;identifiers.replaceChildren(identifierTitle);return;
      }
      if (recordId!==p.id) { recordId=p.id; show('materials'); }
      const state=typeof prepLabels!=='undefined'?(prepLabels[p.state]||'状态待核对'):'状态待核对';
      const meta='资料事项版本 '+p.revision+' · '+state+' · 合成资料';
      identifiers.hidden=false;
      if(identifiers.querySelector('dl')?.textContent!==['资料事项编号',p.id,'所属事项 Case',p.case_id,'技术运行 Run',p.run_id,'资料事项版本',p.revision].join('')){
        identifiers.replaceChildren(identifierTitle,parkFieldList([['资料事项编号',p.id],['所属事项 Case',p.case_id],['技术运行 Run',p.run_id],['资料事项版本',p.revision]]));
      }
      if (summary.querySelector('.workspace-case-goal')?.textContent===p.goal && summary.querySelector('.workspace-case-meta')?.textContent===meta) return;
      const goal=make('span',p.goal,'workspace-case-goal'); goal.setAttribute('role','heading'); goal.setAttribute('aria-level','2');
      summary.replaceChildren(goal,make('span',meta,'workspace-case-meta'));
    }
    new MutationObserver(projectSummary).observe(summary,{childList:true});
    new MutationObserver(projectSummary).observe(detail,{attributes:true,attributeFilter:['hidden']});
    const refreshRecovery=()=>{
      const raw=read.textContent;
      const command=typeof prepCommandPending!=='undefined'?prepCommandPending:null;
      const fact=typeof caseFactPending!=='undefined'?caseFactPending:null;
      const reuse=typeof materialReusePending!=='undefined'?materialReusePending:null;
      const writing=typeof activeEntryWriteFlow!=='undefined'&&!!activeEntryWriteFlow;
      const allowed=typeof entryReadAllowed==='function'?entryReadAllowed('prep-refresh'):true;
      const blocked=refresh.matches(':disabled')||!allowed;
      readState.dataset.refresh=blocked?'blocked':'available';refresh.setAttribute('aria-disabled',String(blocked));readState.dataset.state=read.dataset.state||'UNREAD';
      let reason='';
      if(command?.state==='UNKNOWN')reason=$('prep-command-feedback').textContent;
      else if(command?.state==='SUBMITTING')reason='材料操作正在提交，原处理器暂不允许刷新。请等待原结果。';
      else if(fact?.stage==='SUBMITTING')reason='事实操作正在提交，原处理器暂不允许刷新。请等待原结果。';
      else if(reuse?.stage==='SUBMITTING')reason='材料复用正在提交，原处理器暂不允许刷新。请等待原结果。';
      else if(writing)reason='原写请求正在执行，刷新受原请求守卫限制。请等待该操作的结果。';
      else if(!allowed)reason='原请求尚待核对，当前守卫不允许独立刷新。请继续使用原操作的恢复入口。';
      else if(refresh.matches(':disabled'))reason='刷新被原处理器限制，当前没有可直接采用的原因说明；请保留原状态与请求。';
      setText(recoveryReason,reason);if(recoveryReason.hidden!==!reason)recoveryReason.hidden=!reason;const duplicate=$('prep-command-feedback');if(duplicate)duplicate.classList.toggle('v3-duplicate-recovery',!!reason&&duplicate.textContent===reason);
      const prefix=raw.startsWith('当前读取已失效：')?'当前读取已失效：':raw.includes('；')?raw.slice(0,raw.indexOf('；')+1):'';
      if(prefix&&!read.querySelector('.v3-read-title')){const title=make('strong',prefix,'v3-read-title'),body=make('span','','v3-read-body');const rest=raw.slice(prefix.length),suggestion='请刷新当前资料；',at=rest.indexOf(suggestion);if(at>=0)body.append(document.createTextNode(rest.slice(0,at)),make('span',suggestion,'v3-refresh-suggestion'),document.createTextNode(rest.slice(at+suggestion.length)));else body.textContent=rest;read.replaceChildren(title,body);}
    };
    for(const node of [read,$('prep-command-feedback'),$('prep-recovery-status')])if(node)new MutationObserver(refreshRecovery).observe(node,{childList:true,subtree:true,characterData:true});
    new MutationObserver(refreshRecovery).observe(refresh,{attributes:true,attributeFilter:['disabled']});
    new MutationObserver(refreshRecovery).observe(detail,{attributes:true,attributeFilter:['hidden']});
    const deduplicateReadError=()=>{
      const visible=!detail.hidden&&read.dataset.state==='INVALID';
      for(const node of [$('page-feedback'),$('prep-error')]){
        const message=node?.textContent.trim();
        node?.classList.toggle('v2-duplicate-notice',!!(visible&&message&&read.textContent.includes(message)));
      }
      read.setAttribute('role',read.dataset.state==='INVALID'?'alert':'status');
    };
    for(const node of [read,$('page-feedback'),$('prep-error')])if(node)new MutationObserver(deduplicateReadError).observe(node,{childList:true,subtree:true,characterData:true});
    new MutationObserver(deduplicateReadError).observe(detail,{attributes:true,attributeFilter:['hidden']});
    new MutationObserver(()=>show(active)).observe(detail,{attributes:true,attributeFilter:['class']});
    $('token')?.addEventListener('input',()=>{recordId=null;show('materials');});
    show(active); projectSummary();refineMaterialText();deduplicateReadError();refreshRecovery();
  }

  function detailWorkspace() {
    const main=$('park-main'),body=document.body;
    const ids=['prep-detail','dispatch-detail','receipt-detail','plan-detail','service-case-plan-detail','local-case-detail'];
    const panels=ids.map($).filter(Boolean);
    const stack=make('div','','v2-detail-stack');stack.hidden=true;
    const master=make('aside','','v2-master');master.hidden=true;master.setAttribute('aria-label','事项列表');
    const heading=make('div','','v2-master-heading'),back=make('button','返回协同列表'),title=make('h2','资料事项'),list=make('div','','v2-master-list');
    back.type='button';heading.append(back,title);master.append(heading,list);
    const utilities=main.querySelector('.atelier-utilities');
    if (utilities) utilities.before(master,stack); else main.append(master,stack);
    for (const panel of panels) { panel.classList.add('workspace-detail'); stack.append(panel); }
    preparationViews($('prep-detail'));
    let listSignature='',backSpace='collaboration';
    back.onclick=()=>{
      const original=document.querySelector('[data-tab="'+backSpace+'"]');
      if (original) { original.focus(); original.click(); }
    };
    function synchronize() {
      const locked=body.dataset.localWorkspace==='locked'||body.dataset.localRole==='resource_admin';
      const visible=locked?[]:panels.filter(panel=>!panel.hidden);
      const open=visible.length>0;
      const opening=open&&body.dataset.v2Detail!=='true';
      if (opening) backSpace=body.dataset.workspace||'service';
      body.dataset.v2Detail=String(open);
      master.hidden=stack.hidden=!open;
      if (!open) {list.replaceChildren();listSignature='';return;}
      if(opening){
        stack.scrollTop=0;
        queueMicrotask(()=>{
          if(stack.hidden)return;
          const target=visible[0].querySelector('.workspace-case-goal,h2:not([hidden])')||visible[0];
          target.tabIndex=-1;target.focus({preventScroll:true});
        });
      }
      const current=visible[0];
      const kind=current.id==='dispatch-detail'?'dispatch':current.id==='receipt-detail'?'receipt':'preparation';
      const sourceId=kind==='dispatch'?'dispatch-items':kind==='receipt'?'receipt-items':'prep-items';
      const source=$(sourceId);
      const buttons=[...(source?.children||[])].filter(node=>node.tagName==='BUTTON'&&!node.hidden&&!node.classList.contains('design-filtered'));
      setText(title,kind==='dispatch'?'派单记录':kind==='receipt'?'执行回执':'资料事项');
      setText(back,backSpace==='service'?'返回服务列表':backSpace==='resource'?'返回资源工作区':'返回协同列表');
      const contextId=kind==='dispatch'?(typeof dispatchId!=='undefined'?dispatchId:null):kind==='receipt'?(typeof receiptId!=='undefined'?receiptId:null):(typeof preparationId!=='undefined'?preparationId:null);
      const signature=JSON.stringify([kind,contextId,buttons.map(button=>[button.textContent,button.disabled]),$('prep-summary')?.textContent]);
      if (signature===listSignature) return;
      listSignature=signature;list.replaceChildren();
      if (!buttons.length) {
        const label=current.id==='prep-detail'?$('prep-summary')?.querySelector('.workspace-case-goal')?.textContent:null;
        if (label) list.append(make('div',label,'v2-master-current'));
        list.append(make('p','尚未加载此分类的事项列表。返回列表后可按当前身份读取。','v2-master-empty'));
      }
      for (const original of buttons) {
        const direct=[...original.childNodes].filter(node=>node.nodeType===Node.TEXT_NODE).map(node=>node.textContent).join('').trim();
        const proxy=make('button',original.querySelector('.v2-record-title')?.textContent||direct||original.querySelector('strong')?.textContent||'查看事项');proxy.type='button';proxy.disabled=original.disabled;
        const selected=contextId&&(original.dataset.listRecordId===contextId||original.dataset.preparationId===contextId);
        if (selected) proxy.setAttribute('aria-current','true');
        const status=original.querySelector('.collaboration-record-status');if(status)proxy.append(make('small',status.textContent));
        proxy.onclick=()=>{if(original.isConnected&&!original.disabled)original.click();};list.append(proxy);
      }
    }
    for (const panel of panels) new MutationObserver(synchronize).observe(panel,{attributes:true,attributeFilter:['hidden'],childList:true,subtree:true,characterData:true});
    for (const id of ['prep-items','dispatch-items','receipt-items']) {
      const node=$(id);if(node)new MutationObserver(synchronize).observe(node,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['disabled','class']});
    }
    new MutationObserver(synchronize).observe(body,{attributes:true,attributeFilter:['data-local-workspace','data-local-role']});
    $('token')?.addEventListener('input',()=>queueMicrotask(synchronize));
    synchronize();
  }

  function compactShell() {
    const panel=document.querySelector('.app-sidebar .session-panel'),token=$('token');
    if(!panel||!token||!panel.contains(token))return;
    const disclosure=make('details','','v4-session-disclosure'),title=make('summary','合成会话');
    const label=token.closest('label');
    disclosure.append(title);panel.prepend(disclosure);
    if(label)disclosure.append(label);
    // Only fold the credential input and static explanation. Status and recovery
    // nodes stay in their original panel, outside the disclosure.
    for(const note of [...panel.children])if(note.tagName==='SMALL')disclosure.append(note);
    const jump=make('button','跳到当前事项','v4-current-item');jump.type='button';
    jump.onclick=()=>{const target=document.querySelector('.v2-detail-stack:not([hidden]) .workspace-detail:not([hidden]) .workspace-case-goal,.v2-detail-stack:not([hidden]) .workspace-detail:not([hidden]) h2:not([hidden])');if(target){target.tabIndex=-1;target.focus();target.scrollIntoView({block:'start'});}};
    panel.append(jump);
    const compact=matchMedia('(max-width:768px), (max-height:700px)');
    const sync=()=>{if(!compact.matches)disclosure.open=true;else if(!disclosure.contains(document.activeElement))disclosure.open=false;};
    compact.addEventListener('change',sync);sync();
  }
  function appearance() {
    let effect='glass';try{effect=localStorage.getItem('parkweave.appearance.effects')==='low'?'low':'glass';}catch{}
    document.body.dataset.effects=effect;document.body.dataset.backdrop=globalThis.CSS?.supports?.('backdrop-filter','blur(1px)')?'supported':'unsupported';
    const panel=document.querySelector('.appearance-panel');if(!panel)return;
    const label=make('label','显示效果'),select=make('select');select.setAttribute('aria-label','显示效果');
    for(const [value,text] of [['glass','标准磨砂'],['low','低效果（实色）']]){const option=make('option',text);option.value=value;select.append(option);}select.value=effect;label.append(select);panel.append(label);
    select.onchange=()=>{document.body.dataset.effects=select.value;try{localStorage.setItem('parkweave.appearance.effects',select.value);}catch{}};
  }
  function install() {
    if (!$('service') || document.body.dataset.workspaceDesign==='2') return;
    document.body.dataset.workspaceDesign='2';
    setText(document.querySelector('#park-theme option[value="ink"]'),'浅蓝');
    appearance();serviceWorkspace();resourceWorkspace();
    collaborationWorkspace();
    detailWorkspace();
    compactShell();
  }
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
})();
