// Entire shipped page, actual fetch to the owned HTTP/ASGI/PostgreSQL fixture.
// The small DOM surface below supplies browser mechanics, never product logic.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const readline = require('readline').createInterface({input: process.stdin});
let initialize;
const initialized = new Promise(resolve => initialize = resolve), replies = [];
readline.on('line', line => { const x = JSON.parse(line); if (initialize) { initialize(x); initialize = null; } else replies.shift()(x); });
const control = name => new Promise(resolve => { replies.push(resolve); console.log(JSON.stringify({control: name})); });
const html = fs.readFileSync('src/parkweave/web.html', 'utf8');
const code = html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
let checks = 0, diagnostics;
const check = (value, description) => { checks++; assert(value, description); };
class Element {
  constructor(tag = 'div') {
    this.tagName = tag; this.children = []; this.dataset = {}; this.textContent = ''; this.value = '';
    const classes=new Set();this.classList={add:(...xs)=>xs.forEach(x=>classes.add(x)),remove:(...xs)=>xs.forEach(x=>classes.delete(x)),contains:x=>classes.has(x),toggle:(x,force)=>{const on=force===undefined?!classes.has(x):!!force;if(on)classes.add(x);else classes.delete(x);return on;}};this.hidden = true; this.disabled = false; this.checked = false; this.listeners = {};
    const named = {}; this.elements = new Proxy([], {get: (a, key) => key in a ? a[key] : (named[key] ??= new Element('input'))});
  }
  append(...values) { this.children.push(...values); }
  replaceChildren(...values) { this.children = values; this.textContent = ''; }
  get options() { return this.children.filter(e => e.tagName === 'option'); }
  get selectedOptions() { return this.options.filter(e => e.value === this.value); }
  get firstChild() { return this.children[0]; }
  get firstElementChild() { return this.children[0]; }
  addEventListener(name, handler) { (this.listeners[name] ??= []).push(handler); }
  emit(name) { this['on' + name]?.({target: this}); for (const handler of this.listeners[name] || []) handler({target: this}); }
  reset() {} setAttribute() {} removeAttribute() {} closest() { return null; } querySelectorAll() { return []; }
  scrollIntoView() {} focus() {} select() {} remove() {} click() { return this.onclick?.(); }
}
const textOf = element => element.textContent + element.children.map(e => typeof e === 'object' ? textOf(e) : e).join(' ');
function page(config, storage, calls, transport) {
  const documentHTML = config.page === 'upgrade' ? fs.readFileSync('src/parkweave/template_upgrade_web.html', 'utf8') : html;
  const pageCode = documentHTML.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
  const elements = new Map();
  for (const match of documentHTML.split('<script')[0].matchAll(/<([a-z][\w-]*)\b([^>]*)>/gi)) {
    const attrs = match[2], id = attrs.match(/\bid=["']([^"']+)["']/)?.[1];
    if (!id && !/\bdata-/.test(attrs)) continue;
    const element = new Element(match[1].toLowerCase()); element.id = id || 'anonymous-' + elements.size;
    for (const data of attrs.matchAll(/\bdata-([\w-]+)=["']([^"']*)["']/g)) element.dataset[data[1].replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = data[2];
    element.hidden=/\bhidden\b/.test(attrs);element.disabled=/\bdisabled\b/.test(attrs);elements.set(element.id, element);
  }
  const $ = id => { if (!elements.has(id)) { const e = new Element(); e.id = id; elements.set(id, e); } return elements.get(id); };
  const walk = e => [e, ...e.children.filter(x => typeof x === 'object').flatMap(walk)];
  const query = selector => [...elements.values()].flatMap(walk).filter(e => selector.split(',').some(s => {
    if (['button', 'form'].includes(s)) return e.tagName === s;
    const m = s.match(/^\[data-([\w-]+)\]$/); return m && Object.hasOwn(e.dataset, m[1].replace(/-([a-z])/g, (_, c) => c.toUpperCase()));
  }));
  const localStorage = new Proxy({getItem: k => storage[k] ?? null, setItem: (k, v) => storage[k] = v, removeItem: k => delete storage[k]}, {ownKeys: () => Object.keys(storage), getOwnPropertyDescriptor: () => ({enumerable: true, configurable: true})});
  const context = vm.createContext({console, Date, JSON, Map, Set, WeakMap, Number, String, Error, TextEncoder, URL, URLSearchParams, encodeURIComponent,
    crypto: require('crypto').webcrypto, localStorage, setTimeout: () => 1, clearTimeout() {},
    document: {getElementById: $, createElement: t => new Element(t), querySelectorAll: query, body: new Element('body'), addEventListener() {}, execCommand: () => false},
    window: {addEventListener() {}}, fetch: async (path, options = {}) => {
      if (transport.revokeBeforeRead && (options.method || 'GET') === 'GET' && path.includes('dependency_scope=BOUNDED_MULTI_SOURCE_V1')) {
        transport.revokeBeforeRead = false;
        await control('revoke');
      }
      const response = await fetch(config.base + path, options), body = await response.json();
      const call = {method: options.method || 'GET', path, status: response.status};
      if (options.body) call.body = JSON.parse(options.body);
      if (options.headers?.['Idempotency-Key']) call.request_key = options.headers['Idempotency-Key'];
      if (body.source_impact) call.graph_sha256 = body.source_impact.sha256;
      call.response_scope = body.scope; call.response_schema = body.schema;
      if (body.dependency_propagation) call.dependency_propagation_sha256=body.dependency_propagation.sha256;if(body.typed_dependency_preview)transport.lastPreview=body;if(body.resource_dependency_preview){call.resource_graph_sha256=body.resource_dependency_preview.sha256;call.member_state=body.resource_dependency_preview.membership.state;}
      if (body.scope==='CURRENT_OWNER_SYNTHETIC_CASE_WORKLIST') call.worklist_items=body.items.map(r=>({case_id:r.case_id,preparation_id:r.preparation_id,receipt_step_id:r.receipt_step_id,evidence_verified:r.evidence_verified,case_goal_completed:r.case_goal_completed}));
      calls.push(call);console.log(JSON.stringify({trace:call}));
      if (response.status === 403 && (options.method || 'GET') === 'GET' && path.includes('dependency_scope=BOUNDED_MULTI_SOURCE_V1')) {
        await control('assert_denied_read_no_write');
      }
      const rejectJson = transport.jsonReject?.(call); if (rejectJson) transport.jsonReject = null;
      const rejectFetch = transport.fetchReject?.(call); if (rejectFetch) transport.fetchReject = null;
      if (transport.hold?.(call)) { transport.hold = null; transport.held(call); await transport.release; }
      if (rejectFetch) {
        transport.held(call); await transport.release;
        throw Object.assign(Error('SYNTHETIC_CONTROLLED_LATE_TRANSPORT_REJECT'), {status:403});
      }
      if (transport.dropPath && call.method === 'POST' && path.endsWith(transport.dropPath)) {
        transport.dropPath = null; throw Error('SYNTHETIC_UNIFIED_COMMITTED_RESPONSE_LOST');
      }
      return {status: response.status, ok: response.ok, json: async () => {
        if (rejectJson) {
          transport.held(call); await transport.release;
          throw Object.assign(Error('SYNTHETIC_CONTROLLED_LATE_JSON_REJECT'), {status:403});
        }
        return body;
      }};
    }});
  vm.runInContext(pageCode, context); $('token').value = config.token;
  return {$, run: text => vm.runInContext(text, context), context, elements};
}

const until=async predicate=>{for(let i=0;i<500;i++){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,10));}throw Error('bounded original handler settlement not observed');};
const snapshot=p=>p.run(`JSON.stringify({id:noticeId,view:noticeView,context:noticeContext,cursor:noticeNextCursor,loading:noticeListLoading,summary:document.getElementById('notice-summary').textContent,error:document.getElementById('notice-error').textContent,feedback:document.getElementById('page-feedback').textContent,dispatch:dispatchView,receipt:receiptView})`);
(async()=>{
 const config=await initialized,calls=[];diagnostics={calls};let result;
 if(config.phase==='OFFER'){
  const reviewer=page({...config,token:config.tokens.reviewer},{},calls,{});
  await reviewer.$('prep-list').click();const button=reviewer.$('prep-items').children.find(e=>e.tagName==='button');check(!!button,'actual preparation list');await button.click();
  check(reviewer.run('preparationId')===config.preparation_id,'original preparation row');reviewer.$('dispatch-prepare').click();await until(()=>reviewer.run('dispatchView')!==null);
  check(reviewer.run('dispatchCatalog.assignment_contract')==='CASE_STEP_ASSIGNMENT_V1','ordinary current preparation catalog');check(calls.every(c=>c.method==='GET'),'navigation performs no automatic POST');
  reviewer.$('dispatch-executor').value='executor-a';reviewer.$('dispatch-offer-reason').value='SYNTHETIC ordinary exact duty';await reviewer.$('dispatch-offer').onsubmit({preventDefault(){}});
  const x=reviewer.run('dispatchView');check(x.current_offer.state==='OFFERED','ordinary explicit original offer');result={dispatch_id:x.dispatch_id,deadline:x.assignment_valid_until};
 }else if(config.phase==='REDISPATCH'){
  const transport={dropPath:config.drop_reoffer_response?'/dispatch':null};
  const reviewer=page({...config,token:config.tokens.reviewer},{},calls,transport);
  await reviewer.$('dispatch-list').click();const item=reviewer.$('dispatch-items').children.find(e=>e.tagName==='button');check(!!item,'responsible specialist original dispatch list');item.click();await until(()=>reviewer.run('dispatchView')!==null);
  check(reviewer.run('dispatchCatalog.can_offer_again')===true,'ordinary explicit unaccepted redispatch available');
  check(reviewer.run('dispatchCatalog.can_reassign')===false&&reviewer.run('dispatchCatalog.can_reoffer')===false,'no legacy handoff or material renewal path');
  check(reviewer.$('dispatch-offer').hidden===false,'original form visible after terminal offer');
  if(config.pending_handoff){check(reviewer.run('dispatchCatalog.offer_again_kind')==='WITHDRAWN_ZERO_RECEIPT','exact zero receipt mode');check(reviewer.$('dispatch-offer-button').textContent==='明确交接零回执事项','handoff action named explicitly');check(textOf(reviewer.$('dispatch-current')).includes('不证明现实工作未发生'),'no invented external effect claim');}
  check(textOf(reviewer.$('dispatch-current')).includes('不延长办理时间'),'first deadline is explained');
  reviewer.$('dispatch-executor').value='unassigned';reviewer.$('dispatch-offer-reason').value='SYNTHETIC explicit different responsibility after decline';await reviewer.$('dispatch-offer').onsubmit({preventDefault(){}});
  if(config.drop_reoffer_response){
   check(reviewer.run('dispatchPending')!==null,'unknown result keeps exact original request');
   check(calls.filter(c=>c.method==='POST').length===1,'no automatic retry');
   await reviewer.$('dispatch-retry').click();
   const writes=calls.filter(c=>c.method==='POST');check(writes.length===2&&writes[0].request_key===writes[1].request_key&&JSON.stringify(writes[0].body)===JSON.stringify(writes[1].body),'explicit retry keeps original key and body');
  }
  const x=reviewer.run('dispatchView');check(x.current_offer.executor_id==='unassigned'&&x.current_offer.state==='OFFERED','new executor original offer');check(x.assignment_valid_until===config.deadline,'redispatch does not renew first deadline');
  check(x.history.map(e=>e.action).join(',')===(config.pending_handoff?'OFFER,ACCEPT,WITHDRAW,REOFFER':'OFFER,DECLINE,REOFFER'),'history and generation retained');
  if(config.pending_handoff)check(reviewer.$('dispatch-offer-button').textContent==='明确交接零回执事项' || x.current_offer.state==='OFFERED','pending handoff uses original explicit form');
  result={dispatch_id:x.dispatch_id,offer_id:x.current_offer.id,deadline:x.assignment_valid_until,revision:x.revision};
 }else if(config.phase==='WITHDRAW_PENDING'){
  const executor=page({...config,token:config.tokens.executor},{},calls,{});
  await executor.$('dispatch-list').click();const item=executor.$('dispatch-items').children.find(e=>e.tagName==='button');check(!!item,'own first invitation');item.click();await until(()=>executor.run('dispatchView')!==null);
  check(calls.every(c=>c.method==='GET'),'reading does not accept');executor.$('dispatch-decision-reason').value='SYNTHETIC own acceptance';await executor.$('dispatch-accept').click();
  const old_step=executor.run('dispatchView.receipt_step_id');check(!!old_step,'own acceptance creates old step');
  const reviewer=page({...config,token:config.tokens.reviewer},{},calls,{});await reviewer.$('dispatch-list').click();const own=reviewer.$('dispatch-items').children.find(e=>e.tagName==='button');own.click();await until(()=>reviewer.run('dispatchView')!==null);
  check(reviewer.$('dispatch-offer').hidden===true,'active accepted duty cannot silently reassign');reviewer.$('dispatch-decision-reason').value='SYNTHETIC specialist explicitly withdraws unavailable duty';await reviewer.$('dispatch-withdraw').click();
  check(reviewer.run('dispatchView.current_offer.state')==='WITHDRAWN','specialist withdrawal recorded');check(reviewer.run('dispatchCatalog.can_offer_again')===true,'zero receipt handoff available after explicit withdrawal');
  check(calls.filter(c=>c.method==='POST').map(c=>c.body.action).join(',')==='ACCEPT,WITHDRAW','only each clicked action is sent');result={old_step};
 }else if(config.phase==='EXECUTE'){
  const executor=page({...config,token:config.tokens.executor},{},calls,{});
  await executor.$('notice-list').click();const card=executor.$('notice-items').children.find(e=>e.dataset?.noticeId),button=card?.children.find(e=>e.tagName==='button');check(!!button,'actual restarted inbox card');button.click();await until(()=>executor.run('noticeView')!==null);
  await executor.$('notice-open').click();check(executor.run('dispatchView.assignment_contract')==='CASE_STEP_ASSIGNMENT_V1','original OPEN navigates step');check(!executor.run('noticeView.read_at'),'OPEN separate from read');await executor.$('notice-read').click();check(!!executor.run('noticeView.read_at'),'explicit MARK_READ');
  check(executor.run('dispatchView.assignment_valid_until')===config.deadline,'API/worker restart retains first deadline');executor.$('dispatch-decision-reason').value='SYNTHETIC I accept my own step';await executor.$('dispatch-accept').click();check(executor.run('dispatchView.current_offer.state')==='ACCEPTED','explicit original ACCEPT with proof');
  const step=executor.run('dispatchView.receipt_step_id');await executor.$('receipt-list').click();const receipt=executor.$('receipt-items').children.find(e=>e.tagName==='button');check(!!receipt,'original executor receipt list');receipt.click();await until(()=>executor.run('receiptView')!==null);
  check(executor.run('receiptView.step.id')===step,'receipt list exact accepted step');executor.$('receipt-text').value='SYNTHETIC ordinary manual task output';executor.$('receipt-source').value='SYNTHETIC executor work log';await executor.$('receipt-submit').onsubmit({preventDefault(){}});check(executor.run('receiptView.step.state')==='RECEIPT_RECORDED','original submit and GET proof');
  const owner=page({...config,token:config.tokens.owner},{},calls,{});await owner.$('receipt-list').click();const own=owner.$('receipt-items').children.find(e=>e.tagName==='button');check(!!own,'original owner receipt list');own.click();await until(()=>owner.run('receiptView')!==null);
  owner.$('receipt-reason').value='SYNTHETIC independent owner check';await owner.$('receipt-ack').click();check(owner.run('receiptView.step.state')==='LOCAL_ACKNOWLEDGED','original owner ACK');check(owner.run('receiptView.case_goal_completed')===false,'no fulfillment claim');
  result={step,deadline:owner.run('receiptView.assignment_valid_until'),state:owner.run('receiptView.step.state')};
 }else if(config.phase==='DECLINE'){
  const executor=page({...config,token:config.tokens.executor},{},calls,{});await executor.$('dispatch-list').click();const item=executor.$('dispatch-items').children.find(e=>e.tagName==='button');check(!!item,'actual own dispatch list');item.click();await until(()=>executor.run('dispatchView')!==null);executor.$('dispatch-decision-reason').value='SYNTHETIC I decline this step';await executor.$('dispatch-decline').click();check(executor.run('dispatchView')===null,'terminal old view cleared');check(textOf(executor.$('page-feedback')).includes('已记录本人拒绝'),'successful ordinary decline disclosed');check(calls.at(-1).method==='POST'&&calls.at(-1).status===200&&calls.at(-1).body.action==='DECLINE','no forbidden automatic read after terminal success');result={terminal:true};
 }else{
  const owner=page({...config,token:config.tokens.owner},{},calls,{});await owner.$('receipt-list').click();const own=owner.$('receipt-items').children.find(e=>e.tagName==='button');check(!!own,'cold owner list');own.click();await until(()=>owner.run('receiptView')!==null);
  check(owner.run('receiptView.step.id')===config.step,'cold exact UUID');check(owner.run('receiptView.step.state')==='LOCAL_ACKNOWLEDGED','cold original ACK');check(owner.run('receiptView.assignment_valid_until')===config.deadline,'cold deadline unchanged');
  const executor=page({...config,token:config.tokens.executor},{},calls,{});await executor.$('notice-list').click();const card=executor.$('notice-items').children.find(e=>e.dataset?.noticeId),button=card?.children.find(e=>e.tagName==='button');check(!!button,'cold executor notices');button.click();await until(()=>executor.run('noticeView')!==null);check(!!executor.run('noticeView.read_at'),'original read timestamp retained');check(calls.every(c=>c.method==='GET'),'cold navigation GET only');result={step:config.step,deadline:config.deadline};
 }
 console.log(JSON.stringify({scope:'ORDINARY_CASE_STEP_REAL_HTML',phase:config.phase,checks,calls,...result,real_browser:false}));process.exit(0);
})().catch(e=>{console.error(e.stack);console.error(JSON.stringify(diagnostics));process.exit(1);});
