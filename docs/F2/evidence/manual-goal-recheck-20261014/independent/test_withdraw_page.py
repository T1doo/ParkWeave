from conftest import pg,fixture
from test_template_consumer import template_consumption,products
from test_manual_goal_reply import replied
from test_manual_goal_requests import read,post
from test_recheck_independent import request
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot
from test_manual_goal_privacy import B
from copy import deepcopy
from uuid import uuid4
from pathlib import Path
import subprocess,selectors,json

def test_full_original_page_explicit_human_withdrawal_cold_original_request_recovery(template_consumption):
 f=template_consumption;row,_=replied(f);key=str(uuid4());assert post(f,row,request(read(f,row).json()),key).status_code==200
 before=deepcopy(products(f['owner']));baseline=products(f['owner'],True);grants=grant_snapshot(f['owner']);messages=[];summary=None
 proc=subprocess.Popen(['node','.runtime/manual-goal-recheck-20261014/independent/withdraw_actual.js',REVIEWERS[0],ENTERPRISES[0],row['preparation_id'],key],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
 try:
  while True:
   assert sel.select(timeout=15),'independent withdrawal page timeout';line=proc.stdout.readline()
   if not line:break
   msg=json.loads(line)
   if 'request' not in msg:summary=msg;break
   q=msg['request'];o=q['options'];method=o.get('method','GET');data=json.loads(o['body']) if o.get('body') else None;actor=o['headers']['Authorization'].removeprefix('Bearer SYNTHETIC_');h={'Authorization':'Bearer '+f['tokens'][actor]}
   if k:=o['headers'].get('Idempotency-Key'):h['Idempotency-Key']=k
   if method=='POST':assert data['action']=='WITHDRAW'
   r=f['client'].request(method,q['path'],headers=h,json=data);assert r.status_code==200,r.text
   if actor==REVIEWERS[0]:assert B not in r.text
   if method=='GET':assert products(f['owner'],True)==baseline
   else:baseline=products(f['owner'],True)
   assert grant_snapshot(f['owner'])==grants;messages.append({'method':method,'path':q['path'],'actor':actor,'status':r.status_code,'action':data['action'] if data else None});proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json()})+'\n').encode());proc.stdin.flush()
  assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['result']=='PASS' and summary['posts']==1
  after=deepcopy(products(f['owner']))
  for snapshot in (before,after):
   for p in snapshot['preparations']:p['service_case_plan'].pop('manual_goal_requests',None)
  assert before==after
 finally:
  Path('.runtime/manual-goal-recheck-20261014/independent/withdraw-page-chain.json').write_text(json.dumps({'summary':summary,'requests':messages},indent=2)+'\n');sel.close()
  if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
