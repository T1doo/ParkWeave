"""Two private free-text goals are shared only by original owner REQUEST."""
import pytest
from test_template_consumer import template_consumption,headers,body as intake_body,products
from test_template_consumer_planning import ready,preview,adoption,post as adopt_post
from test_manual_goal_requests import read,post,body
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot

A='SYNTHETIC_PRIVATE_ALPHA_UNREQUESTED_PURPOSE'
B='SYNTHETIC_PRIVATE_BETA_SENSITIVE_TARGET'

def private_case(f):
    data=intake_body(f);data['required_goals']=['LOCAL_MATERIAL_PREPARATION',A,B]
    row=ready(f,data);v=preview(f,row).json();r=adopt_post(f,row,'adopt',{**adoption(v),'partial_adoption':True},'private-partial');assert r.status_code==200,r.text
    return row

def assert_private(r,shared=(),historical_shared=()):
    assert r.status_code==200,r.text
    assert [x['goal'] for x in r.json()['items']]==list(shared)
    for goal in (A,B):
        if goal not in shared and goal not in historical_shared:assert goal not in r.text,'never requested private free-text goal leaked'
    assert r.json()['overall_goal_state']=='PARTIAL' and r.json()['case_goal_completed'] is False
    return r.json()

def test_no_request_specialist_get_and_missing_key_recovery_reveal_no_private_goal(template_consumption):
    f=template_consumption;row=private_case(f);before=products(f['owner'],include_audit=True);grants=grant_snapshot(f['owner'])
    assert [x['goal'] for x in read(f,row).json()['items']]==[A,B]
    assert_private(read(f,row,user=REVIEWERS[0]))
    assert_private(read(f,row,'missing-original',user=REVIEWERS[0]))
    assert products(f['owner'],include_audit=True)==before and grant_snapshot(f['owner'])==grants

def test_one_request_specialist_post_recovery_withdrawal_never_reveals_other_goal(template_consumption):
    f=template_consumption;row=private_case(f);owner=read(f,row).json();r=post(f,row,{**body(owner,'REQUEST'),'goal':A},'share-alpha');assert r.status_code==200,r.text
    before=products(f['owner']);v=assert_private(read(f,row,user=REVIEWERS[0]),[A]);assert products(f['owner'])==before
    data={**body(v,'TAKE'),'goal':A};r=post(f,row,data,'lost-specialist-take',user=REVIEWERS[0]);v=assert_private(r,[A]);original=r.json()['event'];before=products(f['owner'],include_audit=True)
    # Drop the successful POST response: original GET recovers, no business retry.
    r=read(f,row,'lost-specialist-take',user=REVIEWERS[0]);assert_private(r,[A]);assert r.json()['event']==original
    assert_private(post(f,row,data,'lost-specialist-take',user=REVIEWERS[0]),[A]);assert products(f['owner'],include_audit=True)==before
    owner=read(f,row).json();r=post(f,row,{**body(owner,'WITHDRAW'),'goal':A},'withdraw-shared');assert r.status_code==200,r.text
    v=assert_private(read(f,row,user=REVIEWERS[0]),[A]);assert v['items'][0]['state']=='WITHDRAWN';assert len(v['items'][0]['history'])==3
    assert [x['goal'] for x in read(f,row).json()['items']]==[A,B]

@pytest.mark.parametrize('capability',['READ','REVIEW_ASSIGNED'])
def test_revoked_specialist_current_post_and_original_get_denied_without_mutation(template_consumption,capability):
    f=template_consumption;row=private_case(f);v=read(f,row).json();assert post(f,row,{**body(v,'REQUEST'),'goal':A},'share-alpha').status_code==200
    v=read(f,row,user=REVIEWERS[0]).json();data={**body(v,'TAKE'),'goal':A};assert post(f,row,data,'specialist-original',user=REVIEWERS[0]).status_code==200
    with f['owner'].connect() as c:c.execute('UPDATE '+('preparation_grants' if capability=='REVIEW_ASSIGNED' else 'capability_grants')+' SET active=false WHERE principal_id=%s AND capability=%s',(REVIEWERS[0],capability))
    before=products(f['owner']);audit_before=products(f['owner'],include_audit=True)['authorization_audit']
    assert read(f,row,user=REVIEWERS[0]).status_code==403;assert read(f,row,'specialist-original',user=REVIEWERS[0]).status_code==403;assert post(f,row,data,'specialist-original',user=REVIEWERS[0]).status_code==403
    assert products(f['owner'])==before
    audit=products(f['owner'],include_audit=True)['authorization_audit'];assert len(audit)==len(audit_before)+3 and all(x['outcome']=='DENIED' and x['principal_id']==REVIEWERS[0] for x in audit)

