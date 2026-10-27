"""Actual owned PG/API template partial adoption and immutable key reads."""
from copy import deepcopy
from uuid import UUID
import pytest
from parkweave import service_case_steps
from test_template_consumer import template_consumption,headers,body,products
from test_template_consumer_planning import ready,preview,adoption,post,edit
from template_candidate_support import ENTERPRISES,grant_snapshot

EXTERNAL='SYNTHETIC_EXTERNAL_AUTHORITY_APPROVAL'

def partial(f,**extra):
    data=body(f);data['required_goals']=['LOCAL_MATERIAL_PREPARATION',EXTERNAL];data.update(extra)
    return ready(f,data)

def recover(f,row,key,index=0):
    return f['client'].get('/api/template-consumer/instances/'+row['instance_id']+'/planning-recovery',headers=headers(f,index,key))

def journal(f):
    with f['repository'].connect() as c:return {t:[dict(x) for x in c.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in ['consumer_instances','consumer_requests','consumer_stages']}

def test_unknown_partial_confirmation_must_not_call_original_adopt_again(template_consumption,monkeypatch):
    f=template_consumption;row=partial(f);v=preview(f,row).json();data={**adoption(v),'partial_adoption':True};original=service_case_steps.adopt;calls=[]
    def lost(*a,**kw):
        calls.append(a[3]);result=original(*a,**kw)
        if len(calls)==1:raise RuntimeError('SYNTHETIC committed adoption reply lost')
        return result
    monkeypatch.setattr(service_case_steps,'adopt',lost)
    assert post(f,row,'adopt',data,'lost-partial').status_code==503
    reply=post(f,row,'adopt',data,'lost-partial')
    assert reply.status_code==409,reply.text
    assert len(calls)==1

def test_original_consumer_key_get_recovers_exact_partial_body_without_any_writes(template_consumption,monkeypatch):
    f=template_consumption;row=partial(f);v=preview(f,row).json();data={**adoption(v),'partial_adoption':True};original=service_case_steps.adopt
    def lost(*a,**kw):original(*a,**kw);raise RuntimeError('SYNTHETIC exact partial receipt lost')
    monkeypatch.setattr(service_case_steps,'adopt',lost);assert post(f,row,'adopt',data,'read-original-partial').status_code==503
    before=products(f['owner'],include_audit=True);saved=journal(f)
    def forbidden(*a,**kw):raise AssertionError('GET recovery must not call ADOPT')
    monkeypatch.setattr(service_case_steps,'adopt',forbidden)
    r=recover(f,row,'read-original-partial');assert r.status_code==200,r.text
    assert r.json()['status']=='COMMITTED' and r.json()['original_request']['partial_adoption'] is True
    assert r.json()['consumer_request_key']=='read-original-partial'
    assert r.json()['journal_read_only'] and r.json()['product_read_only'] and not r.json()['automatically_replayed']
    assert products(f['owner'],include_audit=True)==before and journal(f)==saved

def committed(f,key='partial-confirm'):
    row=partial(f);v=preview(f,row).json();data={**adoption(v),'partial_adoption':True}
    r=post(f,row,'adopt',data,key);assert r.status_code==200,r.text
    return row,v,data,r.json()

@pytest.mark.parametrize('capability',['READ','PREPARE','EXECUTE'])
def test_recovery_rechecks_current_permission_without_journal_or_product_write(template_consumption,capability):
    f=template_consumption;row,_,_,_=committed(f)
    with f['owner'].connect() as c:
        table='preparation_grants' if capability=='PREPARE' else 'capability_grants'
        c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',(ENTERPRISES[0],capability))
    before=products(f['owner']);saved=journal(f)
    assert recover(f,row,'partial-confirm').status_code==403
    assert products(f['owner'])==before and journal(f)==saved

def test_recovery_cross_owner_key_scope_and_release_currentness(template_consumption):
    from test_template_candidate import advance_source_head
    f=template_consumption;row,_,_,_=committed(f);before=products(f['owner']);saved=journal(f)
    assert recover(f,row,'partial-confirm',1).status_code==403
    assert recover(f,row,'other-key').status_code==409
    assert products(f['owner'])==before and journal(f)==saved
    advance_source_head(f['engine']);assert recover(f,row,'partial-confirm').status_code==403
    assert products(f['owner'])==before and journal(f)==saved

@pytest.mark.parametrize('corruption',['body','sha','key','fp','run'])
def test_journal_prevents_body_scope_mutation_and_recovery_rejects_changed_run(template_consumption,corruption):
    import json
    f=template_consumption;row,_,_,_=committed(f)
    before=products(f['owner'],include_audit=True);saved=journal(f)
    if corruption!='run':
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError,match='immutable consumer'):
            with f['repository'].connect(write=True) as c:
                if corruption=='fp':c.execute("UPDATE consumer_requests SET fp=? WHERE key='partial-confirm'",('0'*64,))
                else:
                    column={'body':'body','sha':'body_sha256','key':'request_key'}[corruption]
                    c.execute('UPDATE consumer_stages SET '+column+"=? WHERE instance_id=? AND name LIKE 'CONFIRM_PLAN_%'",('{}' if corruption=='body' else '0'*64,row['instance_id']))
        assert journal(f)==saved
        r=recover(f,row,'partial-confirm');assert r.status_code==200 and r.json()['status']=='COMMITTED'
    else:
        with f['repository'].connect(write=True) as c:
            c.execute("UPDATE consumer_stages SET result=? WHERE instance_id=? AND name='CREATE_RUN'",(json.dumps({'run_id':'00000000-0000-4000-8000-000000000001'}),row['instance_id']))
        saved=journal(f);assert recover(f,row,'partial-confirm').status_code==409
    assert products(f['owner'],include_audit=True)==before and journal(f)==saved

