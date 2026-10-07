"""One human-operated synthetic workflow; no arbitrary DAG or execution authority."""
import json
from contextvars import ContextVar
from uuid import uuid4
from typing import Literal,Annotated
from pydantic import BaseModel,ConfigDict,Field
from psycopg.types.json import Jsonb
from . import preparation as prep, service_dispatches as sd, executor_receipts as er
from . import case_lifecycle as life, request_intents as intents
from .store import Denied,Conflict,digest

STEPS=('P1','P2','P3','P4')
CHECKS=('MATERIAL_REVIEW','RESOURCE_RECHECK','ACCEPTANCE_RECHECK','RECEIPT_RECHECK')
SCOPE='SYNTHETIC_FIXED_FOUR_STEP_TEMPLATE_ONLY'
TEMPLATE={'id':'synthetic-preparation-coordination','version':1,'namespace':'SYNTHETIC',
 'review':'ENGINEERING_ONLY','business_publication':False,'validation_suite':'eng037/1',
 'steps':[{'id':s,'depends_on':list(STEPS[i-1:i]) if i else [],'adapter':a,'version':1}
          for i,(s,a) in enumerate(zip(STEPS,('preparation','case-resources','dispatch','executor-receipts')))],
 'goal':'LOCAL_SYNTHETIC_COORDINATION_RECORDS','automatic_execution':False}
TEMPLATE_SHA=digest(prep.canonical(TEMPLATE))
OBSERVATIONS=ContextVar('controlled_plan_observations',default=None)
class PlanBlocked(Conflict):
    def __init__(self,parent,row,message='controlled plan prerequisites need explicit current owner check'):
        super().__init__(message)
        self.preparation_id=parent['id'];self.plan_id=row['id'];self.revision=row['revision'];self.index=row['invalidated_from']

def persist_rejected_observation(store,error):
    """Business rollback must not erase observed invalidity of old checkpoints.

    This separate metadata transaction cannot invalidate a later explicit CHECK:
    its plan ID/revision must still equal the rejected operation's observation.
    """
    if getattr(error,'kind',None)=='SERVICE_CASE_PLAN':
        from .service_case_steps import persist_rejected_observation as persist
        return persist(store,error)
    if error.index is None:return
    with store.connect() as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        c.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(error.preparation_id,))
        row=_row(c,error.preparation_id)
        if row and row['id']==error.plan_id and row['revision']==error.revision:
            invalidate(c,error.preparation_id,error.index)
