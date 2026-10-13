"""Explicit partial service plans through original owned PostgreSQL business APIs."""
from uuid import uuid4
import pytest
from test_preparation import preparation_fixture, headers, command as prep_command
from test_executor_receipts import receipt_fixture, ready
from test_case_resources import link_fixture, group, post as link
from test_service_case_steps import read, adopt, adopt_body, command, business, step
from test_service_dispatches import offer, REVIEWER
from test_request_intents import save

UNKNOWN='SYNTHETIC_EXTERNAL_AUTHORITY_APPROVAL'

def setup_partial(f,goal='LOCAL_MATERIAL_PREPARATION',constraints=None):
    p=ready(f)
    body=dict(expected_preparation_revision=p['revision'],request_text='SYNTHETIC local work and external approval',required_goals=[goal,UNKNOWN])
    if constraints is not None:body['planning_constraints']=constraints
    r=f[3].post('/api/preparations/'+p['preparation_id']+'/request-intent',headers=headers(f[2],key=uuid4().hex),json=body)
    assert r.status_code==200,r.text
    p={**p,'revision':r.json()['revision']}
    p=prep_command(f,p,'REVIEW',REVIEWER,reason='SYNTHETIC independent material review').json()
    p=prep_command(f,p,'CONFIRM',reason='SYNTHETIC explicit local material confirmation').json()
    return p

def test_partial_preview_keeps_every_required_goal_and_offers_only_independent_nodes(link_fixture):
    f=link_fixture;p=setup_partial(f)
    preview=read(f,p).json()['current_preview']
    assert preview['state']=='PARTIAL'
    assert preview['required_goals']==['LOCAL_MATERIAL_PREPARATION',UNKNOWN]
    assert preview['partial_offer']['can_adopt'] is True
    assert preview['partial_offer']['step_ids']==['P1']
    assert preview['partial_offer']['manual_goals']==[UNKNOWN]
    assert not preview['execution_enabled']

def test_explicit_partial_adoption_retains_unknown_goal_and_verifies_real_independent_output(link_fixture):
    f=link_fixture;p=setup_partial(f);before=business(f)
    body=adopt_body(f,p,partial_adoption=True)
    r=adopt(f,p,body);assert r.status_code==201,r.text
    assert r.json()['overall_goal_state']=='PARTIAL'
    assert [s['adapter_id'] for s in r.json()['steps']]==['P1']
    assert r.json()['required_goals']==body['required_goals']
    assert business(f)==before
    r=command(f,p,'P1');assert r.status_code==200,r.text
    assert step(r.json(),'P1')['state']=='VERIFIED'
    assert r.json()['overall_goal_state']=='PARTIAL' and not r.json()['case_goal_completed']

def test_original_goal_results_and_worklist_keep_partial_manual_items(link_fixture):
    f=link_fixture;p=setup_partial(f)
    r=adopt(f,p,adopt_body(f,p,partial_adoption=True));assert r.status_code==201,r.text
    assert command(f,p,'P1').status_code==200
    results=f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]))
    assert results.status_code==200,results.text
    assert results.json()['state']=='PARTIAL'
    assert [r['state'] for r in results.json()['results']]==['LOCAL_OUTPUT_VERIFIED','UNSUPPORTED']
    assert results.json()['results'][1]['next_action']=='MANUAL_SERVICE_CONTRACT_REQUIRED'
    row=next(x for x in f[3].get('/api/cases/worklist',headers=headers(f[2])).json()['items'] if x['case_id']==p['case_id'])
    assert row['partial_plan']['plan_id']==r.json()['plan_id']
    assert row['partial_plan']['overall_goal_state']=='PARTIAL'

