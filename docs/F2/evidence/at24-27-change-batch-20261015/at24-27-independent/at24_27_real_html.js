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
  let p = page(config, storage, calls, transport), {$, run} = p;
  const arm = predicate => { transport.hold = predicate; transport.ready = new Promise(resolve => transport.held = resolve); transport.release = new Promise(resolve => transport.resume = resolve); };
  const load = async row => { await run(`loadPreparation(${JSON.stringify(row.preparation_id)}, {role:'enterprise_operator'})`); await $('opp-read').onclick(); };
  const output = extra => console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_AT24_27_FIXED_TWO_CASE_REAL_HTTP_ASGI_OWNED_PG', mode:config.mode, checks, calls,
    negative_transport_fixture: ['late_json_reject','late_transport_reject','lost_note_bad_unknown'].includes(config.mode), real_browser:'NOT_RUN', storage_keys:Object.keys(storage), ...extra}));
  if (config.mode === 'at27') {
    $('instance').value = config.A.instance_id; await $('catalog').onclick();
    $('target').value = config.target.release_id; $('target').onchange?.();
    await $('check').onclick();
    check(run('inspection.check.classification') === 'BREAKING_REJECTED', $('error').textContent);
    check($('result').textContent.includes('破坏性升级拒绝'), 'original upgrade page explains the real current check');
    const choices = [...p.elements.values()].filter(e => e.dataset.choice);
    check(choices.find(e => e.dataset.choice === 'REQUEST_RECHECK').disabled, 'original disallowed recheck button is disabled');
    check($('apply').disabled && !run('applicationReady()'), 'original page cannot enable breaking apply');
    check(calls.every(c => c.method === 'GET'), 'opening and checking an incompatible definition never migrates either Case');
    output({at_results:[{at:'AT-27',result:'PASS',check_classification:'BREAKING_REJECTED',attempts:'Backend publication/recheck/full-apply/rollback denials are independently recorded by the Python HTTP tests.'}]}); process.exit(0);
  }
  await load(config.A);
  if (['current_403','late_aba','late_403','late_json_reject','late_transport_reject'].includes(config.mode)) {
    await $('plan-source-conflict-read').onclick();
    check(!!run('planSourceConflictView'), $('plan-source-conflict-status').textContent);
    if (config.mode === 'current_403') {
      transport.revokeBeforeNote = true; await $('plan-source-conflict-read').onclick();
      check(calls.at(-1).status === 403, 'current conflict read is denied by the actual backend');
      check(run('planSourceConflictView') === null && run('servicePlanView') === null, 'current denial clears private note and plan');
    } else {
      if (config.mode === 'late_403') transport.revokeBeforeNote = true;
      const negative = ['late_json_reject','late_transport_reject'].includes(config.mode);
      arm(negative ? () => false : c => c.path.includes('/plan-source-conflicts'));
      if (negative) transport[config.mode === 'late_json_reject' ? 'jsonReject' : 'fetchReject'] = c => c.path.includes('/plan-source-conflicts');
      const late = $('plan-source-conflict-read').onclick(); const held = await transport.ready;
      check(held.status === (config.mode === 'late_403' ? 403 : 200), 'late reply is the actual HTTP authorization result');
      $('token').value = 'SYNTHETIC_OTHER_AT24_IDENTITY'; $('token').emit('input');
      $('token').value = config.token; $('token').emit('input');
      if (config.mode === 'late_403') await control('restore');
      await load(config.B); await $('plan-source-conflict-read').onclick();
      const current = run('planSourceConflictView');
      check(current.preparation_id === config.B.preparation_id, 'new identity generation reads the other authorized Case');
      transport.resume(); await late;
      check(run('planSourceConflictView') === current, 'late old identity/Case reply cannot replace or clear the new note');
    }
    check(calls.every(c => c.method === 'GET'), 'note read authorization and ABA paths never issue a write'); output({}); process.exit(0);
  }
  const capacity = config.mode.startsWith('capacity');
  check($('plan-source-conflict-edit').tagName === 'button', 'the complete original HTML supplies the real button tag');
  check($('plan-source-conflict-edit').onclick.toString().includes('entryReadAllowed'), 'the installed original handler includes the write-flow wrapper');
  await $('plan-source-conflict-read').onclick();
  check(!!run('planSourceConflictView'), $('plan-source-conflict-status').textContent);
  $('plan-source-conflict-note').value = 'SYNTHETIC AT26 explicitly edited coordination note; preserve until my source choice';
  $('plan-source-conflict-reason').value = 'SYNTHETIC independent original manual note edit';
  const beforeEdit = calls.filter(c => c.method === 'POST').length;
  await $('plan-source-conflict-edit').onclick();
  check(calls.filter(c => c.method === 'POST').length === beforeEdit, 'unchecked manual-note confirmation cannot POST');
  $('plan-source-conflict-confirm').checked = true; await $('plan-source-conflict-edit').onclick();
  check(run('planSourceConflictView.note?.origin') === 'MANUAL', $('plan-source-conflict-status').textContent);
  const manualText = run('planSourceConflictView.note.text');
  const p1 = run("servicePlanView.steps.find(s=>s.adapter_id==='P1').id");
  $('service-plan-reason').value = 'SYNTHETIC independent original owner P1 lock'; await run(`servicePlanWrite('LOCK', ${JSON.stringify(p1)})`);
  check(run("servicePlanView.steps.find(s=>s.adapter_id==='P1').manually_locked"), $('service-plan-error').textContent);
  // Repeated and out-of-order imports use the original form and source family.
  const fillImport = generation => {
    $('opp-generation').value = String(generation); $('opp-kind').value = 'LOCAL_CASE_DATA';
    $('opp-catalog').value = String(run('oppView.current_basis.catalog[0].version'));
    $('opp-title').value = 'SYNTHETIC AT24 fixed two-Case source change'; $('opp-note').value = 'SYNTHETIC unverified opportunity hint cannot authorize';
    $('opp-purpose').checked = true; $('opp-reason').value = 'SYNTHETIC explicit original source import';
  };
  await $('opp-read').onclick(); fillImport(1); await $('opp-import').onsubmit({preventDefault(){}});
  check(run('oppView.cards.length') === 1, $('opp-error').textContent);
  const family = run('oppView.cards[0].entry.family_id'); $('opp-family').value = family;
  fillImport(1); await $('opp-import').onsubmit({preventDefault(){}});
  check(run('oppView.cards.length') === 1 && run('oppView.history.at(-1).outcome') === 'DUPLICATE', 'same version duplicate adds no second card');
  $('opp-family').value = family; fillImport(2); await $('opp-import').onsubmit({preventDefault(){}});
  check(run('oppView.cards.length') === 2, 'an explicit newer generation is a distinct current card');
  $('opp-family').value = family; fillImport(1); await $('opp-import').onsubmit({preventDefault(){}});
  const cardId = run('oppView.cards.find(c=>c.is_latest_generation).id');
  check(run('oppView.cards.length') === 2 && !run('oppView.cards.find(c=>c.entry.generation===1).is_latest_generation'), 'late existing older generation cannot overwrite the latest generation');
  await control(capacity ? 'change_capacity' : 'change_material');
  await $('opp-read').onclick();
  $('opp-reason').value = 'SYNTHETIC explicit source refresh after actual source change'; await $('opp-refresh').onclick();
  if (capacity) {
    await $('case-worklist-read').onclick();
    const anchor = $('case-worklist-items').children.flatMap(e=>e.children).find(e=>e.dataset?.caseSourceImpact === config.A.preparation_id);
    check(!!anchor, 'original worklist links the fixed anchor Case'); await anchor.onclick();
    $('case-shared-source-kind').value = 'OWNER_RESOURCE_QUERY_SET'; $('case-shared-source-kind').onchange();
    const reads = calls.length; await $('case-shared-source-read').onclick();
    check(calls.slice(reads).every(c=>c.method==='GET'), 'shared source reverse lookup is read only');
    check($('case-shared-source-items').children.length === 2, 'both current authorized fixed Cases are located');
    const target = $('case-shared-source-items').children.flatMap(e=>e.children).find(e=>e.dataset?.sharedSourceCase === config.A.case_id);
    check(!!target, 'explicit fixed A reverse row returns to the original graph'); await target.onclick(); await $('case-source-impact-open').onclick(); await $('opp-read').onclick();
  }
  await run(`previewOpportunityPlan(${JSON.stringify(cardId)})`);
  check(run('opportunityPlanView.affected.length') === (capacity ? 4 : 5), 'actual preview matches the frozen literal affected cardinality');
  if (!capacity) {
    $('plan-source-conflict-card').value = cardId; $('plan-source-conflict-card').onchange(); await $('plan-source-conflict-read').onclick();
    check(run('planSourceConflictView.state') === 'CONFLICT', $('plan-source-conflict-status').textContent);
    check(textOf($('plan-source-conflict-result')).includes(manualText) && textOf($('plan-source-conflict-result')).includes('AT25 actual revised material outline'), 'original page shows both manual note and actual source content');
    for (const [id,state] of [['keep','KEPT_MANUAL'],['defer','DEFERRED']]) {
      $('plan-source-conflict-reason').value = 'SYNTHETIC explicit original '+id; $('plan-source-conflict-confirm').checked = true;
      await $('plan-source-conflict-'+id).onclick();
      check(run('planSourceConflictView.state') === state && run('planSourceConflictView.note.text') === manualText, $('plan-source-conflict-status').textContent);
      check(run("servicePlanView.steps.find(s=>s.adapter_id==='P1').manually_locked"), 'keep/defer retains the original P1 lock');
      await control('assert_unresolved');
      // The original negative-adopt probe reads the live plan and may record
      // invalidation, so obtain a new exact note epoch before the next choice.
      $('plan-source-conflict-card').value = cardId; await $('plan-source-conflict-read').onclick();
    }
    const beforeAccept = calls.filter(c=>c.method==='POST').length;
    $('plan-source-conflict-reason').value = 'SYNTHETIC locked accept must refuse'; $('plan-source-conflict-confirm').checked = true;
    await $('plan-source-conflict-accept').onclick();
    check(calls.filter(c=>c.method==='POST').length === beforeAccept, 'affected lock cannot be bypassed by the source-choice button');
    $('service-plan-reason').value = 'SYNTHETIC explicit original owner UNLOCK'; await run(`servicePlanWrite('UNLOCK', ${JSON.stringify(p1)})`);
    check(!run("servicePlanView.steps.find(s=>s.adapter_id==='P1').manually_locked"), 'only the original explicit unlock removes the active lock');
    $('plan-source-conflict-card').value = cardId; await $('plan-source-conflict-read').onclick();
    $('plan-source-conflict-reason').value = 'SYNTHETIC explicitly accept the actual outline source'; $('plan-source-conflict-confirm').checked = true;
    if (config.mode.startsWith('lost_note')) transport.dropPath = '/plan-source-conflicts/commands';
    await $('plan-source-conflict-accept').onclick();
    if (config.mode.startsWith('lost_note')) {
      check(Object.keys(storage).some(k=>k.startsWith('parkweave.plan-source-conflict.')), 'actual committed lost note response preserves the opaque original handle');
      const unknown = ['lost_note_unknown','lost_note_bad_unknown'].includes(config.mode);
      if (unknown) await control('make_unknown');
      if (config.mode === 'lost_note_bad_unknown') transport.badUnknownRecovery = true;
      const count = calls.length; p = page(config, storage, calls, transport); ({$,run}=p);
      await run(`loadPreparation(${JSON.stringify(config.A.preparation_id)}, {role:'enterprise_operator'})`); await $('plan-source-conflict-recover').onclick();
      check(calls.slice(count).every(c=>c.method==='GET'), 'cold note recovery never reposts unknown original content');
      if (unknown) {
        if (config.mode === 'lost_note_bad_unknown') {
          check(Object.keys(storage).some(k=>k.startsWith('parkweave.plan-source-conflict.')), 'malformed UNKNOWN DTO cannot release the opaque original receipt handle');
          check(!run('planSourceConflictView'), 'missing current proof cannot display an invented UNKNOWN projection');
        } else {
          check(!Object.keys(storage).some(k=>k.startsWith('parkweave.plan-source-conflict.')), 'complete historical COMMITTED proof can release the original handle despite current UNKNOWN');
          check(run('planSourceConflictView.state') === 'UNKNOWN', $('plan-source-conflict-status').textContent);
        }
        await control('assert_unknown_history'); output({historical_commit_is_not_current_adoption:true}); process.exit(0);
      }
    }
    check(run('planSourceConflictView.state') === 'ACCEPTED_AWAITING_RECHECK', $('plan-source-conflict-status').textContent);
    check(run('planSourceConflictView.note.origin') === 'SOURCE' && run('planSourceConflictView.note.text') === run('planSourceConflictView.source.text'), 'accept uses exact database source content');
    await $('opp-read').onclick();
  }
  await run(`previewOpportunityPlan(${JSON.stringify(cardId)})`);
  check(run('opportunityPlanView.can_adopt'), $('opp-plan-status').textContent);
  $('service-plan-reason').value = 'SYNTHETIC explicit original local source ADOPT after independent choice';
  $('opp-plan-confirm').checked = true;
  await control('before_adopt');
  if (config.mode.endsWith('lost_adopt')) transport.dropPath = '/service-case-plan';
  await $('opp-plan-adopt').onclick();
  if (config.mode.endsWith('lost_adopt')) {
    const count = calls.length; p = page(config, storage, calls, transport); ({$,run}=p);
    await run(`loadServiceCasePlan(${JSON.stringify(config.A.preparation_id)})`);
    check(calls.slice(count).every(c=>c.method==='GET') && run('servicePlanRecoveryHandle?.observed'), 'cold original ADOPT recovery only GETs its original key');
    await $('service-plan-release').onclick();
  }
  await control('after_adopt');
  for (const adapter of capacity ? ['P2','P3','P4','P5'] : ['P1','P2','P3','P4','P5']) {
    if (!capacity) {
      await control({P1:'review_material',P2:'relink_resources',P3:'reoffer_accept',P4:'new_report_ack',P5:'revalidate_local'}[adapter]);
      await run(`loadServiceCasePlan(${JSON.stringify(config.A.preparation_id)})`);
    }
    const step = run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).id`);
    $('service-plan-reason').value = 'SYNTHETIC fixed batch actual output '+adapter+' VERIFY'; await run(`servicePlanWrite('VERIFY',${JSON.stringify(step)})`);
    check(run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).state`) === 'VERIFIED', $('service-plan-error').textContent);
  }
  await $('goal-results-read').onclick();
  check(run('goalResultView.results.length') === 6 && run('goalResultView.state') === 'LOCAL_OUTPUTS_VERIFIED', $('goal-results-error').textContent);
  check(!run('goalResultView.case_goal_completed'), 'local six-goal evidence does not complete the original business Case');
  await $('case-worklist-read').onclick(); check($('case-worklist-items').children.length === 2, 'the original worklist still contains both fixed Cases');
  if (capacity) {
    await load(config.B);
    $('opp-family').value = ''; fillImport(1); await $('opp-import').onsubmit({preventDefault(){}});
    const bCard = run('oppView.cards.find(c=>c.is_latest_generation).id');
    $('opp-reason').value = 'SYNTHETIC explicit second fixed Case manual source refresh'; await $('opp-refresh').onclick();
    await run(`previewOpportunityPlan(${JSON.stringify(bCard)})`);
    check(run('opportunityPlanView.affected.length') === 4 && run('opportunityPlanView.preserved.length') === 1, 'second fixed Case independently retains P1 and rechecks P2–P5');
    $('service-plan-reason').value = 'SYNTHETIC second fixed Case explicit original local ADOPT'; $('opp-plan-confirm').checked = true;
    await control('before_adopt_B'); await $('opp-plan-adopt').onclick(); await control('after_adopt_B');
    for (const adapter of ['P2','P3','P4','P5']) {
      const step = run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).id`);
      $('service-plan-reason').value = 'SYNTHETIC second fixed Case actual '+adapter+' VERIFY'; await run(`servicePlanWrite('VERIFY',${JSON.stringify(step)})`);
      check(run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).state`) === 'VERIFIED', $('service-plan-error').textContent);
    }
    await $('goal-results-read').onclick(); check(run('goalResultView.results.length') === 6 && run('goalResultView.state') === 'LOCAL_OUTPUTS_VERIFIED', 'second fixed Case also exposes all six actual local outputs');
  }
  await control('final_evidence');
  output({at_results:[{at:'AT-24',result:'PASS'},{at:'AT-25',result:'PASS'},{at:'AT-26',result:'PASS',content_choices:capacity?'unchanged anchor/no conflict':['KEEP_MANUAL','DEFER','ACCEPT_SOURCE']}]});
  process.exit(0);
})().catch(error => {console.error(error.stack);if(diagnostics)console.error(JSON.stringify(diagnostics));process.exit(1);});

