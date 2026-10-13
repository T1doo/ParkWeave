// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync(process.argv[3]||'src/parkweave/template_candidate_web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.id='';this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.options=[];this.listeners={};this.style={};}
 append(...x){for(const e of x)if(e&&typeof e==='object')e.parentElement=this;this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 reset(){}addEventListener(n,f){this.listeners[n]=f;}setAttribute(){}removeAttribute(name){delete this[name];}
 closest(selector){let e=this;while(e){for(const part of selector.split(',')){const t=part.trim();if((t.startsWith('#')&&e.id===t.slice(1))||['button','form','a'].includes(t)&&e.tagName.toLowerCase()===t)return e;}e=e.parentElement;}return null;}querySelectorAll(){return [];}scrollIntoView(){this.scrolled=true;}
 get firstElementChild(){return this.children[0];}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
const elements=new Map(),$=name=>{if(!elements.has(name))elements.set(name,new Element());elements.get(name).id=name;return elements.get(name);};
const store={},calls=[],events=[];
const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},
 {ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
const context=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,
 crypto:{randomUUID:()=>id(99)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},
 Element,document:{getElementById:$,createElement:t=>new Element(t),querySelectorAll:()=>[],body:new Element('body'),addEventListener:(...a)=>events.push(a),execCommand:()=>false},
 window:{addEventListener:(...a)=>events.push(a)},
 fetch:(path,options)=>new Promise((resolve,reject)=>calls.push({path,options,resolve,reject}))});
