from copy import deepcopy
from datetime import datetime, timezone
import pytest
from parkweave import service_capability_contract as contract
from parkweave import bounded_planning as bp

NOW = datetime(2026,10,14,tzinfo=timezone.utc)
INTERVAL = dict(valid_from='2026-01-01T00:00:00+00:00',valid_until='2027-01-01T00:00:00+00:00',timezone='UTC')


def fixture_release(service_id='synthetic-material-preparation', goals=None):
    goals = list(contract.SERVICE_GOALS[service_id]) if goals is None else goals
    goals.sort()
    _,steps = bp.compile(goals)
    ids = [s['id'] for s in steps]
    fields = ['need_summary','material_outline']
    resources = ['primary','secondary'] if 'P2' in ids else []
    value = dict(schema_version=1,service_id=service_id,release_id='release-'+service_id,revision=1,owner_org_id='synthetic-service-owner',title='Synthetic reviewed capability',supported_goals=goals,steps=steps,
        role_keys=sorted({a['role'] for id in ids for a in bp.ACTIONS[id]}),field_keys=fields,resource_keys=resources,
        material_requirements=[dict(field_key=f,purpose='CURRENT_CASE_MATERIAL_PREPARATION') for f in fields],resource_requirements=[dict(resource_key=r,required=True) for r in resources],completion_checks=[contract.CHECKS[id] for id in ids],validity=deepcopy(INTERVAL),
        source_review=dict(template_release_id='original-template-release',template_release_sha256='a'*64,definition_sha256='b'*64,registry_sha256=contract.digest(dict(steps=bp.REGISTRY,actions=bp.ACTIONS)),review_revision=3,review_action='REVIEW',source_id='synthetic-reviewed-source',source_revision='1',source_sha256='c'*64,validity=deepcopy(INTERVAL)),business_publication=False)
    value['release_sha256'] = contract.hash_release(value)
    return value


def fixture_instance(release,park='park-a'):
    value = dict(schema_version=1,instance_id=park+'-instance',park_id=park,release_id=release['release_id'],release_sha256=release['release_sha256'],config_revision=1,roles={r:park+'-'+r for r in release['role_keys']},resources={r:park+'-'+r for r in release['resource_keys']},fields={f:dict(slot=f,input_field=park+'-'+f) for f in release['field_keys']},source=dict(kind='SYNTHETIC',id=park+'-mapping-source',revision='1',validity=deepcopy(INTERVAL)),new_grants=False)
    value['config_sha256'] = contract.hash_instance(value)
    return value


@pytest.mark.parametrize('service',list(contract.SERVICE_GOALS))
def test_three_finite_contracts_have_exact_closure_and_canonical_hash(service):
    release = fixture_release(service)
    assert contract.validate_release(release,now=NOW) == release
    instance = fixture_instance(release)
    assert contract.validate_instance(instance,release,now=NOW) == instance
    assert contract.digest(dict(b=2,a=1)) == contract.digest(dict(a=1,b=2))


def test_separate_park_maps_change_only_configuration_no_case_data():
    release=fixture_release('synthetic-resource-coordination')
    a,b=fixture_instance(release),fixture_instance(release,'park-b')
    b['fields']={f:dict(slot=f,input_field='second-park-'+f) for f in release['field_keys']}
    b['config_sha256']=contract.hash_instance(b)
    assert contract.validate_instance(a,release,now=NOW)['release_sha256']==contract.validate_instance(b,release,now=NOW)['release_sha256']
    assert a['config_sha256']!=b['config_sha256']


@pytest.mark.parametrize('path,value',[
    (['service_id'],'arbitrary-free-script'),(['supported_goals'],['UNSUPPORTED_REAL_DELIVERY']),
    (['supported_goals'],['LOCAL_MATERIAL_PREPARATION','LOCAL_MATERIAL_PREPARATION']),
    (['steps',0,'adapter'],'shell'),(['steps',0,'revision'],2),
    (['steps',0,'depends_on'],['P5']),(['steps',0,'output'],'real business fulfillment'),
    (['source_review','review_action'],'DRAFT'),(['source_review','registry_sha256'],'0'*64),
    (['source_review','review_revision'],True),(['revision'],True),
    (['schema_version'],True),(['business_publication'],0),(['steps',0,'revision'],True),
    (['field_keys'],['need_summary']),(['role_keys'],['enterprise_operator']),
    (['material_requirements'],[]),(['completion_checks'],['EXTERNAL_FULFILLED']),
    (['validity','valid_until'],'2028-01-01T00:00:00+00:00'),
])
def test_release_rejects_resigned_unsupported_or_incomplete_semantics(path,value):
    release=fixture_release()
    target=release
    for key in path[:-1]: target=target[key]
    target[path[-1]]=value
    release['release_sha256']=contract.hash_release(release)
    with pytest.raises(ValueError):contract.validate_release(release,now=NOW)


