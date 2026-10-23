"""Original catalog GET handler with synthetic transport/DOM; no browser or DB."""
import json
from pathlib import Path
import subprocess

import pytest


PROBE = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,{
 value:'',textContent:'',children:[],hidden:false,disabled:false,dataset:{},attributes:{},
 setAttribute(k,v){this.attributes[k]=v;},replaceChildren(){this.children=[];this.textContent='';},
 append(x){this.children.push(x);},reset(){},});return nodes.get(id);};
const scope='SYNTHETIC_LOCAL_PREPARATION_ONLY';
const service={service_id:'fixture-service',version:1,name:'合成资料整理',source:{kind:'SYNTHETIC',statement:'仅限本地演示'}};
const catalog=(services=[],reviewers=[])=>({scope,services,reviewers,required_slots:['need_summary','material_outline']});
const ready=()=>catalog([service],[{id:'SYNTHETIC_REVIEWER'}]);
const queue=[],requests=[];let deniedClears=0;
const context=vm.createContext({$,console,Map,Error,Object,Number,Array,
 document:{querySelectorAll:()=>[]},objectionLock:()=>false,
 textElement:(tag,text)=>({tag,textContent:text}),
 entryFetch:async(path,options)=>{requests.push({path,method:options.method});return queue.shift()();},
 clearEntryWriteRequests:()=>deniedClears++,clearReceiptHistory:()=>{},
});
for(const name of input.stubs)context[name]=()=>{};
vm.runInContext(input.source,context);
$('token').value='SYNTHETIC_IDENTITY_A';
const response=(body,status=200)=>({status,ok:status===200,json:async()=>body});
const reply=(body,status=200)=>queue.push(async()=>response(body,status));
const state=()=>$('prep-catalog-status').dataset.state;
const emptyView=()=>{assert.equal($('prep-catalog-view').children.length,0);assert.equal($('prep-reviewer').children.length,0);assert.equal($('prep-create').hidden,true);};
const settled=()=>{assert.notEqual($('prep-catalog-view').attributes['aria-busy'],'true');assert.equal($('prep-catalog').disabled,false);};
(async()=>{
 if(input.mode==='protected-clear'){
  vm.runInContext('prepCommandPending={state:"UNKNOWN"}',context);
  await assert.rejects($('prep-catalog').onclick(),/核对当前材料操作结果/);
  assert.equal(requests.length,0);assert.notEqual(state(),'LOADING');
  assert.match($('prep-command-feedback').textContent,/仍待核对/);
 }else if(input.mode==='empty-service'||input.mode==='empty-reviewer'||input.mode==='ready'){
  reply(input.mode==='empty-service'?catalog():input.mode==='empty-reviewer'?catalog([service]):ready());
  await $('prep-catalog').onclick();settled();
  assert.match($('prep-catalog-status').textContent,input.mode==='empty-service'?/暂无可用服务/:input.mode==='empty-reviewer'?/暂无可选核对专员/:/填写本次目标/);
  assert.equal($('prep-create').hidden,input.mode!=='ready');
 }else if(input.mode==='failure-retry'){
  reply(ready());await $('prep-catalog').onclick();
  reply({},403);await $('prep-catalog').onclick();emptyView();settled();
  assert.equal(state(),'DENIED');assert.equal(deniedClears,1);assert.match($('page-feedback').textContent,/权限/);
  reply(ready());await $('prep-catalog').onclick();assert.equal(state(),'READY');settled();
 }else if(input.mode==='invalid'){
  for(const body of [{}, {...catalog(),scope:'WRONG'},catalog([{}]),catalog([service],[{}])]){
   reply(body);await $('prep-catalog').onclick();emptyView();settled();assert.equal(state(),'ERROR');
   assert.match($('prep-catalog-status').textContent,/未取得/);
  }
 }else{
  let release;queue.push(()=>new Promise(resolve=>release=resolve));
  const pending=$('prep-catalog').onclick();assert.equal(state(),'LOADING');
  assert.equal($('prep-catalog-view').attributes['aria-busy'],'true');assert.equal($('prep-catalog').disabled,true);
  if(input.mode==='loading'){release(response(ready()));await pending;assert.equal(state(),'READY');settled();}
  else{
   if(input.mode==='late-identity-aba'){$('token').value='SYNTHETIC_IDENTITY_B';context.clearPreparation();$('token').value='SYNTHETIC_IDENTITY_A';context.clearPreparation();}
   else context.clearPreparation();
   let releaseNew;queue.push(()=>new Promise(resolve=>releaseNew=resolve));const newer=$('prep-catalog').onclick();
   release(response({},403));await pending;
   assert.equal(state(),'LOADING');assert.equal($('prep-catalog').disabled,true);assert.equal(deniedClears,0);
   releaseNew(response(ready()));await newer;assert.equal(state(),'READY');settled();
  }
 }
 assert.ok(requests.every(r=>r.path==='/api/preparation-catalog'&&r.method==='GET'));
 process.stdout.write(JSON.stringify({mode:input.mode,result:'PASS',transport:'synthetic',business_POSTs:0}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
"""


def source_parts():
    page = (Path(__file__).resolve().parents[1] / "src/parkweave/web.html").read_text()
    functions = ("prepContext", "prepCurrent", "requirePrepCurrent", "prepCall", "clearPreparation", "prepError")
    lines = page.splitlines()
    source = "\n".join(line for line in lines if any(
        line.startswith(prefix + name + "(") for name in functions for prefix in ("function ", "async function ")))
    start = page.index("function prepCatalogStatus(") if "function prepCatalogStatus(" in page else page.index("$('prep-catalog').onclick=")
    source += "\n" + page[start:page.index("\nasync function retryWrite(", start)]
    declarations = "let prepGeneration=0,preparationId=null,preparationContext=null,preparationView=null,prepRole=null,prepCatalog=null,prepCommandPending=null,prepRecoveryHandle=null,prepRecoveryChecking=false;const prepRetries=new Map();\n"
    return declarations + source


@pytest.mark.parametrize("mode", ["empty-service", "empty-reviewer", "ready", "loading", "failure-retry", "invalid", "late-navigation", "late-identity-aba", "protected-clear"])
def test_catalog_feedback_on_original_get_handler(mode):
    stubs = "clearRuntimeNavigation clearPersonalTaskList mgClear clearCaseCancellation clearDeadline clearOpportunities clearFactBundle clearObjections clearRunAccess clearCaseFacts clearMaterialReuse clearMaterialDraft clearMaterialCorrections renderPrepCommandPending resetPreparationDraft clearReadiness clearPlanMaterialNavigation clearNotices clearLocalCase clearDispatch clearCaseResources clearReceipts invalidatePreparationRead failCurrentEntryRead".split()
    run = subprocess.run(["node", "-e", PROBE], input=json.dumps({"source": source_parts(), "stubs": stubs, "mode": mode}),
                         text=True, capture_output=True, timeout=10)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == {"mode": mode, "result": "PASS", "transport": "synthetic", "business_POSTs": 0}
