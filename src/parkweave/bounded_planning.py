"""Deterministic registered-adapter proposal; metadata persistence, never execution."""
from copy import deepcopy
from uuid import uuid4
from typing import Annotated
from pydantic import BaseModel,ConfigDict,Field
from psycopg.types.json import Jsonb
from . import controlled_plans as cp, preparation as prep
from .store import Conflict,Denied

GOALS={'LOCAL_MATERIAL_PREPARATION':'P1','LOCAL_CASE_RESOURCE_ASSOCIATION':'P2','LOCAL_INTERNAL_ACCEPTANCE':'P3','LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT':'P4','LOCAL_SYNTHETIC_COORDINATION_RECORDS':'P4','LOCAL_CASE_RECORD_RECHECK':'P5'}
REGISTRY=[dict(id=s,depends_on=list(cp.TEMPLATE['steps'][i]['depends_on']),adapter=cp.TEMPLATE['steps'][i]['adapter'],revision=1,**cp.PREVIEW_STEPS[s]) for i,s in enumerate(cp.STEPS)]
REGISTRY.append(dict(id='P5',depends_on=['P4'],adapter='case-lifecycle',revision=1,responsibility='企业经办人',preconditions='当前材料、资源、本人接单与回执核对均有效',output='此Case本地记录重新校验',acceptance='原入口明确重新校验，真实目标与履约仍未验证'))
TRUSTED={(s['id'],s['adapter'],s['revision']) for s in REGISTRY}
ACTIONS={
 'P1':[{'method':'POST','path':'/api/preparations/{preparation_id}/commands','role':'enterprise_operator','commands':['ADD_EVIDENCE','CONFIRM']},{'method':'POST','path':'/api/preparations/{preparation_id}/commands','role':'park_specialist','commands':['REQUEST_CHANGES','REVIEW']}],
 'P2':[{'method':'POST','path':'/api/preparations/{preparation_id}/resource-link','role':'enterprise_operator','commands':['CREATE_OR_RECHECK_LINK']}],
 'P3':[{'method':'POST','path':'/api/preparations/{preparation_id}/dispatch','role':'park_specialist','commands':['OFFER']},{'method':'POST','path':'/api/service-dispatches/{dispatch_id}/commands','role':'service_executor','commands':['ACCEPT','DECLINE']}],
 'P4':[{'method':'POST','path':'/api/executor-receipts/{step_id}/commands','role':'service_executor','commands':['SUBMIT']},{'method':'POST','path':'/api/executor-receipts/{step_id}/commands','role':'enterprise_operator','commands':['ACKNOWLEDGE','REQUEST_CHANGES','REOPEN']}],
 'P5':[{'method':'POST','path':'/api/preparations/{preparation_id}/local-case/commands','role':'enterprise_operator','commands':['REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN']}],
}
LIMIT=16
class Capture(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    expected_preparation_revision:int=Field(ge=1,le=64)
    expected_source_sha256:str=Field(pattern='^[0-9a-f]{64}$')

def validate_registry(registry):
    if not 1<=len(registry)<=16:raise Conflict('bounded registry size required')
    if any(not isinstance(s,dict) or not {'id','adapter','revision','depends_on','responsibility','preconditions','output','acceptance'}<=set(s) or not isinstance(s['depends_on'],list) or len(s['depends_on'])>16 for s in registry):raise Conflict('invalid registered step contract')
    ids={s['id'] for s in registry}
    if len(ids)!=len(registry):raise Conflict('duplicate registered step')
    done=set()
    for s in registry:
        if (s['id'],s['adapter'],s['revision']) not in TRUSTED:raise Conflict('unsupported registered adapter/version')
        if len(s['depends_on'])!=len(set(s['depends_on'])) or not set(s['depends_on'])<=ids:raise Conflict('unknown or duplicate dependency')
    for _ in registry:done|={s['id'] for s in registry if set(s['depends_on'])<=done}
    if done!=ids:raise Conflict('registered dependency cycle')
    return {s['id']:s for s in registry}

def compile(goals,registry=None):
    registry=deepcopy(REGISTRY if registry is None else registry);by_id=validate_registry(registry)
    selected=set();items=[]
    for goal in goals:
        target=GOALS.get(goal)
        if target and target not in by_id:raise Conflict('registered goal target missing')
        nodes=set()
        def add(id):
            if id in nodes:return
            nodes.add(id)
            for dependency in by_id[id]['depends_on']:add(dependency)
        if target:add(target)
        selected|=nodes;items.append(dict(goal=goal,status='SUPPORTED_PREVIEW' if target else 'UNSUPPORTED',steps=sorted(nodes)))
    ordered=[];done=set()
    while done!=selected:
        ready=sorted(id for id in selected-done if set(by_id[id]['depends_on'])<=done)
        if not ready:raise Conflict('unresolved required dependency')
        for id in ready:ordered.append(by_id[id]);done.add(id)
    return items,ordered

def _context(store,c,token,id,write=False):
    p,parent=cp._auth(store,c,token,id)
    if p['role']!='enterprise_operator':raise Denied('owner planning preview required')
    if write:store.check_capability(c,p,'EXECUTE')
    if parent['namespace']!='SYNTHETIC':raise Denied('synthetic planning preview required')
    return p,parent

def _proposal(store,c,p,parent):
    validate_registry(REGISTRY)
    intent=parent.get('request_intent');goals=intent['required_goals'] if intent else []
    items,steps=compile(goals);issues,snapshots=cp._sources(store,c,parent)
    from .catalog_publication import snapshot as catalog_snapshot
    catalog=catalog_snapshot(c,parent)
    from .registered_dependencies import collections
    collection_sources=collections(store,c,parent)
    local=c.execute('SELECT revision,cycle,state,verified_sha256 FROM case_local_lifecycles WHERE preparation_id=%s AND case_id=%s',(parent['id'],parent['case_id'])).fetchone()
    case=c.execute('SELECT state FROM cases WHERE id=%s AND run_id=%s',(parent['case_id'],parent['run_id'])).fetchone()
    source={'case_state':case,'local_lifecycle':local,'collections':collection_sources,'request':intent,'original_request':parent['goal'],'preparation_revision':parent['revision'],'catalog':catalog,'registry':REGISTRY,'actions':ACTIONS,'issues':issues,'dependencies':snapshots}
    sha=cp._hash(cp._normal(source));known=cp.binding_catalog_known(catalog)
    if not known:
        for item in items:
            if item['status']=='SUPPORTED_PREVIEW':item['status']='UNKNOWN'
    for s in steps:
        s.update(request_service_ref=parent['service_id'],request_service_version=parent['service_version'],adapter_ref=s['adapter'],adapter_revision=s['revision'],input='此Case当前来源版本与已有授权事实',actions=ACTIONS[s['id']],
          issues=issues.get(s['id'],sorted(set(k for v in issues.values() for k in v))),
          correction='返回对应原办理入口补正并重新核对',executable=False)
        if s['id']=='P5':
            s['lifecycle_state']=local['state'] if local else 'NOT_STARTED';s['lifecycle_cycle']=local['cycle'] if local else None
            if local and local['state']=='LOCAL_RECORD_CLOSED':s['issues']=s['issues']+['LOCAL_RECORD_REOPEN_REQUIRED']
    state='UNKNOWN' if not goals or any(i['status']=='UNKNOWN' for i in items) else 'PARTIAL' if any(i['status']=='UNSUPPORTED' for i in items) else 'COVERED_PREVIEW_ONLY'
    return dict(namespace='PLANNING_METADATA_PREVIEW',planner='DETERMINISTIC_REGISTERED_ADAPTER_SUBGRAPH',preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),preparation_revision=parent['revision'],source_sha256=sha,
      catalog_sha256=cp._hash(cp._normal(catalog)),registry_sha256=cp._hash({'steps':REGISTRY,'actions':ACTIONS}),required_goals=goals,goal_coverage=items,optional_suggestions=[],state=state,steps=steps,
      dependency_collections=collection_sources,
      source_unknowns=[] if known else ['CURRENT_SERVICE_CATALOG_SOURCE_REQUIRED'],executed=False,execution_enabled=False,new_grants=False,case_goal_completed=False,qualification_truth='UNKNOWN',business_publication=False)

