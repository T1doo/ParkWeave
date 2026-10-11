// NEW independent harness: actual resource JS, DOM/fetch doubles only.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('/workspace/ParkWeave/src/parkweave/web.html','utf8');
const actual=source.slice(source.indexOf('let resourceGeneration=0'),source.indexOf('function updateCombinationSelection'));
const rid='fa161ea0-b665-4ec5-b345-a070bfec764d',mode=process.argv[2];let checks=0;
class Node{constructor(tag='div'){this.tagName=tag;this.value='';this.textContent='';this.children=[];this.dataset={};this.disabled=false;this.hidden=false;}append(...v){this.children.push(...v);}prepend(...v){this.children.unshift(...v);}replaceChildren(...v){this.children=[...v];this.textContent='';}querySelectorAll(){return inputs;}reset(){for(const x of inputs)x.value='';}get firstElementChild(){return this.children[0];}replaceWith(){}}
const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,new Node());return nodes.get(id);};
const inputs=['resource-select','resource-start','resource-end','resource-quantity','resource-ttl','resource-purpose','resource-search-from','resource-search-until'].map($),calls=[];
const context=vm.createContext({$,Date,crypto:{randomUUID:()=> '66666666-6666-6666-6666-666666666666'},
 document:{createElement:t=>new Node(t),querySelectorAll:()=>[]},textElement:(tag,text)=>Object.assign(new Node(tag),{textContent:text}),
 bundleActor:null,bundleBusy:false,bundleLocked:()=>true,clearCombinationSelection:()=>{},updateCombinationSelection:()=>{},
 fetch:(path,options)=>new Promise((resolve,reject)=>calls.push({path,options,resolve,reject}))});
vm.runInContext(actual,context);const run=s=>vm.runInContext(s,context),check=v=>{assert(v);checks++;};
function draft(token='SYNTHETIC_TOKEN_A'){ $('token').value=token;$('resource-select').value=rid;$('resource-start').value='2026-10-15T10:07';$('resource-end').value='2026-10-15T10:52';$('resource-quantity').value='1';$('resource-ttl').value='120';$('resource-purpose').value='SYNTHETIC_PRIVATE_REASON';$('resource-search-from').value='2026-10-15T11:07';$('resource-search-until').value='2026-10-15T13:52';$('resource-form').hidden=false;}
draft();
const response=()=>({...JSON.parse(run('JSON.stringify(resourceAlternativeBody())')),resource_id:rid,resource_revision:2,
 preview_only:true,coverage:'SEARCH_WINDOW_GRID_ONLY',ordering:'START_ASC',grid_minutes:15,scan_limit:100,result_limit:10,
 grid_anchor:'2026-10-15T11:07:00Z',server_time:'2026-10-11T12:00:00Z',scanned_candidates:9,available_candidates:1,
 grid_exhausted:true,results_truncated:false,items:[{starts_at:'2026-10-15T11:22:00Z',ends_at:'2026-10-15T12:07:00Z',quantity:1}]});
