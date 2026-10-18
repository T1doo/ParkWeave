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
 const config=await initialized,storage={},calls=[],transport={};diagnostics={calls};let current=page(config,storage,calls,transport),{$,run,context}=current;
 const button=id=>run("document.querySelectorAll('[data-opp-typed-preview]')").find(b=>b.dataset.oppTypedPreview===id);
 const load=async row=>{await run(`loadPreparation(${JSON.stringify(row.preparation_id)},{role:'enterprise_operator'})`);await $('opp-read').onclick();};
 const show=async(row,card,resource)=>{const first=calls.length;await button(card).onclick();check(run('servicePlanView.preparation_id')===row.preparation_id,'exact Case bound');check(run('opportunityPlanView')===null&&$('opp-plan-write-controls').hidden&&$('opp-plan-adopt').disabled,'resource projection is readonly');check(calls.at(-1).path.endsWith('graph_preview='+(resource?'RESOURCE_QUERY_MEMBERS_V1':'VERSIONED_TYPED_GRAPH_V1')),'explicit resource or P1 mode');const text=textOf($('opp-plan-impact'));check(text.includes('类型图版本只读比较')&&text.includes('原资源查询集合与实际成员')===resource,'member display only actual P2');check(calls.slice(first).every(c=>c.method==='GET'&&!/\/service-case-plan$/.test(c.path)),'only readonly plan context and graph GET');return text;};
 await load(config.A);await control('snapshot');await show(config.A,config.card,true);await control('assert_readonly');
 transport.ready=new Promise(r=>transport.held=r);transport.release=new Promise(r=>transport.resume=r);transport.hold=c=>c.path.includes('graph_preview=RESOURCE_QUERY_MEMBERS_V1');const old=button(config.card).onclick();await transport.ready;
 await load(config.B);const content=await show(config.B,config.cardB,false),generation=run('opportunityPlanGeneration');transport.resume();await old;check(run('servicePlanView.preparation_id')===config.B.preparation_id&&run('opportunityPlanGeneration')===generation&&textOf($('opp-plan-impact'))===content,'late resource A cannot overwrite P1-only B');
 const cold=calls.length;current=page(config,storage,calls,transport);({$,run,context}=current);await load(config.A);await control('snapshot');await show(config.A,config.card,true);await control('assert_readonly');check(calls.slice(cold).every(c=>c.method==='GET'),'cold member page needs only GET');check(Object.keys(storage).length===0,'no graph/token/body storage');
 context.independentDTO=transport.lastPreview;const probes=await run(`(async()=>{const mutations=[
 x=>x.membership.added=[],x=>x.membership.changed=[x.membership.retained[0]],x=>x.before_basis.complete=false,
 x=>x.binding.plan_id='00000000-0000-0000-0000-000000000099',x=>x.authority_verified=true,
 x=>{const r=x.impact.propagation_reasons.find(r=>r.path.length);r.path[0].graph_sha256='0'.repeat(64);}
 ];let rejected=0;for(const mutate of mutations){const v=JSON.parse(JSON.stringify(independentDTO)),x=v.resource_dependency_preview;mutate(x);x.impact.sha256=await coldDigest(Object.fromEntries(Object.entries(x.impact).filter(([k])=>k!=='sha256')));x.sha256=await coldDigest(Object.fromEntries(Object.entries(x).filter(([k])=>k!=='sha256')));try{await resourceQueryPreviewCheck(v);}catch(e){rejected++;}}return {cases:mutations.length,rejected};})()`);check(probes.cases===6&&probes.rejected===6,'rehashed member claims/partial/cross-plan/authority/path rejected');
 transport.revokeBeforeRead=true;await button(config.card).onclick();check(calls.at(-1).status===403,'actual READ revoked');check(run('servicePlanView')===null&&$('opp-plan-preview').hidden,'current403 clears member view');
 check(calls.every(c=>c.method==='GET'&&!/\/service-case-plan$/.test(c.path)),'no POST or observing plan GET');console.log(JSON.stringify({scope:'INDEPENDENT_FULL_HTML_RESOURCE_MEMBER_TWO_CASE_ACTUAL_ASGI_PG',checks,probes,calls,cross_case_late200:true,p1_legacy_explicit:true,cold_page:true,current403:true,real_browser:'NOT_RUN',positive_dto:'ACTUAL_HTTP'}));process.exit(0);
})().catch(e=>{console.error(e.stack);console.error(JSON.stringify(diagnostics));process.exit(1);});
