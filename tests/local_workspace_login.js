/* Login adapter contract only: no browser, DB, real identity or business pass. */
const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto').webcrypto;
const pending=require('../src/parkweave/local_command_pending.js');
const code=fs.readFileSync('src/parkweave/local_workspace_login.js','utf8');
function fixture(){
 const nodes=new Map(),events=[],calls=[],stored=new Map(),windows={},location=[];
 const get=id=>{if(!nodes.has(id))nodes.set(id,{value:'',hidden:false,disabled:false,textContent:'',dispatchEvent:e=>events.push([id,e.type])});return nodes.get(id);};
 const actor={id:'SYNTHETIC-OWNER',org_id:'SYNTHETIC-ORG',park_id:'SYNTHETIC-PARK',role:'enterprise_operator'};
 const identity={bearer:'PUBLIC_SYNTHETIC_TEST_ONLY',actor,installation_id:'a'.repeat(64)};
 let businessPending=false,materialPending=null,hold=null,replyStatus=200,replyBody=null;
 const storage={getItem:k=>stored.get(k)??null,setItem:(k,v)=>stored.set(k,v),removeItem:k=>stored.delete(k)};
 const context=vm.createContext({document:{getElementById:get,body:{dataset:{localWorkspace:'locked'}}},
  fetch:async(path,opt={})=>{calls.push({path,opt});if(hold)await hold;return {ok:replyStatus<400,status:replyStatus,json:async()=>replyBody??identity};},
  window:{addEventListener:(k,fn)=>windows[k]=fn},location:{assign:x=>location.push(x)},
  crypto,TextEncoder,Uint8Array,Event:class{constructor(type){this.type=type;}},localStorage:storage,
  navigator:{locks:{request:async(k,opt,fn)=>fn()}},ParkWeavePending:pending,
  preparationClearRefusal:()=>null,activeEntryWriteFlow:null,entryWriteRequests:new Map(),originalStoredWritePending:()=>businessPending,
  entryFetch:()=>{throw Error('unexpected business tracker call');}});
 vm.runInContext(code,context);get('local-workspace-account').value='enterprise';
 async function login(){get('local-workspace-password').value='PUBLIC_SYNTHETIC_PASSWORD';await get('local-workspace-login').onsubmit({preventDefault(){}});}
 return {nodes,get,events,calls,stored,context,windows,location,identity,storage,login,
  pending(v){businessPending=v;},hold(v){hold=v;},reply(status,body){replyStatus=status;replyBody=body;}};
}
(async()=>{
 let f=fixture();await f.login();assert.equal(f.get('token').value,f.identity.bearer);assert.equal(f.context.document.body.dataset.localWorkspace,'active');assert.equal(f.get('local-workspace-password').value,'');assert.equal(f.calls.length,1);assert.equal(f.calls[0].path,'/api/local/session');assert.equal(f.calls[0].opt.redirect,'error');assert.equal(f.calls[0].opt.credentials,'omit');assert.equal(f.stored.size,0);assert.deepEqual(f.events,[['token','input']]);
 f.pending(true);f.get('local-workspace-logout').onclick();assert.equal(f.get('token').value,f.identity.bearer);f.get('local-workspace-materials').onclick();assert.equal(f.location.length,0);
 f.pending(false);f.get('local-workspace-logout').onclick();assert.equal(f.get('token').value,'');assert.deepEqual(f.events,[['token','input'],['token','input']]);assert.equal(f.stored.size,0);
 f=fixture();await f.login();const credential=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(f.identity.bearer))).toString('hex');const journal=pending.journal(f.storage,f.identity.installation_id,f.identity.actor,credential,{request:async(k,o,fn)=>fn()});
 await journal.prepare('/api/runs','12345678-1234-1234-1234-123456789abc','CREATE_RUN',0,'b'.repeat(64),()=>{});const saved=[...f.stored.values()][0];
 await f.context.fetch('/api/preparations');assert.throws(()=>f.context.fetch('/api/runs',{method:'POST'}),/原资料操作/);assert.throws(()=>f.context.entryFetch('/api/runs',{method:'POST'}),/原资料操作/);assert.equal(f.calls.length,2);assert.equal([...f.stored.values()][0],saved);f.get('local-workspace-logout').onclick();assert.equal(f.get('token').value,f.identity.bearer);
 f=fixture();f.stored.set('parkweave-local-pending/1:'+f.identity.installation_id+':'+f.identity.actor.id,'BROKEN');await f.login();assert.equal(f.get('token').value,'');assert.equal(f.context.document.body.dataset.localWorkspace,'locked');assert.equal(f.stored.size,1);f.get('local-workspace-materials').onclick();assert.deepEqual(f.location,['/']);
 f=fixture();f.reply(503,{code:'LOCAL_IDENTITY_STORAGE_UNAVAILABLE',detail:'PRIVATE_SHOULD_NOT_BE_ECHOED'});await f.login();assert.match(f.get('local-workspace-status').textContent,/恢复原受保护身份文件/);assert(!f.get('local-workspace-status').textContent.includes('PRIVATE_SHOULD_NOT_BE_ECHOED'));assert.equal(f.get('token').value,'');
 f=fixture();let release;f.hold(new Promise(r=>release=r));const first=f.login();await f.login();assert.equal(f.calls.length,1);f.windows.pagehide();release();await first;assert.equal(f.get('token').value,'');assert.equal(f.context.document.body.dataset.localWorkspace,'locked');assert.equal(f.get('local-workspace-submit').disabled,false);f.windows.pageshow({persisted:true});assert.equal(f.get('local-workspace-login').hidden,false);assert.equal(f.get('local-workspace-account').disabled,false);
 console.log('PASS existing-provider login, no secret persistence, full input dispatch, UNKNOWN guards, late-response and duplicate-login refusal');
})().catch(e=>{console.error(e.stack);process.exit(1);});
