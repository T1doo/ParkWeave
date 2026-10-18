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
 const config=await initialized,storage={},calls=[],transport={};diagnostics={calls};const {$,run,context}=page(config,storage,calls,transport);let preview_checks=0;
 const load=async()=>{await run(`loadPreparation(${JSON.stringify(config.A.preparation_id)},{role:'enterprise_operator'})`);await $('opp-read').onclick();};
 const button=kind=>{const key=kind==='typed'?'oppTypedPreview':'oppDependencyPreview',selector=kind==='typed'?'opp-typed-preview':'opp-dependency-preview';return run(`document.querySelectorAll('[data-${selector}]')`).find(e=>e.dataset[key]===config.card);};
 const preview=async()=>{const start=calls.length;check(!!button('typed'),'shipped readonly type graph button');await button('typed').onclick();check(!calls.slice(start).some(c=>/\/service-case-plan$/.test(c.path)),'new button avoids ordinary observation plan GET');check(run('opportunityPlanView')===null,'readonly projection has no adoption view');check($('opp-plan-write-controls').hidden&&$('opp-plan-adopt').disabled,'readonly mode hides and disables old adoption: '+$('service-plan-error').textContent+' '+$('opp-error').textContent);check(textOf($('opp-plan-impact')).includes('类型图版本只读比较'),$('service-plan-error').textContent+' '+$('opp-error').textContent);preview_checks++;};
 const hold=()=>{transport.ready=new Promise(resolve=>transport.held=resolve);transport.release=new Promise(resolve=>transport.resume=resolve);};
 await load();await button('legacy').onclick();check(run('opportunityPlanView')?.scope==='BOUNDED_MULTI_SOURCE_REVISION_PREVIEW','original unified preview still works');$('opp-plan-confirm').checked=true;run('opportunityPlanControls()');check(!run('opportunityPlanView.can_adopt'),'affected current lock still blocks original adoption');
 await control('snapshot');await preview();check($('opp-plan-confirm').checked===false,'new preview clears previous confirmation');check(Object.keys(storage).length===0,'new read stores no private DTO or authority');await control('assert_readonly');
 const display=textOf($('opp-plan-impact'));for(const label of ['确定影响：','不确定影响：','保留：','删除：','受影响锁冲突：P3','保留步骤的当前锁：P1','原核验与当前来源版本对照'])check(display.includes(label),label);
 if(config.mode==='positive'){
  // Rehashing is deliberately insufficient: test exact identity/authority/path/lock checks.
  context.probe=transport.lastPreview;context.probeContext=run('oppCtx(true)');
  const rejected=await run(`(async()=>{const mutations=[x=>x.binding.actor_ref='0'.repeat(64),x=>x.can_adopt=true,x=>x.before.scope.package_id='wrong-plan',x=>x.current_manual_locks=[],x=>x.impact.propagation_reasons[0].node_id='missing-node'];let count=0;for(const mutate of mutations){const v=JSON.parse(JSON.stringify(probe));mutate(v.typed_dependency_preview);const x=v.typed_dependency_preview;x.sha256=await coldDigest(Object.fromEntries(Object.entries(x).filter(([k])=>k!=='sha256')));try{await versionedDependencyPreviewCheck(v,probeContext);}catch(e){count++;}}return count;})()`);check(rejected===5,'self-consistent wrapper rehash cannot replace exact version/authority/lock/path proofs');
  const n=calls.length;await $('opp-plan-adopt').onclick();check(calls.length===n,'readonly result cannot send ADOPT');await control('assert_readonly');
 }else if(config.mode==='current_403'){
  transport.revokeBeforeRead=true;await button('typed').onclick();check(calls.at(-1).status===403,'actual current READ403');check(run('servicePlanView')===null&&run('opportunityPlanView')===null&&$('opp-plan-preview').hidden,'current403 clears private views');
 }else{
  hold();const matches=c=>c.path.includes('graph_preview=');
  if(config.mode==='late_403'){transport.revokeBeforeRead=true;transport.hold=matches;}
  else if(config.mode==='late_json')transport.jsonReject=matches;
  else if(config.mode==='late_transport')transport.fetchReject=matches;
  else if(config.mode==='hash_aba'){
   const original=context.crypto.subtle.digest.bind(context.crypto.subtle);let once=true;context.crypto={...context.crypto,randomUUID:context.crypto.randomUUID.bind(context.crypto),subtle:{digest:async(...args)=>{const value=await original(...args);if(once){once=false;transport.held({status:200});await transport.release;}return value;}}};
  }else transport.hold=matches;
  const old=button('typed').onclick();await transport.ready;$('token').value='SYNTHETIC_DIFFERENT_TOKEN';$('token').emit('input');$('token').value=config.token;$('token').emit('input');if(config.mode==='late_403')await control('restore');await load();await preview();const content=textOf($('opp-plan-impact')),generation=run('opportunityPlanGeneration');transport.resume();await old;check(run('opportunityPlanGeneration')===generation&&textOf($('opp-plan-impact'))===content&&!$('opp-plan-preview').hidden,'late result/failure/hash cannot erase newer view after identity ABA');
 }
 check(calls.every(c=>c.method==='GET'),'new flow makes reads only');console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_VERSIONED_GRAPH_ACTUAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,preview_checks,calls,real_browser:'NOT_RUN',positive_dto:'ACTUAL_HTTP',negative_dto_mutations:config.mode==='positive'?5:0}));process.exit(0);
})().catch(e=>{console.error(e.stack);console.error(JSON.stringify(diagnostics));process.exit(1);});
