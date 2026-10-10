"""Adopted bounded adapter plans: coordination records and verified local outputs.

Business operations remain in their existing adapters. Neither an intention nor
a reported obstacle is execution, acceptance, authorization, or fulfillment.
"""
from copy import deepcopy
import re
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg.types.json import Jsonb

from . import bounded_planning as planning, controlled_plans as cp
from . import preparation as prep, case_lifecycle as life, executor_receipts as er
from .store import Conflict, Denied

SCOPE='SYNTHETIC_REGISTERED_CASE_ADAPTER_PLAN'
ROLES={'P1':('enterprise_operator','park_specialist'),
       'P2':('enterprise_operator',),'P3':('park_specialist','service_executor'),
       'P4':('enterprise_operator','service_executor'),'P5':('enterprise_operator',)}
LIMIT=64


class Adopt(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    expected_preparation_revision:int=Field(ge=1,le=64)
    expected_request_revision:int=Field(ge=1,le=64)
    expected_source_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    expected_plan_revision:int=Field(default=0,ge=0,le=64)
    required_goals:list[Annotated[str,Field(min_length=1,max_length=160)]]=Field(min_length=1,max_length=8)
    reason:str=Field(min_length=1,max_length=1000)


class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    action:Literal['BEGIN','REPORT_FAILURE','RETRY','VERIFY','LOCK','UNLOCK']
    step_id:UUID=Field(strict=False)
    expected_revision:int=Field(ge=1,le=63)
    expected_source_sha256:str|None=Field(default=None,pattern='^[a-f0-9]{64}$')
    reason:str=Field(min_length=1,max_length=1000)

    @model_validator(mode='after')
    def source_check(self):
        if (self.action in ('VERIFY','LOCK'))!=(self.expected_source_sha256 is not None):
            raise ValueError('VERIFY and LOCK require the current adapter source hash')
        return self


class ServicePlanBlocked(cp.PlanBlocked):
    kind='SERVICE_CASE_PLAN'

    def __init__(self,parent,plan,index,message='adopted service plan prerequisites need explicit verification'):
        Conflict.__init__(self,message)
        self.preparation_id=parent['id'];self.plan_id=plan['id']
        self.revision=plan['revision'];self.index=index


def _catalog(c,parent):
    from .catalog_publication import snapshot
    return snapshot(c,parent)


def _binding(c,parent):
    return dict(request_intent=cp._normal(parent.get('request_intent')),original_goal=parent['goal'],
                service_id=parent['service_id'],service_version=parent['service_version'],
                catalog=_catalog(c,parent),registry=dict(steps=planning.REGISTRY,actions=planning.ACTIONS))


def _binding_issues(c,parent,plan):
    current=_binding(c,parent);saved=plan['binding']
    labels={'request_intent':'REQUEST_CHANGED','original_goal':'REQUEST_CHANGED',
            'service_id':'SERVICE_CHANGED','service_version':'SERVICE_CHANGED',
            'catalog':'CATALOG_CHANGED','registry':'REGISTRY_CHANGED'}
    return sorted({labels[k] for k in labels if cp._normal(saved.get(k))!=cp._normal(current.get(k))})


def _supported(parent):
    goals=(parent.get('request_intent') or {}).get('required_goals',[])
    coverage,nodes=planning.compile(goals)
    return bool(goals and nodes and all(g['status']=='SUPPORTED_PREVIEW' for g in coverage))


def current_sources(store,c,parent,plan):
    issues,sources=cp._sources(store,c,parent)
    fixed=cp._row(c,parent['id'])
    if not fixed and _supported(parent):
        issues['P1']=[s for s in issues['P1'] if s!='REQUEST_GOAL_COVERAGE_REQUIRED']
    dispatch=c.execute('SELECT * FROM service_dispatches WHERE preparation_id=%s',(parent['id'],)).fetchone()
    offer=c.execute('SELECT * FROM service_dispatch_offers WHERE id=%s',(dispatch['current_offer_id'],)).fetchone() if dispatch else None
    step=er.current_step(c,parent)
    receipt=er._current(c,step) if step else None
    acceptance=c.execute("SELECT id,dispatch_id,offer_id,revision,actor_id,action,payload FROM service_dispatch_events WHERE offer_id=%s AND action='ACCEPT' ORDER BY revision DESC LIMIT 1",(offer['id'],)).fetchone() if offer else None
    sources['P3'].update(dispatch_id=str(dispatch['id']) if dispatch else None,
                         offer_id=str(offer['id']) if offer else None,
                         executor_id=offer['executor_id'] if offer else None,
                         offer_state=offer['state'] if offer else None,
                         acceptance_event=cp._normal(acceptance),
                         receipt_step_id=str(step['id']) if step else None,
                         receipt_step_preparation_revision=step['preparation_revision'] if step else None,
                         receipt_step_preparation_sha256=step['preparation_sha256'] if step else None)
    if offer and offer['state']=='ACCEPTED' and (not step or offer['receipt_step_id']!=step['id'] or offer['executor_id']!=step['executor_id']):
        issues['P3'].append('RECEIPT_ACCEPTANCE_BINDING_CHANGED')
    if step and tuple(step[k] for k in ('preparation_id','case_id','run_id','owner_id','park_id','org_id','service_id','service_version'))!=tuple(parent[k] for k in ('id','case_id','run_id','owner_id','park_id','org_id','service_id','service_version')):
        issues['P3'].append('RECEIPT_ACCEPTANCE_BINDING_CHANGED')
    if step and not er._fresh(step,parent,c,store,check_execution=False):issues['P3'].append('RECEIPT_ACCEPTANCE_PREPARATION_CHANGED')
    if offer and offer['state']=='ACCEPTED' and not acceptance:issues['P3'].append('ACCEPTANCE_EVENT_REQUIRED')
    if acceptance and offer and dispatch:
        expected=dict(dispatch_id=str(dispatch['id']),offer_id=str(offer['id']),receipt_step_id=str(step['id']) if step else None,
                      action='ACCEPT',state='ACCEPTED',actor_id=offer['executor_id'],executor_id=offer['executor_id'],revision=dispatch['revision'])
        if acceptance['dispatch_id']!=dispatch['id'] or acceptance['offer_id']!=offer['id'] or acceptance['revision']!=dispatch['revision'] or acceptance['actor_id']!=offer['executor_id'] or any(acceptance['payload'].get(k)!=v for k,v in expected.items()):
            issues['P3'].append('ACCEPTANCE_EVENT_PROVENANCE_CHANGED')
    receipt_events=c.execute("SELECT id,step_id,revision,actor_id,action,payload FROM service_receipt_events WHERE step_id=%s AND payload->>'receipt_id'=%s ORDER BY revision",(step['id'],str(receipt['id']))).fetchall() if receipt else []
    receipt_versions=c.execute('SELECT id,version FROM service_step_receipts WHERE step_id=%s ORDER BY version',(step['id'],)).fetchall() if receipt else []
    sources['P4'].update(receipt_version=receipt['version'] if receipt else None,
                         receipt_actor_id=receipt['actor_id'] if receipt else None,
                         receipt_source_kind=receipt['source_kind'] if receipt else None,
                         receipt_versions=cp._normal(receipt_versions),
                         receipt_events=cp._normal(receipt_events))
    if receipt and step and not er._fresh(step,parent,c,store):
        issues['P4'].append('CURRENT_RECEIPT_EXECUTION_REQUIRED')
    if receipt and step and step['state']=='LOCAL_ACKNOWLEDGED':
        def matches(event,action,actor,state):
            expected=dict(step_id=str(step['id']),revision=event['revision'],action=action,actor_id=actor,
                          state=state,receipt_id=str(receipt['id']),receipt_sha256=receipt['source_sha256'],scope=er.SCOPE)
            return event['step_id']==step['id'] and event['action']==action and event['actor_id']==actor and all(event['payload'].get(k)==v for k,v in expected.items())
        submitted=[e for e in receipt_events if matches(e,'SUBMIT',step['executor_id'],'RECEIPT_RECORDED')]
        acknowledged=[e for e in receipt_events if matches(e,'ACKNOWLEDGE',step['owner_id'],'LOCAL_ACKNOWLEDGED') and e['revision']==step['revision']]
        version_bound=bool(receipt_versions and [r['version'] for r in receipt_versions]==list(range(1,len(receipt_versions)+1)) and receipt_versions[-1]['id']==receipt['id'] and receipt_versions[-1]['version']==receipt['version'])
        if receipt['step_id']!=step['id'] or not version_bound or len(submitted)!=1 or len(acknowledged)!=1 or submitted[0]['revision']>=acknowledged[0]['revision']:
            issues['P4'].append('RECEIPT_EVENT_PROVENANCE_CHANGED')
    actual={'P1':parent['state'],'P2':'NOT_LINKED' if not sources['P2'].get('resource_link_id') else 'CURRENT_LINK' if not issues['P2'] else 'LINK_NEEDS_RECHECK',
            'P3':offer['state'] if offer else 'NOT_OFFERED','P4':step['state'] if step else 'NOT_ACCEPTED','P5':'NOT_STARTED'}
    if any(s['adapter_id']=='P5' for s in plan['steps']):
        owner=c.execute('SELECT * FROM principals WHERE id=%s',(parent['owner_id'],)).fetchone()
        checks,snapshot,group,holds,rules=life._sources(store,c,owner,parent)
        life._timed(c,checks,group,holds,rules)
        local=life._ledger(c,parent)
        actual['P5']=local['state'] if local else 'NOT_STARTED'
        issues['P5']=sorted({reason for reasons in checks.values() for reason in reasons})
        if not local or local['state'] not in ('READY','LOCAL_RECORD_CLOSED') or local['verified_sha256']!=life._sha(snapshot,local['cycle']):
            issues['P5'].append('CURRENT_LOCAL_CASE_REVALIDATION_REQUIRED')
        sources['P5']=dict(local_lifecycle=cp._normal(local),sources=snapshot)
    return {k:sorted(set(v)) for k,v in issues.items()},cp._normal(sources),actual


def _invalidate(plan,index):
    for step in plan['steps']:
        if int(step['adapter_id'][1:])>=index and step.get('verified_sha256'):
            step['invalidated']=True


def _manual_lock(plan,step):
    """An active lock must retain its original owner event and verified contents."""
    events=[e for e in plan['events'] if e['step_id']==step['id'] and e['action'] in ('LOCK','UNLOCK')]
    lock=step.get('manual_lock')
    if not events:
        if lock is not None:raise Conflict('service step lock proof missing')
        return None
    last=events[-1]
    if last['action']=='UNLOCK':
        if lock is not None:raise Conflict('service step unlock proof changed')
        return None
    expected=dict(event_id=last['id'],plan_id=plan['id'],step_id=step['id'],actor_id=plan['events'][0]['actor_id'],source_sha256=last['source_sha256'])
    if (lock!=expected or last['actor_id']!=expected['actor_id'] or last['source_sha256']!=cp._hash(last['sources']) or
        step.get('verified_sha256')!=last['source_sha256'] or cp._normal(step.get('verified_sources'))!=cp._normal(last['sources']) or
        step['coordination_state']!='VERIFIED'):
        raise Conflict('service step locked decision proof changed')
    return lock


def persist_rejected_observation(store,error):
    with store.connect() as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        parent=c.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(error.preparation_id,)).fetchone()
        plan=parent.get('service_case_plan') if parent else None
        if plan and plan['id']==error.plan_id and plan['revision']==error.revision:
            _invalidate(plan,error.index)
            c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),parent['id']))


