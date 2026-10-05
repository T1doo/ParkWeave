"""Strict versioned contracts for this bounded increment, not all V1 features."""
from enum import StrEnum
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Truth(StrEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


def conjunction(values: list[Truth]) -> Truth:
    if Truth.FALSE in values:
        return Truth.FALSE
    return Truth.UNKNOWN if Truth.UNKNOWN in values else Truth.TRUE


def disjunction(values: list[Truth]) -> Truth:
    if Truth.TRUE in values:
        return Truth.TRUE
    return Truth.UNKNOWN if Truth.UNKNOWN in values else Truth.FALSE


class SourceRef(Contract):
    id: str = Field(min_length=1, max_length=120)
    kind: Literal["SYNTHETIC", "PUBLIC", "AUTHORIZED_REAL"]
    revision: str = Field(min_length=1, max_length=120)


class ActionSpec(Contract):
    action_id: Literal["case.create"] = "case.create"
    revision: Literal["1"] = "1"
    permission: Literal["case:create"] = "case:create"
    executor: Literal["TRUSTED_LOCAL"] = "TRUSTED_LOCAL"
    effect: Literal["LOCAL_RECORD"] = "LOCAL_RECORD"
    idempotency: Literal["SCOPED_KEY_AND_FINGERPRINT"] = "SCOPED_KEY_AND_FINGERPRINT"
    success_scope: Literal["LOCAL_CASE_CREATED"] = "LOCAL_CASE_CREATED"


class ServiceSpec(Contract):
    schema_version: Literal["parkweave-domain/0.1"]
    service_id: str = Field(min_length=1, max_length=100)
    revision: str = Field(min_length=1, max_length=100)
    owner_org_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    service_kind: Literal["LOCAL_INTAKE"]
    eligibility: Literal["NOT_REQUIRED"]
    source_refs: list[SourceRef] = Field(min_length=1, max_length=10)
    reviewer_id: str = Field(min_length=1, max_length=100)
    publication: Literal["REVIEWED_SYNTHETIC"]
    action: ActionSpec
    completion_checks: list[Literal["LOCAL_RECORD_EXISTS"]] = Field(min_length=1, max_length=1)


PlanID = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")]
Goal = Annotated[str, Field(min_length=1, max_length=2000)]
Coverage = Annotated[list[PlanID], Field(min_length=1, max_length=16)]


class Step(Contract):
    step_id: PlanID
    service_ref: PlanID
    revision: str = Field(min_length=1, max_length=100)
    action: ActionSpec
    depends_on: list[PlanID] = Field(max_length=16)
    responsible_role: Literal["enterprise_operator"]
    delivery: Literal["LOCAL_CASE_RECORD"]


class ServicePlan(Contract):
    schema_version: Literal["parkweave-domain/0.1"]
    required_goals: list[Goal] = Field(min_length=1, max_length=16)
    goal_coverage: dict[Goal, Coverage]
    steps: list[Step] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def graph(self):
        if len(set(self.required_goals)) != len(self.required_goals):
            raise ValueError("duplicate required goal")
        if any(not g.strip() for g in self.required_goals):
            raise ValueError("blank required goal")
        if any(len(set(s.depends_on)) != len(s.depends_on) for s in self.steps):
            raise ValueError("duplicate dependency")
        if any(len(set(refs)) != len(refs) for refs in self.goal_coverage.values()):
            raise ValueError("duplicate goal coverage reference")
        ids = {s.step_id for s in self.steps}
        if len(ids) != len(self.steps) or set(self.goal_coverage) != set(self.required_goals):
            raise ValueError("duplicate step or missing required goal")
        if any(not refs or not set(refs) <= ids for refs in self.goal_coverage.values()):
            raise ValueError("invalid goal coverage")
        done = set()
        for _ in self.steps:
            done |= {s.step_id for s in self.steps if set(s.depends_on) <= done}
        if done != ids:
            raise ValueError("unknown dependency or cycle")
        return self


class Intake(Contract):
    schema_version: Literal["parkweave-domain/0.1"] = "parkweave-domain/0.1"
    action: Literal["case.create", "fault.record", "facts.assess"] = "case.create"
    goal: str = Field(min_length=1, max_length=2000)
    source: Literal["SYNTHETIC"] = "SYNTHETIC"

    fact_fields: list[Literal['region','employees','service_need']] = Field(default_factory=list, max_length=3)

    def snapshot(self):
        data=self.model_dump()
        if self.action!='facts.assess':data.pop('fact_fields')
        return data

    @model_validator(mode="after")
    def nonblank(self):
        if not self.goal.strip():
            raise ValueError("goal is blank")
        if self.action=='facts.assess':
            if not self.fact_fields or len(set(self.fact_fields))!=len(self.fact_fields):
                raise ValueError('assessment requires unique explicit fields')
        elif self.fact_fields:
            raise ValueError('fields only supported by facts.assess')
        return self


# Complete required V1 minimum shape for the currently bounded trusted capabilities.
# Legacy 0.1 projections above remain available for old fixtures; not promoted to V1.
from datetime import datetime

FieldName = Literal['region', 'employees', 'service_need']
FactValue = str | int
ISODate = Annotated[str, Field(min_length=20, max_length=40)]


class Validity(Contract):
    valid_from: ISODate
    valid_until: ISODate
    timezone: Literal['UTC'] = 'UTC'

    @model_validator(mode='after')
    def interval(self):
        start,end=datetime.fromisoformat(self.valid_from),datetime.fromisoformat(self.valid_until)
        if start.utcoffset() is None or end.utcoffset() is None or end <= start:
            raise ValueError('validity requires aware increasing times')
        return self


class Rule(Contract):
    kind: Literal['EXISTS','EQ','AND','OR','MANUAL']
    field: FieldName | None = None
    expected: FactValue | None = None
    children: list['Rule'] = Field(default_factory=list, max_length=8)

    @model_validator(mode='after')
    def grammar(self):
        if self.kind in ('AND','OR'):
            if not self.children or self.field is not None or self.expected is not None:
                raise ValueError('logical rule shape invalid')
        elif self.kind=='MANUAL':
            if self.children or self.field is not None or self.expected is not None:
                raise ValueError('manual rule accepts no expression')
        elif self.field is None or self.children or (self.kind=='EQ') != (self.expected is not None):
            raise ValueError('leaf rule shape invalid')
        def measure(node, depth=1):
            if depth>8:raise ValueError('rule depth exceeds 8')
            return 1+sum(measure(child,depth+1) for child in node.children)
        if measure(self)>32:raise ValueError('rule nodes exceed 32')
        return self


class MaterialRequirement(Contract):
    field: FieldName
    purpose: Literal['SERVICE_PREPARATION']
    evidence_required: bool


class ResourceRequirement(Contract):
    resource_ref: PlanID
    revision: PlanID
    quantity: int = Field(ge=1,le=100)


class HandlingPolicy(Contract):
    accepting_org_id: PlanID
    calendar_ref: PlanID | None
    target_seconds: int | None = Field(ge=1,le=31536000)
    target_source_ref: PlanID | None
    pause_reasons: list[Literal['AWAITING_USER']] = Field(max_length=1)

    @model_validator(mode='after')
    def deadline_source(self):
        if self.target_seconds is not None and (self.target_source_ref is None or self.calendar_ref is None):
            raise ValueError('deadline needs a source and calendar')
        return self


class ActionLimits(Contract):
    max_steps: Literal[1]
    max_payload_bytes: int = Field(ge=1,le=16384)


class V1ActionSpec(ActionSpec):
    input_schema_ref: Literal['Intake/0.1']
    output_schema_ref: Literal['LocalCaseReceipt/1']
    dependencies: list[PlanID] = Field(max_length=16)
    limits: ActionLimits
    prechecks: list[Literal['CURRENT_AUTHORIZATION']] = Field(min_length=1,max_length=1)
    postchecks: list[Literal['LOCAL_RECORD_EXISTS']] = Field(min_length=1,max_length=1)
    reconciliation: Literal['LOCAL_TRANSACTION_ATOMIC']


class V1ServiceSpec(Contract):
    schema_version: Literal['parkweave-domain/1.0-draft']
    service_id: PlanID
    revision: PlanID
    owner_org_id: PlanID
    title: Goal
    service_kind: Literal['LOCAL_INTAKE']
    validity: Validity
    eligibility: Literal['NOT_REQUIRED'] | Rule
    material_requirements: list[MaterialRequirement] = Field(max_length=3)
    resource_requirements: list[ResourceRequirement] = Field(max_length=8)
    action_bindings: list[V1ActionSpec] = Field(min_length=1,max_length=1)
    completion_checks: list[Literal['LOCAL_RECORD_EXISTS']] = Field(min_length=1,max_length=1)
    visibility: Literal['OWN_ORGANIZATION']
    handling_policy: HandlingPolicy
    source_refs: list[SourceRef] = Field(min_length=1,max_length=10)
    reviewer_id: PlanID | None
    publication: Literal['DRAFT','REVIEWED_SYNTHETIC']

    @model_validator(mode='after')
    def approval_metadata(self):
        if self.publication=='REVIEWED_SYNTHETIC' and (self.reviewer_id is None or any(s.kind!='SYNTHETIC' for s in self.source_refs)):
            raise ValueError('reviewed synthetic source/reviewer missing')
        if self.handling_policy.target_source_ref and self.handling_policy.target_source_ref not in {s.id for s in self.source_refs}:
            raise ValueError('deadline source reference unknown')
        return self


class V1Step(Step):
    action: V1ActionSpec
    input_mapping: dict[PlanID, FieldName] = Field(max_length=3)
    preconditions: list[Rule] = Field(max_length=8)
    completion_checks: list[Literal['LOCAL_RECORD_EXISTS']] = Field(min_length=1,max_length=1)


class V1ServicePlan(ServicePlan):
    schema_version: Literal['parkweave-domain/1.0-draft']
    request_ref: PlanID
    plan_id: PlanID
    revision: PlanID
    steps: list[V1Step] = Field(min_length=1,max_length=16)
    dependency_lock: dict[PlanID, PlanID] = Field(max_length=32)
    unknowns: list[Goal] = Field(max_length=16)
    resource_proposals: list[ResourceRequirement] = Field(max_length=8)
    approval_requirements: list[Literal['CURRENT_AUTHORITY']] = Field(max_length=1)
    validation_suite_ref: PlanID

    @model_validator(mode='after')
    def locked_services(self):
        if any(self.dependency_lock.get(s.service_ref)!=s.revision for s in self.steps):
            raise ValueError('service dependency lock missing or revision mismatch')
        return self


class FactInput(Contract):
    schema_version: Literal['parkweave-domain/1.0-draft']
    field: FieldName
    value: Annotated[FactValue, Field(union_mode='left_to_right')]
    unit: str = Field(min_length=1,max_length=20)
    source_ref: SourceRef
    source_excerpt: str = Field(min_length=1,max_length=1000)
    validity: Validity
    purpose: Literal['SERVICE_PREPARATION'] = 'SERVICE_PREPARATION'

    @model_validator(mode='after')
    def synthetic_field_type(self):
        if self.source_ref.kind!='SYNTHETIC':raise ValueError('runtime accepts synthetic evidence only')
        if self.field=='employees':
            if type(self.value) is not int or self.value<0 or self.unit!='people':
                raise ValueError('employees requires nonnegative integer people')
        elif type(self.value) is not str or not self.value.strip() or len(self.value)>2000 or self.unit!='text':
            raise ValueError('text fact requires bounded nonblank text')
        return self