def test_original_full_page_private_goal_projection_cold_get_and_late_owner_response(template_consumption):
    import json,subprocess,selectors
    from pathlib import Path
    f=template_consumption;row=private_case(f);grants=grant_snapshot(f['owner']);messages=[];summary=None;lost=False;revoked=False
    proc=subprocess.Popen(['node','tests/manual_goal_privacy_actual.js',row['preparation_id'],ENTERPRISES[0],REVIEWERS[0],A,B],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
    try:
        while True:
            assert sel.select(timeout=15),'privacy page bridge timeout'
            line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if msg.get('revoke_specialist'):
                assert grant_snapshot(f['owner'])==grants
                with f['owner'].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='READ'",(REVIEWERS[0],))
                revoked=True;proc.stdin.write(b'{}\n');proc.stdin.flush();continue
            if 'request' not in msg:summary=msg;break
            q=msg['request'];o=q['options'];method=o.get('method','GET');data=json.loads(o['body']) if o.get('body') else None;actor=o['headers']['Authorization'].removeprefix('Bearer SYNTHETIC_');h={'Authorization':'Bearer '+f['tokens'][actor]}
            if key:=o['headers'].get('Idempotency-Key'):h['Idempotency-Key']=key
            r=f['client'].request(method,q['path'],headers=h,json=data);messages.append(dict(method=method,path=q['path'],actor=actor,status=r.status_code,action=data.get('action') if data else None))
            if actor==REVIEWERS[0]:assert B not in r.text,'unrequested target leaked in actual specialist HTTP response'
            assert r.status_code==200 or revoked and r.status_code==403,r.text
            drop=method=='POST' and actor==REVIEWERS[0] and not lost
            if drop:lost=True
            proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json(),**({'lost':True} if drop else {})})+'\n').encode());proc.stdin.flush()
        stderr=proc.stderr.read().decode();assert proc.wait(timeout=15)==0,stderr;assert summary and summary['checks']>=25 and summary['manual_posts']==3;assert lost and revoked
        owner=read(f,row).json();assert [i['goal'] for i in owner['items']]==[A,B];assert owner['items'][0]['state']=='WITHDRAWN' and owner['items'][1]['state']=='NOT_REQUESTED';assert owner['overall_goal_state']=='PARTIAL'
        with f['owner'].connect() as c:assert c.execute('SELECT count(*) AS n FROM runs').fetchone()['n']==1
    finally:
        Path('.runtime/manual-goal-privacy-20261014/actual-chain.json').write_text(json.dumps({'summary':summary,'requests':messages,'lost_specialist_reply_after_commit':lost,'revoked_existing_read':revoked},indent=2)+'\n');sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)

@pytest.mark.parametrize('authority',['EXECUTE','case.create'])
@pytest.mark.parametrize('requested',[False,True])
def test_allowed_actions_follow_current_owner_write_authority_while_reads_remain(template_consumption,authority,requested):
    f=template_consumption;row=private_case(f);v=read(f,row).json()
    if requested:
        assert post(f,row,{**body(v,'REQUEST'),'goal':A},'owner-write-key').status_code==200
        v=read(f,row).json()
    data={**body(v,'WITHDRAW' if requested else 'REQUEST'),'goal':A}
    with f['owner'].connect() as c:
        if authority=='EXECUTE':c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='EXECUTE'",(ENTERPRISES[0],))
        else:c.execute("UPDATE action_grants SET active=false WHERE principal_id=%s AND action='case.create'",(ENTERPRISES[0],))
    before=products(f['owner']);r=read(f,row);assert r.status_code==200,r.text
    assert [x['goal'] for x in r.json()['items']]==[A,B]
    assert all(x['allowed_actions']==[] for x in r.json()['items']),'read incorrectly advertises revoked business write'
    if requested:assert read(f,row,'owner-write-key').json()['status']=='COMMITTED'
    assert post(f,row,data,'revoked-owner-key').status_code==403
    assert products(f['owner'])==before

def replace_plan(f,row):
    path='/api/preparations/'+row['preparation_id'];p=f['client'].get(path,headers=headers(f)).json()['preparation']
    data=dict(expected_preparation_revision=p['revision'],request_text='SYNTHETIC explicit revised request, all goals retained',required_goals=['LOCAL_MATERIAL_PREPARATION',A,B])
    r=f['client'].post(path+'/request-intent',headers=headers(f,key='real-revise-request'),json=data);assert r.status_code==200,r.text
    preview=f['client'].get(path+'/planning-preview',headers=headers(f));assert preview.status_code==200,preview.text
    current=preview.json()['current'];request_revision=r.json()['request_intent']['revision'];plan=f['client'].get(path+'/service-case-plan',headers=headers(f)).json()
    data=dict(expected_preparation_revision=current['preparation_revision'],expected_request_revision=request_revision,expected_source_sha256=current['source_sha256'],expected_plan_revision=plan['revision'],required_goals=['LOCAL_MATERIAL_PREPARATION',A,B],reason='SYNTHETIC explicit replacement preserves all original goals',partial_adoption=True)
    r=f['client'].post(path+'/service-case-plan',headers=headers(f,key='real-replace-plan'),json=data);assert r.status_code==201,r.text;return r.json()

