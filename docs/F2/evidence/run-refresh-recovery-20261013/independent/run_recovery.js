// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync(process.argv[3]||'src/parkweave/web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0,nextNonce=900;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.id='';this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.options=[];this.listeners={};}
 append(...x){for(const e of x)if(e&&typeof e==='object')e.parentElement=this;this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 reset(){}addEventListener(n,f){this.listeners[n]=f;}setAttribute(){}removeAttribute(){}
 closest(selector){let e=this;while(e){for(const part of selector.split(',')){const t=part.trim();if((t.startsWith('#')&&e.id===t.slice(1))||['button','form','a'].includes(t)&&e.tagName.toLowerCase()===t)return e;}e=e.parentElement;}return null;}querySelectorAll(){return [];}scrollIntoView(){this.scrolled=true;}
 get firstElementChild(){return this.children[0];}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
const elements=new Map(),$=name=>{if(!elements.has(name))elements.set(name,new Element());elements.get(name).id=name;return elements.get(name);};
const store={},calls=[],events=[];
const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},
 {ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
const context=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,
 crypto:{randomUUID:()=>id(nextNonce++)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},
 Element,document:{getElementById:$,createElement:t=>new Element(t),querySelectorAll:()=>[],body:new Element('body'),addEventListener:(...a)=>events.push(a),execCommand:()=>false},
 window:{addEventListener:(...a)=>events.push(a)},
 fetch:(path,options)=>new Promise((resolve,reject)=>calls.push({path,options,resolve,reject}))});
vm.runInContext(code,context);$('token').value='SYNTHETIC_SESSION_A';
const run=s=>vm.runInContext(s,context),tick=()=>new Promise(r=>setImmediate(r));
function finish(call,status,value){call.resolve({status,ok:status>=200&&status<300,json:async()=>value});}
function projection(target,prep=id(3),receipt=id(4)){
 return {scope:'CURRENT_OWNER_SYNTHETIC_CASE_WORKLIST',read_only:true,automatically_replayed:false,recorded_states_only:true,next_after:null,
 items:[{case_id:id(1),run_id:id(2),preparation_id:prep,receipt_step_id:target==='receipt'?receipt:null,title:'SYNTHETIC item',label:'recorded',attention:'WAITING_RECEIPT',waiting_on:'OWNER',open_target:target,evidence_verified:false,case_goal_completed:false,resource_release_required_separately:false}]};
}
async function queue(target,prep,receipt){const p=$('case-worklist-read').onclick();finish(calls.at(-1),200,projection(target,prep,receipt));await p;return $('case-worklist-items').children[0].children.find(e=>e.tagName==='button');}
function material(){return {preparation:{id:id(3),case_id:id(1),run_id:id(2),owner_id:'fixture-a',state:'IN_PREPARATION',revision:1,goal:'PRIVATE_MATERIAL_A'},current_materials:[{id:id(6),slot:'need_summary',version:1,text:'PRIVATE_BODY_A',source_kind:'USER_STATEMENT',source_label:'SYNTHETIC'}],material_history:[],history:[]};}
function receipt(){return {step:{id:id(4),preparation_id:id(5),case_id:id(7),run_id:id(8),state:'AWAITING_RECEIPT',revision:1,goal:'CURRENT_RECEIPT_B'},role:'enterprise_operator',dependency:'CURRENT',is_current_step:true,current_receipt:null,receipt_history:[],history:[],local_execution:{}};}
async function flushOtherGets(){for(let i=0;i<12;i++){for(const c of calls){if(!c.finished){c.finished=true;finish(c,500,{});}}await tick();}}

function resourceView(){return {case_id:id(1),case_state:'NEEDS_INPUT',preparation_id:id(3),preparation_revision:1,link_revision:0,current:null,history:[]};}
function resourceCatalog(){return {preparation_revision:1,ready:true,items:[{eligible:true,combination:{id:id(11),members:[{resource_name:'SYNTHETIC_ROOM',starts_at:'2026-10-14',ends_at:'2026-10-15'}]}}]};}


