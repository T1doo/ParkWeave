// Full original page script: real apiCall, entry loaders, renderers and clearers.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync(process.argv[3]||'src/parkweave/web.html','utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
let nextRequestKey=99;const mode=process.argv[2],id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');let checks=0;
const check=v=>{checks++;assert(v);};
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];const named={};this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(named[k]??=new Element('input'))});this.dataset={};this.textContent='';this.value='';this.hidden=true;this.disabled=false;this.checked=false;this.options=[];this.listeners={};}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;this.textContent='';}
 prepend(...x){this.children.unshift(...x);}reset(){}addEventListener(n,f){this.listeners[n]=f;}setAttribute(){}removeAttribute(){}
 closest(){return null;}querySelectorAll(){return [];}scrollIntoView(){this.scrolled=true;}
 get firstElementChild(){return this.children[0];}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
const elements=new Map(),$=name=>{if(!elements.has(name)){const e=new Element();e.id=name;elements.set(name,e);}return elements.get(name);};
const store={},calls=[],events=[];
const storage=new Proxy({getItem:n=>store[n]??null,setItem:(n,v)=>store[n]=v,removeItem:n=>delete store[n]},
 {ownKeys:()=>Object.keys(store),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
$('run-access-valid-until').parentElement={firstChild:{textContent:''}};
const context=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,encodeURIComponent,
 Option:function(text,value){const o=new Element('option');o.textContent=text;o.value=value;return o;},
 crypto:{randomUUID:()=>id(nextRequestKey++)},localStorage:storage,setTimeout:()=>1,clearTimeout:()=>{},
 document:{getElementById:$,createElement:t=>new Element(t),querySelectorAll:()=>[],body:new Element('body'),addEventListener:(...a)=>events.push(a),execCommand:()=>false},
 window:{addEventListener:(...a)=>events.push(a)},
 fetch:(path,options)=>new Promise((resolve,reject)=>calls.push({path,options,resolve,reject}))});
