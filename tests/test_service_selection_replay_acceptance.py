"""Additional owned PG replays: new inputs and explicit receipt feedback.

The model wire is an offline fixture. All business state changes use the
original API. Existing permissions are seeded only by the shared fixture.
"""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from parkweave.api import create_app
from parkweave.service_instance_consumer import ParkInstanceConsumer
from parkweave.service_selection_planner import OfflineSelectionPlanner
from parkweave.template_consumer import ConsumerRepository
from test_preparation import preparation_fixture, headers, command as prep_command
from test_executor_receipts import receipt_fixture, act as receipt_command
from test_service_capability_catalog_actual import capability_catalog
from test_service_selection_full_chain import selection_full_chain, GOALS, ok, verify
from test_service_dispatches import offer, command as dispatch_command
from test_service_case_steps import command as plan_command
from test_case_lifecycle import read as local_read, act as local_command
from service_release_acceptance_support import authority_snapshot, case_history, stable_hash


@pytest.fixture
def replay(selection_full_chain, tmp_path):
    a = selection_full_chain
    f = a['f']
    facade = ParkInstanceConsumer(a['catalog'], ConsumerRepository(tmp_path/'replay.consumer.candidate.sqlite3'), enabled_for_isolated_tests=True)
    calls = []
    def model_http(request):
        context = json.loads(json.loads(request.content)['messages'][-1]['content'])
        calls.append(context)
        selection = dict(schema_version=1, binding=context['binding'], selections=[s['ref'] for s in context['available_services']])
        return httpx.Response(200, json=dict(id='synthetic-replay-'+str(len(calls)), model='intern-s2', usage=dict(prompt_tokens=20, completion_tokens=10, total_tokens=30), choices=[dict(index=0, finish_reason='stop', message=dict(role='assistant', content=json.dumps(selection)))]))
    with TestClient(create_app(f[0], capability_catalog=a['catalog'], selection_planner=OfflineSelectionPlanner(transport=httpx.MockTransport(model_http)), instance_consumer=facade)) as api:
        yield dict(a=a, f=(*f[:3], api), facade=facade, calls=calls)


def cold_body(r, marker):
    i = r['a']['configs']['park-b', 'synthetic-material-preparation']
    return dict(instance_id=i['instance_id'], expected_config_revision=i['config_revision'], expected_config_sha256=i['config_sha256'], expected_release_id=i['release_id'], expected_release_sha256=i['release_sha256'], goal='SYNTHETIC '+marker+' six mandatory local goals', required_goals=GOALS, fields={m['input_field']:dict(slot=s, text='SYNTHETIC '+marker+' fresh private '+s, source_kind='USER_STATEMENT', source_label='SYNTHETIC '+marker+' new source') for s,m in i['fields'].items()}, reason='SYNTHETIC '+marker+' explicit owner input')


def new_confirmed_parent(r, marker):
    f=r['f']; store,owner,tokens,api=f; key=uuid4().hex
    cold=ok(api.post('/api/service-instance-cold-inputs', headers=headers(tokens,'fixture-c',key), json=cold_body(r,marker)),201)
    stage=cold['stages'][0]
    run=ok(api.post('/api/runs',headers=headers(tokens,'fixture-c',stage['request_key']),json=stage['body']),202)
    store.finish(store.claim('SYNTHETIC replay '+marker+' original local worker'))
    assert ok(api.get('/api/runs/'+run['run_id'],headers=headers(tokens,'fixture-c')))['state']=='SUCCEEDED'
    for name in ('CREATE_PREPARATION','SAVE_REQUEST','ADD_need_summary','ADD_material_outline'):
        cold=ok(api.post('/api/service-instance-cold-inputs/prepare-stage?stage='+name,headers=headers(tokens,'fixture-c',key)))
        stage=next(s for s in cold['stages'] if s['name']==name)
        path='/api/preparations' if name=='CREATE_PREPARATION' else '/api/preparations/'+p['preparation_id']+('/request-intent' if name=='SAVE_REQUEST' else '/commands')
        p=ok(api.post(path,headers=headers(tokens,'fixture-c',stage['request_key']),json=stage['body']),201 if name=='CREATE_PREPARATION' else 200)
    p=ok(prep_command(f,p,'REVIEW',user='prep-specialist-fixture-c',reason='SYNTHETIC '+marker+' new materials review'))
    p=ok(prep_command(f,p,'CONFIRM',user='fixture-c',reason='SYNTHETIC '+marker+' new materials confirmation'))
    # Explicit existing test fixture assignment, separate from runtime behavior.
    owner.assign_status('executor-c',UUID(p['run_id']),active=True)
    return p,key


