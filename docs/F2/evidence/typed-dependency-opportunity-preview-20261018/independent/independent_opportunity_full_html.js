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
      if (body.dependency_propagation) call.dependency_propagation_sha256=body.dependency_propagation.sha256;if(body.typed_dependency_preview)transport.lastPreview=body;
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
 const typed=card=>run("document.querySelectorAll('[data-opp-typed-preview]')").find(b=>b.dataset.oppTypedPreview===card);
 const load=async row=>{await run(`loadPreparation(${JSON.stringify(row.preparation_id)},{role:'enterprise_operator'})`);await $('opp-read').onclick();};
 const show=async(card,row)=>{const start=calls.length;check(!!typed(card),'actual new button for exact card');await typed(card).onclick();check(run('opportunityPlanView')===null,'new graph never enters adoption view');check($('opp-plan-write-controls').hidden&&$('opp-plan-adopt').disabled&&!$('opp-plan-confirm').checked,'new graph disallows old adoption');check(textOf($('opp-plan-impact')).includes('类型图版本只读比较'),'actual graph displayed');check(run('servicePlanView.preparation_id')===row.preparation_id,'exact current Case');check(calls.slice(start).every(c=>c.method==='GET'&&!/\/service-case-plan$/.test(c.path)),'new click only recovery-context and graph reads');return textOf($('opp-plan-impact'));};
 const hold=()=>{transport.ready=new Promise(r=>transport.held=r);transport.release=new Promise(r=>transport.resume=r);};
 await load(config.A);await control('snapshot');await show(config.card,config.A);await control('assert_readonly');
 hold();transport.hold=c=>c.path.includes(config.A.preparation_id)&&c.path.includes('graph_preview=');const old200=typed(config.card).onclick();await transport.ready;
 await load(config.B);await control('snapshot');let shown=await show(config.cardB,config.B);await control('assert_readonly');let generation=run('opportunityPlanGeneration');transport.resume();await old200;
 check(run('servicePlanView.preparation_id')===config.B.preparation_id&&run('opportunityPlanGeneration')===generation&&textOf($('opp-plan-impact'))===shown,'late A200 cannot replace rendered B');
 await load(config.A);hold();transport.revokeBeforeRead=true;transport.hold=c=>c.path.includes('graph_preview=');const old403=typed(config.card).onclick();check((await transport.ready).status===403,'real denied A403 held');
 $('token').value='SYNTHETIC_UNRELATED_IDENTITY';$('token').emit('input');$('token').value=config.token;$('token').emit('input');await control('restore');await load(config.B);shown=await show(config.cardB,config.B);generation=run('opportunityPlanGeneration');transport.resume();await old403;
 check(run('servicePlanView.preparation_id')===config.B.preparation_id&&run('opportunityPlanGeneration')===generation&&textOf($('opp-plan-impact'))===shown&&!$('opp-plan-preview').hidden,'late denied A cannot erase B after identity ABA');
 await load(config.A);hold();transport.hold=c=>c.path.includes('graph_preview=');const draftOld=typed(config.card).onclick();await transport.ready;$('opp-reason').value='SYNTHETIC changed independent draft';$('opp-reason').emit('input');transport.resume();await draftOld;
 check(run('opportunityPlanView')===null&&$('opp-plan-preview').hidden,'changed draft rejects held response before display');
 const coldStart=calls.length;current=page(config,storage,calls,transport);({$,run,context}=current);await load(config.B);await control('snapshot');await show(config.cardB,config.B);await control('assert_readonly');check(calls.slice(coldStart).every(c=>c.method==='GET'),'cold full page reconstructs through reads only');check(Object.keys(storage).length===0,'no token, graph or body persisted');
 context.independentDTO=transport.lastPreview;context.independentContext=run('oppCtx(true)');
 const probes=await run(`(async()=>{const cases=[
  v=>v.typed_dependency_preview.extra='not-contract',
  v=>v.typed_dependency_preview.binding.preparation_id='00000000-0000-4000-8000-000000000000',
  v=>v.typed_dependency_preview.authority_verified=true,
  v=>v.typed_dependency_preview.current_manual_locks=[{node_id:v.typed_dependency_preview.current.nodes[0].id,event_id:'00000000-0000-4000-8000-000000000000',source_sha256:'a'.repeat(64)}],
  v=>{const x=v.typed_dependency_preview;x.before.nodes.reverse();},
  v=>{v.typed_dependency_preview.impact.propagation_reasons.pop();},
  v=>{const r=v.typed_dependency_preview.impact.propagation_reasons.find(r=>r.path.length);r.path[0].graph_sha256='0'.repeat(64);}
 ];let rejected=0;for(const mutate of cases){const v=JSON.parse(JSON.stringify(independentDTO));mutate(v);const x=v.typed_dependency_preview;x.impact.sha256=await coldDigest(Object.fromEntries(Object.entries(x.impact).filter(([k])=>k!=='sha256')));x.sha256=await coldDigest(Object.fromEntries(Object.entries(x).filter(([k])=>k!=='sha256')));try{opportunityPlanCheck(v,independentContext);await unifiedDependencyPropagationCheck(v);await versionedDependencyPreviewCheck(v,independentContext);}catch(e){rejected++;}}return {cases:cases.length,rejected};})()`);
 check(probes.cases===7&&probes.rejected===7,'independent exact DTO/path/shape probes reject after wrapper and impact rehash');
 check(calls.every(c=>c.method==='GET'),'entire independent readonly full-page flow sends no POST');check(calls.every(c=>!/\/service-case-plan$/.test(c.path)),'readonly full-page flow never invokes observing ordinary plan GET');
 console.log(JSON.stringify({scope:'INDEPENDENT_FULL_HTML_TYPED_GRAPH_TWO_CASE_ACTUAL_ASGI_PG',checks,probes,calls,real_browser:'NOT_RUN',positive_dto:'ACTUAL_HTTP',cross_case_late_200:true,cross_case_late_403_identity_ABA:true,cold_page:true,draft_guard:true}));process.exit(0);
})().catch(e=>{console.error(e.stack);console.error(JSON.stringify(diagnostics));process.exit(1);});
