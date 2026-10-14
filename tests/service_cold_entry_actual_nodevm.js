const fs=require('fs'),vm=require('vm'),assert=require('assert'),readline=require('readline');
const id=()=>require('crypto').randomUUID();let seq=50;
const mode=process.argv[2]||'normal';let lost=false,dropRecovery=false,lastRecovery=null;let number=0;const pending=new Map(),requests=[];
readline.createInterface({input:process.stdin}).on('line',line=>{const answer=JSON.parse(line);const resolve=pending.get(answer.id);pending.delete(answer.id);resolve(answer)});
async function ipc(message){const requestId=++number;const answer=new Promise(resolve=>pending.set(requestId,resolve));process.stdout.write(JSON.stringify({...message,id:requestId})+'\n');return await answer;}
async function control(action){const answer=await ipc({type:'control',action});assert.equal(answer.status,200);return answer.body;}
async function fetchAPI(path,options={}){requests.push({path,method:options.method||'GET'});const reply=await ipc({type:'request',path,options});
 const target=mode==='facade_loss'&&path==='/api/service-instance-cold-inputs'||mode==='run_loss'&&path==='/api/runs'||mode==='material_loss'&&path.endsWith('/commands')&&JSON.parse(options.body||'{}').slot==='need_summary';
 if(!lost&&options.method==='POST'&&target){lost=true;dropRecovery=true;assert(reply.status<300);throw Error('SYNTHETIC dropped committed original POST reply');}
 if(path==='/api/service-instance-cold-inputs/recovery'){if(dropRecovery){dropRecovery=false;throw Error('SYNTHETIC first GET reply also lost before page close');}lastRecovery=reply.body;}
 return {ok:reply.status>=200&&reply.status<300,status:reply.status,json:async()=>reply.body};}
