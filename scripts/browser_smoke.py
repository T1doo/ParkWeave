"""Linux local fixture UI verification using agent-browser, not Windows acceptance."""
from pathlib import Path
import json
import os
import subprocess
import time
import argparse

root=Path.cwd()
env=dict(os.environ,npm_config_cache=str(root/'.cache/npm'),XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
cmd=['npx','--yes','--package=agent-browser','agent-browser','--executable-path','/usr/bin/chromium','--args','--no-sandbox']

def browser(*args,stdin=None):
    result=subprocess.run(cmd+list(args),input=stdin,text=True,capture_output=True,env=env,timeout=30)
    if result.returncode:raise RuntimeError(result.stderr)
    return result.stdout.strip()

parser=argparse.ArgumentParser()
parser.add_argument('--report', type=Path, default=root/'docs/F1/evidence/browser-smoke.json')
args=parser.parse_args()
report={}
try:
    report['open']=browser('open','http://127.0.0.1:8765')
    report['snapshot']=browser('snapshot','-i')
    assert '创建本地办理记录' in report['snapshot'],report['snapshot']
    tokens=json.loads((root/'.runtime/synthetic-sessions.json').read_text())
    # Pass synthetic token through stdin; never expose it in captured commands/evidence.
    browser('eval','--stdin',stdin="document.querySelector('#token').value="+json.dumps(tokens['fixture-a']))
    browser('fill','#goal','合成：需要咨询空间与服务准备；此增量只建单')
    browser('click','#intake button')
    for _ in range(20):
        run=browser('eval',"document.querySelector('#run').value")
        if len(run.strip('"'))==36:break
        time.sleep(.1)
    browser('click','[data-tab=collaboration]')
    browser('snapshot','-i')
    browser('wait','#refresh')
    browser('find','role','button','click','--name','查看持久状态')
    for _ in range(5):
        result=browser('get','text','#result')
        if 'SUCCEEDED' in result:break
        time.sleep(.1);browser('find','role','button','click','--name','查看持久状态')
    assert 'NEEDS_INPUT' in result and 'LOCAL_CASE_CREATED' in result,(result,browser('errors'),browser('snapshot','-i'))
    report['business_record']=json.loads(result)
    browser('click','[data-tab=resource]')
    browser('snapshot','-i')
    report['resource']=browser('get','text','#resource')
    assert '尚未启用' in report['resource']
    report['overlay']=browser('eval',"document.querySelector('[data-nextjs-dialog], .vite-error-overlay') ? 'ERROR' : 'OK'")
    report['errors']=browser('errors')
    assert not report['errors'],report['errors']
    browser('screenshot',str(root/'.runtime/page.png'))
    report['status']='PASS';report['environment']='Linux Chromium only';report['windows']='BLOCKED'
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
finally:
    browser('close')
