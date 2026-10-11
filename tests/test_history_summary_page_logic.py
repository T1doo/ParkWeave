"""Node VM + synthetic DOM unit checks; never starts or replaces a browser."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from parkweave import history_summary as hs
from test_history_summary import sample

WEB = Path(__file__).resolve().parents[1]/'src/parkweave/web.html'
HARNESS = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const payload=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
class Element {
 constructor(id){this.id=id;this.value='';this.textContent='';this.children=[];this.dataset={};this.style={};this.hidden=false;this.disabled=false;this.checked=false;this.elements=new Proxy([],{get:(a,k)=>k in a?a[k]:(a[k]=new Element(String(k)))});this.listeners={};this.classList={add(){},remove(){},toggle(){}};}
 addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
 replaceChildren(...x){this.children=x;this.textContent='';}
 append(...x){this.children.push(...x);}
 get firstElementChild(){return this.children[0]??null;}
 reset(){} setAttribute(){} removeAttribute(){} focus(){} scrollIntoView(){}
 querySelectorAll(){return [];} querySelector(){return null;}
}
const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element(id));return elements.get(id);};
const tabs=['service','collaboration','resource'].map(x=>{const e=new Element(x);e.dataset.tab=x;return e;});
const events={},storage=new Map(),requests=[];
const context={console,URL,URLSearchParams,TextEncoder,structuredClone,crypto:require('node:crypto').webcrypto,
 setTimeout,clearTimeout,setInterval,clearInterval,
 localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 document:{addEventListener(){},getElementById:get,querySelectorAll:s=>s==='[data-tab]'?tabs:[],querySelector:()=>null,createElement:tag=>new Element(tag),body:{dataset:{}}},
 window:{addEventListener:(name,fn)=>(events[name]??=[]).push(fn)},
 fetch:(url,options)=>new Promise(resolve=>requests.push({url,options,resolve}))};
vm.createContext(context);vm.runInContext(payload.script,context,{timeout:2000});
const run=s=>vm.runInContext(s,context,{timeout:2000});
get('token').value='SYNTHETIC_SESSION';get('run').value='SYNTHETIC_RUN_A';
get('history-summary-case').value=payload.reply.case_id;
get('history-summary-preparation').value=payload.reply.preparation_id;
get('history-summary-stage').value='P5';get('history-summary-key').value='synthetic-key';
const text=e=>e.textContent+e.children.map(text).join(' ');
const result=()=>text(get('history-summary-result'));
const complete=(r,ok=true,reply=payload.reply)=>r.resolve({ok,text:async()=>JSON.stringify(reply)});
const clear=async mode=>{
 if(mode==='pagehide')events.pagehide.forEach(fn=>fn({}));
 else if(mode==='pageshow')events.pageshow.forEach(fn=>fn({persisted:true}));
 else if(mode==='token-property'){get('token').value='SYNTHETIC_OTHER_SESSION';get('token').oninput();get('token').value='SYNTHETIC_SESSION';}
 else if(mode==='run-a-b-a'){get('run').value='SYNTHETIC_RUN_B';get('run').oninput();get('run').value='SYNTHETIC_RUN_A';get('run').oninput();}
 else if(mode==='preparation-clear')run('clearPreparation(false,false,true)');
 else if(mode==='preparation-load-blocked'){run("prepCommandPending={};");await run("loadPreparation('SYNTHETIC_OTHER_PREPARATION')").catch(()=>{});}
 else if(mode==='plan-load-blocked')await run("loadPlan('')").catch(()=>{});
 else if(mode==='local-case-clear')run('clearLocalCase()');
 else if(mode==='service-case-clear')run('clearServiceCasePlan()');
 else if(mode==='plan-clear')run('clearPlan()');
 else if(mode==='local-case-load-blocked')await run("loadLocalCase('')").catch(()=>{});
 else if(mode==='service-case-load-blocked')await run("loadServiceCasePlan('')").catch(()=>{});
 else if(mode.endsWith('-input-a-b-a')){
  const id='history-summary-'+mode.split('-input')[0],e=get(id),original=e.value;
  e.value='SYNTHETIC_OTHER_VALUE';e.listeners.input.forEach(fn=>fn());
  e.value=original;e.listeners.input.forEach(fn=>fn());
 }
 else if(mode==='tab')tabs[0].listeners.click.forEach(fn=>fn({}));
 else throw Error('unknown clearing path');
};
(async()=>{
 if(payload.action==='clear-rendered'){
  const read=get('history-summary-read').onclick();assert.equal(requests.length,1);complete(requests[0]);await read;
  assert.match(result(),/P5 FAILED/);assert.match(result(),/NEEDS_INPUT/);
  await clear(payload.mode);assert.equal(result(),'');assert.equal(get('history-summary-status').textContent,'');
 }else if(payload.action==='clear-pending'){
  const read=get('history-summary-read').onclick();assert.equal(requests.length,1);
  await clear(payload.mode);const generation=run('historySummaryGeneration');assert.ok(generation>1);
  complete(requests[0],payload.ok);await read;assert.equal(result(),'');assert.equal(get('history-summary-error').textContent,'');
 }else if(payload.action==='latest'){
  const first=get('history-summary-read').onclick(),second=get('history-summary-read').onclick();assert.equal(requests.length,2);
  complete(requests[1]);await second;const latest=result();assert.match(latest,/P5 FAILED/);
  complete(requests[0],payload.ok);await first;assert.equal(result(),latest);assert.equal(get('history-summary-error').textContent,'');
 }else if(payload.action==='projection'){
  const poisoned=structuredClone(payload.reply);
  if(payload.poison==='body')poisoned.history[0].summary.body='PRIVATE_MATERIAL';
  else if(payload.poison==='case')poisoned.case_id='00000000-0000-0000-0000-000000000000';
  else if(payload.poison==='result')poisoned.result={...poisoned.result,request_key:'other'};
  else if(payload.poison==='duplicate')poisoned.history.push(poisoned.history[0]);
  const read=get('history-summary-read').onclick();complete(requests[0],true,poisoned);await read;
  assert.equal(result(),'');assert.match(get('history-summary-error').textContent,/不可用/);
 }else if(payload.action==='unavailable'){
  const read=get('history-summary-read').onclick();complete(requests[0],false);await read;
  assert.equal(result(),'');assert.match(get('history-summary-error').textContent,/未登记/);assert.equal(get('history-summary-status').textContent,'');
 }
 assert.equal(storage.size,0);assert.equal(requests.filter(r=>r.options.method&&r.options.method!=='GET').length,0);
 process.stdout.write(JSON.stringify({passed:true,requests:requests.length,browser_started:false}));
})().catch(e=>{console.error(e);process.exitCode=1;});
'''


def run_logic(**scenario):
    context,baseline,row,_=sample('P5')
    rows=(row,)
    reply=hs.summaries('P5',baseline,context,rows,'synthetic-key')
    reply.update(case_id=context.case,stage='P5')
    # Original pure fixture is unexecuted; use the supported actual failed Case
    # projection to exercise historical display independently of browser layout.
    for d in [reply['result'],reply['history'][0]['summary']]:
        d.update(p5_state='FAILED',past_case_state='NEEDS_INPUT',past_cycle=1,verification_at_execution=False)
    script=WEB.read_text().split('<script>',1)[1].split('</script>',1)[0]
    node=shutil.which('node');assert node is not None,'existing Node runtime required'
    result=subprocess.run([node,'-e',HARNESS],input=json.dumps(dict(script=script,reply=reply,**scenario)),text=True,capture_output=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['browser_started'] is False


CLEAR_PATHS=['pagehide','pageshow','token-property','run-a-b-a','preparation-clear','preparation-load-blocked','plan-load-blocked','local-case-clear','service-case-clear','plan-clear','local-case-load-blocked','service-case-load-blocked','tab','case-input-a-b-a','preparation-input-a-b-a','key-input-a-b-a','stage-input-a-b-a']

@pytest.mark.parametrize('mode',CLEAR_PATHS)
def test_original_programmatic_paths_clear_rendered_summary(mode):
    run_logic(action='clear-rendered',mode=mode)


@pytest.mark.parametrize('mode',CLEAR_PATHS)
@pytest.mark.parametrize('ok',[True,False])
def test_original_programmatic_paths_invalidate_late_success_and_denial(mode,ok):
    run_logic(action='clear-pending',mode=mode,ok=ok)


@pytest.mark.parametrize('ok',[True,False])
def test_newest_same_context_summary_request_keeps_new_result(ok):
    run_logic(action='latest',ok=ok)


@pytest.mark.parametrize('poison',['body','case','result','duplicate'])
def test_page_projection_refuses_private_or_uncorrelated_reply(poison):
    run_logic(action='projection',poison=poison)


def test_unavailable_page_never_claims_registered_empty_history():
    run_logic(action='unavailable')
