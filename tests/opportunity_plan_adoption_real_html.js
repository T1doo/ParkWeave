// Execute the entire shipped page. Only the DOM and browser transport surface are doubled.
// Every product API response comes from the owned HTTP/ASGI/PostgreSQL fixture.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const readline = require('readline').createInterface({input: process.stdin});
const pending = [];
let initialize;
const initialized = new Promise(resolve => initialize = resolve);
readline.on('line', line => { const value = JSON.parse(line); if (initialize) { initialize(value); initialize = null; } else pending.shift()(value); });
const control = name => new Promise(resolve => { pending.push(resolve); console.log(JSON.stringify({control: name})); });
const original = fs.readFileSync('src/parkweave/web.html', 'utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
let checks = 0, diagnostics = null;
const check = (value, message) => { checks++; assert(value, message); };
class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.dataset = {}; this.textContent = ''; this.value = ''; this.hidden = true; this.disabled = false; this.checked = false; this.listeners = {}; const named = {}; this.elements = new Proxy([], {get: (a, key) => key in a ? a[key] : (named[key] ??= new Element('input'))}); }
  append(...values) { this.children.push(...values); }
  replaceChildren(...values) { this.children = values; this.textContent = ''; }
  get options() { return this.children.filter(child => child.tagName === 'option'); }
  get firstChild() { return this.children[0]; }
  get firstElementChild() { return this.children[0]; }
  reset() {} addEventListener(name, handler) { this.listeners[name] = handler; }
  setAttribute() {} removeAttribute() {} closest() { return null; } querySelectorAll() { return []; }
  scrollIntoView() {} focus() {} select() {} remove() {} click() { return this.onclick?.(); }
}
const textOf = element => element.textContent + element.children.map(child => typeof child === 'object' ? textOf(child) : child).join(' ');
function page(config, storage, calls, transport) {
  const elements = new Map();
  const $ = id => { if (!elements.has(id)) { const element = new Element(); element.id = id; elements.set(id, element); } return elements.get(id); };
  const walk = element => [element, ...element.children.filter(x => typeof x === 'object').flatMap(walk)];
  const query = selector => [...elements.values()].flatMap(walk).filter(element => selector.split(',').some(s => {
    if (s === 'button' || s === 'form') return element.tagName === s;
    const match = s.match(/^\[data-([\w-]+)\]$/); if (!match) return false;
    return Object.hasOwn(element.dataset, match[1].replace(/-([a-z])/g, (_, c) => c.toUpperCase()));
  }));
  const localStorage = new Proxy({getItem: key => storage[key] ?? null, setItem: (key, value) => storage[key] = value, removeItem: key => delete storage[key]}, {ownKeys: () => Object.keys(storage), getOwnPropertyDescriptor: () => ({enumerable: true, configurable: true})});
  const context = vm.createContext({console, Date, JSON, Map, Set, WeakMap, Number, String, Error, TextEncoder, URL, encodeURIComponent,
    crypto: require('crypto').webcrypto, localStorage, setTimeout: () => 1, clearTimeout() {},
    document: {getElementById: $, createElement: tag => new Element(tag), querySelectorAll: query, body: new Element('body'), addEventListener() {}, execCommand: () => false},
    window: {addEventListener() {}}, fetch: async (path, options = {}) => {
      const response = await fetch(config.base + path, options); const body = await response.json();
      const entry = {method: options.method || 'GET', path, status: response.status};
      if (options.body) entry.body = JSON.parse(options.body);
      calls.push(entry);
      if (transport.hold?.(entry)) { transport.hold = null; transport.held(entry); await transport.release; }
      if (transport.dropAdopt && entry.method === 'POST' && path.endsWith('/service-case-plan') && entry.body?.opportunity_proof) { transport.dropAdopt = false; throw Error('SYNTHETIC_COMMITTED_RESPONSE_LOST'); }
      return {status: response.status, ok: response.ok, json: async () => body};
    }});
  vm.runInContext(original, context); $('token').value = config.token;
  return {$, run: code => vm.runInContext(code, context), context};
}
(async () => {
  const config = await initialized, storage = {}, calls = [], transport = {dropAdopt: config.mode === 'lost'};
  diagnostics = {calls};
  let p = page(config, storage, calls, transport), {$, run} = p;
  await run(`loadPreparation(${JSON.stringify(config.preparation_id)}, {role:'enterprise_operator'})`);
  await $('opp-read').onclick();
  check(run('oppView.cards.length') === 0, 'fresh Case has no imported opportunity');
  $('opp-generation').value = '1'; $('opp-kind').value = 'LOCAL_CASE_DATA';
  $('opp-catalog').value = String(run('oppView.current_basis.catalog[0].version'));
  $('opp-title').value = 'SYNTHETIC independent source change'; $('opp-note').value = 'SYNTHETIC unverified hint only';
  $('opp-purpose').checked = true; $('opp-reason').value = 'SYNTHETIC explicitly import same Case source';
  await $('opp-import').onsubmit({preventDefault() {}});
  check(run('oppView.cards.length') === 1, $('opp-error').textContent);
  check(run('oppView.cards[0].state') === 'PENDING_REVIEW');
  const cardId = run('oppView.cards[0].id');
  await control('change_source');
  $('opp-reason').value = 'SYNTHETIC explicit manual refresh of actual source';
  await $('opp-refresh').onclick();
  check(run('oppView.history.at(-1).action') === 'REFRESH');
  const postsBeforePreview = calls.filter(call => call.method === 'POST').length;
  if (['late_draft', 'late_identity_aba', 'late_denied'].includes(config.mode)) {
    const arm = predicate => { transport.hold = predicate; transport.ready = new Promise(resolve => transport.held = resolve); transport.release = new Promise(resolve => transport.resume = resolve); };
    if (config.mode === 'late_denied') await control('revoke_read');
    arm(call => call.path.endsWith(config.mode === 'late_denied' ? '/service-case-plan' : '/plan-revision'));
    let staleError = null;
    const late = run(`previewOpportunityPlan(${JSON.stringify(cardId)})`).catch(error => staleError = error);
    const held = await transport.ready;
    check(held.status === (config.mode === 'late_denied' ? 403 : 200), 'delayed response came from actual authorization check');
    if (config.mode === 'late_draft') {
      $('service-plan-reason').value = 'SYNTHETIC newer draft'; $('service-plan-reason').listeners.input();
      $('service-plan-reason').value = ''; $('service-plan-reason').listeners.input();
    } else {
      $('token').value = 'SYNTHETIC_OTHER_IDENTITY'; $('token').oninput();
      $('token').value = config.token; $('token').oninput();
      if (config.mode === 'late_denied') await control('restore_read');
      await run(`loadPreparation(${JSON.stringify(config.preparation_id)}, {role:'enterprise_operator'})`);
      await $('opp-read').onclick();
      $('service-plan-reason').value = 'SYNTHETIC newer identity draft';
    }
    const draft = $('service-plan-reason').value;
    transport.resume(); await late;
    check(!!staleError, 'late response rejected after context changed');
    run('opportunityPlanError').call(null, staleError);
    check(run('opportunityPlanView') === null, 'late preview did not repopulate private state');
    check($('opp-plan-preview').hidden, 'late preview stays hidden');
    check($('service-plan-reason').value === draft, 'late response did not overwrite current draft');
    check(run('preparationView.preparation.id') === config.preparation_id, 'late forbidden response did not clear current authorized Case');
    check(run('oppView.cards.length') === 1, 'current owner opportunity survived late response');
    check(calls.filter(call => call.method === 'POST').length === postsBeforePreview, 'late reads never cause a write');
    console.log(JSON.stringify({mode: config.mode, checks, scope: 'FULL_ORIGINAL_HTML_REAL_HTTP_ASGI_OWNED_POSTGRESQL', calls, storage_keys: Object.keys(storage)}));
    process.exit(0);
  }
  await run(`previewOpportunityPlan(${JSON.stringify(cardId)})`);
  check(calls.filter(call => call.method === 'POST').length === postsBeforePreview, 'preview remains read only');
  const previewText = textOf($('opp-plan-impact'));
  check(previewText.includes('P2') && previewText.includes('P1'), 'preview names affected and preserved steps');
  $('service-plan-reason').value = 'SYNTHETIC independent explicit original local ADOPT';
  await run('opportunityPlanWrite().catch(e=>{ $("opp-plan-status").textContent=e.message; })');
  check(calls.filter(call => call.method === 'POST').length === postsBeforePreview, 'unchecked confirmation cannot submit');
  $('opp-plan-confirm').checked = true;
  await run('opportunityPlanWrite()');
  const adopts = calls.filter(call => call.method === 'POST' && call.path.endsWith('/service-case-plan') && call.body?.opportunity_proof);
  check(adopts.length === 1 && adopts[0].status === 201, $('opp-plan-status').textContent);
  check(adopts[0].body.local_revision === true && adopts[0].body.opportunity_proof.card_id === cardId);
  if (config.mode === 'lost') {
    check(Object.keys(storage).some(key => key.startsWith('parkweave.service-plan-recovery.')), 'lost receipt retains original opaque handle');
    const privateStorage = JSON.stringify(storage);
    check(!privateStorage.includes('SYNTHETIC independent') && !privateStorage.includes('opportunity_proof'), 'storage contains no private body');
    const count = calls.length;
    p = page(config, storage, calls, transport); ({$, run} = p);
    await run(`loadServiceCasePlan(${JSON.stringify(config.preparation_id)})`);
    check(calls.slice(count).every(call => call.method === 'GET'), 'cold reopening only reads');
    check(calls.slice(count).some(call => call.path.endsWith('/command-recovery')), 'cold reopening reads original key');
    check(run('servicePlanRecoveryHandle?.observed') === true, $('service-plan-error').textContent);
    await $('service-plan-release').onclick();
  }
  await control('after_adopt');
  check(run('opportunityPlanView') === null, 'saved adoption clears the consumed preview');
  check(run('servicePlanView.plan_id') === config.plan_id, 'same plan identity retained');
  check(run('servicePlanView.steps[0].manually_locked') === true, 'unaffected P1 lock retained');
  for (const adapter of ['P2', 'P3', 'P4', 'P5']) {
    const stepId = run(`servicePlanView.steps.find(step=>step.adapter_id===${JSON.stringify(adapter)}).id`);
    $('service-plan-reason').value = 'SYNTHETIC independent explicit actual ' + adapter + ' VERIFY';
    await run(`servicePlanWrite('VERIFY', ${JSON.stringify(stepId)})`);
    check(run(`servicePlanView.steps.find(step=>step.adapter_id===${JSON.stringify(adapter)}).state`) === 'VERIFIED', $('service-plan-error').textContent);
  }
  await $('goal-results-read').onclick();
  check(run('goalResultView.results.length') === 6, $('goal-results-error').textContent);
  check(run('goalResultView.state') === 'LOCAL_OUTPUTS_VERIFIED');
  await $('case-worklist-read').onclick();
  check($('case-worklist-items').children.length > 0, $('case-worklist-status').textContent);
  check(!run('goalResultView.case_goal_completed'), 'local evidence never completes original Case goal');
  console.log(JSON.stringify({mode: config.mode, checks, scope: 'FULL_ORIGINAL_HTML_REAL_HTTP_ASGI_OWNED_POSTGRESQL', calls, storage_keys: Object.keys(storage)}));
  process.exit(0);
})().catch(error => { console.error(error.stack); if (diagnostics) console.error(JSON.stringify(diagnostics)); process.exit(1); });
