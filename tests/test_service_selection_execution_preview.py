"""AT14 development simulation: trusted B mapping, actual rollback-only P1–P5.

The public namespace is an owned SYNTHETIC business control, not production.
Only the compact model response is an offline HTTP fixture.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import json
import httpx
import pytest

from parkweave import bounded_planning as bp, service_selection_candidates as sc
from parkweave import lifecycle_execution_preview as p5, isolated_execution_preview as ep
from parkweave import isolated_local_execution as local, case_lifecycle as lc
from parkweave import resource_combinations as rc, resource_holds as rh
from parkweave.isolated_run_access import IsolatedRunAccessBridge
from parkweave.service_selection_planner import OfflineSelectionPlanner
from test_service_selection_full_chain import selection_full_chain, GOALS, ok
from test_service_capability_catalog_actual import capability_catalog
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, create, command, headers
from test_request_intents import save
from test_isolated_execution_preview import snapshot
from service_release_acceptance_support import authority_snapshot, case_history


@pytest.fixture
def mapped_preview(selection_full_chain, tmp_path):
    a=selection_full_chain;f=a['f'];store,owner,tokens,api=f
    store._isolated_service_capability_catalog=a['catalog']
    # A remains a distinct original business control. No application publication.
    control,_,_=create(f)
    p,_,_=create(f,user='fixture-c',goal='SYNTHETIC AT14 B new six-goal preview')
    p={**p,'revision':ok(save(f,p,goals=GOALS,user='fixture-c'))['revision']}
    for slot in ('need_summary','material_outline'):
        p=ok(command(f,p,'ADD_EVIDENCE',user='fixture-c',slot=slot,
            text='SYNTHETIC AT14 NEW B '+slot,source_kind='USER_STATEMENT',source_label='SYNTHETIC B owner input'))
    p=ok(command(f,p,'REVIEW',user='prep-specialist-fixture-c',reason='SYNTHETIC B material review'))
    p=ok(command(f,p,'CONFIRM',user='fixture-c',reason='SYNTHETIC B explicit material confirmation'))
    bridge=IsolatedRunAccessBridge(owner,owner._case_fact_fixture_receipt,
        tmp_path/'b-preview.run-access.candidate.sqlite3',approver_ids={'prep-specialist-fixture-c'},
        enabled_for_isolated_tests=True,clock=lambda:datetime.now(timezone.utc))
    bridge.attach_store(store)
    now=bridge.clock();validity=dict(valid_from=now.isoformat(),valid_until=(now+timedelta(minutes=10)).isoformat(),timezone='UTC')
    for action,user in [('REQUEST','fixture-c'),('APPROVE','prep-specialist-fixture-c')]:
        view=bridge.read(tokens[user],UUID(p['run_id']))
        body=dict(action=action,expected_revision=view['revision'],expected_run_revision=view['run_revision'],
            expected_authority_sha256=view['authority_sha256'],reason='SYNTHETIC owned B fixture '+action)
        body.update(dict(target_id='executor-c',target_role='service_executor',capability='READ',requested_validity=validity) if action=='REQUEST' else dict(approved_validity=validity))
        bridge.command(tokens[user],UUID(p['run_id']),uuid4().hex,body)
    local.IsolatedLocalExecutor(bridge,enabled_for_isolated_tests=True).attach_store(store)
    calls=[]
    def model(request):
        prompt=json.loads(json.loads(request.content)['messages'][-1]['content']);calls.append(prompt)
        value=dict(schema_version=1,binding=prompt['binding'],selections=[s['ref'] for s in prompt['available_services']])
        return httpx.Response(200,json=dict(id='synthetic-at14',model='intern-s2',usage=dict(prompt_tokens=2,completion_tokens=3,total_tokens=5),choices=[dict(index=0,finish_reason='stop',message=dict(role='assistant',content=json.dumps(value)))]))
    planner=OfflineSelectionPlanner(transport=httpx.MockTransport(model))
    with a['catalog'].connection() as c:
        actor,parent=bp._context(store,c,tokens['fixture-c'],UUID(p['preparation_id']))
        current=sc.current(store,c,actor,parent,a['catalog'])
    candidate=sc.generate(store,tokens['fixture-c'],UUID(p['preparation_id']),uuid4().hex,
        sc.Capture(expected_preparation_revision=p['revision'],expected_source_sha256=current['source_sha256'],expected_capability_catalog_sha256=current['capability_catalog_sha256']),catalog=a['catalog'],planner=planner)
    assert candidate['can_adopt'] and len(calls)==1
    response=api.post('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(tokens,'fixture-c',uuid4().hex),json=dict(
        expected_preparation_revision=p['revision'],expected_request_revision=current['request_revision'],expected_plan_revision=0,
        expected_source_sha256=current['source_sha256'],required_goals=GOALS,reason='SYNTHETIC AT14 explicit trusted B adoption',
        candidate_id=candidate['candidate_id'],expected_candidate_sha256=candidate['candidate_sha256'],expected_verification_sha256=candidate['verification_sha256']))
    ok(response,201)
    engine=p5.LifecycleExecutionPreview(store,(tmp_path/'b-isolated-preview').resolve(),enabled_for_synthetic_preview=True)
    engine.attach_store(store)
    return dict(a=a,f=f,parent=p,control=control,engine=engine,bridge=bridge,calls=calls)


def read(a,key=None,user='fixture-c'):
    f=a['f'];return f[3].get('/api/preparations/'+a['parent']['preparation_id']+'/lifecycle-execution-preview'+('/recovery/'+key if key else ''),headers=headers(f[2],user))


def audit_rows(f):
    with f[1].connect() as c:
        return c.execute('SELECT * FROM authorization_audit ORDER BY id').fetchall()


def only_denial_audit_appends(f,before,principal_id):
    previous={r['id']:r for r in before};current=audit_rows(f)
    assert all(previous[id]==next(r for r in current if r['id']==id) for id in previous)
    added=[r for r in current if r['id'] not in previous]
    assert all(r['principal_id']==principal_id and r['category']=='API_AUTHORIZATION' and r['outcome']=='DENIED' for r in added)


def body(a):
    value=ok(read(a));return dict(expected_preparation_revision=value['preparation_revision'],expected_request_revision=value['request_revision'],expected_source_sha256=value['current_source_sha256'],review_decision='ACKNOWLEDGE',lifecycle_sequence='REVALIDATE_CLOSE_REOPEN')


def execute(a,data=None,key=None,user='fixture-c'):
    f=a['f'];return f[3].post('/api/preparations/'+a['parent']['preparation_id']+'/lifecycle-execution-preview',headers=headers(f[2],user,key or uuid4().hex),json=data or body(a))


def test_second_park_v4_actual_preview_writes_preserve_all_public_business(mapped_preview,monkeypatch):
    a=mapped_preview;f=a['f'];before=snapshot(f);audit_before=audit_rows(f);authority=authority_snapshot(f[1]);control=case_history(f[1],a['control']['preparation_id']);calls=[];connections=[]
    original=lc.command
    def observed(store,*args,**kwargs):
        raw=store.connection._raw;connections.append(raw)
        assert raw.execute('SHOW search_path').fetchone()['search_path']=='pg_temp'
        assert {r['relname'] for r in raw.execute("SELECT relname FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'")}==set(p5.TABLES)
        assert raw.execute('SELECT count(*) n FROM synthetic_resource_holds').fetchone()['n']==2
        assert raw.execute('SELECT count(*) n FROM service_step_receipts').fetchone()['n']==1
        calls.append(args[-1].action)
        return original(store,*args,**kwargs)
    monkeypatch.setattr(lc,'command',observed)
    key=uuid4().hex;result=ok(execute(a,key=key),201)['result'];art=result['artifact']
    assert result['state']=='SUCCEEDED' and result['required_goals']==GOALS and result['not_previewed']==[]
    assert calls==['REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN'] and all(c.closed for c in connections)
    assert {r['source_id'] for r in art['p2_resource_mapping']}==set(a['a']['b_resources'])
    assert not set(a['a']['b_resources']) & {h['resource_id'] for h in art['holds']}
    assert all(p.startswith('preview-') for p in [art['p1']['owner_id'],art['p1']['reviewer_id'],art['executor_id']])
    assert art['roles']=='SIMULATED_ROLES_ONLY' and art['namespace']=='PREVIEW_EXECUTION'
    assert result['formal_writes']==0 and not result['new_grants'] and not result['case_goal_completed']
    assert art['lifecycle_final']['local_record_state']=='REOPENED'
    assert snapshot(f)==before and audit_rows(f)==audit_before and authority_snapshot(f[1])==authority and case_history(f[1],a['control']['preparation_id'])==control
    assert len(before)==45 and len(a['calls'])==1
    with f[1].connect() as c:
        assert c.execute("SELECT count(*) n FROM pg_tables WHERE schemaname='public'").fetchone()['n']==46
    # A discarded client reply is recovered solely by the same original key GET.
    monkeypatch.setattr(a['engine'],'_run_artifact',lambda *args:pytest.fail('GET replayed preview'))
    previous=a['engine'].path.read_bytes()
    recovered=ok(read(a,key));assert recovered['status']=='COMMITTED' and recovered['result']==result and recovered['automatically_replayed'] is False
    assert a['engine'].path.read_bytes()==previous and snapshot(f)==before


@pytest.mark.parametrize('user',['fixture-a','fixture-b','executor-c','prep-specialist-fixture-c'])
def test_mapped_preview_cross_identity_denied_no_isolated_or_business_write(mapped_preview,user):
    a=mapped_preview;data=body(a);before=snapshot(a['f']);audit_before=audit_rows(a['f']);saved=a['engine'].path.read_bytes()
    assert read(a,user=user).status_code==403
    assert execute(a,data,user=user).status_code==403
    assert snapshot(a['f'])==before and a['engine'].path.read_bytes()==saved
    only_denial_audit_appends(a['f'],audit_before,user)


@pytest.mark.parametrize('change',['READ','EXECUTE','PREPARE','RESOURCE_HOLD','INSTANCE_WITHDRAWN','REVIEWER_READ','EXECUTOR_READ','ASSIGNMENT'])
def test_current_revocation_blocks_new_preview_and_same_key_replay(mapped_preview,change):
    a=mapped_preview;f=a['f'];data=body(a);key=uuid4().hex;ok(execute(a,data,key),201)
    if change=='INSTANCE_WITHDRAWN':
        catalog=a['a']['catalog'];config=a['a']['configs']['park-b','synthetic-resource-coordination']
        with f[1].connect() as c:
            journal=c.execute("SELECT service_capability_catalog FROM preparation_catalog WHERE park_id='park-b' AND service_id='synthetic-material-preparation' AND version=1").fetchone()['service_capability_catalog']
        catalog.withdraw_instance('park-b',uuid4().hex,config['instance_id'],journal['revision'],'SYNTHETIC explicit fixture withdrawal')
    else:
        with f[1].connect() as c:
            f[1].lock_principal(c,'fixture-c',exclusive=True)
            if change=='ASSIGNMENT':
                c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-c' AND run_id=%s",(a['parent']['run_id'],))
            elif change in ('REVIEWER_READ','EXECUTOR_READ'):
                actor='prep-specialist-fixture-c' if change=='REVIEWER_READ' else 'executor-c'
                c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='READ'",(actor,))
            elif change=='RESOURCE_HOLD':
                c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-c' AND resource_id=%s AND capability='HOLD'",(a['a']['b_resources'][0],))
            else:
                table='preparation_grants' if change=='PREPARE' else 'capability_grants'
                c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-c' AND capability=%s",(change,))
    before=snapshot(f);audit_before=audit_rows(f);saved=a['engine'].path.read_bytes()
    assert read(a,key).status_code in (403,409)
    assert execute(a,data,key).status_code in (403,409)
    assert snapshot(f)==before and a['engine'].path.read_bytes()==saved
    only_denial_audit_appends(f,audit_before,'fixture-c')


@pytest.mark.parametrize('change',['mapping','drop_profile','contract','extra_resource_selector'])
def test_adopted_proof_tampering_or_client_selector_never_falls_back(mapped_preview,change):
    from psycopg.types.json import Jsonb
    a=mapped_preview;f=a['f'];data=body(a)
    if change=='extra_resource_selector':
        data['resource_ids']=a['a']['b_resources']
    else:
        with f[1].connect() as c:
            value=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(a['parent']['preparation_id'],)).fetchone()['service_case_plan']
            if change=='mapping':
                next(s for s in value['adoption_preview']['steps'] if s['id']=='P2')['instance_mappings'][0]['resources']['primary']=str(rh.RESOURCE_ID)
            elif change=='drop_profile':
                value['adoption_preview'].pop('profile');value['binding'].pop('service_selection')
                value['candidate_consumption']['verification_basis']['validator_version']=3
            else:
                next(s for s in value['steps'] if s['adapter_id']=='P2')['contract']['actions'][0]['commands']=['UNREGISTERED']
            c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(value),a['parent']['preparation_id']))
    before=snapshot(f);saved=a['engine'].path.read_bytes()
    assert execute(a,data).status_code in (409,422)
    assert snapshot(f)==before and a['engine'].path.read_bytes()==saved


def test_actual_temp_write_fault_is_unknown_get_only_not_automatic_repeat(mapped_preview,monkeypatch):
    a=mapped_preview;f=a['f'];data=body(a);key=uuid4().hex;before=snapshot(f);calls=[];connections=[];original=rc.confirm
    def fail_after_real_write(store,*args,**kwargs):
        value=original(store,*args,**kwargs);raw=store.connection._raw;connections.append(raw)
        assert raw.execute('SELECT count(*) n FROM synthetic_resource_combination_receipts').fetchone()['n']==1
        calls.append(value['combination']['id']);raise ep.Unavailable('SYNTHETIC fault after actual isolated combination write')
    monkeypatch.setattr(rc,'confirm',fail_after_real_write)
    assert execute(a,data,key).status_code==503 and len(calls)==1 and all(c.closed for c in connections)
    value=ok(read(a,key));assert value['status']=='NOT_OBSERVED' and value['result'] is None and not value['automatically_replayed']
    assert len(calls)==1 and snapshot(f)==before


def test_lost_reply_after_isolated_artifact_commit_recovers_original_key_only(mapped_preview,monkeypatch):
    a=mapped_preview;f=a['f'];data=body(a);key=uuid4().hex;before=snapshot(f);database=a['engine']._database;calls=[]
    class LostReply:
        def __init__(self,db):self.db=db
        def execute(self,*args):return self.db.execute(*args)
        def commit(self):
            self.db.commit();calls.append('committed');raise ep.Unavailable('SYNTHETIC client reply lost after isolated artifact commit')
    @contextmanager
    def lost():
        with database() as db:yield LostReply(db)
    monkeypatch.setattr(a['engine'],'_database',lost)
    assert execute(a,data,key).status_code==503 and calls==['committed']
    monkeypatch.setattr(a['engine'],'_database',database)
    monkeypatch.setattr(a['engine'],'_run_artifact',lambda *args:pytest.fail('recovery repeated preview'))
    value=ok(read(a,key));assert value['status']=='COMMITTED' and value['result']['state']=='SUCCEEDED' and not value['automatically_replayed']
    assert snapshot(f)==before and len(a['calls'])==1


def test_current_resource_lock_wait_and_revision_change_preserve_saved_preview(mapped_preview):
    from concurrent.futures import ThreadPoolExecutor
    from service_release_acceptance_support import wait_for_pg_blocker
    a=mapped_preview;f=a['f'];old_body=body(a);key=uuid4().hex;result=ok(execute(a,old_body,key),201)['result']
    blocker=f[1].connect();pool=ThreadPoolExecutor(1)
    try:
        rh._lock(blocker,UUID(a['a']['b_resources'][0]),shared=False)
        pid=blocker.execute('SELECT pg_backend_pid() pid').fetchone()['pid']
        future=pool.submit(read,a,key)
        waiters=wait_for_pg_blocker(f[1],pid)
        assert waiters
        blocker.execute('UPDATE synthetic_resources SET revision=revision+1 WHERE id=%s',(a['a']['b_resources'][0],))
        blocker.commit()
        value=ok(future.result(timeout=5));assert value['result']==result and value['history'][0]['source_state']=='STALE'
    finally:
        blocker.rollback();blocker.close();pool.shutdown(wait=True)
    before=snapshot(f);assert execute(a,old_body).status_code==409 and snapshot(f)==before


def test_removed_v4_markers_cannot_attempt_legacy_resource_scope(mapped_preview,monkeypatch):
    from psycopg.types.json import Jsonb
    a=mapped_preview;f=a['f'];data=body(a)
    with f[1].connect() as c:
        plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(a['parent']['preparation_id'],)).fetchone()['service_case_plan']
        plan['adoption_preview'].pop('profile',None)
        plan['binding'].pop('service_selection',None)
        plan.pop('candidate_consumption',None)
        for field in ('candidate_id','expected_candidate_sha256','expected_verification_sha256'):
            plan['adoption_request'].pop(field,None)
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),a['parent']['preparation_id']))
    attempted=[];original=rh._scope
    def scope(c,p,id,*args,**kwargs):
        attempted.append(str(id));return original(c,p,id,*args,**kwargs)
    monkeypatch.setattr(rh,'_scope',scope)
    before=snapshot(f);saved=a['engine'].path.read_bytes()
    assert execute(a,data).status_code==409 and str(rh.RESOURCE_ID) not in attempted
    assert snapshot(f)==before and a['engine'].path.read_bytes()==saved
