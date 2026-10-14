"""Pure bounded release/configuration integrity; never a publication authority.

Callers must resolve source_review against the original TemplateCandidateStore
published release and its current source, review, permissions and head. A valid
hash or a REVIEW string alone does not establish trusted publication.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Annotated, Literal

from pydantic import Field, ValidationInfo, model_validator
from .domain import Contract, PlanID, Validity
from . import bounded_planning as planning

Hash = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
ServiceID = Literal['synthetic-material-preparation', 'synthetic-resource-coordination', 'synthetic-local-record-recheck']
Goal = Literal['LOCAL_MATERIAL_PREPARATION', 'LOCAL_CASE_RESOURCE_ASSOCIATION', 'LOCAL_INTERNAL_ACCEPTANCE', 'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT', 'LOCAL_SYNTHETIC_COORDINATION_RECORDS', 'LOCAL_CASE_RECORD_RECHECK']
Role = Literal['enterprise_operator', 'park_specialist', 'service_executor']
Slot = Literal['need_summary', 'material_outline']
ResourceKey = Literal['primary', 'secondary']
SERVICE_GOALS = {
    'synthetic-material-preparation': {'LOCAL_MATERIAL_PREPARATION'},
    'synthetic-resource-coordination': {'LOCAL_CASE_RESOURCE_ASSOCIATION', 'LOCAL_INTERNAL_ACCEPTANCE', 'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT', 'LOCAL_SYNTHETIC_COORDINATION_RECORDS'},
    'synthetic-local-record-recheck': {'LOCAL_CASE_RECORD_RECHECK'},
}
GOAL_TARGETS = {'LOCAL_MATERIAL_PREPARATION':'P1','LOCAL_CASE_RESOURCE_ASSOCIATION':'P2','LOCAL_INTERNAL_ACCEPTANCE':'P3','LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT':'P4','LOCAL_SYNTHETIC_COORDINATION_RECORDS':'P4','LOCAL_CASE_RECORD_RECHECK':'P5'}
# Revision 1 has these immutable executor/action bindings, not arbitrary routes.
REVISION_ONE_BINDINGS = {'P1':('preparation',[]),'P2':('case-resources',['P1']),'P3':('dispatch',['P2']),'P4':('executor-receipts',['P3']),'P5':('case-lifecycle',['P4'])}
# Historical revision-one semantics must also survive a fresh process importing
# a later current registry. These are version facts, not a current registry copy.
REVISION_ONE_ACTIONS = {
 'P1':[{'method':'POST','path':'/api/preparations/{preparation_id}/commands','role':'enterprise_operator','commands':['ADD_EVIDENCE','CONFIRM']},{'method':'POST','path':'/api/preparations/{preparation_id}/commands','role':'park_specialist','commands':['REQUEST_CHANGES','REVIEW']}],
 'P2':[{'method':'POST','path':'/api/preparations/{preparation_id}/resource-link','role':'enterprise_operator','commands':['CREATE_OR_RECHECK_LINK']}],
 'P3':[{'method':'POST','path':'/api/preparations/{preparation_id}/dispatch','role':'park_specialist','commands':['OFFER']},{'method':'POST','path':'/api/service-dispatches/{dispatch_id}/commands','role':'service_executor','commands':['ACCEPT','DECLINE']}],
 'P4':[{'method':'POST','path':'/api/executor-receipts/{step_id}/commands','role':'service_executor','commands':['SUBMIT']},{'method':'POST','path':'/api/executor-receipts/{step_id}/commands','role':'enterprise_operator','commands':['ACKNOWLEDGE','REQUEST_CHANGES','REOPEN']}],
 'P5':[{'method':'POST','path':'/api/preparations/{preparation_id}/local-case/commands','role':'enterprise_operator','commands':['REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN']}],
}
CHECKS = {'P1':'MATERIAL_REVIEW', 'P2':'RESOURCE_RECHECK', 'P3':'ACCEPTANCE_RECHECK', 'P4':'RECEIPT_RECHECK', 'P5':'LOCAL_RECORD_RECHECK'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode('utf-8')).hexdigest()


def hash_release(value):
    return digest({k:v for k,v in value.items() if k != 'release_sha256'})


def hash_instance(value):
    return digest({k:v for k,v in value.items() if k != 'config_sha256'})


class SourceReview(Contract):
    template_release_id: PlanID
    template_release_sha256: Hash
    definition_sha256: Hash
    registry_sha256: Hash
    review_revision: int = Field(ge=1, le=64)
    review_action: Literal['REVIEW']
    source_id: PlanID
    source_revision: str = Field(pattern=r'^[1-9][0-9]{0,5}$')
    source_sha256: Hash
    validity: Validity


class RegisteredStep(Contract):
    id: Literal['P1','P2','P3','P4','P5']
    adapter: Literal['preparation','case-resources','dispatch','executor-receipts','case-lifecycle']
    revision: Literal[1]
    depends_on: list[Literal['P1','P2','P3','P4','P5']] = Field(max_length=4)
    responsibility: str = Field(min_length=1, max_length=2000)
    preconditions: str = Field(min_length=1, max_length=2000)
    output: str = Field(min_length=1, max_length=2000)
    acceptance: str = Field(min_length=1, max_length=2000)


class MaterialRequirement(Contract):
    field_key: Slot
    purpose: Literal['CURRENT_CASE_MATERIAL_PREPARATION']


class ResourceRequirement(Contract):
    resource_key: ResourceKey
    required: Literal[True]


class ServiceRelease(Contract):
    schema_version: Literal[1]
    service_id: ServiceID
    release_id: PlanID
    revision: int = Field(ge=1, le=64)
    owner_org_id: PlanID
    title: str = Field(min_length=1, max_length=160)
    supported_goals: list[Goal] = Field(min_length=1, max_length=6)
    steps: list[RegisteredStep] = Field(min_length=1, max_length=5)
    role_keys: list[Role] = Field(min_length=1, max_length=3)
    resource_keys: list[ResourceKey] = Field(max_length=2)
    field_keys: list[Slot] = Field(min_length=1, max_length=2)
    material_requirements: list[MaterialRequirement] = Field(min_length=1, max_length=2)
    resource_requirements: list[ResourceRequirement] = Field(max_length=2)
    completion_checks: list[str] = Field(min_length=1, max_length=5)
    validity: Validity
    source_review: SourceReview
    business_publication: Literal[False]
    release_sha256: Hash

    @model_validator(mode='after')
    def registered(self, info: ValidationInfo):
        if not self.title.strip():
            raise ValueError('nonblank release title required')
        if len(set(self.supported_goals)) != len(self.supported_goals) or not set(self.supported_goals) <= SERVICE_GOALS[self.service_id]:
            raise ValueError('distinct goals of the finite service kind required')
        historical = bool(info.context and info.context.get('historical'))
        if historical:
            registry,actions = info.context['registry'],info.context['actions']
            expected = _frozen_closure(self.supported_goals, registry, actions)
        else:
            registry,actions = planning.REGISTRY,planning.ACTIONS
            _, expected = planning.compile(self.supported_goals)
        if [s.model_dump() for s in self.steps] != expected:
            raise ValueError('exact current registered adapter dependency closure required')
        ids = [s.id for s in self.steps]
        roles = sorted({action['role'] for id in ids for action in actions[id]})
        resources = ['primary','secondary'] if 'P2' in ids else []
        fields = ['need_summary','material_outline']
        if self.role_keys != roles or self.resource_keys != resources or self.field_keys != fields:
            raise ValueError('exact registered logical mapping keys required')
        if [r.model_dump() for r in self.material_requirements] != [dict(field_key=f, purpose='CURRENT_CASE_MATERIAL_PREPARATION') for f in fields]:
            raise ValueError('all original material input requirements required')
        if [r.model_dump() for r in self.resource_requirements] != [dict(resource_key=r,required=True) for r in resources]:
            raise ValueError('all original resource requirements required')
        if self.completion_checks != [CHECKS[id] for id in ids]:
            raise ValueError('registered local completion checks required')
        if self.source_review.registry_sha256 != digest(dict(steps=registry, actions=actions)):
            raise ValueError('reviewed registry hash changed')
        if not _within(self.validity.model_dump(), self.source_review.validity.model_dump()):
            raise ValueError('release interval must be within reviewed source interval')
        # Literal accepts bool as 1 in Pydantic; reject this before hashing too.
        if (type(self.schema_version) is not int or type(self.business_publication) is not bool
                or any(type(s.revision) is not int for s in self.steps)
                or any(type(r.required) is not bool for r in self.resource_requirements)):
            raise ValueError('integer contract and adapter revisions required')
        if hash_release(self.model_dump(mode='json')) != self.release_sha256:
            raise ValueError('immutable release hash changed')
        return self


class InstanceSource(Contract):
    kind: Literal['SYNTHETIC']
    id: PlanID
    revision: str = Field(pattern=r'^[1-9][0-9]{0,5}$')
    validity: Validity


class FieldMapping(Contract):
    slot: Slot
    input_field: PlanID


class ParkInstance(Contract):
    schema_version: Literal[1]
    instance_id: PlanID
    park_id: PlanID
    release_id: PlanID
    release_sha256: Hash
    config_revision: int = Field(ge=1, le=64)
    roles: dict[Role, PlanID] = Field(min_length=1, max_length=3)
    resources: dict[ResourceKey, PlanID] = Field(max_length=2)
    fields: dict[Slot, FieldMapping] = Field(min_length=1, max_length=2)
    source: InstanceSource
    new_grants: Literal[False]
    config_sha256: Hash

    @model_validator(mode='after')
    def integrity(self):
        if type(self.schema_version) is not int or type(self.new_grants) is not bool:
            raise ValueError('integer instance schema and boolean authority flag required')
        if len(set(self.roles.values())) != len(self.roles) or len(set(self.resources.values())) != len(self.resources):
            raise ValueError('distinct existing principal/resource mappings required')
        if any(v.slot != key for key,v in self.fields.items()) or len({v.input_field for v in self.fields.values()}) != len(self.fields):
            raise ValueError('distinct bounded input fields must preserve original slot semantics')
        if hash_instance(self.model_dump(mode='json')) != self.config_sha256:
            raise ValueError('immutable instance configuration hash changed')
        return self


def _within(inner, outer):
    return datetime.fromisoformat(outer['valid_from']) <= datetime.fromisoformat(inner['valid_from']) < datetime.fromisoformat(inner['valid_until']) <= datetime.fromisoformat(outer['valid_until'])


def _effective(validity, now):
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError('aware validation clock required')
    if not datetime.fromisoformat(validity['valid_from']) <= now < datetime.fromisoformat(validity['valid_until']):
        raise ValueError('current effective source/release interval required')


def validate_release(data, *, now=None):
    """Validate integrity/time only; caller must separately resolve publication."""
    value = ServiceRelease.model_validate(deepcopy(data)).model_dump(mode='json')
    _effective(value['validity'], now)
    _effective(value['source_review']['validity'], now)
    return value


def validate_instance(data, release, *, now=None):
    value = ParkInstance.model_validate(deepcopy(data)).model_dump(mode='json')
    release = validate_release(release, now=now)
    if value['release_id'] != release['release_id'] or value['release_sha256'] != release['release_sha256']:
        raise ValueError('exact immutable release binding required')
    if any(set(value[k]) != set(release[key]) for k,key in [('roles','role_keys'),('resources','resource_keys'),('fields','field_keys')]):
        raise ValueError('complete exact registered mapping required')
    _effective(value['source']['validity'], now)
    return value


def _frozen_closure(goals, registry, actions):
    """Independent revision-one oracle for an authenticated saved profile.

    This checks integrity only. The caller authenticates that the profile is
    the immutable one recorded at original adoption, never a client proposal.
    """
    if not isinstance(registry,list) or len(registry)!=5 or not isinstance(actions,dict) or actions!=REVISION_ONE_ACTIONS:
        raise ValueError('complete frozen revision-one registered profile required')
    nodes=[RegisteredStep.model_validate(s).model_dump() for s in registry]
    if [s['id'] for s in nodes]!=list(REVISION_ONE_BINDINGS):
        raise ValueError('exact frozen registered node identities required')
    for node in nodes:
        adapter,deps=REVISION_ONE_BINDINGS[node['id']]
        if node['adapter']!=adapter or node['depends_on']!=deps or type(node['revision']) is not int:
            raise ValueError('immutable revision-one adapter/dependency binding required')
    by_id={s['id']:s for s in nodes}
    selected=set()
    def include(id):
        if id not in selected:
            selected.add(id)
            for dep in by_id[id]['depends_on']:include(dep)
    for goal in goals:include(GOAL_TARGETS[goal])
    return [s for s in nodes if s['id'] in selected]


def validate_release_integrity(data, registry, actions, *, accepted_at=None):
    """Historical saved-profile integrity, with no current authorization.

    Never use this to admit a new selection/adoption. Current admission uses
    validate_release plus original publication/authorization resolution.
    """
    value=ServiceRelease.model_validate(deepcopy(data),context=dict(historical=True,registry=deepcopy(registry),actions=deepcopy(actions))).model_dump(mode='json')
    if accepted_at is not None:
        _effective(value['validity'],accepted_at)
        _effective(value['source_review']['validity'],accepted_at)
    return value


def validate_instance_integrity(data, release, registry, actions, *, accepted_at=None):
    value=ParkInstance.model_validate(deepcopy(data)).model_dump(mode='json')
    release=validate_release_integrity(release,registry,actions,accepted_at=accepted_at)
    if value['release_id']!=release['release_id'] or value['release_sha256']!=release['release_sha256']:
        raise ValueError('exact historical immutable release binding required')
    if any(set(value[k])!=set(release[key]) for k,key in [('roles','role_keys'),('resources','resource_keys'),('fields','field_keys')]):
        raise ValueError('complete historical registered mapping required')
    if accepted_at is not None:_effective(value['source']['validity'],accepted_at)
    return value
