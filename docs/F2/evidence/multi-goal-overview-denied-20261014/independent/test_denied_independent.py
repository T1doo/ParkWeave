from conftest import pg,fixture
from test_template_consumer import template_consumption,products,consume,finish,resume,body
from test_template_consumer_planning import preview,adoption,post as adopt
from test_manual_goal_privacy import private_case,A,B
from test_manual_goal_tasks import confirmed,act
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot
from pathlib import Path
import json,subprocess,selectors,pytest

@pytest.mark.parametrize('mode',['manual_mid','manual_late_identity','manual_late_newcase','fact_global','fact_field'])
def test_independent_original_page_current_denial_scope_and_stale_other_scope_preserved(template_consumption,mode):
 f=template_consumption;row=private_case(f);confirmed(f,row);act(f,row,'REQUEST',goal=A);before=products(f['owner']);audit_before=products(f['owner'],True)['authorization_audit'];grants=grant_snapshot(f['owner']);summary=None;messages=[];revoked=False
 target='/api/preparations/'+row['preparation_id']+('/fact-clarifications' if mode.startswith('fact') else '/manual-goal-requests')
 proc=subprocess.Popen(['node','.runtime/multi-goal-overview-denied-20261014/independent/denied_independent.js',row['preparation_id'],ENTERPRISES[0],B,mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
 try:
  while True:
   assert sel.select(timeout=15),'independent denial bridge timeout';line=proc.stdout.readline()
   if not line:break
   msg=json.loads(line)
   if msg.get('ind_restore'):
    with f['owner'].connect() as c:c.execute("UPDATE capability_grants SET active=true WHERE principal_id=%s AND capability='READ'",(ENTERPRISES[0],))
    response={'actor':REVIEWERS[0]}
    if msg['newcase']:
     d=body(f);d['required_goals']=['LOCAL_MATERIAL_PREPARATION',A,B];new=consume(f,key='ind-newcase',data=d).json();finish(f);new=resume(f,new,key='ind-resume').json();v=preview(f,new).json();assert adopt(f,new,'adopt',{**adoption(v),'partial_adoption':True},'ind-adopt').status_code==200;confirmed(f,new);response['pid']=new['preparation_id'];assert response['pid']!=row['preparation_id'];before=products(f['owner'])
    grants=grant_snapshot(f['owner']);proc.stdin.write((json.dumps(response)+'\n').encode());proc.stdin.flush();continue
   if 'request' not in msg:summary=msg;break
   q=msg['request'];assert q['options'].get('method','GET')=='GET'
   if q['path']==target and not revoked:
    with f['owner'].connect() as c:c.execute("UPDATE "+('field_grants' if mode=='fact_field' else 'capability_grants')+" SET active=false WHERE principal_id=%s AND capability='READ'",(ENTERPRISES[0],))
    revoked=True;grants=grant_snapshot(f['owner'])
   user=q['options']['headers']['Authorization'].removeprefix('Bearer SYNTHETIC_');r=f['client'].get(q['path'],headers={'Authorization':'Bearer '+f['tokens'][user]});assert r.status_code in (200,403),r.text
   assert products(f['owner'])==before and grant_snapshot(f['owner'])==grants
   if user==REVIEWERS[0]:assert B not in r.text
   messages.append({'path':q['path'],'actor':user,'status':r.status_code});proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json()})+'\n').encode());proc.stdin.flush()
  assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['posts']==0 and revoked;assert any(m['path']==target and m['status']==403 for m in messages)
  audit=products(f['owner'],True)['authorization_audit'];new_audit=[a for a in audit if a not in audit_before];assert len(new_audit)==sum(m['status']==403 for m in messages) and all(a['outcome']=='DENIED' and a['principal_id']==ENTERPRISES[0] for a in new_audit)
  if mode.startswith('fact'):
   scope='/api/preparations/'+row['preparation_id']
   target_index=next(i for i,m in enumerate(messages) if m['path']==target);check=messages[target_index+1];assert check['path']==scope and check['status']==(200 if mode=='fact_field' else 403)
 finally:
  Path('.runtime/multi-goal-overview-denied-20261014/independent/'+mode+'-chain.json').write_text(json.dumps({'summary':summary,'requests':messages,'business_and_grant_snapshots_unchanged_except_explicit_fixture_setup':True},indent=2)+'\n');sel.close()
  if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
