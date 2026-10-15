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
      if (transport.revokeBeforeNote && (options.method || 'GET') === 'GET' && path.includes('/plan-material-package')) {
        transport.revokeBeforeNote = false;
        await control('revoke');
      }
      const response = await fetch(config.base + path, options), body = await response.json();
      const call = {method: options.method || 'GET', path, status: response.status};
      if (options.body) call.body = JSON.parse(options.body);
      if (call.method === 'POST') call.request_key = options.headers['Idempotency-Key'];
      if (body.source_impact) call.graph_sha256 = body.source_impact.sha256;
      call.response_scope = body.scope; call.response_schema = body.schema;
      const packageDTO=body.package_confirmation||body.current?.package_confirmation;if(packageDTO)call.package_confirmation={schema:packageDTO.schema,scope:packageDTO.scope,mode:packageDTO.mode,outline_carriage_required:packageDTO.outline_carriage_required};
      if(body.scope==='CURRENT_OWNER_SYNTHETIC_CASE_WORKLIST'){call.worklist_items=body.items.map(r=>({case_id:r.case_id,run_id:r.run_id,preparation_id:r.preparation_id,receipt_step_id:r.receipt_step_id,attention:r.attention,evidence_verified:r.evidence_verified,case_goal_completed:r.case_goal_completed}));call.next_after=body.next_after;}
      if (body.continuation) call.continuation = {scope:body.continuation.scope,schema:body.continuation.schema,coverage_known:body.continuation.coverage_known,coverage_satisfied:body.continuation.coverage_satisfied};
      calls.push(call);
      if (response.status === 403 && (options.method || 'GET') === 'GET' && path.includes('/plan-material-package')) {
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
  const config=await initialized,storage={},calls=[],transport={};diagnostics={calls};
  let p=page(config,storage,calls,transport),{$,run}=p;
  const load=async row=>{await run(`loadPreparation(${JSON.stringify(row.preparation_id)},{role:'enterprise_operator'})`);await $('opp-read').onclick();};
  const read=async card=>{if(card){$('plan-source-conflict-card').value=card;$('plan-source-conflict-card').onchange();}await $('material-package-read').onclick();check(!!run('materialPackageView'),$('material-package-status').textContent);};
  const output=extra=>console.log(JSON.stringify({scope:'FULL_ORIGINAL_HTML_MULTIFIELD_PACKAGE_ACTUAL_HTTP_ASGI_OWNED_PG',mode:config.mode,checks,calls,real_browser:'NOT_RUN',fake_dto:false,...extra}));
  await load(config.A);
  if(['current_403','late_403'].includes(config.mode)){
    await read();
    if(config.mode==='current_403'){
      transport.revokeBeforeNote=true;await $('material-package-read').onclick();
      check(calls.at(-1).status===403,'current package GET is actual backend403');
      check(run('materialPackageView')===null&&run('servicePlanView')===null,'current403 clears private views');
    }else{
      transport.revokeBeforeNote=true;transport.ready=new Promise(resolve=>transport.held=resolve);transport.release=new Promise(resolve=>transport.resume=resolve);
      transport.hold=c=>c.path.includes('/plan-material-package');
      const old=$('material-package-read').onclick();check((await transport.ready).status===403,'held response is actual backend403');
      $('token').value='SYNTHETIC_OTHER_PACKAGE_IDENTITY';$('token').emit('input');$('token').value=config.token;$('token').emit('input');
      await control('restore');await load(config.B);await read();await load(config.B);await read();const current=run('materialPackageView');
      transport.resume();await old;
      check(run('materialPackageView')===current&&current.preparation_id===config.B.preparation_id,'identity/caseABA late403 cannot clear later view');
    }
    check(calls.every(c=>c.method==='GET'),'authorization read flow sends no POST');output({});process.exit(0);
  }
  for(const id of ['keep','merge']){
    const button=$('material-package-'+id);check(button.tagName==='button'&&typeof button.onclick==='function','full original HTML installs '+id);
    check(button.onclick.toString().includes('entryReadAllowed'),'actual original flow wrapper protects '+id);
  }
  await $('plan-source-conflict-read').onclick();
  $('plan-source-conflict-note').value=config.manual;$('plan-source-conflict-reason').value='SYNTHETIC explicit initial MANUAL';$('plan-source-conflict-confirm').checked=true;
  await $('plan-source-conflict-edit').onclick();check(run('planSourceConflictView.note.text')===config.manual,$('plan-source-conflict-status').textContent);
  const p1=run("servicePlanView.steps.find(s=>s.adapter_id==='P1').id");$('service-plan-reason').value='SYNTHETIC original P1 lock';await run(`servicePlanWrite('LOCK',${JSON.stringify(p1)})`);
  await $('opp-read').onclick();$('opp-generation').value='1';$('opp-kind').value='LOCAL_CASE_DATA';$('opp-catalog').value=String(run('oppView.current_basis.catalog[0].version'));
  $('opp-title').value='SYNTHETIC two actual material fields';$('opp-note').value='Unverified hint gives no facts or authority';$('opp-purpose').checked=true;$('opp-reason').value='SYNTHETIC explicit original import';
  await $('opp-import').onsubmit({preventDefault(){}});const card=run('oppView.cards.find(c=>c.is_latest_generation).id');
  await control('change_material');await $('opp-read').onclick();$('opp-reason').value='SYNTHETIC original manual actual-source refresh';await $('opp-refresh').onclick();await read(card);
  const q=run('materialPackageView.package_confirmation');
  check(q.mode==='LEGACY_OUTLINE_ONLY'&&q.active===false,'GET has not enabled new mode');
  check(q.manual.text===config.manual&&q.policy.need_summary==='CONTEXT_ACK_ONLY','M is exact and summary context-only');
  const display=textOf($('material-package-result'));
  for(const value of [config.summaryBaseline,config.outlineBaseline,config.manual,config.summaryIncoming,config.outlineIncoming])check(display.includes(value),'original page renders actual B/M/S field text');
  check($('material-package-keep').disabled&&$('material-package-merge').disabled,'original P1 lock blocks both package actions');
  $('service-plan-reason').value='SYNTHETIC original explicit P1 UNLOCK';await run(`servicePlanWrite('UNLOCK',${JSON.stringify(p1)})`);await read(card);
  const both=config.mode==='dual_merge_lost_ack',action=both?'merge':'keep',expected=both?config.merged:config.manual;
  check(run('materialPackageView.package_confirmation.outline_carriage_required')===both,'outline obligation depends on actual outline change');
  if(both){const conditions=run('materialPackageView.package_confirmation.coverage.conditions');check(conditions.find(x=>x.line==='共同条件').required_count===2,'summary duplicate does not add a third required line');}
  $('material-package-note').value=expected;$('material-package-reason').value='SYNTHETIC explicit two-slot package confirmation';
  const count=calls.filter(c=>c.method==='POST').length;await $('material-package-'+action).onclick();
  check(calls.filter(c=>c.method==='POST').length===count,'unchecked package confirmation sends no POST');
  check(!Object.keys(storage).some(k=>k.startsWith('parkweave.material-package.v1.')),'unchecked confirmation creates no phantom handle');
  $('material-package-confirm').checked=true;if(both)transport.dropPath='/plan-material-package/commands';
  await $('material-package-'+action).onclick();
  if(both){
    check(Object.keys(storage).some(k=>k.startsWith('parkweave.material-package.v1.')),'committed lostACK retains original opaque reference');
    const n=calls.length;p=page(config,storage,calls,transport);({$,run}=p);
    await run(`loadPreparation(${JSON.stringify(config.A.preparation_id)},{role:'enterprise_operator'})`);await $('material-package-recover').onclick();
    check(calls.slice(n).every(c=>c.method==='GET'),'cold package recovery only GETs original key');
  }
  check(run('materialPackageView.note.text')===expected&&run('materialPackageView.note.origin')==='MANUAL',$('material-package-status').textContent);
  check(run('materialPackageView.package_confirmation.active')===true,'successful explicit POST enables package mode');
  check(!run('materialPackageView.note.text').includes(config.summaryIncoming.split('\n')[0]),'summary is not forced into M');
  await control('assert_decision_not_adopted');await control('remember_decision');await $('opp-read').onclick();await run(`previewOpportunityPlan(${JSON.stringify(card)})`);
  check(run('opportunityPlanView.can_adopt')&&run('opportunityPlanView.affected.length')===5,'actual two-slot decision permits only explicit original five-step ADOPT');
  $('service-plan-reason').value='SYNTHETIC explicit original same-plan ADOPT';$('opp-plan-confirm').checked=true;await control('before_adopt');await $('opp-plan-adopt').onclick();await control('after_adopt');
  for(const adapter of ['P1','P2','P3','P4','P5']){
    await control({P1:'review_material',P2:'relink_resources',P3:'reoffer_accept',P4:'new_report_ack',P5:'revalidate_local'}[adapter]);
    await run(`loadServiceCasePlan(${JSON.stringify(config.A.preparation_id)})`);const id=run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).id`);
    $('service-plan-reason').value='SYNTHETIC actual '+adapter+' VERIFY';await run(`servicePlanWrite('VERIFY',${JSON.stringify(id)})`);
    check(run(`servicePlanView.steps.find(s=>s.adapter_id===${JSON.stringify(adapter)}).state`)==='VERIFIED',$('service-plan-error').textContent);
  }
  await $('goal-results-read').onclick();check(run('goalResultView.results.length')===6&&run('goalResultView.state')==='LOCAL_OUTPUTS_VERIFIED','actual six original goal outputs');
  await $('case-worklist-read').onclick();const seen=[];for(let i=0;i<4;i++){const latest=[...calls].reverse().find(c=>c.worklist_items);check(!!latest,'actual original worklist response');seen.push(...latest.worklist_items);if($('case-worklist-next').hidden)break;await $('case-worklist-next').onclick();}check($('case-worklist-next').hidden&&seen.length===2&&seen.some(r=>r.case_id===config.A.case_id)&&seen.some(r=>r.case_id===config.B.case_id),'complete bounded original worklist pagination contains both Cases');check(seen.every(r=>r.evidence_verified===false&&r.case_goal_completed===false),'worklist states do not imply fact or goal verification');
  await control('final_evidence');output({manual_preserved:true,controlled_committed_response_loss:both});process.exit(0);
})().catch(error=>{console.error(JSON.stringify({message:error.message,stack:error.stack,diagnostics}));process.exit(1);});