class Create(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    template_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    expected_preparation_revision:int=Field(ge=1,le=64)
    required_goals:list[Literal['LOCAL_SYNTHETIC_COORDINATION_RECORDS']]=Field(min_length=1,max_length=1)
    expected_preview_sha256:str|None=Field(default=None,pattern='^[a-f0-9]{64}$')
class Preview(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    required_goals:list[Annotated[str,Field(min_length=1,max_length=160)]]=Field(min_length=0,max_length=8)

# Describes only existing adapters, never a published business catalogue.
PREVIEW_STEPS={
 'P1':dict(responsibility='企业经办人补件、获派专员人工核对、企业确认',preconditions='有来源的诉求摘要和材料目录；当前专员核对权',output='当前版本的本地确认资料包',acceptance='企业明确核对当前材料版本'),
 'P2':dict(responsibility='企业经办人',preconditions='P1核对有效；本人两资源组合有效且明确关联此Case',output='此Case的两资源组合关联记录',acceptance='核对时段、规则与当前材料绑定'),
 'P3':dict(responsibility='获派专员分派、已有合法Run访问的执行者本人接单',preconditions='P2核对有效；已有运行访问；当前材料对应的本人接单',output='当前内部接单及回执事项',acceptance='核对本人接受记录及当前运行访问'),
 'P4':dict(responsibility='获派执行者提交、企业经办人核对',preconditions='P3核对有效；当前材料绑定的合成回执',output='企业已核对的合成回执记录',acceptance='明确核对来源和当前回执版本；仍不证明外部履约')}
class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    action:Literal['CHECK_STEP']
    step:Literal['P1','P2','P3','P4']
    expected_revision:int=Field(ge=1,le=63)
    expected_source_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    reason:str=Field(min_length=1,max_length=1000)

def _normal(x):return json.loads(json.dumps(x,default=str))
def _hash(x):return digest(prep.canonical(x))
def _row(c,id):return c.execute('SELECT * FROM controlled_plans WHERE preparation_id=%s FOR UPDATE',(id,)).fetchone()
def _creation_blockers(c,parent):
    # Shared with CREATE under the same parent lock; historical records stay intact.
    dependencies=(('EXISTING_CASE_RESOURCE_LINK','case_resource_links','preparation_id'),
      ('EXISTING_DISPATCH_RECORD','service_dispatches','preparation_id'),
      ('EXISTING_RECEIPT_RECORD','service_receipt_steps','preparation_id'))
    blockers=[reason for reason,table,column in dependencies
      if c.execute('SELECT 1 FROM '+table+' WHERE '+column+'=%s',(parent['id'],)).fetchone()]
    if intents.state(parent) not in ('NOT_RECORDED','SUPPORTED_LOCAL'):blockers.append('REQUEST_GOAL_COVERAGE_REQUIRED')
    return blockers

def _auth(store,c,token,id,write=False):
    p=sd._auth(store,c,token)
    candidate=c.execute('SELECT * FROM preparations WHERE id=%s AND park_id=%s AND org_id=%s',(id,p['park_id'],p['org_id'])).fetchone()
    if not candidate:raise Denied('plan unavailable')
    if p['role']=='service_executor':
        store.scoped_run(c,p,candidate['run_id'])
        if not c.execute('SELECT 1 FROM service_dispatch_offers o JOIN service_dispatches d ON d.id=o.dispatch_id WHERE d.preparation_id=%s AND o.executor_id=%s',(id,p['id'])).fetchone():raise Denied('own offered plan required')
    else:
        prep.grant(store,c,p,'PREPARE' if p['role']=='enterprise_operator' else 'REVIEW_ASSIGNED')
        if p['id']!=candidate['owner_id' if p['role']=='enterprise_operator' else 'reviewer_id']:raise Denied('assigned plan scope required')
    # Serialize on the parent without making EXECUTE a read permission. Obtain
    # FUP directly, avoiding simultaneous SHARE->UPDATE lock upgrades on GET.
    if not c.execute('SELECT id FROM preparations WHERE id=%s AND park_id=%s AND org_id=%s FOR UPDATE',(id,p['park_id'],p['org_id'])).fetchone():raise Denied('plan unavailable')
    parent=sd._parent(store,c,p,id)
    if parent['namespace']!='SYNTHETIC':raise Denied('synthetic preparation required')
    if write:
        if p['role']!='enterprise_operator':raise Denied('owner explicit plan check required')
        store.check_capability(c,p,'EXECUTE')
    return p,parent

def template(store,token):
    with store.connect() as c:sd._auth(store,c,token)
    return dict(scope=SCOPE,template=TEMPLATE,template_sha256=TEMPLATE_SHA,executed=False)

def binding_catalog_known(catalog):
    return bool(catalog and catalog['namespace']=='SYNTHETIC' and isinstance(catalog['source'],dict) and catalog['source'].get('kind')=='SYNTHETIC' and catalog['source'].get('id') and catalog['source'].get('revision'))

def binding_p1(c,parent,snapshot):
    """Shared version descriptor for checks and the read-only binding projection."""
    result={k:snapshot.get(k) for k in ('preparation_id','case_id','run_id','service_id','service_version','preparation_revision','preparation_sha256')}
    catalog=c.execute('SELECT service_id,version,source,namespace,qualification FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',(parent['park_id'],parent['service_id'],parent['service_version'])).fetchone()
    result.update(owner_id=parent['owner_id'],reviewer_id=parent['reviewer_id'],goal=parent['goal'],
      required_goals=intents.view(parent)['required_goals'],request_intent=parent.get('request_intent'),
      template_sha256=TEMPLATE_SHA,service_catalog=_normal(catalog) if catalog else None)
    result['owner_grants']={cap:bool(c.execute('SELECT 1 FROM capability_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND capability=%s AND active',(parent['owner_id'],parent['park_id'],parent['org_id'],cap)).fetchone()) for cap in ('READ','EXECUTE')}
    result['owner_grants']['PREPARE']=bool(c.execute("SELECT 1 FROM preparation_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND capability='PREPARE' AND active",(parent['owner_id'],parent['park_id'],parent['org_id'])).fetchone())
    if parent.get('request_intent'):result['request_intent_sha256']=_hash(parent['request_intent'])
    return _normal(result)

def binding_p2(c,parent,snapshot,holds,rules):
    result={k:snapshot.get(k) for k in ('preparation_revision','preparation_sha256','resource_link_id','resource_link_revision','combination_id','combination_state','members')}
    result['resource_catalog_decision']=snapshot.get('resource_catalog_decision')
    result['resource_rules']=[_normal({k:r[k] for k in ('id','revision','capacity','buffer_seconds','open_from','open_until','enabled','source','namespace','authority')}) for _,r in sorted(rules.items(),key=lambda x:str(x[0]))]
    result['hold_sources']=[_normal({k:h[k] for k in ('id','resource_id','resource_revision','starts_at','ends_at','buffer_seconds','quantity','state','expires_at','namespace')}) for h in holds]
    result['resource_grants']=[dict(resource_id=str(h['resource_id']),capability=cap,active=bool(c.execute('SELECT 1 FROM synthetic_resource_grants WHERE principal_id=%s AND resource_id=%s AND park_id=%s AND org_id=%s AND capability=%s AND active',(parent['owner_id'],h['resource_id'],parent['park_id'],parent['org_id'],cap)).fetchone())) for h in holds for cap in ('READ','HOLD')]
    return _normal(result)

def _sources(store,c,parent):
    # Trusted private dependency checks use the existing owner's current scope;
    # their private source data are never projected to counterpart roles.
    store.lock_principal(c,parent['owner_id'])
    owner=c.execute('SELECT * FROM principals WHERE id=%s',(parent['owner_id'],)).fetchone()
    try:
        if not owner or not owner['active'] or owner['role']!='enterprise_operator':raise Denied('owner unavailable')
        prep.grant(store,c,owner,'PREPARE')
    except Denied:
        return {s:['CURRENT_OWNER_AUTHORITY_REQUIRED'] for s in STEPS},{s:{} for s in STEPS}
    issues,snap,group,holds,rules=life._sources(store,c,owner,parent)
    c.execute('SELECT id FROM cases WHERE id=%s FOR SHARE',(parent['case_id'],))
    life._timed(c,issues,group,holds,rules)
    if not c.execute("SELECT 1 FROM run_assignments a JOIN principals p ON p.id=a.principal_id JOIN capability_grants g ON g.principal_id=p.id AND g.park_id=p.park_id AND g.org_id=p.org_id WHERE a.run_id=%s AND a.active AND a.park_id=%s AND a.org_id=%s AND p.park_id=a.park_id AND p.org_id=a.org_id AND p.active AND p.role='service_executor' AND g.capability='READ' AND g.active",(parent['run_id'],parent['park_id'],parent['org_id'])).fetchone():issues['ACCEPTANCE_RECHECK'].append('EXISTING_RUN_ASSIGNMENT_REQUIRED')
    snapshots={
      'P1':{k:snap.get(k) for k in ('preparation_id','case_id','run_id','service_id','service_version','preparation_revision','preparation_sha256')},
      'P2':{k:snap.get(k) for k in ('preparation_revision','preparation_sha256','resource_link_id','resource_link_revision','combination_id','combination_state','members')},
      'P3':{k:snap.get(k) for k in ('preparation_revision','preparation_sha256','dispatch_id','dispatch_revision','offer_id','executor_id','receipt_step_id')},
      'P4':{k:snap.get(k) for k in ('preparation_revision','preparation_sha256','receipt_step_id','receipt_step_revision','receipt_id','receipt_sha256')},
    }
    snapshots['P1']=binding_p1(c,parent,snap)
    if parent.get('request_intent') and intents.state(parent)!='SUPPORTED_LOCAL':issues['MATERIAL_REVIEW'].append('REQUEST_GOAL_COVERAGE_REQUIRED')
    if not binding_catalog_known(snapshots['P1']['service_catalog']):issues['MATERIAL_REVIEW'].append('CURRENT_SERVICE_CATALOG_REQUIRED')
    snapshots['P2']=binding_p2(c,parent,snap,holds,rules)
    return {s:sorted(set(issues[k])) for s,k in zip(STEPS,CHECKS)},_normal(snapshots)

def invalidate(c,id,index):
    row=_row(c,id)
    if row and any(s in row['checked'] for s in STEPS[index-1:]):
        c.execute('UPDATE controlled_plans SET invalidated_from=least(coalesce(invalidated_from,%s),%s),invalidated_at=coalesce(invalidated_at,clock_timestamp()) WHERE preparation_id=%s',(index,index,id))

def _inspect(store,c,parent,row,observe=True):
    if row['template_sha256']!=TEMPLATE_SHA:raise Conflict('fixed template version/hash unavailable')
    issues,snapshots=_sources(store,c,parent);bad=None
    for i,s in enumerate(STEPS,1):
        if s in row['checked'] and (issues[s] or row['checked'][s]['sha256']!=_hash(snapshots[s])):
            bad=i;break
    if observe and bad:
        invalidate(c,parent['id'],bad);row=_row(c,parent['id'])
    invalid=min(x for x in (row['invalidated_from'],bad) if x is not None) if bad or row['invalidated_from'] else None
    states={};prior=True
    for i,s in enumerate(STEPS,1):
        verified=s in row['checked'] and not issues[s] and row['checked'][s]['sha256']==_hash(snapshots[s]) and (invalid is None or i<invalid) and prior
        states[s]='CURRENT' if verified else 'NEEDS_RECHECK' if s in row['checked'] or invalid and i>=invalid else 'PENDING'
        prior=verified
    return row,issues,snapshots,states

def gate(store,c,parent,through):
    if parent.get('service_case_plan'):
        from .service_case_steps import gate as case_step_gate
        case_step_gate(store,c,parent,through)
    row=_row(c,parent['id'])
    if not row:
        # A strict immutable resource decision remains a resource prerequisite
        # even for the older direct business routes without a fixed plan row.
        # Binding through P1 must stay available to record a fresh decision.
        if through>=2:
            from .resource_plan_binding import current_catalog_decision
            if current_catalog_decision(c,parent)['status']=='STALE':
                raise Conflict('resource catalogue decision is stale; explicitly bind a current decision before advancing')
        return
    row,issues,snapshots,states=_inspect(store,c,parent,row)
    observations=OBSERVATIONS.get()
    if observations is not None and row['invalidated_from'] is not None:
        observations.append(PlanBlocked(parent,row))
    if any(states[s]!='CURRENT' for s in STEPS[:through]):raise PlanBlocked(parent,row)

def _view(c,p,parent,row,issues,snapshots,states,event=None):
    owner=p['role']=='enterprise_operator';next_step=next((s for s in STEPS if states[s]!='CURRENT'),None)
    history=c.execute('SELECT revision,action,step,payload,created_at FROM controlled_plan_events WHERE preparation_id=%s ORDER BY revision',(parent['id'],)).fetchall()
    if not owner:history=[{k:v for k,v in h.items() if k!='payload'} for h in history];event=None
    can_write=False
    if owner:
        # READ is sufficient for the projection; command independently rechecks EXECUTE.
        can_write=p.get('_plan_write',False)
    steps=[]
    for i,s in enumerate(STEPS):
        ready=not issues[s] and all(states[t]=='CURRENT' for t in STEPS[:i])
        steps.append(dict(id=s,state=states[s],source_ready=ready if owner else None,
          issues=issues[s] if owner else None,source_sha256=_hash(snapshots[s]) if owner else None,
          can_check=owner and can_write and ready and states[s]!='CURRENT' and row['revision']<64))
    next_ready=next_step is None or not issues[next_step]
    access_blocked='EXISTING_RUN_ASSIGNMENT_REQUIRED' in issues['P3']
    state='LOCAL_RECORDS_CHECKED' if next_step is None else 'BLOCKED' if not next_ready or access_blocked else 'NEEDS_RECHECK' if any(v=='NEEDS_RECHECK' for v in states.values()) else 'IN_PROGRESS'
    return dict(scope=SCOPE,role=p['role'],preparation_id=parent['id'],preparation_revision=parent['revision'],plan_id=row['id'],revision=row['revision'],
      request_intent=intents.view(parent) if owner else None,request_coverage_state=intents.state(parent),
      template_sha256=row['template_sha256'],template_version=1,state=state,steps=steps,next_step=next_step,
      history=history,event=event,source_snapshots=snapshots if owner else None,
      goal=parent['goal'] if owner else None,goal_coverage='LOCAL_SYNTHETIC_RECORDS_ONLY',
      required_goals=intents.view(parent)['required_goals'] if owner else None,template_required_goals=['LOCAL_SYNTHETIC_COORDINATION_RECORDS'],full_original_goal_verified=False,original_case_goal_support='NOT_VERIFIED_BY_LOCAL_TEMPLATE',automatic_execution=False,new_grants=False,
      external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE',case_goal_completed=False)

def _write_flag(store,c,p):
    p['_plan_write']=False
    if p['role']=='enterprise_operator':
        try:store.check_capability(c,p,'EXECUTE');p['_plan_write']=True
        except Denied:pass

def _event(c,p,parent,row,key,fp,action,step=None,reason='',snapshot=None):
    payload=dict(action=action,step=step,revision=row['revision'],actor_id=p['id'],reason=reason,
                 source_sha256=_hash(snapshot) if snapshot is not None else None)
    c.execute('INSERT INTO controlled_plan_events(id,preparation_id,actor_id,request_key,fingerprint,revision,action,step,payload,snapshot) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(uuid4(),parent['id'],p['id'],key,fp,row['revision'],action,step,Jsonb(payload),Jsonb(snapshot) if snapshot is not None else None))
    return payload

def _old(c,p,id,key,fp):
    old=c.execute('SELECT * FROM controlled_plan_events WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
    if old and (old['preparation_id']!=id or old['fingerprint']!=fp):raise Conflict('controlled plan request key fingerprint mismatch')
    return old

@er.bounded
def read(store,token,id):
    with store.connect() as c:
        p,parent=_auth(store,c,token,id);_write_flag(store,c,p);row=_row(c,id)
        if not row:
            owner=p['role']=='enterprise_operator'
            blockers=_creation_blockers(c,parent) if owner else None
            if owner and not p['_plan_write']:blockers.append('CURRENT_EXECUTE_AUTHORITY_REQUIRED')
            return dict(scope=SCOPE,role=p['role'],preparation_id=id,plan_id=None,template_sha256=TEMPLATE_SHA,
              can_create=owner and p['_plan_write'] and not blockers,creation_blockers=blockers,
              request_intent=intents.view(parent) if owner else None,request_coverage_state=intents.state(parent),
              state='NOT_STARTED',preparation_revision=parent['revision'])
        row,issues,snapshots,states=_inspect(store,c,parent,row)
        return _view(c,p,parent,row,issues,snapshots,states)

@er.bounded
def preview(store,token,id,data):
    with store.connect() as c:
        p,parent=_auth(store,c,token,id)
        if p['role']!='enterprise_operator':raise Denied('owner plan preview required')
        return _preview(store,c,p,parent,data.required_goals)

def _preview(store,c,p,parent,goals):
    _write_flag(store,c,p)
    blockers=_creation_blockers(c,parent)
    if _row(c,parent['id']):blockers.append('PLAN_ALREADY_EXISTS')
    if not p['_plan_write']:blockers.append('CURRENT_EXECUTE_AUTHORITY_REQUIRED')
    issues,snapshots=_sources(store,c,parent)
    goals=list(dict.fromkeys(goals))
    if parent.get('request_intent') and goals!=parent['request_intent']['required_goals']:raise Conflict('save explicit request goals before preview')
    unsupported=[g for g in goals if g!=TEMPLATE['goal']]
    steps=[dict(id=s,depends_on=TEMPLATE['steps'][i]['depends_on'],**PREVIEW_STEPS[s],
      state='NEEDS_INPUT' if issues[s] else 'INPUTS_PRESENT',issues=issues[s],source_sha256=_hash(snapshots[s])) for i,s in enumerate(STEPS)]
    result=dict(scope=SCOPE,namespace='PREVIEW',template_review='ENGINEERING_ONLY',business_publication=False,
      preparation_id=parent['id'],case_id=parent['case_id'],preparation_revision=parent['revision'],request_intent=intents.view(parent),
      template_sha256=TEMPLATE_SHA,required_goals=goals,unsupported_goals=unsupported,
      supported_goals=[g for g in goals if g==TEMPLATE['goal']],creation_blockers=blockers,steps=steps,
      can_adopt=not blockers and not unsupported and TEMPLATE['goal'] in goals,
      state='UNKNOWN' if not goals else 'PARTIAL' if unsupported else 'BLOCKED' if blockers else 'READY_TO_ADOPT',
      persisted=False,executed=False,case_goal_completed=False,automatic_execution=False,new_grants=False)
    result['preview_sha256']=_hash(_normal(result))
    return result

@er.bounded
def create(store,token,id,key,data):
    fp=_hash({'preparation_id':str(id),'action':'CREATE',**data.model_dump(exclude_none=True)})
    with store.connect() as c:
        p,parent=_auth(store,c,token,id,write=True);p['_plan_write']=True;row=_row(c,id);old=_old(c,p,id,key,fp)
        if data.template_sha256!=TEMPLATE_SHA:raise Conflict('fixed template hash mismatch')
        if not old:
            if row or parent['revision']!=data.expected_preparation_revision:raise Conflict('plan exists or preparation revision changed')
            blockers=_creation_blockers(c,parent)
            if 'REQUEST_GOAL_COVERAGE_REQUIRED' in blockers:raise Conflict('explicit request goals remain unknown or unsupported')
            if blockers:raise Conflict('start fixed template before resource association/dispatch/receipt')
            if data.expected_preview_sha256 is not None:
                current=_preview(store,c,p,parent,data.required_goals)
                if not current['can_adopt'] or current['preview_sha256']!=data.expected_preview_sha256:raise Conflict('plan preview changed; preview again')
            row=c.execute('INSERT INTO controlled_plans(preparation_id,id,template_sha256,revision) VALUES(%s,%s,%s,1) RETURNING *',(id,uuid4(),TEMPLATE_SHA)).fetchone()
            event=_event(c,p,parent,row,key,fp,'CREATE')
        else:event=old['payload']
        row,issues,snapshots,states=_inspect(store,c,parent,row)
        return _view(c,p,parent,row,issues,snapshots,states,event)

@er.bounded
def command(store,token,id,key,data):
    fp=_hash({'preparation_id':str(id),**data.model_dump()})
    with store.connect() as c:
        p,parent=_auth(store,c,token,id,write=True);p['_plan_write']=True;row=_row(c,id)
        if not row:raise Conflict('fixed plan required')
        old=_old(c,p,id,key,fp);row,issues,snapshots,states=_inspect(store,c,parent,row)
        if old:return _view(c,p,parent,row,issues,snapshots,states,old['payload'])
        i=STEPS.index(data.step)
        if row['revision']!=data.expected_revision or row['revision']>=64:raise PlanBlocked(parent,row,'stale or exhausted plan revision')
        if issues[data.step] or any(states[s]!='CURRENT' for s in STEPS[:i]):raise PlanBlocked(parent,row,'controlled plan source or preceding step needs recheck')
        if states[data.step]=='CURRENT':raise PlanBlocked(parent,row,'step already current')
        snap=snapshots[data.step]
        if data.expected_source_sha256!=_hash(snap):raise PlanBlocked(parent,row,'controlled plan source changed')
        checked={s:v for s,v in row['checked'].items() if STEPS.index(s)<i};checked[data.step]={'sha256':_hash(snap),'snapshot':snap}
        row=c.execute('UPDATE controlled_plans SET revision=revision+1,checked=%s,invalidated_from=NULL,invalidated_at=NULL WHERE preparation_id=%s RETURNING *',(Jsonb(checked),id)).fetchone()
        event=_event(c,p,parent,row,key,fp,'CHECK_STEP',data.step,data.reason,snap)
        row,issues,snapshots,states=_inspect(store,c,parent,row)
        return _view(c,p,parent,row,issues,snapshots,states,event)