@pytest.mark.parametrize('mode',['no_confirmation','global_unknown','all_unsupported','catalog_unknown','all_roles_blocked','drop_goal'])
def test_partial_admission_refuses_unknown_contract_or_incomplete_confirmation(link_fixture,mode):
    f=link_fixture
    constraints={'additional_requirements':['SYNTHETIC region and deadline unknown']} if mode=='global_unknown' else {'excluded_roles':['park_specialist']} if mode=='all_roles_blocked' else None
    p=setup_partial(f,UNKNOWN if mode=='all_unsupported' else 'LOCAL_MATERIAL_PREPARATION',constraints)
    if mode=='catalog_unknown':
        with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source='{}'::jsonb")
    body=adopt_body(f,p,**({} if mode=='no_confirmation' else {'partial_adoption':True}))
    if mode=='drop_goal':body['required_goals']=['LOCAL_MATERIAL_PREPARATION']
    before=business(f)
    r=adopt(f,p,body);assert r.status_code==409,r.text
    assert read(f,p).json()['plan_id'] is None and business(f)==before

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_partial_adoption_still_requires_current_original_owner(link_fixture,user):
    f=link_fixture;p=setup_partial(f);body=adopt_body(f,p,partial_adoption=True);before=business(f)
    assert adopt(f,p,body,user=user).status_code==403
    assert business(f)==before and read(f,p).json()['plan_id'] is None

@pytest.mark.parametrize('capability',['READ','PREPARE','EXECUTE'])
def test_partial_adoption_rechecks_revoked_current_capability(link_fixture,capability):
    f=link_fixture;p=setup_partial(f);body=adopt_body(f,p,partial_adoption=True)
    with f[1].connect() as c:
        table='preparation_grants' if capability=='PREPARE' else 'capability_grants'
        c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',capability))
    before=business(f)
    assert adopt(f,p,body).status_code==403
    assert business(f)==before
    with f[1].connect() as c:assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'] is None

def test_partial_plan_only_allows_selected_original_business_operations(link_fixture):
    f=link_fixture;p=setup_partial(f);assert adopt(f,p,adopt_body(f,p,partial_adoption=True)).status_code==201
    assert command(f,p,'P1').status_code==200
    g=group(f);before=business(f)
    assert link(f,p,g).status_code==409
    assert offer(f,p)[0].status_code==409
    assert business(f)==before
    # Ordinary material writes remain available and invalidate the old P1 proof.
    from test_preparation import add
    assert prep_command(f,p,'REOPEN',reason='SYNTHETIC new material required').status_code==200
    p=f[3].get('/api/preparations/'+p['preparation_id'],headers=headers(f[2])).json()['preparation']
    p={'preparation_id':str(p['id']),'revision':p['revision']}
    assert add(f,p).status_code==200

def test_constraints_leave_dependent_steps_waiting_and_allow_independent_resource_subgraph(link_fixture):
    f=link_fixture;p=setup_partial(f,'LOCAL_CASE_RECORD_RECHECK',{'excluded_roles':['service_executor']})
    preview=read(f,p).json()['current_preview']
    assert preview['partial_offer']['step_ids']==['P1','P2']
    assert preview['partial_offer']['waiting_step_ids']==['P3','P4','P5']
    assert len(preview['steps'])==5 and len(preview['required_goals'])==2
    r=adopt(f,p,adopt_body(f,p,partial_adoption=True));assert r.status_code==201,r.text
    assert [s['adapter_id'] for s in r.json()['steps']]==['P1','P2']
    g=group(f);assert link(f,p,g).status_code==409
    assert command(f,p,'P2').status_code==409
    assert command(f,p,'P1').status_code==200
    assert link(f,p,g).status_code==201
    assert command(f,p,'P2').status_code==200
    assert offer(f,p)[0].status_code==409
    results=f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2])).json()
    assert results['state']=='PARTIAL' and results['results'][0]['state']=='WAITING_DEPENDENCY'
    assert results['results'][0]['actual_output'] is None

def test_full_supported_dependency_closure_in_partial_plan_cannot_jump_prerequisites(link_fixture):
    f=link_fixture;p=setup_partial(f,'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT')
    r=adopt(f,p,adopt_body(f,p,partial_adoption=True));assert r.status_code==201
    assert [s['adapter_id'] for s in r.json()['steps']]==['P1','P2','P3','P4']
    before=business(f);g=group(f)
    assert offer(f,p)[0].status_code==409 and command(f,p,'P4').status_code==409
    assert link(f,p,g).status_code==409 and business(f)==before
    assert command(f,p,'P1').status_code==200
    assert link(f,p,g).status_code==201
    assert offer(f,p)[0].status_code==409