@pytest.mark.parametrize('extra', ['grant','session','credential','material_history','case_id','results','tools','script'])
def test_no_grant_credential_old_case_or_executable_payload(extra):
    release=fixture_release();release[extra]='forbidden'
    release['release_sha256']=contract.hash_release(release)
    with pytest.raises(ValueError):contract.validate_release(release,now=NOW)
    release=fixture_release();instance=fixture_instance(release);instance[extra]='forbidden'
    instance['config_sha256']=contract.hash_instance(instance)
    with pytest.raises(ValueError):contract.validate_instance(instance,release,now=NOW)


@pytest.mark.parametrize('mutator', [
    lambda v:v.update(release_sha256='0'*64),lambda v:v.update(release_id='another-release'),
    lambda v:v['roles'].update(service_executor='invented-executor'),
    lambda v:v['fields']['need_summary'].update(slot='unknown-slot'),
    lambda v:v['fields']['need_summary'].update(slot='material_outline'),
    lambda v:v['fields']['need_summary'].update(input_field=v['fields']['material_outline']['input_field']),
    lambda v:v['roles'].update(park_specialist=v['roles']['enterprise_operator']),
    lambda v:v['source'].update(kind='AUTHORIZED_REAL'),
    lambda v:v.update(config_revision=True),lambda v:v.update(new_grants=0),lambda v:v.update(schema_version=True),
])
def test_resigned_instance_mismatch_rejected(mutator):
    release=fixture_release();instance=fixture_instance(release);mutator(instance)
    instance['config_sha256']=contract.hash_instance(instance)
    with pytest.raises(ValueError):contract.validate_instance(instance,release,now=NOW)


@pytest.mark.parametrize('when', [datetime(2025,12,31,tzinfo=timezone.utc),datetime(2027,1,1,tzinfo=timezone.utc),datetime(2026,10,14)])
def test_effective_interval_and_aware_clock(when):
    with pytest.raises(ValueError):contract.validate_release(fixture_release(),now=when)


def test_immutable_hash_protects_title_and_mapping_changes_and_no_input_mutation():
    release=fixture_release();old=deepcopy(release)
    contract.validate_release(release,now=NOW)
    assert release==old
    release['title']='changed'
    with pytest.raises(ValueError):contract.validate_release(release,now=NOW)
    release=old;instance=fixture_instance(release);instance['roles']['enterprise_operator']='new-owner'
    with pytest.raises(ValueError):contract.validate_instance(instance,release,now=NOW)


def test_source_and_instance_expiry_do_not_infer_false_goal_satisfaction():
    release=fixture_release();instance=fixture_instance(release)
    instance['source']['validity']['valid_until']='2026-10-14T00:00:00+00:00'
    instance['config_sha256']=contract.hash_instance(instance)
    with pytest.raises(ValueError):contract.validate_instance(instance,release,now=NOW)


def test_resource_requirements_cannot_be_dropped_or_optionalized():
    release=fixture_release('synthetic-resource-coordination')
    release['resource_requirements'][0]['required']=False
    release['release_sha256']=contract.hash_release(release)
    with pytest.raises(ValueError):contract.validate_release(release,now=NOW)


def test_boolean_integer_resource_flag_cannot_pass_literal():
    release=fixture_release('synthetic-resource-coordination')
    release['resource_requirements'][0]['required']=1
    release['release_sha256']=contract.hash_release(release)
    with pytest.raises(ValueError):contract.validate_release(release,now=NOW)


def test_historical_integrity_keeps_original_profile_when_current_registry_changes(monkeypatch):
    release=fixture_release('synthetic-local-record-recheck');instance=fixture_instance(release)
    registry,actions=deepcopy(bp.REGISTRY),deepcopy(bp.ACTIONS)
    current=deepcopy(bp.REGISTRY);current[0]['output']='new revision description'
    monkeypatch.setattr(bp,'REGISTRY',current)
    with pytest.raises(ValueError):contract.validate_release(release,now=NOW)
    assert contract.validate_release_integrity(release,registry,actions,accepted_at=NOW)==release
    assert contract.validate_instance_integrity(instance,release,registry,actions,accepted_at=NOW)==instance
    # Historical integrity by itself grants no new admission and has no today clock.
    assert contract.validate_release_integrity(release,registry,actions)==release
    with pytest.raises(ValueError):contract.validate_release_integrity(release,registry,actions,accepted_at=datetime(2028,1,1,tzinfo=timezone.utc))


@pytest.mark.parametrize('mutator',[
    lambda registry,actions:registry.pop(),
    lambda registry,actions:registry[0].update(adapter='shell'),
    lambda registry,actions:registry[0].update(revision=2),
    lambda registry,actions:registry[0].update(depends_on=['P5']),
    lambda registry,actions:actions['P1'][0].update(path='/unsafe'),
    lambda registry,actions:registry[0].update(output='different saved material'),
])
def test_historical_profile_is_exact_frozen_and_bounded(mutator):
    release=fixture_release();registry,actions=deepcopy(bp.REGISTRY),deepcopy(bp.ACTIONS)
    mutator(registry,actions)
    with pytest.raises(ValueError):contract.validate_release_integrity(release,registry,actions,accepted_at=NOW)
