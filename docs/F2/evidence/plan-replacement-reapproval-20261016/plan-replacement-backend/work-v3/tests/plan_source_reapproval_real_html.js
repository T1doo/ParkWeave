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
      if (body.source_impact) call.graph_sha256 = body.source_impact.sha256;
      call.response_scope = body.scope; call.response_schema = body.schema;
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
 const config=await initialized,storage={},calls=[],transport={},contextEvents=[];diagnostics={calls};
 let p=page(config,storage,calls,transport),{$,run}=p;
 const output=()=>console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_PLAN_SOURCE_REAPPROVAL_ACTUAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,calls,context_events:contextEvents,real_browser:'NOT_RUN',fake_dto:false}));
 const load=async row=>{await run(`loadPreparation(${JSON.stringify(row.preparation_id)},{role:'enterprise_operator'})`);await $('opp-read').onclick();};
 const resource=async(row,ids=[])=>{await $('resource-catalog').onclick();await $('resource-mine').onclick();for(const id of ids){const box=run("document.querySelectorAll('[data-combination-hold]')").find(e=>e.dataset.combinationHold===id);check(!!box,'actual original held member checkbox');box.checked=true;box.onchange();}$('delivery-case').value=row.preparation_id;$('delivery-case').emit('input');};
 if(['current_403','late_403'].includes(config.mode)){
   await resource(config.A);await $('plan-approval-read').onclick();check(!!run('planApprovalView'),'original actual old approved history read');
   transport.revokeBeforeRead=true;
   if(config.mode==='current_403'){
     await $('plan-approval-read').onclick();check(calls.at(-1).status===403,'actual current original read403');
     check(run('planApprovalView')===null&&run('planApprovalSelected')===null&&run('deliveryQuote')===null,'current denial clears original private approval and quote');
   }else{
     transport.ready=new Promise(resolve=>transport.held=resolve);transport.release=new Promise(resolve=>transport.resume=resolve);transport.hold=c=>c.path.endsWith('/plan-approval');
     const old=$('plan-approval-read').onclick();check((await transport.ready).status===403,'held actual old403');
     $('delivery-reapproval').checked=true;$('delivery-reapproval').emit('change');contextEvents.push('MODE_FALSE_TO_TRUE');$('delivery-reapproval').checked=false;$('delivery-reapproval').emit('change');contextEvents.push('MODE_TRUE_TO_FALSE');
     $('delivery-case').value=config.B.preparation_id;$('delivery-case').emit('input');contextEvents.push('CASE_A_TO_B');$('delivery-case').value=config.A.preparation_id;$('delivery-case').emit('input');contextEvents.push('CASE_B_TO_A');
     $('token').value='SYNTHETIC_REAPPROVAL_OTHER';$('token').emit('input');$('token').value=config.token;$('token').emit('input');contextEvents.push('IDENTITY_A_B_A');
     await control('restore');await resource(config.B);await $('plan-approval-read').onclick();const now=run('planApprovalView');check(now?.preparation_id===config.B.preparation_id,'new Case actual original approval view');
     transport.resume();await old;check(run('planApprovalView')===now,'late403 afteridentityABA preservesnewCase');
   }
   check(calls.every(c=>c.method==='GET'),'authority modes have reads only');output();process.exit(0);
 }
 await load(config.A);
 $('opp-generation').value='1';$('opp-kind').value='LOCAL_CASE_DATA';$('opp-catalog').value=String(run('oppView.current_basis.catalog[0].version'));
 $('opp-title').value='SYNTHETIC actual source change needs new capacity approval';$('opp-note').value='Hint alone is no fact or authority';$('opp-purpose').checked=true;$('opp-reason').value='SYNTHETIC original explicit import';await $('opp-import').onsubmit({preventDefault(){}});
 const card=run('oppView.cards.find(c=>c.is_latest_generation).id');await control('change_sources');await $('opp-read').onclick();$('opp-reason').value='SYNTHETIC explicit actual source refresh';await $('opp-refresh').onclick();
 const preview=run("document.querySelectorAll('[data-opp-plan-preview]')").find(e=>e.dataset.oppPlanPreview===card);check(!!preview,'original source revision preview button');await preview.onclick();
 check(run('opportunityPlanView.can_adopt')===true,'actual source local revision admissible');check(run('opportunityPlanView.affected.length')===5,'literal all5 source invalidation');
 $('service-plan-reason').value='SYNTHETIC explicit original source ADOPT';$('opp-plan-confirm').checked=true;await $('opp-plan-adopt').onclick();check(calls.some(c=>c.method==='POST'&&c.path.endsWith('/service-case-plan')&&c.status===201),'actual original source ADOPT');
 await control('repair_material');await run(`loadServiceCasePlan(${JSON.stringify(config.A.preparation_id)})`);let step=run("servicePlanView.steps.find(s=>s.adapter_id==='P1').id");$('service-plan-reason').value='SYNTHETIC actual original P1 VERIFY';await run(`servicePlanWrite('VERIFY',${JSON.stringify(step)})`);check(run("servicePlanView.steps[0].state")==='VERIFIED','original P1 reverified before new approval');
 const hs=await control('fresh_holds');await resource(config.A,hs.holds);
 check($('delivery-reapproval').disabled===false,'explicit isolated source reapproval enabled');check(!$('delivery-reapproval').checked,'new mode needs explicit checkbox');
 $('delivery-reapproval').checked=true;$('delivery-reapproval').emit('change');await $('plan-approval-read').onclick();await $('delivery-preview').onclick();check(!!run('deliveryQuote'),'actual explicit reapproval quote');check(run('deliveryQuote.view.expected_link_revision')===1,'literal oldlink revision1 bound');
 const n=calls.filter(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery')).length;check($('delivery-confirm').disabled,'original unapproved commit control disabled');await $('delivery-confirm').click();check(calls.filter(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery')).length===n,'unapproved quote cannot commit resources');
 await $('plan-approval-propose').onclick();check(run('planApprovalSelected.state')==='PROPOSED','actual original proposal');check(run('planApprovalSelected.purpose')==='CASE_RESOURCE_REAPPROVAL','explicit bounded reapproval purpose');
 await $('plan-approval-approve').onclick();check(run('planApprovalSelected.current_available')===true,'actual original explicit APPROVE');
 await control('before_commit');if(config.mode==='lost_ack')transport.dropPath='/resource-delivery';await $('delivery-confirm').onclick();
 if(config.mode==='lost_ack'){
   check(Object.keys(storage).some(k=>k.startsWith('parkweave.case-resource-delivery.v1.')),'lost commit keeps original opaque handle');
   for(const [key,value] of Object.entries(storage)){check(!value.includes(config.token),'storage has no token');if(key.startsWith('parkweave.case-resource-delivery.v1.'))check(Object.keys(JSON.parse(value)).sort().join(',')==='actor,id,key','deliveryhandle excludes bodies sourcevalues and approvals');}
   const n=calls.length;p=page(config,storage,calls,transport);({$,run}=p);await resource(config.A);await $('delivery-recover').onclick();
   check(calls.slice(n).every(c=>c.method==='GET'),'cold original delivery recovery sends GET only');
   const post=calls.find(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery'));check(calls.slice(n).some(c=>c.path.endsWith('/resource-delivery/recovery/'+post.request_key)&&c.status===200),'cold GET exact original committed key');
 }
 check(calls.filter(c=>c.method==='POST'&&c.path.endsWith('/resource-delivery')&&c.status===201).length===1,'one actual resource reapproval COMMIT');await control('after_commit');
 await load(config.A);
 for(const adapter of ['P2','P3','P4','P5']){
   if(adapter!=='P2')await control({P3:'reoffer_accept',P4:'new_report_ack',P5:'revalidate_local'}[adapter]);
   await run(`loadServiceCasePlan(${JSON.stringify(config.A.preparation_id)})`);step=run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).id`);$('service-plan-reason').value='SYNTHETIC actual original '+adapter+' VERIFY';await run(`servicePlanWrite('VERIFY',${JSON.stringify(step)})`);check(run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).state`)==='VERIFIED','actual original '+adapter+' VERIFIED');
 }
 await $('goal-results-read').onclick();check(run('goalResultView.results.length')===6&&run('goalResultView.state')==='LOCAL_OUTPUTS_VERIFIED','all original six local outputs');await $('case-worklist-read').onclick();
 for(let i=0;i<4&&!$('case-worklist-next').hidden;i++)await $('case-worklist-next').onclick();
 check(calls.some(c=>c.worklist_items?.some(r=>r.case_id===config.A.case_id&&r.case_goal_completed===false)),'actual current Case in original worklist');await control('final_evidence');output();process.exit(0);
})().catch(error=>{console.error(JSON.stringify({message:error.message,stack:error.stack,diagnostics}));process.exit(1);});
