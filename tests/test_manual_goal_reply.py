"""Original same-Case human reply and explicit awareness, not fulfillment."""
from copy import deepcopy
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_template_consumer import template_consumption,products
from test_manual_goal_privacy import private_case,replace_plan,A,B
from test_manual_goal_requests import read,post
from test_manual_goal_tasks import act,tasks,manual_items,confirmed
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot

def command(v,action,**extra):
    return dict(action=action,plan_id=v['plan_id'],goal=A,expected_revision=v['revision'],expected_source_sha256=v['source_sha256'],reason='SYNTHETIC explicit '+action,evidence=[],**extra)

def ready(f):
    row=private_case(f);confirmed(f,row);act(f,row,'REQUEST');act(f,row,'TAKE',REVIEWERS[0]);return row

def reply_data(v,kind='INFORMATION'):
    d=command(v,'REPLY',reply_kind=kind)
    if kind=='INFORMATION':d['evidence']=[{k:v['materials'][0][k] for k in ('id','version','source_sha256')}]
    return d

def ack_data(v):
    reply=next(x for x in v['items'] if x['goal']==A)['reply']
    return command(v,'ACKNOWLEDGE_REPLY',reply_event_id=reply['id'],reply_fingerprint=reply['fingerprint'])

def replied(f,kind='INFORMATION'):
    row=ready(f);v=read(f,row,user=REVIEWERS[0]).json();r=post(f,row,reply_data(v,kind),'original-reply',user=REVIEWERS[0]);assert r.status_code==200,r.text;return row,r.json()

@pytest.mark.parametrize('kind',['INFORMATION','UNABLE_TO_HANDLE'])
def test_original_reply_explicit_awareness_closes_only_human_responsibility(template_consumption,kind):
    f=template_consumption;row=ready(f);before=products(f['owner']);grants=grant_snapshot(f['owner']);v=read(f,row,user=REVIEWERS[0]).json();d=reply_data(v,kind)
    r=post(f,row,d,'original-reply',user=REVIEWERS[0]);assert r.status_code==200,r.text
    v=read(f,row).json();item=v['items'][0];assert item['state']=='WAITING_OWNER_ACKNOWLEDGEMENT' and item['reply']['request']['reply_kind']==kind
    assert item['reply']['awareness_proves_reading'] is False and item['reply']['truth_verified'] is False
    assert manual_items(tasks(f))[0]['kind']=='MANUAL_ACKNOWLEDGE_REPLY' and manual_items(tasks(f,REVIEWERS[0]))==[]
    r=post(f,row,ack_data(v),'original-awareness');assert r.status_code==200,r.text
    item=r.json()['items'][0];assert item['state']=='COORDINATION_ENDED' and item['allowed_actions']==[] and item['responsible_actor_id'] is None
    assert manual_items(tasks(f))==[] and manual_items(tasks(f,REVIEWERS[0]))==[]
    assert r.json()['case_goal_completed'] is False and r.json()['overall_goal_state']=='PARTIAL' and item['goal_state']=='UNSUPPORTED'
    after=products(f['owner']);a=deepcopy(after);b=deepcopy(before)
    for snapshot in (a,b):
        for p in snapshot['preparations']:p['service_case_plan'].pop('manual_goal_requests',None)
    assert a==b and grant_snapshot(f['owner'])==grants
    assert read(f,row,'original-awareness').json()['event']==r.json()['event']

@pytest.mark.parametrize('binding',['event','fingerprint','goal','source','revision','plan'])
def test_awareness_requires_exact_current_original_reply(template_consumption,binding):
    f=template_consumption;row,v=replied(f);d=ack_data(read(f,row).json())
    field={'event':'reply_event_id','fingerprint':'reply_fingerprint','goal':'goal','source':'expected_source_sha256','revision':'expected_revision','plan':'plan_id'}[binding]
    d[field]=str(uuid4()) if binding in ('event','plan') else '0'*64 if binding in ('fingerprint','source') else B if binding=='goal' else 0
    before=products(f['owner']);assert post(f,row,d).status_code==409;assert products(f['owner'])==before

