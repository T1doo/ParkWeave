"""Pure selection oracle tests: zero provider, execution, database or sockets."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import pytest

from parkweave import bounded_planning as bp
from parkweave.service_capability_contract import digest, hash_release, hash_instance, CHECKS
from parkweave.service_selection import SelectionError, enumerate_solutions, parse_selection, rebuild_selection, selection_ref

NOW = datetime(2026, 10, 14, tzinfo=timezone.utc)
INTERVAL = dict(valid_from='2026-01-01T00:00:00+00:00', valid_until='2027-01-01T00:00:00+00:00',timezone='UTC')


def release(service='synthetic-material-preparation', goals=None, suffix='a'):
    goals = goals or ['LOCAL_MATERIAL_PREPARATION']
    _, steps = bp.compile(goals)
    fields = ['need_summary', 'material_outline']
    resources = ['primary', 'secondary'] if any(s['id'] == 'P2' for s in steps) else []
    data = dict(schema_version=1,service_id=service,release_id='release-'+suffix,revision=1,owner_org_id='owner-a',title='合成目录',supported_goals=goals,steps=steps,
                role_keys=sorted({a['role'] for s in steps for a in bp.ACTIONS[s['id']]}),resource_keys=resources,field_keys=fields,
                material_requirements=[dict(field_key=f,purpose='CURRENT_CASE_MATERIAL_PREPARATION') for f in fields],
                resource_requirements=[dict(resource_key=r,required=True) for r in resources],completion_checks=[CHECKS[s['id']] for s in steps],validity=INTERVAL,
                source_review=dict(template_release_id='template-a',template_release_sha256='a'*64,definition_sha256='b'*64,registry_sha256=digest(dict(steps=bp.REGISTRY,actions=bp.ACTIONS)),review_revision=1,review_action='REVIEW',source_id='source-a',source_revision='1',source_sha256='c'*64,validity=INTERVAL),business_publication=False)
    data['release_sha256'] = hash_release(data)
    return data


def instance(r, suffix='a', park='park-a'):
    data = dict(schema_version=1,instance_id='instance-'+suffix,park_id=park,release_id=r['release_id'],release_sha256=r['release_sha256'],config_revision=1,
                roles={k:'principal-'+k for k in r['role_keys']},resources={k:'resource-'+k for k in r['resource_keys']},fields={k:dict(slot=k,input_field=k) for k in r['field_keys']},
                source=dict(kind='SYNTHETIC',id='source-instance-'+suffix,revision='1',validity=INTERVAL),new_grants=False)
    data['config_sha256'] = hash_instance(data)
    return data


def request(goals=None):
    return dict(park_id='park-a',required_goals=goals or ['LOCAL_MATERIAL_PREPARATION'],planning_constraints=dict(excluded_roles=[],additional_requirements=[]),mapping_states=dict(
        principals={ 'principal-'+r:'TRUE' for r in ('enterprise_operator','park_specialist','service_executor')},resources={ 'resource-'+r:'TRUE' for r in ('primary','secondary')},fields={r:'TRUE' for r in ('need_summary','material_outline')}))


BINDING = dict(request_revision=1, source_sha256='a'*64, catalog_sha256='b'*64, registry_sha256='c'*64)


def test_unique_is_actual_single_solution_and_trusted_reconstruction():
    r=release(); i=instance(r); req=request()
    oracle=enumerate_solutions([r],[i],req,now=NOW)
    assert oracle['state']=='UNIQUE' and oracle['examined_subsets']==1
    assert oracle['minimal_solutions']==[[selection_ref(r,i)]]
    selection=dict(schema_version=1,binding=BINDING,selections=[selection_ref(r,i)])
    rebuilt=rebuild_selection(selection,[r],[i],req,BINDING,now=NOW)
    assert len(rebuilt['steps'])==1 and rebuilt['steps'][0]['actions']==bp.ACTIONS['P1']
    assert rebuilt['steps'][0]['service_refs']==[selection_ref(r,i)]
    assert rebuilt['execution_enabled'] is False
    rebuilt['steps'][0]['actions'][0]['commands'].append('MALICIOUS')
    assert 'MALICIOUS' not in bp.ACTIONS['P1'][0]['commands']


def test_two_actual_equivalent_releases_are_two_minimal_solutions_not_synthetic_diagrams():
    rs=[release(suffix='a'),release(suffix='b')]; ins=[instance(r,suffix=s) for r,s in zip(rs,('a','b'))]
    oracle=enumerate_solutions(rs,ins,request(),now=NOW)
    assert oracle['state']=='MULTIPLE' and len(oracle['minimal_solutions'])==2
    assert all(len(s)==1 for s in oracle['minimal_solutions'])
    assert oracle['selection_variant_count']==2 and oracle['distinct_execution_graphs']==1


def test_cross_service_goal_coverage_combines_closure_and_stable_adapter_refs():
    rs=[release(),release('synthetic-resource-coordination',['LOCAL_INTERNAL_ACCEPTANCE'],'b')]
    ins=[instance(r,suffix=s) for r,s in zip(rs,('a','b'))]
    req=request(['LOCAL_MATERIAL_PREPARATION','LOCAL_INTERNAL_ACCEPTANCE'])
    oracle=enumerate_solutions(rs,ins,req,now=NOW)
    assert oracle['state']=='UNIQUE' and len(oracle['minimal_solutions'][0])==2
    value=rebuild_selection(dict(schema_version=1,binding=BINDING,selections=oracle['minimal_solutions'][0]),rs,ins,req,BINDING,now=NOW)
    assert [s['id'] for s in value['steps']]==['P1','P2','P3']
    assert len(value['steps'][0]['service_refs'])==2
    assert value['required_goals']==req['required_goals']


@pytest.mark.parametrize('state,expected',[('FALSE','UNSAT'),('UNKNOWN','UNKNOWN')])
def test_mapping_reference_unknown_is_not_false_or_verified(state,expected):
    r=release(); i=instance(r); req=request(); req['mapping_states']['fields']['need_summary']=state
    value=enumerate_solutions([r],[i],req,now=NOW)
    assert value['state']==expected and value['minimal_solutions']==[]
    assert bool(value['unknowns']) == (state=='UNKNOWN')


def test_missing_reference_state_stays_unknown():
    r=release(); i=instance(r); req=request(); del req['mapping_states']
    assert enumerate_solutions([r],[i],req,now=NOW)['state']=='UNKNOWN'


def test_unsupported_goal_preserved_and_never_partial_adopt():
    r=release(); i=instance(r); req=request(['LOCAL_MATERIAL_PREPARATION','REAL_FULFILMENT'])
    value=enumerate_solutions([r],[i],req,now=NOW)
    assert value['state']=='UNSUPPORTED' and value['required_goals']==req['required_goals']
    assert value['unsupported_goals']==['REAL_FULFILMENT']
    with pytest.raises(SelectionError):
        rebuild_selection(dict(schema_version=1,binding=BINDING,selections=[selection_ref(r,i)]),[r],[i],req,BINDING,now=NOW)


def test_other_park_instance_is_unsatisfiable_not_unknown_or_unsupported():
    r=release(); i=instance(r,park='park-b')
    assert enumerate_solutions([r],[i],request(),now=NOW)['state']=='UNSAT'


@pytest.mark.parametrize('constraint,expected',[(dict(excluded_roles=['park_specialist'],additional_requirements=[]),'UNSAT'),(dict(excluded_roles=[],additional_requirements=['真实交付保证']),'UNKNOWN')])
def test_hard_constraints_not_erased(constraint,expected):
    r=release(); i=instance(r); req=request();req['planning_constraints']=constraint
    assert enumerate_solutions([r],[i],req,now=NOW)['state']==expected


def test_merge_semantic_mapping_conflict_rejects_covering_set():
    rs=[release(),release('synthetic-resource-coordination',['LOCAL_INTERNAL_ACCEPTANCE'],'b')]
    ins=[instance(r,suffix=s) for r,s in zip(rs,('a','b'))]
    ins[1]['roles']['enterprise_operator']='principal-different';ins[1]['config_sha256']=hash_instance(ins[1])
    req=request(['LOCAL_MATERIAL_PREPARATION','LOCAL_INTERNAL_ACCEPTANCE']);req['mapping_states']['principals']['principal-different']='TRUE'
    assert enumerate_solutions(rs,ins,req,now=NOW)['state']=='UNSAT'


@pytest.mark.parametrize('mutation',[
    lambda v:v.update(steps=[]), lambda v:v.update(actions=[]), lambda v:v.update(required_goals=[]),
    lambda v:v['binding'].update(source_sha256='d'*64), lambda v:v['selections'][0].update(revision=True),
    lambda v:v['selections'][0].update(config_sha256='D'*64), lambda v:v['selections'].append(deepcopy(v['selections'][0])),
    lambda v:v['selections'][0].update(authority='execute'), lambda v:v.update(schema_version=True),
])
def test_compact_dsl_forbids_model_authority_sources_and_goal_drop(mutation):
    r=release();i=instance(r);v=dict(schema_version=1,binding=deepcopy(BINDING),selections=[selection_ref(r,i)])
    mutation(v)
    with pytest.raises(SelectionError):parse_selection(json.dumps(v),BINDING)


def test_duplicate_json_key_rejected():
    with pytest.raises(SelectionError):parse_selection('{"schema_version":1,"schema_version":1,"binding":{},"selections":[]}',{})


def test_nonminimal_selection_is_rejected_even_if_coverage_sufficient():
    rs=[release(suffix='a'),release(suffix='b')];ins=[instance(r,suffix=s) for r,s in zip(rs,('a','b'))]
    with pytest.raises(SelectionError):
        rebuild_selection(dict(schema_version=1,binding=BINDING,selections=[selection_ref(r,i) for r,i in zip(rs,ins)]),rs,ins,request(),BINDING,now=NOW)


def test_unknown_superset_does_not_destroy_known_minimal_solution():
    rs=[release(suffix='a'),release(suffix='b')];ins=[instance(r,suffix=s) for r,s in zip(rs,('a','b'))]
    ins[1]['roles']['enterprise_operator']='unknown-owner';ins[1]['config_sha256']=hash_instance(ins[1])
    oracle=enumerate_solutions(rs,ins,request(),now=NOW)
    assert oracle['state']=='UNKNOWN' and len(oracle['minimal_solutions'])==1 and len(oracle['unknown_solutions'])==1


def test_oracle_does_not_call_builder(monkeypatch):
    import parkweave.service_selection as module
    monkeypatch.setattr(module,'rebuild_selection',lambda *a,**k:pytest.fail('builder used as oracle'))
    r=release();i=instance(r)
    assert module.enumerate_solutions([r],[i],request(),now=NOW)['state']=='UNIQUE'


def test_second_park_different_existing_principal_resource_and_input_field_mapping():
    r=release('synthetic-local-record-recheck',['LOCAL_CASE_RECORD_RECHECK'])
    i=instance(r,park='park-b');req=request(['LOCAL_CASE_RECORD_RECHECK']);req['park_id']='park-b'
    i['roles']={key:'park-b-'+key for key in i['roles']}
    i['resources']={key:'park-b-resource-'+key for key in i['resources']}
    i['fields']={key:dict(slot=key,input_field='park-b-input-'+key) for key in i['fields']}
    i['config_sha256']=hash_instance(i)
    req['mapping_states']=dict(principals={v:'TRUE' for v in i['roles'].values()},resources={v:'TRUE' for v in i['resources'].values()},fields={v['input_field']:'TRUE' for v in i['fields'].values()})
    refs=[selection_ref(r,i)]
    result=rebuild_selection(dict(schema_version=1,binding=BINDING,selections=refs),[r],[i],req,BINDING,now=NOW)
    assert result['oracle']['state']=='UNIQUE'
    assert [s['id'] for s in result['steps']]==['P1','P2','P3','P4','P5']
    assert result['steps'][0]['instance_mappings'][0]['fields']['need_summary']==dict(slot='need_summary',input_field='park-b-input-need_summary')
    assert result['steps'][0]['actions']==bp.ACTIONS['P1']


@pytest.mark.parametrize('key,value', [('selections',[]),('schema_version',2),('binding',None)])
def test_empty_or_unknown_compact_schema_rejected(key,value):
    r=release();i=instance(r);v=dict(schema_version=1,binding=BINDING,selections=[selection_ref(r,i)]);v[key]=value
    with pytest.raises(SelectionError):parse_selection(json.dumps(v),BINDING)


@pytest.mark.parametrize('change',[
    lambda r:r['steps'][0].update(adapter='case-lifecycle'),
    lambda r:r['steps'][0].update(revision=2),
    lambda r:r['steps'][0].update(depends_on=['P1']),
    lambda r:r.update(steps=[]),
])
def test_oracle_independently_refuses_invalid_adapter_dependency_and_missing_coverage(monkeypatch,change):
    # Bypass the separate structural validator to test the oracle's independent
    # adapter/dependency/target checks; neither compiler nor builder supplies it.
    import parkweave.service_capability_contract as contract
    r=release();i=instance(r);change(r)
    monkeypatch.setattr(contract,'validate_release',lambda v,**k:deepcopy(v))
    monkeypatch.setattr(contract,'validate_instance',lambda v,*a,**k:deepcopy(v))
    assert enumerate_solutions([r],[i],request(),now=NOW)['state']=='UNSAT'


def test_trusted_current_collection_addition_changes_unique_to_multiple():
    first=release();one=instance(first)
    assert enumerate_solutions([first],[one],request(),now=NOW)['state']=='UNIQUE'
    second=release(suffix='b');two=instance(second,suffix='b')
    assert enumerate_solutions([first,second],[one,two],request(),now=NOW)['state']=='MULTIPLE'


def test_exact_config_or_release_hash_tampering_cannot_select_valid_current_ref():
    r=release();i=instance(r);v=dict(schema_version=1,binding=BINDING,selections=[selection_ref(r,i)])
    v['selections'][0]['release_sha256']='d'*64
    with pytest.raises(SelectionError):rebuild_selection(v,[r],[i],request(),BINDING,now=NOW)


def test_duplicate_catalog_instance_and_release_rejected():
    r=release();i=instance(r)
    with pytest.raises(SelectionError):enumerate_solutions([r,r],[i],request(),now=NOW)
    with pytest.raises(SelectionError):enumerate_solutions([r],[i,i],request(),now=NOW)


@pytest.mark.parametrize('states',[{'fields':{'need_summary':True}}, {'unknown_group':{}}, []])
def test_mapping_truth_requires_explicit_three_valued_current_reference_states(states):
    r=release();i=instance(r);req=request();req['mapping_states']=states
    with pytest.raises(SelectionError):enumerate_solutions([r],[i],req,now=NOW)
