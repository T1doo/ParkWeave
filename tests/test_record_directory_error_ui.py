"""Original directory handler with synthetic transport/DOM doubles; no DB or browser.

The hosted Chrome smoke separately exercises the full original page and real clicks.
"""
import json
from pathlib import Path
import subprocess

import pytest


PROBE = r"""
const vm = require('node:vm');
const assert = require('node:assert/strict');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const elements = new Map();
const $ = id => {
  if (!elements.has(id)) {
    const element={value:'',dataset:{},disabled:false,hidden:false,children:[],firstChild:null,
      replaceChildren(){this.textContent='';},append(x){this.children.push(x);}};
    let text='';
    Object.defineProperty(element,'textContent',{get(){return text;},set(value){
      text=String(value);element.firstChild=text?{data:text}:null;element.children=[];
    }});
    elements.set(id,element);
  }
  return elements.get(id);
};
const empty = {scope:'CURRENT_OWNER_LOCAL_CASE_RECORDS',read_only:true,
  automatically_replayed:false,items:[],next_after:null};
function response(status, malformed=false){return {status,ok:status===200,
  async json(){if(malformed) throw Error('SYNTHETIC_NON_JSON_BODY');return status===200?empty:{detail:'denied'};}};}
const context = vm.createContext({$, clearCaseWorklist:()=>{},
  document:{createElement:()=>({})}, entryFetch:null,
  show:x=>{$('result').textContent=JSON.stringify(x);$('page-feedback').dataset.tone=x.error?'error':'success';$('page-feedback').textContent=x.error||'';}});
context.clearGeneric=()=>{context.clearRecordDirectory();$('result').textContent='';};
vm.runInContext(input.source,context);
$('token').value='SYNTHETIC_CLIENT_FIXTURE_A';
(async()=>{
  if(input.mode==='late-success'){
    let release,started,calls=0;
    const retryStarted=new Promise(resolve=>started=resolve);
    context.entryFetch=()=>{calls++;if(calls===1)return Promise.resolve(response(403));started();return new Promise(resolve=>release=resolve);};
    await context.loadRecordDirectory();
    const retry=context.loadRecordDirectory();await retryStarted;
    $('token').value='SYNTHETIC_CLIENT_FIXTURE_B';context.clearGeneric();
    context.show({error:'SYNTHETIC_OTHER_OPERATION'});
    release(response(200));await retry;
    assert.equal($('page-feedback').textContent,'SYNTHETIC_OTHER_OPERATION');
    assert.equal($('record-directory-status').textContent,'');
  }else if(['other-feedback','same-feedback','during-read','transient-retry'].includes(input.mode)){
    let release,started,calls=0;
    const retryStarted=new Promise(resolve=>started=resolve);
    context.entryFetch=()=>{calls++;
      if(calls===1)return Promise.resolve(response(403));
      if(input.mode==='during-read'){started();return new Promise(resolve=>release=resolve);}
      return Promise.resolve(response(input.mode==='transient-retry'&&calls===2?502:200));
    };
    await context.loadRecordDirectory();const original=$('page-feedback').textContent;
    const nextMessage=input.mode==='same-feedback'?original:'SYNTHETIC_OTHER_OPERATION';
    if(input.mode==='other-feedback'||input.mode==='same-feedback')context.show({error:nextMessage});
    const retry=context.loadRecordDirectory();
    if(input.mode==='during-read'){await retryStarted;context.show({error:nextMessage});release(response(200));}
    await retry;
    if(input.mode==='transient-retry'){
      assert.equal($('page-feedback').textContent,original);
      await context.loadRecordDirectory();
    }
    assert.match($('record-directory-status').textContent,/当前没有可读/);
    assert.equal($('page-feedback').textContent,input.mode==='transient-retry'?'':nextMessage);
  }else if(input.mode.startsWith('late-')){
    let release,started;
    const firstStarted=new Promise(resolve=>started=resolve);
    let calls=0;
    context.entryFetch=()=>{calls++;if(calls===1){started();return new Promise(resolve=>release=resolve);}return Promise.resolve(response(200));};
    const old=context.loadRecordDirectory();await firstStarted;
    if(input.mode==='late-identity'){$('token').value='SYNTHETIC_CLIENT_FIXTURE_B';context.clearGeneric();}
    await context.loadRecordDirectory();
    const current=$('record-directory-status').textContent;
    assert.match(current,/当前没有可读/);
    release(response(403,true));await old;
    assert.equal($('record-directory-status').textContent,current);
    assert.equal($('result').textContent,'');
    assert.equal($('record-directory-read').disabled,false);
  }else{
    const status=Number(input.mode.slice(0,3));let calls=0;
    context.entryFetch=async()=>{calls++;return calls===1?response(status,input.mode.endsWith('html')):response(200);};
    await context.loadRecordDirectory();
    const message=$('record-directory-status').textContent;
    assert.match(message,status===403?/当前记录不可读或权限已撤回/:status===401?/会话已失效/:/记录暂时无法读取/);
    if(status===401||status===403)assert.equal($('page-feedback').textContent,message);
    assert.equal($('record-directory-read').disabled,false);
    assert.equal($('record-directory-items').children.length,0);
    assert.equal($('record-directory-next').hidden,true);
    await context.loadRecordDirectory();
    assert.match($('record-directory-status').textContent,/当前没有可读/);
    assert.equal($('page-feedback').textContent,'');
    assert.equal(calls,2);
  }
  process.stdout.write(JSON.stringify({mode:input.mode,result:'PASS',business_requests:0}));
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
"""


@pytest.mark.parametrize("mode", ["403-json", "403-html", "401-html", "502-html", "late-identity", "late-new-read",
                                  "other-feedback", "same-feedback", "during-read", "transient-retry", "late-success"])
def test_original_record_directory_error_feedback_and_explicit_retry(mode):
    page = (Path(__file__).resolve().parents[1] / "src/parkweave/web.html").read_text()
    start = page.index("let recordDirectoryGeneration=")
    end = page.index("\n// Owner Case worklist:", start)
    result = subprocess.run(["node", "-e", PROBE], input=json.dumps({"source": page[start:end], "mode": mode}),
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"mode": mode, "result": "PASS", "business_requests": 0}
