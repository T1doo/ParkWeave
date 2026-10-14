from conftest import pg,fixture
from test_template_consumer import template_consumption,products
from test_manual_goal_privacy import private_case,A,B
from test_manual_goal_tasks import confirmed,act
from test_manual_goal_requests import read
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot
from parkweave import controlled_plans as cp
from pathlib import Path
import json,subprocess,selectors,pytest

def overview(f,row,user=ENTERPRISES[0]):return f['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers={'Authorization':'Bearer '+f['tokens'][user]})

def test_per_goal_projection_digest_and_readonly_scope(template_consumption):
 f=template_consumption;row=private_case(f);confirmed(f,row);act(f,row,'REQUEST');act(f,row,'TAKE',REVIEWERS[0]);act(f,row,'REQUEST_EVIDENCE',REVIEWERS[0]);before=products(f['owner'],True);g=grant_snapshot(f['owner']);r=overview(f,row);assert r.status_code==200,r.text;x=r.json();manual={i['goal']:i for i in read(f,row).json()['items']}
 assert x['state']=='PARTIAL' and x['case_goal_completed'] is False and len(x['results'])==3
 for item in x['results']:
  digest=item['result_sha256'];assert cp._hash({k:v for k,v in item.items() if k!='result_sha256'})==digest
  if item['goal'] in (A,B):
   m=manual[item['goal']];assert item['state']=='UNSUPPORTED';assert item['human_request_state']==m['state'] and item['human_responsible_actor_id']==m['responsible_actor_id'] and item['human_responsibility']==m['responsibility'] and item['human_blocked_reasons']==m['blocked_reasons']
 assert products(f['owner'],True)==before and grant_snapshot(f['owner'])==g

@pytest.mark.parametrize('actor',[REVIEWERS[0],ENTERPRISES[1]])
def test_overview_does_not_expand_owner_scope(template_consumption,actor):
 f=template_consumption;row=private_case(f);before=products(f['owner']);r=overview(f,row,actor);assert r.status_code==403 and A not in r.text and B not in r.text;assert products(f['owner'])==before

@pytest.mark.parametrize('mode',['exact','manual_late','auxiliary_late'])
def test_full_original_page_exact_goal_and_late_sources_keep_new_panels(template_consumption,mode):
 f=template_consumption;row=private_case(f);confirmed(f,row);before=products(f['owner'],True);g=grant_snapshot(f['owner']);messages=[];summary=None
 proc=subprocess.Popen(['node','.runtime/multi-goal-overview-20261014/independent/overview_independent.js',row['preparation_id'],ENTERPRISES[0],B,mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
 try:
  while True:
   assert sel.select(timeout=15),'independent overview timeout';line=proc.stdout.readline()
   if not line:break
   msg=json.loads(line)
   if 'request' not in msg:summary=msg;break
   q=msg['request'];assert q['options'].get('method','GET')=='GET';r=f['client'].get(q['path'],headers={'Authorization':'Bearer '+f['tokens'][ENTERPRISES[0]]});assert r.status_code==200,r.text;assert products(f['owner'],True)==before and grant_snapshot(f['owner'])==g
   messages.append({'path':q['path'],'status':r.status_code});proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json()})+'\n').encode());proc.stdin.flush()
  assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['posts']==0
 finally:
  Path('.runtime/multi-goal-overview-20261014/independent/'+mode+'-chain.json').write_text(json.dumps({'summary':summary,'requests':messages},indent=2)+'\n');sel.close()
  if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
