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
let checks = 0, diagnostics; const blobs=[]; class OwnedURL extends URL {static createObjectURL(blob){blobs.push(blob);return 'blob:owned-test';} static revokeObjectURL(){}};
const check = (value, description) => { checks++; assert(value, description); };
class Element {
  constructor(tag = 'div') {
    this.tagName = tag; this.children = []; this.dataset = {}; this.textContent = ''; this.value = '';
    const classes=new Set();this.classList={add:(...xs)=>xs.forEach(x=>classes.add(x)),remove:(...xs)=>xs.forEach(x=>classes.delete(x)),contains:x=>classes.has(x),toggle:(x,force)=>{const on=force===undefined?!classes.has(x):!!force;if(on)classes.add(x);else classes.delete(x);return on;}};this.hidden = true; this.disabled = false; this.checked = false; this.listeners = {};
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
    element.hidden=/\bhidden\b/.test(attrs);element.disabled=/\bdisabled\b/.test(attrs);elements.set(element.id, element);
  }
  const $ = id => { if (!elements.has(id)) { const e = new Element(); e.id = id; elements.set(id, e); } return elements.get(id); };
  const walk = e => [e, ...e.children.filter(x => typeof x === 'object').flatMap(walk)];
  const query = selector => [...elements.values()].flatMap(walk).filter(e => selector.split(',').some(s => {
    if (['button', 'form'].includes(s)) return e.tagName === s;
    const m = s.match(/^\[data-([\w-]+)\]$/); return m && Object.hasOwn(e.dataset, m[1].replace(/-([a-z])/g, (_, c) => c.toUpperCase()));
  }));
  const localStorage = new Proxy({getItem: k => storage[k] ?? null, setItem: (k, v) => storage[k] = v, removeItem: k => delete storage[k]}, {ownKeys: () => Object.keys(storage), getOwnPropertyDescriptor: () => ({enumerable: true, configurable: true})});
  const context = vm.createContext({console, Date, JSON, Map, Set, WeakMap, Number, String, Error, TextEncoder, Blob, URL:OwnedURL, URLSearchParams, encodeURIComponent,
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
      if (body.dependency_propagation) call.dependency_propagation_sha256=body.dependency_propagation.sha256;if(body.typed_dependency_preview)transport.lastPreview=body;if(body.resource_dependency_preview){call.resource_graph_sha256=body.resource_dependency_preview.sha256;call.member_state=body.resource_dependency_preview.membership.state;}
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

const until=async predicate=>{for(let i=0;i<500;i++){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,10));}throw Error('bounded original handler settlement not observed');};
const snapshot=p=>p.run(`JSON.stringify({id:noticeId,view:noticeView,context:noticeContext,cursor:noticeNextCursor,loading:noticeListLoading,summary:document.getElementById('notice-summary').textContent,error:document.getElementById('notice-error').textContent,feedback:document.getElementById('page-feedback').textContent,dispatch:dispatchView,receipt:receiptView})`);
(async()=>{
 const config=await initialized,calls=[];diagnostics={calls};
 const owner=page({...config,token:config.tokens.owner},{},calls,{});
 await owner.$('prep-list').click();const item=owner.$('prep-items').children.find(e=>e.tagName==='button');check(!!item,'actual original preparation list');await item.click();
 check(owner.run('preparationId')===config.preparation_id,'exact original preparation row');
 await owner.$('service-plan-prepare').click();check(owner.run('servicePlanView.plan_id')===config.plan_id,'original durable adopted plan');
 check(owner.run('servicePlanView.current_case_step_scope.contract')==='CASE_STEP_ASSIGNMENT_V1','explicit ordinary display metadata');
 check(textOf(owner.$('service-plan-coverage')).includes('受限步骤核对接单'),'ordinary current scope distinguishes original Run contract text');
 check(calls.every(c=>c.method==='GET'),'navigation is GET only');
 const originalReads=[];
 if(config.original_links){
  await owner.$('case-resource-load').click();
  for(const original of config.original_links){
   owner.$('case-resource-recovery-kind').value='LINK';owner.$('case-resource-recovery-key').value=original.key;
   owner.$('case-resource-recovery-fingerprint').value='';
   await owner.$('case-resource-recovery-read').click();
   const text=textOf(owner.$('case-resource-recovery-result'));
   check(text.includes('COMMITTED')&&text.includes(original.link_id)&&text.includes(original.fingerprint),'original LINK key and exact historical identity');
   originalReads.push({key:original.key,text});
  }
  await owner.$('service-plan-prepare').click();
 }
 if(config.verify){
  owner.$('service-plan-reason').value='SYNTHETIC owner explicitly verifies original ordinary output';
  for(const adapter of ['P3','P4']){
   owner.$('service-plan-reason').value='SYNTHETIC independent owner decision '+adapter;
   const card=owner.$('service-plan-steps').children.find(e=>e.dataset.serviceAdapter===adapter);
   const button=card?.children.find(e=>e.dataset.serviceAction==='VERIFY');check(!!button,'original allowed VERIFY '+adapter);await button.click();
   check(owner.run(`servicePlanView.steps.find(s=>s.adapter_id==='${adapter}').state`)==='VERIFIED','durable explicit VERIFY '+adapter);
  }
 }
 if(config.local_action){
  const card=owner.$('service-plan-steps').children.find(e=>e.dataset.serviceAdapter==='P5');
  const open=card?.children.find(e=>e.dataset.serviceOpen==='localcase');
  check(!!open,'original P5 navigation');await open.click();
  check(owner.run('localCaseId')===config.preparation_id,'exact original local record');
  const actions=config.local_action==='CLOSE'?[['local-case-validate','READY'],['local-case-close','LOCAL_RECORD_CLOSED']]:[['local-case-reopen','REOPENED']];
  for(const [button,state] of actions){
   check(!owner.$(button).disabled,'current owner permission '+button);
   owner.$('local-case-reason').value='SYNTHETIC explicit original '+button;
   const before=calls.length;await owner.$(button).click();
   check(owner.run('localCaseView.local_record_state')===state,'durable local record '+state);
   check(calls.slice(before).filter(c=>c.method==='POST'&&c.path.endsWith('/local-case/commands')).length===1,'one explicit original local command');
   check(calls.slice(before).some(c=>c.method==='GET'&&c.path.includes('/local-case/recovery/')),'original GET recovery without resubmit');
  }
  check(owner.run('localCaseView.case_goal_completed')===false,'local closure is not physical fulfillment');
  await owner.$('service-plan-read').click();
  if(config.local_action==='CLOSE'){
   check(owner.run("servicePlanView.steps.find(s=>s.adapter_id==='P5').state")!=='VERIFIED','local close does not automatically VERIFY P5');
   const refreshed=owner.$('service-plan-steps').children.find(e=>e.dataset.serviceAdapter==='P5');
   const verify=refreshed?.children.find(e=>e.dataset.serviceAction==='VERIFY');
   check(!!verify,'original explicit P5 VERIFY');owner.$('service-plan-reason').value='SYNTHETIC explicit independent P5 decision';
   await verify.click();check(owner.run("servicePlanView.steps.find(s=>s.adapter_id==='P5').state")==='VERIFIED','durable P5 owner decision');
  }else{
   check(owner.run('localCaseView.cycle')===2,'reopen starts original next cycle');
  }
 }
 await owner.$('goal-results-read').click();const view=owner.run('goalResultView');check(!!view,'actual goal result button');
 const expectedGoals=config.goal_count||4;
 check(view.state===config.state,'expected current truth');check(view.current_required_goals.length===expectedGoals,'all required goals retained');
 const postCount=calls.filter(c=>c.method==='POST').length;
 const before=calls.filter(c=>c.path.endsWith('/goal-results')).length;
 await owner.$('case-record-pack-generate').click();check(!!owner.run('caseRecordPackView'),'original generate handler');
 await owner.$('case-record-pack-download').click();check(blobs.length===1,'original Blob download');
 const text=await blobs[0].text(),marker='核对数据（UTF-8 JSON，原文按JSON转义；不包含读取凭据）：\n';
 const pack=JSON.parse(text.split(marker)[1]);
 check(pack.scope==='SYNTHETIC_CASE_RECORD_PACK_V1','original pack format');check(pack.state===config.state,'pack retains current truth');
 check(pack.results.length===expectedGoals&&pack.case_goal_completed===false,'complete targets and no fulfillment claim');
 check(calls.filter(c=>c.path.endsWith('/goal-results')).length===before+4,'two fresh GETs per generate and download');
 check(calls.filter(c=>c.method==='POST').length===postCount,'export performs no write');
 check(!text.includes(config.tokens.owner)&&!text.includes(config.tokens.executor),'no sessions in export');
 check(!text.includes('PRIVATE_MATERIAL')&&!text.includes('PRIVATE_OUTLINE')&&!text.includes('SYNTHETIC local receipt'),'no material or receipt bodies');
 const canonical=owner.run('coldCanonical'),sha=require('crypto').createHash('sha256').update(canonical(pack)).digest('hex');
 check(text.includes('核对数据 SHA256：'+sha),'download canonical hash');
 console.log(JSON.stringify({scope:'ORDINARY_CASE_GOAL_RECORD_PACK_REAL_HTML',checks,calls,pack_sha256:sha,pack,
   downloaded_bytes:Buffer.byteLength(text),text,real_browser:false,
   ...(config.capture_truth?{goal_results:view,step_states:owner.run('servicePlanView.steps.map(s=>({adapter_id:s.adapter_id,state:s.state}))'),original_reads:originalReads}: {})}));process.exit(0);
})().catch(e=>{console.error(e.stack);console.error(JSON.stringify(diagnostics));process.exit(1);});
