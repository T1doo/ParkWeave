"""Owned PG original template partial goals and manual coordination."""
from copy import deepcopy
from uuid import UUID,uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_template_consumer import template_consumption,headers,products
from test_template_partial import committed,EXTERNAL
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot
from parkweave import manual_goal_requests as manual

def read(f,row,key=None,user=None):
    h=headers(f) if user is None else {'Authorization':'Bearer '+f['tokens'][user]}
    return f['client'].get('/api/preparations/'+row['preparation_id']+'/manual-goal-requests'+('/recovery/'+key if key else ''),headers=h)

def body(v,action,**extra):
    return dict(action=action,plan_id=v['plan_id'],goal=EXTERNAL,expected_revision=v['revision'],expected_source_sha256=v['source_sha256'],reason='SYNTHETIC explicit manual '+action,**extra)

def post(f,row,data,key=None,user=None):
    h=headers(f,key=key or uuid4().hex) if user is None else {'Authorization':'Bearer '+f['tokens'][user],'Idempotency-Key':key or uuid4().hex}
    return f['client'].post('/api/preparations/'+row['preparation_id']+'/manual-goal-requests',headers=h,json=data)

def setup(f):
    row,_,_,_=committed(f);r=read(f,row);assert r.status_code==200,r.text;return row,r.json()

def state(r,want):
    assert r.status_code==200,r.text;assert r.json()['items'][0]['state']==want;assert r.json()['overall_goal_state']=='PARTIAL';assert r.json()['case_goal_completed'] is False;return r.json()

def test_original_owner_and_reviewer_request_supplement_responsibility_without_fulfillment(template_consumption):
    f=template_consumption;row,v=setup(f);before=products(f['owner']);grants=grant_snapshot(f['owner']);v=state(post(f,row,body(v,'REQUEST')),'REQUESTED')
    assert v['items'][0]['responsibility']=='WAITING_ORIGINAL_SPECIALIST_ACCEPTANCE'
    v=state(post(f,row,body(v,'TAKE'),user=REVIEWERS[0]),'UNDER_MANUAL_REVIEW')
    v=state(post(f,row,body(v,'REQUEST_EVIDENCE'),user=REVIEWERS[0]),'WAITING_OWNER_EVIDENCE')
    evidence=[{k:v['materials'][0][k] for k in ('id','version','source_sha256')}]
    v=state(post(f,row,body(v,'SUPPLY_EVIDENCE',evidence=evidence)),'AWAITING_SPECIALIST_REVIEW')
    v=state(post(f,row,body(v,'TAKE'),user=REVIEWERS[0]),'UNDER_MANUAL_REVIEW')
    state(post(f,row,body(v,'WITHDRAW')),'WITHDRAWN');assert grant_snapshot(f['owner'])==grants
    after=products(f['owner']);a=deepcopy(after);b=deepcopy(before)
    for x in a['preparations']:x['service_case_plan'].pop('manual_goal_requests',None)
    assert a==b
    result=f['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(f));assert result.status_code==200 and result.json()['state']=='PARTIAL' and result.json()['results'][1]['state']=='UNSUPPORTED'

def test_exact_original_key_recovery_same_parameters_and_changed_conflict(template_consumption):
    f=template_consumption;row,v=setup(f);data=body(v,'REQUEST');first=post(f,row,data,'original-manual');state(first,'REQUESTED');before=products(f['owner'],include_audit=True)
    again=post(f,row,data,'original-manual');assert again.json()['event']==first.json()['event'];assert post(f,row,{**data,'reason':'SYNTHETIC different'},'original-manual').status_code==409
    r=read(f,row,'original-manual');assert r.json()['status']=='COMMITTED' and r.json()['event']==first.json()['event'];assert read(f,row,'missing').json()['status']=='NOT_OBSERVED';assert products(f['owner'],include_audit=True)==before

@pytest.mark.parametrize('action',['TAKE','REQUEST_EVIDENCE','SUPPLY_EVIDENCE'])
def test_owner_cannot_accept_specialist_responsibility_or_skip_states(template_consumption,action):
    f=template_consumption;row,v=setup(f);extra={'evidence':[{k:v['materials'][0][k] for k in ('id','version','source_sha256')}]} if action=='SUPPLY_EVIDENCE' else {}
    before=products(f['owner']);assert post(f,row,body(v,action,**extra)).status_code==409;assert products(f['owner'])==before

@pytest.mark.parametrize('kind',['goal','plan','source','revision','other_owner','reviewer_request','capability','cancelled','reconciling','closed'])
def test_refusal_has_zero_write(template_consumption,kind):
    f=template_consumption;row,v=setup(f);data=body(v,'REQUEST');user=None
    if kind=='goal':data['goal']='LOCAL_MATERIAL_PREPARATION'
    if kind=='plan':data['plan_id']=str(uuid4())
    if kind=='source':data['expected_source_sha256']='0'*64
    if kind=='revision':data['expected_revision']=1
    if kind=='other_owner':user=ENTERPRISES[1]
    if kind=='reviewer_request':user=REVIEWERS[0]
    with f['owner'].connect() as c:
        if kind=='capability':c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='EXECUTE'",(ENTERPRISES[0],))
        if kind in ('cancelled','reconciling'):c.execute('UPDATE cases SET state=%s WHERE id=%s',(kind.upper(),row['case_id']))
        if kind=='closed':
            # A pre-existing local closure is setup evidence only, no new capability.
            c.execute("INSERT INTO case_local_lifecycles(preparation_id,case_id,revision,cycle,state,verified_snapshot,verified_sha256) VALUES(%s,%s,1,1,'LOCAL_RECORD_CLOSED','{}',%s)",(row['preparation_id'],row['case_id'],'0'*64))
    before=products(f['owner']);r=post(f,row,data,user=user);assert r.status_code in (403,409),r.text;assert products(f['owner'])==before

@pytest.mark.parametrize('same',[True,False])
def test_concurrent_original_keys_exactly_one_admission(template_consumption,same):
    f=template_consumption;row,v=setup(f);data=body(v,'REQUEST')
    with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda i:post(f,row,data,'same' if same else 'different-'+str(i)),range(2)))
    assert sorted(r.status_code for r in rs)==([200,200] if same else [200,409]);assert read(f,row).json()['revision']==1

