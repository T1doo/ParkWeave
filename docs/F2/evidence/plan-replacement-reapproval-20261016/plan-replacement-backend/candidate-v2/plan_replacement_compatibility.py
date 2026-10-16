"""Original V4 finite ServiceRelease preflight constrains explicit replacement.

This is an immutable observation bound by a fresh original Approval. It never
imports a saved can_record result as consent and never grants new authority.
"""
import re
from uuid import UUID
from . import controlled_plans as cp, service_case_steps as steps
from .store import Conflict,Denied

SCHEMA=1
PROFILE='ORIGINAL_V4_SERVICE_RELEASE_PLAN_REPLACEMENT_V1'
KEYS={'link_id','link_revision','snapshot_sha256','previous_delivery_context','previous_approved_plan_revision',
      'approved_plan_revision','previous_plan_id','replacement_plan_id','previous_definition_sha256',
      'replacement_definition_sha256','replacement_adoption_event_id','replacement_adoption_sha256',
      'compatibility','compatibility_sha256'}


def _definition(plan):
    from .case_resource_delivery import _definition
    return _definition(plan)


def _pairs(parent,plan,checker):
    from . import service_selection_candidates as selection,service_selection as refs
    try:
        if (plan.get('candidate_consumption') or {}).get('verification_basis',{}).get('validator_version')!=4:
            raise ValueError()
        record=selection.find(parent,plan['candidate_consumption']['candidate_id'])
        snapshot=record['document']['catalog_snapshot'];pairs=[]
        for ref in record['selection']['selections']:
            matches=[(r,i) for r in snapshot['releases'] for i in snapshot['instances']
                if r['release_id']==i['release_id'] and refs.selection_ref(r,i)==ref]
            if len(matches)!=1:raise ValueError()
            release,instance=matches[0]
            pairs.append((release,instance,checker._historical_source(release)))
        if not pairs or len(pairs)>16:raise ValueError()
        return record,pairs
    except (KeyError,ValueError,TypeError,AttributeError):raise Conflict('original immutable V4 selected pairs required') from None


