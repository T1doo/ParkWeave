"""Original preparation entry with synthetic transport and DOM; no browser or DB."""
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
 crypto:require('node:crypto'),loadPreparation:async id=>loaded.push(id),
 document:{querySelectorAll:()=>[]},objectionLock:()=>false,
 textElement:(tag,text)=>({tag,textContent:text}),
 entryFetch:async(path,options)=>{
  requests.push({path,method:options.method,body:options.body&&JSON.parse(options.body)});
  return queue.shift()();
 },
 clearEntryWriteRequests:()=>deniedClears++,clearReceiptHistory:()=>{},
});
const loaded=[];
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
  assert.match($('prep-catalog-status').textContent,input.mode==='empty-service'?/暂无可用服务/:input.mode==='empty-reviewer'?/暂无可选核对专员/:/核对本次目标/);
  assert.equal($('prep-create').hidden,input.mode!=='ready');
  if(input.mode==='ready')assert.equal($('prep-service').value,'0');
 }else if(input.mode==='service-version'){
  const newer={...service,version:2};
  reply(catalog([service,newer],[{id:'SYNTHETIC_REVIEWER'}]));
  await $('prep-catalog').onclick();
  const select=$('prep-service'),submit=()=>$('prep-create').onsubmit({preventDefault(){}});
  assert.equal(select.value,'');
  assert.deepEqual(select.children.map(option=>option.value),['','0','1']);
  assert.equal(select.children[0].disabled,true);
  assert.match(select.children[2].textContent,/v2$/);
  await submit();
  assert.equal(requests.length,1);
  assert.match($('prep-error').textContent,/请选择当前目录中的服务与版本/);
  select.value='1';$('prep-reviewer').value='SYNTHETIC_REVIEWER';$('prep-goal').value='本次目标';
  reply({run_id:'new-run'});reply({state:'SUCCEEDED'});reply({preparation_id:'new-preparation'});
  await submit();
  assert.deepEqual(requests.slice(1),[
   {path:'/api/runs',method:'POST',body:{goal:'本次目标'}},
   {path:'/api/runs/new-run',method:'GET',body:undefined},
   {path:'/api/preparations',method:'POST',body:{run_id:'new-run',service_id:service.service_id,service_version:2,reviewer_id:'SYNTHETIC_REVIEWER'}},
  ]);
  assert.deepEqual(loaded,['new-preparation']);
  reply(ready());await $('prep-catalog').onclick();
  assert.equal(select.value,'0');
  assert.deepEqual(select.children.map(option=>option.value),['0']);
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
 if(input.mode!=='service-version')assert.ok(requests.every(r=>r.path==='/api/preparation-catalog'&&r.method==='GET'));
 process.stdout.write(JSON.stringify({mode:input.mode,result:'PASS',transport:'synthetic',business_POSTs:requests.filter(r=>r.method==='POST').length}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
"""


def source_parts():
    page = (Path(__file__).resolve().parents[1] / "src/parkweave/web.html").read_text(encoding="utf-8")
    functions = ("prepContext", "prepCurrent", "requirePrepCurrent", "prepCall", "clearPreparation", "prepError")
    lines = page.splitlines()
    source = "\n".join(line for line in lines if any(
        line.startswith(prefix + name + "(") for name in functions for prefix in ("function ", "async function ")))
    start = page.index("function preparationClearRefusal(")
    source += "\n" + page[start:page.index("\nfunction clearPreparation(", start)]
    start = page.index("function prepCatalogStatus(") if "function prepCatalogStatus(" in page else page.index("$('prep-catalog').onclick=")
    source += "\n" + page[start:page.index("\nlet runtimeNavigationGeneration=", start)]
    declarations = "let prepGeneration=0,preparationId=null,preparationContext=null,preparationView=null,prepRole=null,prepCatalog=null,prepCommandPending=null,prepRecoveryHandle=null,prepRecoveryChecking=false;const prepRetries=new Map();\n"
    return declarations + source


@pytest.mark.parametrize("mode", ["empty-service", "empty-reviewer", "ready", "service-version", "loading", "failure-retry", "invalid", "late-navigation", "late-identity-aba", "protected-clear"])
def test_catalog_feedback_on_original_get_handler(mode):
    stubs = "clearRuntimeNavigation clearPersonalTaskList mgClear clearCaseCancellation clearDeadline clearOpportunities clearFactBundle clearObjections clearRunAccess clearCaseFacts clearMaterialReuse clearMaterialDraft clearMaterialCorrections renderPrepCommandPending resetPreparationDraft clearReadiness clearPlanMaterialNavigation clearNotices clearLocalCase clearDispatch clearCaseResources clearReceipts invalidatePreparationRead failCurrentEntryRead".split()
    run = subprocess.run(["node", "-e", PROBE], input=json.dumps({"source": source_parts(), "stubs": stubs, "mode": mode}),
                         text=True, capture_output=True, timeout=10)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == {"mode": mode, "result": "PASS", "transport": "synthetic", "business_POSTs": 2 if mode == "service-version" else 0}
