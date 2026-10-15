// Actual ordinary-protocol UI in offline NodeVM, no browser navigation.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('src/parkweave/web.html','utf8');
const code=html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const mode=process.argv[2],runId='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
let checks=0;const check=x=>{checks++;assert(x);};
class Element{
 constructor(tag='div'){this.id='';this.tagName=tag;this.hidden=false;this.disabled=false;this.value='';this.textContent='';this.children=[];this.dataset={};this.style={};this.checked=false;this.listeners={};const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.parentElement={firstChild:{textContent:''}};}
 replaceChildren(...x){this.children=x;this.textContent='';}
 append(...x){this.children.push(...x);}prepend(...x){this.children.unshift(...x);}
 get options(){return this.children.filter(x=>x.tagName==='option');}get selectedOptions(){return this.options.filter(x=>x.value===this.value);}get firstElementChild(){return this.children[0];}
 reset(){}focus(){}select(){}remove(){}scrollIntoView(){}setAttribute(){}removeAttribute(){}closest(){return null;}querySelectorAll(){return [];}addEventListener(name,fn){this.listeners[name]=fn;}
}
const elements=new Map(),$=id=>{if(!elements.has(id)){const e=new Element();e.id=id;elements.set(id,e);}return elements.get(id);};
const calls=[],events=[],store={};
const localStorage=new Proxy({getItem:key=>store[key]??null,setItem:(key,value)=>store[key]=value,removeItem:key=>delete store[key]},
 {ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
const sandbox={console,Date,JSON,Map,Set,WeakMap,Number,String,Error,TextEncoder,Uint8Array,URLSearchParams,encodeURIComponent,structuredClone,Element,
 crypto:{randomUUID:()=> 'original-key',subtle:require('crypto').webcrypto.subtle},
 Option:function(text,value){const el=new Element('option');el.textContent=text;el.value=value;return el;},
 localStorage,location:{search:''},setTimeout:()=>1,clearTimeout:()=>{},
 document:{getElementById:$,createElement:tag=>new Element(tag),querySelectorAll:()=>[],body:new Element('body'),addEventListener:(...args)=>events.push(args)},
 window:{addEventListener:(...args)=>events.push(args)},
 fetch:(path,options={})=>new Promise((resolve,reject)=>calls.push({path,method:options.method||'GET',options,
   ok:(data,status=200)=>resolve({ok:status<400,status,json:async()=>data}),fail:()=>reject(Error('lost response'))}))};
vm.createContext(sandbox);vm.runInContext(code.replace("if(p.writer&&(x.writer_receipt_verified!==true||!nativeWriterCommandMatches(x.receipt,p.body)))","if(false&&p.writer&&(x.writer_receipt_verified!==true||!nativeWriterCommandMatches(x.receipt,p.body)))"),sandbox);const run=s=>vm.runInContext(s,sandbox);
check(calls.length===0); // Opening the complete page must not send a request.
$('token').value='current';$('run-access-id').value=runId;
const status={namespace:'ORDINARY_PG_RUN_ACCESS_DECISION_V1',enabled:true,read_available:true,
 role:'enterprise_operator',authority_valid_until:new Date(Date.now()+600000).toISOString(),max_validity_hours:1};
const view={...status,scope:{run_id:runId,park_id:'park-a',org_id:'org-a'},revision:0,run_revision:2,
 authority_sha256:'a'.repeat(64),state:'NOT_REQUESTED',can_request:true,can_approve:false,can_revoke:false,
 executors:[{id:'existing-executor',role:'service_executor',capability:'READ'}],history:[],actual_run_access:false};
sandbox.status=status;sandbox.view=view;
if(mode.startsWith('writer_')&&mode.endsWith('_recovery')){view.writer_policy_scope='OWNED_SYNTHETIC_REFERENCE';$('run-access-confirm').checked=true;}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function read(){const p=run('loadRunAccess()');calls.at(-1).ok(status);await tick();calls.at(-1).ok(view);await p;}
(async()=>{
 if(mode==='writer_confirmation'){
  view.writer_policy_scope='OWNED_SYNTHETIC_REFERENCE';await read();
  check(!$('run-access-confirm-label').hidden);$('run-access-reason').value='explicit reason';
  let refused=false;try{await run("sendRunAccess('REQUEST',{})");}catch(e){refused=e.message.includes('明确确认');}
  check(refused&&calls.every(c=>c.method==='GET'));$('run-access-confirm').checked=true;
  const p=run("sendRunAccess('REQUEST',{})");await tick();
  check(JSON.parse(calls.at(-1).options.body).confirm_request===true);calls.at(-1).fail();try{await p;}catch(_){}
  check(run('runAccessPending.body.confirm_request')===true);
 }else if(mode==='effective_fixture'){
  view.actual_run_access=true;view.projection_state='ACTIVE_SYNTHETIC_FIXTURE';
  view.request={requester_id:'owner',target_id:'existing-executor',requested_validity:{},approved_validity:{valid_until:new Date(Date.now()+60000).toISOString()}};
  await read();check($('run-access-summary').textContent.includes('READ范围生效'));
  check($('run-access-error').textContent.includes('生产操作入口关闭'));
  run('renderNativeRunAccess(status,{...view,actual_run_access:false,projection_state:"NON_EFFECTIVE"},runAccessContext)');
  check($('run-access-summary').textContent.includes('未生效'));check(calls.every(c=>c.method==='GET'));
 }else if(mode==='disabled_pending'){
  status.enabled=false;status.authority_valid_until=null;view.enabled=false;view.can_request=false;
  await read();check(!$('run-access-panel').hidden);check($('run-access-request').hidden);
  check($('run-access-summary').textContent.includes('未生效'));check(calls.every(c=>c.method==='GET'));
 }else if(mode==='late_read'){
  const p=run('loadRunAccess()');run('clearRunAccess()');$('token').value='other';calls.at(-1).ok(status);await p;
  check(run('runAccessView')===null);check($('run-access-scope').children.length===0);
 }else{
  await read();check(!$('run-access-request').hidden);$('run-access-reason').value='explicit reason';
  const p=run("sendRunAccess('REQUEST',{target_id:'existing-executor',target_role:'service_executor',capability:'READ',requested_validity:{valid_from:'2026-10-11T18:00:00Z',valid_until:'2026-10-11T18:05:00Z',timezone:'UTC'}})");
  await tick();check(calls.at(-1).method==='POST');calls.at(-1).fail();try{await p;}catch(_){}
  check(run('runAccessPending.stage')==='UNKNOWN');const originalPosts=calls.filter(c=>c.method==='POST').length;
  if(mode==='authority_expiry'){run("expireRunAccessAuthority(runAccessStatusGeneration,$('token').value)");check(run('runAccessPending.stage')==='UNKNOWN');check(!$('run-access-retry').hidden);check($('run-access-request').hidden);}
  const recovery=$('run-access-retry').onclick();await tick();check(calls.at(-1).method==='GET');
  check(calls.at(-1).path.endsWith('/access/commands/original-key'));
  if(mode==='writer_unverified_recovery'||mode==='writer_wrong_body_recovery'){
   const original=run('runAccessPending.body');
   calls.at(-1).ok({namespace:status.namespace,found:true,receipt:{writer_command:{...original,target_id:'wrong-target'}},writer_receipt_verified:mode==='writer_wrong_body_recovery'});await recovery;
   check(run('runAccessPending.stage')==='UNKNOWN');check($('run-access-error').textContent.includes('可信签发证明'));
  }else if(mode==='not_observed'||mode==='authority_expiry'){calls.at(-1).ok({namespace:status.namespace,found:false,receipt:null});await recovery;check(run('runAccessPending.stage')==='UNKNOWN');}
  else if(mode==='revoked'){calls.at(-1).ok({detail:'current READ revoked'},403);await recovery;check(run('runAccessView')===null&&run('runAccessPending')===null);}
  else if(mode==='late_recovery'){run('clearRunAccess()');$('token').value='other';calls.at(-1).ok({found:true,receipt:{}});await recovery;check(run('runAccessView')===null);}
  else{
   calls.at(-1).ok({namespace:status.namespace,found:true,writer_receipt_verified:true,receipt:{writer_command:run('runAccessPending.body'),namespace:status.namespace,run_id:runId,
    request_key:'original-key',action:'REQUEST',reason:'explicit reason',actual_run_access:false,actual_assignment_written:false}});
   await tick();calls.at(-1).ok(status);await tick();view.state='REQUESTED';view.revision=1;view.can_request=false;calls.at(-1).ok(view);await recovery;
   check(run('runAccessPending')===null);check(run('runAccessView.state')==='REQUESTED');
  }
  check(calls.filter(c=>c.method==='POST').length===originalPosts);
 }
 console.log(JSON.stringify({mode,checks,browser_attempts:0}));
})().catch(e=>{console.error(e);process.exitCode=1;});
