"""Adopted bounded adapter plans: coordination records and verified local outputs.

Business operations remain in their existing adapters. Neither an intention nor
a reported obstacle is execution, acceptance, authorization, or fulfillment.
"""
from copy import deepcopy
from contextlib import contextmanager
import re
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from psycopg.types.json import Jsonb

from . import bounded_planning as planning, controlled_plans as cp
from . import preparation as prep, case_lifecycle as life, executor_receipts as er, registered_dependencies as dependencies
from .store import Conflict, Denied
from .source_change_adoption import OpportunityProof

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
    local_revision:Literal[True]|None=None
    partial_adoption:Literal[True]|None=None
    opportunity_proof:OpportunityProof|None=None
    fact_provenance_scope:Literal['EMPLOYEES_USER_ASSERTION_V1','EMPLOYEES_USER_ASSERTION_MANUAL_V1']|None=None
    dependency_scope:Literal['BOUNDED_MULTI_SOURCE_V1']|None=None

    candidate_id:str|None=Field(default=None,pattern='^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    expected_candidate_sha256:str|None=Field(default=None,pattern='^[a-f0-9]{64}$')
    expected_verification_sha256:str|None=Field(default=None,pattern='^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def paired_candidate(self):
        if self.dependency_scope is not None and (self.fact_provenance_scope is not None or self.local_revision is not True or self.opportunity_proof is None):raise ValueError('unified dependencies require a unique explicit opportunity local revision')
        if self.fact_provenance_scope is not None and (self.local_revision is not True or self.opportunity_proof is None):raise ValueError("fact provenance requires explicit opportunity local revision")
        values=(self.candidate_id,self.expected_candidate_sha256,self.expected_verification_sha256)
        if self.opportunity_proof is not None and (self.local_revision is not True or self.partial_adoption is not None):raise ValueError('opportunity proof requires explicit original local revision')
        if any(v is not None for v in values) and (not all(v is not None for v in values) or self.local_revision is not None):raise ValueError('complete candidate confirmation for adoption required')
        return self

    @field_validator('partial_adoption',mode='before')
    @classmethod
    def explicit_partial_confirmation(cls,value):
        if value is not None and value is not True:raise ValueError('partial adoption requires explicit boolean true')
        return value


def _adopt_request(data):
    # Missing optional extension must preserve every historical fingerprint.
    return data.model_dump(exclude_none=True)


def _source_scope(data):
    return {name:getattr(data,name) for name in ('fact_provenance_scope','dependency_scope') if getattr(data,name) is not None}


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


def _selection_plan(plan):
    return bool(plan.get('adoption_preview',{}).get('profile')=='TRUSTED_SERVICE_SELECTION_V4' or
        'service_selection' in plan.get('binding',{}) or
        (plan.get('candidate_consumption') or {}).get('verification_basis',{}).get('validator_version')==4)


def _candidate_module(parent,id):
    from . import service_plan_candidates as legacy
    records=[h for h in parent.get('planning_previews') or [] if h.get('id')==str(id)]
    if len(records)!=1:raise Conflict('exact original candidate required')
    record=records[0]
    if record.get('profile')=='LOCAL_SYNTHETIC_DEMO' or record.get('document',{}).get('profile')=='LOCAL_SYNTHETIC_DEMO':
        from . import local_demo_selections
        return local_demo_selections
    if (record.get('profile')=='TRUSTED_SERVICE_SELECTION_V4' or record.get('producer',{}).get('version')==4 or
        record.get('document',{}).get('profile')=='TRUSTED_SERVICE_SELECTION_V4' or 'selection' in record):
        from . import service_selection_candidates
        return service_selection_candidates
    return legacy


def _selection_catalog(store):
    from .service_capability_catalog import IsolatedServiceCapabilityCatalog
    catalog=getattr(store,'_isolated_service_capability_catalog',None)
    if type(catalog) is not IsolatedServiceCapabilityCatalog or catalog.consumer.store is not store:
        raise Denied('explicit owned service capability catalog required')
    return catalog


def _catalog_for_profile(store,profile):
    if profile=='LOCAL_SYNTHETIC_DEMO':
        from .local_synthetic_demo import LocalDemoCatalog
        catalog=getattr(store,'_local_synthetic_demo_catalog',None)
        if type(catalog) is not LocalDemoCatalog or catalog.store is not store:
            raise Denied('explicit independent local demo catalog required')
        return catalog
    if profile!='TRUSTED_SERVICE_SELECTION_V4':raise Denied('unknown service selection profile')
    return _selection_catalog(store)


def _selected_candidates(module):
    from . import service_selection_candidates,local_demo_selections
    return module in (service_selection_candidates,local_demo_selections)


def _binding_issues(c,parent,plan,*,store=None):
    current=_binding(c,parent);saved=plan['binding']
    labels={'request_intent':'REQUEST_CHANGED','original_goal':'REQUEST_CHANGED',
            'service_id':'SERVICE_CHANGED','service_version':'SERVICE_CHANGED',
            'catalog':'CATALOG_CHANGED','registry':'REGISTRY_CHANGED'}
    issues={labels[k] for k in labels if cp._normal(saved.get(k))!=cp._normal(current.get(k))}
    if _selection_plan(plan):
        try:
            selected=saved['service_selection']
            snapshot=_catalog_for_profile(store,selected['profile']).snapshot(c,parent)
            if (selected['capability_catalog_sha256']!=cp._hash(cp._normal(snapshot)) or snapshot['unknowns']):
                issues.add('SERVICE_CAPABILITY_BINDING_CHANGED')
        except (KeyError,TypeError,ValueError,Denied,Conflict):issues.add('CURRENT_SERVICE_CAPABILITY_SOURCE_REQUIRED')
    return sorted(issues)


def _supported(parent):
    goals=(parent.get('request_intent') or {}).get('required_goals',[])
    coverage,nodes=planning.compile(goals)
    return bool(goals and nodes and all(g['status']=='SUPPORTED_PREVIEW' for g in coverage))

def _initial_adoption_proof(parent,plan):
    # Even with both optional candidate fields missing, the original ADOPT
    # fingerprint cannot be reinterpreted as a legacy request.
    try:
        event=plan['events'][0];previous=(plan.get('history') or [None])[-1]
        data=Adopt(expected_preparation_revision=plan['adoption_preparation_revision'],
                   expected_request_revision=plan['binding']['request_intent']['revision'],
                   expected_plan_revision=previous['revision'] if previous else 0,
                   expected_source_sha256=plan['adoption_preview']['source_sha256'],
                   required_goals=plan['required_goals'],reason=event['reason'],
                   partial_adoption=True if plan.get('partial_adoption') is True else None)
        if plan.get('candidate_consumption') is not None or (plan.get('adoption_request') or {}).get('candidate_id') is not None:
            _recovery_proofs(parent)
            return
        if event['fingerprint']!=cp._hash(dict(preparation_id=str(parent['id']),action='ADOPT',**_adopt_request(data))):raise ValueError()
    except (KeyError,TypeError,ValueError,IndexError):raise Conflict('original initial adoption proof invalid')


def adopted_preview_steps(plan):
    """Prove the saved partial selection without rewriting historical contracts."""
    preview=plan['adoption_preview']
    if plan.get('partial_adoption') is not True:return preview['steps']
    offer=planning.partial_offer(preview['goal_coverage'],preview['steps'],
        known=not preview['source_unknowns'],constraints=preview.get('constraint_evaluation'),global_requirements=preview.get('global_requirements',[]),fixed_plan=preview.get('legacy_fixed_plan',False))
    if (not offer['can_adopt'] or preview.get('partial_offer')!=offer or preview['state']!='PARTIAL' or
        plan['required_goals']!=preview['required_goals'] or plan['goal_coverage']!=preview['goal_coverage'] or
        plan['required_goals']!=plan['binding']['request_intent']['required_goals']):
        raise Conflict('partial service plan selection proof invalid')
    request=Adopt.model_validate(plan['adoption_request']);event=plan['events'][0]
    if (request.partial_adoption is not True or request.local_revision is not None or
        request.required_goals!=plan['required_goals'] or request.expected_preparation_revision!=plan['adoption_preparation_revision'] or
        request.expected_request_revision!=plan['binding']['request_intent']['revision'] or
        request.expected_source_sha256!=preview['source_sha256'] or request.reason!=event['reason'] or
        event['action']!='ADOPT' or event['fingerprint']!=cp._hash(dict(preparation_id=preview['preparation_id'],action='ADOPT',**_adopt_request(request)))):
        raise Conflict('partial service plan explicit confirmation proof invalid')
    return [s for s in preview['steps'] if s['id'] in offer['step_ids']]

def current_partial(c,parent,plan,*,store=None):
    if plan.get('partial_adoption') is not True:return False
    adopted_preview_steps(plan);dependencies.plan_proof(parent,plan)
    return not _binding_issues(c,parent,plan,store=store)


def current_sources(store,c,parent,plan):
    issues,sources=cp._sources(store,c,parent)
    fixed=cp._row(c,parent['id'])
    if not fixed and (_selection_plan(plan) or _supported(parent) or current_partial(c,parent,plan,store=store)):
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
        checks,snapshot,group,holds,rules=life._record_sources(store,c,owner,parent)
        local=life._ledger(c,parent)
        life._ordinary_record_proof(store,c,parent,local)
        life._timed(c,checks,group,holds,rules)
        actual['P5']=local['state'] if local else 'NOT_STARTED'
        issues['P5']=sorted({reason for reasons in checks.values() for reason in reasons})
        if not local or local['state'] not in ('READY','LOCAL_RECORD_CLOSED') or local['verified_sha256']!=life._sha(snapshot,local['cycle']):
            issues['P5'].append('CURRENT_LOCAL_CASE_REVALIDATION_REQUIRED')
        sources['P5']=dict(local_lifecycle=cp._normal(local),sources=snapshot)
    values=dependencies.collections(store,c,parent)
    if plan.get('dependency_manifest') is not None:
        sources['P2']['resource_collection']=values['resources']
        sources['P3']['run_access_collection']=values['existing_access']
    if _selection_plan(plan):
        # A configured reference is a prerequisite, not evidence that the
        # original business action used that actor or resource. Check its output.
        for registered in plan['steps']:
            adapter=registered['adapter_id']
            for mapping in registered['contract'].get('instance_mappings',[]):
                roles=mapping['roles']
                if (roles['enterprise_operator']!=parent['owner_id'] or
                    roles.get('park_specialist',parent['reviewer_id'])!=parent['reviewer_id']):
                    issues[adapter].append('SELECTED_INSTANCE_ACTOR_BINDING_CHANGED')
                if adapter=='P2' and sources['P2'].get('resource_link_id'):
                    actual_ids={m['resource_id'] for m in sources['P2'].get('members') or []}
                    if actual_ids!=set(mapping['resources'].values()):issues['P2'].append('SELECTED_INSTANCE_RESOURCE_BINDING_CHANGED')
                if adapter=='P3' and offer and offer['executor_id']!=roles.get('service_executor'):
                    issues['P3'].append('SELECTED_INSTANCE_EXECUTOR_BINDING_CHANGED')
                if adapter=='P4' and step and step['executor_id']!=roles.get('service_executor'):
                    issues['P4'].append('SELECTED_INSTANCE_EXECUTOR_BINDING_CHANGED')
    from .template_migration import add_sources
    add_sources(parent,plan,sources)
    if any(s['adapter_id'] in ('P3','P4') for s in plan['steps']):
        cp.ordinary.guard_current(store,c,parent,sources['P3'].get('case_step_assignment'))
    return {k:sorted(set(v)) for k,v in issues.items()},cp._normal(sources),actual


def _invalidate(plan,index):
    reached=dependencies.closure(plan['steps'],{'P'+str(index)})
    for step in plan['steps']:
        if step['adapter_id'] in reached and step.get('verified_sha256'):
            step['invalidated']=True


def dependency_impact(store,c,parent,plan,issues=None):
    current,affected,unknown=dependencies.inspect(plan,dependencies.collections(store,c,parent))
    if issues is not None:
        for adapter in affected:issues[adapter]=sorted(set(issues[adapter]+['DEPENDENCY_REVISION_REQUIRES_EXPLICIT_ADOPT']))
    return current,affected,unknown


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
    with cp.connection(store) as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        parent=c.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(error.preparation_id,)).fetchone()
        if not parent or prep.case_write_blocked(c,parent):return
        plan=parent.get('service_case_plan')
        if plan and plan['id']==error.plan_id and plan['revision']==error.revision:
            _invalidate(plan,error.index)
            c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),parent['id']))


