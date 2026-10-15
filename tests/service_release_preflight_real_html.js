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
  get firstChild() { return this.children[0]; }
  get firstElementChild() { return this.children[0]; }
  addEventListener(name, handler) { (this.listeners[name] ??= []).push(handler); }
  emit(name) { this['on' + name]?.({target: this}); for (const handler of this.listeners[name] || []) handler({target: this}); }
  reset() {} setAttribute() {} removeAttribute() {} closest() { return null; } querySelectorAll() { return []; }
  scrollIntoView() {} focus() {} select() {} remove() {} click() { return this.onclick?.(); }
}
const textOf = element => element.textContent + element.children.map(e => typeof e === 'object' ? textOf(e) : e).join(' ');
function page(config, storage, calls, transport) {
  const elements = new Map();
  for (const match of html.split('<script')[0].matchAll(/<([a-z][\w-]*)\b[^>]*\bid=["']([^"']+)["'][^>]*>/gi)) {
    const element = new Element(match[1].toLowerCase()); element.id = match[2]; elements.set(element.id, element);
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
      if (transport.beforeBusiness && (options.method || 'GET') === 'POST' && path.endsWith('/service-case-plan/commands')) {
        transport.beforeBusiness=false;transport.held({stage:'BEFORE_ORIGINAL_BUSINESS_SEND'});await transport.release;
        throw Error('SYNTHETIC_ORIGINAL_BUSINESS_REQUEST_DELIVERY_UNCERTAIN');
      }
      const response = await fetch(config.base + path, options), body = await response.json();
      const call = {method: options.method || 'GET', path, status: response.status};
      if (options.body) call.body = JSON.parse(options.body);
      if(call.method==='POST'&&path.endsWith('/service-release-preflight'))call.request_key=options.headers['Idempotency-Key'];
      if (body.source_impact) call.graph_sha256 = body.source_impact.sha256;
      calls.push(call);
      if (transport.futureSchema && path.includes('/service-release-preflight/preview?')) { transport.futureSchema = false; body.schema = 2; }
      if (transport.hold?.(call)) { transport.hold = null; transport.held(call); await transport.release; }
      if (transport.dropRecord && call.method === 'POST' && path.endsWith('/service-release-preflight')) { transport.dropRecord = false; throw Error('SYNTHETIC_PREFLIGHT_REPORT_RESPONSE_LOST'); }
      return {status: response.status, ok: response.ok, json: async () => body};
    }});
  vm.runInContext(code, context); $('token').value = config.token;
  return {$, run: text => vm.runInContext(text, context), context, elements};
}

