// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('src/parkweave/web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.options=[];this.listeners={};}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 reset(){}addEventListener(n,f){this.listeners[n]=f;}setAttribute(){}removeAttribute(){}
 closest(){return null;}querySelectorAll(){return [];}scrollIntoView(){this.scrolled=true;}
 focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
const elements=new Map(),$=name=>{if(!elements.has(name))elements.set(name,new Element());return elements.get(name);};
const store={},calls=[],events=[];
const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},
 {ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
const context=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,
 crypto:{randomUUID:()=>id(99)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},
 document:{getElementById:$,createElement:t=>new Element(t),querySelectorAll:()=>[],body:new Element('body'),addEventListener:(...a)=>events.push(a),execCommand:()=>false},
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
(async()=>{
 if(mode==='run_403'){
  $('prep-summary').textContent='PRIVATE_OLD_MATERIAL';$('prep-detail').hidden=false;
  $('receipt-summary').textContent='PRIVATE_OLD_RECEIPT';$('receipt-detail').hidden=false;
  $('resource-current').textContent='PRIVATE_OLD_RESOURCE';
  run("preparationView={preparation:{id:'"+id(3)+"'}};receiptView={step:{id:'"+id(4)+"'}}");
  const button=await queue('run');const p=button.onclick();const c=calls.at(-1);c.finished=true;finish(c,403,{});await p;
  check($('prep-summary').textContent==='');check($('receipt-summary').textContent==='');check($('resource-current').textContent==='');
  check(run('preparationView===null&&receiptView===null'));check($('page-feedback').textContent.includes('权限'));
 }else if(mode==='material_to_receipt'||mode==='material_to_localcase'){
  const button=await queue('materials');const a=button.onclick();await tick();const old=calls.at(-1);if(old.path!=='/api/preparations/'+id(3))console.error(JSON.stringify({harness_setup_error:$('page-feedback').textContent}));check(old.path==='/api/preparations/'+id(3));old.finished=true;
  const next=await queue(mode==='material_to_receipt'?'receipt':'localcase',id(5),id(4));const b=next.onclick();const current=calls.at(-1);current.finished=true;
  if(mode==='material_to_receipt')finish(current,200,receipt());else finish(current,500,{});
  await b;finish(old,200,material());await tick();console.error(JSON.stringify({phase:'before_extra_gets',prep:$('prep-summary').textContent,receipt:$('receipt-summary').textContent,feedback:$('page-feedback').textContent,paths:calls.map(c=>c.path)}));check(!$('prep-summary').textContent.includes('PRIVATE_MATERIAL_A'));await flushOtherGets();await a;
  check(!$('prep-summary').textContent.includes('PRIVATE_MATERIAL_A'));check(!$('prep-materials').children.some(e=>JSON.stringify(e).includes('PRIVATE_BODY_A')));
  check(run('preparationView===null'));if(mode==='material_to_receipt')check($('receipt-summary').textContent.includes('CURRENT_RECEIPT_B'));
 }
 check(calls.every(c=>!c.options.method||c.options.method==='GET'));
 console.log(JSON.stringify({mode,checks,scope:'FULL_ORIGINAL_PAGE_NODE_VM_ONLY_NO_ENTRY_MOCKS'}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
