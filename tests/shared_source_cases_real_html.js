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
      if (transport.dropAdopt && call.method === 'POST' && path.endsWith('/service-case-plan') && call.body?.opportunity_proof) { transport.dropAdopt = false; throw Error('SYNTHETIC_SHARED_ADOPT_RESPONSE_LOST'); }
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
  async function graph(anchor = config) {
    await $('case-worklist-read').onclick();
    const card = $('case-worklist-items').children.find(e => e.children.some(child => child.dataset?.caseSourceImpact === anchor.preparation_id));
    check(!!card, 'current owner worklist has original anchor Case');
    const buttons = card.children.filter(e => e.tagName === 'button');
    check(!buttons[0].dataset.caseSourceImpact, 'original action stays the first button');
    await buttons.find(e => e.dataset.caseSourceImpact === anchor.preparation_id).onclick();
    check(run('caseSourceImpactView.row.preparation_id') === anchor.preparation_id, $('case-source-impact-status').textContent);
    check(!$('case-shared-source-cases').hidden, 'reverse source selector is available only within current Case graph');
  }
  async function reverse(kind = 'OWNER_RESOURCE_QUERY_SET') {
    $('case-shared-source-kind').value = kind;
    $('case-shared-source-kind').onchange();
    const before = calls.length; await $('case-shared-source-read').onclick();
    check(calls.slice(before).every(c => c.method === 'GET'), 'shared-source lookup only reads');
    check(!!run('sharedSourceCasesView'), $('case-shared-source-status').textContent);
    check(run('sharedSourceCasesView.kind') === kind, 'source selection is bound to returned reverse page');
    return calls.filter(c => c.path.includes('/shared-source-cases?')).at(-1);
  }
  await graph();
  if (['pagination','pagination_stale'].includes(config.mode)) {
    await reverse();
    check(!$('case-shared-source-next').hidden && run('sharedSourceCasesView.next_cursor') !== null, 'first bounded page exposes an explicit next-page action');
    check($('case-shared-source-items').children.length === 10, 'page respects the original ten-row UI bound');
    if (config.mode === 'pagination_stale') await control('change_source');
    const before = calls.length; await $('case-shared-source-next').onclick();
    check(calls.slice(before).every(c => c.method === 'GET'), 'next-page action only GETs the original cursor');
    if (config.mode === 'pagination_stale') {
      check(calls.at(-1).status === 409 && run('sharedSourceCasesView') === null, 'changed source refuses the old cursor and removes candidate rows');
      check($('case-shared-source-items').children.length === 0 && $('case-shared-source-status').textContent.includes('第一页'), 'stale page tells the user to restart without retaining old rows');
    } else {
      check($('case-shared-source-next').hidden && $('case-shared-source-items').children.length === 1, 'second page is bounded and exhausts this explicit candidate enumeration');
      check($('case-shared-source-status').textContent.includes('未知'), 'unknown unprepared Cases do not become no-impact claims');
    }
    check(calls.every(c => c.method === 'GET'), 'pagination cannot import or adopt');
    console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_SHARED_SOURCE_REAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,calls,storage_keys:Object.keys(storage)})); process.exit(0);
  }
  if (config.mode === 'overflow') {
    await reverse();
    check($('case-shared-source-items').children.length === 0, 'overflow never shows an invented zero-impact list');
    check($('case-shared-source-status').textContent.includes('未知') && $('case-shared-source-next').hidden, 'overflow explicitly states unknown coverage without a continuation cursor');
    check(calls.every(c => c.method === 'GET'), 'overflow source lookup never writes');
    console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_SHARED_SOURCE_REAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,calls,storage_keys:Object.keys(storage)})); process.exit(0);
  }
  if (!['positive', 'lost'].includes(config.mode)) {
    await reverse();
    if (config.mode === 'current_403') {
      await control('revoke'); await $('case-shared-source-read').onclick();
      check(calls.at(-1).status === 403, 'current reverse lookup encountered actual authorization denial');
      check(run('sharedSourceCasesView') === null && run('caseSourceImpactView') === null, 'current denial clears private reverse and graph');
      check($('case-shared-source-items').children.length === 0, 'current denial leaves no private candidate rows');
    } else {
      if (config.mode === 'late_403') await control('revoke');
      arm(call => call.path.includes('/shared-source-cases?'));
      const late = $('case-shared-source-read').onclick(), held = await transport.ready;
      check(held.status === (config.mode === 'late_403' ? 403 : 200), 'held response came from actual HTTP authorization');
      if (config.mode === 'kind_switch') {
        await reverse('SERVICE_CATALOG_REFERENCE');
      } else {
        $('token').value = 'SYNTHETIC_OTHER_SHARED_IDENTITY'; $('token').emit('input');
        $('token').value = config.token; $('token').emit('input');
        if (config.mode === 'late_403') await control('restore');
        await graph(); await reverse();
      }
      const current = run('sharedSourceCasesView'), rows = $('case-shared-source-items').children;
      transport.resume(); await late;
      check(run('sharedSourceCasesView') === current && $('case-shared-source-items').children === rows, 'late response cannot replace or clear the newer identity/source generation');
    }
    check(calls.every(c => c.method === 'GET'), 'reverse read refusal and race paths never write');
    check(Object.keys(storage).length === 0, 'source lookup adds no persistent private state');
    console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_SHARED_SOURCE_REAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,calls,storage_keys:Object.keys(storage)})); process.exit(0);
  }
  await reverse();
  check($('case-shared-source-items').children.length === 2, 'both independent owner Cases are listed');
  const target = config.target;
  const findTarget = () => $('case-shared-source-items').children.flatMap(e => e.children).find(e => e.dataset?.sharedSourceCase === target.case_id);
  check(!!findTarget(), 'explicit reverse row opens the other Case');
  await findTarget().onclick();
  check(run('caseSourceImpactView.row.preparation_id') === target.preparation_id, 'reverse row navigates to original other Case graph');
  await $('case-source-impact-open').onclick(); await $('opp-read').onclick();
  check(run('oppView.cards.length') === 0, 'reverse reads create no opportunity');
  $('opp-generation').value = '1'; $('opp-kind').value = 'LOCAL_CASE_DATA'; $('opp-catalog').value = String(run('oppView.current_basis.catalog[0].version'));
  $('opp-title').value = 'SYNTHETIC shared source opportunity'; $('opp-note').value = 'SYNTHETIC hint cannot authorize a change';
  $('opp-purpose').checked = true; $('opp-reason').value = 'SYNTHETIC explicit import';
  await $('opp-import').onsubmit({preventDefault() {}});
  check(run('oppView.cards.length') === 1, $('opp-error').textContent); const cardId = run('oppView.cards[0].id');
  await control('change_source'); $('opp-reason').value = 'SYNTHETIC explicit original source refresh'; await $('opp-refresh').onclick();
  const postCount = calls.filter(c => c.method === 'POST').length;
  await graph(); await reverse();
  check(textOf($('case-shared-source-items')).includes('共享来源已变化'), 'actual shared version change is visible in reverse list');
  check(calls.filter(c => c.method === 'POST').length === postCount, 'reverse version refresh never adopts a plan');
  await findTarget().onclick(); const graphCall = calls.filter(c => c.path.endsWith('/source-impact')).at(-1);
  await $('case-source-impact-open').onclick(); await $('opp-read').onclick();
  await run(`previewOpportunityPlan(${JSON.stringify(cardId)})`);
  check(run('opportunityPlanView.source_impact.affected.length') === 4, $('opp-plan-status').textContent);
  check(run('opportunityPlanView.source_impact.sha256') === graphCall.graph_sha256, 'original preview binds the exact current Case graph');
  $('service-plan-reason').value = 'SYNTHETIC explicit shared source ADOPT';
  await run('opportunityPlanWrite().catch(()=>{})');
  check(calls.filter(c => c.method === 'POST').length === postCount, 'unchecked confirmation never writes');
  $('opp-plan-confirm').checked = true; await run('opportunityPlanWrite()');
  check(calls.filter(c => c.method === 'POST' && c.body?.opportunity_proof).length === 1, 'one explicit original ADOPT');
  if (config.mode === 'lost') {
    check(Object.keys(storage).some(k => k.startsWith('parkweave.service-plan-recovery.')), 'lost response keeps original opaque recovery key');
    check(!JSON.stringify(storage).includes('opportunity_proof'), 'opaque recovery storage has no private request body');
    const count = calls.length; p = page(config, storage, calls, transport); ({$, run} = p);
    await run(`loadServiceCasePlan(${JSON.stringify(target.preparation_id)})`);
    check(calls.slice(count).every(c => c.method === 'GET'), 'cold recovery only GETs original command state');
    check(run('servicePlanRecoveryHandle.observed') === true, $('service-plan-error').textContent);
    await $('service-plan-release').onclick();
  }
  await control('after_adopt');
  check(run('servicePlanView.plan_id') === config.plan_id && run('servicePlanView.steps[0].manually_locked'), 'original plan UUID and unaffected P1 lock survive');
  for (const adapter of ['P2','P3','P4','P5']) {
    const id = run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).id`);
    $('service-plan-reason').value = 'SYNTHETIC original shared ' + adapter + ' VERIFY'; await run(`servicePlanWrite('VERIFY',${JSON.stringify(id)})`);
    check(run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).state`) === 'VERIFIED', $('service-plan-error').textContent);
  }
  await $('goal-results-read').onclick(); check(run('goalResultView.results.length') === 6 && run('goalResultView.state') === 'LOCAL_OUTPUTS_VERIFIED', $('goal-results-error').textContent);
  check(!run('goalResultView.case_goal_completed'), 'six local outputs do not complete the original real goal');
  await $('case-worklist-read').onclick();
  console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_SHARED_SOURCE_REAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,calls,storage_keys:Object.keys(storage)})); process.exit(0);
})().catch(error => { console.error(error.stack); if (diagnostics) console.error(JSON.stringify(diagnostics)); process.exit(1); });

