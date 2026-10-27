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
let checks = 0, diagnostics; const blobs=[]; class OwnedURL extends URL {static createObjectURL(blob){blobs.push(blob);return 'blob:owned-test';} static revokeObjectURL(){}};
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
  const context = vm.createContext({console, Date, JSON, Map, Set, WeakMap, Number, String, Error, TextEncoder, Blob, URL:OwnedURL, URLSearchParams, encodeURIComponent,
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
(async()=>{const config=await initialized,storage={},calls=[],transport={};diagnostics={calls};const p=page(config,storage,calls,transport),$=p.$;
 await $('template-input-catalog').onclick();
 if(config.mode==='default'){check($('template-input-form').hidden,'missing source leaves form unavailable');check(textOf($('template-input-status')).includes('未接入'),'precise missing-source message');check(!calls.some(c=>c.method==='POST'),'no fallback creation');}
 else{
 check(!p.run('tiBusy'),'catalog flow releases its own busy ticket');check(p.run('tiCatalog.templates.length')===1,'one current catalog-bound existing candidate');
 for(const [field,value] of Object.entries({goal:'本次全新模板诉求',need:'本次全新诉求证据', 'need-source':'本次企业声明',outline:'本次全新资料清单','outline-source':'本次文档摘录',reason:'本次明确按已审版本准备新输入'}))$('template-input-'+field).value=value;
 $('template-input-confirm').checked=true;
 if(config.mode==='pin')await control('drift');
 if(['edit','token','aba'].includes(config.mode)){
  let held;const waiting=new Promise(resolve=>held=resolve);let release;transport.release=new Promise(resolve=>release=resolve);transport.held=held;transport.hold=c=>c.path==='/api/template-consumer/catalog';
  const pending=$('template-input-form').onsubmit({preventDefault(){}});await waiting;
  if(config.mode==='edit'){$('template-input-goal').value='编辑后的新目标';$('template-input-goal').emit('input');}else{$('token').value=config.other_token;$('token').emit('input');if(config.mode==='aba'){$('token').value=config.token;$('token').emit('input');}}
  release();await pending;check(!calls.some(c=>c.method==='POST'),'late preflight cannot submit edited or different identity input');check(!p.run('tiBusy'),'old finally does not retain busy ticket');if(['token','aba'].includes(config.mode))check($('template-input-need').value===''&&p.run('tiCatalog')===null,'identity change erases private inputs');
 }else{
  if(['lost','denied'].includes(config.mode))transport.dropPath='/api/template-consumer/instances';
  await $('template-input-form').onsubmit({preventDefault(){}});
  if(config.mode==='pin'){check(!calls.some(c=>c.method==='POST'),'changed source pin requires a new read and confirmation');check(p.run('tiCatalog')===null,'stale catalog is invalidated');}
  else{
   if(['lost','denied'].includes(config.mode)){check(p.run('tiUnresolved()'),'lost reply retains original request');check(calls.filter(c=>c.method==='POST').length===1,'no automatic resend');const count=calls.length;if(config.mode==='denied')await control('revoke');await $('template-input-recover').onclick();check(calls.slice(count).every(c=>c.method==='GET'),'explicit recovery uses only GET');}
   if(config.mode==='denied'){check(p.run('tiUnresolved()')&&p.run('tiView')===null,'403 preserves opaque original key and erases private view');check($('template-input-need').value===''&&$('template-input-form').hidden,'403 clears private materials');}
   else {check(!p.run('tiUnresolved()')&&p.run('tiView.run_id')!==null,'exact original creation observed');check(calls.filter(c=>c.method==='POST').length===1,'one create only');
   if(config.mode==='success'){check($('template-input-resume').disabled,'queued Run cannot save materials');await control('worker');await $('template-input-read').onclick();check(!$('template-input-resume').disabled,'real worker success permits separate confirmation');$('template-input-material-confirm').checked=true;await $('template-input-resume').onclick();check(p.run('tiView.state')==='PLAN_CONFIRMATION_REQUIRED','new materials stop before manual plan: '+$('template-input-status').textContent+' feedback '+$('page-feedback').textContent+' leases '+p.run('JSON.stringify([...entryWriteRequests.values()].map(x=>({key:x.key,kind:x.kind,stage:x.stage})))'));check(!p.run('tiUnresolved()'),'readback verifies exact material request');check(p.run('tiView.plan_id')===null,'no plan adoption');}
   }
   check(!calls.some(c=>/\/adopt|\/planning|\/commands/.test(c.path)),'no automatic planning review adopt or P1-P5');
  }
 }
 check(Object.keys(storage).length===0,'no raw input/session browser storage');
 }
 console.log(JSON.stringify({checks,mode:config.mode,calls,real_browser:false,ordinary_formal_success:false}));readline.close();
})().catch(e=>{console.error(JSON.stringify({error:e.stack,diagnostics}));process.exitCode=1;readline.close();});