def _inspect(store,c,parent,plan,observe=True,fresh_clock=False):
    if any(e['action'] in ('LOCK','UNLOCK') for e in plan['events']) or any(s.get('manual_lock') is not None for s in plan['steps']):
        _recovery_proofs(parent)
    binding_issues=_binding_issues(c,parent,plan)
    issues,sources,actual=current_sources(store,c,parent,plan)
    if fresh_clock:issues,sources,actual=current_sources(store,c,parent,plan)
    states={};bad=None
    for step in plan['steps']:
        adapter=step['adapter_id'];prior=all(states.get(dep)=='VERIFIED' for dep in step['depends_on'])
        lock=_manual_lock(plan,step)
        changed=bool(step.get('verified_sha256') and (binding_issues or issues[adapter] or step['verified_sha256']!=cp._hash(sources[adapter])))
        if changed and bad is None:bad=int(adapter[1:])
        if changed:_invalidate(plan,int(adapter[1:]))
        state=step['coordination_state']
        if lock and (binding_issues or not prior or step.get('invalidated') or issues[adapter]):state='LOCK_CONFLICT'
        elif binding_issues or not prior:state='BLOCKED'
        elif state=='REPORTED_BLOCKED':pass
        elif step.get('invalidated'):state='NEEDS_RECHECK'
        elif step.get('verified_sha256') and not issues[adapter]:state='VERIFIED'
        states[adapter]=state
    if observe and bad:
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),parent['id']))
    return binding_issues,issues,sources,actual,states,bad