@pytest.mark.parametrize('kind',['owner_reply','specialist_ack','other_owner','other_specialist','unaccepted'])
def test_original_responsibility_cannot_be_skipped_or_transferred(template_consumption,kind):
    f=template_consumption
    if kind=='unaccepted':
        row=private_case(f);act(f,row,'REQUEST');d=reply_data(read(f,row).json());user=REVIEWERS[0]
    else:
        row,_=replied(f);v=read(f,row).json();d=reply_data(v) if kind=='owner_reply' else ack_data(v)
        user={'owner_reply':ENTERPRISES[0],'specialist_ack':REVIEWERS[0],'other_owner':ENTERPRISES[1],'other_specialist':REVIEWERS[1]}[kind]
    before=products(f['owner']);r=post(f,row,d,user=user);assert r.status_code in (403,409);assert products(f['owner'])==before

@pytest.mark.parametrize('authority',['READ','PREPARE','EXECUTE','case.create','REVIEW_ASSIGNED'])
def test_current_authority_rechecked_before_reply_awareness_and_cache(template_consumption,authority):
    f=template_consumption;row,v=replied(f);d=ack_data(read(f,row).json());assert post(f,row,d,'ack-known').status_code==200
    user=REVIEWERS[0] if authority=='REVIEW_ASSIGNED' else ENTERPRISES[0]
    table='action_grants' if authority=='case.create' else 'preparation_grants' if authority in ('PREPARE','REVIEW_ASSIGNED') else 'capability_grants'
    column='action' if authority=='case.create' else 'capability'
    with f['owner'].connect() as c:c.execute(f'UPDATE {table} SET active=false WHERE principal_id=%s AND {column}=%s',(user,authority))
    before=products(f['owner']);r=post(f,row,d,'ack-known') if user==ENTERPRISES[0] else read(f,row,'original-reply',user=user)
    assert r.status_code==403 and products(f['owner'])==before
    if authority in ('EXECUTE','case.create'):assert read(f,row,'ack-known').json()['status']=='COMMITTED'

@pytest.mark.parametrize('action',['REPLY','ACKNOWLEDGE_REPLY'])
@pytest.mark.parametrize('same',[True,False])
def test_concurrent_reply_and_awareness_original_key_admission(template_consumption,action,same):
    f=template_consumption
    if action=='REPLY':row=ready(f);d=reply_data(read(f,row).json());user=REVIEWERS[0]
    else:row,_=replied(f);d=ack_data(read(f,row).json());user=ENTERPRISES[0]
    initial=read(f,row).json()['revision']
    with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda i:post(f,row,d,'same-key' if same else 'key-'+str(i),user=user),range(2)))
    assert sorted(r.status_code for r in rs)==([200,200] if same else [200,409]);assert read(f,row).json()['revision']==initial+1
    event=next(r.json()['event'] for r in rs if r.status_code==200)
    assert read(f,row,event['request_key'],user=user).json()['event']==event
    assert post(f,row,{**d,'reason':'SYNTHETIC changed'},event['request_key'],user=user).status_code==409

@pytest.mark.parametrize('action',['REPLY','ACKNOWLEDGE_REPLY'])
def test_event_save_failure_all_rolls_back_then_original_key_recovers(template_consumption,monkeypatch,action):
    from parkweave import manual_goal_requests as human
    f=template_consumption
    if action=='REPLY':row=ready(f);d=reply_data(read(f,row).json());user=REVIEWERS[0]
    else:row,_=replied(f);d=ack_data(read(f,row).json());user=ENTERPRISES[0]
    before=products(f['owner']);save=human.steps._save
    def fail(*args):save(*args);raise RuntimeError('SYNTHETIC reply event rollback')
    monkeypatch.setattr(human.steps,'_save',fail)
    with pytest.raises(RuntimeError,match='event rollback'):post(f,row,d,'lost',user=user)
    assert products(f['owner'])==before
    monkeypatch.setattr(human.steps,'_save',save);first=post(f,row,d,'lost',user=user);assert first.status_code==200
    before=products(f['owner'],True);assert read(f,row,'lost',user=user).json()['event']==first.json()['event'];assert products(f['owner'],True)==before