def _inspect(store,c,parent,plan,observe=True,fresh_clock=False):
    if prep.case_write_blocked(c,parent):observe=False
    dependencies.plan_proof(parent,plan)
    _initial_adoption_proof(parent,plan)
    if any(e['action'] in ('LOCK','UNLOCK') for e in plan['events']) or any(s.get('manual_lock') is not None for s in plan['steps']):
        _recovery_proofs(parent)
    binding_issues=_binding_issues(c,parent,plan,store=store)
    issues,sources,actual=current_sources(store,c,parent,plan)
    if fresh_clock:issues,sources,actual=current_sources(store,c,parent,plan)
    _,dependency_affected,_=dependency_impact(store,c,parent,plan,issues)
    for a in dependency_affected:_invalidate(plan,int(a[1:]))
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
    if observe and (bad or dependency_affected):
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),parent['id']))
    return binding_issues,issues,sources,actual,states,bad


def gate(store,c,parent,through,*,observe=True):
    plan=deepcopy(parent.get('service_case_plan'))
    if not plan:return
    from .template_migration import check_live
    if observe:check_live(store,c,parent,plan)
    if plan.get('partial_adoption') is True:
        selected={s['adapter_id'] for s in plan['steps']}
        # These gates precede P2 link, P3 dispatch, P4 receipt and P5 local
        # lifecycle operations respectively. A truncated partial graph cannot
        # admit an unselected operation through a vacuously true prerequisite.
        if not {'P'+str(i) for i in range(1,through+2)}<=selected:
            raise Conflict('operation is outside the explicitly adopted independent subgraph')
    binding_issues,issues,sources,actual,states,bad=_inspect(store,c,parent,plan,observe=observe)
    required=[s for s in plan['steps'] if int(s['adapter_id'][1:])<=through]
    failed=next((s for s in required if states[s['adapter_id']]!='VERIFIED'),None)
    if binding_issues or failed:
        index=bad or (int(failed['adapter_id'][1:]) if failed else 1)
        raise ServicePlanBlocked(parent,plan,index)


