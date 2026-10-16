"""Optional exact capture, absent fields preserve old command bytes."""
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field

class BusinessFrontierFence(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 generation:UUID=Field(strict=False)
 preparation_id:UUID=Field(strict=False)
 plan_id:UUID=Field(strict=False)
 plan_revision:int=Field(ge=1,le=64)
 epoch:int=Field(ge=0,le=4096)

def request(data):
 value=data.model_dump(mode='json')
 if value.get('expected_business_frontier') is None:value.pop('expected_business_frontier',None)
 return value


def historical_fields(payload):
 """Saved events omit the field or contain one exact original captured fence.

 Normal request None remains compatible; an event never writes a null fence.
 """
 if 'expected_business_frontier' not in payload:return {}
 value=payload['expected_business_frontier']
 if type(value) is not dict:raise ValueError('original saved business frontier must be a valid object')
 fence=BusinessFrontierFence.model_validate(value).model_dump(mode='json')
 if fence!=value:raise ValueError('exact original saved business frontier required')
 return {'expected_business_frontier':fence}
