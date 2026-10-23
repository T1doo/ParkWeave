"""Original request handoff and navigation, synthetic DOM/transport; no browser."""
import ast
from copy import deepcopy
from html.parser import HTMLParser
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
const document={getElementById:$,body:{dataset:{...input.initial.dataset},
 hasAttribute:name=>name==='data-workspace'&&Object.hasOwn(document.body.dataset,'workspace'),
 getAttribute:name=>name==='data-workspace'?(document.body.dataset.workspace??null):null},
 querySelectorAll:selector=>selector==='[data-tab]'?tabs:selector==='[data-tab][aria-current=page]'?tabs.filter(t=>t.attributes['aria-current']==='page'):[]};
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
$('token').value='SYNTHETIC_A';
for(const row of input.initial.panels)$(row.id).hidden=row.hidden;
tabs.forEach(b=>{const value=input.initial.tabs[b.dataset.tab];if(value!==null)b.setAttribute('aria-current',value);});
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
 const initial=vm.runInContext('('+input.workspaceScript+')()',ctx);
 if(input.establishWorkspace){await tabs[1].onclick();await tabs[0].onclick();}
 const workspaceBefore=vm.runInContext('('+input.workspaceScript+')()',ctx);
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
 const workspaceAfter=vm.runInContext('('+input.workspaceScript+')()',ctx);
 process.stdout.write(JSON.stringify({mode:input.mode,result:'PASS',navigation_HTTP:0,transport:'synthetic',initial,workspaceBefore,workspaceAfter}));
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


def initial_workspace():
    """Read initial attributes; an omitted body has no data-workspace attribute."""
    class InitialHTML(HTMLParser):
        def __init__(self):
            super().__init__()
            self.dataset = {}
            self.tabs = {}
            self.panels = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'body' and 'data-workspace' in attrs:
                self.dataset['workspace'] = attrs['data-workspace']
            if tag == 'button' and 'data-tab' in attrs:
                self.tabs[attrs['data-tab']] = attrs.get('aria-current')
            if tag == 'section' and attrs.get('id') in ('service', 'collaboration', 'resource'):
                self.panels.append(dict(id=attrs['id'], hidden='hidden' in attrs))

    parser = InitialHTML()
    parser.feed((Path(__file__).resolve().parents[1] / 'src/parkweave/web.html').read_text())
    return dict(dataset=parser.dataset, tabs=parser.tabs, panels=parser.panels)


def driver_workspace_contract():
    """Load only the actual pure oracle and JS observation, no browser imports."""
    source = (Path(__file__).resolve().parents[1] / 'scripts/workspace_visual_browser_once.py').read_text()
    tree = ast.parse(source)
    script = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'NAVIGATION_WORKSPACE_SCRIPT' for t in n.targets))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'assert_navigation_workspace')
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<actual-driver-workspace-contract>', 'exec'), namespace)
    return script, namespace['assert_navigation_workspace']


@pytest.mark.parametrize("mode", ["unknown-post", "unknown-readback", "normal", "discard", "objection"])
def test_original_unknown_material_navigation_preserves_context(mode):
    source, wrapper = original_source()
    workspace_script, contract = driver_workspace_contract()
    initial = initial_workspace()
    assert initial['dataset'] == {}  # Current product starts in service without this attribute.
    stubs = "clearRecordDirectory clearRuntimeNavigation clearPersonalTaskList mgClear clearCaseCancellation clearDeadline clearOpportunities clearFactBundle clearObjections clearRunAccess clearCaseFacts clearMaterialReuse clearMaterialDraft clearMaterialCorrections resetPreparationDraft clearReadiness clearPlanMaterialNavigation clearNotices clearLocalCase clearDispatch clearCaseResources clearReceipts invalidatePreparationRead clearResources prepCatalogStatus".split()
    for establish in ([False, True] if mode.startswith('unknown-') else [False]):
        run = subprocess.run(["node", "-e", PROBE], input=json.dumps({"source": source, "wrapper": wrapper, "stubs": stubs,
                             "mode": mode, "initial": initial, "workspaceScript": workspace_script, "establishWorkspace": establish}),
                             text=True, capture_output=True, timeout=10)
        assert run.returncode == 0, run.stderr
        result = json.loads(run.stdout)
        assert {k: result[k] for k in ('mode', 'result', 'navigation_HTTP', 'transport')} == {
            "mode": mode, "result": "PASS", "navigation_HTTP": 0, "transport": "synthetic"}
        assert result['initial']['workspace'] == {'present': False, 'value': None}
        if mode.startswith('unknown-'):
            before, after = result['workspaceBefore'], result['workspaceAfter']
            assert before['workspace'] == {'present': establish, 'value': 'service' if establish else None}
            contract(before, after)
            # Reject appearance/disappearance and drift, not a permissive null-or-service fallback.
            for replacement in ({'present': not establish, 'value': None if establish else 'service'},
                                {'present': True, 'value': 'resource'}):
                changed = deepcopy(after); changed['workspace'] = replacement
                with pytest.raises(AssertionError): contract(before, changed)
            for current in (['resource'], ['service', 'resource']):
                changed = deepcopy(after); changed['current'] = current
                with pytest.raises(AssertionError): contract(before, changed)
            changed = deepcopy(after); changed['panels'][0]['hidden'] = True
            with pytest.raises(AssertionError): contract(before, changed)
            # Equality alone must not accept an invalid initial snapshot.
            for workspace in ({'present': False, 'value': 'service'}, {'present': True, 'value': None},
                              {'present': True, 'value': 'resource'}):
                invalid = deepcopy(before); invalid['workspace'] = workspace
                with pytest.raises(AssertionError): contract(invalid, deepcopy(invalid))
