"""Explicit Linux Chromium/local SYNTHETIC R3 flow. No automatic installs."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import time
from parkweave.process_env import minimal_environment

root=Path.cwd();parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
env=minimal_environment(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
candidates=[p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text()).get('version')=='0.38.2']
if not candidates:raise RuntimeError('approved cached agent-browser0.38.2 required; no install')
command=['node',str(sorted(candidates)[0].parent/'bin/agent-browser.js'),'--session','parkweave-r3','--executable-path','/usr/bin/chromium','--args','--no-sandbox']
def browser(*items,stdin=None):
    p=subprocess.run(command+list(items),input=stdin,capture_output=True,text=True,env=env,timeout=30)
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout.strip()
def value(expression):
    result=json.loads(browser('eval','(async()=>JSON.stringify(await ('+expression+')))()'))
    return json.loads(result) if isinstance(result,str) else result
def ready(run):
    for _ in range(30):
        state=value("(async()=>{const r=await fetch('/api/runs/'+"+json.dumps(run)+",{headers:{Authorization:'Bearer '+document.querySelector('#token').value}});return (await r.json()).state;})()")
        if state=='SUCCEEDED':return
        time.sleep(.1)
    raise AssertionError('candidate worker not completed')
try:
    browser('open','http://127.0.0.1:8765');browser('snapshot','-i')
    token=json.loads((root/'.runtime/synthetic-sessions.json').read_text())['fixture-a']
    browser('eval','--stdin',stdin="document.querySelector('#token').value="+json.dumps(token)+";undefined")
    browser('fill','#candidate-region','SYNTHETIC 地区');browser('find','role','button','click','--name','评审三项候选');browser('snapshot','-i')
    parent=value("document.querySelector('#run').value");assert len(parent)==36;ready(parent)
    browser('click','#review');browser('snapshot','-i');browser('wait','#answer-employees')
    before=value('currentReview');assert [q['field'] for q in before['document']['necessary_questions']]==['region','employees','service_need']
    assert [r['reason'] for r in before['document']['results']][1:]==['MISSING','MISSING']
    browser('fill','#answer-employees','15');browser('fill','#answer-version','2');browser('find','role','button','click','--name','提交补充自述');browser('snapshot','-i')
    child=value("document.querySelector('#run').value");assert child!=parent;ready(child)
    browser('click','#review');browser('snapshot','-i');browser('wait','#answer-employees')
    after=value('currentReview');assert after['document']['results'][1]['reason']=='UNVERIFIED'
    assert all(r['state']=='UNKNOWN' for r in after['document']['results'])
    browser('click','#cancel-clarification');browser('snapshot','-i');cancel=value("JSON.parse(document.querySelector('#result').textContent)")
    assert cancel['decision']=='CANCEL' and cancel['run_id'] is None
    # Re-read historical snapshot through authorized API; never infer from stale UI.
    original=value("(async()=>{const r=await fetch('/api/runs/'+"+json.dumps(parent)+"+'/fact-review',{headers:{Authorization:'Bearer '+document.querySelector('#token').value}});return await r.json();})()")
    assert original['document']==before['document'] and original['sha256']==before['sha256']
    narrow=[]
    for width in (320,390):
        browser('set','viewport',str(width),'844');browser('snapshot','-i')
        metric=value('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert metric['scroll']<=metric['width'];narrow.append(metric)
    errors=browser('errors');assert not errors,errors
    report={'status':'PARTIAL_SYNTHETIC_ENGINEERING_PASS','environment':'Linux Chromium/local API/independent worker/PG only','provider_requests':0,'real_budget':0,'whole_AT_EX':'NOT_RUN','native_windows':'NOT_RUN','parent_run':parent,'child_run':child,'parent_sha256':before['sha256'],'child_sha256':after['sha256'],'grouped_fields':['region','employees','service_need'],'answer_kept_unknown':True,'cancel_only_followup':True,'history_unchanged':True,'narrow_viewports':narrow,'browser_errors':0}
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
finally:browser('close')
