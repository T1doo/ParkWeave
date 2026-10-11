// Actual ordinary-protocol UI in offline NodeVM, no browser navigation.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('src/parkweave/web.html','utf8');
const code=html.slice(html.indexOf('let runAccessGeneration='),html.indexOf('const boundedGoals='));
const mode=process.argv[2],runId='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
let checks=0;const check=x=>{checks++;assert(x);};
class Element{
 constructor(){this.hidden=false;this.disabled=false;this.value='';this.textContent='';this.children=[];this.elements=[];this.options=[];this.parentElement={firstChild:{textContent:''}};}
 replaceChildren(...x){this.children=x;this.options=x;}
 append(...x){this.children.push(...x);this.options.push(...x);}
 reset(){} focus(){} addEventListener(){}
}
const elements=new Map(),$=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
$('token').value='current';$('run-access-id').value=runId;
const calls=[];
const sandbox={$ ,crypto:{randomUUID:()=> 'original-key'},Option:function(text,value){return {text,value};},
 textElement:(tag,text)=>{const el=new Element();el.textContent=text;return el;},
 setTimeout:()=>1,clearTimeout:()=>{},document:{querySelectorAll:()=>[]},receiptView:null,
 fetch:(path,options={})=>new Promise((resolve,reject)=>calls.push({path,method:options.method||'GET',options,
   ok:(data,status=200)=>resolve({ok:status<400,status,json:async()=>data}),fail:()=>reject(Error('lost response'))}))};
vm.createContext(sandbox);vm.runInContext(code,sandbox);const run=s=>vm.runInContext(s,sandbox);
const status={namespace:'ORDINARY_PG_RUN_ACCESS_DECISION_V1',enabled:true,read_available:true,
 role:'enterprise_operator',authority_valid_until:new Date(Date.now()+600000).toISOString(),max_validity_hours:1};
const view={...status,scope:{run_id:runId,park_id:'park-a',org_id:'org-a'},revision:0,run_revision:2,
 authority_sha256:'a'.repeat(64),state:'NOT_REQUESTED',can_request:true,can_approve:false,can_revoke:false,
 executors:[{id:'existing-executor',role:'service_executor',capability:'READ'}],history:[],actual_run_access:false};
sandbox.status=status;sandbox.view=view;
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function read(){const p=run('loadRunAccess()');calls.at(-1).ok(status);await tick();calls.at(-1).ok(view);await p;}
(async()=>{
 if(mode==='disabled_pending'){
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
  if(mode==='not_observed'||mode==='authority_expiry'){calls.at(-1).ok({namespace:status.namespace,found:false,receipt:null});await recovery;check(run('runAccessPending.stage')==='UNKNOWN');}
  else if(mode==='revoked'){calls.at(-1).ok({detail:'current READ revoked'},403);await recovery;check(run('runAccessView')===null&&run('runAccessPending')===null);}
  else if(mode==='late_recovery'){run('clearRunAccess()');$('token').value='other';calls.at(-1).ok({found:true,receipt:{}});await recovery;check(run('runAccessView')===null);}
  else{
   calls.at(-1).ok({namespace:status.namespace,found:true,receipt:{namespace:status.namespace,run_id:runId,
    request_key:'original-key',action:'REQUEST',reason:'explicit reason',actual_run_access:false,actual_assignment_written:false}});
   await tick();calls.at(-1).ok(status);await tick();view.state='REQUESTED';view.revision=1;view.can_request=false;calls.at(-1).ok(view);await recovery;
   check(run('runAccessPending')===null);check(run('runAccessView.state')==='REQUESTED');
  }
  check(calls.filter(c=>c.method==='POST').length===originalPosts);
 }
 console.log(JSON.stringify({mode,checks,browser_attempts:0}));
})().catch(e=>{console.error(e);process.exitCode=1;});
