// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync(process.argv[3]||'src/parkweave/web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
let nextRequestKey=99;const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];const classes=new Set();this.classList={add:(...names)=>names.forEach(n=>classes.add(n)),remove:(...names)=>names.forEach(n=>classes.delete(n)),contains:n=>classes.has(n)};const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.options=[];this.listeners={};}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 reset(){}addEventListener(n,f){this.listeners[n]=f;}setAttribute(n,v){(this.attributes??={})[n]=String(v);}removeAttribute(n){if(this.attributes)delete this.attributes[n];}
 closest(){return null;}querySelectorAll(){return [];}scrollIntoView(){this.scrolled=true;}
 get firstElementChild(){return this.children[0];}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
const elements=new Map(),$=name=>{if(!elements.has(name)){const e=new Element();e.id=name;elements.set(name,e);}return elements.get(name);};
const store={},calls=[],events=[];
const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},
 {ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
const context=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,
 crypto:{randomUUID:()=>id(nextRequestKey++)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},
 document:{getElementById:$,createElement:t=>new Element(t),querySelectorAll:()=>[],body:new Element('body'),addEventListener:(...a)=>events.push(a),execCommand:()=>false},
 window:{addEventListener:(...a)=>events.push(a)},
 fetch:(path,options)=>new Promise((resolve,reject)=>calls.push({path,options,resolve,reject}))});
