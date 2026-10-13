"""Explicit template consumer planning; original APIs on owned PostgreSQL."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID
import pytest
from parkweave import preparation,service_case_steps
from test_template_consumer import template_consumption,headers,body,consume,resume,finish,products
from template_candidate_support import ENTERPRISES,grant_snapshot
from test_template_candidate import advance_source_head


def ready(f,data=None):
    row=consume(f,data=data).json();finish(f);r=resume(f,row);assert r.status_code==200,r.text
    row=r.json();assert row['state']=='PLAN_CONFIRMATION_REQUIRED' and row['plan_id'] is None
    assert not any(s['name']=='ADOPT_PLAN' for s in row['stages'])
    return row


def preview(f,row,index=0):
    return f['client'].get(f"/api/template-consumer/instances/{row['instance_id']}/planning",headers=headers(f,index))


def adoption(v):
    return dict(expected_preparation_revision=v['current']['preparation_revision'],expected_request_revision=v['request_intent']['revision'],expected_source_sha256=v['current']['source_sha256'],expected_plan_revision=0,required_goals=v['request_intent']['required_goals'],reason='SYNTHETIC owner explicitly adopts reviewed current source')


def post(f,row,suffix,data,key,index=0):
    return f['client'].post(f"/api/template-consumer/instances/{row['instance_id']}/{suffix}",headers=headers(f,index,key),json=data)


def edit(v,**extra):
    return dict(expected_preparation_revision=v['current']['preparation_revision'],request_text=v['request_intent']['current_request'],required_goals=v['request_intent']['required_goals'],**extra)


def test_resume_and_get_never_adopt_compatible_constraint_requires_exact_explicit_confirmation(template_consumption):
    f=template_consumption;authority=grant_snapshot(f['owner']);data=body(f);data['planning_constraints']={'excluded_roles':['service_executor']};row=ready(f,data)
    before=products(f['owner'],include_audit=True);v=preview(f,row).json();assert v['current']['state']=='COVERED_PREVIEW_ONLY' and len(v['current']['steps'])==1
    assert v['current']['constraint_evaluation']['state']=='COMPATIBLE' and not v['automatic_adoption'] and not v['model_inference']
    assert resume(f,row,key='second-resume').json()['plan_id'] is None
    assert products(f['owner'],include_audit=True)==before
    reply=post(f,row,'adopt',adoption(v),'explicit-adopt');assert reply.status_code==200,reply.text
    assert reply.json()['state']=='PLAN_ADOPTED'
    stable=products(f['owner']);assert post(f,row,'adopt',adoption(v),'explicit-adopt').json()['plan_id']==reply.json()['plan_id'];assert products(f['owner'])==stable
    changed=adoption(v);changed['reason']='Different confirmation';assert post(f,row,'adopt',changed,'explicit-adopt').status_code==409
    assert grant_snapshot(f['owner'])==authority


@pytest.mark.parametrize('invalid',[{'required_goals':['']},{'required_goals':['x'*161]},{'planning_constraints':None},{'required_goals':['g'+str(i) for i in range(8)],'planning_constraints':{'additional_requirements':['outside']}}])
def test_invalid_declarations_rejected_before_any_run(template_consumption,invalid):
    f=template_consumption;before=products(f['owner']);data=body(f);data.update(invalid);assert consume(f,data=data).status_code==422;assert products(f['owner'])==before


@pytest.mark.parametrize('kind',['conflict','unsupported'])
def test_template_and_saved_goals_retained_conflict_and_unsupported_cannot_adopt(template_consumption,kind):
    f=template_consumption;data=body(f);data['required_goals']=['LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RECORD_RECHECK'] if kind=='conflict' else ['LOCAL_MATERIAL_PREPARATION'];data['planning_constraints']={'excluded_roles':['service_executor']} if kind=='conflict' else {'additional_requirements':['SYNTHETIC outside registered contract']};row=ready(f,data);v=preview(f,row).json()
    assert v['current']['state']==('CONSTRAINT_BLOCKED' if kind=='conflict' else 'PARTIAL')
    assert len(v['current']['steps'])==(5 if kind=='conflict' else 1)
    before=products(f['owner']);assert post(f,row,'adopt',adoption(v),'blocked-adopt').status_code==409;assert products(f['owner'])==before
    reduced=edit(v);reduced['required_goals']=[];assert post(f,row,'planning',reduced,'remove-goals').status_code==409
    reduced=edit(v,planning_constraints={});reduced['required_goals']=['LOCAL_MATERIAL_PREPARATION'];assert post(f,row,'planning',reduced,'clear-and-reduce').status_code==409
    assert products(f['owner'])==before


def test_return_edit_changes_source_old_confirmation_rejected_new_explicit_confirmation_succeeds(template_consumption):
    f=template_consumption;row=ready(f);old=preview(f,row).json();request=edit(old,planning_constraints={'excluded_roles':['service_executor']});request['request_text']='Current edited explicit need';r=post(f,row,'planning',request,'edit-source');assert r.status_code==200,r.text
    v=preview(f,row).json();assert v['current']['source_sha256']!=old['current']['source_sha256'];assert v['request_intent']['current_request']==request['request_text'];assert post(f,row,'adopt',adoption(old),'stale-confirm').status_code==409
    good=post(f,row,'adopt',adoption(v),'current-confirm');assert good.status_code==200,good.text
    snapshot=products(f['owner']);assert post(f,row,'planning',edit(v),'edit-after-adopt').status_code==409;assert products(f['owner'])==snapshot
    assert post(f,row,'planning',request,'edit-source').status_code==200;assert products(f['owner'])==snapshot


def test_original_material_source_advance_rejects_confirm_without_plan_write(template_consumption):
    f=template_consumption;row=ready(f);v=preview(f,row).json();r=f['client'].post(f"/api/preparations/{row['preparation_id']}/commands",headers=headers(f,key='peer-material'),json={'action':'ADD_EVIDENCE','expected_revision':v['current']['preparation_revision'],'slot':'need_summary','text':'SYNTHETIC current source advanced','source_kind':'USER_STATEMENT','source_label':'SYNTHETIC peer source'});assert r.status_code==200,r.text
    before=products(f['owner']);assert post(f,row,'adopt',adoption(v),'old-material-confirm').status_code==409;assert products(f['owner'])==before
    assert preview(f,row).json()['current']['source_sha256']!=v['current']['source_sha256']


@pytest.mark.parametrize('capability',['READ','PREPARE','EXECUTE'])
def test_current_permission_denial_precedes_confirmation_replay_and_get(template_consumption,capability):
    f=template_consumption;row=ready(f);v=preview(f,row).json();assert post(f,row,'adopt',adoption(v),'before-revoke').status_code==200
    with f['owner'].connect() as c:
        table='preparation_grants' if capability=='PREPARE' else 'capability_grants';c.execute(f'UPDATE {table} SET active=false WHERE principal_id=%s AND capability=%s',(ENTERPRISES[0],capability))
    before=products(f['owner']);assert preview(f,row).status_code==403;assert post(f,row,'adopt',adoption(v),'before-revoke').status_code==403;assert products(f['owner'])==before


def test_cross_owner_and_release_advance_deny_new_confirmation_keep_history(template_consumption):
    f=template_consumption;row=ready(f);v=preview(f,row).json();before=products(f['owner']);assert preview(f,row,1).status_code==403;assert post(f,row,'adopt',adoption(v),'wrong-owner',1).status_code==403;assert products(f['owner'])==before
    assert post(f,row,'adopt',adoption(v),'historical-confirm').status_code==200;advance_source_head(f['engine']);before=products(f['owner']);assert post(f,row,'adopt',adoption(v),'historical-confirm').status_code==403
    history=f['client'].get(f"/api/template-consumer/instances/{row['instance_id']}",headers=headers(f));assert history.status_code==200 and history.json()['state']=='PLAN_ADOPTED' and not history.json()['release_available'];assert products(f['owner'])==before


def test_unknown_edit_blocks_other_keys_and_recovers_only_immutable_original_body(template_consumption,monkeypatch):
    from parkweave import request_intents
    f=template_consumption;row=ready(f);v=preview(f,row).json();data=edit(v,planning_constraints={});original=request_intents.save
    def lost(*a,**kw):
        original(*a,**kw);raise RuntimeError('Injected original save response lost after commit')
    monkeypatch.setattr(request_intents,'save',lost);assert post(f,row,'planning',data,'lost-edit').status_code==503
    before=products(f['owner']);now=preview(f,row).json();assert post(f,row,'planning',edit(now),'different-edit').status_code==409;assert post(f,row,'adopt',adoption(now),'new-adopt-while-unknown').status_code==409;assert products(f['owner'])==before
    monkeypatch.setattr(request_intents,'save',original);changed=deepcopy(data);changed['request_text']='different';assert post(f,row,'planning',changed,'lost-edit').status_code==409
    assert post(f,row,'planning',data,'lost-edit').status_code==200;assert products(f['owner'])==before


@pytest.mark.parametrize('same_key',[True,False])
def test_concurrent_confirmations_create_one_plan_and_keep_full_target_set(template_consumption,same_key):
    f=template_consumption;row=ready(f);v=preview(f,row).json();data=adoption(v)
    with ThreadPoolExecutor(max_workers=2) as pool:replies=list(pool.map(lambda i:post(f,row,'adopt',data,'parallel' if same_key else 'parallel-'+str(i)),range(2)))
    assert sorted(r.status_code for r in replies)==([200,200] if same_key else [200,409])
    with f['owner'].connect() as c:
        p=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan'];assert p['required_goals']==v['request_intent']['required_goals']


def test_planning_admission_registers_pending_before_original_operation_and_blocks_other_key(template_consumption,monkeypatch):
    from threading import Event
    f=template_consumption;row=ready(f);v=preview(f,row).json();entered=Event();release=Event();original=f['consumer']._perform
    def pause(*args,**kw):
        if args[2].startswith('EDIT_REQUEST_'):
            entered.set();assert release.wait(5),'test pending release not signalled'
        return original(*args,**kw)
    monkeypatch.setattr(f['consumer'],'_perform',pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first=pool.submit(post,f,row,'planning',edit(v,planning_constraints={}),'pending-admission')
        try:
            assert entered.wait(5),'test admission not reached'
            before=products(f['owner']);assert post(f,row,'adopt',adoption(v),'interleaving-confirm').status_code==409;assert products(f['owner'])==before
            with f['repository'].connect() as c:
                pending=c.execute("SELECT * FROM consumer_stages WHERE instance_id=? AND name LIKE 'EDIT_REQUEST_%'",(row['instance_id'],)).fetchall();assert len(pending)==1 and pending[0]['state']=='ADMITTED'
        finally:release.set()
        assert first.result().status_code==200


def test_unknown_committed_confirmation_requires_original_key_recovery_and_no_second_plan(template_consumption,monkeypatch):
    f=template_consumption;row=ready(f);v=preview(f,row).json();data=adoption(v);original=service_case_steps.adopt
    def lost(*a,**kw):
        original(*a,**kw);raise RuntimeError('Injected committed original adoption reply lost')
    monkeypatch.setattr(service_case_steps,'adopt',lost);assert post(f,row,'adopt',data,'lost-confirm').status_code==503
    before=products(f['owner']);current=preview(f,row).json();assert current['plan_id'] is not None
    assert post(f,row,'adopt',data,'new-key-for-unknown').status_code==409;assert post(f,row,'planning',edit(current),'edit-while-unknown').status_code==409;assert products(f['owner'])==before
    monkeypatch.setattr(service_case_steps,'adopt',original);reply=post(f,row,'adopt',data,'lost-confirm');assert reply.status_code==200 and reply.json()['state']=='PLAN_ADOPTED';assert products(f['owner'])==before


def test_legacy_confirmed_adopt_stage_and_omitted_create_fingerprint_remain_compatible(template_consumption):
    from parkweave.store import digest
    from parkweave.template_consumer import canonical
    f=template_consumption;row=ready(f)
    with f['repository'].connect() as c:
        old=c.execute("SELECT fp FROM consumer_requests WHERE actor=? AND key=?",(ENTERPRISES[0],'new-instance')).fetchone();assert old['fp']==digest(canonical(dict(action='CONSUME',**body(f))))
    v=preview(f,row).json();p,database=f['consumer']._auth(f['tokens'][ENTERPRISES[0]]);instance=f['consumer']._instance(p,database,row['instance_id'])
    f['consumer']._perform(f['tokens'][ENTERPRISES[0]],instance,'ADOPT_PLAN',lambda:adoption(v),lambda key,data:service_case_steps.adopt(f['store'],f['tokens'][ENTERPRISES[0]],UUID(row['preparation_id']),key,service_case_steps.Adopt.model_validate(data)))
    before=products(f['owner']);history=f['consumer'].read(f['tokens'][ENTERPRISES[0]],row['instance_id']);assert history['state']=='PLAN_ADOPTED';assert resume(f,row,key='legacy-resume-read').json()['plan_id']==history['plan_id'];assert products(f['owner'])==before



def test_definite_authority_refusal_after_admission_does_not_leave_unknown_lease(template_consumption,monkeypatch):
    from parkweave.store import Denied
    f=template_consumption;row=ready(f);v=preview(f,row).json();original=f['consumer']._perform
    def refuse(*args,**kwargs):
        if args[2].startswith('EDIT_REQUEST_'):raise Denied('Injected definite authority refusal after admission')
        return original(*args,**kwargs)
    monkeypatch.setattr(f['consumer'],'_perform',refuse);before=products(f['owner']);assert post(f,row,'planning',edit(v),'admission-denied').status_code==403;assert products(f['owner'])==before
    with f['repository'].connect() as c:assert not c.execute("SELECT 1 FROM consumer_stages WHERE state IN ('ADMITTED','STARTED','UNKNOWN')").fetchone()
    monkeypatch.setattr(f['consumer'],'_perform',original);assert post(f,row,'adopt',adoption(v),'after-definite-refusal').status_code==200


def test_adoption_between_old_read_and_admission_refuses_new_edit(template_consumption,monkeypatch):
    from threading import Event,local
    f=template_consumption;row=ready(f);v=preview(f,row).json();entered=Event();release=Event();original=f['consumer'].read;caller=local();original_command=f['consumer']._planning_command
    def marked(token,id,key,data,adopt=False):
        caller.pause=key=='old-read-edit'
        try:return original_command(token,id,key,data,adopt=adopt)
        finally:caller.pause=False
    monkeypatch.setattr(f['consumer'],'_planning_command',marked)
    def pause(*args,**kwargs):
        value=original(*args,**kwargs)
        if getattr(caller,'pause',False) and not entered.is_set():entered.set();assert release.wait(5)
        return value
    monkeypatch.setattr(f['consumer'],'read',pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        old=pool.submit(post,f,row,'planning',edit(v,planning_constraints={}),'old-read-edit')
        try:
            assert entered.wait(5);assert post(f,row,'adopt',adoption(v),'adopt-before-admission').status_code==200;before=products(f['owner'])
        finally:release.set()
        assert old.result().status_code==409;assert products(f['owner'])==before


def test_original_outside_adoption_also_blocks_consumer_edit_in_same_parent_transaction(template_consumption):
    f=template_consumption;row=ready(f);v=preview(f,row).json();r=f['client'].post('/api/preparations/'+row['preparation_id']+'/service-case-plan',headers=headers(f,key='original-outside-adopt'),json=adoption(v));assert r.status_code==201,r.text
    before=products(f['owner']);assert post(f,row,'planning',edit(v,planning_constraints={}),'edit-outside-adopted').status_code==409;assert products(f['owner'])==before


def test_retry_authority_refusal_never_terminates_existing_unknown_commit(template_consumption,monkeypatch):
    from parkweave import request_intents
    from parkweave.store import Denied
    f=template_consumption;row=ready(f);v=preview(f,row).json();data=edit(v,planning_constraints={});original_save=request_intents.save
    def lost(*a,**kw):original_save(*a,**kw);raise RuntimeError('Injected committed save unknown')
    monkeypatch.setattr(request_intents,'save',lost);assert post(f,row,'planning',data,'unknown-recheck').status_code==503;before=products(f['owner']);original_perform=f['consumer']._perform
    def refused(*args,**kw):raise Denied('Injected retry recheck refusal before original send')
    monkeypatch.setattr(f['consumer'],'_perform',refused);assert post(f,row,'planning',data,'unknown-recheck').status_code==403
    with f['repository'].connect() as c:assert c.execute("SELECT state FROM consumer_stages WHERE name LIKE 'EDIT_REQUEST_%'").fetchone()['state']=='UNKNOWN'
    monkeypatch.setattr(f['consumer'],'_perform',original_perform);monkeypatch.setattr(request_intents,'save',original_save);assert post(f,row,'planning',data,'unknown-recheck').status_code==200;assert products(f['owner'])==before



def test_unknown_retry_original_send_denial_keeps_pending_original_key(template_consumption,monkeypatch):
    from parkweave import request_intents
    from parkweave.store import Denied
    f=template_consumption;row=ready(f);v=preview(f,row).json();data=edit(v,planning_constraints={});original=request_intents.save
    def lost(*a,**kw):original(*a,**kw);raise RuntimeError('Injected committed save response loss')
    monkeypatch.setattr(request_intents,'save',lost);assert post(f,row,'planning',data,'unknown-send-denial').status_code==503;before=products(f['owner'])
    def refused(*a,**kw):raise Denied('Injected current original send authorization refusal')
    monkeypatch.setattr(request_intents,'save',refused);assert post(f,row,'planning',data,'unknown-send-denial').status_code==403
    with f['repository'].connect() as c:assert c.execute("SELECT state FROM consumer_stages WHERE name LIKE 'EDIT_REQUEST_%'").fetchone()['state']=='UNKNOWN'
    assert post(f,row,'adopt',adoption(preview(f,row).json()),'different-after-send-denial').status_code==409
    monkeypatch.setattr(request_intents,'save',original);assert post(f,row,'planning',data,'unknown-send-denial').status_code==200;assert products(f['owner'])==before


def test_incomplete_original_material_pipeline_cannot_preview_or_confirm(template_consumption,monkeypatch):
    from threading import Event
    f=template_consumption;row=consume(f).json();finish(f);entered=Event();release=Event();original=f['consumer']._perform
    def pause(*args,**kwargs):
        if args[2]=='ADD_need_summary':entered.set();assert release.wait(5)
        return original(*args,**kwargs)
    monkeypatch.setattr(f['consumer'],'_perform',pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        preparing=pool.submit(resume,f,row)
        try:
            assert entered.wait(5);current=f['client'].get('/api/template-consumer/instances/'+row['instance_id'],headers=headers(f)).json();assert preview(f,current).status_code==409
            sc=f['client'].get('/api/preparations/'+current['preparation_id']+'/service-case-plan',headers=headers(f)).json();v={'current':sc['current_preview'],'request_intent':{'revision':sc['request_revision'],'required_goals':sc['current_preview']['required_goals']}};before=products(f['owner']);assert post(f,current,'adopt',adoption(v),'confirm-incomplete-materials').status_code==409;assert products(f['owner'])==before
        finally:release.set()
        assert preparing.result().json()['state']=='PLAN_CONFIRMATION_REQUIRED'
