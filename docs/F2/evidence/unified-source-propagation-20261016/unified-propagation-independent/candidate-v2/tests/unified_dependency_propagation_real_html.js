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
      if (body.dependency_propagation) call.dependency_propagation_sha256=body.dependency_propagation.sha256;
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

// Flow body will be bound to the integrated shipped UI IDs before execution.
// No DTO stubs, fetched-page substitutions or product function replacements.
(async()=>{
 const config=await initialized,storage={},calls=[],transport={};diagnostics={calls};
 let p=page(config,storage,calls,transport),{$,run}=p;
 const load=async row=>{await run(`loadPreparation(${JSON.stringify(row.preparation_id)},{role:'enterprise_operator'})`);await $('opp-read').onclick();};
 const factButton=id=>{const button=run("document.querySelectorAll('[data-opp-dependency-preview]')").find(e=>e.dataset?.oppDependencyPreview===id);check(!!button&&typeof button.onclick==='function','shipped explicit unified preview button');return button;};
 const preview=async id=>{await factButton(id).onclick();check(!!run('opportunityPlanView'),$('opp-plan-status').textContent);};
 const output=()=>console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_UNIFIED_PROPAGATION_ACTUAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,calls,real_browser:'NOT_RUN',fake_dto:false}));
 await load(config.A);
 if(['current_403','late_403'].includes(config.mode)){
  await preview(config.card);
  if(config.mode==='current_403'){
   transport.revokeBeforeRead=true;await factButton(config.card).onclick();
   check(calls.at(-1).status===403,'actual original capability READ denial GET403');
   check(run('opportunityPlanView')===null&&run('servicePlanView')===null,'current denial clears original private plan and preview');
  }else{
   transport.revokeBeforeRead=true;transport.ready=new Promise(resolve=>transport.held=resolve);transport.release=new Promise(resolve=>transport.resume=resolve);transport.hold=c=>c.path.includes('dependency_scope=BOUNDED_MULTI_SOURCE_V1');
   const old=factButton(config.card).onclick();check((await transport.ready).status===403,'held original actual403');
   $('token').value='SYNTHETIC_UNIFIED_OTHER_IDENTITY';$('token').emit('input');$('token').value=config.token;$('token').emit('input');
   await control('restore');await load(config.B);await preview(config.cardB);const now=run('opportunityPlanView');
   transport.resume();await old;
   check(run('opportunityPlanView')===now&&now.preparation_id===config.B.preparation_id,'late403 cannot erase later Case after identityABA');
  }
  check(calls.every(c=>c.method==='GET'),'authority flows contain reads only');output();process.exit(0);
 }
 $('opp-generation').value='1';$('opp-kind').value='LOCAL_CASE_DATA';$('opp-catalog').value=String(run('oppView.current_basis.catalog[0].version'));
 $('opp-title').value='SYNTHETIC actual mixed actual source changed';$('opp-note').value='Unverified hint provides no facts or authority';$('opp-purpose').checked=true;$('opp-reason').value='SYNTHETIC explicit original import';
 await $('opp-import').onsubmit({preventDefault(){}});const card=run('oppView.cards.find(c=>c.is_latest_generation).id');
 await control('change_fact');await $('opp-read').onclick();$('opp-reason').value='SYNTHETIC original explicit actual-source refresh';await $('opp-refresh').onclick();
 const button=run("document.querySelectorAll('[data-opp-dependency-preview]')").find(e=>e.dataset?.oppDependencyPreview===card);
 check(!!button&&typeof button.onclick==='function','shipped original opportunity card offers explicit unified preview');await button.onclick();
 check(run('opportunityPlanView.scope')==='BOUNDED_MULTI_SOURCE_REVISION_PREVIEW','new explicit preview scope');
 check(run('opportunityPlanView.dependency_propagation.schema')===2,'unified dependency propagation schema2');
 check(run('opportunityPlanView.affected.length')===5&&run('opportunityPlanView.preserved.length')===0,'actual mixed actual source change requires original all-five verification');
 const display=textOf($('opp-plan-impact'));check(display.length>0&&!display.includes('PRIVATE_FACT_EXCERPT_')&&!display.includes('PRIVATE_REGION_SELECTED'),'unified projection omits raw private source values');
 $('service-plan-reason').value='SYNTHETIC explicit original plan adoption with exact unified source propagation';
 const before=calls.filter(c=>c.method==='POST').length;await $('opp-plan-adopt').onclick();check(calls.filter(c=>c.method==='POST').length===before,'unchecked original confirmation sends no POST');
 await preview(card);$('service-plan-reason').value='SYNTHETIC explicit original exact unified source propagation';$('opp-plan-confirm').checked=true;await control('before_adopt');if(config.mode==='lost_ack')transport.dropPath='/service-case-plan';await $('opp-plan-adopt').onclick();
 if(config.mode==='lost_ack'){
  check(Object.keys(storage).some(k=>k.startsWith('parkweave.service-plan-recovery.v1.')),'lost response retains original opaque plan recovery handle');
  for(const [k,v] of Object.entries(storage))if(k.startsWith('parkweave.service-plan-recovery.v1.')){const handle=JSON.parse(v);check(!('dependency_propagation' in handle)&&!('reason' in handle)&&!('body' in handle),'local recovery handle excludes body and provenance');}
  const n=calls.length;p=page(config,storage,calls,transport);({$,run}=p);await run(`loadPreparation(${JSON.stringify(config.A.preparation_id)},{role:'enterprise_operator'})`);await $('service-plan-prepare').onclick();await $('service-plan-retry').onclick();
  check(calls.slice(n).every(c=>c.method==='GET'),'cold original plan recovery only GETs');
  const originalAdopt=calls.find(c=>c.method==='POST'&&c.path.endsWith('/service-case-plan'));
  const recovered=calls.slice(n).filter(c=>c.path.endsWith('/service-case-plan/command-recovery')&&typeof c.request_key==='string');
  check(recovered.length>0&&recovered.every(c=>c.method==='GET'&&c.status===200&&c.request_key===originalAdopt.request_key),'actual cold GET uses exact original Idempotency-Key header');
  check(run('servicePlanRecoveryHandle?.observed')===true,'original recovery is observed and still requires explicit release');
  await $('service-plan-release').onclick();check(run('servicePlanRecoveryHandle')===null,'user explicitly ends original read-only recovery before later VERIFY');
  check(calls.slice(n).every(c=>c.method==='GET'),'explicit recovery release only reads current original plan');
 }
 const sent=calls.filter(c=>c.method==='POST'&&c.path.endsWith('/service-case-plan')).at(-1);check(sent?.status===201,'original ADOPT must actually commit: '+$('opp-plan-status').textContent+' '+$('service-plan-error').textContent);await control('after_adopt');
 for(const adapter of ['P1','P2','P3','P4','P5']){
  await control({P1:'review_material',P2:'relink_resources',P3:'reoffer_accept',P4:'new_report_ack',P5:'revalidate_local'}[adapter]);
  await run(`loadServiceCasePlan(${JSON.stringify(config.A.preparation_id)})`);const id=run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).id`);
  $('service-plan-reason').value='SYNTHETIC actual original '+adapter+' VERIFY';await run(`servicePlanWrite('VERIFY',${JSON.stringify(id)})`);
  check(run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).state`)==='VERIFIED',$('service-plan-error').textContent);
 }
 await $('goal-results-read').onclick();check(run('goalResultView.results.length')===6&&run('goalResultView.state')==='LOCAL_OUTPUTS_VERIFIED','all actual original six local goal outputs');
 await $('case-worklist-read').onclick();const seen=[];for(let i=0;i<4;i++){const q=[...calls].reverse().find(c=>c.worklist_items);check(!!q,'actual original worklist request');seen.push(...q.worklist_items);if($('case-worklist-next').hidden)break;await $('case-worklist-next').onclick();}
 check(seen.some(r=>r.case_id===config.A.case_id)&&seen.every(r=>r.evidence_verified===false&&r.case_goal_completed===false),'current goal/worklist evidence remains recorded local state');
 await control('final_evidence');output();process.exit(0);
})().catch(error=>{console.error(JSON.stringify({message:error.message,stack:error.stack,diagnostics}));process.exit(1);});