def cancel(f,row):
    from test_template_consumer import headers
    path='/api/preparations/'+row['preparation_id']+'/case-cancellation';q=f['client'].get(path,headers=headers(f)).json();assert q['can_cancel']
    d=dict(case_id=q['case_id'],expected_preparation_revision=q['preparation_revision'],expected_lifecycle_revision=q['lifecycle_revision'],expected_source_sha256=q['source_sha256'],confirm_cancel=True,reason='SYNTHETIC original owner explicitly cancels')
    r=f['client'].post(path,headers=headers(f,key=uuid4().hex),json=d);assert r.status_code==200,r.text

def test_real_cancel_after_reply_preserves_receipt_and_refuses_awareness(template_consumption):
    f=template_consumption;row,_=replied(f);d=ack_data(read(f,row).json());cancel(f,row);before=products(f['owner'])
    assert post(f,row,d).status_code==409;v=read(f,row).json();assert v['items'][0]['state']=='WAITING_OWNER_ACKNOWLEDGEMENT' and v['items'][0]['allowed_actions']==[]
    assert read(f,row,'original-reply',user=REVIEWERS[0]).json()['status']=='COMMITTED';assert products(f['owner'])==before

def test_real_plan_replacement_keeps_old_reply_awareness_receipts_out_of_current_tasks(template_consumption):
    f=template_consumption;row,v=replied(f);d=ack_data(read(f,row).json());r=post(f,row,d,'awareness-old');assert r.status_code==200;old=r.json()['event'];reply=read(f,row,'original-reply',user=REVIEWERS[0]).json()['event']
    replace_plan(f,row);before=products(f['owner'],True)
    assert read(f,row,'awareness-old').json()['event']==old and read(f,row,'original-reply',user=REVIEWERS[0]).json()['event']==reply
    assert post(f,row,d,'awareness-old').json()['event']==old and post(f,row,{**d,'reason':'SYNTHETIC different'},'awareness-old').status_code==409
    assert manual_items(tasks(f))==[] and manual_items(tasks(f,REVIEWERS[0]))==[];assert products(f['owner'],True)==before

@pytest.mark.parametrize('winner',['material','cancelled'])
def test_actual_owned_pg_lock_wait_rechecks_reply_source_before_awareness(template_consumption,winner):
    import time,json
    from pathlib import Path
    from parkweave.preparation import _insert_evidence
    f=template_consumption;row,_=replied(f);d=ack_data(read(f,row).json())
    with ThreadPoolExecutor(1) as pool:
        with f['owner'].connect() as holder:
            parent=holder.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(row['preparation_id'],)).fetchone();pid=holder.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'];future=pool.submit(post,f,row,d,'waiting-awareness')
            deadline=time.monotonic()+2;blocked=False
            with f['owner'].connect() as monitor:
                while time.monotonic()<deadline:
                    monitor.execute('SELECT pg_stat_clear_snapshot()');blocked=monitor.execute('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND %s=ANY(pg_blocking_pids(pid))) AS yes',(pid,)).fetchone()['yes']
                    if blocked:break
                    time.sleep(.01)
            assert blocked
            if winner=='cancelled':holder.execute("UPDATE cases SET state='CANCELLED' WHERE id=%s",(row['case_id'],))
            else:
                actor=holder.execute('SELECT * FROM principals WHERE id=%s',(ENTERPRISES[0],)).fetchone();_insert_evidence(holder,actor,parent,'material_outline','SYNTHETIC changed after reply','DOCUMENT_EXCERPT','SYNTHETIC newer material')
        r=future.result(timeout=5);assert r.status_code==409,r.text
    v=read(f,row).json();assert v['items'][0]['state']=='WAITING_OWNER_ACKNOWLEDGEMENT' and 'ACKNOWLEDGE_REPLY' not in v['items'][0]['allowed_actions']
    Path('.runtime/manual-goal-reply-20261014/pg-'+winner+'.json').write_text(json.dumps(dict(actual_pg_lock_wait=blocked,winner=winner,status=r.status_code,revision=v['revision']))+'\n')