def test_real_original_api_plan_replacement_old_key_recovery_and_new_ledger_isolation(template_consumption):
    from copy import deepcopy
    f=template_consumption;row=private_case(f);v=read(f,row).json();request={**body(v,'REQUEST'),'goal':A};first=post(f,row,request,'old-owner-request');assert first.status_code==200
    v=assert_private(read(f,row,user=REVIEWERS[0]),[A]);take={**body(v,'TAKE'),'goal':A};old=post(f,row,take,'old-specialist-key',user=REVIEWERS[0]);assert old.status_code==200
    with f['owner'].connect() as c:prior=deepcopy(c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan'])
    replaced=replace_plan(f,row);assert replaced['plan_id']!=prior['id']
    assert prior['history']==[];archived_prior={k:v for k,v in prior.items() if k!='history'}  # Original API flattens this empty history container.
    before=products(f['owner']);assert_private(read(f,row,user=REVIEWERS[0]))
    restored=read(f,row,'old-specialist-key',user=REVIEWERS[0]);assert_private(restored,historical_shared=[A]);assert restored.json()['status']=='COMMITTED' and restored.json()['original_plan_id']==prior['id'] and restored.json()['event']==old.json()['event']
    replay=post(f,row,take,'old-specialist-key',user=REVIEWERS[0]);assert_private(replay,historical_shared=[A]);assert replay.json()['event']==old.json()['event']
    assert post(f,row,{**take,'reason':'SYNTHETIC changed original reason'},'old-specialist-key',user=REVIEWERS[0]).status_code==409
    assert products(f['owner'])==before
    with f['owner'].connect() as c:
        current=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan'];assert current['history'][-1]==archived_prior and current.get('manual_goal_requests',[])==[]
    v=read(f,row).json();assert post(f,row,{**body(v,'REQUEST'),'goal':B},'new-beta-request').status_code==200
    assert_private(read(f,row,user=REVIEWERS[0]),[B]);restored=read(f,row,'old-specialist-key',user=REVIEWERS[0]);assert_private(restored,[B],historical_shared=[A]);assert restored.json()['event']==old.json()['event']
    with f['owner'].connect() as c:
        current=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan'];assert current['history'][-1]==archived_prior and len(current['manual_goal_requests'])==1
        c.execute("UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability='REVIEW_ASSIGNED'",(REVIEWERS[0],))
    before=products(f['owner']);assert read(f,row,'old-specialist-key',user=REVIEWERS[0]).status_code==403;assert post(f,row,take,'old-specialist-key',user=REVIEWERS[0]).status_code==403;assert products(f['owner'])==before

def test_actual_full_page_replaced_plan_old_handle_and_revoked_write_actions(template_consumption):
    import json,subprocess,selectors
    from uuid import uuid4
    from pathlib import Path
    f=template_consumption;row=private_case(f);v=read(f,row).json();assert post(f,row,{**body(v,'REQUEST'),'goal':A},'history-request').status_code==200
    v=read(f,row,user=REVIEWERS[0]).json();take={**body(v,'TAKE'),'goal':A};key=str(uuid4());old=post(f,row,take,key,user=REVIEWERS[0]);assert old.status_code==200
    replace_plan(f,row)
    with f['owner'].connect() as c:c.execute("UPDATE action_grants SET active=false WHERE principal_id=%s AND action='case.create'",(ENTERPRISES[0],))
    before=products(f['owner']);messages=[];summary=None;h=dict(actor=REVIEWERS[0],id=row['preparation_id'],key=key)
    proc=subprocess.Popen(['node','tests/manual_goal_history_actual.js',row['preparation_id'],ENTERPRISES[0],REVIEWERS[0],json.dumps(h)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
    try:
        while True:
            assert sel.select(timeout=15),'history page bridge timeout';line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if msg.get('revoke_history_reader'):
                assert products(f['owner'])==before
                with f['owner'].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability='REVIEW_ASSIGNED'",(REVIEWERS[0],))
                proc.stdin.write(b'{}\n');proc.stdin.flush();continue
            if 'request' not in msg:summary=msg;break
            q=msg['request'];o=q['options'];assert o.get('method','GET')=='GET';actor=o['headers']['Authorization'].removeprefix('Bearer SYNTHETIC_');r=f['client'].get(q['path'],headers={'Authorization':'Bearer '+f['tokens'][actor]});messages.append(dict(path=q['path'],actor=actor,status=r.status_code))
            if actor==REVIEWERS[0]:assert B not in r.text
            assert r.status_code in (200,403),r.text;proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json()})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['checks']>=15 and summary['posts']==0;assert products(f['owner'])==before
    finally:
        Path('.runtime/manual-goal-privacy-20261014/history-page-chain.json').write_text(json.dumps({'summary':summary,'requests':messages,'old_reply_discarded_seeded_opaque_handle':True,'all_page_calls_get':True},indent=2)+'\n');sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