vm.runInContext(code,context);$('token').value='SYNTHETIC_SESSION_A';
const run=s=>vm.runInContext(s,context),tick=()=>new Promise(r=>setImmediate(r));
function finish(call,status,value){call.resolve({status,ok:status>=200&&status<300,json:async()=>value});}
function projection(target,prep=id(3),receipt=id(4)){
 return {scope:'CURRENT_OWNER_SYNTHETIC_CASE_WORKLIST',read_only:true,automatically_replayed:false,recorded_states_only:true,next_after:null,
 items:[{case_id:id(1),run_id:id(2),preparation_id:prep,receipt_step_id:target==='receipt'?receipt:null,title:'SYNTHETIC item',label:'recorded',attention:'WAITING_RECEIPT',waiting_on:'OWNER',open_target:target,evidence_verified:false,case_goal_completed:false,resource_release_required_separately:false}]};
}
async function queue(target,prep,receipt){const p=$('case-worklist-read').onclick();finish(calls.at(-1),200,projection(target,prep,receipt));await p;return $('case-worklist-items').children[0].children.find(e=>e.tagName==='button');}
function material(){return {preparation:{id:id(3),case_id:id(1),run_id:id(2),owner_id:'fixture-a',state:'IN_PREPARATION',revision:1,goal:'PRIVATE_MATERIAL_A'},current_materials:[{id:id(6),slot:'need_summary',version:1,text:'PRIVATE_BODY_A',source_kind:'USER_STATEMENT',source_label:'SYNTHETIC'}],material_history:[],history:[]};}
function receipt(){return {step:{id:id(4),preparation_id:id(5),case_id:id(7),run_id:id(8),state:'AWAITING_RECEIPT',revision:1,preparation_revision:1,goal:'CURRENT_RECEIPT_B'},actor_ref:'b'.repeat(64),role:'enterprise_operator',can_submit:false,dependency:'CURRENT',is_current_step:true,current_receipt:null,receipt_history:[],history:[],local_execution:{}};}
async function flushOtherGets(){for(let i=0;i<12;i++){for(const c of calls){if(!c.finished){c.finished=true;finish(c,500,{});}}await tick();}}
// Owned ASGI bridge: execute original page entries; Python supplies actual API
// responses from its existing PG fixture, never replacement entry functions.
if(mode==='intake_cold_asgi'){
 const lines=require('readline').createInterface({input:process.stdin});const replies=[];
 lines.on('line',line=>{const pending=replies.shift();if(pending)pending(JSON.parse(line));});
 context.fetch=async(path,options={})=>{calls.push({path,options});const response=new Promise(resolve=>replies.push(resolve));console.log(JSON.stringify({request:{path,options}}));const x=await response;return {status:x.status,ok:x.status>=200&&x.status<300,json:async()=>x.body};};
}
(async()=>{
 if(mode==='resource_catalog_feedback_invalidated'){
  const opening=$('resource-catalog').onclick(),catalog=calls.at(-1),mine=$('resource-mine').onclick(),holds=calls.at(-1);
  check(holds.path==='/api/resource-holds');finish(holds,200,{items:[]});await mine;
  finish(catalog,200,{server_time:'2026-10-26T12:00:00Z',items:[]});await opening;
  check(calls.length===2);check($('resource-catalog-status').dataset.state==='UNREAD');check($('resource-catalog-view').attributes['aria-busy']==='false');
  const old=$('resource-catalog').onclick(),oldCall=calls.at(-1),latest=$('resource-catalog').onclick(),latestCall=calls.at(-1);
  finish(oldCall,403,{});await old;check($('resource-catalog-status').dataset.state==='LOADING');check($('resource-catalog-view').attributes['aria-busy']==='true');
  finish(latestCall,403,{});await latest;check($('resource-catalog-status').dataset.state==='DENIED');check($('resource-catalog-view').attributes['aria-busy']==='false');
 }else if(mode==='resource_catalog_feedback'){
  const status=$('resource-catalog-status'),view=$('resource-catalog-view');
  const start=()=>{const promise=$('resource-catalog').onclick();check(status.dataset.state==='LOADING');check(view.attributes['aria-busy']==='true');check(status.textContent.includes('尚未预检'));return {promise,call:calls.at(-1)};};
  let a=start();a.call.reject(Error('SYNTHETIC_NETWORK_FAILURE'));await a.promise;
  check(status.dataset.state==='ERROR');check(view.attributes['aria-busy']==='false');check(status.textContent.includes('手动'));check($('resource-form').hidden);
  a=start();finish(a.call,200,{server_time:'2026-10-26T12:00:00Z',items:[]});await tick();
  for(const call of calls.slice(-2))finish(call,200,call.path==='/api/resource-bundles'?{actor_id:'SYNTHETIC_ACTOR_A',items:[]}:{enabled:false,approval_scope:null});await a.promise;
  check(status.dataset.state==='EMPTY');check(view.attributes['aria-busy']==='false');check(status.textContent.includes('不是资源已用完'));
  a=start();finish(a.call,403,{});await a.promise;check(status.dataset.state==='DENIED');check(view.attributes['aria-busy']==='false');check(view.children.length===0);
  $('token').value='SYNTHETIC_SESSION_B';$('token').oninput();check(status.dataset.state==='UNREAD');check(view.attributes['aria-busy']==='false');
 }else if(mode.startsWith('resource_catalog_chain_')){
  const scenario=mode.slice('resource_catalog_chain_'.length),opening=$('resource-catalog').onclick(),catalog=calls.at(-1);
  check(catalog.path==='/api/synthetic-resources');check(catalog.options.headers.Authorization==='Bearer SYNTHETIC_SESSION_A');
  if(scenario==='denied'){
   finish(catalog,403,{});await tick();check(calls.length===1);await opening;
   check($('resource-form').hidden);check(run('bundleActor===null'));check($('resource-error').textContent.includes('权限'));
  }else if(scenario==='identity_switch'){
   $('token').value='SYNTHETIC_SESSION_B';$('token').oninput();
   finish(catalog,200,{server_time:'2026-10-26T12:00:00Z',items:[]});await tick();check(calls.length===1);await opening;
   check($('resource-catalog-view').children.length===0);check(run('bundleActor===null'));
  }else if(scenario==='handoff_identity_switch'){
   catalog.resolve({status:200,ok:true,json:async()=>{
    let change=()=>{$('token').value='SYNTHETIC_SESSION_B';$('token').oninput();};
    for(let n=0;n<5;n++){const next=change;change=()=>Promise.resolve().then(next);}change();
    return {server_time:'2026-10-26T12:00:00Z',items:[]};
   }});
   await tick();check(calls.length===1);await opening;
   check($('resource-catalog-view').children.length===0);check(run('bundleActor===null'));
  }else if(scenario==='superseded'){
   const latest=$('resource-catalog').onclick(),fresh=calls.at(-1);
   finish(catalog,403,{});await tick();check(calls.length===2);await opening;
   finish(fresh,200,{server_time:'2026-10-26T12:00:00Z',items:[]});await tick();
   check(calls.length===4);for(const call of calls.slice(2))finish(call,200,call.path==='/api/resource-bundles'?{actor_id:'SYNTHETIC_ACTOR_A',items:[]}:{enabled:false,approval_scope:null});await latest;
   check(run('bundleActor')==='SYNTHETIC_ACTOR_A');check($('resource-error').textContent==='');
  }else{
   check(['empty','populated'].includes(scenario));
   const items=scenario==='empty'?[]:[{id:id(61),name:'合成资源',capacity:3,revision:1,buffer_seconds:0,enabled:true,source:{kind:'SYNTHETIC',id:'fixture',revision:1,statement:'非真实资源'},open_from:'2026-10-26T00:00:00Z',open_until:'2026-10-27T00:00:00Z'}];
   finish(catalog,200,{server_time:'2026-10-26T12:00:00Z',items});await tick();check(calls.length===3);
   for(const call of calls.slice(1)){check(call.options.headers.Authorization==='Bearer SYNTHETIC_SESSION_A');check(['/api/resource-bundles','/api/plan-approval/status'].includes(call.path));finish(call,200,call.path==='/api/resource-bundles'?{actor_id:'SYNTHETIC_ACTOR_A',items:[]}:{enabled:false,approval_scope:null});}
   await opening;check(run('bundleActor')==='SYNTHETIC_ACTOR_A');check(run('planApprovalEnabled')===false);check($('resource-form').hidden===(scenario==='empty'));
   if(scenario==='populated'){
    const card=$('resource-catalog-view').children.find(e=>e.className==='resource-catalog-card');check(!!card);
    const text=e=>e.textContent+' '+e.children.map(text).join(' '),value=text(card);
    for(const field of ['合成资源','目录启用','容量 3','合成版本 1','0秒缓冲','SYNTHETIC / fixture / v1','非真实资源','2026-10-26T00:00:00Z','2026-10-27T00:00:00Z','UTC'])check(value.includes(field));
   }
  }
 }else if(mode==='same_batch_receipt_navigation'){
  const rows=[{id:id(21),goal:'SYNTHETIC SAME GOAL',state:'AWAITING_RECEIPT',revision:1},{id:id(22),goal:'SYNTHETIC SAME GOAL',state:'AWAITING_RECEIPT',revision:1}];
  const listing=$('receipt-list').onclick();finish(calls.at(-1),200,{role:'enterprise_operator',items:rows});await listing;
  const buttons=$('receipt-items').children.filter(e=>e.tagName==='button');check(buttons.length===2);
  for(let n=0;n<2;n++){
   const count=calls.length,reading=buttons[n].onclick();check(calls.length===count+1);check(calls.at(-1).path==='/api/executor-receipts/'+rows[n].id);
   const x=receipt();x.step.id=rows[n].id;finish(calls.at(-1),200,x);await reading;check(run('receiptView.step.id')===rows[n].id);check($('receipt-items').children.filter(e=>e.tagName==='button').length===2);
  }
  check(calls.every(c=>(c.options.method||'GET')==='GET'));
 }else if(mode.startsWith('list_feedback_')){
  const kind=mode.slice('list_feedback_'.length),prefix=kind==='dispatch'?'dispatch':'receipt',items=prefix+'-items',status=prefix+'-list-status',button=prefix+'-list';
  const visible=e=>e.textContent+' '+e.children.map(visible).join(' ');
  const rows=[{id:id(21),preparation_id:id(41),goal:'SYNTHETIC SAME GOAL <img src=x onerror=alert(1)>',state:'LOCAL_ACKNOWLEDGED',revision:2,case_cancelled:true,case_reconciling:true,case_write_blocked:true},{id:id(22),preparation_id:id(42),goal:'SYNTHETIC SAME GOAL',state:'constructor',revision:1}];
  if(kind==='dispatch')for(const r of rows)for(const k of ['state','revision','case_cancelled','case_reconciling','case_write_blocked'])delete r[k];
  const response=(values=rows,extra={})=>({role:'enterprise_operator',items:values,...extra});
  const start=()=>{const promise=$(button).onclick(),call=calls.at(-1);return {promise,call};};
  let a=start();check($(button).disabled);check($(status).dataset.state==='LOADING');check(visible($(items)).trim()==='');finish(a.call,200,response());await a.promise;
  check(!$(button).disabled);check($(status).dataset.state==='READY');let cards=$(items).children.filter(e=>e.tagName==='button');check(cards.length===2);
  for(let n=0;n<2;n++){check(visible(cards[n]).includes(rows[n].id));check(!visible(cards[n]).includes(rows[1-n].id));check(visible(cards[n]).includes('只读打开'));}
  if(kind==='receipt'){check(visible(cards[0]).includes('已本地核对'));check(visible(cards[0]).includes('已取消'));check(visible(cards[0]).includes('核对中'));check(visible(cards[0]).includes('新办理暂停'));check(visible(cards[1]).includes('状态待核对'));check(!visible(cards[1]).includes('undefined'));}
  else{check(visible(cards[0]).includes('进入原记录后核对'));check(visible(cards[0]).includes('含历史'));}
  // A newer valid empty result wins over an older successful response.
  a=start();let b=start();finish(b.call,200,response([],{has_older_records:true,access_filtered:1}));await b.promise;const empty=$(status).textContent;check($(status).dataset.state==='EMPTY');check(empty.includes('范围'));check(visible($(items)).includes('更早'));check(visible($(items)).includes('读取条件'));
  finish(a.call,200,response());await a.promise;check($(status).textContent===empty);check($(items).children.filter(e=>e.tagName==='button').length===0);
  // A late denial cannot clear the newer successful page.
  a=start();b=start();finish(b.call,200,response(rows.slice(0,1)));await b.promise;const ready=$(status).textContent;finish(a.call,403,{});await a.promise;check($(status).textContent===ready);check($(items).children.filter(e=>e.tagName==='button').length===1);
  // Identity switch plus new pending read: an old denial must not enable it.
  a=start();$('token').value='SYNTHETIC_SESSION_B';b=start();finish(a.call,403,{});await a.promise;check($(button).disabled);check($(status).dataset.state==='LOADING');finish(b.call,200,response());await b.promise;check($(status).dataset.state==='READY');
  a=start();finish(a.call,403,{});await a.promise;check($(status).dataset.state==='DENIED');check(!$(button).disabled);check($(items).children.length===0);check(run('dispatchView===null&&receiptView===null'));
  a=start();a.call.resolve({status:403,ok:false,json:async()=>{throw Error('SYNTHETIC_DENIED_INVALID_JSON')}});await a.promise;check($(status).dataset.state==='DENIED');check($(items).children.length===0);check(!$(button).disabled);
  a=start();finish(a.call,200,{role:'enterprise_operator',items:null});await a.promise;check($(status).dataset.state==='ERROR');check(!$(status).textContent.includes('暂无'));check($(items).children.length===0);check(!$(button).disabled);
  a=start();finish(a.call,500,{});await a.promise;check($(status).dataset.state==='ERROR');check($(items).children.length===0);check(!$(button).disabled);
  check(calls.every(c=>(c.options.method||'GET')==='GET'));
 }else if(mode.startsWith('duplicate_record_')){
  const kind=mode.slice('duplicate_record_'.length),names={preparation:['prep-list','prep-items','/api/preparations'],dispatch:['dispatch-list','dispatch-items','/api/service-dispatches'],receipt:['receipt-list','receipt-items','/api/executor-receipts']},[list,items,path]=names[kind];
  const rows=[{id:id(21),case_id:id(31),preparation_id:id(41),goal:'SYNTHETIC SAME GOAL <img src=x onerror=alert(1)>',state:'RECEIPT_RECORDED',revision:2},{id:id(22),case_id:id(32),preparation_id:id(42),goal:'SYNTHETIC SAME GOAL <img src=x onerror=alert(1)>',state:'RECEIPT_RECORDED',revision:2}];
  for(const row of rows){if(kind==='preparation'){row.state='IN_PREPARATION';delete row.preparation_id;}else if(kind==='dispatch'){delete row.state;delete row.case_id;delete row.revision;}else{delete row.preparation_id;delete row.case_id;}}
  const visible=e=>e.textContent+' '+e.children.map(visible).join(' ');
  for(let chosen=0;chosen<2;chosen++){
   const listing=$(list).onclick();check(calls.at(-1).path===path);finish(calls.at(-1),200,{role:'enterprise_operator',items:rows});await listing;
   const buttons=$(items).children.filter(e=>e.tagName==='button');check(buttons.length===2);
   for(let i=0;i<2;i++){
    const text=visible(buttons[i]);check(text.includes(rows[i].goal));check(text.includes(rows[i].id));check(!text.includes(rows[1-i].id));
    if(kind==='preparation')check(text.includes(rows[i].case_id));
    if(kind==='dispatch')check(text.includes(rows[i].preparation_id));
   }
   const reading=buttons[chosen].onclick();await tick();const call=calls.at(-1);
   const expected=kind==='dispatch'?'/api/preparations/'+rows[chosen].preparation_id+'/dispatch':'/api/'+(kind==='preparation'?'preparations':'executor-receipts')+'/'+rows[chosen].id;
   check(call.path===expected);call.reject(Error('SYNTHETIC_READ_FAILURE_KEEP_ORIGINAL_ERROR_HANDLING'));await reading;
  }
 }else if(mode==='intake_cold_asgi'){
  $('goal').value='SYNTHETIC cold initial intake';await $('intake').onsubmit({preventDefault(){}});check(run('entryWriteRequests.size')===1);const firstRun=$('run').value;check(!!firstRun);
  await $('refresh').onclick();check(run('entryWriteRequests.size')===0);
  await $('case-worklist-read').onclick();const button=$('case-worklist-items').children[0].children.find(e=>e.tagName==='button');check(!!button);await button.onclick();check($('run').value===firstRun);
  await $('prep-catalog').onclick();$('prep-reviewer').value=run('prepCatalog.reviewers[0].id');$('prep-goal').value='SYNTHETIC cold preparation creation';
  await $('prep-create').onsubmit({preventDefault(){}});check(run('preparationView!==null'));check(run('entryWriteRequests.size')===0);
  $('prep-slot').value='need_summary';$('prep-text').value='SYNTHETIC cold source';$('prep-source-kind').value='DOCUMENT_EXCERPT';$('prep-source-label').value='SYNTHETIC cold document';
  await $('prep-evidence').onsubmit({preventDefault(){}});check(run('prepCommandPending===null'));check(run('preparationView.current_materials.length')===1);check(run('entryWriteRequests.size')===0);
  const prepId=run('preparationId');await $('case-worklist-read').onclick();const card=$('case-worklist-items').children.find(e=>e.children.some(c=>c.textContent.includes('SYNTHETIC cold preparation creation')));const materialButton=card?.children.find(e=>e.tagName==='button');check(!!materialButton);await materialButton.onclick();check(run('preparationId')===prepId);check(run('preparationView.current_materials.length')===1);
  check(calls.filter(c=>c.options.method==='POST').length===4);
 }else if(mode.startsWith('intake_')){
  $('goal').value='SYNTHETIC_COLD_INTAKE';$('candidate-region').value='SYNTHETIC_REGION';
  const form=mode==='intake_candidate'?'candidate-intake':'intake';const submit=$(form).onsubmit({preventDefault(){}}),post=calls.at(-1);
  check(post.path==='/api/runs'&&post.options.method==='POST');
  if(mode==='intake_unknown'){post.reject(Error('SYNTHETIC_LOST_RESPONSE'));await submit;$('run').value=id(2);}
  else{finish(post,201,{run_id:id(2)});await submit;check($('run').value===id(2));}
  check(run('entryWriteRequests.size')===1);
  const count=calls.length,refresh=$('refresh').onclick();await tick();check(calls.length===count+1);check(calls.at(-1).path==='/api/runs/'+id(2));
  finish(calls.at(-1),200,{id:mode==='intake_wrong_run'?id(9):id(2),state:'SUCCEEDED'});await refresh;
  if(['intake_unknown','intake_wrong_run'].includes(mode)){check(run('entryWriteRequests.size')===1);}
  else{check(run('entryWriteRequests.size')===0);const button=await queue('run');const open=button.onclick();check(calls.at(-1).path==='/api/runs/'+id(2));finish(calls.at(-1),200,{id:id(2),state:'SUCCEEDED'});await open;check($('run').scrolled);}
  check(calls.filter(c=>c.options.method==='POST').length===1);
 }else if(mode.startsWith('receipt_reject_')){
  const r=receipt();r.step.state='RECEIPT_RECORDED';r.current_receipt={source_sha256:'a'.repeat(64),version:1,text:'SYNTHETIC_RECEIPT',source_kind:'SYNTHETIC',source_label:'SYNTHETIC',actor_id:'fixture-executor',created_at:'SYNTHETIC'};
  const load=run("loadReceipt('"+id(4)+"')");finish(calls.at(-1),200,r);await load;$('receipt-reason').value=mode.endsWith('422')?'':'PRIVATE_FIRST_REASON';const before=run('receiptDraft()');
  const command=$('receipt-ack').onclick(),post=calls.at(-1),key=post.options.headers['Idempotency-Key'];check(post.options.method==='POST');
  const status=mode.endsWith('422')?422:409,detail=status===422?[{loc:['body','reason'],type:'string_too_short',msg:'String should have at least 1 character'}]:mode.endsWith('ambiguous')?'Case cancelled; business writes disabled':'stale receipt step revision; refresh required';finish(post,status,{detail});await command;
  check(run('receiptDraft()')===before);check(calls.filter(c=>c.options.method==='POST').length===1);
  if(mode.endsWith('ambiguous')){check(run('entryWriteRequests.size')===1);}
  else{check(run('entryWriteRequests.size')===0);const refresh=$('receipt-refresh').onclick();const r2=receipt();Object.assign(r2,{current_receipt:r.current_receipt});r2.step.state='RECEIPT_RECORDED';r2.step.revision=2;finish(calls.at(-1),200,r2);await refresh;
   $('receipt-reason').value='PRIVATE_CORRECTED_REASON';const corrected=$('receipt-ack').onclick(),second=calls.at(-1);check(second.options.method==='POST');check(second.options.headers['Idempotency-Key']!==key);check(JSON.parse(second.options.body).expected_revision===2);
   const r3={...r2,step:{...r2.step,revision:3,state:'LOCAL_ACKNOWLEDGED'},event:{revision:3}};finish(second,200,r3);await tick();finish(calls.at(-1),200,r3);await corrected;check(run('entryWriteRequests.size')===0);check(calls.filter(c=>c.options.method==='POST').length===2);
  }
 }else if(mode.startsWith('receipt_form_')){
  const r=receipt();r.role='service_executor';r.can_submit=true;const load=run("loadReceipt('"+id(4)+"')");finish(calls.at(-1),200,r);await load;
  $('receipt-text').value='PRIVATE_FORM_TEXT';$('receipt-source').value='SYNTHETIC_FORM_SOURCE';const draft=run('receiptDraft()');
  const command=$('receipt-submit').onsubmit({preventDefault(){}}),post=calls.at(-1);check(post.options.method==='POST');const key=post.options.headers['Idempotency-Key'];
  if(mode.endsWith('unknown')){post.reject(Error('SYNTHETIC_LOST_RESPONSE'));await tick();await command;}
  await tick();const saved=run('receiptSubmitHandle');check(saved?.key===key);check(storage.getItem(saved.name)===saved.raw);check(JSON.parse(saved.raw).key===key);
  const count=calls.length,list=$('receipt-list').onclick();await tick();
  if(mode.endsWith('unknown')){
   // A settled unknown SUBMIT permits original read-only navigation, while
   // its opaque persisted handle continues to block new business writes.
   check(calls.length===count+1);check(calls.at(-1).path==='/api/executor-receipts');check(calls.at(-1).options.method==='GET');
   finish(calls.at(-1),200,{items:[],role:'service_executor'});await list;
   check(storage.getItem(saved.name)===saved.raw);check($('receipt-current').children.length===0);check($('receipt-detail').hidden);check(run('receiptView===null'));
   check(run('receiptSubmitStoredPending()'));check(run('originalStoredWritePending()'));
  }else{check(calls.length===count);check(run('receiptDraft()')===draft);check(run('receiptSubmitHandle.key')===key);await list;}
  if(mode.endsWith('pending')){post.reject(Error('SYNTHETIC_LOST_RESPONSE'));await tick();await command;}check(calls.filter(c=>c.options.method==='POST').length===1);
 }else if(mode.startsWith('resource_write_')){
  const load=run("loadPreparation('"+id(3)+"',{role:'enterprise_operator'}).catch(prepError)");const m=material();m.preparation.state='LOCAL_CONFIRMED';finish(calls.at(-1),200,m);await flushOtherGets();await load;
  const resource=run('loadCaseResources()');finish(calls.at(-1),200,{link_revision:0,preparation_revision:1,current:null,history:[]});await tick();finish(calls.at(-1),200,{preparation_revision:1,ready:true,items:[{eligible:true,combination:{id:id(12),members:[]}}]});await resource;
  $('case-resource-reason').value='PRIVATE_LINK_REASON';const draft=run('caseResourceDraft()'),button=await queue('run');
  const command=$('case-resource-form').onsubmit({preventDefault(){}}),post=calls.at(-1);check(post.options.method==='POST');const key=post.options.headers['Idempotency-Key'];check(!!key);
  if(mode.endsWith('unknown')){post.reject(Error('SYNTHETIC_LOST_RESPONSE'));await command;}
  if(mode.endsWith('semantic')){finish(post,200,{preparation_id:id(3),link_revision:1});await tick();finish(calls.at(-1),200,{preparation_id:id(3),link_revision:1,preparation_revision:1,current:null,history:[]});await tick();finish(calls.at(-1),200,{preparation_revision:2,ready:true,items:[{eligible:true,combination:{id:id(12),members:[]}}]});await command;check(run('entryWriteRequests.size')===1);}
  const count=calls.length;const navigation=button.onclick();await tick();check(calls.length===count);check(run('caseResourceDraft()')===draft);check(run('[...caseResourceRetries.values()].includes("'+key+'")'));check($('page-feedback').textContent.includes('原入口'));await navigation;
  if(mode.endsWith('pending')){post.reject(Error('SYNTHETIC_LOST_RESPONSE'));await command;}check(calls.filter(c=>c.options.method==='POST').length===1);
 }else if(mode.startsWith('history_')){
  $('receipt-history-preparation').value=id(3);$('receipt-history-key').value='SYNTHETIC_HISTORY_KEY';
  const history=$('receipt-history-read').onclick(),old=calls.at(-1);const x={read_only:true,history_transport:'ISOLATED_P4_LIVE_ISSUER_HISTORY_GET_V1',preparation_id:id(3),scope:'ISOLATED_REGISTERED_P4_RECEIPT_EXECUTION_PREVIEW',formal_writes:0,automatically_replayed:false,status:'NOT_OBSERVED',result:null};
  if(mode==='history_rendered'){finish(old,200,x);await history;check($('receipt-history-result').children.length>0);}
  const denied=run("apiCall('/api/runs/"+id(2)+"').catch(pageError)");finish(calls.at(-1),403,{});await denied;check($('receipt-history-result').children.length===0);
  if(mode==='history_pending'){finish(old,200,x);await history;}check($('receipt-history-result').children.length===0);check($('page-feedback').textContent.includes('权限'));
 }else if(mode.startsWith('manual_receipt_')){
  const action=mode.split('_')[2],phase=mode.split('_')[3];
  const r=receipt();if(action==='SUBMIT'){r.role='service_executor';r.can_submit=true;}else{r.step.state='RECEIPT_RECORDED';r.current_receipt={source_sha256:'a'.repeat(64),version:1,text:'SYNTHETIC_RECEIPT',source_kind:'SYNTHETIC',source_label:'SYNTHETIC',actor_id:'fixture-executor',created_at:'SYNTHETIC'};}
  const load=run("loadReceipt('"+id(4)+"')");finish(calls.at(-1),200,r);await load;
  $('receipt-text').value='PRIVATE_UNRESOLVED_TEXT';$('receipt-source').value='SYNTHETIC_SOURCE';$('receipt-reason').value='PRIVATE_UNRESOLVED_REASON';
  const button=await queue('run'),beforeDraft=run('receiptDraft()');
  const command=run("receiptCommand('"+action+"').catch(receiptError)"),post=calls.at(-1);check(post.options.method==='POST');
  const key=post.options.headers['Idempotency-Key'];check(!!key);
  if(phase==='unknown'){post.reject(Error('SYNTHETIC_LOST_RESPONSE'));await command;}
  const count=calls.length;const navigation=button.onclick();await tick();
  check(calls.length===count);check(run('receiptDraft()')===beforeDraft);if(action==='SUBMIT'){const saved=run('receiptSubmitHandle');check(saved?.key===key);check(storage.getItem(saved.name)===saved.raw);check(JSON.parse(saved.raw).key===key);}else check(run('[...receiptRetries.values()].includes("'+key+'")'));check($('page-feedback').textContent.includes('原入口'));await navigation;
  if(phase==='pending'){post.reject(Error('SYNTHETIC_LOST_RESPONSE'));await command;}
  check(calls.filter(c=>c.options.method==='POST').length===1);
 }else if(mode==='run_403'||mode==='run_403_invalid_json'||mode==='run_403_pending_reference'){
  $('prep-summary').textContent='PRIVATE_OLD_MATERIAL';$('prep-detail').hidden=false;
  $('receipt-summary').textContent='PRIVATE_OLD_RECEIPT';$('receipt-detail').hidden=false;
  $('resource-current').textContent='PRIVATE_OLD_RESOURCE';
  run("preparationView={preparation:{id:'"+id(3)+"'}};receiptView={step:{id:'"+id(4)+"'}}");
  let p;if(mode==='run_403_pending_reference'){store['existing-opaque-handle']='SYNTHETIC_OPAQUE_REFERENCE';run("$('run-access-id').value='"+id(2)+"';runAccessPending={key:'"+id(99)+"',body:{reason:'PRIVATE_UNKNOWN_REASON'},context:runAccessCtx()}");p=run("apiCall('/api/runs/"+id(2)+"').catch(pageError)");}else{const button=await queue('run');p=button.onclick();}const c=calls.at(-1);c.finished=true;if(mode==='run_403_invalid_json')c.resolve({status:403,ok:false,json:async()=>{throw Error('PRIVATE_INVALID_JSON');}});else finish(c,403,{});await p;
  check($('prep-summary').textContent==='');check($('receipt-summary').textContent==='');check($('resource-current').textContent==='');
  check(run('preparationView===null&&receiptView===null'));check($('page-feedback').textContent.includes('权限'));if(mode==='run_403_pending_reference'){check(store['existing-opaque-handle']==='SYNTHETIC_OPAQUE_REFERENCE');check(run("deniedOperationReferences.get('RUN_ACCESS:"+id(99)+"').key")===id(99));check(run("deniedOperationReferences.get('RUN_ACCESS:"+id(99)+"').id")===id(2));check(!run('JSON.stringify([...deniedOperationReferences.values()])').includes('PRIVATE_UNKNOWN_REASON'));}
 }else if(mode.startsWith('pending_')){
  const flag=mode.slice(8),button=await queue('run');const originalCount=calls.length;run(flag+'='+(flag.endsWith('Pending')||flag.endsWith('Handle')?"{key:'SYNTHETIC_UNRESOLVED',body:{reason:'PRIVATE_PENDING'}}":'true'));const before=run('JSON.stringify('+flag+')');await button.onclick();check(calls.length===originalCount);check(run('JSON.stringify('+flag+')')===before);check($('page-feedback').textContent.includes('原入口'));
 }else if(mode==='material_to_receipt'||mode==='material_to_localcase'){
  const button=await queue('materials');const a=button.onclick();await tick();const old=calls.at(-1);if(old.path!=='/api/preparations/'+id(3))console.error(JSON.stringify({harness_setup_error:$('page-feedback').textContent}));check(old.path==='/api/preparations/'+id(3));old.finished=true;
  const next=await queue(mode==='material_to_receipt'?'receipt':'localcase',id(5),id(4));const b=next.onclick();const current=calls.at(-1);current.finished=true;
  if(mode==='material_to_receipt')finish(current,200,receipt());else finish(current,200,{preparation_id:id(5),goal:'CURRENT_LOCALCASE_B',local_record_state:'NEEDS_INPUT',case_state:'WAITING_CONFIRMATION',cycle:1,revision:1,current_snapshot_sha256:'SYNTHETIC_SHA',role:'enterprise_operator',checks:{},history:[],can_revalidate:false,can_close_local_record:false,can_reopen:false});
  await b;finish(old,200,material());await tick();if($('prep-summary').textContent.includes('PRIVATE_MATERIAL_A'))console.error(JSON.stringify({phase:'late_material_render',prep:$('prep-summary').textContent,paths:calls.map(c=>c.path)}));check(!$('prep-summary').textContent.includes('PRIVATE_MATERIAL_A'));await flushOtherGets();await a;
  check(!$('prep-summary').textContent.includes('PRIVATE_MATERIAL_A'));check(!$('prep-materials').children.some(e=>JSON.stringify(e).includes('PRIVATE_BODY_A')));
  check(run('preparationView===null'));if(mode==='material_to_receipt')check($('receipt-summary').textContent.includes('CURRENT_RECEIPT_B'));else check($('local-case-summary').textContent.includes('CURRENT_LOCALCASE_B'));
 }
 if(!mode.startsWith('intake_')&&!mode.startsWith('manual_receipt_')&&!mode.startsWith('resource_write_')&&!mode.startsWith('receipt_form_')&&!mode.startsWith('receipt_reject_'))check(calls.every(c=>!c.options.method||c.options.method==='GET'));
 console.log(JSON.stringify({mode,checks,scope:'FULL_ORIGINAL_PAGE_NODE_VM_ONLY_NO_ENTRY_MOCKS'}));if(mode==='intake_cold_asgi')process.exit(0);
})().catch(e=>{console.error(e.stack);if(mode==='intake_cold_asgi')process.exit(1);process.exitCode=1;});
