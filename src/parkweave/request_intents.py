"""Explicit owner assertions, never inferred coverage of a natural language goal."""
from typing import Annotated
from pydantic import BaseModel,ConfigDict,Field
from psycopg.types.json import Jsonb
from . import preparation as prep
from .store import Denied,Conflict,digest

class Save(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    expected_preparation_revision:int=Field(ge=1,le=63)
    request_text:str=Field(min_length=1,max_length=2000)
    required_goals:list[Annotated[str,Field(min_length=1,max_length=160)]]=Field(min_length=0,max_length=8)

def coverage(goals):
    from .controlled_plans import TEMPLATE,TEMPLATE_SHA
    unsupported=[g for g in goals if g!=TEMPLATE['goal']]
    return dict(state='UNKNOWN' if not goals else 'PARTIAL' if unsupported else 'SUPPORTED_LOCAL',
      items=[dict(goal=g,status='SUPPORTED_LOCAL' if g==TEMPLATE['goal'] else 'UNSUPPORTED') for g in goals],
      unsupported_goals=unsupported,template_sha256=TEMPLATE_SHA,
      original_request_understood=False,original_case_goal_completed=False)

def view(parent):
    value=parent.get('request_intent')
    projected=dict(value['coverage']) if value else coverage([])
    if state(parent)=='STALE':projected['state']='STALE'
    return dict(recorded=bool(value),original_request=parent['goal'],
      current_request=value['request_text'] if value else parent['goal'],
      revision=value['revision'] if value else 0,
      required_goals=value['required_goals'] if value else [],
      coverage=projected,
      source='USER_EXPLICIT_STATEMENT' if value else 'LEGACY_NOT_RECORDED')

def state(parent):
    from .controlled_plans import TEMPLATE_SHA
    value=parent.get('request_intent')
    if not value:return 'NOT_RECORDED'
    if value['coverage']['template_sha256']!=TEMPLATE_SHA:return 'STALE'
    return value['coverage']['state']

def save(store,token,id,key,data):
    from . import controlled_plans as cp
    fp=digest(prep.canonical({'preparation_id':str(id),'action':'UPDATE_REQUEST',**data.model_dump()}))
    with store.connect() as c:
        p=store.auth(c,token,lock=True)
        prep.grant(store,c,p,'PREPARE');store.check_capability(c,p,'EXECUTE')
        prep.key_lock(c,p,key)
        parent=prep.scoped(store,c,p,id,write=True)
        if parent['namespace']!='SYNTHETIC':raise Denied('synthetic request required')
        old=prep.replay(c,p,key,fp,id)
        if old:return old
        if parent['revision']!=data.expected_preparation_revision or parent['revision']>=64:raise Conflict('request revision changed or history limit reached')
        goals=list(dict.fromkeys(data.required_goals))
        value=dict(request_text=data.request_text,required_goals=goals,coverage=coverage(goals),
          revision=parent['revision']+1,source='USER_EXPLICIT_STATEMENT')
        updated=c.execute("UPDATE preparations SET request_intent=%s,revision=revision+1,state='IN_PREPARATION',review_sha256=NULL WHERE id=%s RETURNING *",(Jsonb(value),id)).fetchone()
        cp.invalidate(c,id,1)
        return prep.event(c,p,updated,key,fp,'UPDATE_REQUEST',request_intent=view(updated))
