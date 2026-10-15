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
      if (transport.revokeBeforeNote && (options.method || 'GET') === 'GET' && path.includes('/plan-source-conflicts')) {
        transport.revokeBeforeNote = false;
        await control('revoke');
      }
      const response = await fetch(config.base + path, options), body = await response.json();
      const call = {method: options.method || 'GET', path, status: response.status};
      if (options.body) call.body = JSON.parse(options.body);
      if (call.method === 'POST') call.request_key = options.headers['Idempotency-Key'];
      if (body.source_impact) call.graph_sha256 = body.source_impact.sha256;
      call.response_scope = body.scope; call.response_schema = body.schema;
      if (body.continuation) call.continuation = {scope:body.continuation.scope,schema:body.continuation.schema,coverage_known:body.continuation.coverage_known,coverage_satisfied:body.continuation.coverage_satisfied};
      calls.push(call);
      if (response.status === 403 && (options.method || 'GET') === 'GET' && path.includes('/plan-source-conflicts')) {
        await control('assert_denied_read_no_write');
      }
      if (transport.badUnknownRecovery && path.includes('/plan-source-conflicts/recovery/')) {
        transport.badUnknownRecovery = false;
        delete body.current;  // Explicit malformed client DTO negative, never a backend claim.
      }
      const rejectJson = transport.jsonReject?.(call); if (rejectJson) transport.jsonReject = null;
      const rejectFetch = transport.fetchReject?.(call); if (rejectFetch) transport.fetchReject = null;
      if (transport.hold?.(call)) { transport.hold = null; transport.held(call); await transport.release; }
      if (rejectFetch) {
        transport.held(call); await transport.release;
        throw Object.assign(Error('SYNTHETIC_CONTROLLED_LATE_TRANSPORT_REJECT'), {status:403});
      }
      if (transport.dropPath && call.method === 'POST' && path.endsWith(transport.dropPath)) {
        transport.dropPath = null; throw Error('SYNTHETIC_AT24_27_COMMITTED_RESPONSE_LOST');
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

(async () => {
  const config = await initialized, storage = {}, calls = [], transport = {};
  diagnostics = {calls};
  let p = page(config, storage, calls, transport), {$,run} = p;
  const load = async row => { await run(`loadPreparation(${JSON.stringify(row.preparation_id)}, {role:'enterprise_operator'})`); await $('opp-read').onclick(); };
  const read = async card => { if(card) { $('plan-source-conflict-card').value=card; $('plan-source-conflict-card').onchange(); } await $('plan-source-conflict-read').onclick(); check(!!run('planSourceConflictView'),$('plan-source-conflict-status').textContent); };
  const output = extra => console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_MANUAL_CONTINUATION_REAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,calls,real_browser:'NOT_RUN',negative_transport_fixture:false,storage_keys:Object.keys(storage),...extra}));
  await load(config.A);
  if(['current_403','late_403'].includes(config.mode)) {
    await read();
    if(config.mode==='current_403') {
      transport.revokeBeforeNote=true;await $('plan-source-conflict-read').onclick();
      check(calls.at(-1).status===403,'actual backend denies current note read');
      check(run('planSourceConflictView')===null && run('servicePlanView')===null,'current 403 clears the private view');
    } else {
      transport.revokeBeforeNote=true;
      transport.ready=new Promise(resolve=>transport.held=resolve);
      transport.release=new Promise(resolve=>transport.resume=resolve);
      transport.hold=c=>c.path.includes('/plan-source-conflicts');
      const old=$('plan-source-conflict-read').onclick();const held=await transport.ready;
      check(held.status===403,'late denial is an actual server 403');
      $('token').value='SYNTHETIC_OTHER_MANUAL_IDENTITY';$('token').emit('input');
      $('token').value=config.token;$('token').emit('input');await control('restore');
      await load(config.B);await read();const current=run('planSourceConflictView');
      transport.resume();await old;
      check(run('planSourceConflictView')===current && current.preparation_id===config.B.preparation_id,'late identity A-B-A denial cannot clear the later Case');
    }
    check(calls.every(c=>c.method==='GET'),'authorization read flows never POST');output({});process.exit(0);
  }
  for(const id of ['edit','continue','merge']) {
    const element=$('plan-source-conflict-'+id);
    check(element.tagName==='button' && typeof element.onclick==='function','full HTML supplies installed '+id+' button');
    check(element.onclick.toString().includes('entryReadAllowed'),'actual original wrapper protects '+id);
  }
  await read();
  $('plan-source-conflict-note').value=config.manual;
  $('plan-source-conflict-reason').value='SYNTHETIC explicit original manual note';
  const before=calls.filter(c=>c.method==='POST').length;
  await $('plan-source-conflict-edit').onclick();
  check(calls.filter(c=>c.method==='POST').length===before,'unchecked note confirmation does not POST');
  check(!Object.keys(storage).some(k=>k.startsWith('parkweave.plan-source-conflict.')),'unchecked action creates no phantom recovery handle');
  $('plan-source-conflict-confirm').checked=true;await $('plan-source-conflict-edit').onclick();
  check(run('planSourceConflictView.note.text')===config.manual,$('plan-source-conflict-status').textContent);
  const step=run("servicePlanView.steps.find(s=>s.adapter_id==='P1').id");
  $('service-plan-reason').value='SYNTHETIC explicit P1 lock';await run(`servicePlanWrite('LOCK',${JSON.stringify(step)})`);
  await $('opp-read').onclick();
  $('opp-generation').value='1';$('opp-kind').value='LOCAL_CASE_DATA';
  $('opp-catalog').value=String(run('oppView.current_basis.catalog[0].version'));
  $('opp-title').value='SYNTHETIC actual material revision';$('opp-note').value='SYNTHETIC hint is not evidence or permission';
  $('opp-purpose').checked=true;$('opp-reason').value='SYNTHETIC explicit manual import';
  await $('opp-import').onsubmit({preventDefault(){}});
  const card=run('oppView.cards.find(c=>c.is_latest_generation).id');
  await control('change_material');await $('opp-read').onclick();
  $('opp-reason').value='SYNTHETIC refresh current actual source';await $('opp-refresh').onclick();
  await read(card);
  check(run('planSourceConflictView.continuation.baseline.text')===config.baseline,'B is the actual captured historical material');
  check(run('planSourceConflictView.continuation.manual.text')===config.manual,'M preserves full current manual text');
  check(run('planSourceConflictView.continuation.incoming.text')===config.incoming,'S is the exact current server material');
  const rendered=textOf($('plan-source-conflict-result'));
  check(rendered.includes(config.baseline)&&rendered.includes(config.manual)&&rendered.includes(config.incoming),'original page displays all three actual text versions');
  check(run('planSourceConflictView.continuation.semantic_evaluated')===false,'line coverage never claims semantic obligation verification');
  const lockedPosts=calls.filter(c=>c.method==='POST').length;
  $('plan-source-conflict-confirm').checked=true;$('plan-source-conflict-reason').value='SYNTHETIC locked continue refuses';
  await $('plan-source-conflict-continue').onclick();
  check(calls.filter(c=>c.method==='POST').length===lockedPosts,'new continuation cannot bypass original P1 lock');
  if(config.mode==='defer_unknown') {
    $('plan-source-conflict-confirm').checked=true;$('plan-source-conflict-reason').value='SYNTHETIC explicit DEFER';
    await $('plan-source-conflict-defer').onclick();
    check(run('planSourceConflictView.state')==='DEFERRED','old defer stays pending');await control('assert_unresolved');
    await control('make_unknown');await read(card);
    check(!run('planSourceConflictView.continuation.can_keep_and_continue')&&!run('planSourceConflictView.continuation.can_merge'),'actual UNKNOWN refuses both new actions');
    const count=calls.filter(c=>c.method==='POST').length;
    $('plan-source-conflict-confirm').checked=true;await $('plan-source-conflict-continue').onclick();
    check(calls.filter(c=>c.method==='POST').length===count,'unknown continuation cannot POST');
    await control('assert_unresolved');output({unknown_actual_source:true});process.exit(0);
  }
  $('service-plan-reason').value='SYNTHETIC original explicit P1 UNLOCK';await run(`servicePlanWrite('UNLOCK',${JSON.stringify(step)})`);await read(card);
  let expected=config.manual,origin='MANUAL',action;
  if(config.mode==='accept') {
    action='accept';expected=config.incoming;origin='SOURCE';
  } else if(config.mode==='merge') {
    action='merge';expected=config.manual+'\n'+config.incoming;$('plan-source-conflict-note').value=expected;
  } else {
    check(!run('planSourceConflictView.continuation.coverage_satisfied'),'missing exact new condition prevents keeping original M');
    $('plan-source-conflict-confirm').checked=true;$('plan-source-conflict-reason').value='SYNTHETIC record old keep only';
    await $('plan-source-conflict-keep').onclick();await control('assert_unresolved');await read(card);
    expected=config.manual+'\n'+config.incoming;
    $('plan-source-conflict-note').value=expected;$('plan-source-conflict-reason').value='SYNTHETIC legal explicit append of actual new conditions';
    $('plan-source-conflict-confirm').checked=true;await $('plan-source-conflict-edit').onclick();
    check(run('planSourceConflictView.continuation.coverage_satisfied'),'legal manual edit includes every actual source line');
    action='continue';
  }
  $('plan-source-conflict-reason').value='SYNTHETIC explicit '+action+' decision';$('plan-source-conflict-confirm').checked=true;
  if(config.mode==='lost_choice')transport.dropPath='/plan-source-conflicts/commands';
  await $('plan-source-conflict-'+action).onclick();
  if(config.mode==='lost_choice') {
    check(Object.keys(storage).some(k=>k.startsWith('parkweave.plan-source-conflict.')),'lost committed continuation retains opaque original handle');
    const count=calls.length;p=page(config,storage,calls,transport);({$,run}=p);
    await run(`loadPreparation(${JSON.stringify(config.A.preparation_id)},{role:'enterprise_operator'})`);await $('plan-source-conflict-recover').onclick();
    check(calls.slice(count).every(c=>c.method==='GET'),'cold continuation recovery only GETs the original request key');
  }
  check(run('planSourceConflictView.note.text')===expected && run('planSourceConflictView.note.origin')===origin,$('plan-source-conflict-status').textContent);
  check(run('planSourceConflictView.state')===(origin==='SOURCE'?'ACCEPTED_AWAITING_RECHECK':'CONTINUED_AWAITING_RECHECK'),'decision is pending actual original recheck');
  await control('remember_decision');await $('opp-read').onclick();await run(`previewOpportunityPlan(${JSON.stringify(card)})`);
  check(run('opportunityPlanView.can_adopt'),$('opp-plan-status').textContent);
  check(run('opportunityPlanView.affected.length')===5 && run('opportunityPlanView.preserved.length')===0,'A material impact remains literal all five steps');
  $('service-plan-reason').value='SYNTHETIC original explicit same-plan source ADOPT';$('opp-plan-confirm').checked=true;await control('before_adopt');
  if(config.mode==='lost_adopt')transport.dropPath='/service-case-plan';
  await $('opp-plan-adopt').onclick();
  if(config.mode==='lost_adopt') {
    const count=calls.length;p=page(config,storage,calls,transport);({$,run}=p);
    await run(`loadServiceCasePlan(${JSON.stringify(config.A.preparation_id)})`);
    check(calls.slice(count).every(c=>c.method==='GET')&&run('servicePlanRecoveryHandle?.observed'),'cold original ADOPT recovers without a second POST');await $('service-plan-release').onclick();
  }
  await control('after_adopt');
  for(const adapter of ['P1','P2','P3','P4','P5']) {
    await control({P1:'review_material',P2:'relink_resources',P3:'reoffer_accept',P4:'new_report_ack',P5:'revalidate_local'}[adapter]);
    await run(`loadServiceCasePlan(${JSON.stringify(config.A.preparation_id)})`);
    const id=run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).id`);
    $('service-plan-reason').value='SYNTHETIC actual output '+adapter+' VERIFY';await run(`servicePlanWrite('VERIFY',${JSON.stringify(id)})`);
    check(run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).state`)==='VERIFIED',$('service-plan-error').textContent);
  }
  await $('goal-results-read').onclick();check(run('goalResultView.results.length')===6&&run('goalResultView.state')==='LOCAL_OUTPUTS_VERIFIED','all original six actual goal outputs are current');
  check(!run('goalResultView.case_goal_completed'),'local evidence never completes the business Case');
  await $('case-worklist-read').onclick();check($('case-worklist-items').children.length===2,'original worklist still contains both authorized Cases');
  await control('final_evidence');output({manual_preserved:origin==='MANUAL',actual_source_accept:origin==='SOURCE'});process.exit(0);
})().catch(error=>{console.error(JSON.stringify({message:error.message,stack:error.stack,diagnostics}));process.exit(1);});
