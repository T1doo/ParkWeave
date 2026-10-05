"""Strict versioned contracts for this bounded increment, not all V1 features."""
from enum import StrEnum
from typing import Literal
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


class Step(Contract):
    step_id: str = Field(min_length=1, max_length=100)
    service_ref: str = Field(min_length=1, max_length=100)
    revision: str = Field(min_length=1, max_length=100)
    action: ActionSpec
    depends_on: list[str] = Field(max_length=16)
    responsible_role: Literal["enterprise_operator"]
    delivery: Literal["LOCAL_CASE_RECORD"]


class ServicePlan(Contract):
    schema_version: Literal["parkweave-domain/0.1"]
    required_goals: list[str] = Field(min_length=1, max_length=16)
    goal_coverage: dict[str, list[str]]
    steps: list[Step] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def graph(self):
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
    action: Literal["case.create"] = "case.create"
    goal: str = Field(min_length=1, max_length=2000)
    source: Literal["SYNTHETIC"] = "SYNTHETIC"

    @model_validator(mode="after")
    def nonblank(self):
        if not self.goal.strip():
            raise ValueError("goal is blank")
        return self