def gate(store,c,parent,through,*,observe=True):
    plan=deepcopy(parent.get('service_case_plan'))
    if not plan:return
    binding_issues,issues,sources,actual,states,bad=_inspect(store,c,parent,plan,observe=observe)
    required=[s for s in plan['steps'] if int(s['adapter_id'][1:])<=through]
    failed=next((s for s in required if states[s['adapter_id']]!='VERIFIED'),None)
    if binding_issues or failed:
        index=bad or (int(failed['adapter_id'][1:]) if failed else 1)
        raise ServicePlanBlocked(parent,plan,index)


def _context(store,c,token,id,write=False):
    p,parent=cp._auth(store,c,token,id)
    if write and p['role']=='enterprise_operator':store.check_capability(c,p,'EXECUTE')
    return p,parent


def _allowed(p,step,states,binding_issues,issues,sources,revision,lock_count=0):
    if revision>=LIMIT:return []
    if step.get('manual_lock'):
        return ['UNLOCK'] if p['role']=='enterprise_operator' and p.get('_plan_write') else []
    if revision+1+lock_count>LIMIT:return []
    if binding_issues:return []
    if p['role']=='service_executor' and (sources['P3'].get('offer_state')!='ACCEPTED' or not sources['P3'].get('receipt_step_id') or issues['P3']):return []
    adapter=step['adapter_id'];prior=all(states.get(dep)=='VERIFIED' for dep in step['depends_on'])
    if not prior:return []
    actions=[]
    if p['role'] in ROLES[adapter] and (p['role']!='enterprise_operator' or p.get('_plan_write')):
        if states[adapter] in ('PENDING','NEEDS_RECHECK'):actions.append('BEGIN')
        if states[adapter] in ('PENDING','IN_PROGRESS','NEEDS_RECHECK'):actions.append('REPORT_FAILURE')
        if step['coordination_state']=='REPORTED_BLOCKED':actions.append('RETRY')
    if p['role']=='enterprise_operator' and p.get('_plan_write') and not issues[adapter] and states[adapter]!='VERIFIED' and step['coordination_state']!='REPORTED_BLOCKED':actions.append('VERIFY')
    if p['role']=='enterprise_operator' and p.get('_plan_write') and not issues[adapter] and states[adapter]=='VERIFIED' and revision+2+lock_count<=LIMIT:actions.append('LOCK')
    return actions