def _context(store,c,token,id,write=False):
    p,parent=cp._auth(store,c,token,id)
    if write:
        prep.case_write_guard(c,parent)
        if p['role']=='enterprise_operator':store.check_capability(c,p,'EXECUTE')
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
    cancelled=prep.case_write_blocked(c,parent)
    if cancelled:p['_plan_write']=False;observe=False
    preview=None;source_unavailable=False
    if owner:
        try:preview=planning._proposal(store,c,p,parent)
        except Conflict:
            if not plan or not _selection_plan(plan):raise
            _initial_adoption_proof(parent,plan)
            source_unavailable=True;observe=False
    context=dict(role=p['role'],actor_ref=cp._hash(dict(actor_id=p['id'])),preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
                 preparation_revision=parent['revision'],request_revision=(parent.get('request_intent') or {}).get('revision',0),
                 current_preview=preview)
    context.update(cp.ordinary.display_scope(store))
    if source_unavailable:context['current_source_unavailable']=True
    if not plan:return dict(**context,scope=SCOPE,state='NOT_ADOPTED',plan_id=None,revision=0,steps=[],history=[],events=[],can_adopt=owner and p.get('_plan_write') and context['current_preview']['state']=='COVERED_PREVIEW_ONLY',can_adopt_partial=bool(owner and p.get('_plan_write') and context['current_preview']['partial_offer']['can_adopt']),new_grants=False,automatic_execution=False,case_goal_completed=False)
    # A migrated read preserves stored decisions even when its live source expires.
    binding_issues,issues,sources,actual,states,bad=_inspect(store,c,parent,plan,observe=observe and not bool(plan.get('template_migration')),fresh_clock=fresh_clock)
    dependency_basis,dependency_affected,dependency_unknown=dependency_impact(store,c,parent,plan)
    from .template_migration import availability
    template_availability=availability(store,parent,plan)
    template_current=template_availability is None or template_availability['current']
    steps=[]
    for step in plan['steps']:
        adapter=step['adapter_id']
        # Executors never receive the current other executor's offer or sources.
        own=owner or p['role']=='park_specialist' or sources['P3'].get('executor_id')==p['id']
        allowed=_allowed(p,step,states,binding_issues,issues,sources,plan['revision'],sum(bool(s.get('manual_lock')) for s in plan['steps'])) if own and not cancelled else []
        if not template_current:allowed=[a for a in allowed if a=='UNLOCK']
        steps.append(dict(id=step['id'],adapter_id=adapter,adapter=step['adapter'],depends_on=step['depends_on'],
                          state=states[adapter] if template_current else 'LOCK_CONFLICT' if step.get('manual_lock') else 'NEEDS_RECHECK',actual_business_state=actual[adapter] if own and not (p['role']=='park_specialist' and adapter=='P4') else None,
                          allowed_actions=allowed,
                          source_sha256=cp._hash(sources[adapter]) if owner else None,
                          issues=sorted(set(issues[adapter]+([] if template_current else template_availability['reasons']))) if owner else None,
                          verified_sources=step.get('verified_sources') if owner else None,
                          verified_sha256=step.get('verified_sha256') if owner else None,
                          manually_locked=bool(step.get('manual_lock'))))
    status='VERIFIED' if all(v=='VERIFIED' for v in states.values()) else 'BLOCKED' if binding_issues or any(v in ('BLOCKED','REPORTED_BLOCKED','LOCK_CONFLICT') for v in states.values()) else 'NEEDS_RECHECK' if any(v=='NEEDS_RECHECK' for v in states.values()) else 'ACTIVE'
    if not template_current:status='BLOCKED'
    direct=[s['id'] for s in plan['steps'] if s.get('verified_sha256') and (set(issues[s['adapter_id']])-{'DEPENDENCY_REVISION_REQUIRES_EXPLICIT_ADOPT'} or s['verified_sha256']!=cp._hash(sources[s['adapter_id']]))]
    affected=[s['id'] for s in plan['steps'] if binding_issues or s['adapter_id'] in dependency_affected or s.get('invalidated') or states[s['adapter_id']] in ('BLOCKED','LOCK_CONFLICT')]
    impact=dict(scope='REGISTERED_CASE_CHAIN',unknown_scope='THIS_CASE' if binding_issues or dependency_unknown else None,
                directly_changed=direct,affected=affected,preserved=[s['id'] for s in plan['steps'] if s['id'] not in affected])
    note_blockers=[]
    if owner and plan.get('owner_amendments'):
        from .plan_source_conflicts import adoption_blockers
        note_blockers=adoption_blockers(c,parent,plan)
        if binding_issues:note_blockers=note_blockers+['OWNER_NOTE_CONTROLLED_CARRY_REQUIRED_FOR_REPLACEMENT']
    events=plan['events'] if owner else [{k:e[k] for k in ('id','revision','action','step_id')} for e in plan['events']]
    receipt=None
    if event and event['actor_id']==p['id']:
        plans=plan.get('history',[])+[plan];index=next(i for i,item in enumerate(plans) if item['id']==event['plan_id'])
        local=event['action']=='ADOPT' and event['revision']>1
        previous=plans[index-1] if index and event['action']=='ADOPT' and not local else None
        receipt=dict(id=event['id'],plan_id=event['plan_id'],revision=event['revision'],action=event['action'],step_id=event['step_id'],
                     request_key=event['request_key'],actor_ref=context['actor_ref'],expected_revision=event['revision']-1 if local else previous['revision'] if previous else 0 if event['action']=='ADOPT' else event['revision']-1,
                     previous_plan_id=plan['id'] if local else previous['id'] if previous else None)
    return dict(**context,scope=SCOPE,plan_id=plan['id'],revision=plan['revision'],state=status,steps=steps,
                template_migration=deepcopy(plan.get('template_migration')) if owner else None,
                template_availability=template_availability if owner else None,
                candidate_consumption=plan.get('candidate_consumption') if owner else None,
                partial_adoption=plan.get('partial_adoption') is True,
                overall_goal_state='PARTIAL' if plan.get('partial_adoption') is True else 'LOCAL_PLAN_ONLY',
                manual_goals=plan['adoption_preview']['partial_offer']['manual_goals'] if owner and plan.get('partial_adoption') is True else None,
                binding=plan['binding'] if owner else None,binding_issues=binding_issues if owner else None,
                required_goals=plan['required_goals'] if owner else None,goal_coverage=plan['goal_coverage'] if owner else None,
                history=plan.get('history',[]) if owner else [],events=events,event=event if owner else None,command_receipt=receipt,
                can_adopt=not note_blockers and template_current and owner and p.get('_plan_write') and bool(preview) and preview['state']=='COVERED_PREVIEW_ONLY' and (
                    bool(binding_issues) and not any(s.get('manual_lock') for s in plan['steps']) and len(plan.get('history',[]))<8 or
                    not binding_issues and bool(dependency_affected) and plan['revision']+1+sum(bool(s.get('manual_lock')) for s in plan['steps'])<=LIMIT and
                    not any(s.get('manual_lock') and s['adapter_id'] in dependency_affected for s in plan['steps']) and not any(not v['known'] for v in dependency_basis['collections'].values())),
                local_revision_required=plan.get('partial_adoption') is not True and not binding_issues and bool(dependency_affected),
                can_adopt_partial=bool(not plan.get('owner_amendments') and template_current and owner and p.get('_plan_write') and preview and preview['partial_offer']['can_adopt'] and (binding_issues or plan.get('partial_adoption') is True and dependency_affected) and not any(s.get('manual_lock') for s in plan['steps']) and len(plan.get('history',[]))<8),
                change_impact=impact if owner else None,
                **(dict(owner_note_blockers=note_blockers) if owner and plan.get('owner_amendments') else {}),
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
    with cp.connection(store) as c:
        p,parent=_context(store,c,token,id)
        plan=deepcopy(parent.get('service_case_plan'))
        return _view(store,c,p,parent,plan,observe=not (plan and _selection_plan(plan)))


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
            latest_dependencies=None
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
                               expected_plan_revision=expected,expected_source_sha256=plan['adoption_preview']['source_sha256'],required_goals=plan['required_goals'],reason=event['reason'],partial_adoption=True if plan.get('partial_adoption') is True else None)
                    if plan.get('candidate_consumption') is not None or (plan.get('adoption_request') or {}).get('candidate_id') is not None:
                        data=Adopt.model_validate(plan['adoption_request'])
                        if data.expected_plan_revision!=expected or data.reason!=event['reason']:raise ValueError()
                        candidates=_candidate_module(parent,data.candidate_id)
                        candidates.consumption_proof(parent,plan,data)
                    fp=cp._hash(dict(preparation_id=str(parent['id']),action='ADOPT',**_adopt_request(data)))
                    latest_dependencies=event.get('dependencies')
                    if latest_dependencies is not None:dependencies.validate(latest_dependencies)
                elif event['action']=='ADOPT':
                    if event['step_id'] is not None or event['actor_id']!=parent['owner_id']:raise ValueError()
                    expected=revision-1
                    patch=event['local_revision'];data=Adopt.model_validate(patch['request'])
                    if (data.local_revision is not True or data.expected_plan_revision!=expected or
                        data.required_goals!=plan['required_goals'] or
                        data.expected_request_revision!=plan['binding']['request_intent']['revision'] or
                        data.reason!=event['reason'] or patch['previous_sha256']!=(latest_dependencies['sha256'] if latest_dependencies else None) or
                        set(patch)!=({'request','previous_sha256','affected','preserved','source_change'} if data.opportunity_proof is not None else {'request','previous_sha256','affected','preserved'}) or
                        not isinstance(patch['affected'],list) or not isinstance(patch['preserved'],list) or
                        not patch['affected'] or len(set(patch['affected']+patch['preserved']))!=len(step_ids) or
                        set(patch['affected']+patch['preserved'])!=step_ids):raise ValueError()
                    latest_dependencies=event['dependencies'];dependencies.validate(latest_dependencies)
                    fp=cp._hash(dict(preparation_id=str(parent['id']),action='ADOPT',**_adopt_request(data)))
                elif event['action']=='TEMPLATE_UPGRADE':
                    from .template_migration import parse_apply_request,fingerprint
                    request=parse_apply_request(event['template_upgrade'])
                    fp=fingerprint(request.expected_instance_id,request)
                elif event['action'] in ('EDIT_NOTE','KEEP_MANUAL','ACCEPT_SOURCE','DEFER','KEEP_AND_CONTINUE','MERGE_NOTE'):
                    from .plan_source_conflicts import Command as NoteCommand,fingerprint as note_fingerprint
                    expected=revision-1
                    if event['plan_note']['version']==3:
                        from .material_package_continuation import Command as NoteCommand
                    data=NoteCommand.model_validate(event['plan_note']['request'])
                    if data.action!=event['action'] or data.expected_plan_revision!=revision-1 or data.reason!=event['reason']:raise ValueError()
                    fp=note_fingerprint(parent['id'],data)
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
            if latest_dependencies!=plan.get('dependency_manifest'):raise ValueError()
            dependencies.plan_proof(parent,plan)
            from .plan_source_conflicts import validate_plan_history
            validate_plan_history(parent,plan)
            from .template_migration import validate_plan
            validate_plan(parent,plan)
        return proofs
    except (KeyError,TypeError,ValueError,AttributeError):raise Conflict('original service plan recovery proof invalid')