const start=()=> $('resource-alternatives').onclick(),tick=()=>new Promise(r=>setImmediate(r));
const finish=(i,status,x)=>calls[i].resolve({ok:status<400,status,json:async()=>x});
const buttons=()=> $('resource-alternative-results').children.filter(n=>n.tagName==='button');
const text=n=>n.textContent+' '+n.children.map(text).join(' ');
async function show(){const x=response(),p=start();finish(calls.length-1,200,x);await p;check(buttons().length===1);return buttons()[0];}
(async()=>{
 if(mode==='old_button_after_draft'){
  const old=await show();$('resource-start').value='2026-10-15T12:33';$('resource-start').oninput();old.onclick();check($('resource-start').value==='2026-10-15T12:33');check($('resource-hold').disabled&&buttons().length===0);
 }else if(mode==='old_button_after_search'){
  const old=await show();await show();old.onclick();check(buttons().length===1);check($('resource-start').value==='2026-10-15T10:07');check($('resource-hold').disabled);
 }else if(mode==='old_button_identity_aba'){
  const old=await show();run('clearResources()');draft('SYNTHETIC_TOKEN_B');run('clearResources()');draft();old.onclick();check($('resource-start').value==='2026-10-15T10:07');check(buttons().length===0&&$('resource-error').textContent==='');
 }else if(mode==='delayed_json_identity_aba'){
  const x=response(),p=start();let resolveBody;calls[0].resolve({ok:true,status:200,json:()=>new Promise(r=>resolveBody=r)});await tick();
  run('clearResources()');draft('SYNTHETIC_TOKEN_B');run('clearResources()');draft();$('resource-current').textContent='SYNTHETIC NEWEST A';resolveBody(x);await p;
  check($('resource-current').textContent==='SYNTHETIC NEWEST A');check(buttons().length===0&&$('resource-error').textContent==='');check(!$('resource-form').hidden);
 }else if(mode==='late_403_other_identity'){
  const p=start();run('clearResources()');draft('SYNTHETIC_TOKEN_B');$('resource-current').textContent='SYNTHETIC B';finish(0,403,{});await p;
  check($('resource-current').textContent==='SYNTHETIC B'&&!$('resource-form').hidden);check($('resource-error').textContent==='');
 }else if(mode==='current_403_clear'){
  $('resource-current').append(new Node());const p=start();finish(0,403,{});await p;check($('resource-form').hidden);check($('resource-current').children.length===0&&buttons().length===0);check($('resource-hold').disabled);
 }else if(mode==='bundle_unknown_read_search'){
  await show();check(calls.length===1&&buttons().length===1);check($('resource-hold').disabled);check(run('bundleLocked()')===true);
 }else if(mode==='change_ttl'||mode==='change_purpose'){
  const x=response(),p=start(),id=mode==='change_ttl'?'resource-ttl':'resource-purpose';$(id).value+='changed';$(id).oninput();finish(0,200,x);await p;
  check(buttons().length===0&&$('resource-hold').disabled);check($('resource-preview-result').textContent.includes('输入已变化'));
 }else if(['outside_window','duplicate_candidates','quantity_bool'].includes(mode)){
  const x=response(),p=start();if(mode==='outside_window')x.items[0]={starts_at:'2026-10-15T13:22:00Z',ends_at:'2026-10-15T14:07:00Z',quantity:1};
  if(mode==='duplicate_candidates')x.items.push({...x.items[0]});if(mode==='quantity_bool')x.items[0].quantity=true;
  finish(0,200,x);await p;check(buttons().length===0);check($('resource-error').textContent.includes('不匹配'));check($('resource-hold').disabled);
 }else if(mode==='select_no_automatic_write'){
  const old=await show();old.onclick();check($('resource-start').value==='2026-10-15T11:22'&&$('resource-end').value==='2026-10-15T12:07');
  check(run('resourcePreview===null')&&$('resource-hold').disabled&&buttons().length===0);check(calls.length===1);
  await $('resource-form').onsubmit({preventDefault(){}});check(calls.length===1);check($('resource-preview-result').textContent.includes('重新预检'));
 }else if(mode==='empty_sampling_message'||mode==='truncated_sampling_message'){
  const x=response(),p=start();if(mode==='empty_sampling_message'){x.items=[];x.available_candidates=0;}else x.results_truncated=true;
  finish(0,200,x);await p;const rendered=text($('resource-alternative-results'));
  check(rendered.includes('15分钟'));check(rendered.includes(mode==='empty_sampling_message'?'不表示所有时刻都不可用':'还有更晚'));check($('resource-hold').disabled);
 }else throw Error('unknown independent mode');
 for(const c of calls){check(c.path.endsWith('/alternative-times')&&c.options.method==='POST');check(!c.options.headers['Idempotency-Key']);const sent=JSON.parse(c.options.body);check(!('purpose' in sent)&&!('ttl_seconds' in sent));}
 console.log(JSON.stringify({mode,checks,scope:'NEW_ACTUAL_RESOURCE_JS_NODE_VM_DOUBLES_ONLY'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
