"""Three trusted capabilities → fresh B mappings → actual original P1–P5 outputs.

The only fake is the exact offline model HTTP response containing compact refs.
Every business result is written by the original public command, never a mock.
"""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from psycopg.types.json import Jsonb

from parkweave.store import Store
from parkweave.template_consumer import ConsumerRepository
from parkweave.service_capability_contract import hash_instance
from test_preparation import preparation_fixture, headers, command as prep_command, create
from test_executor_receipts import receipt_fixture, act as receipt_command
from test_service_capability_catalog_actual import capability_catalog, register, material_instance
from test_service_dispatches import offer, command as dispatch_command
from test_case_lifecycle import read as local_read, act as local_command
from test_service_case_steps import command as plan_command
from service_release_acceptance_support import authority_snapshot, case_history

GOALS = ['LOCAL_MATERIAL_PREPARATION', 'LOCAL_CASE_RESOURCE_ASSOCIATION',
         'LOCAL_INTERNAL_ACCEPTANCE', 'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT',
         'LOCAL_SYNTHETIC_COORDINATION_RECORDS', 'LOCAL_CASE_RECORD_RECHECK']
KINDS = ['synthetic-material-preparation', 'synthetic-resource-coordination',
         'synthetic-local-record-recheck']


def ok(response, code=200):
    assert response.status_code == code, response.text
    return response.json()


def seed_second_park_resources(owner):
    """Explicit initial fixture, not application Grant or registry publication."""
    ids = [str(uuid4()), str(uuid4())]
    with owner.connect() as c:
        for number, resource_id in enumerate(ids):
            source = dict(kind='SYNTHETIC', id='B-independent-resource-'+str(number),
                          revision='1', statement='SYNTHETIC B own initial resource fixture')
            c.execute("""INSERT INTO synthetic_resources VALUES(%s,'park-b',%s,1,2,300,
                clock_timestamp()-interval '1 day',clock_timestamp()+interval '30 days',
                true,'UTC','SYNTHETIC','LOCAL_AUTHORITY',%s)""",
                (resource_id, 'SYNTHETIC B resource '+str(number), Jsonb(source)))
            for capability in ('READ', 'HOLD'):
                c.execute('INSERT INTO synthetic_resource_grants VALUES(%s,%s,%s,%s,%s,true)',
                          ('fixture-c', resource_id, 'park-b', 'org-c', capability))
    return ids


@pytest.fixture
def selection_full_chain(capability_catalog, receipt_fixture):
    a = capability_catalog
    assert receipt_fixture is a['f']
    from parkweave.resource_combinations import seed_synthetic
    seed_synthetic(a['f'][1])
    before_seed = authority_snapshot(a['f'][1])
    b_resources = seed_second_park_resources(a['f'][1])
    after_seed = authority_snapshot(a['f'][1])
    added = [r for r in after_seed['synthetic_resource_grants']
             if r not in before_seed['synthetic_resource_grants']]
    assert len(added) == 4
    assert all(r['principal_id']=='fixture-c' and r['park_id']=='park-b' and r['org_id']=='org-c' for r in added)
    assert all(after_seed[t]==before_seed[t] for t in before_seed if t!='synthetic_resource_grants')
    from parkweave import resource_holds as rh, resource_combinations as rc
    releases = {kind:register(a, service=kind)['release'] for kind in KINDS}
    configs = {}
    for park in ('park-a', 'park-b'):
        for kind, release in releases.items():
            value = material_instance(release, park)
            value['instance_id'] = park+'-'+kind+'-full-chain-instance'
            if kind!='synthetic-material-preparation':
                value['roles']['service_executor']='executor-c' if park=='park-b' else 'executor-a'
                resources = b_resources if park=='park-b' else [str(rh.RESOURCE_ID),str(rc.SECOND_RESOURCE_ID)]
                value['resources']=dict(zip(('primary','secondary'),resources))
            value['config_sha256']=hash_instance(value)
            a['catalog'].bind_instance(park,uuid4().hex,value)
            configs[park,kind]=value
    return dict(**a,releases=releases,configs=configs,b_resources=b_resources,
                fixture_seed_grants=4,fixture_seed_assignments=0)