def adopt_selection(r,p):
    f=r['f']; _,_,tokens,api=f; path='/api/preparations/'+p['preparation_id']
    current=ok(api.get(path+'/service-capabilities',headers=headers(tokens,'fixture-c')))
    assert current['selection_oracle']['state']=='UNIQUE'
    assert current['required_goals']==GOALS
    key=uuid4().hex
    candidate=ok(api.post(path+'/service-selections',headers=headers(tokens,'fixture-c',key),json={
        'expected_preparation_revision':p['revision'], 'expected_source_sha256':current['source_sha256'], 'expected_capability_catalog_sha256':current['capability_catalog_sha256']}),201)
    assert candidate['can_adopt'] and candidate['required_goals']==GOALS
    assert ok(api.get(path+'/service-case-plan',headers=headers(tokens,'fixture-c')))['state']=='NOT_ADOPTED'
    adopted=ok(api.post(path+'/service-case-plan',headers=headers(tokens,'fixture-c',uuid4().hex),json=dict(expected_preparation_revision=p['revision'],expected_request_revision=current['request_revision'],expected_plan_revision=0,expected_source_sha256=current['source_sha256'],required_goals=GOALS,reason='SYNTHETIC explicit replay adoption',candidate_id=candidate['candidate_id'],expected_candidate_sha256=candidate['candidate_sha256'],expected_verification_sha256=candidate['verification_sha256'])),201)
    assert [s['adapter_id'] for s in adopted['steps']]==['P1','P2','P3','P4','P5']
    return candidate


def execute_to_receipt(r,p,marker,hour):
    f=r['f']; _,owner,tokens,api=f; path='/api/preparations/'+p['preparation_id']
    verify(f,p,'P1')
    with owner.connect() as c: now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
    body=dict(starts_at=(now+timedelta(hours=hour)).isoformat(),ends_at=(now+timedelta(hours=hour+1)).isoformat(),quantity=2,expected_revision=1,ttl_seconds=300,purpose='SYNTHETIC '+marker+' selected own resources')
    holds=[ok(api.post('/api/synthetic-resources/'+id+'/holds',headers=headers(tokens,'fixture-c',uuid4().hex),json=body),201)['hold'] for id in r['a']['b_resources']]
    group=ok(api.post('/api/resource-combinations',headers=headers(tokens,'fixture-c',uuid4().hex),json=dict(members=[dict(hold_id=h['id'],expected_revision=h['resource_revision']) for h in holds])),201)['combination']
    ok(api.post(path+'/resource-link',headers=headers(tokens,'fixture-c',uuid4().hex),json=dict(combination_id=group['id'],expected_preparation_revision=p['revision'],expected_link_revision=0,reason='SYNTHETIC '+marker+' original resource link')),201)
    verify(f,p,'P2')
    dispatch=ok(offer(f,p,user='prep-specialist-fixture-c',executor='executor-c')[0],201)
    dispatch=ok(dispatch_command(f,dispatch,'ACCEPT',user='executor-c')); verify(f,p,'P3')
    receipt=ok(api.get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(tokens,'executor-c')))
    receipt=ok(receipt_command(f,receipt,'SUBMIT',user='executor-c',text='SYNTHETIC '+marker+' first receipt'))
    receipt=ok(receipt_command(f,receipt,'REQUEST_CHANGES',user='fixture-c',reason='SYNTHETIC '+marker+' clarify evidence'))
    current_plan=ok(api.get(path+'/service-case-plan',headers=headers(tokens,'fixture-c')))
    assert plan_command(f,p,'P4',user='fixture-c',row=current_plan).status_code==409
    receipt=ok(receipt_command(f,receipt,'SUBMIT',user='executor-c',text='SYNTHETIC '+marker+' corrected receipt',source_label='SYNTHETIC replay corrected source v2'))
    receipt=ok(receipt_command(f,receipt,'ACKNOWLEDGE',user='fixture-c'))
    verify(f,p,'P4')
    ok(local_command(f,p,ok(local_read(f,p,user='fixture-c')),'REVALIDATE',user='fixture-c')); verify(f,p,'P5')
    return group,dispatch,receipt


