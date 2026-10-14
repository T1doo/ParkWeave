const fs=require('fs'),vm=require('vm'),assert=require('assert'),readline=require('readline');
const id=()=>require('crypto').randomUUID();let seq=50;
const mode=process.argv[3]||'normal';let loseGenerate=true,lastRecovery=null;
let requestNumber=0;const pending=new Map();
readline.createInterface({input:process.stdin}).on('line',line=>{const value=JSON.parse(line);const resolve=pending.get(value.id);pending.delete(value.id);resolve(value);});
async function fetchAPI(path,options={}){const requestId=++requestNumber;const answer=new Promise(resolve=>pending.set(requestId,resolve));process.stdout.write(JSON.stringify({type:'request',id:requestId,path,options})+'\n');const reply=await answer;if(path.endsWith('/service-selections/recovery'))lastRecovery=reply.body;if(mode==='historical_lost_response'&&loseGenerate&&options.method==='POST'&&path.endsWith('/service-selections')){loseGenerate=false;assert.equal(reply.status,201);throw Error('SYNTHETIC lost reply after actual committed candidate');}return {ok:reply.status>=200&&reply.status<300,status:reply.status,json:async()=>reply.body};}
class Element{
constructor(tag='div'){this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.style={};this.listeners={};}
append(...x){this.children.push(...x)}replaceChildren(...x){this.children=x;this.textContent=''}prepend(...x){this.children.unshift(...x)}reset(){}addEventListener(n,f){(this.listeners[n]??=[]).push(f)}setAttribute(){}removeAttribute(n){delete this[n]}closest(){return null}querySelectorAll(){return []}scrollIntoView(){}focus(){}select(){}remove(){}get firstElementChild(){return this.children[0]}get options(){return this.children.filter(x=>x.tagName==='option')}get selectedOptions(){return this.options.filter(x=>x.value===this.value)}
}
function page(seed={}){const elements=new Map(),get=id=>{if(!elements.has(id)){const e=new Element();e.id=id;elements.set(id,e)}return elements.get(id)},store={...seed};const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},{ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});get('run-access-valid-until').parentElement={firstChild:{textContent:''}};
const ctx=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,URLSearchParams,structuredClone,TextEncoder,Option:function(t,v){const x=new Element('option');x.textContent=t;x.value=v;return x},crypto:{randomUUID:()=>id(seq++)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},location:{search:''},document:{getElementById:get,createElement:t=>new Element(t),querySelectorAll:()=>[],body:new Element('body'),addEventListener(){}},window:{addEventListener(){}},fetch:fetchAPI});
vm.runInContext(fs.readFileSync('src/parkweave/web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1],ctx);return {get,read:s=>vm.runInContext(s,ctx),snapshot:()=>({...store})};}

(async()=>{const prep=process.argv[2];let p=page();p.get('token').value='SYNTHETIC_NODE_API_SESSION';
await p.read('loadServiceCasePlan('+JSON.stringify(prep)+')');
assert.equal(p.read('servicePlanView.plan_id'),null);
await p.get('service-selection-read').onclick();
assert.equal(p.read('serviceSelectionCatalog.selection_oracle.state'),'UNIQUE');
assert.equal(p.read('serviceSelectionCatalog.catalog_snapshot.instances.length'),3);
assert(p.read('serviceSelectionCatalog.catalog_snapshot.instances.every(i=>i.instance_id.startsWith("park-b-"))'));
await p.get('service-selection-generate').onclick();
if(mode==='historical_lost_response'){
 const snapshot=p.snapshot(),names=Object.keys(snapshot).filter(n=>n.startsWith('parkweave.service-selection-original-key'));
 assert.equal(names.length,1,'lost committed response must retain original opaque key');
 assert.equal(p.read('serviceSelectionView'),null);
 const cold=page(snapshot);cold.get('token').value='SYNTHETIC_NODE_API_SESSION';
 await cold.read('loadServiceCasePlan('+JSON.stringify(prep)+')');
 await cold.get('service-selection-read').onclick();
 const fresh=cold.read('serviceSelectionCatalog');assert(fresh,'new source metadata must remain readable');
 await cold.get('service-selection-recover').onclick();
 assert(lastRecovery&&lastRecovery.status==='COMMITTED');assert.equal(lastRecovery.items.length,1);
 const historical=lastRecovery.items[0];assert.equal(historical.state,'CURRENT_SOURCE_UNAVAILABLE');
 assert.equal(lastRecovery.actor_ref,fresh.actor_ref);assert.equal(lastRecovery.case_id,fresh.case_id);assert.equal(lastRecovery.run_id,fresh.run_id);
 assert.equal(historical.case_id,fresh.case_id);assert.equal(historical.run_id,fresh.run_id);assert.notEqual(historical.preparation_revision,fresh.preparation_revision);
 assert.equal(cold.read('serviceSelectionView'),null);assert.equal(cold.read('servicePlanView.plan_id'),null);
 assert.equal(Object.keys(cold.snapshot()).filter(n=>n.startsWith('parkweave.service-selection-original-key')).length,0,'verified historical recovery must release original handle');
 assert.equal(cold.get('service-selection-confirm').checked,false);assert.equal(cold.get('service-selection-confirm').disabled,true);
 assert(cold.get('service-selection-status').textContent.includes('CURRENT_SOURCE_UNAVAILABLE'));
 process.stdout.write(JSON.stringify({type:'result',result:'PASS',mode,completeOriginalHTML:true,realASGIResponses:true,candidate_id:historical.candidate_id,plan_id:null,historical_state:historical.state,old_preparation_revision:historical.preparation_revision,new_preparation_revision:fresh.preparation_revision,original_handle_cleared:true,current_can_adopt:cold.read('servicePlanView.can_adopt'),new_explicit_generate_enabled:!cold.get('service-selection-generate').disabled})+'\n');process.exit(0);
}

assert(p.read('serviceSelectionView')!==null,'actual API candidate did not survive UI validation');
assert.equal(p.read('serviceSelectionView.validator_version'),4);
const selected=p.read('serviceSelectionView.candidate_id');
p.get('service-plan-reason').value='SYNTHETIC explicit real API NodeVM selection adoption';
await p.get('service-plan-adopt').onclick();assert.equal(p.read('servicePlanView.plan_id'),null);
p.get('service-selection-confirm').checked=true;
await p.get('service-plan-adopt').onclick();
const plan=p.read('servicePlanView.plan_id');assert(plan,'actual original ADOPT did not survive UI validation');
assert.equal(p.read('servicePlanView.steps.length'),5);
assert.equal(p.read('servicePlanView.required_goals.length'),6);
await p.get('goal-results-read').onclick();
const originalTrace=p.read('goalResultView.source_trace');
assert(originalTrace,'actual goal result trace absent');
assert.equal(originalTrace.candidate.validator_version,4);
assert.equal(originalTrace.service_capabilities.length,3);
assert.equal(originalTrace.park_instances.length,3);
assert.equal(originalTrace.service_selection.selection.selections.length,3);
await p.get('goal-results-source-read').onclick();
const treeText=node=>String(node.textContent||'')+' '+node.children.map(treeText).join(' ');
const visible=treeText(p.get('goal-results-source'));
assert.equal((visible.match(/实际选中服务 /g)||[]).length,3,'must display only the three selected services');
assert.equal((visible.match(/实际选中园区 /g)||[]).length,3,'must display the three selected park configurations');
for(const ref of originalTrace.service_selection.selection.selections){
 const release=originalTrace.service_capabilities.find(r=>r.release_id===ref.release_id),instance=originalTrace.park_instances.find(i=>i.instance_id===ref.instance_id);
 assert(release&&instance);
 for(const expected of [release.service_id,ref.release_id,ref.release_sha256,ref.instance_id,ref.config_sha256,JSON.stringify(instance.roles),JSON.stringify(instance.resources),JSON.stringify(instance.fields)])assert(visible.includes(expected),'frozen selected mapping not visible: '+expected);
}
assert(visible.includes(originalTrace.trace_sha256));
assert.equal(p.get('goal-results-error').textContent,'');

const cold=page(p.snapshot());cold.get('token').value='SYNTHETIC_NODE_API_SESSION';
await cold.read('loadServiceCasePlan('+JSON.stringify(prep)+')');assert.equal(cold.read('servicePlanView.plan_id'),plan);
process.stdout.write(JSON.stringify({type:'result',result:'PASS',mode,completeOriginalHTML:true,realASGIResponses:true,candidate_id:selected,plan_id:plan,selected_services_visible:3,selected_instances_visible:3,source_trace_sha256:originalTrace.trace_sha256})+'\n');process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1)});
