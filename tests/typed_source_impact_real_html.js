// Entire shipped page, actual fetch to the owned HTTP/ASGI/PostgreSQL fixture.
// The small DOM surface below supplies browser mechanics, never product logic.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const readline = require('readline').createInterface({input: process.stdin});
let initialize;
const initialized = new Promise(resolve => initialize = resolve), replies = [];
readline.on('line', line => { const x = JSON.parse(line); if (initialize) { initialize(x); initialize = null; } else replies.shift()(x); });
const control = name => new Promise(resolve => { replies.push(resolve); console.log(JSON.stringify({control: name})); });
const code = fs.readFileSync('src/parkweave/web.html', 'utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
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
  get firstChild() { return this.children[0]; }
  get firstElementChild() { return this.children[0]; }
  addEventListener(name, handler) { (this.listeners[name] ??= []).push(handler); }
  emit(name) { this['on' + name]?.({target: this}); for (const handler of this.listeners[name] || []) handler({target: this}); }
  reset() {} setAttribute() {} removeAttribute() {} closest() { return null; } querySelectorAll() { return []; }
  scrollIntoView() {} focus() {} select() {} remove() {} click() { return this.onclick?.(); }
}
const textOf = element => element.textContent + element.children.map(e => typeof e === 'object' ? textOf(e) : e).join(' ');
function page(config, storage, calls, transport) {
  const elements = new Map(), $ = id => { if (!elements.has(id)) { const e = new Element(); e.id = id; elements.set(id, e); } return elements.get(id); };
  const walk = e => [e, ...e.children.filter(x => typeof x === 'object').flatMap(walk)];
  const query = selector => [...elements.values()].flatMap(walk).filter(e => selector.split(',').some(s => {
    if (['button', 'form'].includes(s)) return e.tagName === s;
    const m = s.match(/^\[data-([\w-]+)\]$/); return m && Object.hasOwn(e.dataset, m[1].replace(/-([a-z])/g, (_, c) => c.toUpperCase()));
  }));
  const localStorage = new Proxy({getItem: k => storage[k] ?? null, setItem: (k, v) => storage[k] = v, removeItem: k => delete storage[k]}, {ownKeys: () => Object.keys(storage), getOwnPropertyDescriptor: () => ({enumerable: true, configurable: true})});
  const context = vm.createContext({console, Date, JSON, Map, Set, WeakMap, Number, String, Error, TextEncoder, URL, encodeURIComponent,
    crypto: require('crypto').webcrypto, localStorage, setTimeout: () => 1, clearTimeout() {},
    document: {getElementById: $, createElement: t => new Element(t), querySelectorAll: query, body: new Element('body'), addEventListener() {}, execCommand: () => false},
    window: {addEventListener() {}}, fetch: async (path, options = {}) => {
      const response = await fetch(config.base + path, options), body = await response.json();
      const call = {method: options.method || 'GET', path, status: response.status};
      if (options.body) call.body = JSON.parse(options.body);
      if (body.source_impact) call.graph_sha256 = body.source_impact.sha256;
      calls.push(call);
      if (transport.hold?.(call)) { transport.hold = null; transport.held(call); await transport.release; }
      if (transport.dropAdopt && call.method === 'POST' && path.endsWith('/service-case-plan') && call.body?.opportunity_proof) { transport.dropAdopt = false; throw Error('SYNTHETIC_TYPED_ADOPT_RESPONSE_LOST'); }
      return {status: response.status, ok: response.ok, json: async () => body};
    }});
  vm.runInContext(code, context); $('token').value = config.token;
  return {$, run: text => vm.runInContext(text, context), context, elements};
}

