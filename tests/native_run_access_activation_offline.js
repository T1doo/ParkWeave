// Full production UI script with synthetic DTOs in offline NodeVM. No browser, server or authority issuer.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('src/parkweave/web.html','utf8');
const code=html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const mode=process.argv[2],runId='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
let checks=0;const check=x=>{checks++;assert(x);};
class Element{
 constructor(tag='div'){this.id='';this.tagName=tag;this.hidden=false;this.disabled=false;this.value='';this.textContent='';this.children=[];this.dataset={};this.style={};this.checked=false;this.listeners={};const classes=new Set();this.classList={add:(...x)=>x.forEach(v=>classes.add(v)),remove:(...x)=>x.forEach(v=>classes.delete(v)),contains:x=>classes.has(x)};const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.parentElement={firstChild:{textContent:''}};}
 replaceChildren(...x){this.children=x;this.textContent='';}
 append(...x){this.children.push(...x);}prepend(...x){this.children.unshift(...x);}
 get options(){return this.children.filter(x=>x.tagName==='option');}get selectedOptions(){return this.options.filter(x=>x.value===this.value);}get firstElementChild(){return this.children[0];}
 reset(){}focus(){}select(){}remove(){}scrollIntoView(){}setAttribute(){}removeAttribute(){}closest(){return null;}querySelectorAll(){return [];}addEventListener(name,fn){this.listeners[name]=fn;}
}
const elements=new Map(),$=id=>{if(!elements.has(id)){const e=new Element();e.id=id;elements.set(id,e);}return elements.get(id);};
const calls=[],events=[],store={},timers=new Map();let timerId=0;const clock={now:Date.parse('2026-10-18T12:00:00Z')};class ClockDate extends Date{constructor(...args){super(...(args.length?args:[clock.now]));}static now(){return clock.now;}}
const localStorage=new Proxy({getItem:key=>store[key]??null,setItem:(key,value)=>store[key]=value,removeItem:key=>delete store[key]},
 {ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
const sandbox={console,Date:ClockDate,JSON,Map,Set,WeakMap,Number,String,Error,TextEncoder,Uint8Array,URLSearchParams,encodeURIComponent,structuredClone,Element,
 crypto:{randomUUID:()=> 'original-key',subtle:require('crypto').webcrypto.subtle},
 Option:function(text,value){const el=new Element('option');el.textContent=text;el.value=value;return el;},
 localStorage,location:{search:''},setTimeout:(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;},clearTimeout:id=>timers.delete(id),
 document:{getElementById:$,createElement:tag=>new Element(tag),querySelectorAll:()=>[],body:new Element('body'),addEventListener:(...args)=>events.push(args)},
 window:{addEventListener:(...args)=>events.push(args)},
 fetch:(path,options={})=>new Promise((resolve,reject)=>calls.push({path,method:options.method||'GET',options,
   ok:(data,status=200)=>resolve({ok:status<400,status,json:async()=>data}),fail:()=>reject(Error('lost response'))}))};
vm.createContext(sandbox);vm.runInContext(code,sandbox);const run=s=>vm.runInContext(s,sandbox);
check(calls.length===0);
// Native DOM registration and input state, not replacement production functions.
for(const id of ['run-access-activation-reason','run-access-activation-confirm','run-access-activate'])$('run-access-activation').elements.push($(id));
$('run-access-activation').hidden=true;$('token').value='current';$('run-access-id').value=runId;
const namespace='ORDINARY_PG_RUN_ACCESS_DECISION_V1',activationNamespace='ORDINARY_PG_RUN_ACCESS_ACTIVATION_V1';
const lease='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',caseId='cccccccc-cccc-4ccc-8ccc-cccccccccccc',prepId='dddddddd-dddd-4ddd-8ddd-dddddddddddd';
const status={namespace,enabled:true,read_available:true,read_only:false,role:'enterprise_operator',authority_valid_until:'2026-10-18T12:05:00Z',max_validity_hours:1};
const source={run_id:runId,run_revision:2,input_fingerprint:'c'.repeat(64),owner_id:'existing-owner',park_id:'park-a',org_id:'org-a',preparation_id:prepId,preparation_revision:4,preparation_state:'LOCAL_CONFIRMED',review_sha256:'d'.repeat(64),material_sha256:'d'.repeat(64),case_id:caseId,case_state:'OPEN'};
const view={...status,scope:{run_id:runId,park_id:'park-a',org_id:'org-a'},revision:2,run_revision:4,activation_revision:0,authority_sha256:'a'.repeat(64),activation_policy_sha256:'b'.repeat(64),state:'APPROVED',lease_id:lease,writer_policy_scope:'PRODUCTION_CONTRACT',writer_history_verified:true,activation_enabled:true,can_activate:true,actual_run_access:false,projection_state:'NON_EFFECTIVE',history:[],executors:[],request:{request_id:'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',requester_id:'existing-owner',target_id:'existing-executor',target_role:'service_executor',capability:'READ',approver_id:'existing-reviewer',source,requested_validity:{valid_from:'2026-10-18T11:59:00Z',valid_until:'2026-10-18T12:01:00Z',timezone:'UTC'},approved_validity:{valid_from:'2026-10-18T11:59:00Z',valid_until:'2026-10-18T12:01:00Z',timezone:'UTC'}}};
sandbox.status=status;sandbox.view=view;
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function read(){const p=run('loadRunAccess()');calls.at(-1).ok(status);await tick();calls.at(-1).ok(view);await p;}
const posts=()=>calls.filter(c=>c.method==='POST');
function confirm(){check(!$('run-access-activation').hidden);$('run-access-activation-confirm').checked=true;$('run-access-activation-reason').value='explicit activation reason';}
function submit(){return $('run-access-activation').onsubmit({preventDefault(){}});}
function receipt(){const p=run('runAccessPending');return {namespace:activationNamespace,run_id:runId,actor_id:'existing-owner',request_key:'original-key',action:'ACTIVATE',reason:p.body.reason,state:'ACTIVATED',revision:1,activation_id:'ffffffff-ffff-4fff-8fff-ffffffffffff',lease_id:lease,policy_sha256:'b'.repeat(64),binding:structuredClone(p.capture.binding),actual_run_access:true,actual_assignment_written:true,writer_command:structuredClone(p.body)};}
function recoveryData(r=receipt()){return {namespace,found:true,receipt:r,writer_receipt_verified:true,actual_run_access:false,actual_assignment_written:false};}
function assertUnknown(){check(run('runAccessPending.stage')==='UNKNOWN');check(posts().length===1);check(!$("run-access-retry").hidden);check(run('runAccessPending.key')==='original-key');}
(async()=>{
 await read();
 if(mode==='gates'){
  const cases=[['read_only',true],['read_only',undefined],['writer_policy_scope','OWNED_SYNTHETIC_REFERENCE'],['writer_policy_scope',undefined],['writer_history_verified',false],['can_activate',false],['activation_enabled',false],['enabled',false],['role','park_specialist'],['state','REQUESTED'],['actual_run_access',true],['activation_policy_sha256','bad'],['activation_revision',-1],['namespace','WRONG'],['lease_id','bad']];
  for(const [k,value] of cases){const altered={...view,[k]:value},oldStatus=status.read_only;if(k==='read_only')status.read_only=value;sandbox.altered=altered;run('renderNativeRunAccess(status,altered,runAccessCtx())');check($('run-access-activation').hidden);$('run-access-activation-confirm').checked=true;$('run-access-activation-reason').value='reason';await submit();check(posts().length===0);status.read_only=oldStatus;}
  for(const alter of [v=>delete v.request.source,v=>v.request.source.material_sha256='bad',v=>v.request.source.preparation_revision=0,v=>v.request.source.owner_id='other',v=>v.request.target_id='existing-reviewer',v=>v.request.approved_validity.timezone='LOCAL',v=>v.request.approved_validity.valid_until='2026-10-18T11:59:30Z',v=>v.request.approved_validity.valid_until='2026-10-18T12:06:00Z']){const v=structuredClone(view);alter(v);sandbox.altered=v;run('renderNativeRunAccess(status,altered,runAccessCtx())');check($('run-access-activation').hidden);await submit();check(posts().length===0);}
  const wrongStatus={...status,namespace:'WRONG'};sandbox.wrongStatus=wrongStatus;run('renderNativeRunAccess(wrongStatus,view,runAccessCtx())');check($('run-access-activation').hidden);await submit();check(posts().length===0);
 }else if(mode==='confirmation'){
  $('run-access-activation-reason').value='reason';await submit();check(posts().length===0);$('run-access-activation-confirm').checked=true;$('run-access-activation-reason').value=' ';await submit();check(posts().length===0);check(!$('run-access-activation').hidden);
 }else if(mode==='unicode_blank'){
  confirm();$('run-access-activation-reason').value='\u0085\u0085';await submit();check(posts().length===0);
 }else if(mode==='mutated_snapshot'){
  confirm();view.request.target_id='changed-target';await submit();check(posts().length===0);check($('run-access-error').textContent.includes('来源版本'));
 }else if(mode==='lease_expiry'||mode==='authority_expiry'){
  confirm();clock.now=Date.parse(mode==='lease_expiry'?'2026-10-18T12:01:00Z':'2026-10-18T12:05:00Z');const timer=[...timers.values()].sort((a,b)=>a.ms-b.ms).at(mode==='lease_expiry'?0:-1);timer.fn();check($('run-access-activation').hidden);await submit();check(posts().length===0);
 }else{
  confirm();if(mode==='unicode_reason')$('run-access-activation-reason').value='\u0085explicit activation reason\u0085';const operation=submit();await tick();check(posts().length===1);check(posts()[0].path.endsWith('/access/activate'));
  const body=JSON.parse(posts()[0].options.body);check(Object.keys(body).length===9&&body.action==='ACTIVATE'&&body.confirm_activate===true);check(body.reason==='explicit activation reason');check(posts()[0].options.headers['Idempotency-Key']==='original-key');check($('run-access-activate').disabled);
  if(mode==='post403'){
   posts()[0].ok({detail:'denied'},403);await operation;check(run('runAccessView')===null&&run('runAccessPending')===null);check(run('runAccessActivationBlocked()'));check(run('entryWriteRequests.size')===0);check(run("deniedOperationReferences.get('RUN_ACCESS_ACTIVATE:original-key').id")===runId);check(JSON.stringify([...Object.values(store)]).includes('explicit activation reason')===false);
  }else if(mode==='late_post200'||mode==='late_post403'||mode==='token_aba'){
   $('token').value='other';$('token').oninput();if(mode==='token_aba'){$('token').value='current';$('token').oninput();}
   posts()[0].ok({found:true},mode==='late_post403'?403:200);await operation;check(run('runAccessView')===null);check(run('runAccessActivationBlocked()'));check(calls.length===3);check($('run-access-activation').hidden);
  }else{
   const directUnknown=['timeout','post409','post422','navigation','unknown_expiry','late_get200','late_get403'].includes(mode);
   if(directUnknown){if(mode==='post409'||mode==='post422')posts()[0].ok({detail:'unknown result'},mode==='post409'?409:422);else posts()[0].fail();await operation;assertUnknown();}
   else{posts()[0].ok({namespace:'UNTRUSTED',receipt:{actual_run_access:true}});await tick();check(calls.at(-1).method==='GET');check(calls.at(-1).path.endsWith('/access/commands/original-key'));}
   if(mode==='navigation'){
    run('clearPlan()');check(run('runAccessPending')===null);check(run('runAccessActivationBlocked()'));check(run("Object.keys(deniedOperationReferences.get('RUN_ACCESS_ACTIVATE:original-key')).sort().join(',')")==='id,key,kind');await read();check($('run-access-reference').textContent.includes('original-key'));check($('run-access-activation').hidden);await submit();check(posts().length===1);
   }else{
    let recovering=operation;if(directUnknown){
     if(mode==='unknown_expiry'){clock.now=Date.parse('2026-10-18T12:05:00Z');run("expireRunAccessAuthority(runAccessStatusGeneration,$('token').value)");assertUnknown();check($('run-access-activation').hidden);}
     const count=calls.length;await submit();check(calls.length===count);recovering=$('run-access-retry').onclick();await tick();check(calls.at(-1).method==='GET');check(calls.at(-1).path.endsWith('/access/commands/original-key'));
    }
    if(mode==='auto_get403'){
     calls.at(-1).ok({detail:'current permission denied'},403);await recovering;check(run('entryWriteRequests.size')===0);check(run('runAccessView')===null&&run('runAccessPending')===null);check(run('runAccessActivationBlocked()'));check($('run-access-reference').textContent.includes('original-key'));check(posts().length===1);
    }else if(mode==='late_get200'||mode==='late_get403'){
     const result=recoveryData();$('token').value='other';$('token').oninput();calls.at(-1).ok(result,mode==='late_get403'?403:200);await recovering;check(run('runAccessView')===null);check(run('runAccessActivationBlocked()'));
    }else if(['verified','unicode_reason','history_revoked','history_expired','verified_then_read403'].includes(mode)){
     calls.at(-1).ok(recoveryData());await tick();check(calls.at(-1).path==='/api/run-access/status');
     if(mode==='history_revoked'||mode==='history_expired'){view.actual_run_access=false;view.can_activate=false;view.state='REVOKED';if(mode==='history_expired')clock.now=Date.parse('2026-10-18T12:02:00Z');}
     if(mode==='verified_then_read403'){calls.at(-1).ok({detail:'current read denied'},403);await recovering;check(run('runAccessView')===null);}
     else{calls.at(-1).ok(status);await tick();calls.at(-1).ok(view);await recovering;check(run('runAccessView.actual_run_access')===false);}
     check(run('runAccessPending')===null);check(posts().length===1);check(!run('runAccessActivationBlocked()'));check(run('entryWriteRequests.size')===0);
     const before=calls.length;const fresh=$('run-access-read').onclick();await tick();check(calls.length===before+1&&calls.at(-1).path==='/api/run-access/status');calls.at(-1).ok(status);await tick();calls.at(-1).ok(view);await fresh;check(posts().length===1);
    }else{
     const result=recoveryData();if(mode==='unverified')result.writer_receipt_verified=false;
     else if(mode==='wrong_body')result.receipt.writer_command.reason='other';
     else if(mode==='wrong_source')result.receipt.binding.source.preparation_revision++;
     else if(mode==='wrong_target')result.receipt.binding.executor_id='other';
     else if(mode==='wrong_validity')result.receipt.binding.validity.valid_until='2026-10-18T12:02:00Z';
     else if(mode==='wrong_revision')result.receipt.revision=2;
     else if(mode==='wrong_namespace')result.namespace='WRONG';
     else if(mode==='wrong_receipt_namespace')result.receipt.namespace=namespace;
     else if(mode==='extra_body')result.receipt.writer_command.unexpected=true;
     else {result.found=false;result.receipt=null;}
     calls.at(-1).ok(result);await recovering;assertUnknown();const count=calls.length;await submit();check(calls.length===count);check(run('runAccessView.actual_run_access')===false);
    }
   }
  }
 }
 check(calls.filter(c=>c.method==='POST').length<=1);check(Object.keys(store).length===0);
 console.log(JSON.stringify({mode,checks,browser_attempts:0,real_activation_attempts:0}));
})().catch(e=>{console.error(e);process.exitCode=1;});