def verify(f, parent, adapter):
    row=ok(f[3].get('/api/preparations/'+parent['preparation_id']+'/service-case-plan',headers=headers(f[2],'fixture-c')))
    reply = plan_command(f,parent,adapter,user='fixture-c',row=row)
    actual = ok(reply)
    assert next(s for s in actual['steps'] if s['adapter_id']==adapter)['state']=='VERIFIED'


@pytest.mark.parametrize('via_api',[False,True],ids=['direct-selection-original-business-api','selection-cold-and-business-api'])
def test_three_capability_selection_second_park_original_local_outputs(selection_full_chain,tmp_path,via_api,request):
    # New interfaces are imported here so a pending integration cannot mask an
    # otherwise collectable old regression suite with an import-time error.
    from parkweave import bounded_planning as bp,service_selection_candidates as candidates
    from parkweave.service_selection_planner import OfflineSelectionPlanner
    from parkweave.service_instance_consumer import ColdInput,ParkInstanceConsumer
    from parkweave import case_goal_results
    a=selection_full_chain;f=a['f'];store,owner,tokens,api=f
    store._isolated_service_capability_catalog=a['catalog']
    # Existing original A workflow is history setup only; the new capability
    # selection under test is the independently created B chain below.
    from test_case_goal_results import complete as complete_existing_original_case
    before_A_fixture=authority_snapshot(owner)
    a_parent,a_group,a_dispatch,a_receipt=complete_existing_original_case(f,local=True)
    after_A_fixture=authority_snapshot(owner)
    assert len(after_A_fixture['run_assignments'])==len(before_A_fixture['run_assignments'])+1
    assert all(after_A_fixture[t]==before_A_fixture[t] for t in before_A_fixture if t!='run_assignments')
    old_history=case_history(owner,a_parent['preparation_id'])
    a_materials=ok(api.get('/api/preparations/'+a_parent['preparation_id'],headers=headers(tokens)))['current_materials']
    a_result_reply=api.get('/api/preparations/'+a_parent['preparation_id']+'/goal-results',headers=headers(tokens))
    a_results=ok(a_result_reply)
    a_result_bytes=a_result_reply.content
    assert a_results['state']=='LOCAL_OUTPUTS_VERIFIED' and not a_results['case_goal_completed']
    assert all(row['state']=='LOCAL_OUTPUT_VERIFIED' for row in a_results['results'])
    a_resource_ids={str(h['resource_id']) for h in old_history['synthetic_resource_holds']}
    assert len(a_resource_ids)==2

    instance=a['configs']['park-b','synthetic-material-preparation']
    facade=ParkInstanceConsumer(a['catalog'],ConsumerRepository(tmp_path/'full-chain-cold.consumer.candidate.sqlite3'),enabled_for_isolated_tests=True)
    data=ColdInput(instance_id=instance['instance_id'],expected_config_revision=instance['config_revision'],
        expected_config_sha256=instance['config_sha256'],expected_release_id=instance['release_id'],
        expected_release_sha256=instance['release_sha256'],goal='SYNTHETIC B fresh six-goal request',
        required_goals=GOALS,fields={mapping['input_field']:dict(slot=slot,text='SYNTHETIC B FRESH PRIVATE '+slot,
        source_kind='USER_STATEMENT',source_label='SYNTHETIC B newly supplied source') for slot,mapping in instance['fields'].items()},
        reason='SYNTHETIC B explicitly confirms current cold inputs')
    calls=[]
    def model_http(request):
        prompt=json.loads(json.loads(request.content)['messages'][-1]['content']);calls.append(prompt)
        assert 'steps' not in prompt and 'B FRESH PRIVATE' not in json.dumps(prompt)
        selection=dict(schema_version=1,binding=prompt['binding'],selections=[s['ref'] for s in prompt['available_services']])
        return httpx.Response(200,json=dict(id='synthetic-B-three-capability',model='intern-s2',usage=dict(prompt_tokens=20,completion_tokens=10,total_tokens=30),choices=[dict(index=0,finish_reason='stop',message=dict(role='assistant',content=json.dumps(selection)))]))
    planner=OfflineSelectionPlanner(transport=httpx.MockTransport(model_http))
    if via_api:
        from fastapi.testclient import TestClient
        from parkweave.api import create_app
        ok(api.get('/api/preparations/'+a_parent['preparation_id']+'/service-capabilities',headers=headers(tokens)),403)
        api=TestClient(create_app(store,capability_catalog=a['catalog'],selection_planner=planner,instance_consumer=facade))
        request.addfinalizer(api.close)
        f=(*f[:3],api)
    key=uuid4().hex;initial_authority=authority_snapshot(owner)
    view=ok(api.post('/api/service-instance-cold-inputs',headers=headers(tokens,'fixture-c',key),json=data.model_dump()),201) if via_api else facade.prepare(tokens['fixture-c'],key,data)
    assert len(view['stages'])==1 and not view['automatic_execution']
    stage=next(s for s in view['stages'] if s['name']=='CREATE_RUN')
    run=ok(api.post('/api/runs',headers=headers(tokens,'fixture-c',stage['request_key']),json=stage['body']),202)
    # Original local Run worker uses actual ordinary processing; no provider.
    store.finish(store.claim('SYNTHETIC B original local worker'))
    run_view=ok(api.get('/api/runs/'+run['run_id'],headers=headers(tokens,'fixture-c')))
    assert run_view['state']=='SUCCEEDED' and run_view['success_scope']=='LOCAL_CASE_CREATED'
    assert run_view['operation']['state']=='VERIFIED' and run_view['case']['state']=='NEEDS_INPUT'
    view=ok(api.post('/api/service-instance-cold-inputs/prepare-stage?stage=CREATE_PREPARATION',headers=headers(tokens,'fixture-c',key))) if via_api else facade.prepare_stage(tokens['fixture-c'],key,'CREATE_PREPARATION')
    stage=next(s for s in view['stages'] if s['name']=='CREATE_PREPARATION')
    p=ok(api.post('/api/preparations',headers=headers(tokens,'fixture-c',stage['request_key']),json=stage['body']),201)
    for name in ('SAVE_REQUEST','ADD_need_summary','ADD_material_outline'):
        view=ok(api.post('/api/service-instance-cold-inputs/prepare-stage?stage='+name,headers=headers(tokens,'fixture-c',key))) if via_api else facade.prepare_stage(tokens['fixture-c'],key,name)
        stage=next(s for s in view['stages'] if s['name']==name)
        suffix='/request-intent' if name=='SAVE_REQUEST' else '/commands'
        p=ok(api.post('/api/preparations/'+p['preparation_id']+suffix,headers=headers(tokens,'fixture-c',stage['request_key']),json=stage['body']))
    assert authority_snapshot(owner)==initial_authority
    material_view=ok(api.get('/api/preparations/'+p['preparation_id'],headers=headers(tokens,'fixture-c')))
    assert {m['text'] for m in material_view['current_materials']}=={m.text for m in data.fields.values()}
    assert {m['id'] for m in material_view['current_materials']}.isdisjoint(m['id'] for m in a_materials)
    assert {m['text'] for m in material_view['current_materials']}.isdisjoint(m['text'] for m in a_materials)
    assert (p['run_id']!=a_parent['run_id'] and p['case_id']!=a_parent['case_id']
            and p['preparation_id']!=a_parent['preparation_id'])
    p=ok(prep_command(f,p,'REVIEW',user='prep-specialist-fixture-c',reason='SYNTHETIC B own reviewer confirms materials'))
    p=ok(prep_command(f,p,'CONFIRM',user='fixture-c',reason='SYNTHETIC B owner explicitly confirms materials'))
    # Existing owner-only assignment is an isolated initial permission fixture,
    # never a planner/consumer operation or claimed new-Run permission feature.
    owner.assign_status('executor-c',UUID(p['run_id']),active=True)
    baseline_authority=authority_snapshot(owner)
    assert len(baseline_authority['run_assignments'])==len(initial_authority['run_assignments'])+1
    assert len(baseline_authority['run_assignments'])==len(before_A_fixture['run_assignments'])+2
    with store.connect() as c:
        principal,parent=bp._context(store,c,tokens['fixture-c'],UUID(p['preparation_id']))
        current=candidates.current(store,c,principal,parent,a['catalog'])
    assert current['selection_oracle']['state']=='UNIQUE'
    assert current['selection_oracle']['selection_variant_count']==1
    assert len(current['selection_context']['available_services'])==3
    candidate_key=uuid4().hex
    if via_api:
        api_current=ok(api.get('/api/preparations/'+p['preparation_id']+'/service-capabilities',headers=headers(tokens,'fixture-c')))
        assert all(api_current[k]==v for k,v in current.items())
        assert api_current['read_only'] and api_current['actor_ref']
    capture=candidates.Capture(expected_preparation_revision=p['revision'],expected_source_sha256=current['source_sha256'],expected_capability_catalog_sha256=current['capability_catalog_sha256'])
    candidate=ok(api.post('/api/preparations/'+p['preparation_id']+'/service-selections',headers=headers(tokens,'fixture-c',candidate_key),json=capture.model_dump()),201) if via_api else candidates.generate(store,tokens['fixture-c'],UUID(p['preparation_id']),candidate_key,capture,catalog=a['catalog'],planner=planner)
    assert candidate['can_adopt'] and candidate['producer']['version']==4 and len(calls)==1
    recovered=ok(api.get('/api/preparations/'+p['preparation_id']+'/service-selections/recovery',headers=headers(tokens,'fixture-c',candidate_key))) if via_api else candidates.read(store,tokens['fixture-c'],UUID(p['preparation_id']),key=candidate_key,catalog=a['catalog'])
    assert recovered['status']=='COMMITTED' and len(calls)==1
    path='/api/preparations/'+p['preparation_id']
    adopted=ok(api.post(path+'/service-case-plan',headers=headers(tokens,'fixture-c',uuid4().hex),json=dict(
        expected_preparation_revision=p['revision'],expected_request_revision=current['request_revision'],expected_plan_revision=0,
        expected_source_sha256=current['source_sha256'],required_goals=GOALS,reason='SYNTHETIC explicit three-capability candidate adoption',
        candidate_id=candidate['candidate_id'],expected_candidate_sha256=candidate['candidate_sha256'],expected_verification_sha256=candidate['verification_sha256'])),201)
    assert [s['adapter_id'] for s in adopted['steps']]==['P1','P2','P3','P4','P5']
    verify(f,p,'P1')
    with owner.connect() as c:now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
    hold_body=dict(starts_at=(now+timedelta(hours=1)).isoformat(),ends_at=(now+timedelta(hours=2)).isoformat(),quantity=2,expected_revision=1,ttl_seconds=300,purpose='SYNTHETIC B actual selected resources')
    holds=[ok(api.post('/api/synthetic-resources/'+id+'/holds',headers=headers(tokens,'fixture-c',uuid4().hex),json=hold_body),201)['hold'] for id in a['b_resources']]
    group=ok(api.post('/api/resource-combinations',headers=headers(tokens,'fixture-c',uuid4().hex),json=dict(members=[dict(hold_id=h['id'],expected_revision=h['resource_revision']) for h in holds])),201)['combination']
    ok(api.post(path+'/resource-link',headers=headers(tokens,'fixture-c',uuid4().hex),json=dict(combination_id=group['id'],expected_preparation_revision=p['revision'],expected_link_revision=0,reason='SYNTHETIC B actual explicit link')),201)
    verify(f,p,'P2')
    dispatch=ok(offer(f,p,user='prep-specialist-fixture-c',executor='executor-c')[0],201)
    dispatch=ok(dispatch_command(f,dispatch,'ACCEPT',user='executor-c'));verify(f,p,'P3')
    receipt=ok(api.get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(tokens,'executor-c')))
    receipt=ok(receipt_command(f,receipt,'SUBMIT',user='executor-c',text='SYNTHETIC B new executor receipt only'))
    receipt=ok(receipt_command(f,receipt,'ACKNOWLEDGE',user='fixture-c'));verify(f,p,'P4')
    local=ok(local_read(f,p,user='fixture-c'))
    ok(local_command(f,p,local,'REVALIDATE',user='fixture-c'));verify(f,p,'P5')
    results=ok(api.get(path+'/goal-results',headers=headers(tokens,'fixture-c')))
    assert results['state']=='LOCAL_OUTPUTS_VERIFIED' and len(results['results'])==6
    outputs={r['adapter_id']:r['actual_output'] for r in results['results']}
    assert outputs['P2']['combination_id']==group['id']
    assert group['id']!=a_group['id']
    assert set(a['b_resources']).isdisjoint(a_resource_ids)
    assert dispatch['dispatch_id']!=a_dispatch['dispatch_id']
    assert dispatch['current_offer']['id']!=a_dispatch['current_offer']['id']
    assert dispatch['receipt_step_id']!=a_dispatch['receipt_step_id']
    assert receipt['current_receipt']['id']!=a_receipt['current_receipt']['id']
    a_local_output=next(r['actual_output'] for r in a_results['results'] if r['adapter_id']=='P5')
    assert outputs['P5']['revalidation_event_id']!=a_local_output['revalidation_event_id']
    assert outputs['P3']['offer_id']==dispatch['current_offer']['id']
    assert outputs['P4']['receipt_id']==receipt['current_receipt']['id']
    assert results['source_trace']['candidate']['validator_version']==4 and not results['case_goal_completed']
    assert results['source_trace']['service_selection']['profile']=='TRUSTED_SERVICE_SELECTION_V4'
    assert len(results['source_trace']['service_capabilities'])==3
    assert len(results['source_trace']['park_instances'])==3
    from parkweave.template_consumer import TemplateConsumer
    from parkweave.service_capability_catalog import IsolatedServiceCapabilityCatalog
    cold_history=case_history(owner,p['preparation_id'])
    cold_store=Store(store.dsn)
    cold_consumer=TemplateConsumer(cold_store,a['engine'],a['consumer'].config,a['consumer'].repository)
    cold_store._isolated_service_capability_catalog=IsolatedServiceCapabilityCatalog(cold_consumer,owner,enabled_for_isolated_tests=True)
    assert case_goal_results.read(cold_store,tokens['fixture-c'],UUID(p['preparation_id']))==results
    assert case_history(owner,p['preparation_id'])==cold_history
    assert authority_snapshot(owner)==baseline_authority
    assert ok(api.get(path+'/goal-results',headers=headers(tokens,'fixture-a')),403)
    assert case_history(owner,a_parent['preparation_id'])==old_history
    assert ok(api.get('/api/preparations/'+a_parent['preparation_id'],headers=headers(tokens)))['current_materials']==a_materials
    unchanged_A=api.get('/api/preparations/'+a_parent['preparation_id']+'/goal-results',headers=headers(tokens))
    assert unchanged_A.status_code==200 and unchanged_A.content==a_result_bytes
    with owner.connect() as c:
        resources=c.execute('SELECT resource_id FROM synthetic_resource_holds WHERE id=ANY(%s)',([UUID(h['id']) for h in holds],)).fetchall()
        assert {str(r['resource_id']) for r in resources}==set(a['b_resources'])
    assert facade.read(tokens['fixture-c'],key)['automatic_adoption'] is False

    evidence=dict(scope='OWNED_SYNTHETIC_THREE_CAPABILITY_SECOND_PARK_LOCAL_CHAIN',
        park_id='park-b',owner_id='fixture-c',reviewer_id='prep-specialist-fixture-c',executor_id='executor-c',
        initial_fixture_resource_grant_rows=4,initial_fixture_run_assignment_rows=2,
        existing_A_history_fixture_assignment_rows=1,new_B_fixture_assignment_rows=1,
        existing_A_history_setup_uses_original_chain=True,
        existing_A_setup_is_not_new_capability_selection_acceptance=True,
        existing_A_case_id=a_parent['case_id'],existing_A_run_id=a_parent['run_id'],
        existing_A_combination_id=a_group['id'],existing_A_receipt_id=a_receipt['current_receipt']['id'],
        existing_A_results_bytes_unchanged=True,new_B_material_and_output_ids_disjoint=True,
        runtime_authority_rows_changed=0,model_http_mock_calls=len(calls),real_provider_calls=0,
        case_id=p['case_id'],preparation_id=p['preparation_id'],run_id=p['run_id'],
        candidate_id=candidate['candidate_id'],producer_version=candidate['producer']['version'],
        selected_capability_count=3,execution_adapter_ids=['P1','P2','P3','P4','P5'],
        actual_resource_ids=a['b_resources'],combination_id=group['id'],
        dispatch_offer_id=dispatch['current_offer']['id'],receipt_id=receipt['current_receipt']['id'],
        source_trace_sha256=results['source_trace']['trace_sha256'],result_state=results['state'],
        source_trace_validator_version=results['source_trace']['candidate']['validator_version'],
        original_A_history_unchanged=True,cold_store_results_equal=True,case_goal_completed=False,
        browser='NOT RUN',LIVE='NOT RUN')
    evidence['selection_and_cold_via_api']=via_api
    evidence_path=Path('.runtime/service-release-tests-20261014/full-chain-outcome-'+('api' if via_api else 'direct')+'.json')
    evidence_path.parent.mkdir(parents=True,exist_ok=True)
    evidence_path.write_text(json.dumps(evidence,indent=2)+'\n')


