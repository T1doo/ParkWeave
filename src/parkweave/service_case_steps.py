"""Adopted bounded adapter plans: coordination records and verified local outputs.

Business operations remain in their existing adapters. Neither an intention nor
a reported obstacle is execution, acceptance, authorization, or fulfillment.
"""
from copy import deepcopy
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
    action:Literal['BEGIN','REPORT_FAILURE','RETRY','VERIFY']
    step_id:UUID=Field(strict=False)
    expected_revision:int=Field(ge=1,le=63)
    expected_source_sha256:str|None=Field(default=None,pattern='^[a-f0-9]{64}$')
    reason:str=Field(min_length=1,max_length=1000)

    @model_validator(mode='after')
    def source_check(self):
        if (self.action=='VERIFY')!=(self.expected_source_sha256 is not None):
            raise ValueError('only VERIFY requires the current adapter source hash')
        return self


class ServicePlanBlocked(cp.PlanBlocked):
    kind='SERVICE_CASE_PLAN'

    def __init__(self,parent,plan,index,message='adopted service plan prerequisites need explicit verification'):
        Conflict.__init__(self,message)
        self.preparation_id=parent['id'];self.plan_id=plan['id']
        self.revision=plan['revision'];self.index=index


def _catalog(c,parent):
    return cp._normal(c.execute('SELECT service_id,version,source,namespace,qualification FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',
                               (parent['park_id'],parent['service_id'],parent['service_version'])).fetchone())


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
    if step and not er._fresh(step,parent):issues['P3'].append('RECEIPT_ACCEPTANCE_PREPARATION_CHANGED')
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


def persist_rejected_observation(store,error):
    with store.connect() as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        parent=c.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(error.preparation_id,)).fetchone()
        plan=parent.get('service_case_plan') if parent else None
        if plan and plan['id']==error.plan_id and plan['revision']==error.revision:
            _invalidate(plan,error.index)
            c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),parent['id']))


def _inspect(store,c,parent,plan,observe=True):
    binding_issues=_binding_issues(c,parent,plan)
    issues,sources,actual=current_sources(store,c,parent,plan)
    states={};bad=None
    for step in plan['steps']:
        adapter=step['adapter_id'];prior=all(states.get(dep)=='VERIFIED' for dep in step['depends_on'])
        changed=bool(step.get('verified_sha256') and (binding_issues or issues[adapter] or step['verified_sha256']!=cp._hash(sources[adapter])))
        if changed and bad is None:bad=int(adapter[1:])
        if changed:_invalidate(plan,int(adapter[1:]))
        state=step['coordination_state']
        if binding_issues or not prior:state='BLOCKED'
        elif state=='REPORTED_BLOCKED':pass
        elif step.get('invalidated'):state='NEEDS_RECHECK'
        elif step.get('verified_sha256') and not issues[adapter]:state='VERIFIED'
        states[adapter]=state
    if observe and bad:
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),parent['id']))
    return binding_issues,issues,sources,actual,states,bad


def gate(store,c,parent,through):
    plan=deepcopy(parent.get('service_case_plan'))
    if not plan:return
    binding_issues,issues,sources,actual,states,bad=_inspect(store,c,parent,plan)
    required=[s for s in plan['steps'] if int(s['adapter_id'][1:])<=through]
    failed=next((s for s in required if states[s['adapter_id']]!='VERIFIED'),None)
    if binding_issues or failed:
        index=bad or (int(failed['adapter_id'][1:]) if failed else 1)
        raise ServicePlanBlocked(parent,plan,index)


def _context(store,c,token,id,write=False):
    p,parent=cp._auth(store,c,token,id)
    if write and p['role']=='enterprise_operator':store.check_capability(c,p,'EXECUTE')
    return p,parent


def _allowed(p,step,states,binding_issues,issues,sources,revision):
    if binding_issues or revision>=LIMIT:return []
    if p['role']=='service_executor' and (sources['P3'].get('offer_state')!='ACCEPTED' or not sources['P3'].get('receipt_step_id') or issues['P3']):return []
    adapter=step['adapter_id'];prior=all(states.get(dep)=='VERIFIED' for dep in step['depends_on'])
    if not prior:return []
    actions=[]
    if p['role'] in ROLES[adapter] and (p['role']!='enterprise_operator' or p.get('_plan_write')):
        if states[adapter] in ('PENDING','NEEDS_RECHECK'):actions.append('BEGIN')
        if states[adapter] in ('PENDING','IN_PROGRESS','NEEDS_RECHECK'):actions.append('REPORT_FAILURE')
        if step['coordination_state']=='REPORTED_BLOCKED':actions.append('RETRY')
    if p['role']=='enterprise_operator' and p.get('_plan_write') and not issues[adapter] and states[adapter]!='VERIFIED' and step['coordination_state']!='REPORTED_BLOCKED':actions.append('VERIFY')
    return actions