def test_save_failure_rolls_back_and_original_get_can_recover_lost_reply(template_consumption,monkeypatch):
    f=template_consumption;row,v=setup(f);before=products(f['owner']);original=manual.steps._save
    def fail(c,parent,plan):original(c,parent,plan);raise RuntimeError('SYNTHETIC injected save failure')
    monkeypatch.setattr(manual.steps,'_save',fail)
    with pytest.raises(RuntimeError,match='injected'):post(f,row,body(v,'REQUEST'),'lost')
    assert products(f['owner'])==before;monkeypatch.setattr(manual.steps,'_save',original)
    state(post(f,row,body(v,'REQUEST'),'lost'),'REQUESTED');assert read(f,row,'lost').json()['status']=='COMMITTED'

@pytest.mark.parametrize('winner',['cancelled','material'])
def test_actual_parent_pg_lock_wait_rechecks_committed_source(template_consumption,winner):
    import time,json
    from pathlib import Path
    from parkweave.preparation import _insert_evidence
    f=template_consumption;row,v=setup(f);data=body(v,'REQUEST');blocked=False
    with ThreadPoolExecutor(1) as pool:
        with f['owner'].connect() as holder:
            parent=holder.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(row['preparation_id'],)).fetchone();pid=holder.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            future=pool.submit(post,f,row,data,'pg-wait-'+winner)
            deadline=time.monotonic()+2
            with f['owner'].connect() as monitor:
                while time.monotonic()<deadline:
                    blocked=monitor.execute('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND %s=ANY(pg_blocking_pids(pid))) AS yes',(pid,)).fetchone()['yes']
                    if blocked:break
                    time.sleep(.01)
            assert blocked,'actual PG parent blocker not observed'
            if winner=='cancelled':holder.execute("UPDATE cases SET state='CANCELLED' WHERE id=%s",(row['case_id'],))
            else:
                actor=holder.execute('SELECT * FROM principals WHERE id=%s',(ENTERPRISES[0],)).fetchone();_insert_evidence(holder,actor,parent,'material_outline','SYNTHETIC newer evidence','DOCUMENT_EXCERPT','SYNTHETIC updated source')
        result=future.result(timeout=5);assert result.status_code==409,result.text
    assert read(f,row).json()['revision']==0
    Path('.runtime/same-case-goals-20261014/pg-'+winner+'.json').write_text(json.dumps({'actual_pg_parent_lock_wait':blocked,'winner':winner,'response':result.status_code,'manual_revision':0})+'\n')

