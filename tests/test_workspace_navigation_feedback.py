"""Original request handoff and navigation, synthetic DOM/transport; no browser."""
import json
from pathlib import Path
import subprocess

import pytest


PROBE = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const nodes=new Map(),clears=[],requests=[];
const $=id=>{if(!nodes.has(id))nodes.set(id,{id,value:'',textContent:'',hidden:false,disabled:false,dataset:{},attributes:{},children:[],
 setAttribute(k,v){this.attributes[k]=v;},replaceChildren(){this.children=[];this.textContent='';},reset(){},append(x){this.children.push(x);}});return nodes.get(id);};
const tabs=['service','collaboration','resource'].map(id=>{const b=$('nav-'+id);b.dataset.tab=id;return b;});
const document={getElementById:$,body:{dataset:{workspace:'service'}},querySelectorAll:selector=>selector==='[data-tab]'?tabs:[]};
let observedLease=false,stored=null;
const ctx=vm.createContext({document,console,Error,Map,Set,WeakMap,Proxy,Reflect,encodeURIComponent,
 fetch:async(path,options)=>{
  requests.push({path,method:options.method});observedLease=vm.runInContext('entryWriteRequests.size===1&&activeEntryWriteFlow.requests.size===1',ctx);
  if(input.mode==='unknown-readback'&&options.method==='POST')return {ok:true,status:200,json:async()=>({preparation_id:'11111111-1111-4111-8111-111111111111'})};
  throw Error('SYNTHETIC transport failure');
 },
 rememberPrepRecovery:p=>{stored={id:p.context.id,key:p.key};},readPrepRecovery:()=>stored,
 sendClarification:()=>{},objectionLock:()=>input.mode==='objection',
 pauseClockUnresolved:()=>false,tiUnresolved:()=>false,receiptSubmitStoredPending:()=>false,dispatchAcceptStoredPending:()=>false,
 materialPackagePending:()=>false,planSourceConflictPending:()=>false,coldUnresolved:()=>false,
 serviceSelectionHandles:()=>[],planCandidateHandles:()=>[],mgHandles:()=>[],
});
for(const name of input.stubs)ctx[name]=()=>{clears.push(name);$('sentinel-'+name).textContent='CLEARED';};
ctx.renderPrepCommandPending=()=>{};ctx.renderPreparationReadControls=()=>{};ctx.renderMaterialReviewControls=()=>{};
vm.runInContext(input.source,ctx);
$('token').value='SYNTHETIC_A';$('service').hidden=false;$('collaboration').hidden=true;$('resource').hidden=true;
tabs.forEach(b=>b.setAttribute('aria-current',b.dataset.tab==='service'?'page':'false'));
// Install the exact original non-mutating entry wrapper around the original navigation.
const install=vm.runInContext('(element,fn)=>{'+input.wrapper+'}',ctx);
for(const element of tabs)install(element,element.onclick);
const capture=()=>JSON.stringify({workspace:document.body.dataset.workspace,tabs:tabs.map(t=>t.attributes),
 views:[...nodes].filter(([id])=>!['page-feedback','result','prep-command-feedback'].includes(id)).map(([id,n])=>[id,n.value,n.textContent,n.hidden,n.children]),
 pending:vm.runInContext('JSON.stringify(prepCommandPending)',ctx),stored,clears:[...clears]});
