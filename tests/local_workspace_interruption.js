// Actual page transport/logout/recovery functions over a bounded HTTP fault
// proxy. Node VM contexts represent independent pages, not browser acceptance.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const crypto=require('node:crypto').webcrypto;
const ParkWeavePending=require(process.cwd()+'/src/parkweave/local_command_pending.js');
const page=fs.readFileSync('src/parkweave/local_preparation_web.html','utf8');
const api=page.slice(page.indexOf('async function secretDigest('),page.indexOf('\nasync function perform'));
const fingerprint=page.slice(page.indexOf('function canonical('),page.indexOf("$('recover').onclick="));
const clear=page.slice(page.indexOf('function clearPrivate('),page.indexOf('async function secretDigest('));
const logout=page.slice(page.indexOf("$('logout').onclick="),page.indexOf("$('submit-case').onsubmit="));
const recover=page.slice(page.indexOf("$('recover').onclick="),page.indexOf("window.addEventListener('storage'"));
const disk=new Map(),storage={getItem:k=>disk.get(k)??null,setItem:(k,v)=>disk.set(k,v),removeItem:k=>disk.delete(k)};
let queued=Promise.resolve();const locks={request:(key,options,fn)=>{const next=queued.then(fn);queued=next.catch(()=>{});return next}};
const input=JSON.parse(fs.readFileSync(0,'utf8'));
let sends=0,reads=0,firstSent;
const dispatched=new Promise(resolve=>{firstSent=resolve});
function context(){
 const nodes=new Map();const $=id=>{if(!nodes.has(id))nodes.set(id,{replaceChildren(){},value:'',hidden:false,textContent:''});return nodes.get(id)};
 const c=vm.createContext({console,crypto,TextEncoder,AbortSignal,ParkWeavePending,storage,locks,$,input,
   fetch:async(path,options)=>{if(options.method==='POST'){sends++;firstSent();}else reads++;
     return fetch((options.method==='POST'?input.proxy:input.base)+path,options)}});
 vm.runInContext(`let epoch=1,bearer='',role='',actor='',actorScope=null,selected=null,current=null,run=null,catalog=null,
   unknown=null,pendingJournal=null,credentialHash=null,runCursor=null,pageCursors=[null],pageIndex=0,nextPage=null;
   const feedback=()=>{};const perform=fn=>fn();
   async function identify(value){bearer=value.bearer;actorScope=value.actor;actor=value.actor.id;role=value.actor.role;
     credentialHash=await secretDigest(bearer);pendingJournal=ParkWeavePending.journal(storage,input.installation,actorScope,credentialHash,locks);unknown=pendingJournal.read();}
   async function open(id){current=await api('/api/preparations/'+id);}
   ${api}\n${fingerprint}\n${clear}\n${logout}\n${recover}`,c);
 return c;
}
(async()=>{
 const a=context(),other=context();
 await vm.runInContext('identify(input.identity)',a);await vm.runInContext('identify(input.identity)',other);
 const first=vm.runInContext('api(input.route+"/commands",input.command,input.key)',a);
 const interrupted=assert.rejects(first);await dispatched;
 await assert.rejects(vm.runInContext('api(input.route+"/commands",input.command,crypto.randomUUID())',other));
 await interrupted;assert.equal(sends,1);
 const saved=vm.runInContext('unknown',a);assert.equal(saved.request_key,input.key);
 vm.runInContext("$('logout').onclick()",a);
 assert.equal(vm.runInContext('bearer',a),'');assert.equal(vm.runInContext('unknown',a),null);
 // Even an accidentally retained stale A handle cannot be queried as B.
 a.stale=saved;await vm.runInContext('identify({...input.identity,actor:{...input.identity.actor,id:"other-account"}});',a);
 vm.runInContext('unknown=stale',a);await vm.runInContext("$('recover').onclick()",a);
 assert.equal(reads,0);assert.equal(sends,1);assert(disk.size===1);
 const reopened=context();await vm.runInContext('identify(input.identity)',reopened);
 assert.equal(vm.runInContext('unknown.request_key',reopened),input.key);
 await vm.runInContext("$('recover').onclick()",reopened);
 assert.equal(reads,2);assert.equal(sends,1);assert.equal(disk.size,0);
 assert.equal(vm.runInContext('unknown',reopened),null);
 process.stdout.write('actual HTTP response interrupted; two page transports: one POST; A logout/B zero recovery reads; A reload: original-key GET + current-version GET, no replay\n');
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1});
