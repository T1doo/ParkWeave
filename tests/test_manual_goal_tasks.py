"""Original personal queue for current-plan, legally shared human work."""
from uuid import uuid4
import pytest
from test_template_consumer import template_consumption,headers,products,body as intake_body,consume,finish,resume
from test_template_consumer_planning import preview,adoption,post as adopt_post
from test_manual_goal_requests import read,post,body
from test_manual_goal_privacy import private_case,replace_plan,A,B
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot

def tasks(f,user=ENTERPRISES[0],**query):
    return f['client'].get('/api/preparation-tasks',headers={'Authorization':'Bearer '+f['tokens'][user]},params=query)

def manual_items(r):
    assert r.status_code==200,r.text;return [x for x in r.json()['items'] if x['kind'].startswith('MANUAL_')]

def act(f,row,action,user=ENTERPRISES[0],goal=A):
    v=read(f,row,user=user).json();r=post(f,row,{**body(v,action),'goal':goal},user=user);assert r.status_code==200,r.text;return r.json()

def confirmed(f,row):
    path='/api/preparations/'+row['preparation_id']
    for action,user in [('REVIEW',REVIEWERS[0]),('CONFIRM',ENTERPRISES[0])]:
        rev=f['client'].get(path,headers=headers(f)).json()['preparation']['revision']
        r=f['client'].post(path+'/commands',headers={'Authorization':'Bearer '+f['tokens'][user],'Idempotency-Key':uuid4().hex},json=dict(action=action,expected_revision=rev,reason='SYNTHETIC explicit original '+action));assert r.status_code==200,r.text
    return r.json()

def test_confirmed_case_manual_responsibility_and_shared_privacy_without_any_read_write(template_consumption):
    f=template_consumption;row=private_case(f);confirmed(f,row);before=products(f['owner']);grants=grant_snapshot(f['owner'])
    assert manual_items(tasks(f,REVIEWERS[0]))==[] and A not in tasks(f,REVIEWERS[0]).text and B not in tasks(f,REVIEWERS[0]).text
    assert products(f['owner'])==before
    act(f,row,'REQUEST');before=products(f['owner']);items=manual_items(tasks(f,REVIEWERS[0]));assert len(items)==1 and items[0]['kind']=='MANUAL_ACCEPT_REQUEST' and items[0]['manual_goal']==A
    assert B not in tasks(f,REVIEWERS[0]).text and manual_items(tasks(f))==[];assert products(f['owner'])==before
    assert items[0]['state']=='LOCAL_CONFIRMED' and items[0]['case_id']==row['case_id'] and items[0]['run_id']==row['run_id'] and items[0]['plan_id']==read(f,row).json()['plan_id']
    act(f,row,'TAKE',REVIEWERS[0]);assert manual_items(tasks(f,REVIEWERS[0]))[0]['kind']=='MANUAL_REVIEW_REQUEST'
    act(f,row,'REQUEST_EVIDENCE',REVIEWERS[0]);before=products(f['owner']);items=manual_items(tasks(f));assert len(items)==1 and items[0]['kind']=='MANUAL_SUPPLY_EVIDENCE' and items[0]['manual_state']=='WAITING_OWNER_EVIDENCE';assert manual_items(tasks(f,REVIEWERS[0]))==[]
    assert items[0]['overall_goal_state']=='PARTIAL' and items[0]['goal_state']=='UNSUPPORTED' and items[0]['case_goal_completed'] is False and items[0]['requires_current_read'] is True
    assert products(f['owner'])==before and grant_snapshot(f['owner'])==grants

def test_withdrawn_and_previous_plan_requests_are_not_current_manual_work(template_consumption):
    f=template_consumption;row=private_case(f);act(f,row,'REQUEST');act(f,row,'WITHDRAW');before=products(f['owner']);assert manual_items(tasks(f,REVIEWERS[0]))==[] and manual_items(tasks(f))==[];assert products(f['owner'])==before
    # Withdrawn history is still legally shared, but a new actual plan has no work.
    replace_plan(f,row);before=products(f['owner']);assert manual_items(tasks(f,REVIEWERS[0]))==[];assert A not in tasks(f,REVIEWERS[0]).text and B not in tasks(f,REVIEWERS[0]).text;assert products(f['owner'])==before
    act(f,row,'REQUEST',goal=B);items=manual_items(tasks(f,REVIEWERS[0]));assert [x['manual_goal'] for x in items]==[B] and A not in tasks(f,REVIEWERS[0]).text

