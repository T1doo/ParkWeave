"""Read-only owner goal overview and exact same-Case goal navigation."""
import json,subprocess,selectors
from pathlib import Path
import pytest
from test_template_consumer import template_consumption,headers,products
from test_manual_goal_privacy import private_case,A,B
from test_manual_goal_tasks import confirmed,act
from test_manual_goal_recheck import resource_state
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot

def overview(f,row,user=ENTERPRISES[0]):
    return f['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers={'Authorization':'Bearer '+f['tokens'][user]})

def test_overview_keeps_supported_result_and_per_goal_human_responsibility_blocking_readonly(template_consumption):
    f=template_consumption;row=private_case(f);confirmed(f,row);act(f,row,'REQUEST');act(f,row,'TAKE',REVIEWERS[0]);act(f,row,'REQUEST_EVIDENCE',REVIEWERS[0]);before=products(f['owner'],True);grants=grant_snapshot(f['owner']);resources=resource_state(f)
    r=overview(f,row);assert r.status_code==200,r.text;x=r.json();items={i['goal']:i for i in x['results']}
    assert len(items)==3 and items['LOCAL_MATERIAL_PREPARATION']['state']=='AWAITING_OWNER_VERIFICATION'
    assert items[A]['human_request_state']=='WAITING_OWNER_EVIDENCE' and items[A]['human_responsible_actor_id']==ENTERPRISES[0]
    assert items[B]['human_request_state']=='NOT_REQUESTED' and items[B]['human_responsible_actor_id']==ENTERPRISES[0]
    assert all(i['result_sha256'] for i in items.values()) and items[A]['human_source_sha256'] and items[A]['human_revision']==3
    assert x['state']=='PARTIAL' and x['case_goal_completed'] is False
    assert products(f['owner'],True)==before and grant_snapshot(f['owner'])==grants and resource_state(f)==resources

@pytest.mark.parametrize('state',['REQUESTED','UNDER_MANUAL_REVIEW','WAITING_OWNER_ACKNOWLEDGEMENT','COORDINATION_ENDED','RECHECK_REQUESTED','UNDER_MANUAL_RECHECK'])
def test_overview_projects_current_human_states_without_task_or_goal_completion(template_consumption,state):
    from test_manual_goal_reply import reply_data,ack_data
    from test_manual_goal_recheck import request_data,take_data
    from test_manual_goal_requests import read,post
    f=template_consumption;row=private_case(f);confirmed(f,row);act(f,row,'REQUEST')
    if state!='REQUESTED':act(f,row,'TAKE',REVIEWERS[0])
    if state not in ('REQUESTED','UNDER_MANUAL_REVIEW'):assert post(f,row,reply_data(read(f,row).json()),user=REVIEWERS[0]).status_code==200
    if state in ('COORDINATION_ENDED','RECHECK_REQUESTED','UNDER_MANUAL_RECHECK'):assert post(f,row,ack_data(read(f,row).json())).status_code==200
    if state in ('RECHECK_REQUESTED','UNDER_MANUAL_RECHECK'):assert post(f,row,request_data(read(f,row).json())).status_code==200
    if state=='UNDER_MANUAL_RECHECK':assert post(f,row,take_data(read(f,row,user=REVIEWERS[0]).json()),user=REVIEWERS[0]).status_code==200
    before=products(f['owner'],True);x=overview(f,row).json();item=next(i for i in x['results'] if i['goal']==A)
    assert item['state']=='UNSUPPORTED' and item['human_request_state']==state and x['state']=='PARTIAL' and x['case_goal_completed'] is False
    if state in ('COORDINATION_ENDED','RECHECK_REQUESTED'):assert item['human_responsible_actor_id'] is None
    assert products(f['owner'],True)==before

@pytest.mark.parametrize('user',[REVIEWERS[0],ENTERPRISES[1]])
def test_overview_does_not_expand_owner_scope(template_consumption,user):
    f=template_consumption;row=private_case(f);before=products(f['owner']);r=overview(f,row,user);assert r.status_code==403 and A not in r.text and B not in r.text;assert products(f['owner'])==before

@pytest.mark.parametrize('obstacle',['cancel','write_revoked','integrity'])
def test_overview_readable_human_source_blockers_never_authorize_actions(template_consumption,obstacle):
    from test_manual_goal_reply import cancel
    f=template_consumption;row=private_case(f);confirmed(f,row);act(f,row,'REQUEST')
    if obstacle=='cancel':cancel(f,row)
    with f['owner'].connect() as c:
        if obstacle=='write_revoked':c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='EXECUTE'",(ENTERPRISES[0],))
        if obstacle=='integrity':c.execute("UPDATE preparation_evidence SET text='SYNTHETIC altered content' WHERE preparation_id=%s",(row['preparation_id'],))
    before=products(f['owner']);r=overview(f,row);assert r.status_code==200,r.text;item=next(i for i in r.json()['results'] if i['goal']==A)
    assert {'cancel':'CASE_CANCELLED','write_revoked':'CURRENT_WRITE_AUTHORITY_REQUIRED','integrity':'MATERIAL_REFERENCE_INTEGRITY_REQUIRED'}[obstacle] in item['human_blocked_reasons'];assert products(f['owner'])==before

@pytest.mark.parametrize('mode',['exact','supported','saved_button','source_switch','revoke','late_list','late_manual','late_aux','plan_switch','switch_goal','resource','late_resource','dispatch','localcase','receipt_blocked'])
def test_original_page_second_unsupported_goal_opens_exact_selected_goal(template_consumption,mode):
    f=template_consumption
    if mode in ('resource','late_resource','dispatch','localcase','receipt_blocked'):
        from test_template_consumer import body as intake_body
        from test_template_consumer_planning import ready,preview,adoption,post as adopt_post
        data=intake_body(f);data['required_goals']=['LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION','LOCAL_INTERNAL_ACCEPTANCE','LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT','LOCAL_CASE_RECORD_RECHECK',A,B] if mode in ('dispatch','localcase','receipt_blocked') else ['LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION',A,B];row=ready(f,data);v=preview(f,row).json();assert adopt_post(f,row,'adopt',{**adoption(v),'partial_adoption':True},'resource-overview-adopt').status_code==200
    else:row=private_case(f)
    confirmed(f,row);baseline=products(f['owner'],True);messages=[];summary=None
    proc=subprocess.Popen(['node','tests/multi_goal_overview_actual.js',row['preparation_id'],ENTERPRISES[0],A,B,mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
    try:
        while True:
            assert sel.select(timeout=15),'overview bridge timeout';line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if 'request' not in msg and 'result' not in msg:
                if msg.get('replace_plan'):
                    from test_manual_goal_privacy import replace_plan
                    replace_plan(f,row)
                elif msg.get('change_source'):
                    act(f,row,'REQUEST',goal=B)
                elif msg.get('revoke'):
                    with f['owner'].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='READ'",(ENTERPRISES[0],))
                else:raise AssertionError(msg)
                baseline=products(f['owner'],True);proc.stdin.write(b'{}\n');proc.stdin.flush();continue
            if 'request' not in msg:summary=msg;break
            q=msg['request'];assert q['options'].get('method','GET')=='GET';r=f['client'].get(q['path'],headers=headers(f));assert r.status_code in (200,403),r.text;assert products(f['owner'])=={k:v for k,v in baseline.items() if k!='authorization_audit'}
            messages.append(dict(path=q['path'],status=r.status_code));proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json()})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['posts']==0
    finally:
        p=Path('.runtime/multi-goal-overview-20261014');p.mkdir(exist_ok=True);(p/('page-'+mode+'-chain.json')).write_text(json.dumps(dict(summary=summary,requests=messages),indent=2)+'\n');sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