def _view(store,c,p,parent,plan,event=None,observe=True,fresh_clock=False):
    owner=p['role']=='enterprise_operator';cp._write_flag(store,c,p)
    context=dict(role=p['role'],actor_ref=cp._hash(dict(actor_id=p['id'])),preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
                 preparation_revision=parent['revision'],request_revision=(parent.get('request_intent') or {}).get('revision',0),
                 current_preview=planning._proposal(store,c,p,parent) if owner else None)
    if not plan:return dict(**context,scope=SCOPE,state='NOT_ADOPTED',plan_id=None,revision=0,steps=[],history=[],events=[],can_adopt=owner and p.get('_plan_write') and context['current_preview']['state']=='COVERED_PREVIEW_ONLY',new_grants=False,automatic_execution=False,case_goal_completed=False)
    binding_issues,issues,sources,actual,states,bad=_inspect(store,c,parent,plan,observe=observe,fresh_clock=fresh_clock)
    steps=[]
    for step in plan['steps']:
        adapter=step['adapter_id']
        # Executors never receive the current other executor's offer or sources.
        own=owner or p['role']=='park_specialist' or sources['P3'].get('executor_id')==p['id']
        steps.append(dict(id=step['id'],adapter_id=adapter,adapter=step['adapter'],depends_on=step['depends_on'],
                          state=states[adapter],actual_business_state=actual[adapter] if own and not (p['role']=='park_specialist' and adapter=='P4') else None,
                          allowed_actions=_allowed(p,step,states,binding_issues,issues,sources,plan['revision'],sum(bool(s.get('manual_lock')) for s in plan['steps'])) if own else [],
                          source_sha256=cp._hash(sources[adapter]) if owner else None,
                          issues=issues[adapter] if owner else None,
                          verified_sources=step.get('verified_sources') if owner else None,
                          verified_sha256=step.get('verified_sha256') if owner else None,
                          manually_locked=bool(step.get('manual_lock'))))
    status='VERIFIED' if all(v=='VERIFIED' for v in states.values()) else 'BLOCKED' if binding_issues or any(v in ('BLOCKED','REPORTED_BLOCKED','LOCK_CONFLICT') for v in states.values()) else 'NEEDS_RECHECK' if any(v=='NEEDS_RECHECK' for v in states.values()) else 'ACTIVE'
    direct=[s['id'] for s in plan['steps'] if s.get('verified_sha256') and (issues[s['adapter_id']] or s['verified_sha256']!=cp._hash(sources[s['adapter_id']]))]
    affected=[s['id'] for s in plan['steps'] if binding_issues or s.get('invalidated') or states[s['adapter_id']] in ('BLOCKED','LOCK_CONFLICT')]
    impact=dict(scope='REGISTERED_CASE_CHAIN',unknown_scope='THIS_CASE' if binding_issues else None,
                directly_changed=direct,affected=affected,preserved=[s['id'] for s in plan['steps'] if s['id'] not in affected])
    events=plan['events'] if owner else [{k:e[k] for k in ('id','revision','action','step_id')} for e in plan['events']]
    receipt=None
    if event and event['actor_id']==p['id']:
        plans=plan.get('history',[])+[plan];index=next(i for i,item in enumerate(plans) if item['id']==event['plan_id'])
        previous=plans[index-1] if index and event['action']=='ADOPT' else None
        receipt=dict(id=event['id'],plan_id=event['plan_id'],revision=event['revision'],action=event['action'],step_id=event['step_id'],
                     request_key=event['request_key'],actor_ref=context['actor_ref'],expected_revision=previous['revision'] if previous else 0 if event['action']=='ADOPT' else event['revision']-1,
                     previous_plan_id=previous['id'] if previous else None)
    return dict(**context,scope=SCOPE,plan_id=plan['id'],revision=plan['revision'],state=status,steps=steps,
                binding=plan['binding'] if owner else None,binding_issues=binding_issues if owner else None,
                required_goals=plan['required_goals'] if owner else None,goal_coverage=plan['goal_coverage'] if owner else None,
                history=plan.get('history',[]) if owner else [],events=events,event=event if owner else None,command_receipt=receipt,
                can_adopt=owner and p.get('_plan_write') and bool(binding_issues) and not any(s.get('manual_lock') for s in plan['steps']) and len(plan.get('history',[]))<8 and context['current_preview']['state']=='COVERED_PREVIEW_ONLY',
                change_impact=impact if owner else None,
                new_grants=False,automatic_execution=False,case_goal_completed=False,
                external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE')


def _replay(c,p,parent,key,fp):
    rows=c.execute("SELECT id,service_case_plan FROM preparations WHERE jsonb_path_exists(service_case_plan,'$.** ? (@.actor_id == $actor && @.request_key == $key)',%s)",
                   (Jsonb(dict(actor=p['id'],key=key)),)).fetchall()
    for row in rows:
        plans=[row['service_case_plan']]+row['service_case_plan'].get('history',[])
        for plan in plans:
            for event in plan['events']:
                if event['actor_id']==p['id'] and event['request_key']==key:
                    if row['id']!=parent['id'] or event['fingerprint']!=fp:raise Conflict('service plan key fingerprint or Case scope changed')
                    return event


def _event(plan,p,key,fp,action,reason,step=None,sources=None):
    if len(plan['events'])>=LIMIT:raise Conflict('service plan event limit reached')
    event=dict(id=str(uuid4()),plan_id=plan['id'],revision=plan['revision'],actor_id=p['id'],request_key=key,fingerprint=fp,
               action=action,reason=reason,step_id=step['id'] if step else None,
               source_sha256=cp._hash(sources) if sources is not None else None,
               sources=sources,coordination_only=action!='VERIFY')
    plan['events'].append(event);return event


def _save(c,parent,plan):
    c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),parent['id']))