def test_partial_original_key_replay_conflict_and_cold_read_only_recovery(link_fixture):
    from parkweave import service_case_steps as scs
    from parkweave.store import Store
    from uuid import UUID
    f=link_fixture;p=setup_partial(f);body=adopt_body(f,p,partial_adoption=True);key=uuid4().hex
    r=adopt(f,p,body,key);assert r.status_code==201
    before=business(f);event=r.json()['event']
    assert adopt(f,p,body,key).json()['event']==event
    assert adopt(f,p,{**body,'reason':'SYNTHETIC other reason'},key).status_code==409
    assert adopt(f,p,{k:v for k,v in body.items() if k!='partial_adoption'},key).status_code==409
    cold=scs.recover(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']),key)
    assert cold['status']=='COMMITTED' and cold['event']['id']==event['id']
    assert cold['read_only'] and not cold['automatically_replayed']
    assert cold['current']['overall_goal_state']=='PARTIAL' and cold['current']['can_adopt'] is False
    assert business(f)==before

def test_old_partial_preview_rejected_after_actual_material_and_request_source_changes(link_fixture):
    from test_preparation import add
    f=link_fixture;p=setup_partial(f);body=adopt_body(f,p,partial_adoption=True)
    assert prep_command(f,p,'REOPEN',reason='SYNTHETIC source advance').status_code==200
    assert adopt(f,p,body).status_code==409
    current=f[3].get('/api/preparations/'+p['preparation_id'],headers=headers(f[2])).json()['preparation']
    p={**p,'revision':current['revision']}
    fresh=adopt_body(f,p,partial_adoption=True)
    r=save(f,p,goals=['LOCAL_MATERIAL_PREPARATION',UNKNOWN],text='SYNTHETIC changed request')
    assert r.status_code==200
    assert adopt(f,p,fresh).status_code==409
    assert read(f,p).json()['plan_id'] is None

@pytest.mark.parametrize('mode',['same_key_same_body','same_key_changed_body','different_keys'])
def test_partial_adoption_same_key_and_different_keys_are_serialized_by_real_parent_lock(link_fixture,mode):
    from concurrent.futures import ThreadPoolExecutor
    f=link_fixture;p=setup_partial(f);body=adopt_body(f,p,partial_adoption=True);key=uuid4().hex
    inputs=[(body,key),({**body,'reason':'SYNTHETIC second simultaneous decision'} if mode=='same_key_changed_body' else body,uuid4().hex if mode=='different_keys' else key)]
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda item:adopt(f,p,*item),inputs))
    assert sorted(r.status_code for r in results)==([201,201] if mode=='same_key_same_body' else [201,409])
    if mode=='same_key_same_body':assert results[0].json()['event']==results[1].json()['event']
    assert adopt(f,p,body,uuid4().hex).status_code==409
    assert len(read(f,p).json()['events'])==1

def test_partial_flag_or_selection_tampering_has_no_valid_original_confirmation(link_fixture):
    from psycopg.types.json import Jsonb
    f=link_fixture;p=setup_partial(f);assert adopt(f,p,adopt_body(f,p,partial_adoption=True)).status_code==201
    with f[1].connect() as c:
        row=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
        row['adoption_request'].pop('partial_adoption')
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(row),p['preparation_id']))
    assert read(f,p).status_code==409