def test_unknown_before_product_send_stays_unobserved_and_does_not_resend(template_consumption,monkeypatch):
    f=template_consumption;row=partial(f);v=preview(f,row).json();data={**adoption(v),'partial_adoption':True};calls=[]
    def unavailable(*a,**kw):calls.append(1);raise RuntimeError('SYNTHETIC before send interrupted')
    monkeypatch.setattr(service_case_steps,'adopt',unavailable)
    assert post(f,row,'adopt',data,'before-send').status_code==503
    before=products(f['owner'],include_audit=True);saved=journal(f)
    r=recover(f,row,'before-send');assert r.status_code==200,r.text
    assert r.json()['status']=='NOT_OBSERVED' and r.json()['instance']['plan_id'] is None
    assert post(f,row,'adopt',data,'before-send').status_code==409
    assert post(f,row,'adopt',data,'replacement').status_code==409
    assert calls==[1] and products(f['owner'],include_audit=True)==before and journal(f)==saved

def test_cold_engine_recovers_committed_original_key_without_repair(template_consumption,monkeypatch):
    from fastapi.testclient import TestClient
    from parkweave.template_consumer import ConsumerRepository,TemplateConsumer
    from parkweave.template_isolated_app import create_isolated_template_app
    f=template_consumption;row=partial(f);v=preview(f,row).json();original=service_case_steps.adopt
    def lost(*a,**kw):original(*a,**kw);raise RuntimeError('SYNTHETIC cold committed response lost')
    monkeypatch.setattr(service_case_steps,'adopt',lost)
    assert post(f,row,'adopt',{**adoption(v),'partial_adoption':True},'cold-original').status_code==503
    before=products(f['owner'],include_audit=True);saved=journal(f)
    consumer=TemplateConsumer(f['store'],f['engine'],f['config'],ConsumerRepository(f['repository'].path))
    with TestClient(create_isolated_template_app(f['store'],f['engine'],consumer)) as client:
        r=client.get('/api/template-consumer/instances/'+row['instance_id']+'/planning-recovery',headers=headers(f,key='cold-original'))
        assert r.status_code==200 and r.json()['status']=='COMMITTED'
        assert r.json()['instance']['service_case_plan']['overall_goal_state']=='PARTIAL'
    assert products(f['owner'],include_audit=True)==before and journal(f)==saved

def test_partial_full_goal_set_idempotency_and_unadopted_only(template_consumption):
    f=template_consumption;authority=grant_snapshot(f['owner']);row,v,data,result=committed(f)
    plan=result['service_case_plan'];assert plan['overall_goal_state']=='PARTIAL' and not plan['case_goal_completed']
    assert plan['required_goals']==['LOCAL_MATERIAL_PREPARATION',EXTERNAL] and [s['adapter_id'] for s in plan['steps']]==['P1']
    before=products(f['owner']);assert post(f,row,'adopt',data,'partial-confirm').status_code==200
    changed={**data,'reason':'SYNTHETIC different confirmation'};assert post(f,row,'adopt',changed,'partial-confirm').status_code==409
    assert post(f,row,'adopt',data,'another-confirm').status_code==409
    assert post(f,row,'planning',edit(v,planning_constraints={}),'overwrite-edit').status_code==409
    assert products(f['owner'])==before and grant_snapshot(f['owner'])==authority