@er.bounded
def read(store,token,id):
    with store.connect() as c:
        p,parent=_context(store,c,token,id)
        return _view(store,c,p,parent,deepcopy(parent.get('service_case_plan')))


def _recovery_proofs(parent):
    """Bounded structural and original fingerprint proof, never an admin signature."""
    root=parent.get('service_case_plan')
    if root is None:return []
    try:
        history=root.get('history',[])
        if not isinstance(history,list) or len(history)>8:raise ValueError()
        plans=history+[root];ids=set();event_ids=set();keys=set();proofs=[]
        for index,plan in enumerate(plans):
            UUID(plan['id'])
            if plan['id'] in ids or type(plan['revision']) is not int or not 1<=plan['revision']<=64 or len(plan['events'])!=plan['revision'] or (index<len(history) and plan.get('history')):raise ValueError()
            ids.add(plan['id']);step_ids=set()
            if any(plan['adoption_preview'].get(k)!=str(parent[v]) for k,v in (('preparation_id','id'),('case_id','case_id'),('run_id','run_id'))):raise ValueError()
            if not 1<=len(plan['steps'])<=5:raise ValueError()
            for step in plan['steps']:
                UUID(step['id'])
                if step['id'] in step_ids or step['adapter_id'] not in ROLES:raise ValueError()
                step_ids.add(step['id'])
            for revision,event in enumerate(plan['events'],1):
                UUID(event['id'])
                legacy_adoption_key = (revision == 1 and event['action'] == 'ADOPT' and
                    isinstance(event['request_key'], str) and bool(re.fullmatch(
                        r'tc:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:ADOPT_PLAN', event['request_key'])))
                if (event['id'] in event_ids or type(event['revision']) is not int or event['revision']!=revision or event['plan_id']!=plan['id'] or
                    (event['actor_id'],event['request_key']) in keys or type(event['actor_id']) is not str or
                    type(event['request_key']) is not str or not (re.fullmatch('[A-Za-z0-9_-]{1,100}',event['request_key']) or legacy_adoption_key) or
                    type(event['coordination_only']) is not bool or type(event['reason']) is not str or not 1<=len(event['reason'])<=1000):raise ValueError()
                event_ids.add(event['id']);keys.add((event['actor_id'],event['request_key']))
                previous=plans[index-1] if index else None
                if revision==1:
                    if event['action']!='ADOPT' or event['step_id'] is not None or event['actor_id']!=parent['owner_id']:raise ValueError()
                    expected=previous['revision'] if previous else 0
                    data=Adopt(expected_preparation_revision=plan['adoption_preparation_revision'],expected_request_revision=plan['binding']['request_intent']['revision'],
                               expected_plan_revision=expected,expected_source_sha256=plan['adoption_preview']['source_sha256'],required_goals=plan['required_goals'],reason=event['reason'])
                    fp=cp._hash(dict(preparation_id=str(parent['id']),action='ADOPT',**data.model_dump()))
                else:
                    if event['step_id'] not in step_ids or event['action']=='ADOPT':raise ValueError()
                    expected=revision-1
                    data=Command(action=event['action'],step_id=event['step_id'],expected_revision=expected,
                                 expected_source_sha256=event['source_sha256'] if event['action'] in ('VERIFY','LOCK') else None,reason=event['reason'])
                    fp=cp._hash(dict(preparation_id=str(parent['id']),**data.model_dump(mode='json')))
                    if event['action'] in ('VERIFY','LOCK','UNLOCK') and event['actor_id']!=parent['owner_id']:raise ValueError()
                    if event['action'] in ('VERIFY','LOCK') and event['source_sha256']!=cp._hash(event['sources']):raise ValueError()
                if event['fingerprint']!=fp or event['coordination_only']!=(event['action']!='VERIFY'):raise ValueError()
                if event['action'] not in ('VERIFY','LOCK') and (event['source_sha256'] is not None or event['sources'] is not None):raise ValueError()
                proofs.append((plan,event,expected,previous))
        return proofs
    except (KeyError,TypeError,ValueError,AttributeError):raise Conflict('original service plan recovery proof invalid')


