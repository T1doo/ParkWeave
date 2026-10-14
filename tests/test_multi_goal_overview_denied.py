"""Real PG/API denial between overview preflight and the original target GET."""
import json,os,subprocess,selectors
from pathlib import Path
import pytest
from test_template_consumer import template_consumption,headers,products
from test_manual_goal_privacy import private_case,A,B
from test_manual_goal_tasks import confirmed,act
from test_manual_goal_recheck import resource_state
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot

MODES=['manual_deny','manual_deny_late','manual_deny_late_newcase','manual_deny_late_identity','support_deny','support_deny_aux','support_deny_late','support_deny_aux_late','support_deny_fact','support_deny_fact_late','support_field_denied']

@pytest.mark.parametrize('mode',MODES)
def test_original_page_target_denial_clears_current_scope_only(template_consumption,mode):
    f=template_consumption;row=private_case(f);confirmed(f,row);act(f,row,'REQUEST',goal=A)
    baseline=products(f['owner']);resources=resource_state(f);grants=grant_snapshot(f['owner']);messages=[];summary=None;checkpoints=[];revoked=False;stderr=''
    target='/api/preparations/'+row['preparation_id']+('/fact-clarifications' if 'fact' in mode or mode=='support_field_denied' else '/readiness' if 'aux' in mode else '' if mode.startswith('support') else '/manual-goal-requests')
    proc=subprocess.Popen(['node','tests/multi_goal_overview_actual.js',row['preparation_id'],ENTERPRISES[0],A,B,mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
    try:
        while True:
            assert sel.select(timeout=15),'denied overview bridge timeout';line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if 'checkpoint' in msg:checkpoints.append(msg['checkpoint']);continue
            if 'restore' in msg or 'restore_and_new_case' in msg:
                with f['owner'].connect() as c:c.execute("UPDATE capability_grants SET active=true WHERE principal_id=%s AND capability='READ'",(ENTERPRISES[0],))
                reply={'actor':REVIEWERS[0]}
                if msg.get('restore_and_new_case'):
                    from test_template_consumer import consume,finish,resume,body
                    from test_template_consumer_planning import preview,adoption,post
                    data=body(f);data['required_goals']=['LOCAL_MATERIAL_PREPARATION',A,B]
                    new=consume(f,key='denial-new-case',data=data).json();finish(f);new=resume(f,new,key='denial-new-resume').json();v=preview(f,new).json();assert post(f,new,'adopt',{**adoption(v),'partial_adoption':True},'denial-new-adopt').status_code==200;confirmed(f,new);reply['preparation_id']=new['preparation_id'];assert reply['preparation_id']!=row['preparation_id'];baseline=products(f['owner']);resources=resource_state(f)
                grants=grant_snapshot(f['owner']);proc.stdin.write((json.dumps(reply)+'\n').encode());proc.stdin.flush();continue
            if 'result' in msg:summary=msg;break
            q=msg['request'];assert q['options'].get('method','GET')=='GET'
            if q['path']==target and not revoked:
                assert messages[-1]['path'].endswith('/goal-results') or mode.startswith('support_deny_aux') or mode.startswith('support_deny_fact') or mode=='support_field_denied'
                with f['owner'].connect() as c:c.execute("UPDATE "+('field_grants' if mode=='support_field_denied' else 'capability_grants')+" SET active=false WHERE principal_id=%s AND capability='READ'",(ENTERPRISES[0],))
                revoked=True;grants=grant_snapshot(f['owner'])
            r=f['client'].get(q['path'],headers={'Authorization':'Bearer '+f['tokens'][q['options']['headers']['Authorization'].removeprefix('Bearer SYNTHETIC_')]});assert r.status_code in (200,403),r.text
            assert products(f['owner'])==baseline and resource_state(f)==resources and grant_snapshot(f['owner'])==grants
            messages.append(dict(path=q['path'],status=r.status_code,authorization=q['options']['headers']['Authorization']));proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json()})+'\n').encode());proc.stdin.flush()
        code=proc.wait(timeout=15);stderr=proc.stderr.read().decode();assert code==0,stderr;assert summary and summary['posts']==0 and revoked
        assert any(m['path']==target and m['status']==403 for m in messages)
    finally:
        p=Path(os.environ.get('OVERVIEW_DENIED_EVIDENCE','.runtime/multi-goal-overview-denied-20261014/green'));p.mkdir(parents=True,exist_ok=True);(p/('page-'+mode+'-chain.json')).write_text(json.dumps(dict(summary=summary,requests=messages,checkpoints=checkpoints,stderr=stderr),indent=2)+'\n');sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