def test_same_actor_original_key_cannot_escape_to_other_case(template_consumption):
    from test_template_consumer_planning import ready,preview,adoption,post as adopt_post
    from test_template_consumer import body as consume_body
    f=template_consumption;row,v=setup(f);state(post(f,row,body(v,'REQUEST'),'global-original'),'REQUESTED')
    from test_template_consumer import consume,finish,resume
    second=consume(f,key='second-create',data={**consume_body(f),'goal':'SYNTHETIC second fresh case','required_goals':['LOCAL_MATERIAL_PREPARATION',EXTERNAL]}).json();finish(f);second=resume(f,second,key='second-resume').json()
    pv=preview(f,second).json();r=adopt_post(f,second,'adopt',{**adoption(pv),'partial_adoption':True},'second-adopt');assert r.status_code==200,r.text
    v2=read(f,second).json();assert read(f,second,'global-original').status_code==409;assert post(f,second,body(v2,'REQUEST'),'global-original').status_code==409
    assert read(f,second).json()['revision']==0

def test_material_replacement_retains_old_supplement_as_stale_not_verified(template_consumption):
    from parkweave.preparation import _insert_evidence
    f=template_consumption;row,v=setup(f)
    for action,user in [('REQUEST',None),('TAKE',REVIEWERS[0]),('REQUEST_EVIDENCE',REVIEWERS[0])]:v=state(post(f,row,body(v,action),user=user),{'REQUEST':'REQUESTED','TAKE':'UNDER_MANUAL_REVIEW','REQUEST_EVIDENCE':'WAITING_OWNER_EVIDENCE'}[action])
    material=v['materials'][0];v=state(post(f,row,body(v,'SUPPLY_EVIDENCE',evidence=[{k:material[k] for k in ('id','version','source_sha256')}])),'AWAITING_SPECIALIST_REVIEW');history=deepcopy(v['items'][0]['history'])
    with f['owner'].connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(row['preparation_id'],)).fetchone();actor=c.execute('SELECT * FROM principals WHERE id=%s',(ENTERPRISES[0],)).fetchone();_insert_evidence(c,actor,parent,material['slot'],'SYNTHETIC changed material','USER_STATEMENT','SYNTHETIC fresh source')
    after=read(f,row).json();assert after['items'][0]['supplement_state']=='STALE';assert after['items'][0]['history'][-1]['evidence_current'] is False
    assert after['items'][0]['history'][-1]['request']==history[-1]['request'];assert after['overall_goal_state']=='PARTIAL'