@er.bounded
def recover(store,token,id,key=None):
    """Current original actor reads an immutable key proof; never replay/observe-write."""
    with store.connect() as c:
        p,parent=_context(store,c,token,id,key is not None)
        if key is not None:prep.key_lock(c,p,'service-case-plan:'+key)
        proofs=_recovery_proofs(parent)
        matches=[proof for proof in proofs if key is not None and proof[1]['actor_id']==p['id'] and proof[1]['request_key']==key]
        if len(matches)>1:raise Conflict('original service plan recovery key ambiguous')
        if key is not None and not matches and any(proof[1]['request_key']==key for proof in proofs):raise Denied('original service plan actor required')
        # Reuse the original global actor/key scope boundary without exposing another Case.
        rows=c.execute("SELECT id FROM preparations WHERE jsonb_path_exists(service_case_plan,'$.** ? (@.actor_id == $actor && @.request_key == $key)',%s)",(Jsonb(dict(actor=p['id'],key=key)),)).fetchall() if key is not None else []
        if any(row['id']!=id for row in rows):raise Conflict('original service plan recovery Case changed')
        original=None
        if matches:
            plan,event,expected,previous=matches[0]
            step=next((s for s in plan['steps'] if s['id']==event['step_id']),None)
            if event['action'] in ('ADOPT','VERIFY','LOCK','UNLOCK'):
                if p['role']!='enterprise_operator':raise Denied('original owner plan action required')
            elif not step or p['role'] not in ROLES[step['adapter_id']]:raise Denied('original adapter actor required')
            original=dict(id=event['id'],plan_id=plan['id'],revision=event['revision'],action=event['action'],step_id=event['step_id'],
                          expected_revision=expected,previous_plan_id=previous['id'] if previous and event['action']=='ADOPT' else None,
                          actor_ref=cp._hash(dict(actor_id=p['id'])),request_key=key,historical_only=True,
                          current_plan=plan['id']==parent['service_case_plan']['id'])
        if key is not None and p['role']=='service_executor':
            offer=c.execute('SELECT o.* FROM service_dispatch_offers o JOIN service_dispatches d ON d.current_offer_id=o.id WHERE d.preparation_id=%s',(id,)).fetchone()
            if not offer or offer['executor_id']!=p['id']:raise Denied('own current adapter offer required')
        view=_view(store,c,p,parent,deepcopy(parent.get('service_case_plan')),observe=False,fresh_clock=True)
        # Source locks may have waited beyond a Run access deadline. Recheck after all waits.
        _context(store,c,token,id,key is not None)
        for step in view['steps']:
            step.update(allowed_actions=[],source_sha256=None,verified_sources=None,verified_sha256=None)
        view.update(current_preview=None,binding=None,required_goals=None,goal_coverage=None,can_adopt=False,command_receipt=None,
                    events=[{k:e[k] for k in ('id','revision','action','step_id')} for e in view['events']],
                    history=[{k:h[k] for k in ('id','revision')} for h in view['history']],read_only=True)
        return dict(scope=SCOPE,preparation_id=str(id),case_id=str(parent['case_id']),run_id=str(parent['run_id']),actor_ref=view['actor_ref'],
                    status='NO_REQUEST' if key is None else 'COMMITTED' if original else 'NOT_OBSERVED',event=original,current=view,
                    historical_only=True,automatically_replayed=False,read_only=True,case_goal_completed=False)


