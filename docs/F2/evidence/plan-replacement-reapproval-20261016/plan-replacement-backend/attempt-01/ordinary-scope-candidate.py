"""Finite original synthetic catalog replacement eligibility; never an approval.

No V4 ServiceRelease/Instance migration, new action, partial graph or parameter
schema is inferred. Existing explicit replacement and fresh Approval remain
separate original commands. The immutable report is bound by that Approval.
"""
import re
from uuid import UUID
from . import controlled_plans as cp, bounded_planning as planning
from .store import Conflict

SCHEMA=1
PROFILE='ORIGINAL_SYNTHETIC_CATALOG_PLAN_REPLACEMENT_V1'
KEYS={'link_id','link_revision','snapshot_sha256','previous_delivery_context','previous_approved_plan_revision',
      'approved_plan_revision','previous_plan_id','replacement_plan_id','previous_definition_sha256',
      'replacement_definition_sha256','replacement_adoption_event_id','replacement_adoption_sha256',
      'compatibility','compatibility_sha256'}


def _definition(plan):
    from .case_resource_delivery import _definition
    return _definition(plan)


def compare(previous,current):
    """Exhaustive allowlist for the ordinary catalog only; unknown is rejected."""
    try:
        if any(p.get('partial_adoption') or p.get('candidate_consumption') or p.get('template_migration')
               or p.get('owner_amendments') or p.get('adoption_request') for p in (previous,current)):
            raise ValueError()
        expected_binding={'request_intent','original_goal','service_id','service_version','catalog','registry'}
        old,new=previous['binding'],current['binding']
        if set(old)!=expected_binding or set(new)!=expected_binding:raise ValueError()
        # The original request, six-target coverage, registered adapters/actions,
        # and all executable fields must be exactly unchanged.
        for k in ('request_intent','original_goal','service_id','service_version','registry'):
            if old[k]!=new[k]:raise ValueError()
        if old['registry']!=cp._normal(dict(steps=planning.REGISTRY,actions=planning.ACTIONS)):raise ValueError()
        if previous['required_goals']!=current['required_goals'] or previous['goal_coverage']!=current['goal_coverage']:raise ValueError()
        before,after=old['catalog'],new['catalog'];base={'service_id','version','source','namespace','qualification'}
        if set(before) not in (base,base|{'cooperative_catalog'}) or set(after) not in (base,base|{'cooperative_catalog'}):raise ValueError()
        if set(before)!=set(after):raise ValueError()
        if not cp.binding_catalog_known(before) or not cp.binding_catalog_known(after):raise ValueError()
        if any(before[k]!=after[k] for k in base-{'source'}):raise ValueError()
        if before['qualification']!='NOT_EVALUATED' or after['qualification']!='NOT_EVALUATED':raise ValueError()
        a,b=before['source'],after['source']
        if set(a) not in ({'kind','id','revision'},{'kind','id','revision','statement'}) or set(b)!=set(a):raise ValueError()
        if any(a[k]!=b[k] for k in set(a)-{'revision'}):raise ValueError()
        if a['kind']!='SYNTHETIC' or a['kind']!=b['kind'] or a['id']!=b['id'] or not isinstance(a['id'],str) or not a['id']:raise ValueError()
        if any(type(v) is not str or re.fullmatch('[1-9][0-9]{0,3}',v) is None for v in (a['revision'],b['revision'])):raise ValueError()
        if int(b['revision'])<=int(a['revision']):raise ValueError()
        if 'cooperative_catalog' in before:
            for descriptor in (before['cooperative_catalog'],after['cooperative_catalog']):
                if (set(descriptor)!={'scope','id','revision','sha256','state'} or descriptor['scope']!='ISOLATED_CATALOG_APPROVAL_COORDINATION_V1'
                    or descriptor['state']!='ACTIVE' or type(descriptor['revision']) is not int or not 1<=descriptor['revision']<=32):raise ValueError()
                UUID(descriptor['id'])
                if re.fullmatch('[a-f0-9]{64}',descriptor['sha256']) is None:raise ValueError()
            if after['cooperative_catalog']['revision']<=before['cooperative_catalog']['revision']:raise ValueError()
        def contract(plan):
            return [{k:s[k] for k in ('adapter_id','adapter','adapter_revision','depends_on','contract')} for s in plan['steps']]
        if contract(previous)!=contract(current):raise ValueError()
        adapters=[s['adapter_id'] for s in current['steps']]
        if adapters!=['P'+str(i) for i in range(1,len(adapters)+1)] or 'P2' not in adapters:raise ValueError()
        # All old coordination decisions stay in history; none authorize or
        # silently populate the new plan. Existing ADOPT owns unlock rules.
        if any(s.get('manual_lock') for s in previous['steps']):raise ValueError()
        result=dict(schema=SCHEMA,profile=PROFILE,classification='NEEDS_RECHECK',
            old_catalog_sha256=cp._hash(before),new_catalog_sha256=cp._hash(after),
            registered_contract_sha256=cp._hash(contract(current)),
            required_goals_sha256=cp._hash(current['required_goals']),
            affected=[s['id'] for s in current['steps']],preserved=[],
            automatic_adoption=False,automatic_approval=False,automatic_release=False)
        return result
    except (KeyError,TypeError,ValueError,AttributeError):
        raise Conflict('known nonbreaking original catalog replacement required') from None


