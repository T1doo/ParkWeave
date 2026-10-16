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
    this.hidden = true; this.disabled = false; this.checked = false; this.listeners = {};
    const named = {}; this.elements = new Proxy([], {get: (a, key) => key in a ? a[key] : (named[key] ??= new Element('input'))});
  }
  append(...values) { this.children.push(...values); }
  prepend(...values) { this.children.unshift(...values); }
  replaceChildren(...values) { this.children = values; this.textContent = ''; }
  get options() { return this.children.filter(e => e.tagName === 'option'); }
  get selectedOptions() { return this.options.filter(e => e.value === this.value); }
  get firstChild() { return this.children[0]; }
  get firstElementChild() { return this.children[0]; }
  addEventListener(name, handler) { (this.listeners[name] ??= []).push(handler); }
  emit(name) { this['on' + name]?.({target: this}); for (const handler of this.listeners[name] || []) handler({target: this}); }
  reset() {} setAttribute() {} removeAttribute() {} closest() { return null; } querySelectorAll() { return []; }
  scrollIntoView() {} focus() {} select() {} remove() {} click() { if(this.disabled)return;return this.onclick?.(); }
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
      if (transport.revokeBeforeRead && (options.method || 'GET') === 'GET' && path.endsWith('/plan-approval')) {
        transport.revokeBeforeRead = false;
        await control('revoke');
      }
      const response = await fetch(config.base + path, options), body = await response.json();
      const call = {method: options.method || 'GET', path, status: response.status};
      if (options.body) call.body = JSON.parse(options.body);
      if (options.headers?.['Idempotency-Key']) call.request_key = options.headers['Idempotency-Key'];
      if (call.method==='POST'&&path.endsWith('/resource-delivery')&&response.status===201)call.actual_delivery_receipt=body.receipt;
      if (body.source_impact) call.graph_sha256 = body.source_impact.sha256;
      call.response_scope = body.scope; call.response_schema = body.schema;if(path.endsWith('/goal-results'))call.actual_goal_results=body;
      if (body.dependency_propagation) call.dependency_propagation_sha256=body.dependency_propagation.sha256;
      if (body.scope==='CURRENT_OWNER_SYNTHETIC_CASE_WORKLIST') call.worklist_items=body.items.map(r=>({case_id:r.case_id,preparation_id:r.preparation_id,receipt_step_id:r.receipt_step_id,evidence_verified:r.evidence_verified,case_goal_completed:r.case_goal_completed}));
      calls.push(call);console.log(JSON.stringify({trace:call}));
      if (response.status === 403 && (options.method || 'GET') === 'GET' && path.endsWith('/plan-approval')) {
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
 const config=await initialized,storage={},calls=[],transport={},contextEvents=[];diagnostics={calls};let p=page(config,storage,calls,transport),{$,run}=p;
 const output=()=>console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_P3_NEVER_ACCEPTED_CLOSURE_ACTUAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,calls,context_events:contextEvents,real_browser:'NOT_RUN',fake_dto:false,python_prerequisites:['birth-tracked six-goal V4 original services, old P1/P2 and original never-accepted closed P3 history','title-only compatible publication and original withdrawal','catalog-change original REOPEN REVIEW CONFIRM','whole new plan ADOPT','new P1 VERIFY','new dispatch REOFFER ACCEPT','new receipt SUBMIT ACK','P5 REVALIDATE']}));
 const resource=async(row,ids=[])=>{await $('resource-catalog').onclick();await $('resource-mine').onclick();for(const id of ids){const box=run("document.querySelectorAll('[data-combination-hold]')").find(e=>e.dataset.combinationHold===id);check(!!box,'actual held member checkbox');box.checked=true;box.onchange();}$('delivery-case').value=row.preparation_id;$('delivery-case').emit('input');};
 if(['current_403','late_403'].includes(config.mode)){
  await resource(config.A);await $('plan-approval-read').onclick();check(!!run('planApprovalView'),'actual original history read');transport.revokeBeforeRead=true;
  if(config.mode==='current_403'){await $('plan-approval-read').onclick();check(calls.at(-1).status===403,'actual current original read403');check(run('planApprovalView')===null&&run('planApprovalSelected')===null&&run('deliveryQuote')===null,'current denial clears private view');}
  else{transport.ready=new Promise(resolve=>transport.held=resolve);transport.release=new Promise(resolve=>transport.resume=resolve);transport.hold=c=>c.path.endsWith('/plan-approval');const old=$('plan-approval-read').onclick();check((await transport.ready).status===403,'held actual old403');$('delivery-plan-replacement').checked=true;$('delivery-plan-replacement').emit('change');$('delivery-plan-replacement').checked=false;$('delivery-plan-replacement').emit('change');contextEvents.push('MODE_FIRST_REPLACEMENT_FIRST');$('delivery-case').value=config.B.preparation_id;$('delivery-case').emit('input');$('delivery-case').value=config.A.preparation_id;$('delivery-case').emit('input');contextEvents.push('CASE_A_B_A');$('token').value='SYNTHETIC_REPLACEMENT_OTHER';$('token').emit('input');$('token').value=config.token;$('token').emit('input');contextEvents.push('IDENTITY_A_B_A');await control('restore');await resource(config.B);await $('plan-approval-read').onclick();const now=run('planApprovalView');check(now?.preparation_id===config.B.preparation_id,'new Case actual history view');transport.resume();await old;check(run('planApprovalView')===now,'late old403 preserves new Case');}
  check(calls.every(c=>c.method==='GET'),'authority modes read only');output();process.exit(0);
 }
 await resource(config.A,config.holds);check($('delivery-plan-replacement').disabled===false,'explicit replacement available');check(!$('delivery-plan-replacement').checked,'no implicit replacement consent');$('delivery-plan-replacement').checked=true;$('delivery-plan-replacement').emit('change');check(!$('delivery-p3-closure').checked,'no implicit frontier consent');check(!$('delivery-p3-closure').disabled,'explicit tracked frontier available');$('delivery-p3-closure').checked=true;$('delivery-p3-closure').emit('change');await $('plan-approval-read').onclick();await $('delivery-preview').onclick();check(!!run('deliveryQuote'),'actual replacement quote');check(run('deliveryQuote.view.replacement_frontier_profile')==='P3_NEVER_ACCEPTED_CLOSED_V1','explicit frontier profile echoed');check(run('deliveryQuote.view.context.plan_replacement.compatibility.schema')===3,'independent versioned compatibility');check(run('deliveryQuote.view.expected_link_revision')===1,'old association bound');check(run('deliveryQuote.view.expected_previous_plan_id')===config.old_plan_id,'actual old plan bound');check(run('deliveryQuote.view.context.plan_id')===config.new_plan_id,'actual new plan bound');
 const n=calls.filter(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery')).length;check($('delivery-confirm').disabled,'unapproved commit disabled');await $('delivery-confirm').click();check(calls.filter(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery')).length===n,'unapproved no resource POST');await $('plan-approval-propose').onclick();check(run('planApprovalSelected.state')==='PROPOSED','explicit original proposal');check(run('planApprovalSelected.purpose')==='CASE_RESOURCE_PLAN_REPLACEMENT','distinct exact purpose');await $('plan-approval-approve').onclick();check(run('planApprovalSelected.current_available')===true,'actual explicit APPROVE');await control('before_commit');if(config.mode==='lost_ack')transport.dropPath='/resource-delivery';await $('delivery-confirm').onclick();
 if(config.mode==='lost_ack'){check(Object.keys(storage).some(k=>k.startsWith('parkweave.case-resource-delivery.v1.')),'lost committed response keeps handle');for(const [key,value] of Object.entries(storage)){check(!value.includes(config.token),'no token persisted');if(key.startsWith('parkweave.case-resource-delivery.v1.'))check(Object.keys(JSON.parse(value)).sort().join(',')==='actor,id,key','opaque original handle only');}const n=calls.length;p=page(config,storage,calls,transport);({$,run}=p);await resource(config.A);await $('delivery-recover').onclick();check(calls.slice(n).every(c=>c.method==='GET'),'cold original recovery onlyGET');const post=calls.find(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery'));check(calls.slice(n).some(c=>c.path.endsWith('/resource-delivery/recovery/'+post.request_key)&&c.status===200),'cold GET original exact committed key');}
 check(calls.filter(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery')&&c.status===201).length===1,'one actual replacement COMMIT');await control('after_commit');await run(`loadPreparation(${JSON.stringify(config.A.preparation_id)},{role:'enterprise_operator'})`);
 for(const adapter of ['P2','P3','P4','P5']){if(adapter!=='P2')await control({P3:'reoffer_accept',P4:'new_report_ack',P5:'revalidate_local'}[adapter]);await run(`loadServiceCasePlan(${JSON.stringify(config.A.preparation_id)})`);const step=run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).id`);$('service-plan-reason').value='SYNTHETIC original replacement '+adapter+' VERIFY';await run(`servicePlanWrite('VERIFY',${JSON.stringify(step)})`);check(run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).state`)==='VERIFIED','actual original '+adapter+' VERIFIED');}
 await $('goal-results-read').onclick();check(run('goalResultView.results.length')===6&&run('goalResultView.state')==='LOCAL_OUTPUTS_VERIFIED','six original local outputs');await $('case-worklist-read').onclick();for(let i=0;i<4&&!$('case-worklist-next').hidden;i++)await $('case-worklist-next').onclick();check(calls.some(c=>c.worklist_items?.some(r=>r.case_id===config.A.case_id&&r.case_goal_completed===false)),'actual Case in worklist');const committed=calls.find(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery')&&c.status===201);const recovered=await run(`apiCall(${JSON.stringify('/api/preparations/'+config.A.preparation_id+'/resource-delivery/recovery/'+committed.request_key)})`);assert.deepStrictEqual(JSON.parse(JSON.stringify(recovered.receipt)),JSON.parse(JSON.stringify(committed.actual_delivery_receipt)));checks++;check(recovered.independent_check.status==='CURRENT','current resource survives later business effects');await control('final_evidence');output();process.exit(0);
})().catch(error=>{console.error(JSON.stringify({message:error.message,stack:error.stack,diagnostics}));process.exit(1);});
