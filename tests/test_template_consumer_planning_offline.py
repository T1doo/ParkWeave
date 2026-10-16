"""Original template HTML handlers, owned PG/ASGI; no browser or model."""
import json,selectors,subprocess,os
from pathlib import Path
from test_template_consumer import template_consumption,headers,finish
from template_candidate_support import ENTERPRISES,grant_snapshot


def test_template_consumer_current_constraints_preview_confirmation_and_return_edit(template_consumption):
    f=template_consumption;before=grant_snapshot(f['owner']);proc=subprocess.Popen(['node','tests/template_consumer_planning.js','template_consumer_planning',ENTERPRISES[0]],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ);requests=[];summary=None
    try:
        while True:
            assert sel.select(timeout=15),'original template planning bridge timeout';line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if 'advance_source' in msg:
                v=msg['advance_source'];path='/api/preparations/'+v['preparation_id']+'/commands';data={'action':'ADD_EVIDENCE','expected_revision':v['revision'],'slot':'need_summary','text':'SYNTHETIC peer current material version','source_kind':'USER_STATEMENT','source_label':'SYNTHETIC original peer API'};r=f['client'].post(path,headers=headers(f,key='original-peer-material'),json=data);requests.append({'method':'POST','path':path,'status':r.status_code,'entry':'ORIGINAL_PEER_API'});assert r.status_code==200,r.text;proc.stdin.write(b'{"advanced":true}\n');proc.stdin.flush();continue
            if 'request' not in msg:summary=msg;break
            q=msg['request'];o=q['options'];method=o.get('method','GET');body=json.loads(o['body']) if o.get('body') else None;h=headers(f,key=o.get('headers',{}).get('Idempotency-Key'));r=f['client'].request(method,q['path'],headers=h,json=body);requests.append({'method':method,'path':q['path'],'status':r.status_code,'entry':'ORIGINAL_HTML'});assert r.status_code<400,(method,q['path'],r.status_code,r.json())
            if method=='POST' and q['path']=='/api/template-consumer/instances':finish(f)
            proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json()})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['checks']>=25;assert grant_snapshot(f['owner'])==before
        rows=f['consumer'].instances(f['tokens'][ENTERPRISES[0]])['items'];assert len(rows)==3 and sum(x['state']=='PLAN_ADOPTED' for x in rows)==2;assert next(x for x in rows if x['instance_id']==summary['third'])['plan_id'] is None
        r=(Path(os.environ.get('RELEASE_REGRESSION_ARTIFACT_ROOT','.runtime'))/'template-consumer-planning-20261013');r.mkdir(parents=True,exist_ok=True);(r/'actual-chain.json').write_text(json.dumps({'summary':summary,'requests':requests,'permission_snapshot_unchanged':True,'lost_responses':0},indent=2)+'\n')
    finally:
        r=(Path(os.environ.get('RELEASE_REGRESSION_ARTIFACT_ROOT','.runtime'))/'template-consumer-planning-20261013');r.mkdir(parents=True,exist_ok=True);(r/'latest-partial-chain.json').write_text(json.dumps({'summary':summary,'requests':requests},indent=2)+'\n')
        sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)


import pytest

@pytest.mark.parametrize('mode',['late_preview403','late_confirm_edit','nested_case','nested_sha','nested_goals','current_empty403','pending_controls'])
def test_original_template_planning_guard_context_and_pending(mode):
    r=subprocess.run(['node','tests/template_consumer_planning_guards.js',mode],capture_output=True,text=True,timeout=15)
    assert r.returncode==0,r.stdout+r.stderr
    v=json.loads(r.stdout);assert v['result']=='PASS' and v['checks']>=5