def _view(store,c,p,parent):
    current=_proposal(store,c,p,parent);history=parent['planning_previews'] or []
    return dict(current=current,history=[dict(id=h['id'],revision=h['revision'],document=h['document'],state='CURRENT' if h['document']['source_sha256']==current['source_sha256'] else 'STALE') for h in history],history_limit=LIMIT,
                isolated_execution_preview_enabled=getattr(store,'_isolated_execution_preview',None) is not None,
                isolated_resource_execution_preview_enabled=getattr(store,'_isolated_resource_execution_preview',None) is not None,
                isolated_dispatch_execution_preview_enabled=getattr(store,'_isolated_dispatch_execution_preview',None) is not None, isolated_receipt_execution_preview_enabled=getattr(store,'_isolated_receipt_execution_preview',None) is not None)

def read(store,token,id):
    with store.connect() as c:
        p,parent=_context(store,c,token,id);return _view(store,c,p,parent)

def capture(store,token,id,key,data):
    with store.connect() as c:
        p,parent=_context(store,c,token,id,True);prep.key_lock(c,p,'planning-preview:'+key)
        fp=cp._hash({'preparation_id':str(id),**data.model_dump()})
        prior=c.execute('SELECT id,planning_previews FROM preparations WHERE planning_previews @> %s',(Jsonb([{'actor_id':p['id'],'request_key':key}]),)).fetchall()
        if prior:
            for row in prior:
                for h in row['planning_previews']:
                    if h['actor_id']==p['id'] and h['request_key']==key:
                        if row['id']!=parent['id'] or h['fingerprint']!=fp:raise Conflict('planning preview key scope changed')
                        return _view(store,c,p,parent)
        current=_proposal(store,c,p,parent)
        if parent['revision']!=data.expected_preparation_revision or current['source_sha256']!=data.expected_source_sha256:raise Conflict('planning preview source changed')
        history=list(parent['planning_previews'] or [])
        if len(history)>=LIMIT:raise Conflict('planning preview history limit reached')
        history.append(dict(id=str(uuid4()),revision=len(history)+1,actor_id=p['id'],request_key=key,fingerprint=fp,document=current))
        parent=c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s RETURNING *',(Jsonb(history),id)).fetchone()
        return _view(store,c,p,parent)