@er.bounded
def adopt(store,token,id,key,data):
    with store.connect() as c:
        p,parent=_context(store,c,token,id,True)
        if p['role']!='enterprise_operator':raise Denied('owner adopted plan required')
        prep.key_lock(c,p,'service-case-plan:'+key)
        fp=cp._hash(dict(preparation_id=str(id),action='ADOPT',**data.model_dump()))
        old=_replay(c,p,parent,key,fp);prior=deepcopy(parent.get('service_case_plan'))
        if old:return _view(store,c,p,parent,prior,old)
        intent=parent.get('request_intent')
        if not intent or not _supported(parent) or data.required_goals!=intent['required_goals'] or intent['revision']!=data.expected_request_revision:
            raise Conflict('explicit supported current request goals required')
        if parent['revision']!=data.expected_preparation_revision:raise Conflict('preparation revision changed')
        current=planning._proposal(store,c,p,parent)
        if current['state']!='COVERED_PREVIEW_ONLY' or current['source_sha256']!=data.expected_source_sha256:
            raise Conflict('current bounded planning preview required')
        binding=cp._normal(_binding(c,parent))
        if cp._hash(binding['catalog'])!=current['catalog_sha256'] or cp._hash(binding['registry'])!=current['registry_sha256']:
            raise Conflict('catalog or registry changed during service plan adoption')
        if (prior['revision'] if prior else 0)!=data.expected_plan_revision:raise Conflict('service plan revision changed')
        history=[]
        if prior:
            if any(e['action'] in ('LOCK','UNLOCK') for e in prior['events']):_recovery_proofs(parent)
            if any(_manual_lock(prior,s) for s in prior['steps']):raise Conflict('locked service step decisions require explicit unlock before replacement')
            if not _binding_issues(c,parent,prior):raise Conflict('current adopted plan already exists')
            history=prior.pop('history',[])+[prior]
            if len(history)>8:raise Conflict('service plan replacement history limit reached')
        steps=[dict(id=str(uuid4()),adapter_id=s['id'],adapter=s['adapter'],adapter_revision=s['revision'],
                    depends_on=s['depends_on'],contract=cp._normal(s),coordination_state='PENDING',
                    verified_sha256=None,verified_sources=None,invalidated=False) for s in current['steps']]
        plan=dict(id=str(uuid4()),revision=1,required_goals=list(data.required_goals),goal_coverage=current['goal_coverage'],
                  binding=binding,adoption_preparation_revision=parent['revision'],
                  adoption_preview=current,steps=steps,events=[],history=history)
        event=_event(plan,p,key,fp,'ADOPT',data.reason)
        _save(c,parent,plan)
        return _view(store,c,p,parent,plan,event)