(async () => {
  const config = await initialized, storage = {}, calls = [], transport = {dropAdopt: config.mode === 'lost'};
  diagnostics = {calls};
  let p = page(config, storage, calls, transport), {$, run} = p;
  const arm = predicate => { transport.hold = predicate; transport.ready = new Promise(resolve => transport.held = resolve); transport.release = new Promise(resolve => transport.resume = resolve); };
  async function lookup() {
    await $('case-worklist-read').onclick();
    const cards = $('case-worklist-items').children;
    const card = cards.find(e => e.children.some(child => child.dataset?.caseSourceImpact === config.preparation_id));
    check(!!card, 'current owner worklist contains original Case');
    const buttons = card.children.filter(e => e.tagName === 'button');
    check(!buttons[0].dataset.caseSourceImpact, 'original action remains the first button');
    const button = buttons.find(e => e.dataset.caseSourceImpact === config.preparation_id);
    check(!!button, 'source lookup has its own explicit button');
    return button;
  }
  const firstButton = await lookup(), beforeRead = calls.length;
  await firstButton.onclick();
  check(calls.slice(beforeRead).every(c => c.method === 'GET'), 'initial graph lookup only reads');
  check(run('caseSourceImpactView.row.preparation_id') === config.preparation_id, $('case-source-impact-status').textContent);
  check(textOf($('case-source-impact-items')).includes('查看此事项的来源证明'), 'original proof details are rendered');
  if (!['positive', 'lost'].includes(config.mode)) {
    if (config.mode === 'open_current_403') {
      await control('revoke'); await $('case-source-impact-open').onclick();
      check(calls.at(-1).status === 403, 'opening original materials encountered actual current denial');
      check(run('preparationView') === null && run('caseSourceImpactView') === null, 'current 403 clears private material and graph');
      check($('page-feedback').textContent.includes('权限'), 'current denial is visible');
    } else {
      const readButton = config.mode === 'open_late_403' ? null : await lookup();
      if (config.mode !== 'late_read_aba') await control('revoke');
      const opening = config.mode === 'open_late_403';
      arm(call => opening ? call.path === '/api/preparations/' + config.preparation_id : call.path.endsWith('/source-impact'));
      let late;
      if (opening) late = $('case-source-impact-open').onclick();
      else late = readButton.onclick();
      const held = await transport.ready;
      check(held.status === (config.mode === 'late_read_aba' ? 200 : 403), 'delayed response is an actual HTTP authorization result');
      $('token').value = 'SYNTHETIC_OTHER_TYPED_IDENTITY'; $('token').emit('input');
      $('token').value = config.token; $('token').emit('input');
      if (config.mode !== 'late_read_aba') await control('restore');
      await run(`loadPreparation(${JSON.stringify(config.preparation_id)}, {role:'enterprise_operator'})`);
      if (opening) {
        const currentPreparation = run('preparationView');
        check(currentPreparation.preparation.id === config.preparation_id, 'new identity has current authorized materials');
        transport.resume(); await late;
        check(run('preparationView') === currentPreparation, 'late graph-open 403 cannot clear new authorized materials');
      } else {
        const button = await lookup(); await button.onclick();
        const currentView = run('caseSourceImpactView');
        check(!!currentView, 'new identity generation has current authorized graph');
        transport.resume(); await late;
        check(run('caseSourceImpactView') === currentView, 'late success or 403 cannot replace or clear the new graph');
      }
    }
    check(calls.every(call => call.method === 'GET'), 'graph and navigation denial scenarios never write');
    console.log(JSON.stringify({scope: 'FULL_ORIGINAL_HTML_TYPED_SOURCE_REAL_HTTP_ASGI_OWNED_PG', mode: config.mode, checks, calls, storage_keys: Object.keys(storage)}));
    process.exit(0);
  }
  await $('case-source-impact-open').onclick();
  await $('opp-read').onclick();
  check(run('oppView.cards.length') === 0, 'source lookup created no opportunity');
  $('opp-generation').value = '1'; $('opp-kind').value = 'LOCAL_CASE_DATA'; $('opp-catalog').value = String(run('oppView.current_basis.catalog[0].version'));
  $('opp-title').value = 'SYNTHETIC typed source independent hint'; $('opp-note').value = 'SYNTHETIC imported prose cannot authorize a change';
  $('opp-purpose').checked = true; $('opp-reason').value = 'SYNTHETIC explicit original import';
  await $('opp-import').onsubmit({preventDefault() {}});
  check(run('oppView.cards.length') === 1, $('opp-error').textContent); const cardId = run('oppView.cards[0].id');
  await control('change_source'); $('opp-reason').value = 'SYNTHETIC explicit source refresh'; await $('opp-refresh').onclick();
  const graphButton = await lookup(), postsBefore = calls.filter(c => c.method === 'POST').length;
  await graphButton.onclick();
  check(calls.filter(c => c.method === 'POST').length === postsBefore, 'changed graph lookup did not adopt or refresh');
  const lastGraph = calls.filter(c => c.path.endsWith('/source-impact')).at(-1);
  check(lastGraph.status === 200, $('case-source-impact-status').textContent);
  check(textOf($('case-source-impact-items')).includes('P2') && textOf($('case-source-impact-items')).includes('P1'), 'graph names affected and preserved original steps');
  await $('case-source-impact-open').onclick(); await $('opp-read').onclick();
  await run(`previewOpportunityPlan(${JSON.stringify(cardId)})`);
  check(run('opportunityPlanView.source_impact.affected.length') === 4, $('opp-plan-status').textContent);
  check(run('opportunityPlanView.source_impact.sha256') === lastGraph.graph_sha256, 'Case lookup and original opportunity preview prove exactly the same graph');
  check(textOf($('opp-plan-impact')).includes('来源证明'), 'same typed graph is rendered in original opportunity preview');
  $('service-plan-reason').value = 'SYNTHETIC explicit original typed ADOPT';
  await run('opportunityPlanWrite().catch(()=>{})');
  check(calls.filter(c => c.method === 'POST').length === postsBefore, 'unchecked confirmation never submits');
  $('opp-plan-confirm').checked = true; await run('opportunityPlanWrite()');
  check(calls.filter(c => c.method === 'POST' && c.body?.opportunity_proof).length === 1, 'one explicit original ADOPT');
  if (config.mode === 'lost') {
    check(Object.keys(storage).some(k => k.startsWith('parkweave.service-plan-recovery.')), 'lost response retains original opaque handle');
    check(!JSON.stringify(storage).includes('opportunity_proof') && !JSON.stringify(storage).includes('SYNTHETIC explicit'), 'opaque storage contains no private body');
    const count = calls.length; p = page(config, storage, calls, transport); ({$, run} = p);
    await run(`loadServiceCasePlan(${JSON.stringify(config.preparation_id)})`);
    check(calls.slice(count).every(c => c.method === 'GET'), 'cold restore only GETs original key');
    check(run('servicePlanRecoveryHandle.observed') === true, $('service-plan-error').textContent);
    await $('service-plan-release').onclick();
  }
  await control('after_adopt');
  check(run('servicePlanView.plan_id') === config.plan_id && run('servicePlanView.steps[0].manually_locked'), 'same plan and unaffected P1 lock retained');
  for (const adapter of ['P2', 'P3', 'P4', 'P5']) {
    const id = run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).id`);
    $('service-plan-reason').value = 'SYNTHETIC typed original ' + adapter + ' VERIFY'; await run(`servicePlanWrite('VERIFY', ${JSON.stringify(id)})`);
    check(run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).state`) === 'VERIFIED', $('service-plan-error').textContent);
  }
  await $('goal-results-read').onclick(); check(run('goalResultView.results.length') === 6 && run('goalResultView.state') === 'LOCAL_OUTPUTS_VERIFIED', $('goal-results-error').textContent);
  check(!run('goalResultView.case_goal_completed'), 'local output evidence does not complete the original real goal');
  await $('case-worklist-read').onclick();
  console.log(JSON.stringify({scope: 'FULL_ORIGINAL_HTML_TYPED_SOURCE_REAL_HTTP_ASGI_OWNED_PG', mode: config.mode, checks, calls, storage_keys: Object.keys(storage)}));
  process.exit(0);
})().catch(error => { console.error(error.stack); if (diagnostics) console.error(JSON.stringify(diagnostics)); process.exit(1); });
