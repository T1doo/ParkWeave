// Original page transport/journal/recovery over a real SQL-backed HTTP fault
// bridge. VM contexts model reloads/tabs; this is not browser pixel acceptance.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const crypto=require('node:crypto').webcrypto;
const ParkWeavePending=require(process.cwd()+'/src/parkweave/local_command_pending.js');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const page=fs.readFileSync('src/parkweave/local_preparation_web.html','utf8');
const transport=page.slice(page.indexOf('async function secretDigest('),page.indexOf('\nasync function perform'));
const recovery=page.slice(page.indexOf('function canonical('),page.indexOf("window.addEventListener('storage'"));
const disk=new Map(),storage={getItem:k=>disk.get(k)??null,setItem:(k,v)=>disk.set(k,v),removeItem:k=>disk.delete(k)};
let queue=Promise.resolve(),postCount=0,getCount=0;
const locks={request:(key,options,fn)=>{const result=queue.then(fn);queue=result.catch(()=>{});return result}};
function context(identity){
 const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,{value:'',textContent:''});return nodes.get(id)};
 const c=vm.createContext({crypto,TextEncoder,AbortSignal,ParkWeavePending,$,storage,locks,identity,
  interrupt:false,fetch:async(path,options)=>{
   if(options.method==='POST')postCount++;else getCount++;
   const truncate=c.interrupt&&options.method==='POST';if(truncate)c.interrupt=false;
   return fetch(input.base+path,{...options,headers:{...options.headers,...(truncate?{'X-Test-Truncate':'1'}:{})}});
  }});
 vm.runInContext(`let bearer='',role='',actor='',actorScope=null,epoch=1,unknown=null,pendingJournal=null,
 credentialHash=null,selected=null,current=null,run=null;const feedback=()=>{},perform=fn=>fn();
 async function open(id){current=await api('/api/preparations/'+id);selected=id;}
 async function identify(){bearer=identity.bearer;actorScope=identity.actor;actor=actorScope.id;role=actorScope.role;
 credentialHash=await secretDigest(bearer);pendingJournal=ParkWeavePending.journal(storage,'a'.repeat(64),actorScope,credentialHash,locks);unknown=pendingJournal.read();}
 ${transport}\n${recovery}`,c);
 return c;
}
async function ready(who){const c=context(input.actors[who]);await vm.runInContext('identify()',c);return c;}
async function send(c,path,body,interrupt=false){
 c.path=path;c.body=body;c.key=crypto.randomUUID();c.interrupt=interrupt;
 const result=vm.runInContext('api(path,body,key)',c);
 if(interrupt){await assert.rejects(result);assert(vm.runInContext('unknown',c));return;}
 return result;
}
async function recover(c){await vm.runInContext("$('recover').onclick()",c);assert.equal(vm.runInContext('unknown',c),null);}
let recovered=0,otherReads=0,historical=false,tampered=false;
async function reloadRecover(c,who,mutate){
 const saved=vm.runInContext('unknown',c),before=postCount;
 const b=await ready('fixture-b');b.stale=saved;vm.runInContext('unknown=stale',b);
 const reads=getCount;await vm.runInContext("$('recover').onclick()",b);otherReads+=getCount-reads;
 assert.equal(postCount,before);assert.equal(getCount,reads);
 const a=await ready(who);assert.equal(vm.runInContext('unknown.request_key',a),saved.request_key);
 if(mutate)await mutate(a);
 await recover(a);assert.equal(postCount,before);recovered++;return a;
}
(async()=>{
 let e=await ready('fixture-a');
 await send(e,'/api/runs',{goal:'SYNTHETIC interrupted request recovery',source:'SYNTHETIC'},true);
 e=await reloadRecover(e,'fixture-a',async a=>{
  const original=vm.runInContext('unknown',a);a.saved=original;
  vm.runInContext("unknown={...saved,fingerprint:'0'.repeat(64)};storage.setItem(pendingJournal.key,JSON.stringify(unknown))",a);
  await vm.runInContext("$('recover').onclick()",a);assert(vm.runInContext('unknown',a));tampered=true;
  vm.runInContext('unknown=saved;storage.setItem(pendingJournal.key,JSON.stringify(saved))',a);
 });
 const run=vm.runInContext('run.id',e);
 await send(e,'/api/preparations',{run_id:run,service_id:'synthetic-material-preparation',service_version:1,
  reviewer_id:'prep-specialist-fixture-a'},true);
 e=await reloadRecover(e,'fixture-a');const id=vm.runInContext('selected',e),route='/api/preparations/'+id+'/commands';
 let revision=1;
 for(const slot of ['need_summary','material_outline']){
  const result=await send(e,route,{action:'ADD_EVIDENCE',expected_revision:revision,slot,text:'SYNTHETIC '+slot,
   source_kind:'DOCUMENT_EXCERPT',source_label:'SYNTHETIC v1'});revision=result.revision;
 }
 let r=await ready('prep-specialist-fixture-a');
 await send(r,route,{action:'REQUEST_CHANGES',expected_revision:revision,reason:'\u0085  Inspect current material  \u0085'},true);
 r=await reloadRecover(r,'prep-specialist-fixture-a');revision=vm.runInContext('current.preparation.revision',r);
 await send(r,route,{action:'REVIEW',expected_revision:revision,reason:'\ufeffIndependent review\ufeff'},true);revision++;
 // Another actor can advance the state while the original reviewer has lost
 // the acknowledgement. The exact historical receipt plus current scope/read
 // must recover without undoing or resending either operation.
 const confirmed=await send(e,route,{action:'CONFIRM',expected_revision:revision,reason:'Explicit enterprise confirmation'});
 revision=confirmed.revision;
 r=await reloadRecover(r,'prep-specialist-fixture-a');
 assert.equal(vm.runInContext('current.preparation.revision',r),revision);historical=true;
 await send(e,route,{action:'REOPEN',expected_revision:revision,reason:'\u0085\ufeffExplicit reopen\ufeff\u0085'},true);
 e=await reloadRecover(e,'fixture-a');revision=vm.runInContext('current.preparation.revision',e);
 const reviewed=await send(r,route,{action:'REVIEW',expected_revision:revision,reason:'Review again'});revision=reviewed.revision;
 await send(e,route,{action:'CONFIRM',expected_revision:revision,reason:'Final confirmation'},true);
 // Exercise pre-fix non-evidence handles, whose old page hashed its minimal
 // body rather than the normalized command model. No body is stored on disk.
 e.legacy={action:'CONFIRM',expected_revision:revision,reason:'Final confirmation'};
 await vm.runInContext("(async()=>{unknown={...unknown,fingerprint:await secretDigest(canonical(legacy))};storage.setItem(pendingJournal.key,JSON.stringify(unknown));})()",e);
 e=await reloadRecover(e,'fixture-a');
 assert.equal(vm.runInContext('current.preparation.state',e),'LOCAL_CONFIRMED');
 const absent=await ready('fixture-b');
 absent.fresh=crypto.randomUUID();await vm.runInContext("(async()=>{unknown=await pendingJournal.prepare('/api/runs',fresh,'CREATE_RUN',0,'b'.repeat(64),()=>{});})()",absent);
 const before=postCount;await vm.runInContext("$('recover').onclick()",absent);
 assert(vm.runInContext('unknown',absent));assert.equal(postCount,before);
 process.stdout.write(JSON.stringify({recovered,interrupted_posts:6,other_identity_reads:otherReads,
  tampered_handle_retained:tampered,not_observed_retained:true,historical_receipt_recovered:historical}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1});
