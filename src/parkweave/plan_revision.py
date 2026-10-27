"""Single trusted local-action plan projection. Not F2 composite service planning."""
import hashlib
import json
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from .intern_adapter import ModelBoundaryError,strict_json

class LocalStep(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    action:Literal['case.create']
    state:Literal['LOCAL_RECORD_CREATED']
    case_id:str=Field(pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

class Revision(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    schema_version:Literal['parkweave/local-plan-revision/1']
    revision:Literal[2]
    previous_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    goal:str=Field(min_length=1,max_length=2000)
    operation_id:str=Field(pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    tool_call_id:str=Field(pattern=r'^[A-Za-z0-9_-]{1,100}$')
    receipt_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    step:LocalStep
    case_state:Literal['NEEDS_INPUT']
    next_step:Literal['REQUEST_MISSING_INPUT']
    success_scope:Literal['LOCAL_CASE_CREATED']
    external_acceptance:Literal['NOT_SUBMITTED']
    offline_fulfillment:Literal['NO_EVIDENCE']


def fingerprint(document):
    return hashlib.sha256(json.dumps(document,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def initial(goal,operation_id,tool_call_id):
    return {'schema_version':'parkweave/local-plan-revision/1','revision':1,'goal':goal,
            'operation_id':str(operation_id),'tool_call_id':tool_call_id,
            'step':{'action':'case.create','state':'PENDING_ACTION'},'case_state':'NOT_CREATED',
            'next_step':'EXECUTE_TRUSTED_LOCAL_ACTION','external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE'}


def validate_revision(content,before,receipt,case):
    try:
        raw=strict_json(content)
        if not isinstance(raw,dict) or type(raw.get('revision')) is not int:raise ValueError()
        document=Revision.model_validate(raw).model_dump()
        expected_receipt={'case_id':str(case['id']),'source':'LOCAL_DATABASE','verified':True,'success_scope':'LOCAL_CASE_CREATED'}
        if (receipt!=expected_receipt or case['goal']!=before['goal'] or case['state']!='NEEDS_INPUT'
            or case['source']!='SYNTHETIC' or case['external_acceptance']!='NOT_SUBMITTED' or case['offline_fulfillment']!='NO_EVIDENCE'):
            raise ValueError()
        if (document['previous_sha256']!=fingerprint(before) or document['goal']!=before['goal']
            or document['operation_id']!=before['operation_id'] or document['tool_call_id']!=before['tool_call_id']
            or document['receipt_sha256']!=fingerprint(receipt) or document['step']['case_id']!=str(case['id'])):
            raise ValueError()
        return document
    except Exception:raise ModelBoundaryError('INVALID_PLAN_REVISION') from None