def test_actual_original_page_same_case_facts_manual_request_lost_reply_and_cold_get(template_consumption):
    import json,subprocess,selectors
    from pathlib import Path
    from test_template_consumer import body as consume_body
    from test_template_consumer_planning import ready,preview,adoption,post as adopt_post
    f=template_consumption;data=consume_body(f);data['required_goals']=['LOCAL_MATERIAL_PREPARATION',EXTERNAL];data['materials'][1]['text']='地区甲 / 17 / 本次服务诉求'
    row=ready(f,data);pv=preview(f,row).json();assert adopt_post(f,row,'adopt',{**adoption(pv),'partial_adoption':True},'actual-original-partial').status_code==200
    grants=grant_snapshot(f['owner']);before=products(f['owner']);messages=[];summary=None;lost=False
    proc=subprocess.Popen(['node','tests/manual_goals_actual.js',row['instance_id'],row['preparation_id'],ENTERPRISES[0],REVIEWERS[0]],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
    try:
        while True:
            assert sel.select(timeout=15),'manual original page bridge timeout'
            line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if 'request' not in msg:summary=msg;break
            q=msg['request'];o=q['options'];method=o.get('method','GET');body=json.loads(o['body']) if o.get('body') else None;actor=o.get('headers',{}).get('Authorization','').removeprefix('Bearer SYNTHETIC_');h={'Authorization':'Bearer '+f['tokens'][actor]}
            if key:=o.get('headers',{}).get('Idempotency-Key'):h['Idempotency-Key']=key
            r=f['client'].request(method,q['path'],headers=h,json=body);messages.append(dict(method=method,path=q['path'],status=r.status_code,actor=actor,action=body.get('action') if body else None));assert r.status_code<400,r.text
            drop=method=='POST' and q['path'].endswith('/manual-goal-requests') and not lost
            if drop:lost=True
            proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json(),**({'lost':True} if drop else {})})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['checks']>=30;assert summary['manual_posts']==5 and lost
        after=products(f['owner']);assert grant_snapshot(f['owner'])==grants;assert after['runs']==before['runs'] and after['cases']==before['cases'] and after['model_steps']==before['model_steps'];assert len(after['preparations'])==1
        fact=f['client'].get('/api/preparations/'+row['preparation_id']+'/fact-clarifications',headers=headers(f));assert fact.json()['state']=='CURRENT' and fact.json()['case_id']==row['case_id']
        result=f['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(f));assert result.json()['state']=='PARTIAL' and result.json()['results'][1]['state']=='UNSUPPORTED'
    finally:
        Path('.runtime/same-case-goals-20261014/actual-chain.json').write_text(json.dumps({'summary':summary,'requests':messages,'lost_reply_after_actual_commit':lost},indent=2)+'\n');sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
        Path('.runtime/same-case-goals-20261014/page-stderr.log').write_bytes(proc.stderr.read())

def test_real_case_cancellation_retains_human_history_and_blocks_all_new_actions(template_consumption):
    f=template_consumption;row,v=setup(f);v=state(post(f,row,body(v,'REQUEST'),'before-cancel'),'REQUESTED');path='/api/preparations/'+row['preparation_id']+'/case-cancellation'
    quote=f['client'].get(path,headers=headers(f));assert quote.status_code==200,quote.text;q=quote.json();assert q['can_cancel']
    data=dict(case_id=q['case_id'],expected_preparation_revision=q['preparation_revision'],expected_lifecycle_revision=q['lifecycle_revision'],expected_source_sha256=q['source_sha256'],confirm_cancel=True,reason='SYNTHETIC original owner cancels before first acceptance')
    r=f['client'].post(path,headers=headers(f,key='actual-cancel'),json=data);assert r.status_code==200,r.text
    before=products(f['owner']);assert post(f,row,body(v,'WITHDRAW')).status_code==409;assert read(f,row,'before-cancel').json()['status']=='COMMITTED';assert read(f,row).json()['items'][0]['allowed_actions']==[];assert products(f['owner'])==before

def test_corrupt_material_hash_blocks_new_actions_but_preserves_original_get(template_consumption):
    f=template_consumption;row,v=setup(f);state(post(f,row,body(v,'REQUEST'),'integrity-original'),'REQUESTED')
    with f['owner'].connect() as c:c.execute("UPDATE preparation_evidence SET text='SYNTHETIC corrupt unchanged stored hash' WHERE id=%s",(v['materials'][0]['id'],))
    current=read(f,row);assert current.status_code==200;assert current.json()['items'][0]['allowed_actions']==[];assert read(f,row,'integrity-original').json()['status']=='COMMITTED'
    assert post(f,row,body(current.json(),'WITHDRAW')).status_code==409
