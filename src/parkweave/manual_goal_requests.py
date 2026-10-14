"""Bounded same-Case human coordination for unsupported goals, never fulfillment.

An independent append-only ledger inside the existing adopted-plan JSON retains
original request keys. It does not change plan revision, outputs or capabilities.
"""
from copy import deepcopy
import re
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from . import preparation as prep, bounded_planning as bp, service_case_steps as steps
from . import controlled_plans as cp, registered_dependencies as dependencies
from .store import Conflict, Denied

SCOPE='SYNTHETIC_UNSUPPORTED_GOAL_HUMAN_COORDINATION'
LIMIT=32
class Evidence(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    id: UUID=Field(strict=False)
    version: int=Field(ge=1)
    source_sha256: str=Field(pattern='^[a-f0-9]{64}$')

class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    action: Literal['REQUEST','TAKE','REQUEST_EVIDENCE','SUPPLY_EVIDENCE','WITHDRAW']
    plan_id: UUID=Field(strict=False)
    goal: str=Field(min_length=1,max_length=160)
    expected_revision: int=Field(ge=0,le=LIMIT-1)
    expected_source_sha256: str=Field(pattern='^[a-f0-9]{64}$')
    reason: str=Field(min_length=1,max_length=1000)
    evidence: list[Evidence]=Field(default_factory=list,max_length=2)
    @model_validator(mode='after')
    def shape(self):
        if (self.action=='SUPPLY_EVIDENCE')!=bool(self.evidence):raise ValueError('only explicit supplement requires current material references')
        if len({x.id for x in self.evidence})!=len(self.evidence):raise ValueError('distinct material references required')
        return self

def basis(c,parent,plan):
    from .store import digest
    materials=[dict({k:r[k] for k in ('id','slot','version','source_sha256')},integrity_current=digest(r['text'])==r['source_sha256']) for r in prep.latest(c,parent['id'])]
    return cp._normal(dict(scope=SCOPE,preparation_id=parent['id'],case_id=parent['case_id'],run_id=parent['run_id'],owner_id=parent['owner_id'],reviewer_id=parent['reviewer_id'],plan_id=plan['id'],request_intent=parent.get('request_intent'),materials=materials))

def transition(state,action,owner):
    if action=='REQUEST' and owner and state is None:return 'REQUESTED'
    if action=='TAKE' and not owner and state in ('REQUESTED','AWAITING_SPECIALIST_REVIEW'):return 'UNDER_MANUAL_REVIEW'
    if action=='REQUEST_EVIDENCE' and not owner and state=='UNDER_MANUAL_REVIEW':return 'WAITING_OWNER_EVIDENCE'
    if action=='SUPPLY_EVIDENCE' and owner and state=='WAITING_OWNER_EVIDENCE':return 'AWAITING_SPECIALIST_REVIEW'
    if action=='WITHDRAW' and owner and state not in (None,'WITHDRAWN'):return 'WITHDRAWN'
    raise Conflict('current human request state and original responsibility required')

def ledger(parent,plan):
    events=plan.get('manual_goal_requests',[]);states={};seen=set();ids=set()
    try:
        if not isinstance(events,list) or len(events)>LIMIT:raise ValueError()
        for revision,e in enumerate(events,1):
            data=Command.model_validate(e['request']);UUID(e['id'])
            owner=e['actor_id']==parent['owner_id']
            if e['actor_id'] not in (parent['owner_id'],parent['reviewer_id']):raise ValueError()
            if (data.plan_id!=UUID(plan['id']) or data.goal not in plan['required_goals'] or data.goal in bp.GOALS or
                data.expected_revision!=revision-1 or type(e['revision']) is not int or e['revision']!=revision or e['id'] in ids or not re.fullmatch('[A-Za-z0-9_-]{1,100}',e['request_key']) or (e['actor_id'],e['request_key']) in seen or
                e['fingerprint']!=cp._hash(dict(preparation_id=str(parent['id']),**data.model_dump(mode='json'))) or
                e['state']!=transition(states.get(data.goal),data.action,owner)):raise ValueError()
            seen.add((e['actor_id'],e['request_key']));ids.add(e['id']);states[data.goal]=e['state']
    except (ValueError,KeyError,TypeError,Conflict):raise Conflict('human request journal proof invalid')
    return events,states

def key_scope(c,p,parent,key):
    # The original actor key spans Cases. Do not disclose the other Case's data.
    rows=c.execute('SELECT id,service_case_plan FROM preparations WHERE park_id=%s AND org_id=%s AND (owner_id=%s OR reviewer_id=%s) AND id<>%s AND service_case_plan IS NOT NULL',(p['park_id'],p['org_id'],p['id'],p['id'],parent['id'])).fetchall()
    for row in rows:
        for plan in [row['service_case_plan']]+row['service_case_plan'].get('history',[]):
            if any(e.get('actor_id')==p['id'] and e.get('request_key')==key for e in plan.get('manual_goal_requests',[])):
                raise Conflict('original human request key belongs to another Case')

def context(store,c,token,id,write=False):
    c.execute("SET LOCAL lock_timeout='3s'")
    p=store.auth(c,token,lock=True);parent=prep.scoped(store,c,p,id,write=write,business_write=write)
    run=c.execute('SELECT * FROM runs WHERE id=%s AND principal_id=%s AND park_id=%s AND org_id=%s',(parent['run_id'],parent['owner_id'],parent['park_id'],parent['org_id'])).fetchone()
    case=c.execute("SELECT id FROM cases WHERE id=%s AND run_id=%s AND park_id=%s AND org_id=%s AND source='SYNTHETIC'",(parent['case_id'],parent['run_id'],parent['park_id'],parent['org_id'])).fetchone()
    if not run or not case or parent['namespace']!='SYNTHETIC' or parent['service_id']!=prep.SERVICE or parent['service_version']!=1 or run['state']!='SUCCEEDED' or run['input'].get('action','case.create')!='case.create':raise Denied('original synthetic Case required')
    if write and p['role']=='enterprise_operator':store.check_execution(c,p,run)
    plan=deepcopy(parent.get('service_case_plan'))
    if not plan:raise Conflict('existing adopted partial plan required')
    from .case_goal_results import structure
    structure(plan);dependencies.plan_proof(parent,plan)
    return p,parent,plan

def view(store,c,p,parent,plan,event=None):
    events,states=ledger(parent,plan);source=basis(c,parent,plan);materials={r['id']:(r['version'],r['source_sha256']) for r in source['materials'] if r['integrity_current']}
    owner=p['id']==parent['owner_id'];binding_issues=steps._binding_issues(c,parent,plan);current=not binding_issues
    local=c.execute('SELECT state FROM case_local_lifecycles WHERE preparation_id=%s',(parent['id'],)).fetchone()
    case_state=prep.case_state(c,parent);blocked=list(binding_issues)
    if case_state in ('CANCELLED','RECONCILING'):blocked.append('CASE_'+case_state)
    if local and local['state']=='LOCAL_RECORD_CLOSED':blocked.append('LOCAL_RECORD_CLOSED')
    if not all(r['integrity_current'] for r in source['materials']):blocked.append('MATERIAL_REFERENCE_INTEGRITY_REQUIRED')
    if len(events)>=LIMIT:blocked.append('MANUAL_HISTORY_LIMIT_REACHED')
    writable=not blocked and current and plan.get('partial_adoption') is True
    if owner and writable:
        try:store.check_execution(c,p,store.scoped_run(c,p,parent['run_id']))
        except Denied:blocked.append('CURRENT_WRITE_AUTHORITY_REQUIRED');writable=False  # Historical READ survives revoked write authority.
    # Free-text goals remain private until the original owner explicitly requests
    # human review. Validated REQUEST history also preserves sharing on withdrawal.
    shared={e['request']['goal'] for e in events if e['actor_id']==parent['owner_id'] and e['request']['action']=='REQUEST'}
    items=[]
    for goal in plan['required_goals']:
        if goal in bp.GOALS or not owner and goal not in shared:continue
        state=states.get(goal);actions=[]
        if writable:
            for action in ('REQUEST','TAKE','REQUEST_EVIDENCE','SUPPLY_EVIDENCE','WITHDRAW'):
                try:transition(state,action,owner);actions.append(action)
                except Conflict:pass
        history=[dict(e,evidence_current=all(materials.get(r['id'])==(r['version'],r['source_sha256']) for r in e['request']['evidence'])) for e in events if e['request']['goal']==goal]
        supplements=[e for e in history if e['request']['action']=='SUPPLY_EVIDENCE']
        items.append(dict(goal=goal,state=state or 'NOT_REQUESTED',responsible_actor_id=parent['owner_id'] if state in (None,'WAITING_OWNER_EVIDENCE','WITHDRAWN') else parent['reviewer_id'],responsibility='OWNER_PREPARATION' if state in (None,'WAITING_OWNER_EVIDENCE','WITHDRAWN') else 'ORIGINAL_SPECIALIST_REVIEW' if state in ('UNDER_MANUAL_REVIEW','AWAITING_SPECIALIST_REVIEW') else 'WAITING_ORIGINAL_SPECIALIST_ACCEPTANCE',allowed_actions=actions,blocked_reasons=sorted(set(blocked)),history=history,supplement_state='STALE' if supplements and not supplements[-1]['evidence_current'] else 'CURRENT_REFERENCE_UNVERIFIED' if supplements else 'NOT_SUPPLIED',goal_state='UNSUPPORTED'))
    return dict(scope=SCOPE,actor_id=p['id'],preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),plan_id=plan['id'],revision=len(events),source_sha256=cp._hash(source),materials=source['materials'],items=items,event=event,overall_goal_state='PARTIAL' if plan.get('partial_adoption') is True else 'UNVERIFIED',case_goal_completed=False,qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE',new_grants=False)

@steps.er.bounded
def read(store,token,id,key=None):
    with store.connect() as c:
        p,parent,plan=context(store,c,token,id);found=[]
        if key:key_scope(c,p,parent,key)
        for saved in [plan]+plan.get('history',[]):
            events,_=ledger(parent,saved);found.extend(e for e in events if e['actor_id']==p['id'] and e['request_key']==key)
        if len(found)>1:raise Conflict('human request key scope ambiguous')
        result=view(store,c,p,parent,plan,found[0] if found else None)
        return dict(result,status='COMMITTED' if found else 'NOT_OBSERVED' if key else 'CURRENT',original_plan_id=found[0]['request']['plan_id'] if found else None,read_only=True,automatically_replayed=False)

@steps.er.bounded
def command(store,token,id,key,data):
    with store.connect() as c:
        p,parent,plan=context(store,c,token,id,True);prep.key_lock(c,p,'manual-goal:'+key)
        key_scope(c,p,parent,key)
        fp=cp._hash(dict(preparation_id=str(id),**data.model_dump(mode='json')))
        for saved in [plan]+plan.get('history',[]):
            events,_=ledger(parent,saved)
            for e in events:
                if (e['actor_id'],e['request_key'])==(p['id'],key):
                    if e['fingerprint']!=fp:raise Conflict('human request key fingerprint changed')
                    return dict(view(store,c,p,parent,plan),event=e,original_result=e)
        current=view(store,c,p,parent,plan);item=next((x for x in current['items'] if x['goal']==data.goal),None)
        if data.plan_id!=UUID(plan['id']) or data.expected_revision!=current['revision'] or data.expected_source_sha256!=current['source_sha256']:raise Conflict('current original plan and human request source required')
        if not item or data.action not in item['allowed_actions']:raise Conflict('unsupported goal action and original responsibility required')
        materials={x['id']:x for x in current['materials']}
        for e in data.evidence:
            if not (r:=materials.get(str(e.id))) or (e.version,e.source_sha256)!=(r['version'],r['source_sha256']):raise Conflict('exact current Case material supplement required')
        state=transition(None if item['state']=='NOT_REQUESTED' else item['state'],data.action,p['id']==parent['owner_id'])
        event=dict(id=str(uuid4()),revision=current['revision']+1,actor_id=p['id'],request_key=key,fingerprint=fp,request=data.model_dump(mode='json'),state=state)
        plan.setdefault('manual_goal_requests',[]).append(event);ledger(parent,plan)
        # Recheck current authority after the last possible lock wait, before save.
        context(store,c,token,id,True);steps._save(c,parent,plan)
        return dict(view(store,c,p,parent,plan),event=event,original_result=event)