def compare(store,c,p,parent,previous,current,*,historical=False):
    from .service_release_preflight import ServiceReleasePreflight,compare_v1
    from . import service_selection as refs
    bridge=getattr(store,'_isolated_plan_approval',None)
    checker=getattr(bridge,'plan_replacement_preflight',None)
    if (type(checker) is not ServiceReleasePreflight or checker.store is not store
        or getattr(store,'_isolated_service_capability_catalog',None) is not checker.catalog):
        raise Denied('explicit same-store original ServiceRelease preflight required')
    checker.consumer.validate_fixture()
    try:
        if any(plan.get('partial_adoption') or plan.get('template_migration') or plan.get('owner_amendments') for plan in (previous,current)):
            raise ValueError()
        goals={'LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION','LOCAL_INTERNAL_ACCEPTANCE',
            'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT','LOCAL_SYNTHETIC_COORDINATION_RECORDS','LOCAL_CASE_RECORD_RECHECK'}
        if (previous['required_goals']!=current['required_goals'] or previous['goal_coverage']!=current['goal_coverage']
            or len(current['required_goals'])!=6 or set(current['required_goals'])!=goals
            or any([s['adapter_id'] for s in plan['steps']]!=['P1','P2','P3','P4','P5'] for plan in (previous,current))):raise ValueError()
        # Original request and registry remain the same; only original catalog /
        # selected release instance source may have required the full ADOPT.
        for key in ('request_intent','original_goal','service_id','service_version','registry'):
            if previous['binding'][key]!=current['binding'][key]:raise ValueError()
        old_record,old_pairs=_pairs(parent,previous,checker);new_record,new_pairs=_pairs(parent,current,checker)
        if old_record['frozen_registry']!=new_record['frozen_registry']:raise ValueError()
        kinds={'synthetic-material-preparation','synthetic-resource-coordination','synthetic-local-record-recheck'}
        if (len(old_pairs)!=3 or len(new_pairs)!=3
            or any({r['service_id'] for r,_,_ in pairs}!=kinds for pairs in (old_pairs,new_pairs))):raise ValueError()
        reports=[];seen=set();targets=[]
        for old,old_instance,old_source in old_pairs:
            candidates=[(target,instance,source) for target,instance,source in new_pairs
                if target['service_id']==old['service_id'] and target['owner_org_id']==old['owner_org_id'] and source['scope']==old_source['scope']]
            if len(candidates)!=1:raise ValueError()
            target,instance,source=candidates[0]
            key=(target['release_id'],instance['instance_id'])
            if key in seen:raise ValueError()
            seen.add(key)
            comparison=compare_v1(previous,old,old_instance,target,instance,old_source,source,old_record['frozen_registry'])
            if comparison['classification'] not in ('COMPATIBLE','NEEDS_RECHECK') or comparison['blocking_reasons']:raise ValueError()
            if not historical:
                actual,actual_instance,actual_source,source_version=checker._target(c,parent,instance['instance_id'])
                if (actual,actual_instance,actual_source)!=(target,instance,source):raise ValueError()
                targets.append((instance['instance_id'],refs.selection_ref(target,instance),cp._hash(source_version)))
            reports.append(dict(original_ref=refs.selection_ref(old,old_instance),target_ref=refs.selection_ref(target,instance),
                original_source_sha256=cp._hash(old_source),target_source_sha256=cp._hash(source),comparison=comparison))
        if not historical:
            # The original target reader takes original catalog/authority locks
            # and checks latest immutable template head; recheck every target
            # after all mapping reads, within the existing delivery transaction.
            for instance_id,ref,version in targets:
                release,instance,_,source_version=checker._target(c,parent,instance_id)
                if refs.selection_ref(release,instance)!=ref or cp._hash(source_version)!=version:raise ValueError()
        return dict(schema=SCHEMA,profile=PROFILE,classification='NEEDS_RECHECK',
            previous_candidate_id=old_record['id'],replacement_candidate_id=new_record['id'],
            previous_candidate_sha256=old_record['candidate_sha256'],replacement_candidate_sha256=new_record['candidate_sha256'],
            frozen_registry_sha256=cp._hash(old_record['frozen_registry']),pairs=reports,
            affected=[s['id'] for s in current['steps']],preserved=[],
            automatic_adoption=False,automatic_approval=False,automatic_release=False)
    except (KeyError,TypeError,ValueError,AttributeError):
        raise Conflict('known nonbreaking original V4 replacement preflight required') from None


def binding(store,c,p,parent,data,anchor,prior,*,historical=False):
    root=parent['service_case_plan'];plans=[*root.get('history',[]),root]
    old_id=str(data.expected_previous_plan_id)
    matches=[i for i,plan in enumerate(plans) if plan['id']==old_id]
    if len(matches)!=1 or matches[0]+1>=len(plans):raise Conflict('original adjacent replacement history required')
    index=matches[0];previous=plans[index];current=plans[index+1]
    if old_id!=prior['context'].get('plan_id') or (not historical and current['id']!=root['id']):
        raise Conflict('latest original plan replacement required')
    if current['id']==old_id or previous['revision']<prior['approved_plan_revision']:raise Conflict('original replacement identity required')
    approved=getattr(data,'expected_plan_revision',current['revision']);event=current['events'][0]
    if (event['action']!='ADOPT' or event['revision']!=1 or event['plan_id']!=current['id']
        or event['actor_id']!=parent['owner_id'] or event.get('local_revision') is not None
        or not 1<=approved<=current['revision'] or any(e['action']=='ADOPT' and 1<e['revision']<=approved for e in current['events'])):
        raise Conflict('explicit original full replacement adoption required')
    comparison=compare(store,c,p,parent,previous,current,historical=historical)
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