@pytest.mark.parametrize('restriction',['READ','PREPARE','EXECUTE','CANCELLED'])
def test_selection_api_scope_revocation_and_cancel_cannot_dispatch_model(capability_catalog,restriction):
    from fastapi.testclient import TestClient
    from parkweave.api import create_app
    from parkweave.service_selection_planner import OfflineSelectionPlanner
    from test_service_selection_candidates import arrangement,planner
    from test_case_cancellation import post as cancel_case
    a=capability_catalog;f,p,capture,_=arrangement(a);calls=[]
    with TestClient(create_app(f[0],capability_catalog=a['catalog'],selection_planner=planner(calls))) as api:
        path='/api/preparations/'+p['preparation_id']
        before=case_history(f[1],p['preparation_id'])
        for actor in ('fixture-b','fixture-c','prep-specialist-fixture-a'):
            ok(api.get(path+'/service-capabilities',headers=headers(f[2],actor)),403)
            ok(api.post(path+'/service-selections',headers=headers(f[2],actor,uuid4().hex),json=capture.model_dump()),403)
        assert case_history(f[1],p['preparation_id'])==before and calls==[]
        if restriction=='CANCELLED':
            ok(cancel_case(f,p))
        else:
            with f[1].connect() as c:
                f[1].lock_principal(c,'fixture-a',exclusive=True)
                if restriction=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
                else:c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',restriction))
        before=case_history(f[1],p['preparation_id'])
        reply=api.post(path+'/service-selections',headers=headers(f[2],'fixture-a',uuid4().hex),json=capture.model_dump())
        assert reply.status_code in (403,409),reply.text
        assert calls==[] and case_history(f[1],p['preparation_id'])==before