async function submitIntake(candidate=false,unknown=false){
 $('goal').value='SYNTHETIC_INDEPENDENT_INTAKE';for(const f of ['region','employees','service_need'])$('candidate-'+f).value=f==='employees'?'42':'SYNTHETIC_'+f;
 const command=$(candidate?'candidate-intake':'intake').onsubmit({preventDefault(){}}),post=calls.at(-1);check(post.path==='/api/runs');check(post.options.method==='POST');
 if(unknown){post.reject(Error('SYNTHETIC_LOST_POST'));await command;$('run').value=id(21);}else{finish(post,201,{run_id:id(21)});await command;check($('run').value===id(21));}
 check(run('entryWriteRequests.size')===1);check(run('[...entryWriteRequests.values()][0].observed')===!unknown);return post;
}
if(mode==='cold_owned'){
 const lines=require('readline').createInterface({input:process.stdin}),replies=[];lines.on('line',line=>{const next=replies.shift();if(next)next(JSON.parse(line));});
 context.fetch=async(path,options={})=>{calls.push({path,options});console.log(JSON.stringify({request:{path,options}}));const x=await new Promise(resolve=>replies.push(resolve));return {status:x.status,ok:x.status>=200&&x.status<300,json:async()=>x.body};};
}
(async()=>{
 if(mode==='cold_owned'){
  $('goal').value='SYNTHETIC independent first intake';await $('intake').onsubmit({preventDefault(){}});check(run('entryWriteRequests.size')===1);const first=$('run').value;check(!!first);
  await $('refresh').onclick();check(run('entryWriteRequests.size')===0);check(calls.at(-1).path==='/api/runs/'+first);
  await $('case-worklist-read').onclick();const item=$('case-worklist-items').children.find(e=>e.children.some(c=>c.textContent.includes('SYNTHETIC independent first intake')));const button=item?.children.find(e=>e.tagName==='button');check(!!button);await button.onclick();check($('run').value===first);
  await $('prep-catalog').onclick();$('prep-reviewer').value=run('prepCatalog.reviewers[0].id');$('prep-goal').value='SYNTHETIC independent cold preparation';
  await $('prep-create').onsubmit({preventDefault(){}});check(run('preparationView!==null'));check(run('entryWriteRequests.size')===0);check($('run').value!==first);const prep=run('preparationId');
  const runPost=calls.filter(c=>c.path==='/api/runs'&&c.options.method==='POST');check(runPost.length===2);check(runPost[0].options.headers['Idempotency-Key']!==runPost[1].options.headers['Idempotency-Key']);check(calls.some(c=>c.path==='/api/runs/'+$('run').value&&c.options.method==='GET'));
  $('prep-slot').value='need_summary';$('prep-text').value='SYNTHETIC independent material';$('prep-source-kind').value='DOCUMENT_EXCERPT';$('prep-source-label').value='SYNTHETIC independent document';
  await $('prep-evidence').onsubmit({preventDefault(){}});check(run('prepCommandPending===null'));check(run('preparationView.current_materials.length')===1);check(run('entryWriteRequests.size')===0);check(run('preparationId')===prep);
  await $('case-worklist-read').onclick();const card=$('case-worklist-items').children.find(e=>e.children.some(c=>c.textContent.includes('SYNTHETIC independent cold preparation')));const open=card?.children.find(e=>e.tagName==='button');check(!!open);await open.onclick();check(run('preparationId')===prep);check(run('preparationView.current_materials.length')===1);check(calls.filter(c=>c.options.method==='POST').length===4);
 }else if(mode.startsWith('prep_')){
  const catalog=$('prep-catalog').onclick();finish(calls.at(-1),200,{services:[{service_id:'synthetic-material-preparation',version:1,name:'SYNTHETIC',source:{kind:'SYNTHETIC',statement:'SYNTHETIC'}}],reviewers:[{id:'prep-specialist-fixture-a'}]});await catalog;
  $('prep-reviewer').value='prep-specialist-fixture-a';$('prep-goal').value='SYNTHETIC independent prep';const create=$('prep-create').onsubmit({preventDefault(){}}),post=calls.at(-1);check(post.path==='/api/runs');check(post.options.method==='POST');
  if(mode==='prep_unknown'){post.reject(Error('SYNTHETIC_LOST_PREP_RUN_POST'));await create;check(run('entryWriteRequests.size')===1);check(!run('[...entryWriteRequests.values()][0].observed'));const poll=run("prepCall('/api/runs/"+id(22)+"','GET')");finish(calls.at(-1),200,{id:id(22),state:'SUCCEEDED'});await poll;check(run('entryWriteRequests.size')===1);}
  else{finish(post,201,{run_id:id(22)});await tick();check(calls.at(-1).path==='/api/runs/'+id(22));finish(calls.at(-1),200,{id:mode==='prep_wrong_binding'?id(23):id(22),state:'SUCCEEDED'});await tick();
   if(mode==='prep_wrong_binding'){await create;check(calls.filter(c=>c.options.method==='POST').length===1);check(run('entryWriteRequests.size')===1);check(!run('[...entryWriteRequests.values()][0].verified'));}
   else{check(run('[...entryWriteRequests.values()].find(op=>op.path==="/api/runs").verified')===true);check(calls.at(-1).path==='/api/preparations');finish(calls.at(-1),500,{detail:'SYNTHETIC_STOP_AFTER_VERIFIED_POLL'});await create;check(calls.filter(c=>c.options.method==='POST').length===2);}
  }
 }else{
  await submitIntake(mode==='candidate_success',mode==='intake_unknown');const before=calls.length;
  if(mode==='nonrun_cannot_prove'){const read=run("prepCall('/api/preparation-catalog','GET')");finish(calls.at(-1),200,{id:id(21),run_id:id(21)});await read;check(run('entryWriteRequests.size')===1);check(!run('[...entryWriteRequests.values()][0].verified'));}
  else{if(mode==='intake_wrong_path')$('run').value=id(22);const refresh=$('refresh').onclick().catch(()=>{});await tick();check(calls.length===before+1);check(calls.at(-1).options.method==='GET');finish(calls.at(-1),200,{id:mode==='intake_wrong_response'?id(23):mode==='intake_wrong_path'?id(22):id(21),state:'SUCCEEDED'});await refresh;
   const negative=['intake_unknown','intake_wrong_path','intake_wrong_response'].includes(mode);check(run('entryWriteRequests.size')===(negative?1:0));check(calls.filter(c=>c.options.method==='POST').length===1);
   if(!negative){const catalog=$('prep-catalog').onclick();check(calls.at(-1).path==='/api/preparation-catalog');finish(calls.at(-1),200,{services:[],reviewers:[]});await catalog;check(run('entryWriteRequests.size')===0);}
  }
 }
 console.log(JSON.stringify({mode,checks,result:'PASS',scope:'FULL_ORIGINAL_HTML_REAL_HANDLERS_NO_ENTRY_MOCK'}));if(mode==='cold_owned')process.exit(0);
})().catch(e=>{console.error(e.stack);if(mode==='cold_owned')process.exit(1);process.exitCode=1;});
