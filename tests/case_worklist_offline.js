// Real worklist page code in Node VM; offline DOM/navigation/fetch doubles.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('src/parkweave/web.html','utf8');
const actual=html.slice(html.indexOf('// Owner Case worklist:'),html.indexOf('// End owner Case worklist.'));
const mode=process.argv[2],uid=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.textContent='';this.value='';this.disabled=false;this.hidden=false;this.dataset={};}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 set innerHTML(v){throw Error('UNSAFE_HTML');}scrollIntoView(){this.scrolled=true;}
}
const elements=new Map(),$=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const content=e=>e.textContent+' '+e.children.map(content).join(' ');
const calls=[],nav=[],errors=[];let heldNavigation=null,forceCleanup=false;
function navigate(kind,id){nav.push({kind,id});if(mode==='late_navigation')return new Promise((resolve,reject)=>heldNavigation={resolve,reject});return Promise.resolve();}
const context=vm.createContext({$,JSON,Set,Error,encodeURIComponent,console,
 textElement:(tag,text)=>{const e=new Element(tag);e.textContent=text;return e;},
 fetch:(path,options)=>new Promise((resolve,reject)=>calls.push({path,options,resolve,reject})),
 clearGeneric:()=>{vm.runInContext('clearCaseWorklist()',context);$('result').textContent='';},
 clearPreparation:(a,b,force)=>{forceCleanup=force===true;if(mode==='403_pending'&&!force)throw Error('PRIVATE_DRAFT_BLOCKED');$('private').textContent='';},
 clearReceipts:()=>{$('receipt').textContent='';},clearResources:()=>{$('resources').textContent='';},
 loadPreparation:(id)=>navigate('materials',id),loadDispatch:id=>navigate('dispatch',id),
 loadReceipt:id=>navigate('receipt',id),loadLocalCase:id=>navigate('localcase',id),
 apiCall:path=>navigate('run',path),pageError:e=>errors.push('run:'+e.message),
 prepError:e=>errors.push('materials:'+e.message),dispatchError:e=>errors.push('dispatch:'+e.message),
 receiptError:e=>errors.push('receipt:'+e.message),localCaseError:e=>errors.push('localcase:'+e.message)});
context.entryFetch=context.fetch;
context.entryWriteRequests=new Map();context.activeEntryWriteFlow=null;
context.clearDeniedPrivateViews=()=>{context.clearGeneric();context.clearPreparation(false,false,true);context.clearReceipts();context.clearResources();$('page-feedback').textContent='权限已失效';};
vm.runInContext(actual,context);$('token').value='SYNTHETIC_TOKEN_A';$('run').oninput=()=>vm.runInContext('clearCaseWorklist()',context);
function response(target='materials'){
 return {scope:'CURRENT_OWNER_SYNTHETIC_CASE_WORKLIST',read_only:true,recorded_states_only:true,automatically_replayed:false,next_after:null,
 items:[{case_id:uid(1),run_id:uid(2),preparation_id:uid(3),receipt_step_id:target==='receipt'?uid(4):null,
 title:'SYNTHETIC <img onerror=private()>',label:'录得等待状态',attention:'WAITING_RECEIPT',waiting_on:'EXECUTOR',open_target:target,
 evidence_verified:false,case_goal_completed:false,resource_release_required_separately:false}]};
}
const finish=(i,status,x)=>calls[i].resolve({status,ok:status>=200&&status<300,json:async()=>x});
const start=()=> $('case-worklist-read').onclick();
(async()=>{
 if(mode==='missing_session'){
  $('token').value='';await start();check(calls.length===0);check(content($('case-worklist-status')).includes('会话'));
 }else if(mode==='403_pending'){
  for(const id of ['private','receipt','resources','result'])$(id).textContent='PRIVATE_OLD_DATA';
  const p=start();finish(0,403,{});await p;check(forceCleanup);check(['private','receipt','resources','result'].every(id=>!content($(id)).includes('PRIVATE_OLD_DATA')));
 }else if(['late_identity','identity_aba','context_reset','late_403'].includes(mode)){
  const p=start();$('token').value='SYNTHETIC_TOKEN_B';vm.runInContext('clearCaseWorklist()',context);
  if(mode==='identity_aba'){$('token').value='SYNTHETIC_TOKEN_A';vm.runInContext('clearCaseWorklist()',context);}
  finish(0,mode==='late_403'?403:200,response());await p;check($('case-worklist-items').children.length===0);check($('page-feedback').textContent==='');
 }else if(['bad_shape','bad_target','bad_receipt','claim_complete','bad_cursor','too_many'].includes(mode)){
  const x=response();if(mode==='bad_shape')x.scope='OTHER';if(mode==='bad_target')x.items[0].open_target='execute';
  if(mode==='bad_receipt')x.items[0].receipt_step_id='../private';if(mode==='claim_complete')x.items[0].case_goal_completed=true;
  if(mode==='bad_cursor')x.next_after='bad';if(mode==='too_many')x.items=Array(21).fill(x.items[0]);
  const p=start();finish(0,200,x);await p;check($('case-worklist-items').children.length===0);check(content($('case-worklist-status')).includes('无法核对'));
 }else if(mode==='pagination'){
  let p=start();let x=response();x.next_after=uid(1);finish(0,200,x);await p;
  check(!$('case-worklist-next').hidden);p=$('case-worklist-next').onclick();check(calls[1].path.endsWith('&after='+uid(1)));
  finish(1,200,{...response(),items:[]});await p;check($('case-worklist-items').children.length===0&&$('case-worklist-next').hidden);
 }else{
  const target=mode.startsWith('open_')?mode.slice(5):'materials';let x=response(target);
  if(mode==='cancelled'){x.items[0].attention='CANCELLED';x.items[0].resource_release_required_separately=true;}
  if(mode==='backend_projection')x=JSON.parse(fs.readFileSync(0,'utf8'));
  const p=start();finish(0,200,x);await p;check($('case-worklist-items').children.length===x.items.length);
  check(calls.length===1&&nav.length===0);
  const card=$('case-worklist-items').children[0];
  if(mode==='cancelled')check(content(card).includes('不代表已释放资源'));
  if(mode==='late_navigation'){
   const navigation=card.children.find(e=>e.tagName==='button').onclick();check(!!heldNavigation);
   $('token').value='SYNTHETIC_TOKEN_B';vm.runInContext('clearCaseWorklist()',context);heldNavigation.reject(Error('PRIVATE_OLD_ERROR'));await navigation;
   check(errors.length===0&&$('case-worklist-items').children.length===0);
  }else if(mode.startsWith('open_')){
   await card.children.find(e=>e.tagName==='button').onclick();check(nav.length===1&&nav[0].kind===target);
   check(calls.length===1&&$('case-worklist-items').children.length===0);
   const focus={run:'run',materials:'prep-detail',dispatch:'dispatch-detail',receipt:'receipt-detail',localcase:'local-case-detail'}[target];check($(focus).scrolled===true);
  }else check(errors.length===0);
 }
 check(calls.every(c=>!c.options.method||c.options.method==='GET'));
 console.log(JSON.stringify({mode,checks,scope:'NODE_VM_REAL_PAGE_CODE_OFFLINE_ONLY'}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