(async () => {
  const config = await initialized, storage = {}, calls = [], transport = {dropRecord:config.mode.startsWith('lost'),futureSchema:config.mode==='unknown_dto'};
  diagnostics={calls}; let p=page(config,storage,calls,transport),{$,run}=p;
  check($('service-release-preflight-save').tagName==='button','actual HTML identifies the installed save button');
  check($('service-release-preflight-save').onclick!==run('saveServiceReleasePreflight')&&$('service-release-preflight-save').onclick.toString().includes('entryReadAllowed'),'original installation wrapped the actual save handler');
  const arm = predicate => {transport.hold=predicate;transport.ready=new Promise(resolve=>transport.held=resolve);transport.release=new Promise(resolve=>transport.resume=resolve);};
  async function directory() {
    await run(`loadServiceCasePlan(${JSON.stringify(config.preparation_id)})`);
    check(run('servicePlanView.plan_id')===config.plan_id,'original plan is read before preflight');
    await $('service-release-preflight-read').onclick();
    check(!!run('serviceReleasePreflightDirectory'),$('service-release-preflight-status').textContent);
    const original=run(`serviceReleasePreflightDirectory.originals.findIndex(x=>x.ref.release_id===${JSON.stringify(config.original_ref.release_id)}&&x.ref.instance_id===${JSON.stringify(config.original_ref.instance_id)})`);
    const target=run(`serviceReleasePreflightDirectory.targets.findIndex(x=>x.ref.instance_id===${JSON.stringify(config.target_ref.instance_id)})`);
    check(original>=0&&target>=0,'original historical selection and actual current target are separate exact options');
    $('service-release-preflight-original').value=String(original);$('service-release-preflight-original').emit('change');
    $('service-release-preflight-target').value=String(target);$('service-release-preflight-target').emit('change');
  }
  const show=()=>$('service-release-preflight-preview').onclick();
  await directory();
  if(config.mode==='pending') {
    await show();check(run('serviceReleasePreflightView.classification')==='COMPATIBLE','unchanged original target can be previewed before pending business operation');
    $('service-release-preflight-confirm').checked=true;$('service-release-preflight-reason').value='SYNTHETIC pending must block audit';
    $('service-plan-reason').value='SYNTHETIC original LOCK delivery pending';const step=run("servicePlanView.steps.find(s=>s.adapter_id==='P1').id");
    arm(()=>false);transport.beforeBusiness=true;const pending=run(`servicePlanWrite('LOCK',${JSON.stringify(step)})`);
    const held=await transport.ready;check(held.stage==='BEFORE_ORIGINAL_BUSINESS_SEND','original business handler is genuinely awaiting its delivery');
    await $('service-release-preflight-save').onclick();
    check(!Object.keys(storage).some(k=>k.startsWith('parkweave.service-release-preflight.')),'pending original business creates no phantom preflight handle');
    check(calls.every(c=>c.method==='GET'),'pending business prevents a new audit POST');
    transport.resume();await pending;
    check(Object.keys(storage).some(k=>k.startsWith('parkweave.service-plan-recovery.')),'original uncertain business handle is retained');
  } else if(['current_403','late_aba','late_403','target_aba'].includes(config.mode)) {
    if(config.mode==='current_403') {
      await control('revoke');await show();
      check(calls.at(-1).status===403,'current denial is an actual HTTP 403');
      check(run('servicePlanView')===null&&run('serviceReleasePreflightView')===null,'current denial clears private plan/preflight');
      check($('service-release-preflight-result').children.length===0,'denied private report is cleared');
    } else {
      if(config.mode==='late_403')await control('revoke');
      arm(call=>call.path.includes('/service-release-preflight/preview?'));
      const late=show(),held=await transport.ready;
      check(held.status===(config.mode==='late_403'?403:200),'late reply holds an actual API result');
      if(config.mode==='target_aba') {
        const current=$('service-release-preflight-original').value;
        $('service-release-preflight-original').value=String((Number(current)+1)%run('serviceReleasePreflightDirectory.originals.length'));
        $('service-release-preflight-original').emit('change');
        $('service-release-preflight-original').value=current;$('service-release-preflight-original').emit('change');
      } else {
        $('token').value='SYNTHETIC_OTHER_PREFLIGHT_IDENTITY';$('token').emit('input');
        $('token').value=config.token;$('token').emit('input');
        if(config.mode==='late_403')await control('restore');
        await directory();
      }
      await show();const current=run('serviceReleasePreflightView'),nodes=$('service-release-preflight-result').children;
      check(!!current,'new generation has its own current report');transport.resume();await late;
      check(run('serviceReleasePreflightView')===current&&$('service-release-preflight-result').children===nodes,'late success/denial cannot replace or clear the newer report');
    }
    check(calls.every(c=>c.method==='GET'),'denial/ABA preflight paths never write');
    check(Object.keys(storage).length===0,'read-only preflight does not persist a request');
  } else {
    await show();
    if(config.mode==='unknown_dto') {
      check(run('serviceReleasePreflightView')===null&&$('service-release-preflight-result').children.length===0,'unknown DTO schema is never accepted as a preflight');
      $('service-release-preflight-confirm').checked=true;$('service-release-preflight-reason').value='SYNTHETIC reject unknown schema';
      await $('service-release-preflight-save').onclick();check(calls.every(c=>c.method==='GET'),'unknown DTO cannot record');
    } else {
      check(run('serviceReleasePreflightView.classification')===config.classification,$('service-release-preflight-status').textContent);
      check(run('serviceReleasePreflightView.contract_classification')===config.contract_classification,'contract and current Case classifications remain separate');
      const visible=textOf($('service-release-preflight-result'));
      check(visible.includes(config.original_ref.release_id)&&visible.includes(config.target_ref.release_id),'both exact historical and target releases are visible');
      check(visible.includes('不授权发布')&&visible.includes(config.classification),'preflight remains an observation with an explicit result');
      if(['record','lost','lost_withdrawn','repeat','tampered'].includes(config.mode)) {
        $('service-release-preflight-reason').value='SYNTHETIC explicit independent immutable preflight report';
        await $('service-release-preflight-save').onclick();check(calls.every(c=>c.method==='GET'),'unchecked confirmation sends no report');
        $('service-release-preflight-confirm').checked=true;await $('service-release-preflight-save').onclick();
        check(calls.filter(c=>c.method==='POST').length===1&&calls.find(c=>c.method==='POST').path.endsWith('/service-release-preflight'),'one explicit original installed save handler records only the preflight');
        check(!JSON.stringify(storage).includes(config.token)&&!JSON.stringify(storage).includes('original_ref')&&!JSON.stringify(storage).includes('SYNTHETIC explicit'),'persistent recovery contains only an opaque reference');
        if(config.mode.startsWith('lost')) {
          check(Object.keys(storage).some(k=>k.startsWith('parkweave.service-release-preflight.')),'lost reply keeps the original durable recovery handle');
          if(config.mode==='lost_withdrawn')await control('withdraw');
          const count=calls.length;p=page(config,storage,calls,transport);({$,run}=p);
          await run(`loadServiceCasePlan(${JSON.stringify(config.preparation_id)})`);
          await $('service-release-preflight-recover').onclick();
          check(calls.slice(count).every(c=>c.method==='GET'),'cold recovery only GETs the original report key');
        }
        check($('service-release-preflight-status').textContent.includes('已持久记录'),'original report proof was observed');
        check(!$('service-release-preflight-release').hidden,'only an observed original record enables explicit release');
        if(config.mode==='tampered') {
          const name=Object.keys(storage).find(k=>k.startsWith('parkweave.service-release-preflight.')),h=JSON.parse(storage[name]);
          h.sha='0'.repeat(64);storage[name]=JSON.stringify(h);const changed=storage[name];
          await $('service-release-preflight-release').onclick();
          check(storage[name]===changed,'a valid-shaped mutated handle cannot release an earlier observed proof');
          await $('service-release-preflight-recover').onclick();
          check(storage[name]===changed&&$('service-release-preflight-release').hidden,'mismatched original proof cannot observe or release the mutated handle');
          check(calls.filter(c=>c.method==='POST').length===1,'handle mutation never dispatches another POST');
        } else {
          await $('service-release-preflight-release').onclick();
          check(!Object.keys(storage).some(k=>k.startsWith('parkweave.service-release-preflight.')),'explicit observed release clears only the opaque recovery handle');
          if(config.mode==='repeat') {
            await directory();await show();$('service-release-preflight-reason').value='SYNTHETIC second explicit independent report';$('service-release-preflight-confirm').checked=true;
            await $('service-release-preflight-save').onclick();
            const records=calls.filter(c=>c.method==='POST');check(records.length===2&&records[0].request_key!==records[1].request_key,'observed release permits a second explicit record using a new key');
            check($('service-release-preflight-status').textContent.includes('已持久记录'),'second report has its own observed durable receipt');
          } else check(calls.filter(c=>c.method==='POST').length===1,'release and recovery cannot repeat a POST');
        }
      } else check(calls.every(c=>c.method==='GET'),'source/lock/breaking preview writes no audit or business record');
    }
  }
  console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_SERVICE_RELEASE_PREFLIGHT_REAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,calls,storage_keys:Object.keys(storage),negative_transport_fixture:['unknown_dto','pending'].includes(config.mode)}));process.exit(0);
})().catch(error=>{console.error(error.stack);if(diagnostics)console.error(JSON.stringify(diagnostics));process.exit(1);});