@pytest.mark.parametrize('mode',['normal','unable','lost_reply','lost_ack','cancel','late'])
def test_original_page_reply_awareness_cancel_late_and_lost_original_key(template_consumption,mode):
    import json,subprocess,selectors
    from pathlib import Path
    f=template_consumption;row=ready(f);grants=grant_snapshot(f['owner']);baseline=products(f['owner'],True);messages=[];summary=None;lost=False
    proc=subprocess.Popen(['node','tests/manual_goal_reply_actual.js',REVIEWERS[0],ENTERPRISES[0],row['preparation_id'],mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
    try:
        while True:
            assert sel.select(timeout=15),'reply page timeout';line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if msg.get('cancel_case'):
                cancel(f,row);baseline=products(f['owner'],True);proc.stdin.write(b'{}\n');proc.stdin.flush();continue
            if 'request' not in msg:summary=msg;break
            q=msg['request'];o=q['options'];method=o.get('method','GET');data=json.loads(o['body']) if o.get('body') else None;actor=o['headers']['Authorization'].removeprefix('Bearer SYNTHETIC_');h={'Authorization':'Bearer '+f['tokens'][actor]}
            if key:=o['headers'].get('Idempotency-Key'):h['Idempotency-Key']=key
            r=f['client'].request(method,q['path'],headers=h,json=data);assert r.status_code==200,r.text;assert B not in r.text if actor==REVIEWERS[0] else True
            if method=='GET':assert products(f['owner'],True)==baseline
            else:baseline=products(f['owner'],True)
            assert grant_snapshot(f['owner'])==grants
            drop=not lost and method=='POST' and ((mode=='lost_reply' and data['action']=='REPLY') or (mode=='lost_ack' and data['action']=='ACKNOWLEDGE_REPLY'));lost=lost or drop
            messages.append(dict(method=method,path=q['path'],actor=actor,status=r.status_code,action=data.get('action') if data else None,dropped_reply=drop))
            proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json(),**({'lost':True} if drop else {})})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['posts']==(1 if mode in ('cancel','late') else 2);assert lost==(mode in ('lost_reply','lost_ack'))
    finally:
        Path('.runtime/manual-goal-reply-20261014/page-'+mode+'-chain.json').write_text(json.dumps(dict(summary=summary,requests=messages,lost_original_response=lost),indent=2)+'\n');sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)

def at_revision_29(f):
    row=ready(f)
    for _ in range(9):
        for action,user in [('REQUEST_EVIDENCE',REVIEWERS[0]),('SUPPLY_EVIDENCE',ENTERPRISES[0]),('TAKE',REVIEWERS[0])]:
            v=read(f,row,user=user).json();d=command(v,action)
            if action=='SUPPLY_EVIDENCE':d['evidence']=[{k:v['materials'][0][k] for k in ('id','version','source_sha256')}]
            assert post(f,row,d,user=user).status_code==200
    assert read(f,row).json()['revision']==29;return row

def test_reply_reserves_final_awareness_slot_against_other_goal_writes(template_consumption):
    f=template_consumption;row=at_revision_29(f);v=read(f,row).json();assert post(f,row,reply_data(v),user=REVIEWERS[0]).status_code==200
    v=read(f,row).json();assert post(f,row,{**command(v,'REQUEST'),'goal':B}).status_code==200
    v=read(f,row).json();before=products(f['owner']);assert post(f,row,{**command(v,'TAKE'),'goal':B},user=REVIEWERS[0]).status_code==409;assert products(f['owner'])==before
    r=post(f,row,ack_data(v));assert r.status_code==200 and r.json()['revision']==32 and r.json()['items'][0]['state']=='COORDINATION_ENDED'

def test_reply_cannot_consume_last_event_without_awareness_capacity(template_consumption):
    f=template_consumption;row=at_revision_29(f)
    for action,user in [('REQUEST',ENTERPRISES[0]),('TAKE',REVIEWERS[0])]:
        v=read(f,row).json();assert post(f,row,{**command(v,action),'goal':B},user=user).status_code==200
    v=read(f,row,user=REVIEWERS[0]).json();assert v['revision']==31 and 'REPLY' not in v['items'][0]['allowed_actions'];before=products(f['owner']);assert post(f,row,reply_data(v),user=REVIEWERS[0]).status_code==409;assert products(f['owner'])==before
