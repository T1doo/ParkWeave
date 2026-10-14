"""Explicit same-reply recheck application and separate original specialist take."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from test_template_consumer import template_consumption,products
from test_manual_goal_reply import replied,ack_data,reply_data,command,cancel,at_revision_29
from test_manual_goal_requests import read,post
from test_manual_goal_tasks import tasks,manual_items
from test_manual_goal_privacy import replace_plan,A,B
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot

def resource_state(f):
    tables=('synthetic_resources','synthetic_resource_grants','synthetic_resource_holds','synthetic_resource_receipts','synthetic_resource_combinations','synthetic_resource_combination_members','synthetic_resource_combination_receipts','resource_case_claims','case_resource_links')
    with f['owner'].connect() as c:return {t:c.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall() for t in tables}

def request_data(v):
    reply=next(i for i in v['items'] if i['goal']==A)['reply']
    return command(v,'REQUEST_RECHECK',reply_event_id=reply['id'],reply_fingerprint=reply['fingerprint'])

def take_data(v):
    item=next(i for i in v['items'] if i['goal']==A);reply=item['reply'];req=item['recheck']
    return command(v,'TAKE_RECHECK',reply_event_id=reply['id'],reply_fingerprint=reply['fingerprint'],recheck_event_id=req['id'],recheck_fingerprint=req['fingerprint'])

def applied(f,ended=False):
    row,_=replied(f)
    if ended:assert post(f,row,ack_data(read(f,row).json()),'original-awareness').status_code==200
    v=read(f,row).json();r=post(f,row,request_data(v),'original-recheck');assert r.status_code==200,r.text;return row,r.json()

@pytest.mark.parametrize('ended',[False,True])
def test_owner_recheck_application_does_not_resume_until_original_specialist_takes(template_consumption,ended):
    f=template_consumption;row,_=replied(f)
    if ended:assert post(f,row,ack_data(read(f,row).json()),'first-awareness').status_code==200
    before=products(f['owner']);grants=grant_snapshot(f['owner']);resources=resource_state(f);original=read(f,row,'original-reply',user=REVIEWERS[0]).json()['event'];v=read(f,row).json()
    r=post(f,row,request_data(v),'original-recheck');assert r.status_code==200,r.text;v=r.json();item=v['items'][0]
    assert item['state']=='RECHECK_REQUESTED' and item['responsible_actor_id'] is None and item['responsibility']=='WAITING_ORIGINAL_SPECIALIST_RECHECK_ACCEPTANCE'
    assert 'REPLY' not in item['allowed_actions'] and manual_items(tasks(f,REVIEWERS[0]))[0]['kind']=='MANUAL_ACCEPT_RECHECK'
    v=read(f,row,user=REVIEWERS[0]).json();r=post(f,row,take_data(v),'original-take-recheck',user=REVIEWERS[0]);assert r.status_code==200,r.text;assert r.json()['items'][0]['state']=='UNDER_MANUAL_RECHECK'
    r=post(f,row,reply_data(read(f,row,user=REVIEWERS[0]).json()),'new-reply',user=REVIEWERS[0]);assert r.status_code==200,r.text;assert r.json()['items'][0]['reply']['id']!=original['id']
    r=post(f,row,ack_data(read(f,row).json()),'new-awareness');assert r.status_code==200 and r.json()['items'][0]['state']=='COORDINATION_ENDED'
    assert manual_items(tasks(f))==[] and manual_items(tasks(f,REVIEWERS[0]))==[]
    assert r.json()['overall_goal_state']=='PARTIAL' and r.json()['case_goal_completed'] is False
    assert read(f,row,'original-reply',user=REVIEWERS[0]).json()['event']==original
    a=deepcopy(products(f['owner']));b=deepcopy(before)
    for snap in (a,b):
        for p in snap['preparations']:p['service_case_plan'].pop('manual_goal_requests',None)
    assert a==b and grant_snapshot(f['owner'])==grants and resource_state(f)==resources

@pytest.mark.parametrize('phase',['request','take'])
@pytest.mark.parametrize('bad',['reply_id','reply_hash','source','plan','revision','other_owner','other_reviewer','wrong_role'])
def test_recheck_exact_bindings_and_original_role_refuse_zero_write(template_consumption,phase,bad):
    f=template_consumption
    if phase=='request':row,_=replied(f);v=read(f,row).json();d=request_data(v);user=ENTERPRISES[0]
    else:row,_=applied(f);v=read(f,row,user=REVIEWERS[0]).json();d=take_data(v);user=REVIEWERS[0]
    if bad=='reply_id':d['reply_event_id']=str(uuid4())
    if bad=='reply_hash':d['reply_fingerprint']='0'*64
    if bad=='source':d['expected_source_sha256']='0'*64
    if bad=='plan':d['plan_id']=str(uuid4())
    if bad=='revision':d['expected_revision']=0
    if bad=='other_owner':user=ENTERPRISES[1]
    if bad=='other_reviewer':user=REVIEWERS[1]
    if bad=='wrong_role':user=REVIEWERS[0] if phase=='request' else ENTERPRISES[0]
    before=products(f['owner']);r=post(f,row,d,user=user);assert r.status_code in (403,409);assert products(f['owner'])==before

@pytest.mark.parametrize('phase',['request','take'])
@pytest.mark.parametrize('same',[True,False])
def test_recheck_concurrent_original_key_and_changed_parameter_conflict(template_consumption,phase,same):
    f=template_consumption
    if phase=='request':row,_=replied(f);d=request_data(read(f,row).json());user=ENTERPRISES[0]
    else:row,_=applied(f);d=take_data(read(f,row,user=REVIEWERS[0]).json());user=REVIEWERS[0]
    rev=read(f,row).json()['revision']
    with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda i:post(f,row,d,'same' if same else 'key-'+str(i),user=user),range(2)))
    assert sorted(r.status_code for r in rs)==([200,200] if same else [200,409]);assert read(f,row).json()['revision']==rev+1
    first=next(r for r in rs if r.status_code==200).json()['event'];assert read(f,row,first['request_key'],user=user).json()['event']==first
    before=products(f['owner']);assert post(f,row,{**d,'reason':'SYNTHETIC changed'},first['request_key'],user=user).status_code==409;assert products(f['owner'])==before

@pytest.mark.parametrize('phase',['request','take'])
@pytest.mark.parametrize('obstacle',['cancel','read','write','source','replace'])
def test_recheck_current_authority_source_cancel_plan_and_cold_receipt(template_consumption,phase,obstacle):
    from parkweave.preparation import _insert_evidence
    f=template_consumption
    if phase=='request':row,_=replied(f);d=request_data(read(f,row).json());user=ENTERPRISES[0]
    else:row,_=applied(f);d=take_data(read(f,row,user=REVIEWERS[0]).json());user=REVIEWERS[0]
    if obstacle=='cancel':cancel(f,row)
    if obstacle in ('read','write'):
        table='capability_grants' if obstacle=='read' or phase=='request' else 'preparation_grants';cap='READ' if obstacle=='read' else 'EXECUTE' if phase=='request' else 'REVIEW_ASSIGNED'
        with f['owner'].connect() as c:c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',(user,cap))
    if obstacle=='source':
        with f['owner'].connect() as c:
            parent=c.execute('SELECT * FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone();actor=c.execute('SELECT * FROM principals WHERE id=%s',(ENTERPRISES[0],)).fetchone();_insert_evidence(c,actor,parent,'material_outline','SYNTHETIC changed recheck source','DOCUMENT_EXCERPT','SYNTHETIC newer material')
    if obstacle=='replace':replace_plan(f,row)
    before=products(f['owner']);r=post(f,row,d,user=user);assert r.status_code in (403,409);assert products(f['owner'])==before
    if obstacle not in ('read','write'):
        oldkey='original-recheck' if phase=='take' else 'original-reply';olduser=ENTERPRISES[0] if phase=='take' else REVIEWERS[0]
        assert read(f,row,oldkey,user=olduser).json()['status']=='COMMITTED'
        if obstacle=='replace':assert manual_items(tasks(f,REVIEWERS[0]))==[]

@pytest.mark.parametrize('phase',['request','take'])
def test_recheck_event_failure_rollback_and_original_key_recovery_after_plan_replacement(template_consumption,monkeypatch,phase):
    from parkweave import manual_goal_requests as human
    f=template_consumption
    if phase=='request':row,_=replied(f);d=request_data(read(f,row).json());user=ENTERPRISES[0]
    else:row,_=applied(f);d=take_data(read(f,row,user=REVIEWERS[0]).json());user=REVIEWERS[0]
    before=products(f['owner']);save=human.steps._save
    def fail(*args):save(*args);raise RuntimeError('SYNTHETIC recheck rollback')
    monkeypatch.setattr(human.steps,'_save',fail)
    with pytest.raises(RuntimeError,match='recheck rollback'):post(f,row,d,'lost-recheck',user=user)
    assert products(f['owner'])==before;monkeypatch.setattr(human.steps,'_save',save)
    r=post(f,row,d,'lost-recheck',user=user);assert r.status_code==200;event=r.json()['event'];replace_plan(f,row);before=products(f['owner'],True)
    assert read(f,row,'lost-recheck',user=user).json()['event']==event;assert post(f,row,d,'lost-recheck',user=user).json()['event']==event
    assert manual_items(tasks(f))==[] and manual_items(tasks(f,REVIEWERS[0]))==[] and products(f['owner'],True)==before

def test_old_reply_cannot_acknowledge_new_reply_and_exact_application_required(template_consumption):
    f=template_consumption;row,_=applied(f);v=read(f,row,user=REVIEWERS[0]).json();d=take_data(v)
    for field in ('recheck_event_id','recheck_fingerprint'):
        before=products(f['owner']);assert post(f,row,{**d,field:str(uuid4()) if field.endswith('_id') else '0'*64},user=REVIEWERS[0]).status_code==409;assert products(f['owner'])==before
    assert post(f,row,d,user=REVIEWERS[0]).status_code==200;old=ack_data(read(f,row).json())
    assert post(f,row,reply_data(read(f,row).json()),user=REVIEWERS[0]).status_code==200;v=read(f,row).json();old['expected_revision']=v['revision'];before=products(f['owner']);assert post(f,row,old).status_code==409;assert products(f['owner'])==before

def test_recheck_cannot_spend_ack_slot_or_start_without_full_take_reply_ack_capacity(template_consumption):
    f=template_consumption;row=at_revision_29(f);assert post(f,row,reply_data(read(f,row).json()),user=REVIEWERS[0]).status_code==200
    v=read(f,row).json();assert v['revision']==30 and 'REQUEST_RECHECK' not in v['items'][0]['allowed_actions'];before=products(f['owner']);assert post(f,row,request_data(v)).status_code==409;assert products(f['owner'])==before
    assert post(f,row,ack_data(v)).status_code==200;v=read(f,row).json();assert 'REQUEST_RECHECK' not in v['items'][0]['allowed_actions'];before=products(f['owner']);assert post(f,row,request_data(v)).status_code==409;assert products(f['owner'])==before

@pytest.mark.parametrize('phase',['request','take'])
def test_actual_owned_pg_recheck_wait_rechecks_new_material_before_admission(template_consumption,phase):
    import time,json
    from pathlib import Path
    from parkweave.preparation import _insert_evidence
    f=template_consumption
    if phase=='request':row,_=replied(f);d=request_data(read(f,row).json());user=ENTERPRISES[0]
    else:row,_=applied(f);d=take_data(read(f,row,user=REVIEWERS[0]).json());user=REVIEWERS[0]
    with ThreadPoolExecutor(1) as pool:
        with f['owner'].connect() as holder:
            parent=holder.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(row['preparation_id'],)).fetchone();pid=holder.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'];future=pool.submit(post,f,row,d,'waiting-recheck',user=user);deadline=time.monotonic()+2;blocked=False
            with f['owner'].connect() as monitor:
                while time.monotonic()<deadline:
                    monitor.execute('SELECT pg_stat_clear_snapshot()');blocked=monitor.execute('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND %s=ANY(pg_blocking_pids(pid))) AS yes',(pid,)).fetchone()['yes']
                    if blocked:break
                    time.sleep(.01)
            assert blocked;actor=holder.execute('SELECT * FROM principals WHERE id=%s',(ENTERPRISES[0],)).fetchone();_insert_evidence(holder,actor,parent,'material_outline','SYNTHETIC newer recheck material','DOCUMENT_EXCERPT','SYNTHETIC changed source')
        r=future.result(timeout=5);assert r.status_code==409,r.text
    v=read(f,row).json();assert v['items'][0]['state']==('WAITING_OWNER_ACKNOWLEDGEMENT' if phase=='request' else 'RECHECK_REQUESTED')
    Path('.runtime/manual-goal-recheck-20261014/pg-'+phase+'.json').write_text(json.dumps(dict(actual_owned_pg_parent_wait=blocked,response=r.status_code,state=v['items'][0]['state']))+'\n')

@pytest.mark.parametrize('mode',['waiting','ended','lost_request','lost_take','cancel','late'])
def test_original_page_explicit_recheck_cold_unknown_cancel_and_late(template_consumption,mode):
    import json,subprocess,selectors
    from pathlib import Path
    f=template_consumption;row,_=replied(f)
    if mode=='ended':assert post(f,row,ack_data(read(f,row).json()),'known-before-recheck').status_code==200
    grants=grant_snapshot(f['owner']);resources=resource_state(f);baseline=products(f['owner'],True);messages=[];summary=None;lost=False
    proc=subprocess.Popen(['node','tests/manual_goal_recheck_actual.js',REVIEWERS[0],ENTERPRISES[0],row['preparation_id'],mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
    try:
        while True:
            assert sel.select(timeout=15),'recheck page timeout';line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if msg.get('cancel_case'):
                cancel(f,row);baseline=products(f['owner'],True);proc.stdin.write(b'{}\n');proc.stdin.flush();continue
            if 'request' not in msg:summary=msg;break
            q=msg['request'];o=q['options'];method=o.get('method','GET');data=json.loads(o['body']) if o.get('body') else None;actor=o['headers']['Authorization'].removeprefix('Bearer SYNTHETIC_');h={'Authorization':'Bearer '+f['tokens'][actor]}
            if key:=o['headers'].get('Idempotency-Key'):h['Idempotency-Key']=key
            r=f['client'].request(method,q['path'],headers=h,json=data);assert r.status_code==200,r.text
            if actor==REVIEWERS[0]:assert B not in r.text
            if method=='GET':assert products(f['owner'],True)==baseline
            else:baseline=products(f['owner'],True)
            assert grant_snapshot(f['owner'])==grants and resource_state(f)==resources
            drop=not lost and method=='POST' and ((mode=='lost_request' and data['action']=='REQUEST_RECHECK') or (mode=='lost_take' and data['action']=='TAKE_RECHECK'));lost=lost or drop
            messages.append(dict(method=method,path=q['path'],actor=actor,status=r.status_code,action=data.get('action') if data else None,dropped_reply=drop))
            proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json(),**({'lost':True} if drop else {})})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['posts']==(1 if mode in ('cancel','late') else 4);assert lost==(mode in ('lost_request','lost_take'))
    finally:
        Path('.runtime/manual-goal-recheck-20261014/page-'+mode+'-chain.json').write_text(json.dumps(dict(summary=summary,requests=messages,lost_original_response=lost),indent=2)+'\n');sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)

def test_recheck_reserved_take_reply_ack_survive_other_goal_until_revision_32(template_consumption):
    f=template_consumption;row,_=applied(f)
    for action,user in [('REQUEST',ENTERPRISES[0]),('TAKE',REVIEWERS[0])]:
        v=read(f,row).json();assert post(f,row,{**command(v,action),'goal':B},user=user).status_code==200
    actions=[('REQUEST_EVIDENCE',REVIEWERS[0]),('SUPPLY_EVIDENCE',ENTERPRISES[0]),('TAKE',REVIEWERS[0])]*7+[('REQUEST_EVIDENCE',REVIEWERS[0]),('SUPPLY_EVIDENCE',ENTERPRISES[0])]
    for action,user in actions:
        v=read(f,row).json();d={**command(v,action),'goal':B}
        if action=='SUPPLY_EVIDENCE':d['evidence']=[{k:v['materials'][0][k] for k in ('id','version','source_sha256')}]
        assert post(f,row,d,user=user).status_code==200
    v=read(f,row).json();assert v['revision']==29
    r=post(f,row,take_data(v),user=REVIEWERS[0]);assert r.status_code==200 and r.json()['revision']==30
    v=read(f,row).json();before=products(f['owner']);assert post(f,row,{**command(v,'TAKE'),'goal':B},user=REVIEWERS[0]).status_code==409;assert products(f['owner'])==before
    r=post(f,row,reply_data(v),user=REVIEWERS[0]);assert r.status_code==200 and r.json()['revision']==31
    r=post(f,row,ack_data(read(f,row).json()));assert r.status_code==200 and r.json()['revision']==32 and r.json()['items'][0]['state']=='COORDINATION_ENDED'