@er.bounded
def command(store,token,id,key,data):
    with store.connect() as c:
        p,parent=_context(store,c,token,id,True);cp._write_flag(store,c,p)
        plan=deepcopy(parent.get('service_case_plan'))
        if not plan:raise Conflict('adopted service plan required')
        step=next((s for history in [plan]+plan.get('history',[]) for s in history['steps'] if s['id']==str(data.step_id)),None)
        if not step:raise Conflict('step belongs to another adopted plan')
        if data.action in ('VERIFY','LOCK','UNLOCK') and p['role']!='enterprise_operator':raise Denied('owner source decision required')
        if data.action not in ('VERIFY','LOCK','UNLOCK') and p['role'] not in ROLES[step['adapter_id']]:raise Denied('adapter coordination role required')
        if p['role']=='service_executor':
            offer=c.execute('SELECT o.* FROM service_dispatch_offers o JOIN service_dispatches d ON d.current_offer_id=o.id WHERE d.preparation_id=%s',(id,)).fetchone()
            if not offer or offer['executor_id']!=p['id']:raise Denied('own current adapter offer required')
        prep.key_lock(c,p,'service-case-plan:'+key)
        fp=cp._hash(dict(preparation_id=str(id),**data.model_dump(mode='json')))
        old=_replay(c,p,parent,key,fp)
        if old:return _view(store,c,p,parent,plan,old)
        if not any(s['id']==str(data.step_id) for s in plan['steps']):raise Conflict('historical step requires its existing command key')
        binding_issues,issues,sources,actual,states,bad=_inspect(store,c,parent,plan)
        if plan['revision']!=data.expected_revision or plan['revision']>=LIMIT:raise Conflict('service plan revision changed or exhausted')
        if step.get('manual_lock') and data.action!='UNLOCK':raise Conflict('locked service step decision requires explicit unlock')
        lock_count=sum(bool(s.get('manual_lock')) for s in plan['steps'])
        if data.action!='UNLOCK' and plan['revision']+1+lock_count+(data.action=='LOCK')>LIMIT:raise Conflict('event capacity reserved for explicit unlocks')
        if data.action not in _allowed(p,step,states,binding_issues,issues,sources,plan['revision'],lock_count):
            raise ServicePlanBlocked(parent,plan,bad or int(step['adapter_id'][1:]),'adapter sources, binding, reported obstacle or predecessors need recheck')
        adapter=step['adapter_id'];source=None
        if data.action in ('VERIFY','LOCK'):
            if data.expected_source_sha256!=cp._hash(sources[adapter]):
                if data.action=='LOCK':raise Conflict('current source fingerprint required for lock')
                raise ServicePlanBlocked(parent,plan,int(adapter[1:]),'adapter source changed')
            source=sources[adapter]
            if data.action=='VERIFY':step.update(coordination_state='VERIFIED',verified_sha256=cp._hash(source),verified_sources=source,invalidated=False)
        elif data.action=='UNLOCK':step['manual_lock']=None
        elif data.action=='REPORT_FAILURE':step.update(coordination_state='REPORTED_BLOCKED',invalidated=bool(step.get('verified_sha256')))
        else:step.update(coordination_state='IN_PROGRESS' if data.action=='BEGIN' else 'PENDING')
        if data.action not in ('VERIFY','LOCK','UNLOCK'):_invalidate(plan,int(adapter[1:]))
        plan['revision']+=1;event=_event(plan,p,key,fp,data.action,data.reason,step,source)
        if data.action=='LOCK':step['manual_lock']=dict(event_id=event['id'],plan_id=plan['id'],step_id=step['id'],actor_id=p['id'],source_sha256=event['source_sha256'])
        _context(store,c,token,id,True)
        _save(c,parent,plan)
        return _view(store,c,p,parent,plan,event)
