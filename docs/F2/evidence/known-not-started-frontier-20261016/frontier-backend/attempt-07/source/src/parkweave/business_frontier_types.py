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