@er.bounded
def recover(store,token,id,key=None,*,expected_request=None):
    """Current original actor reads an immutable key proof; never replay/observe-write."""
    with cp.connection(store) as c:
        p,parent=_context(store,c,token,id,key is not None)
        if key is not None:prep.key_lock(c,p,'service-case-plan:'+key)
        proofs=_recovery_proofs(parent)
        matches=[proof for proof in proofs if key is not None and proof[1]['actor_id']==p['id'] and proof[1]['request_key']==key]
        if len(matches)>1:raise Conflict('original service plan recovery key ambiguous')
        if key is not None and not matches and any(proof[1]['request_key']==key for proof in proofs):raise Denied('original service plan actor required')
        # Reuse the original global actor/key scope boundary without exposing another Case.
        rows=c.execute("SELECT id FROM preparations WHERE jsonb_path_exists(service_case_plan,'$.** ? (@.actor_id == $actor && @.request_key == $key)',%s)",(Jsonb(dict(actor=p['id'],key=key)),)).fetchall() if key is not None else []
        if any(row['id']!=id for row in rows):raise Conflict('original service plan recovery Case changed')
        request_verified=False;not_committed_final=False
        if expected_request is not None:
            if key is None:raise Conflict('exact original request key required')
            expected=Adopt.model_validate(expected_request)
            expected_fp=cp._hash(dict(preparation_id=str(id),action='ADOPT',**_adopt_request(expected)))
            if matches:
                if matches[0][1]['action']!='ADOPT' or matches[0][1]['fingerprint']!=expected_fp:
                    raise Conflict('original adoption receipt does not match saved request body')
                request_verified=True
            else:
                # Absence alone is inconclusive. Strictly advanced monotonically
                # persisted versions prove this immutable request cannot commit
                # after the parent/key locks are released either.
                not_committed_final=(parent['revision']>expected.expected_preparation_revision or
                    (parent.get('request_intent') or {}).get('revision',0)>expected.expected_request_revision)
                request_verified=True
        original=None
        if matches:
            plan,event,expected,previous=matches[0]
            step=next((s for s in plan['steps'] if s['id']==event['step_id']),None)
            if event['action'] in ('ADOPT','VERIFY','LOCK','UNLOCK'):
                if p['role']!='enterprise_operator':raise Denied('original owner plan action required')
            elif not step or p['role'] not in ROLES[step['adapter_id']]:raise Denied('original adapter actor required')
            original=dict(id=event['id'],plan_id=plan['id'],revision=event['revision'],action=event['action'],step_id=event['step_id'],
                          expected_revision=expected,previous_plan_id=plan['id'] if event['action']=='ADOPT' and event['revision']>1 else previous['id'] if previous and event['action']=='ADOPT' else None,
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
        view.update(current_preview=None,binding=None,required_goals=None,goal_coverage=None,can_adopt=False,can_adopt_partial=False,command_receipt=None,
                    events=[{k:e[k] for k in ('id','revision','action','step_id')} for e in view['events']],
                    history=[{k:h[k] for k in ('id','revision')} for h in view['history']],read_only=True)
        return dict(**({'saved_request_verified':request_verified,'not_committed_final':not_committed_final} if expected_request is not None else {}),scope=SCOPE,preparation_id=str(id),case_id=str(parent['case_id']),run_id=str(parent['run_id']),actor_ref=view['actor_ref'],
                    status='NO_REQUEST' if key is None else 'COMMITTED' if original else 'NOT_OBSERVED',event=original,current=view,
                    historical_only=True,automatically_replayed=False,read_only=True,case_goal_completed=False)


@contextmanager
def _adoption_connection(store,token,id,key,data):
    if data.candidate_id is None:
        with cp.connection(store) as c:yield c
        return
    # Resolve the locator under original authority, then recheck everything in
    # the final transaction. Existing receipts never need a publication lease.
    with cp.connection(store) as c:
        p,parent=_context(store,c,token,id,True)
        prep.key_lock(c,p,'service-case-plan:'+key)
        fp=cp._hash(dict(preparation_id=str(id),action='ADOPT',**_adopt_request(data)))
        if _replay(c,p,parent,key,fp):
            yield c
            return
        module=_candidate_module(parent,data.candidate_id)
        selected=_selected_candidates(module)
    with (_catalog_for_profile(store,module.PROFILE).connection() if selected else cp.connection(store)) as c:yield c


@er.bounded
def adopt(store,token,id,key,data,*,unadopted_only=False):
    with _adoption_connection(store,token,id,key,data) as c:
        p,parent=_context(store,c,token,id,True)
        if p['role']!='enterprise_operator':raise Denied('owner adopted plan required')
        prep.key_lock(c,p,'service-case-plan:'+key)
        fp=cp._hash(dict(preparation_id=str(id),action='ADOPT',**_adopt_request(data)))
        old=_replay(c,p,parent,key,fp);prior=deepcopy(parent.get('service_case_plan'))
        if old:
            if data.candidate_id is not None:_recovery_proofs(parent)
            return _view(store,c,p,parent,prior,old)
        from .plan_source_conflicts import adoption_guard
        adoption_guard(c,parent,prior)
        # Replacement creates a new plan identity. Until an explicit annotation
        # carry contract exists, preserve the current owner body in this plan.
        if prior and prior.get('owner_amendments') and data.local_revision is not True:
            raise Conflict('owner coordination note requires controlled carry before plan replacement')
        if prior and prior.get('template_migration'):
            from .template_migration import live_guard
            live_guard(store,c,parent,prior)
            if not data.local_revision:raise Conflict('migrated template plans require original explicit local revision')
        if unadopted_only and prior is not None:raise Conflict('template consumer cannot replace an already adopted original plan')
        intent=parent.get('request_intent')
        if not intent or data.required_goals!=intent['required_goals'] or intent['revision']!=data.expected_request_revision:
            raise Conflict('explicit supported current request goals required')
        if parent['revision']!=data.expected_preparation_revision:raise Conflict('preparation revision changed')
        candidates=_candidate_module(parent,data.candidate_id) if data.candidate_id is not None else None
        selected=candidates is not None and _selected_candidates(candidates)
        if selected:
            catalog=_catalog_for_profile(store,candidates.PROFILE)
            record=candidates.find(parent,data.candidate_id)
            current=candidates.current(store,c,p,parent,catalog,record['selection'])
        else:current=planning._proposal(store,c,p,parent)
        partial=data.partial_adoption is True
        if (not (current['state']=='PARTIAL' and current['partial_offer']['can_adopt'] if partial else current['state']=='COVERED_PREVIEW_ONLY' and _supported(parent)) or current['source_sha256']!=data.expected_source_sha256):
            raise Conflict('current bounded planning preview required')
        candidate_proof=None
        if data.candidate_id is not None:
            candidate_proof=candidates.consume(parent,current,data,now=candidates.clock(c))
        binding=cp._normal(_binding(c,parent))
        if cp._hash(binding['catalog'])!=current['catalog_sha256'] or cp._hash(binding['registry'])!=current['registry_sha256']:
            raise Conflict('catalog or registry changed during service plan adoption')
        if selected:
            binding['service_selection']=dict(profile=current['profile'],capability_catalog_sha256=current['capability_catalog_sha256'],
                selection=deepcopy(current['selection']))
        if (prior['revision'] if prior else 0)!=data.expected_plan_revision:raise Conflict('service plan revision changed')
        if data.local_revision:
            if partial or prior and prior.get('partial_adoption') is True:raise Conflict('partial plan dependency changes require explicit replacement')
            if not prior:raise Conflict('existing registered plan required for local revision')
            _recovery_proofs(parent)
            if _binding_issues(c,parent,prior,store=store):raise Conflict('changed request or service contract requires original explicit replacement')
            source_change=None
            if data.opportunity_proof is not None:
                from .source_change_adoption import build
                opportunity_preview,source_change,basis,affected=build(store,c,p,parent,data.opportunity_proof.card_id,current=current,**_source_scope(data))
                if not opportunity_preview['can_adopt'] or opportunity_preview['adoption']['opportunity_proof']!=data.opportunity_proof.model_dump():
                    raise Conflict('current opportunity source-change preview required')
            else:basis,affected,unknown=dependency_impact(store,c,parent,prior)
            if not affected or any(not v['known'] for v in basis['collections'].values()):raise Conflict('known current dependency patch required')
            if basis!=dependencies.manifest(prior['steps'],current['dependency_collections']):raise Conflict('dependency collection changed during local adoption')
            locks=[s for s in prior['steps'] if _manual_lock(prior,s)]
            if any(s['adapter_id'] in affected for s in locks):raise Conflict('affected locked decisions require explicit unlock')
            if prior['revision']+1+len(locks)>LIMIT:raise Conflict('event capacity reserved for explicit unlocks')
            if source_change is not None:
                # Re-read actual sources, original card/ledger and proposal after
                # source locks/waits, immediately before the single plan write.
                final_preview,final_change,final_basis,final_affected=build(store,c,p,parent,data.opportunity_proof.card_id,**_source_scope(data))
                if (not final_preview['can_adopt'] or final_change!=source_change or final_basis!=basis or final_affected!=affected):
                    raise Conflict('opportunity source changed during explicit adoption')
            before=prior.get('dependency_manifest')
            for a in affected:_invalidate(prior,int(a[1:]))
            prior['dependency_manifest']=basis;prior['revision']+=1
            event=_event(prior,p,key,fp,'ADOPT',data.reason)
            event['dependencies']=basis
            event['local_revision']=dict(request=_adopt_request(data),previous_sha256=before['sha256'] if before else None,
                                        affected=[s['id'] for s in prior['steps'] if s['adapter_id'] in affected],
                                        preserved=[s['id'] for s in prior['steps'] if s['adapter_id'] not in affected])
            if source_change is not None:event['local_revision']['source_change']=source_change
            _context(store,c,token,id,True);_save(c,parent,prior)
            return _view(store,c,p,parent,prior,event)
        history=[]
        if prior:
            if any(e['action'] in ('LOCK','UNLOCK') for e in prior['events']):_recovery_proofs(parent)
            if any(_manual_lock(prior,s) for s in prior['steps']):raise Conflict('locked service step decisions require explicit unlock before replacement')
            if not _binding_issues(c,parent,prior,store=store) and not (partial and prior.get('partial_adoption') is True and dependency_impact(store,c,parent,prior)[1]):raise Conflict('current adopted plan already exists')
            history=prior.pop('history',[])+[prior]
            if len(history)>8:raise Conflict('service plan replacement history limit reached')
        selected=[s for s in current['steps'] if not partial or s['id'] in current['partial_offer']['step_ids']]
        steps=[dict(id=str(uuid4()),adapter_id=s['id'],adapter=s['adapter'],adapter_revision=s['revision'],
                    depends_on=s['depends_on'],contract=cp._normal(s),coordination_state='PENDING',
                    verified_sha256=None,verified_sources=None,invalidated=False) for s in selected]
        plan=dict(id=str(uuid4()),revision=1,required_goals=list(data.required_goals),goal_coverage=current['goal_coverage'],
                  binding=binding,adoption_preparation_revision=parent['revision'],
                  adoption_preview=current,steps=steps,events=[],history=history)
        if partial:plan.update(partial_adoption=True,adoption_request=_adopt_request(data))
        if candidate_proof is not None:plan.update(candidate_consumption=candidate_proof,adoption_request=_adopt_request(data))
        plan['dependency_manifest']=dependencies.manifest(steps,current['dependency_collections'])
        event=_event(plan,p,key,fp,'ADOPT',data.reason)
        event['dependencies']=deepcopy(plan['dependency_manifest'])
        _context(store,c,token,id,True)
        if candidate_proof is not None:
            # Recheck the database wall clock after every authority/source wait,
            # immediately before saving the original plan and its event together.
            plan['candidate_consumption']=candidates.consume(parent,current,data,now=candidates.clock(c))
            event['candidate_consumption_sha256']=cp._hash(plan['candidate_consumption'])
        _save(c,parent,plan)
        return _view(store,c,p,parent,plan,event)


@er.bounded
def command(store,token,id,key,data):
    with cp.connection(store) as c:
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
        if data.action not in ('UNLOCK','VERIFY','LOCK'):
            from .template_migration import check_live
            check_live(store,c,parent,plan)
        if data.action in ('VERIFY','LOCK'):
            from .template_migration import live_guard
            live_guard(store,c,parent,plan)
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