def result(r,p):
    f=r['f'];return ok(f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2],'fixture-c')))


def test_v4_twice_new_inputs_receipt_correction_and_feedback_recheck(replay):
    r=replay;f=r['f'];owner=f[1]
    p1,key1=new_confirmed_parent(r,'AT35-FIRST'); authority1=authority_snapshot(owner)
    candidate1=adopt_selection(r,p1)
    g1,d1,s1=execute_to_receipt(r,p1,'AT35-FIRST',1)
    first=result(r,p1)
    assert first['state']=='LOCAL_OUTPUTS_VERIFIED' and not first['case_goal_completed']
    outputs={x['adapter_id']:x['actual_output'] for x in first['results']}
    assert outputs['P4']['receipt_version']==2
    old_p5=outputs['P5']['revalidation_event_id']
    s1=ok(receipt_command(f,s1,'REOPEN',user='fixture-c',reason='SYNTHETIC explicit new feedback after verification'))
    changed=result(r,p1)
    assert changed['state']!='LOCAL_OUTPUTS_VERIFIED'
    for adapter in ('P4','P5'):
        rows=[x for x in changed['results'] if x['adapter_id']==adapter]
        assert rows and all(x['state']!='LOCAL_OUTPUT_VERIFIED' and x['actual_output'] is None for x in rows)
    s1=ok(receipt_command(f,s1,'SUBMIT',user='executor-c',text='SYNTHETIC AT35-FIRST feedback revision three',source_label='SYNTHETIC replay feedback v3'))
    s1=ok(receipt_command(f,s1,'ACKNOWLEDGE',user='fixture-c')); verify(f,p1,'P4')
    assert result(r,p1)['state']!='LOCAL_OUTPUTS_VERIFIED'
    ok(local_command(f,p1,ok(local_read(f,p1,user='fixture-c')),'REVALIDATE',user='fixture-c')); verify(f,p1,'P5')
    restored=result(r,p1)
    assert restored['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert next(x['actual_output'] for x in restored['results'] if x['adapter_id']=='P5')['revalidation_event_id']!=old_p5
    assert authority_snapshot(owner)==authority1
    historical=case_history(owner,p1['preparation_id'])
    p2,key2=new_confirmed_parent(r,'AT35-SECOND'); authority2=authority_snapshot(owner)
    assert len(authority2['run_assignments'])==len(authority1['run_assignments'])+1
    assert all(authority1[t]==authority2[t] for t in authority1 if t!='run_assignments')
    candidate2=adopt_selection(r,p2);g2,d2,s2=execute_to_receipt(r,p2,'AT35-SECOND',3)
    second=result(r,p2)
    assert second['state']=='LOCAL_OUTPUTS_VERIFIED' and not second['case_goal_completed']
    for field in ('case_id','run_id','preparation_id'):assert p1[field]!=p2[field]
    assert candidate1['candidate_id']!=candidate2['candidate_id'] and key1!=key2
    assert g1['id']!=g2['id'] and d1['dispatch_id']!=d2['dispatch_id'] and s1['current_receipt']['id']!=s2['current_receipt']['id']
    materials=[ok(f[3].get('/api/preparations/'+p['preparation_id'],headers=headers(f[2],'fixture-c')))['current_materials'] for p in (p1,p2)]
    assert {m['id'] for m in materials[0]}.isdisjoint(m['id'] for m in materials[1])
    assert {m['text'] for m in materials[0]}.isdisjoint(m['text'] for m in materials[1])
    assert case_history(owner,p1['preparation_id'])==historical and result(r,p1)==restored
    assert authority_snapshot(owner)==authority2 and len(r['calls'])==2
    assert all(c['required_goals']==GOALS for c in r['calls'])
    # Business C subset: an original explicit resource cancellation changes
    # current feasibility; it cannot leave old P2/P5 output proofs current.
    cancel_key=uuid4().hex
    cancelled=ok(f[3].post('/api/resource-combinations/'+g2['id']+'/cancel',headers=headers(f[2],'fixture-c',cancel_key),json={}))
    assert cancelled['combination']['state']=='CANCELLED'
    assert all(h['state']=='RELEASED' for h in cancelled['combination']['members'])
    impacted=result(r,p2)
    assert [row['goal'] for row in impacted['results']]==GOALS and impacted['adopted_goals']==GOALS
    assert impacted['state']!='LOCAL_OUTPUTS_VERIFIED'
    for adapter in ('P2','P5'):
        rows=[x for x in impacted['results'] if x['adapter_id']==adapter]
        assert rows and all(x['actual_output'] is None and x['state']!='LOCAL_OUTPUT_VERIFIED' for x in rows)
    assert case_history(owner,p1['preparation_id'])==historical and result(r,p1)==restored
    assert authority_snapshot(owner)==authority2 and len(r['calls'])==2
    artifact=dict(scope='OWNED_SYNTHETIC_V4_TWO_FRESH_INPUT_FEEDBACK_REPLAY',first_case=p1['case_id'],second_case=p2['case_id'],first_result_sha256=stable_hash(restored),second_result_sha256=stable_hash(second),fixture_new_resource_grants=4,fixture_new_run_assignments=2,runtime_authority_rows_changed=0,offline_model_calls=2,real_model_calls=0,feedback_actions=['SUBMIT','REQUEST_CHANGES','SUBMIT','ACKNOWLEDGE','REOPEN','SUBMIT','ACKNOWLEDGE'],second_run_distinct_materials=True,first_history_unchanged=True,resource_change_original_cancel=True,resource_change_replanning='NOT RUN',case_goal_completed=False)
    path=Path('.runtime/at-replay-20261014/two-input-feedback-outcome.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(artifact,indent=2)+'\n')


def all_public_rows(owner):
    """Independent complete data oracle; no compiler/product hash function."""
    with owner.connect() as c:
        names=[row['tablename'] for row in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()]
        assert names and all(name.replace('_','').isalnum() for name in names)
        return {name:c.execute('SELECT * FROM "'+name+'" ORDER BY to_jsonb("'+name+'")::text').fetchall() for name in names}


def cold_journal_rows(r):
    with r['facade'].repository.connect() as c:
        return {table:[dict(x) for x in c.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()] for table in ('consumer_instances','consumer_requests','consumer_stages')}


def test_invalid_new_cold_inputs_reject_without_pg_or_journal_writes(replay):
    r=replay;f=r['f'];api=f[3];original=cold_body(r,'AT08-INVALID');first=next(iter(original['fields']))
    cases=[]
    def altered(label,status,change,user='fixture-c'):
        value=deepcopy(original);change(value);cases.append((label,status,value,user))
    altered('blank_material',422,lambda b:b['fields'][first].update(text=' '))
    altered('old_material_extra',422,lambda b:b.update(old_case_id=str(uuid4())))
    altered('unknown_external_field',409,lambda b:b['fields'].update({'foreign-external-field':b['fields'].pop(first)}))
    altered('duplicate_slot',422,lambda b:b['fields'][first].update(slot=next(v['slot'] for k,v in b['fields'].items() if k!=first)))
    altered('invented_provenance',422,lambda b:b['fields'][first].update(source_kind='VERIFIED'))
    altered('blank_goal',422,lambda b:b.update(goal=' '))
    altered('changed_revision',409,lambda b:b.update(expected_config_revision=2))
    altered('changed_release',409,lambda b:b.update(expected_release_sha256='0'*64))
    altered('duplicate_required_goal',422,lambda b:b.update(required_goals=GOALS+[GOALS[0]]))
    altered('foreign_owner_instance',409,lambda b:None,user='fixture-a')
    before_pg=all_public_rows(f[1]);before_journal=cold_journal_rows(r)
    outcomes=[]
    for label,status,body,user in cases:
        response=api.post('/api/service-instance-cold-inputs',headers=headers(f[2],user,uuid4().hex),json=body)
        assert response.status_code==status,(label,response.text)
        assert all_public_rows(f[1])==before_pg,label
        assert cold_journal_rows(r)==before_journal,label
        assert r['calls']==[]
        outcomes.append(dict(input=label,status=response.status_code,pg_rows_unchanged=True,cold_journal_rows_unchanged=True))
    path=Path('.runtime/at-replay-20261014/invalid-cold-inputs-outcome.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(dict(scope='OWNED_SYNTHETIC_COLD_INPUT_REJECTION',cases=outcomes,public_table_count=len(before_pg),model_calls=0),indent=2)+'\n')
