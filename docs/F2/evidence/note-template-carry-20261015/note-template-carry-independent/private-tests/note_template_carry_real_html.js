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
  const config=await initialized,calls=[],storage={},transport={};diagnostics={calls};
  let p=page({...config,page:'upgrade'},storage,calls,transport),{$,run}=p;
  const output=extra=>console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_NOTE_TEMPLATE_CARRY_ACTUAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,calls,real_browser:'NOT_RUN',...extra}));
  check($('apply').tagName==='button'&&$('note-carry-confirm').tagName==='input','parse actual original button and explicit checkbox tags');
  check(typeof $('apply').onclick==='function'&&$('apply').onclick.toString().includes('applicationReady'),'execute installed original apply handler');
  $('instance').value=config.row.instance_id;await $('catalog').onclick();
  $('target').value=config.target.release_id;await $('check').onclick();
  check(!!run('inspection'),'actual checker inspection rendered');
  check(run('inspection.application.eligible')===false,'old apply remains ineligible for a manual note');
  $('reason').value='SYNTHETIC explicit original choice for this current compatible version';
  const choice=[...p.elements.values()].find(e=>e.dataset.choice==='REQUEST_RECHECK');check(!!choice,'actual HTML supplies original REQUEST_RECHECK choice');
  await choice.onclick();check(run('inspection===null'),'explicit choice requires fresh check');
  await $('check').onclick();
  const carry=run('inspection.application.note_carry');
  check(carry.schema===1&&carry.eligible&&carry.manual_preserved,'current actual MANUAL carry DTO is eligible');
  const preview=textOf($('note-carry-preview'));
  check(preview.includes(config.manual)&&preview.includes(JSON.stringify(carry.previous_template_source))&&preview.includes(JSON.stringify(carry.target_template_source)),'original page renders full M and actual old/new template sources');
  check(Object.values(carry.notes).length===1&&Object.values(carry.notes)[0].origin==='MANUAL'&&Object.values(carry.notes)[0].text===config.manual,'actual source does not relabel M');
  check(carry.affected.length===(config.mode==='title_locked'?0:5)&&carry.preserved.length===(config.mode==='title_locked'?5:0),'literal template impact partition');
  check(carry.proof.materials.current.length===2,'both current material slots appear in proof');
  const beforePost=calls.filter(c=>c.method==='POST').length;
  $('apply-reason').value='SYNTHETIC explicit keep exact MANUAL while adopting this compatible template';$('apply-reason').oninput();
  $('apply-confirm').checked=true;$('apply-confirm').onchange();
  await $('apply').onclick();check(calls.filter(c=>c.method==='POST').length===beforePost&&run('pending===null'),'ordinary apply confirmation cannot replace separate note carry confirmation');
  $('note-carry-confirm').checked=true;$('note-carry-confirm').onchange();check(!$('apply').disabled,'both explicit confirmations enable the original apply button');
  await control('before_apply');
  if(config.mode==='source_changed')transport.dropPath='/apply-note-carry';
  await $('apply').onclick();const originalKey=$('apply-key').value;check(!!originalKey,'original key retained');
  if(config.mode==='source_changed') {
    check(run("pending?.kind==='apply'"),'actual committed response loss retains pending');
    const count=calls.length;p=page({...config,page:'upgrade'},storage,calls,transport);({$,run}=p);
    $('instance').value=config.row.instance_id;$('apply-key').value=originalKey;
    await $('apply-recover').onclick();
    check(calls.slice(count).every(c=>c.method==='GET'),'fresh VM cold recovery only GETs the original key');
    check($('apply-receipt').textContent.includes('COMMITTED')&&run('pending===null'),'full new carry proof validates in cold recovery');
  } else check($('apply-receipt').textContent.includes('TEMPLATE_UPGRADE')||$('original-case').hidden===false,'original handler validates successful complete carry receipt');
  check(calls.filter(c=>c.method==='POST'&&c.path.endsWith('/apply-note-carry')).length===1,'exactly one explicit new carry POST');
  check(calls.filter(c=>c.method==='POST'&&/\/apply(?:-structure)?$/.test(c.path)).length===0,'no old apply route used to bypass carry');
  await control('after_apply');
  p=page(config,storage,calls,transport);({$,run}=p);
  await run(`loadServiceCasePlan(${JSON.stringify(config.row.preparation_id)})`);
  check(run('servicePlanView.plan_id')===config.plan_id,'stable original plan UUID');
  const walk=e=>[e,...e.children.filter(x=>typeof x==='object').flatMap(walk)];
  if(config.mode==='source_changed') {
    check(run("servicePlanView.steps.every(s=>s.state!=='VERIFIED')"),'template source change invalidates all original five steps');
    for(const adapter of ['P1','P2','P3','P4','P5']) {
      const step=run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)})`);
      const verify=walk($('service-plan-steps')).find(e=>e.dataset.serviceAction==='VERIFY'&&e.dataset.serviceStep===step.id);
      check(!!verify,'actual original page renders affected '+adapter+' VERIFY button');
      $('service-plan-reason').value='SYNTHETIC explicit actual '+adapter+' VERIFY under new template';
      await verify.onclick();check(run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).state`)==='VERIFIED',$('service-plan-error').textContent);
    }
  } else {
    check(run("servicePlanView.steps.every(s=>s.state==='VERIFIED')"),'same template source preserves all current checks');
    check(run("servicePlanView.steps.filter(s=>s.manually_locked).length")===2,'unaffected P1/P3 locks remain active');
    check(!calls.some(c=>c.method==='POST'&&c.body?.action==='UNLOCK'),'no automatic or implicit unlock');
  }
  await $('goal-results-read').onclick();check(run("goalResultView.state==='LOCAL_OUTPUTS_VERIFIED'&&goalResultView.results.length===6&&!goalResultView.case_goal_completed"),'all six original actual goal outputs remain current without completing Case');
  await $('case-worklist-read').onclick();check($('case-worklist-items').children.length===1,'original owner worklist contains the same Case');
  await control('final');output({manual_preserved:true,six_goals_current:true,stable_plan_and_history:true,controlled_committed_response_loss:config.mode==='source_changed',fake_dto:false});process.exit(0);
})().catch(e=>{console.error(JSON.stringify({message:e.message,stack:e.stack,diagnostics}));process.exit(1);});