async function unknown(){
 vm.runInContext(`preparationId='11111111-1111-4111-8111-111111111111';
 const pending={context:prepContext(),path:'/api/preparations/'+preparationId+'/commands',key:'22222222-2222-4222-8222-222222222222',body:{action:'ADD_EVIDENCE',expected_revision:1,text:'SYNTHETIC draft'},draft:'SYNTHETIC draft'};
 pending.context.caseId='33333333-3333-4333-8333-333333333333';pending.context.revision=1;
 originalSend=trackedEntryFunction(sendPrepCommand,'sendPrepCommand',new Set(['sendPrepCommand']));`,ctx);
 await assert.rejects(vm.runInContext('originalSend(pending)',ctx),/SYNTHETIC transport failure/);
 assert.equal(observedLease,true);assert.equal(vm.runInContext('prepCommandPending.state',ctx),'UNKNOWN');
 assert.equal(vm.runInContext('entryWriteRequests.size',ctx),0);assert.equal(vm.runInContext('activeEntryWriteFlow',ctx),null);
 assert.equal(vm.runInContext('entryReadAllowed("nav-resource")',ctx),true);
}
(async()=>{
 if(input.mode.startsWith('unknown-')||input.mode==='discard'){
  await unknown();for(const name of input.stubs)$('sentinel-'+name).textContent='PRESERVED';clears.length=0;
  if(input.mode==='discard'){
   vm.runInContext('clearPreparation(false,false,true)',ctx);
   assert.equal(vm.runInContext('prepCommandPending',ctx),null);assert.ok(clears.length>0);assert.ok(stored);
  }else{
   const before=capture(),count=requests.length;
   let failure=null;try{await tabs[2].onclick();}catch(e){failure=e;}
   if(failure)console.error(JSON.stringify({unhandled_navigation_error:failure.message,child_clearers_before_rejection:clears}));
   assert.equal(clears.length,0,'refused navigation ran child clearers');assert.equal(failure,null);
   assert.equal(capture(),before,'refused navigation cleared protected state');assert.equal(requests.length,count);
   assert.match($('page-feedback').textContent,/核对当前材料操作结果/);assert.equal($('page-feedback').dataset.tone,'error');
  }
 }else if(input.mode==='objection'){
  const before=capture();assert.throws(()=>vm.runInContext('clearPreparation()',ctx),/核对原异议操作/);
  assert.equal(capture(),before,'refused clear must run no child clearer');
  vm.runInContext('clearPreparation(false,false,true)',ctx);assert.ok(clears.length>0);
 }else{
  for(const tab of [tabs[1],tabs[2],tabs[0]]){
   await tab.onclick();assert.equal(document.body.dataset.workspace,tab.dataset.tab);
   for(const t of tabs){assert.equal(t.attributes['aria-current'],t===tab?'page':'false');assert.equal($(t.dataset.tab).hidden,t!==tab);}
  }
  assert.equal(requests.length,0);assert.equal($('page-feedback').textContent,'');assert.ok(clears.length>0);
 }
 process.stdout.write(JSON.stringify({mode:input.mode,result:'PASS',navigation_HTTP:0,transport:'synthetic'}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
"""


def original_source():
    page = (Path(__file__).resolve().parents[1] / "src/parkweave/web.html").read_text()
    lines = page.splitlines()
    names = ("prepContext", "prepCurrent", "requirePrepCurrent", "prepCall", "clearPreparation", "clearGeneric", "sendPrepCommand", "failEntryFlow", "entryWriteDomain")
    source = "\n".join(line for line in lines if any(line.startswith(p + n + "(") for n in names for p in ("function ", "async function ")))
    source += "\n" + next(line for line in lines if line.startswith("const $=id=>"))
    for start, end in [("function originalWriteOwnerRetains(", "\nfunction retainDeniedOperationReference("),
                       ("function entryReadAllowed(", "\nfunction blockIndependentEntryUI(")]:
        source += "\n" + page[page.index(start):page.index(end, page.index(start))]
    if "function preparationClearRefusal(" in page:
        start = page.index("function preparationClearRefusal(")
        source += "\n" + page[start:page.index("\nfunction clearPreparation(", start)]
    start = page.index("document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=")
    source += "\n" + page[start:page.index("\n$('intake').onsubmit=", start)]
    begin = page.index("element[event]=async function(...args){if(!entryReadAllowed(element.id))")
    wrapper = page[begin:page.index(";}}", begin)+1].replace("element[event]=", "element.onclick=", 1)
    declarations = "let pageGeneration=0,currentReview=null,lastClarification=null,clarificationKey=null,prepGeneration=0,preparationId=null,preparationContext=null,preparationView=null,prepRole=null,prepCatalog=null,prepCommandPending=null,prepRecoveryHandle=null,prepRecoveryChecking=false,pauseClockBusy=false,templateEntryGeneration=0,activeEntryWriteFlow=null;const prepRetries=new Map(),entryWriteRequests=new Map(),entryFailureFlows=new WeakMap(),capturedCancelFrontierRequests=new WeakMap();\n"
    return declarations + source, wrapper


@pytest.mark.parametrize("mode", ["unknown-post", "unknown-readback", "normal", "discard", "objection"])
def test_original_unknown_material_navigation_preserves_context(mode):
    source, wrapper = original_source()
    stubs = "clearRecordDirectory clearRuntimeNavigation clearPersonalTaskList mgClear clearCaseCancellation clearDeadline clearOpportunities clearFactBundle clearObjections clearRunAccess clearCaseFacts clearMaterialReuse clearMaterialDraft clearMaterialCorrections resetPreparationDraft clearReadiness clearPlanMaterialNavigation clearNotices clearLocalCase clearDispatch clearCaseResources clearReceipts invalidatePreparationRead clearResources prepCatalogStatus".split()
    run = subprocess.run(["node", "-e", PROBE], input=json.dumps({"source": source, "wrapper": wrapper, "stubs": stubs, "mode": mode}),
                         text=True, capture_output=True, timeout=10)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == {"mode": mode, "result": "PASS", "navigation_HTTP": 0, "transport": "synthetic"}