class Element{
constructor(tag='div'){this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.style={};this.listeners={};}
append(...x){this.children.push(...x)}replaceChildren(...x){this.children=x;this.textContent=''}prepend(...x){this.children.unshift(...x)}reset(){}addEventListener(n,f){(this.listeners[n]??=[]).push(f)}setAttribute(){}removeAttribute(n){delete this[n]}closest(){return null}querySelectorAll(selector){const all=this.children.flatMap(c=>[c,...c.querySelectorAll(selector)]);return all.filter(c=>selector==='input[data-cold-goal]'&&c.dataset.coldGoal)}scrollIntoView(){}focus(){}select(){}remove(){}get firstElementChild(){return this.children[0]}get options(){return this.children.filter(x=>x.tagName==='option')}get selectedOptions(){return this.options.filter(x=>x.value===this.value)}
}
function page(seed={}){const elements=new Map(),get=id=>{if(!elements.has(id)){const e=new Element();e.id=id;elements.set(id,e)}return elements.get(id)},store={...seed};const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},{ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});get('run-access-valid-until').parentElement={firstChild:{textContent:''}};
const ctx=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,URLSearchParams,structuredClone,TextEncoder,Uint8Array,Option:function(t,v){const x=new Element('option');x.textContent=t;x.value=v;return x},crypto:{randomUUID:()=>id(seq++),subtle:require('crypto').webcrypto.subtle},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},location:{search:''},document:{getElementById:get,createElement:t=>new Element(t),querySelectorAll:()=>[],body:new Element('body'),addEventListener(){}},window:{addEventListener(){}},fetch:fetchAPI});
vm.runInContext(fs.readFileSync('src/parkweave/web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1],ctx);return {get,read:s=>vm.runInContext(s,ctx),snapshot:()=>({...store})};}

(async()=>{let p=page();p.get('token').value='SYNTHETIC_NODE_API_SESSION';
await p.get('cold-directory-read').onclick();assert(p.read('coldDirectory'),'real initial directory rejected');assert.equal(p.read('coldDirectory.park_id'),'park-b');assert.equal(p.read('coldDirectory.instances.length'),3);
p.get('cold-instance').value=p.read('coldDirectory.instances.find(i=>i.service_id==="synthetic-material-preparation").instance_id');p.get('cold-instance').onchange();
p.get('cold-goal').value='SYNTHETIC NODE COLD '+mode+' new request';p.get('cold-need').value='SYNTHETIC NODE PRIVATE '+mode+' new need';p.get('cold-outline').value='SYNTHETIC NODE PRIVATE '+mode+' new outline';p.get('cold-reason').value='SYNTHETIC owner explicitly prepares '+mode;
p.get('cold-goals').querySelectorAll('input[data-cold-goal]').forEach(el=>el.checked=true);p.get('cold-prepare-confirm').checked=true;p.get('cold-prepare-confirm').onchange();
await p.get('cold-prepare').onclick();
let coldReloads=0;
async function coldPage(){const saved=p.snapshot(),h=JSON.parse(saved['parkweave.cold-input-original-key.v1']);assert(h&&h.key&&h.actor);const serialized=JSON.stringify(saved);assert(!serialized.includes('SYNTHETIC NODE PRIVATE'));assert(!serialized.includes('SYNTHETIC_NODE_API_SESSION'));assert.deepEqual(Object.keys(h).sort(),['actor','key','sent','v']);
 const previous=requests.length;p=page(saved);p.get('token').value='SYNTHETIC_NODE_API_SESSION';await p.get('cold-recover').onclick();assert(p.read('coldView'),'cold real recovery DTO rejected: '+p.get('cold-status').textContent);await p.get('cold-directory-read').onclick();assert(requests.slice(previous).every(r=>r.method==='GET'),'cold recovery must GET only');coldReloads++;return p;}
if(mode==='facade_loss')await coldPage();
assert(p.read('coldView'),'initial real cold facade DTO rejected: '+p.get('cold-status').textContent);assert.equal(p.read('coldView.stages.length'),1);
const stages=['CREATE_RUN','CREATE_PREPARATION','SAVE_REQUEST','ADD_need_summary','ADD_material_outline'];
for(const name of stages){
 assert.equal(p.get('cold-stage').value,name);
 if(name!=='CREATE_RUN'){await p.get('cold-stage-prepare').onclick();assert(p.read('coldView.stages.some(s=>s.name==='+JSON.stringify(name)+')'),'real stage description rejected '+name+': '+p.get('cold-status').textContent);}
 assert.equal(p.get('cold-stage-send').disabled,true,'each original command needs explicit confirmation');p.get('cold-send-confirm').checked=true;p.get('cold-send-confirm').onchange();assert.equal(p.get('cold-stage-send').disabled,false,'original stage send unexpectedly disabled '+name);
 await p.get('cold-stage-send').onclick();
 if(name==='CREATE_RUN'){await control('worker');if(mode==='run_loss')await coldPage();else await p.get('cold-recover').onclick();}
 if(name==='ADD_need_summary'&&mode==='material_loss')await coldPage();
 assert(p.read('coldCommitted('+JSON.stringify(name)+')'),'original committed stage missing '+name+': '+p.get('cold-status').textContent);
 if(!p.read('coldDirectory'))await p.get('cold-directory-read').onclick();
}
assert.equal(p.get('cold-open').disabled,false);const prep=p.read('coldView.product_observations.find(o=>o.name==="CREATE_PREPARATION").result.preparation_id');
assert.equal(p.read('coldView.product_observations.every(o=>o.status==="COMMITTED")'),true);
await coldPage();assert.equal(p.read('coldView.product_observations.every(o=>o.status==="COMMITTED")'),true);
if(mode==='execute_revoked'){await control('revoke_execute');const before=requests.length;await p.get('cold-directory-read').onclick();assert.equal(p.read('coldDirectory'),null);await p.get('cold-recover').onclick();assert(p.read('coldView'),'READ-authorized history must recover');assert.equal(p.read('coldView.current_available'),false);assert.equal(p.get('cold-stage-send').disabled,true);assert.equal(p.get('cold-stage-prepare').disabled,true);assert(requests.slice(before).every(r=>r.method==='GET'));
 const treeText=node=>String(node.textContent||'')+' '+node.children.map(treeText).join(' '),visible=treeText(p.get('cold-input-history'));
 assert(visible.includes('SYNTHETIC NODE COLD '+mode+' new request'));
 assert(visible.includes('SYNTHETIC NODE PRIVATE '+mode+' new need'));assert(visible.includes('SYNTHETIC NODE PRIVATE '+mode+' new outline'));
 for(const goal of p.read('coldView.input.required_goals'))assert(visible.includes(goal),'required goal absent from READ history '+goal);
 for(const material of Object.values(p.read('coldView.input.fields'))){assert(visible.includes(material.source_label));assert(visible.includes(material.source_kind));}
 assert.equal(p.get('cold-open').disabled,true);const beforeOpen=requests.length,handle=p.snapshot()['parkweave.cold-input-original-key.v1'];await p.get('cold-open').onclick();assert.equal(requests.length,beforeOpen,'READ-only open handler must not fetch original writable page');assert.equal(p.snapshot()['parkweave.cold-input-original-key.v1'],handle,'READ-only history must retain opaque handle');}

if(mode!=='execute_revoked'){await p.get('cold-open').onclick();assert.equal(p.read('preparationView.preparation.id'),prep);assert.equal(p.read('prepRole'),'enterprise_operator');assert.equal(p.read('servicePlanView.plan_id'),null);assert.equal(p.snapshot()['parkweave.cold-input-original-key.v1'],undefined,'resolved original handle should be released on explicit open');}else{assert(p.snapshot()['parkweave.cold-input-original-key.v1'],'READ-only recovery retains original history handle');}
assert.equal(requests.filter(r=>r.method==='POST'&&r.path==='/api/service-instance-cold-inputs').length,1);assert.equal(requests.filter(r=>r.method==='POST'&&r.path==='/api/runs').length,1);assert.equal(requests.filter(r=>r.method==='POST'&&r.path.endsWith('/commands')).length,2);
assert(!requests.some(r=>r.method==='POST'&&(/service-selections|service-case-plan/.test(r.path))));
process.stdout.write(JSON.stringify({type:'result',result:'PASS',mode,completeOriginalHTML:true,realASGIResponses:true,preparation_id:prep,coldReloads,originalPostCount:requests.filter(r=>r.method==='POST').length,lostCommittedReply:lost,onlyOpaqueStorage:true,allOriginalStagesObserved:true,originalPreparationOpened:mode!=='execute_revoked',automaticGeneration:false,automaticAdoption:false})+'\n');process.exit(0);
})().catch(e=>{console.error(e.stack);process.exit(1)});