@pytest.mark.parametrize('historical',[False,True])
def test_global_unknown_cannot_be_cleared_or_renamed_into_independent_goal(template_consumption,historical):
    f=template_consumption;row=partial(f,planning_constraints={'additional_requirements':['SYNTHETIC unknown region deadline']})
    v=preview(f,row).json()
    if historical:
        r=post(f,row,'planning',edit(v,planning_constraints={}),'clear-global');assert r.status_code==200,r.text
        v=preview(f,row).json()
    assert v['current']['state']=='PARTIAL' and not v['current']['partial_offer']['can_adopt']
    before=products(f['owner']);r=post(f,row,'adopt',{**adoption(v),'partial_adoption':True},'renamed-global')
    assert r.status_code==409 and products(f['owner'])==before

def test_actual_template_partial_lost_reply_cold_get_original_handling_and_worklist(template_consumption):
    import json,selectors,subprocess
    from pathlib import Path
    from test_template_consumer import finish
    from template_candidate_support import REVIEWERS
    f=template_consumption;authority=grant_snapshot(f['owner']);requests=[];summary=None;lost=0
    proc=subprocess.Popen(['node','tests/template_partial_actual.js','template_partial_actual',ENTERPRISES[0]],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
    out=Path('.runtime/template-partial-20261014');out.mkdir(parents=True,exist_ok=True)
    try:
        while True:
            assert selector.select(timeout=20),'Original template partial bridge stalled'
            line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if 'prepare_review' in msg:
                id=msg['prepare_review']['preparation_id'];path='/api/preparations/'+id
                for action,principal in [('REVIEW',REVIEWERS[0]),('CONFIRM',ENTERPRISES[0])]:
                    h={'Authorization':'Bearer '+f['tokens'][principal]};v=f['client'].get(path,headers=h).json()['preparation']
                    r=f['client'].post(path+'/commands',headers={**h,'Idempotency-Key':'original-'+action},json={'action':action,'expected_revision':v['revision'],'reason':'SYNTHETIC original actual '+action})
                    requests.append({'method':'POST','path':path+'/commands','status':r.status_code,'action':action,'entry':'ORIGINAL_ACTUAL_API'});assert r.status_code==200,r.text
                proc.stdin.write(b'{"reviewed":true}\n');proc.stdin.flush();continue
            if 'request' not in msg:summary=msg;break
            q=msg['request'];options=q['options'];method=options.get('method','GET');data=json.loads(options['body']) if options.get('body') else None;h=headers(f,key=options.get('headers',{}).get('Idempotency-Key'))
            before=products(f['owner'],include_audit=True) if q['path'].endswith('/planning-recovery') else None;saved=journal(f) if before is not None else None
            r=f['client'].request(method,q['path'],headers=h,json=data);requests.append({'method':method,'path':q['path'],'status':r.status_code,'key':h.get('Idempotency-Key'),'body':data,'entry':'ORIGINAL_HTML'})
            assert r.status_code<400,(method,q['path'],r.status_code,r.text)
            if before is not None:assert products(f['owner'],include_audit=True)==before and journal(f)==saved
            if method=='POST' and q['path']=='/api/template-consumer/instances':finish(f)
            drop=method=='POST' and q['path'].endswith('/adopt')
            if drop:lost+=1
            proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json(),'lost':drop})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=20)==0,proc.stderr.read().decode()
        assert summary and summary['checks']>=30 and summary['adopts']==1 and lost==1
        assert grant_snapshot(f['owner'])==authority
        with f['owner'].connect() as c:
            p=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(summary['preparation'],)).fetchone()['service_case_plan']
            assert p['partial_adoption'] and p['required_goals']==['LOCAL_MATERIAL_PREPARATION',EXTERNAL]
            assert [s['adapter_id'] for s in p['steps']]==['P1'] and p['steps'][0]['coordination_state']=='VERIFIED' and p['steps'][0]['verified_sha256']
            assert c.execute('SELECT count(*) AS n FROM service_dispatches').fetchone()['n']==0
            assert c.execute('SELECT count(*) AS n FROM service_receipt_steps').fetchone()['n']==0
            assert c.execute('SELECT count(*) AS n FROM case_local_lifecycles').fetchone()['n']==0
    finally:
        (out/'actual-chain.json').write_text(json.dumps({'summary':summary,'requests':requests,'lost_responses':lost,'permission_snapshot_unchanged':grant_snapshot(f['owner'])==authority},indent=2)+'\n')
        selector.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
