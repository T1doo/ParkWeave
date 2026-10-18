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
    elements.set(element.id, element);
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

(async()=>{
 const config=await initialized,calls=[],storage={},transport={};diagnostics={calls};
 const reviewer=page({...config,token:config.tokens.reviewer},{},calls,{});
 await reviewer.run(`loadDispatch(${JSON.stringify(config.preparation_id)})`);
 check(reviewer.run('dispatchCatalog.assignment_contract')==='ISOLATED_CASE_STEP_ASSIGNMENT_V1','explicit isolated CaseStep catalog');
 check(textOf(reviewer.$('dispatch-current')).includes('未授予Run访问权'),'scope disclosure');
 check(calls.every(x=>x.method==='GET'),'no automatic business write');
 reviewer.$('dispatch-executor').value='executor-a';reviewer.$('dispatch-offer-reason').value='SYNTHETIC explicit CaseStep duty';
 await reviewer.$('dispatch-offer').onsubmit({preventDefault(){}});
 check(reviewer.run('dispatchView.current_offer.state')==='OFFERED','original form records actual offer');
 const executor=page({...config,token:config.tokens.executor},storage,calls,transport);
 await executor.run(`loadDispatch(${JSON.stringify(config.preparation_id)})`);
 check(executor.run('dispatchView.run_access_granted')===false,'no Run grant');
 if(config.flow==='DECLINE'){
  executor.$('dispatch-decision-reason').value='SYNTHETIC I decline this step';await executor.$('dispatch-decline').onclick();
  check(executor.run('dispatchView')===null,'terminal view cleared');check(textOf(executor.$('page-feedback')).includes('已记录本人拒绝'),'explicit terminal success');
  check(calls.at(-1).method==='POST'&&calls.at(-1).body.action==='DECLINE','no forbidden automatic GET after terminal decline');
  await control('assert_final');console.log(JSON.stringify({scope:'ISOLATED_CASE_STEP_ORIGINAL_FULL_HTML',checks,calls,flow:config.flow,real_browser:false}));process.exit(0);
 }
 executor.$('dispatch-decision-reason').value='SYNTHETIC I accept my exact step';await executor.$('dispatch-accept').onclick();
 check(executor.run('dispatchView.current_offer.state')==='ACCEPTED','original ACCEPT and original-key recovery');
 if(config.flow==='WITHDRAW_REVOKED'){
  await control('revoke_executor');const specialist=page({...config,token:config.tokens.reviewer},{},calls,{});
  await specialist.run(`loadDispatch(${JSON.stringify(config.preparation_id)})`);
  check(!specialist.$('dispatch-decision').hidden,'current specialist can enter revoked step termination');
  specialist.$('dispatch-decision-reason').value='SYNTHETIC terminate revoked step';await specialist.$('dispatch-withdraw').onclick();
  check(specialist.run('dispatchView.current_offer.state')==='WITHDRAWN','actual original UI withdrawal after target revocation');
  await control('assert_final');console.log(JSON.stringify({scope:'ISOLATED_CASE_STEP_ORIGINAL_FULL_HTML',checks,calls,flow:config.flow,real_browser:false}));process.exit(0);
 }
 const step=executor.run('dispatchView.receipt_step_id');await executor.run(`loadReceipt(${JSON.stringify(step)})`);
 executor.$('receipt-text').value='SYNTHETIC actual bounded task output';executor.$('receipt-source').value='SYNTHETIC executor manual work';
 await executor.$('receipt-submit').onsubmit({preventDefault(){}});
 check(executor.run('receiptView.step.state')==='RECEIPT_RECORDED','original SUBMIT form and GET proof');
 check(Object.keys(storage).length===0,'accept/submit opaque handles cleared by actual proofs');
 const owner=page({...config,token:config.tokens.owner},{},calls,{});await owner.run(`loadReceipt(${JSON.stringify(step)})`);
 owner.$('receipt-reason').value='SYNTHETIC owner independently checks actual output';await owner.$('receipt-ack').onclick();
 check(owner.run('receiptView.step.state')==='LOCAL_ACKNOWLEDGED','original owner ACK');
 check(owner.run('receiptView.case_goal_completed')===false,'no fulfillment claim');
 check(calls.filter(x=>x.method==='POST').length===4,'only OFFER ACCEPT SUBMIT ACK explicit POST');
 check(!JSON.stringify(calls).includes('PRIVATE_REQUEST_')&&!JSON.stringify(calls).includes('PRIVATE_MATERIAL_'),'no private request or material in step actions');
 await control('assert_final');
 console.log(JSON.stringify({scope:'ISOLATED_CASE_STEP_ORIGINAL_FULL_HTML',checks,calls,step,real_browser:false}));process.exit(0);
})().catch(e=>{console.error(e.stack);console.error(JSON.stringify(diagnostics));process.exit(1);});