def test_queue_transaction_enforces_readonly_at_authorization_and_projection(template_consumption,monkeypatch):
    from parkweave import manual_goal_requests as human
    f=template_consumption;row=private_case(f);act(f,row,'REQUEST');seen=[]
    auth=f['store'].auth;view=human.view
    def observed_auth(c,*args,**kwargs):
        seen.append(('auth',c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']))
        return auth(c,*args,**kwargs)
    def observed_view(store,c,*args,**kwargs):
        seen.append(('view',c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']))
        return view(store,c,*args,**kwargs)
    monkeypatch.setattr(f['store'],'auth',observed_auth);monkeypatch.setattr(human,'view',observed_view)
    before=products(f['owner'],True);assert manual_items(tasks(f,REVIEWERS[0]))
    assert seen==[('auth','on'),('view','on')] and products(f['owner'],True)==before

@pytest.mark.parametrize('authority',['READ','REVIEW_ASSIGNED'])
def test_queue_rechecks_specialist_permission_and_scopes_subject(template_consumption,authority):
    f=template_consumption;row=private_case(f);act(f,row,'REQUEST');assert manual_items(tasks(f,REVIEWERS[0]));assert manual_items(tasks(f,REVIEWERS[1]))==[] and A not in tasks(f,REVIEWERS[1]).text
    table='capability_grants' if authority=='READ' else 'preparation_grants'
    with f['owner'].connect() as c:c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',(REVIEWERS[0],authority))
    before=products(f['owner']);r=tasks(f,REVIEWERS[0]);assert r.status_code==403 and A not in r.text and B not in r.text;assert products(f['owner'])==before

@pytest.mark.parametrize('obstacle',['cancelled','reconciling','closed','request_changed','write_revoked'])
def test_current_manual_work_keeps_explicit_blocked_reason(template_consumption,obstacle):
    f=template_consumption;row=private_case(f);act(f,row,'REQUEST');act(f,row,'TAKE',REVIEWERS[0]);act(f,row,'REQUEST_EVIDENCE',REVIEWERS[0])
    with f['owner'].connect() as c:
        if obstacle in ('cancelled','reconciling'):c.execute('UPDATE cases SET state=%s WHERE id=%s',(obstacle.upper(),row['case_id']))
        if obstacle=='closed':c.execute("INSERT INTO case_local_lifecycles(preparation_id,case_id,revision,cycle,state,verified_snapshot,verified_sha256) VALUES(%s,%s,1,1,'LOCAL_RECORD_CLOSED','{}',%s)",(row['preparation_id'],row['case_id'],'0'*64))
        if obstacle=='write_revoked':c.execute("UPDATE action_grants SET active=false WHERE principal_id=%s AND action='case.create'",(ENTERPRISES[0],))
    if obstacle=='request_changed':
        path='/api/preparations/'+row['preparation_id'];rev=f['client'].get(path,headers=headers(f)).json()['preparation']['revision'];r=f['client'].post(path+'/request-intent',headers=headers(f,key='changed-intent'),json=dict(expected_preparation_revision=rev,request_text='SYNTHETIC new explicit request retaining all goals',required_goals=['LOCAL_MATERIAL_PREPARATION',A,B]));assert r.status_code==200,r.text
    before=products(f['owner']);items=manual_items(tasks(f));assert len(items)==1 and items[0]['blocked_reason'] and items[0]['blocked_reasons'];assert items[0]['overall_goal_state']=='PARTIAL' and items[0]['goal_state']=='UNSUPPORTED';assert products(f['owner'])==before

def test_cursor_pages_include_confirmed_work_without_duplicates_or_foreign_cursor(template_consumption):
    f=template_consumption;rows=[]
    for i in range(4):
        data=intake_body(f);data['goal']='SYNTHETIC private fresh queue '+str(i);data['required_goals']=['LOCAL_MATERIAL_PREPARATION',A,B]
        row=consume(f,key='queue-create-'+str(i),data=data).json();finish(f);row=resume(f,row,key='queue-resume-'+str(i)).json();v=preview(f,row).json();assert adopt_post(f,row,'adopt',{**adoption(v),'partial_adoption':True},'queue-adopt-'+str(i)).status_code==200
        confirmed(f,row);act(f,row,'REQUEST');rows.append(row)
    before=products(f['owner']);first=tasks(f,REVIEWERS[0],limit=2);second=tasks(f,REVIEWERS[0],limit=2,before=first.json()['next_before']);items=manual_items(first)+manual_items(second)
    assert len(items)==4 and len({x['id'] for x in items})==4 and first.json()['has_older_records'] is True and second.json()['next_before'] is None
    assert first.json()['check_limit']==2 and first.json()['checked_count']==2 and first.json()['read_only'] is True
    assert B not in first.text+second.text and products(f['owner'])==before
    assert tasks(f,REVIEWERS[1],before=rows[0]['preparation_id']).status_code==403

@pytest.mark.parametrize('query',[{'limit':0},{'limit':101},{'before':'bad'}])
def test_task_page_bounds(template_consumption,query):assert tasks(template_consumption,**query).status_code==422

def test_original_page_cold_confirmed_manual_tasks_stale_subject_permission_and_pages(template_consumption):
    import json,subprocess,selectors
    from pathlib import Path
    from uuid import UUID
    f=template_consumption;row=private_case(f);confirmed(f,row);act(f,row,'REQUEST');messages=[];bridges=[];summary=None;page_snapshot=products(f['owner']);expected_case=row['case_id'];grants=grant_snapshot(f['owner'])
    proc=subprocess.Popen(['node','tests/manual_goal_tasks_actual.js',ENTERPRISES[0],REVIEWERS[0],A,B],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
    try:
        while True:
            assert sel.select(timeout=15),'task page bridge timeout';line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if 'request' not in msg and 'result' not in msg:
                if msg.get('replace_current_plan'):replace_plan(f,row)
                elif msg.get('create_beta_request'):act(f,row,'REQUEST',goal=B)
                elif msg.get('revoke_specialist_list'):
                    assert grant_snapshot(f['owner'])==grants
                    with f['owner'].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='READ'",(REVIEWERS[0],))
                elif msg.get('scale_owner_pages'):
                    # Deliberately restore only the test prerequisite already used, not an app permission repair.
                    with f['owner'].connect() as c:c.execute("UPDATE capability_grants SET active=true WHERE principal_id=%s AND capability='READ'",(REVIEWERS[0],))
                    act(f,row,'TAKE',REVIEWERS[0],goal=B);act(f,row,'REQUEST_EVIDENCE',REVIEWERS[0],goal=B)
                    with f['owner'].connect() as c:
                        for _ in range(100):
                            run,case,id=uuid4(),uuid4(),uuid4()
                            c.execute("INSERT INTO runs(id,principal_id,park_id,org_id,namespace,request_key,fingerprint,input,state) SELECT %s,principal_id,park_id,org_id,namespace,%s,fingerprint,input,state FROM runs WHERE id=%s",(run,uuid4().hex,UUID(row['run_id'])))
                            c.execute('INSERT INTO cases SELECT %s,%s,park_id,org_id,goal,state,source,external_acceptance,offline_fulfillment FROM cases WHERE id=%s',(case,run,UUID(row['case_id'])))
                            c.execute("INSERT INTO preparations(id,run_id,case_id,owner_id,reviewer_id,park_id,org_id,service_id,service_version,namespace,goal,state) SELECT %s,%s,%s,owner_id,reviewer_id,park_id,org_id,service_id,service_version,namespace,goal,'IN_PREPARATION' FROM preparations WHERE id=%s",(id,run,case,UUID(row['preparation_id'])))
                else:raise AssertionError(msg)
                bridges.append(msg);page_snapshot=products(f['owner']);proc.stdin.write(b'{}\n');proc.stdin.flush();continue
            if 'request' not in msg:summary=msg;break
            q=msg['request'];o=q['options'];method=o.get('method','GET');data=json.loads(o['body']) if o.get('body') else None;actor=o['headers']['Authorization'].removeprefix('Bearer SYNTHETIC_');h={'Authorization':'Bearer '+f['tokens'][actor]}
            if key:=o['headers'].get('Idempotency-Key'):h['Idempotency-Key']=key
            r=f['client'].request(method,q['path'],headers=h,json=data);messages.append(dict(method=method,path=q['path'],actor=actor,status=r.status_code,action=data.get('action') if data else None))
            assert r.status_code in (200,403),r.text
            if method=='GET':assert products(f['owner'])==page_snapshot,'queue or entry GET changed business records'
            else:page_snapshot=products(f['owner'])
            if q['path'].startswith('/api/preparation-tasks') and actor==REVIEWERS[0] and not any(x.get('create_beta_request') for x in bridges):assert B not in r.text
            if q['path'].startswith('/api/preparations/') and method=='POST':assert q['path'].split('/')[3]==row['preparation_id'] and r.json()['case_id']==expected_case
            proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json()})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['checks']>=30 and summary['posts']==3;assert products(f['owner'])==page_snapshot
        assert grant_snapshot(f['owner'])==grants
    finally:
        Path('.runtime/manual-goal-tasks-20261014/actual-chain.json').write_text(json.dumps({'summary':summary,'requests':messages,'explicit_test_bridges':bridges,'scale_setup_clones_for_read_bound_only':100},indent=2)+'\n');sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
