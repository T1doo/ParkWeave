"""Explicit bounded planning declarations, never authority or inferred intent."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

class Constraints(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    excluded_roles:list[Literal['enterprise_operator','park_specialist','service_executor']]=Field(default_factory=list,max_length=3)
    additional_requirements:list[Annotated[str,Field(min_length=1,max_length=160)]]=Field(default_factory=list,max_length=4)

def evaluate(intent,steps,actions):
    value=(intent or {}).get('planning_constraints')
    if value is None:return None
    excluded=set(value['excluded_roles']);blocked=set();rows=[]
    for step in steps:
        roles=sorted({a['role'] for a in actions[step['id']]})
        direct=sorted(excluded.intersection(roles));prior=sorted(blocked.intersection(step['depends_on']))
        if direct or prior:blocked.add(step['id'])
        rows.append(dict(step_id=step['id'],required_roles=roles,excluded_required_roles=direct,blocked_predecessors=prior,
                         state='CONFLICT' if direct or prior else 'COMPATIBLE'))
    unsupported=list(value['additional_requirements'])
    return dict(source='USER_EXPLICIT_PLANNING_DECLARATION',constraints=value,steps=rows,
                unsupported_requirements=unsupported,state='UNSUPPORTED' if unsupported else 'CONFLICT' if blocked else 'COMPATIBLE',
                execution_authority_changed=False,model_inference=False)