vm.runInContext(code,context);$('token').value='SYNTHETIC_SESSION_A';
const run=s=>vm.runInContext(s,context),tick=()=>new Promise(r=>setImmediate(r));
const lines=require('readline').createInterface({input:process.stdin}),replies=[],milestones=[];
context.fetch=async(path,options={})=>{calls.push({path,options});const response=new Promise(resolve=>replies.push(resolve));console.log(JSON.stringify({request:{path,options}}));const x=await response;if(x.lost)throw Error('SYNTHETIC_COMMITTED_RESPONSE_LOST');return {status:x.status,ok:x.status>=200&&x.status<300,json:async()=>x.body};};
lines.on('line',line=>{const pending=replies.shift();if(pending)pending(JSON.parse(line));});
async function waitFor(predicate,label){const end=Date.now()+10000;while(!predicate()){if(Date.now()>end)throw Error(label+' '+$('page-feedback').textContent+' '+$('prep-error').textContent+' '+$('run-access-error').textContent);await new Promise(r=>setTimeout(r,10));}}
async function identity(actor){$('token').value='SYNTHETIC_'+actor;$('token').oninput();$('token').listeners.input?.();await tick();}
async function openPrep(goal){await $('prep-list').onclick();const button=$('prep-items').children.find(x=>x.textContent.startsWith(goal+' ·'));check(!!button);await button.onclick();check(run('preparationView.preparation.goal')===goal);}
async function writeEvidence(slot,text){$('prep-slot').value=slot;$('prep-text').value=text;$('prep-source-kind').value='DOCUMENT_EXCERPT';$('prep-source-label').value='SYNTHETIC fresh document';await $('prep-evidence').onsubmit({preventDefault(){}});}
async function readAccess(runId){$('run-access-id').value=runId;await $('run-access-read').onclick();check(run('runAccessContext.runId')===runId);}
function nested(root,predicate){for(const child of root.children){if(predicate(child))return child;const found=nested(child,predicate);if(found)return found;}return null;}
async function fullCase(index,lose){
 const goal='SYNTHETIC_FULL_CASE_'+index;await identity('fixture-a');await $('prep-catalog').onclick();$('prep-reviewer').value='prep-specialist-fixture-a';$('prep-goal').value=goal;await $('prep-create').onsubmit({preventDefault(){}});
 check(run('preparationView!==null'));const ids=run('({preparation:preparationId,case:preparationView.preparation.case_id,run:preparationView.preparation.run_id})');check($('run').value===ids.run);check(run('entryWriteRequests.size')===0);
 await writeEvidence('need_summary','SYNTHETIC new summary '+index);
 if(lose){check(run('prepCommandPending.state')==='UNKNOWN');const postCount=calls.filter(c=>c.options.method==='POST').length;await $('prep-recovery-read').onclick();check(run('prepRecoveryHandle.observed')===true);await $('prep-recovery-release').onclick();check(calls.filter(c=>c.options.method==='POST').length===postCount);check(run('preparationView.current_materials.length')===1);}
 await identity('prep-specialist-fixture-a');await openPrep(goal);$('prep-reason').value='SYNTHETIC request current outline';await $('prep-correction').onclick();check(run('preparationView.preparation.state')==='CHANGES_REQUESTED');
 await identity('fixture-a');await openPrep(goal);await writeEvidence('material_outline','SYNTHETIC new outline '+index);check(run('preparationView.current_materials.length')===2);
 await identity('prep-specialist-fixture-a');await openPrep(goal);$('prep-reason').value='SYNTHETIC independent review '+index;await $('prep-review').onclick();check(run('preparationView.preparation.state')==='REVIEWED');
 await identity('fixture-a');await openPrep(goal);$('prep-reason').value='SYNTHETIC owner confirms '+index;await $('prep-confirm').onclick();check(run('preparationView.preparation.state')==='LOCAL_CONFIRMED');
 // Exact Run authority through the existing isolated owned-test bridge API.
 await readAccess(ids.run);const from=new Date(Date.now()-1000).toISOString(),until=new Date(Date.now()+1200000).toISOString();$('run-access-target').value='executor-a';$('run-access-valid-from').value=from;$('run-access-valid-until').value=until;$('run-access-reason').value='SYNTHETIC exact Run request';await $('run-access-request').onsubmit({preventDefault(){}});await waitFor(()=>run('runAccessView?.state')==='REQUESTED'&&!run('runAccessPending'),'request');
 await identity('prep-specialist-fixture-a');await readAccess(ids.run);const validity=run('runAccessView.request.requested_validity');$('run-access-approved-from').value=validity.valid_from;$('run-access-approved-until').value=validity.valid_until;$('run-access-decision-reason').value='SYNTHETIC bounded independent approval';await $('run-access-approve').onclick();await waitFor(()=>run('runAccessView?.state')==='APPROVED'&&!run('runAccessPending'),'approval');
 await openPrep(goal);await $('dispatch-prepare').onclick();await waitFor(()=>run('dispatchView?.preparation_id')===ids.preparation,'dispatch load');$('dispatch-executor').value='executor-a';$('dispatch-offer-reason').value='SYNTHETIC assigned '+index;await $('dispatch-offer').onsubmit({preventDefault(){}});check(run('dispatchView.current_offer.state')==='OFFERED');check(run('dispatchView.case_id')===ids.case);
 await identity('executor-a');await $('dispatch-list').onclick();const dispatchButton=$('dispatch-items').children.find(x=>x.textContent===goal);check(!!dispatchButton);await dispatchButton.onclick();$('dispatch-decision-reason').value='SYNTHETIC本人accept '+index;await $('dispatch-accept').onclick();check(run('dispatchView.current_offer.state')==='ACCEPTED');const step=run('dispatchView.current_receipt_step_id');check(!!step);
 await $('dispatch-receipt').onclick();await waitFor(()=>run('receiptView?.step.id')===step,'receipt load');check(run('receiptView.step.run_id')===ids.run);check(run('receiptView.step.case_id')===ids.case);$('receipt-text').value='SYNTHETIC actual manual receipt '+index;$('receipt-source').value='SYNTHETIC current work v1';await $('receipt-submit').onsubmit({preventDefault(){}});check(run('receiptView.step.state')==='RECEIPT_RECORDED');
 await identity('fixture-a');await $('receipt-list').onclick();const receiptButton=$('receipt-items').children.find(x=>x.textContent.includes(goal));check(!!receiptButton);await receiptButton.onclick();$('receipt-reason').value='SYNTHETIC owner verifies current receipt '+index;await $('receipt-ack').onclick();check(run('receiptView.step.state')==='LOCAL_ACKNOWLEDGED');
 // P5 requires original resource holds, two-resource confirmation and Case link.
 await $('resource-catalog').onclick();const resources=$('resource-select').children.map(x=>x.value);check(resources.length===2);const holdChecks=[];
 for(const resource of resources){$('resource-select').value=resource;$('resource-quantity').value='1';$('resource-ttl').value='300';$('resource-purpose').value='SYNTHETIC full Case '+index;await $('resource-preview').onclick();check(run('resourcePreview.view.available'));await $('resource-form').onsubmit({preventDefault(){}});const box=nested($('resource-current'),x=>!!x.dataset.combinationHold);check(!!box);holdChecks.push(box);}
 for(const box of holdChecks){box.checked=true;box.onchange();}await $('combination-confirm').onclick();check($('combination-items').children[0]?.dataset.state==='CONFIRMED');const combination=$('combination-items').children[0].dataset.combinationId;
 await openPrep(goal);await $('case-resource-load').onclick();$('case-resource-choice').value=combination;$('case-resource-reason').value='SYNTHETIC associate original resources '+index;await $('case-resource-form').onsubmit({preventDefault(){}});check(run('caseResourceView.current.record.combination_id')===combination);check(run('entryWriteRequests.size')===0);
 await $('local-case-prepare').onclick();check(run('localCaseView.case_id')===ids.case);check(run('localCaseView.preparation_id')===ids.preparation);$('local-case-reason').value='SYNTHETIC revalidate current cycle';await $('local-case-validate').onclick();check(run('localCaseView.can_close_local_record'));
 $('local-case-reason').value='SYNTHETIC close local only';await $('local-case-close').onclick();check(run('localCaseView.local_record_state')==='LOCAL_RECORD_CLOSED');check(run('localCaseView.case_state')==='WAITING_CONFIRMATION');check(run('localCaseView.case_goal_completed')===false);
 $('local-case-reason').value='SYNTHETIC reopen preserves history';await $('local-case-reopen').onclick();check(run('localCaseView.local_record_state')==='REOPENED');check(run('localCaseView.cycle')===2);check(run('localCaseView.history.length')===3);check(run('entryWriteRequests.size')===0);
 milestones.push({...ids,goal,receipt:step,combination,cycle:2});return ids;
}
(async()=>{const a=await fullCase(1,true),b=await fullCase(2,false);check(a.run!==b.run&&a.case!==b.case&&a.preparation!==b.preparation);console.log(JSON.stringify({mode:'full_owned_lifecycle',checks,milestones,scope:'FULL_ORIGINAL_PAGE_HANDLERS_OWNED_PG_ASGI_ISOLATED_ACCESS_NO_BROWSER_NO_FULFILLMENT'}));process.exit(0);})().catch(e=>{console.error(e.stack);process.exit(1);});