def binding(parent,data,anchor,prior,*,historical=False):
    root=parent['service_case_plan'];plans=[*root.get('history',[]),root]
    old_id=str(data.expected_previous_plan_id)
    matches=[i for i,p in enumerate(plans) if p['id']==old_id]
    if len(matches)!=1 or matches[0]+1>=len(plans):raise Conflict('original adjacent replacement history required')
    index=matches[0];previous=plans[index];current=plans[index+1]
    if (old_id!=prior['context'].get('plan_id') or (not historical and current['id']!=root['id'])):
        raise Conflict('latest original plan replacement required')
    if current['id']==old_id or previous['revision']<prior['approved_plan_revision']:raise Conflict('original replacement identity required')
    approved=getattr(data,'expected_plan_revision',current['revision'])
    event=current['events'][0]
    if (event['action']!='ADOPT' or event['revision']!=1 or event['plan_id']!=current['id']
        or event['actor_id']!=parent['owner_id'] or event.get('local_revision') is not None
        or not 1<=approved<=current['revision'] or any(e['action']=='ADOPT' and 1<e['revision']<=approved for e in current['events'])):
        raise Conflict('explicit original full replacement adoption required')
    comparison=compare(previous,current)
    return dict(link_id=str(anchor['id']),link_revision=anchor['revision'],snapshot_sha256=cp._hash(anchor['snapshot']),
        previous_delivery_context=prior['context'],previous_approved_plan_revision=prior['approved_plan_revision'],
        approved_plan_revision=approved,previous_plan_id=old_id,replacement_plan_id=current['id'],
        previous_definition_sha256=_definition(previous),replacement_definition_sha256=_definition(current),
        replacement_adoption_event_id=event['id'],replacement_adoption_sha256=cp._hash(event),
        compatibility=comparison,compatibility_sha256=cp._hash(comparison))


def validate_binding(value,data,context):
    if (not isinstance(value,dict) or set(value)!=KEYS or type(value['link_revision']) is not int
        or value['link_revision']!=data.expected_link_revision or value['previous_plan_id']!=str(data.expected_previous_plan_id)
        or value['previous_plan_id']==value['replacement_plan_id'] or value['replacement_plan_id']!=context['plan_id']
        or value['previous_delivery_context'].get('plan_id')!=value['previous_plan_id']
        or type(value['approved_plan_revision']) is not int or value['approved_plan_revision']!=data.expected_plan_revision
        or type(value['previous_approved_plan_revision']) is not int or not 1<=value['previous_approved_plan_revision']<=64
        or not isinstance(value['compatibility'],dict) or value['compatibility_sha256']!=cp._hash(value['compatibility'])
        or value['compatibility'].get('profile')!=PROFILE or value['compatibility'].get('schema')!=SCHEMA
        or value['compatibility'].get('classification')!='NEEDS_RECHECK'):
        raise ValueError('original replacement Approval binding required')
    for key in ('link_id','previous_plan_id','replacement_plan_id','replacement_adoption_event_id'):UUID(value[key])
    for key in ('snapshot_sha256','previous_definition_sha256','replacement_definition_sha256','replacement_adoption_sha256','compatibility_sha256'):
        if type(value[key]) is not str or re.fullmatch('[a-f0-9]{64}',value[key]) is None:raise ValueError('replacement proof digest required')
