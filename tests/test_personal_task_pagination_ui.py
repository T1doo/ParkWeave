"""Actual personal task handlers with synthetic transport/DOM; no DB or browser."""
import json
from pathlib import Path
import subprocess

import pytest


PROBE = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const elements=new Map();
const $=id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:'',hidden:false,disabled:false,dataset:{},children:[],
 replaceChildren(){this.children=[];this.textContent='';},append(x){this.children.push(x);},addEventListener(){}});return elements.get(id);};
const A='11111111-1111-4111-8111-111111111111',B='22222222-2222-4222-8222-222222222222';
const page=next=>({scope:'SYNTHETIC_LOCAL_PREPARATION_ONLY',read_only:true,recorded_states_only:true,
 role:'enterprise_operator',check_limit:100,items:[],next_before:next,checked_count:100,has_older_records:next!==null});
let calls=[],clears=0,writeClears=0,historyClears=0,failures=0,queue=[];
const context=vm.createContext({$,console,encodeURIComponent,
 prepGeneration:0,preparationId:null,preparationContext:null,prepRole:null,prepLabels:{},
 uuidHandle:x=>typeof x==='string'&&/^[a-f0-9-]{36}$/.test(x),mgCancelTaskRead:()=>{},
 textElement:(tag,text)=>({tag,text,append(){},dataset:{}}),
 entryFetch:async(path,options)=>{calls.push({path,method:options.method,token:options.headers.Authorization});return await queue.shift()();},
 failCurrentEntryRead:()=>failures++,clearEntryWriteRequests:()=>writeClears++,clearReceiptHistory:()=>historyClears++});
context.clearPreparation=()=>{clears++;context.clearPersonalTaskList();context.prepGeneration++;context.preparationId=null;context.preparationContext=null;};
vm.runInContext(input.source,context);
$('token').value='SYNTHETIC_CLIENT_FIXTURE_A';
$('prep-tasks-next').textContent='检查更早的待办事项';
const reply=(status,body=page(null))=>async()=>({status,ok:status===200,json:async()=>body});
const bad=()=>{const status=input.mode.startsWith('403')?403:input.mode.startsWith('401')?401:input.mode==='422'?422:502;
 if(input.mode==='network')return async()=>{throw Error('SYNTHETIC network unavailable');};
 if(input.mode==='malformed')return reply(200,{});
 if(input.mode==='html'||input.mode.endsWith('-html'))return async()=>({status,ok:false,json:async()=>{throw Error('SYNTHETIC non-JSON body');}});
 return reply(status,{detail:'SYNTHETIC refused'});};
async function first(){queue.push(reply(200,page(A)));await $('prep-tasks').onclick();assert.equal($('prep-tasks-next').hidden,false);}
function noRetry(){assert.equal($('prep-tasks-next').hidden,true);assert.equal($('prep-task-items').children.length,0);}
(async()=>{
 if(input.mode.startsWith('late-')){
  await first();let release,started;const begun=new Promise(r=>started=r);
  queue.push(()=>{started();return new Promise(r=>release=r);});
  const old=$('prep-tasks-next').onclick();await begun;
  if(input.mode.includes('identity')){$('token').value='SYNTHETIC_CLIENT_FIXTURE_B';context.clearPreparation();}
  else if(!input.mode.includes('new-read'))context.clearPreparation();
  queue.push(reply(200,page(B)));await $('prep-tasks').onclick();
  const current=$('prep-task-status').textContent;
  release(await reply(input.mode.endsWith('403')?403:200,page(null))());await old;
  assert.equal($('prep-task-status').textContent,current);
  assert.equal($('prep-tasks-next').textContent,'检查更早的待办事项');
  queue.push(reply(200));await $('prep-tasks-next').onclick();
  assert.equal(calls.at(-1).path,'/api/preparation-tasks?before='+B);
  assert.equal(writeClears,0);assert.equal(historyClears,0);
 }else if(input.mode==='navigation-after-failure'||input.mode==='identity-after-failure'){
  await first();queue.push(reply(502));await $('prep-tasks-next').onclick();
  assert.match($('prep-task-status').textContent,/读取失败/);
  if(input.mode.startsWith('identity'))$('token').value='SYNTHETIC_CLIENT_FIXTURE_B';
  context.clearPreparation();noRetry();assert.equal($('prep-task-status').textContent,'');
  queue.push(reply(200));await $('prep-tasks').onclick();assert.equal(calls.at(-1).path,'/api/preparation-tasks');
 }else{
  const firstPage=input.mode==='first-page';if(!firstPage)await first();
  queue.push(bad());await (firstPage?$('prep-tasks').onclick():$('prep-tasks-next').onclick());
  assert.equal(calls.length,firstPage?1:2);assert.equal($('prep-tasks').disabled,false);
  if(['401','403','401-html','403-html','422','malformed'].includes(input.mode)){
   const auth=input.mode.startsWith('401')||input.mode.startsWith('403');
   assert.match($('prep-task-status').textContent,input.mode.startsWith('401')?/会话已失效/:input.mode.startsWith('403')?/当前身份无此事项或操作权限/:/读取失败/);noRetry();
   assert.equal(writeClears,input.mode.startsWith('403')?1:0);assert.equal(historyClears,input.mode.startsWith('403')?1:0);
   assert.equal(clears,auth?1:0);
   queue.push(reply(200));await $('prep-tasks').onclick();assert.equal(calls.at(-1).path,'/api/preparation-tasks');
  }else{
   assert.match($('prep-task-status').textContent,/读取失败/);
   assert.equal($('prep-tasks-next').hidden,false);assert.equal($('prep-tasks-next').textContent,'重试本页待办');
   assert.equal($('page-feedback').textContent,'');assert.equal($('prep-task-items').children.length,0);
   queue.push(reply(200,page(B)));await $('prep-tasks-next').onclick();
   assert.equal(calls.at(-1).path,'/api/preparation-tasks'+(firstPage?'':'?before='+A));
   assert.match($('prep-task-status').textContent,/本页检查/);
   assert.equal($('prep-tasks-next').textContent,'检查更早的待办事项');
   queue.push(reply(200));await $('prep-tasks-next').onclick();assert.equal(calls.at(-1).path,'/api/preparation-tasks?before='+B);
  }
 }
 assert.ok(calls.every(c=>c.method==='GET'));
 process.stdout.write(JSON.stringify({mode:input.mode,result:'PASS',requests:calls.length,business_requests:0}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
"""


@pytest.mark.parametrize("mode", ["502", "html", "network", "malformed", "first-page", "401", "403", "401-html", "403-html", "422",
                                  "late-identity-403", "late-navigation-403", "late-new-read-success",
                                  "identity-after-failure", "navigation-after-failure"])
def test_original_personal_task_pagination_failure_and_explicit_retry(mode):
    page = (Path(__file__).resolve().parents[1] / "src/parkweave/web.html").read_text()
    helpers = [line for line in page.splitlines() if line.startswith(("function prepContext(", "function prepCurrent(",
               "function requirePrepCurrent(", "async function prepCall("))]
    start = page.index("var prepTaskGeneration=")
    end = page.index("\nfunction clearMaterialCorrections", start)
    result = subprocess.run(["node", "-e", PROBE], input=json.dumps({"source": "\n".join(helpers) + "\n" + page[start:end], "mode": mode}),
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["result"] == "PASS"
