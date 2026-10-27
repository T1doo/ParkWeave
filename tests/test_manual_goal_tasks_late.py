"""Real original page late reads, with owned PG and actual API plan replacement."""
import json,subprocess,selectors
from pathlib import Path
from uuid import uuid4
import pytest
from test_template_consumer import template_consumption,products
from test_manual_goal_privacy import private_case,replace_plan,A
from test_manual_goal_tasks import confirmed,act
from template_candidate_support import REVIEWERS,grant_snapshot

@pytest.mark.parametrize('mode',['refresh','page','replace_refresh','replace_live'])
def test_late_manual_task_read_cannot_render_or_replace_new_draft(template_consumption,mode):
    f=template_consumption;row=private_case(f);confirmed(f,row);act(f,row,'REQUEST')
    if mode=='page':
        with f['owner'].connect() as c:
            for _ in range(100):
                run,case,id=uuid4(),uuid4(),uuid4()
                c.execute("INSERT INTO runs(id,principal_id,park_id,org_id,namespace,request_key,fingerprint,input,state) SELECT %s,principal_id,park_id,org_id,namespace,%s,fingerprint,input,state FROM runs WHERE id=%s",(run,uuid4().hex,row['run_id']))
                c.execute('INSERT INTO cases SELECT %s,%s,park_id,org_id,goal,state,source,external_acceptance,offline_fulfillment FROM cases WHERE id=%s',(case,run,row['case_id']))
                c.execute("INSERT INTO preparations(id,run_id,case_id,owner_id,reviewer_id,park_id,org_id,service_id,service_version,namespace,goal,state,created_at) SELECT %s,%s,%s,owner_id,reviewer_id,park_id,org_id,service_id,service_version,namespace,goal,'IN_PREPARATION',created_at-interval '1 hour' FROM preparations WHERE id=%s",(id,run,case,row['preparation_id']))
    before=products(f['owner'],True);grants=grant_snapshot(f['owner']);messages=[];summary=None
    proc=subprocess.Popen(['node','tests/manual_goal_tasks_late_actual.js',REVIEWERS[0],A,mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
    try:
        while True:
            assert sel.select(timeout=15),'late page bridge timed out'
            line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if msg.get('replace_plan'):
                replace_plan(f,row);before=products(f['owner'],True);proc.stdin.write(b'{}\n');proc.stdin.flush();continue
            if 'request' not in msg:summary=msg;break
            q=msg['request'];o=q['options'];assert o.get('method','GET')=='GET'
            if mode=='replace_live' and q['path'].endswith('/manual-goal-requests'):
                replace_plan(f,row);before=products(f['owner'],True)
            r=f['client'].get(q['path'],headers={'Authorization':'Bearer '+f['tokens'][REVIEWERS[0]]});assert r.status_code==200,r.text
            assert products(f['owner'],True)==before and grant_snapshot(f['owner'])==grants
            messages.append(dict(path=q['path'],status=r.status_code))
            proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json()})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['posts']==0
    finally:
        out=Path('.runtime/manual-goal-task-late-20261014');out.mkdir(exist_ok=True);(out/(mode+'-chain.json')).write_text(json.dumps(dict(summary=summary,requests=messages),indent=2)+'\n');sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
