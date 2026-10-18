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
 const config=await initialized,calls=[];diagnostics={calls};
 const reviewer=page({...config,token:config.tokens.reviewer},{},calls,{});
 await reviewer.$('prep-list').click();const prep=reviewer.$('prep-items').children.find(e=>e.tagName==='button');check(!!prep,'actual preparation list entry');await prep.click();
 check(reviewer.run('preparationId')===config.preparation_id,'original preparation list navigation');reviewer.$('dispatch-prepare').click();await until(()=>reviewer.run('dispatchView')!==null);
 check(reviewer.run('dispatchCatalog.assignment_contract')==='ISOLATED_CASE_STEP_ASSIGNMENT_V1','original preparation dispatch button');
 reviewer.$('dispatch-executor').value='executor-a';reviewer.$('dispatch-offer-reason').value='PRIVATE_NOTICE_REASON';await reviewer.$('dispatch-offer').onsubmit({preventDefault(){}});
 check(reviewer.run('dispatchView.current_offer.state')==='OFFERED','original form offer');await control('drain');
 const transport={},executor=page({...config,token:config.tokens.executor},{},calls,transport);
 if(config.flow==='LATE_LIST'){
  let arrived,release;const held=new Promise(r=>arrived=r);transport.release=new Promise(r=>release=r);transport.held=arrived;transport.hold=c=>c.path==='/api/dispatch-notices'&&c.method==='GET';
  const old=executor.$('notice-list').click();await held;executor.$('token').value=config.tokens.other;executor.$('token').emit('input');await executor.$('notice-list').click();const before=snapshot(executor);release();await old;check(snapshot(executor)===before,'late actual list cannot restore prior identity');
 }else{
  await executor.$('notice-list').click();check(calls.at(-1).path==='/api/dispatch-notices','original notice list button');
  const card=executor.$('notice-items').children.find(e=>e.dataset?.noticeId),button=card?.children.find(e=>e.tagName==='button');check(!!button,'actual inbox card navigation');button.click();await until(()=>executor.run('noticeView')!==null);
  check(textOf(executor.$('notice-summary')).includes('未授予Run访问权'),'bounded scope disclosed');check(!executor.run('noticeView.read_at'),'not implicitly read');
  if(config.flow==='NORMAL'){
   await executor.$('notice-open').click();check(executor.run('dispatchView?.assignment_contract')==='ISOLATED_CASE_STEP_ASSIGNMENT_V1','original OPEN navigates current step');check(!executor.run('noticeView.read_at'),'OPEN distinct from read');
   check(!executor.$('notice-read').disabled,'explicit read available');await executor.$('notice-read').click();check(!!executor.run('noticeView.read_at'),'actual explicit MARK_READ');
   check(calls.filter(c=>c.method==='POST').map(c=>c.body.action||'OFFER').join(',')==='OFFER,OPEN,MARK_READ','no automatic accept or fulfilment');
  }else{
   if(config.flow==='LATE_MARK')await executor.$('notice-open').click();
   if(config.flow==='LATE_403')await control('revoke');
   let arrived,release;const held=new Promise(r=>arrived=r);transport.release=new Promise(r=>release=r);transport.held=arrived;transport.hold=c=>c.method==='POST'&&c.path.includes('/api/dispatch-notices/');
   const old=executor.$(config.flow==='LATE_MARK'?'notice-read':'notice-open').click();const response=await held;
   check(response.status===(config.flow==='LATE_403'?403:200),'held actual server response');executor.$('token').value=config.tokens.other;executor.$('token').emit('input');await executor.$('notice-list').click();const before=snapshot(executor);release();await old;
   check(snapshot(executor)===before,'late actual command result cannot restore old identity');
  }
 }
 await control('assert_final');console.log(JSON.stringify({scope:'CASE_STEP_NOTICE_ORIGINAL_LIST_NAVIGATION',flow:config.flow,checks,calls,real_browser:false}));process.exit(0);
})().catch(error=>{console.error(error.stack);console.error(JSON.stringify(diagnostics));process.exit(1);});
