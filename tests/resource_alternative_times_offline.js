// Executes the real resource form code with offline DOM/fetch doubles.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('src/parkweave/web.html','utf8');
const actual=html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const mode=process.argv[2],rid='fa161ea0-b665-4ec5-b345-a070bfec764d';let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.tagName=tag;this.value='';this.textContent='';this.children=[];this.dataset={};this.disabled=false;this.hidden=false;this.checked=false;this.style={};this.listeners={};const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});}
 append(...xs){this.children.push(...xs);}
 prepend(...xs){this.children.unshift(...xs);}
 replaceChildren(...xs){this.children=xs;this.textContent='';}
 querySelectorAll(){return this===elements.get('resource-form')?inputs:[];}
 addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
 setAttribute(){} removeAttribute(name){delete this[name];} closest(){return null;} scrollIntoView(){} focus(){} select(){} remove(){}
 get options(){return this.children.filter(e=>e.tagName==='option');}
 get selectedOptions(){return this.options.filter(e=>e.value===this.value);}
 reset(){for(const el of inputs)el.value='';}
 get firstElementChild(){return this.children[0];}
 replaceWith(){}
}
const elements=new Map(),$=id=>{if(!elements.has(id)){const el=new Element();el.id=id;elements.set(id,el);}return elements.get(id);};
const inputIds=['resource-select','resource-start','resource-end','resource-quantity','resource-ttl','resource-purpose','resource-search-from','resource-search-until'];
const inputs=inputIds.map($),calls=[];
const store={};
const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},{ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
$('run-access-valid-until').parentElement={firstChild:{textContent:''}};
const context=vm.createContext({Date,JSON,Number,String,Map,Set,WeakMap,Error,Infinity,encodeURIComponent,URLSearchParams,structuredClone,TextEncoder,Uint8Array,
 crypto:{randomUUID:()=> '00000000-0000-0000-0000-000000000001',subtle:require('crypto').webcrypto.subtle},
 Option:function(text,value){const e=new Element('option');e.textContent=text;e.value=value;return e;},
 localStorage:storage,setTimeout:()=>1,clearTimeout(){},location:{search:''},window:{addEventListener(){}},
 document:{getElementById:$,createElement:tag=>new Element(tag),querySelectorAll:()=>[],addEventListener(){},body:new Element('body')},
 fetch:(path,options)=>new Promise((resolve,reject)=>calls.push({path,options,resolve,reject}))});
vm.runInContext(actual,context);
function draft(){ $('token').value='PRIVATE_TOKEN_A';$('resource-select').value=rid;$('resource-start').value='2026-10-12T10:00';$('resource-end').value='2026-10-12T11:00';$('resource-quantity').value='2';$('resource-ttl').value='120';$('resource-purpose').value='PRIVATE_PURPOSE';$('resource-search-from').value='2026-10-12T10:00';$('resource-search-until').value='2026-10-12T14:00';$('resource-form').hidden=false;}
draft();
const body=()=>JSON.parse(vm.runInContext('JSON.stringify(resourceAlternativeBody())',context));
function result(){const b=body();return {...b,resource_id:rid,resource_revision:1,preview_only:true,coverage:'SEARCH_WINDOW_GRID_ONLY',ordering:'START_ASC',grid_anchor:b.search_from,grid_minutes:15,scan_limit:100,result_limit:10,scanned_candidates:13,server_time:'2026-10-11T12:00:00Z',items:[{starts_at:'2026-10-12T11:15:00Z',ends_at:'2026-10-12T12:15:00Z',quantity:2}]};}
function finish(i,status,value){calls[i].resolve({ok:status>=200&&status<300,status,json:async()=>value});}
const start=()=> $('resource-alternatives').onclick();
const tick=()=>new Promise(r=>setImmediate(r));
const content=el=>el.textContent+' '+el.children.map(content).join(' ');
const buttons=()=> $('resource-alternative-results').children.filter(e=>e.tagName==='button');
(async()=>{
 if(mode==='choose_fills_only'||mode==='original_flow_explicit'){
  vm.runInContext('resourcePreview={view:{available:true},context:resourceContext()}',context);$('resource-hold').disabled=false;
  const p=start();check($('resource-hold').disabled);finish(0,200,result());await p;check(buttons().length===1);const before=calls.length;buttons()[0].onclick();
  check(calls.length===before&&$('resource-start').value==='2026-10-12T11:15'&&$('resource-end').value==='2026-10-12T12:15'&&$('resource-quantity').value==='2');
  check($('resource-hold').disabled&&vm.runInContext('resourcePreview===null',context)&&buttons().length===0);check($('resource-preview-result').textContent.includes('重新预检'));
  await $('resource-form').onsubmit({preventDefault(){}});check(calls.length===before);
  if(mode==='original_flow_explicit'){
   const pre=$('resource-preview').onclick();check(calls.length===2&&calls[1].path.endsWith('/preview'));finish(1,200,{resource_id:rid,resource_revision:1,available:true,occupied_peak:0,capacity:2,available_quantity:2,server_time:'2026-10-11T12:00:00Z',scope:'SYNTHETIC_LOCAL_RESOURCE_HOLD_ONLY',namespace:'SYNTHETIC',preview_only:true,authority:'LOCAL_AUTHORITY',timezone:'UTC',resource_name:'SYNTHETIC owned resource',source:{kind:'SYNTHETIC',id:'owned-resource-source',revision:'1',statement:'SYNTHETIC original offline response contract'},external_availability:'UNKNOWN',confirmation_required:true,reservation:'NOT_CONFIRMED',external_acceptance:'NOT_SUBMITTED',offline_fulfillment:'NO_EVIDENCE'});await pre;check(!$('resource-hold').disabled);
   const writing=$('resource-form').onsubmit({preventDefault(){}});check(calls.length===3&&calls[2].path.endsWith('/holds')&&calls[2].options.headers['Idempotency-Key']);const h={id:'hold-owned',resource_id:rid,state:'HELD',quantity:2,purpose:'owned',resource_revision:1,starts_at:'2026-10-12T11:15:00Z',ends_at:'2026-10-12T12:15:00Z',expires_at:'2026-10-11T12:02:00Z'};finish(2,201,{hold:h});await writing;
   const card=$('resource-current').children[0],confirm=card.children.find(e=>e.dataset.resourceAction==='confirm');check(!!confirm&&calls.length===3);const confirming=confirm.onclick();check(calls.length===4&&calls[3].path.endsWith('/confirm'));finish(3,200,{hold:{...h,state:'CONFIRMED'}});await confirming;
  }
 }else if(mode==='unknown_bundle_controls'){
  vm.runInContext('bundleBusy=true;bundleBusyContext=null',context);
  const formButtons=['resource-preview','resource-hold','resource-alternatives'].map($);
  context.document.querySelectorAll=()=>formButtons;
  vm.runInContext('bundleControls();',context);
  check(!$('resource-alternatives').disabled&&$('resource-hold').disabled&&$('resource-preview').disabled);
  const p=start();finish(0,200,result());await p;check(buttons().length===1);
  buttons()[0].onclick();check(calls.length===1&&$('resource-hold').disabled&&$('resource-preview').disabled);
  await $('resource-form').onsubmit({preventDefault(){}});check(calls.length===1);
 }else if(mode==='empty_grid'||mode==='truncated_grid'){
  const p=start(),x=result();if(mode==='empty_grid')x.items=[];else x.results_truncated=true;finish(0,200,x);await p;
  check(content($('resource-alternative-results')).includes(mode==='empty_grid'?'所查网格未找到':'还有更晚'));check($('resource-hold').disabled&&calls.length===1);
 }else if(mode==='current_403_clears'){
  $('resource-current').append(new Element());const p=start();finish(0,403,{});await p;
  check($('resource-form').hidden&&$('resource-current').children.length===0&&buttons().length===0);check($('resource-error').textContent.includes('无此资源'));
 }else if(mode==='late_403_other_identity'||mode==='identity_aba_delayed_json'){
  const p=start(),x=result();let resolveBody;
  if(mode==='identity_aba_delayed_json'){calls[0].resolve({ok:true,status:200,json:()=>new Promise(r=>resolveBody=r)});await tick();}
  vm.runInContext('clearResources()',context);draft();$('token').value='PRIVATE_TOKEN_B';$('resource-current').textContent='new identity';
  if(mode==='identity_aba_delayed_json'){vm.runInContext('clearResources()',context);draft();$('resource-current').textContent='newest A';resolveBody(x);}else finish(0,403,{});
  await p;check(!$('resource-form').hidden&&$('resource-current').textContent.includes(mode==='identity_aba_delayed_json'?'newest A':'new identity'));check(buttons().length===0&&$('resource-error').textContent==='');
 }else if(mode.startsWith('change_')){
  const id={'change_resource':'resource-select','change_start':'resource-start','change_end':'resource-end','change_quantity':'resource-quantity','change_search_from':'resource-search-from','change_search_until':'resource-search-until'}[mode];
  const p=start(),x=result();$(id).value+='changed';$(id).oninput();finish(0,200,x);await p;
  check(buttons().length===0&&$('resource-hold').disabled);check($('resource-preview-result').textContent.includes('输入已变化')&&calls.length===1);
 }else if(mode==='two_searches_latest_wins'){
  const p=start(),x=result(),q=start(),y=result();finish(1,200,y);await q;finish(0,200,{...x,items:[]});await p;check(buttons().length===1&&calls.length===2);check($('resource-error').textContent==='');
 }else{
  const p=start(),x=result();
  if(mode==='wrong_resource')x.resource_id='other';else if(mode==='wrong_quantity')x.items[0].quantity=1;else if(mode==='wrong_duration')x.items[0].ends_at='2026-10-12T12:30:00Z';else if(mode==='wrong_grid')x.items[0].starts_at='2026-10-12T11:16:00Z';else if(mode==='unsorted')x.items.push({...x.items[0],starts_at:'2026-10-12T11:00:00Z',ends_at:'2026-10-12T12:00:00Z'});else if(mode==='too_many_results')x.items=Array(11).fill(x.items[0]);else throw Error('unknown mode');
  finish(0,200,x);await p;check(buttons().length===0&&$('resource-hold').disabled);check($('resource-error').textContent.includes('不匹配'));
 }
 for(const call of calls){if(mode!=='original_flow_explicit'){check(call.path.endsWith('/alternative-times')&&call.options.method==='POST'&&!call.options.headers['Idempotency-Key']);const sent=JSON.parse(call.options.body);check(!('purpose' in sent)&&!('ttl_seconds' in sent));}}
 console.log(JSON.stringify({mode,checks,scope:'NODE_VM_DOM_FETCH_DOUBLES_ONLY'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