def _view(store,c,p,parent,plan,event=None):
    owner=p['role']=='enterprise_operator';cp._write_flag(store,c,p)
    context=dict(role=p['role'],preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
                 preparation_revision=parent['revision'],request_revision=(parent.get('request_intent') or {}).get('revision',0),
                 current_preview=planning._proposal(store,c,p,parent) if owner else None)
    if not plan:return dict(**context,scope=SCOPE,state='NOT_ADOPTED',plan_id=None,revision=0,steps=[],history=[],events=[],can_adopt=owner and p.get('_plan_write') and context['current_preview']['state']=='COVERED_PREVIEW_ONLY',new_grants=False,automatic_execution=False,case_goal_completed=False)
    binding_issues,issues,sources,actual,states,bad=_inspect(store,c,parent,plan)
    steps=[]
    for step in plan['steps']:
        adapter=step['adapter_id']
        # Executors never receive the current other executor's offer or sources.
        own=owner or p['role']=='park_specialist' or sources['P3'].get('executor_id')==p['id']
        steps.append(dict(id=step['id'],adapter_id=adapter,adapter=step['adapter'],depends_on=step['depends_on'],
                          state=states[adapter],actual_business_state=actual[adapter] if own and not (p['role']=='park_specialist' and adapter=='P4') else None,
                          allowed_actions=_allowed(p,step,states,binding_issues,issues,sources,plan['revision']) if own else [],
                          source_sha256=cp._hash(sources[adapter]) if owner else None,
                          issues=issues[adapter] if owner else None,
                          verified_sources=step.get('verified_sources') if owner else None,
                          verified_sha256=step.get('verified_sha256') if owner else None))
    status='VERIFIED' if all(v=='VERIFIED' for v in states.values()) else 'BLOCKED' if binding_issues or any(v in ('BLOCKED','REPORTED_BLOCKED') for v in states.values()) else 'NEEDS_RECHECK' if any(v=='NEEDS_RECHECK' for v in states.values()) else 'ACTIVE'
    events=plan['events'] if owner else [{k:e[k] for k in ('id','revision','action','step_id')} for e in plan['events']]
    return dict(**context,scope=SCOPE,plan_id=plan['id'],revision=plan['revision'],state=status,steps=steps,
                binding=plan['binding'] if owner else None,binding_issues=binding_issues if owner else None,
                required_goals=plan['required_goals'] if owner else None,goal_coverage=plan['goal_coverage'] if owner else None,
                history=plan.get('history',[]) if owner else [],events=events,event=event if owner else None,
                can_adopt=owner and p.get('_plan_write') and bool(binding_issues) and len(plan.get('history',[]))<8 and context['current_preview']['state']=='COVERED_PREVIEW_ONLY',
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
        if data.action=='VERIFY' and p['role']!='enterprise_operator':raise Denied('owner source verification required')
        if data.action!='VERIFY' and p['role'] not in ROLES[step['adapter_id']]:raise Denied('adapter coordination role required')
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
        if data.action not in _allowed(p,step,states,binding_issues,issues,sources,plan['revision']):
            raise ServicePlanBlocked(parent,plan,bad or int(step['adapter_id'][1:]),'adapter sources, binding, reported obstacle or predecessors need recheck')
        adapter=step['adapter_id'];source=None
        if data.action=='VERIFY':
            if data.expected_source_sha256!=cp._hash(sources[adapter]):raise ServicePlanBlocked(parent,plan,int(adapter[1:]),'adapter source changed')
            source=sources[adapter];step.update(coordination_state='VERIFIED',verified_sha256=cp._hash(source),verified_sources=source,invalidated=False)
        elif data.action=='REPORT_FAILURE':step.update(coordination_state='REPORTED_BLOCKED',invalidated=bool(step.get('verified_sha256')))
        else:step.update(coordination_state='IN_PROGRESS' if data.action=='BEGIN' else 'PENDING')
        if data.action!='VERIFY':_invalidate(plan,int(adapter[1:]))
        plan['revision']+=1;event=_event(plan,p,key,fp,data.action,data.reason,step,source)
        _save(c,parent,plan)
        return _view(store,c,p,parent,plan,event)
