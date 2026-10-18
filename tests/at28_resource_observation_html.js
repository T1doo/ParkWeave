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
  append(...values) { for(const v of values)if(v&&typeof v==='object')v.parentElement=this; this.children.push(...values); }
  prepend(...values) {for(const v of values)if(v&&typeof v==='object')v.parentElement=this;this.children.unshift(...values);}
  replaceWith(value) {const p=this.parentElement;if(p){const i=p.children.indexOf(this);p.children[i]=value;value.parentElement=p;}}
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
      if(path.endsWith('/preview')){transport.preview=JSON.parse(JSON.stringify(body));if(config.mode==='missing-source')delete body.source;if(config.mode==='invalid-observation-time')body.server_time='not-an-observation';}
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
(async()=>{const config=await initialized,calls=[],storage={},transport={};diagnostics={calls};const p=page(config,storage,calls,transport),$=p.$;
 await $('resource-catalog').onclick();$('resource-select').value=config.resource_id;
 check(textOf($('resource-catalog-view')).includes('本次目录读取时间'),'catalog observation time is visible');
 check(textOf($('resource-catalog-view')).includes('ENG018-reviewed-resource-fixture'),'original catalog source visible');
 $('resource-quantity').value='1';$('resource-ttl').value='120';$('resource-purpose').value='SYNTHETIC explicit AT28 local request';
 await control('advance');await $('resource-preview').onclick();
 check(transport.preview.source.id==='AT28-current-resource-source'&&transport.preview.resource_revision===2,'actual current backend source is version2');
 check(!calls.some(c=>/\/holds$|\/confirm$/.test(c.path)),'preview sends no hold or confirmation');
 if(config.mode==='current-source'){
  const text=textOf($('resource-preview-result'));
  for(const expected of ['AT28-current-resource-source','资源版本 2','/ v2','SYNTHETIC current v2 <note>& source',transport.preview.server_time,'UNKNOWN','本地须另行明确占位及确认'])check(text.includes(expected),'current source/time/boundary '+expected);
  check(textOf($('resource-catalog-view')).includes('ENG018-reviewed-resource-fixture'),'prior catalog remains separate');
  check(!$('resource-hold').disabled,'verified local current observation permits explicit hold');
  await $('resource-form').onsubmit({preventDefault(){}});
  const card=$('resource-current').children[0];check(card?.dataset.state==='HELD','explicit original hold observed');
  const button=card.children.find(e=>e.dataset?.resourceAction==='confirm');check(!!button,'separate local confirm remains explicit');await button.onclick();
  check($('resource-current').children[0].dataset.state==='CONFIRMED','original local confirmation observed');
  check(textOf($('resource-current')).includes('真实预约未确认'),'local confirmation does not assert external availability');
  check(calls.filter(c=>/\/holds$|\/confirm$/.test(c.path)).length===2,'exactly explicit hold and confirm');
 }else{
  check($('resource-hold').disabled&&p.run('resourcePreview')===null,'unverified source or observation cannot become usable hold preview');
  check(textOf($('resource-error')).includes('尚未核实'),'precise missing observation notice');
  check(!calls.some(c=>/\/holds$|\/confirm$/.test(c.path)),'unverified observation sends no business command');
 }
 check(Object.keys(storage).length===0,'no session/source browser persistence added');
 console.log(JSON.stringify({checks,mode:config.mode,calls,preview:transport.preview,real_browser:false,external_resource_availability:'UNKNOWN'}));readline.close();
})().catch(e=>{console.error(JSON.stringify({error:e.stack,diagnostics}));process.exitCode=1;readline.close();});