vm.runInContext(code,context);$('token').value='SYNTHETIC_SESSION_A';
const run=s=>vm.runInContext(s,context),tick=()=>new Promise(r=>setImmediate(r));
function finish(call,status,value){call.resolve({status,ok:status>=200&&status<300,json:async()=>value});}
Object.defineProperty(Element.prototype,'selectedOptions',{get(){return this.children.filter(x=>x.tagName==='option'&&x.value===this.value);}});
function instance(n=70){return {instance_id:id(n),state:'PLAN_ADOPTED',run_id:id(2),case_id:id(1),preparation_id:id(3),plan_id:id(9),release_available:true,binding:{source:'SYNTHETIC'}};}
(async()=>{
 finish(calls[0],200,{enabled_for_isolated_tests:true,isolated_personas:[]});await tick();$('consumer-token').value='SYNTHETIC_A';$('consumer-instance-id').value=id(70);const read=$('consumer-read').onclick();finish(calls.at(-1),200,instance());await read;check($('product-link').href==='/?template_instance='+id(70));check(!$('product-link').hidden);
 if(mode==='unknown_create_then_old_read'){
  const catalog=$('consumer-catalog').onclick();finish(calls.at(-1),200,{park_id:'park-a',org_id:'org-a',templates:[{release_id:id(81),release_sha256:'f'.repeat(64),name:'SYNTHETIC'}],reviewers:[{id:'prep-specialist-fixture-a'}]});await catalog;$('consumer-release').value=id(81);$('consumer-reviewer').value='prep-specialist-fixture-a';$('consumer-goal').value='SYNTHETIC NEW UNRESOLVED REQUEST';$('consumer-need-summary').value='SYNTHETIC NEW NEED';$('consumer-need-source').value='SYNTHETIC SOURCE';$('consumer-material-outline').value='SYNTHETIC NEW OUTLINE';$('consumer-outline-source').value='SYNTHETIC SOURCE';
  const submit=$('consumer-create').onclick(),post=calls.at(-1);check(post.options.method==='POST');check($('product-link').hidden);check(!$('product-link').href);finish(post,500,{detail:'SYNTHETIC NEW CONSUME UNKNOWN'});await submit;check(run('cp.state')==='UNKNOWN');check($('product-link').hidden);const pending=run('cp');$('consumer-instance-id').value=id(70);const lookup=$('consumer-read').onclick();finish(calls.at(-1),200,instance());await lookup;check(run('cp')===pending);check($('product-link').hidden);check(!$('product-link').href);check($('consumer-goal').value==='SYNTHETIC NEW UNRESOLVED REQUEST');check(run('cp.state')==='UNKNOWN');check(calls.filter(c=>c.options?.method==='POST').length===1);console.log(JSON.stringify({mode,checks,result:'PASS',scope:'REAL_CONSUMER_CREATE500_UNKNOWN_THEN_OLD_INSTANCE_READ_NO_PENDING_MOCK'}));return;
 }
 for(const name of ['consumer-goal','consumer-need-summary','consumer-material-outline','consumer-need-source','consumer-outline-source'])$(name).value='SYNTHETIC PRIVATE DRAFT';
 if(mode==='template_reason403'){
  const read=$('template-refresh').onclick();finish(calls.at(-1),200,{state:'DRAFT',revision:1,content_version:1,candidate_available:false,draft:{name:'SYNTHETIC PRIVATE TEMPLATE',source:{revision:'1',statement:'SYNTHETIC PRIVATE SOURCE'},required_goals:[]},history:[{reason:'SYNTHETIC PRIVATE HISTORY'}],releases:[]});await read;$('template-reason').value='SYNTHETIC PRIVATE REASON';check(run('view!==null'));check($('template-history').children.length>0);
  const refused=$('template-refresh').onclick();let parses=0;calls.at(-1).resolve({status:403,ok:false,json:async()=>{parses++;throw new SyntaxError('Unexpected token <');}});await refused;check(parses===0);check(run('view===null && tp===null'));check($('template-history').children.length===0);for(const name of ['template-name','template-source-revision','template-source-statement','template-reason'])check($(name).value==='');check($('template-error').textContent.includes('无权访问'));console.log(JSON.stringify({mode,checks,result:'PASS',scope:'FULL_ORIGINAL_TEMPLATE_REFRESH_CURRENT403_CLEARS_REASON_DRAFT'}));return;
 }
 const old=$('consumer-read').onclick(),request=calls.at(-1);
 if(/^(empty403|nonjson403|late_empty403|late_nonjson403)$/.test(mode)){
  const late=mode.startsWith('late_');
  if(late){$('consumer-token').value='SYNTHETIC_B';$('consumer-token').oninput();$('consumer-instance-id').value=id(71);const newer=$('consumer-read').onclick();finish(calls.at(-1),200,instance(71));await newer;$('consumer-goal').value='SYNTHETIC NEW PRIVATE DRAFT';}
  let parses=0;request.resolve({status:403,ok:false,json:async()=>{parses++;throw new SyntaxError(mode.includes('nonjson')?'Unexpected token <':'Unexpected end of JSON input');}});await old;
  console.error(JSON.stringify({mode,parses,instancePresent:run('instance!==null'),resultNodes:$('consumer-result').children.length,draftRetained:$('consumer-goal').value==='SYNTHETIC PRIVATE DRAFT'}));
  check(parses===0);
  if(late){check(run('instance.instance_id')===id(71));check($('product-link').href==='/?template_instance='+id(71));check(!$('product-link').hidden);check($('consumer-result').children.length>0);check($('consumer-goal').value==='SYNTHETIC NEW PRIVATE DRAFT');}
  else {check(run('instance===null && catalog===null && cp===null'));check($('consumer-result').children.length===0);check($('product-link').hidden);check(!$('product-link').href);check($('consumer-instance-id').value==='');for(const name of ['consumer-goal','consumer-need-summary','consumer-material-outline','consumer-need-source','consumer-outline-source'])check($(name).value==='');check($('consumer-error').textContent.includes('无权访问'));}
  console.log(JSON.stringify({mode,checks,result:'PASS',scope:'FULL_ORIGINAL_TEMPLATE_HTML_403_BEFORE_BODY_WITH_CURRENT_GENERATION_CLEARING'}));return;
 }
 if(mode==='late_identity'){$('consumer-token').value='SYNTHETIC_B';$('consumer-token').oninput();$('consumer-instance-id').value=id(71);const newer=$('consumer-read').onclick();finish(calls.at(-1),200,instance(71));await newer;finish(request,403,{detail:'SYNTHETIC OLD DENIAL'});await old;check($('product-link').href==='/?template_instance='+id(71));check(!$('product-link').hidden);}
 else{finish(request,mode==='crossowner403'?403:500,{detail:'SYNTHETIC current read refusal'});await old;check($('product-link').hidden);check(!$('product-link').href);if(mode==='crossowner403'){check(run('instance===null'));check($('consumer-result').children.length===0);}}
 console.log(JSON.stringify({mode,checks,result:'PASS',scope:'FULL_ORIGINAL_TEMPLATE_HTML_REAL_CONSUMER_READ_CLEARERS_HTTPDOM_DOUBLES'}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