def test_actual_original_html_partial_confirmation_lost_response_cold_recovery_results_and_worklist(link_fixture):
    import json,subprocess,selectors
    from pathlib import Path
    f=link_fixture;p=setup_partial(f);before=business(f)
    proc=subprocess.Popen(['node','tests/partial_service_plan.js','partial_original_entry',p['preparation_id']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ);requests=[];lost=0;summary=None
    try:
        while True:
            assert selector.select(timeout=15),'Original partial UI bridge stalled'
            line=proc.stdout.readline()
            if not line:break
            message=json.loads(line)
            if 'request' not in message:summary=message;break
            req=message['request'];options=req['options'];method=options.get('method','GET');body=json.loads(options['body']) if options.get('body') else None
            actor=options['headers']['Authorization'].removeprefix('Bearer SYNTHETIC_')
            response=f[3].request(method,req['path'],headers=headers(f[2],actor,key=options['headers'].get('Idempotency-Key')),json=body)
            drop=method=='POST' and req['path'].endswith('/service-case-plan')
            requests.append(dict(method=method,path=req['path'],status=response.status_code,action=body.get('action') if body else None,lost=drop))
            assert response.status_code<400,(requests[-1],response.text)
            lost+=int(drop)
            proc.stdin.write((json.dumps(dict(status=response.status_code,body=response.json(),lost=drop))+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read().decode()
        assert summary and summary['checks']>=25 and summary['adopts']==1 and lost==1
        assert business(f)==before
        with f[1].connect() as c:
            stored=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
            assert len(stored['events'])==2 and stored['partial_adoption'] is True
        out=Path('.runtime/partial-plan-20261013');out.mkdir(parents=True,exist_ok=True)
        (out/'actual-chain.json').write_text(json.dumps(dict(summary=summary,requests=requests,lost_responses=lost,business_rows_unchanged=True),indent=2)+'\n')
    finally:
        Path('.runtime/partial-plan-20261013/latest-partial-chain.json').write_text(json.dumps(dict(summary=summary,requests=requests,lost_responses=lost),indent=2)+'\n')
        selector.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)

def test_partial_adoption_waits_for_actual_pg_parent_mutation_and_refuses_stale_preview(link_fixture,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import time,json
    from pathlib import Path
    from parkweave import preparation as prep
    f=link_fixture;p=setup_partial(f)
    p=prep_command(f,p,'REOPEN',reason='SYNTHETIC reopen before reviewer correction').json()
    body=adopt_body(f,p,partial_adoption=True)
    entered=Event();release=Event();original=prep.event
    def held_event(c,actor,row,key,fp,action,*args,**kwargs):
        result=original(c,actor,row,key,fp,action,*args,**kwargs)
        if action=='REQUEST_CHANGES':
            entered.set();assert release.wait(5),'owned writer release deadline exceeded'
        return result
    monkeypatch.setattr(prep,'event',held_event);waiting=False
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer=pool.submit(prep_command,f,p,'REQUEST_CHANGES',REVIEWER,reason='SYNTHETIC actual source correction during partial adoption')
        assert entered.wait(3)
        pending=pool.submit(adopt,f,p,body)
        try:
            with f[1].connect() as monitor:
                until=time.monotonic()+2
                while time.monotonic()<until:
                    monitor.execute('SELECT pg_stat_clear_snapshot()')
                    waiting=monitor.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query ILIKE '%%FROM preparations%%FOR UPDATE%%') AS waiting").fetchone()['waiting']
                    if waiting:break
                    time.sleep(.01)
            assert waiting,'adoption did not reach the actual PostgreSQL parent row lock'
        finally:release.set()
        assert writer.result(5).status_code==200
        r=pending.result(5);assert r.status_code==409,r.text
    assert read(f,p).json()['plan_id'] is None
    Path('.runtime/partial-plan-20261013/actual-pg-wait.json').write_text(json.dumps(dict(actual_parent_lock_wait=waiting,original_writer='REQUEST_CHANGES',writer_status=200,stale_adoption_status=409,plan_saved=False),indent=2)+'\n')

def test_partial_adoption_event_persistence_failure_rolls_back_all_state(link_fixture,monkeypatch):
    from parkweave import service_case_steps as scs
    from test_resource_plan_binding import complete_digest
    f=link_fixture;p=setup_partial(f);body=adopt_body(f,p,partial_adoption=True);before=complete_digest(f)
    original=scs._save
    def failed(c,parent,plan):
        original(c,parent,plan)
        raise RuntimeError('SYNTHETIC_PARTIAL_EVENT_FAILURE')
    monkeypatch.setattr(scs,'_save',failed)
    with pytest.raises(RuntimeError,match='SYNTHETIC_PARTIAL_EVENT_FAILURE'):adopt(f,p,body)
    assert complete_digest(f)==before

def test_partial_supported_receipt_goal_finishes_local_output_without_completing_whole_request(link_fixture):
    from test_service_dispatches import command as dispatch_command
    from test_executor_receipts import act as receipt_command
    from test_isolated_run_access import permission_snapshot
    f=link_fixture;p=setup_partial(f,'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT');permissions=permission_snapshot(f[1])
    assert adopt(f,p,adopt_body(f,p,partial_adoption=True)).status_code==201
    assert command(f,p,'P1').status_code==200
    g=group(f);assert link(f,p,g).status_code==201
    assert command(f,p,'P2').status_code==200
    dispatch=offer(f,p)[0];assert dispatch.status_code==201,dispatch.text
    accepted=dispatch_command(f,dispatch.json(),'ACCEPT');assert accepted.status_code==200,accepted.text
    assert command(f,p,'P3').status_code==200
    receipt=f[3].get('/api/executor-receipts/'+accepted.json()['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
    response=receipt_command(f,receipt,'SUBMIT');assert response.status_code==200,response.text
    response=receipt_command(f,response.json(),'ACKNOWLEDGE');assert response.status_code==200,response.text
    r=command(f,p,'P4');assert r.status_code==200,r.text
    assert r.json()['state']=='VERIFIED' and r.json()['overall_goal_state']=='PARTIAL'
    results=f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2])).json()
    assert results['state']=='PARTIAL' and [x['state'] for x in results['results']]==['LOCAL_OUTPUT_VERIFIED','UNSUPPORTED']
    assert results['results'][0]['actual_output']['ack_event_ids']
    assert not results['case_goal_completed'] and permission_snapshot(f[1])==permissions
    with f[1].connect() as c:assert c.execute('SELECT state FROM cases WHERE id=%s',(p['case_id'],)).fetchone()['state']!='FULFILLED'

def test_clearing_constraint_form_cannot_relabel_required_global_condition_as_independent_goal(link_fixture):
    f=link_fixture;p=setup_partial(f,constraints={'additional_requirements':['SYNTHETIC mandatory region and deadline']})
    r=f[3].post('/api/preparations/'+p['preparation_id']+'/request-intent',headers=headers(f[2],key=uuid4().hex),json=dict(expected_preparation_revision=p['revision'],request_text='SYNTHETIC clear form, keep all required goals',required_goals=['LOCAL_MATERIAL_PREPARATION',UNKNOWN,'SYNTHETIC mandatory region and deadline'],planning_constraints={}))
    assert r.status_code==200,r.text;p={**p,'revision':r.json()['revision']}
    preview=read(f,p).json()['current_preview']
    assert preview['partial_offer']['global_condition_unknown'] and not preview['partial_offer']['can_adopt']
    assert preview['global_requirements']==['SYNTHETIC mandatory region and deadline']
    assert len(preview['required_goals'])==3
    assert adopt(f,p,adopt_body(f,p,partial_adoption=True)).status_code==409

def test_existing_fixed_plan_guard_cannot_be_bypassed_by_partial_adoption(link_fixture):
    from test_controlled_plans import create as fixed_adopt
    f=link_fixture;p=ready(f)
    assert fixed_adopt(f,p).status_code==201
    r=save(f,p,goals=['LOCAL_SYNTHETIC_COORDINATION_RECORDS',UNKNOWN]);assert r.status_code==200
    p={**p,'revision':r.json()['revision']}
    preview=read(f,p).json()['current_preview']
    assert preview['partial_offer']['legacy_fixed_plan_conflict'] and not preview['partial_offer']['can_adopt']
    assert adopt(f,p,adopt_body(f,p,partial_adoption=True)).status_code==409
