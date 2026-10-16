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


def compare(store,c,p,parent,previous,current,*,historical=False,approved_revision=None,frontier_profile=None,consumption_key=None):
    from .service_release_preflight import ServiceReleasePreflight,compare_v1
    from . import service_selection as refs
    bridge=getattr(store,'_isolated_plan_approval',None)
    checker=getattr(bridge,'plan_replacement_preflight',None)
    if (type(checker) is not ServiceReleasePreflight or checker.store is not store
        or getattr(store,'_isolated_service_capability_catalog',None) is not checker.catalog):
        raise Denied('explicit same-store original ServiceRelease preflight required')
    checker.consumer.validate_fixture()
    try:
        if previous.get('partial_adoption') or current.get('partial_adoption'):raise ValueError()
        # The historical predecessor was already closed when the new plan was
        # adopted. No unsupported predecessor metadata can be introduced later.
        if previous.get('template_migration') or previous.get('owner_amendments'):raise ValueError()
        if not historical:
            if current.get('template_migration') or current.get('owner_amendments'):raise ValueError()
        else:
            # Later lawful annotations/upgrades do not erase the consumed fact.
            # Their original event proofs have already been validated; metadata
            # only qualifies here if its first original event is after approval.
            from .plan_source_conflicts import ACTIONS as note_actions
            for metadata,actions in (('owner_amendments',set(note_actions)),('template_migration',{'TEMPLATE_UPGRADE'})):
                if current.get(metadata):
                    events=[e for e in current['events'] if e['action'] in actions]
                    if (type(approved_revision) is not int or not events
                        or any(e['revision']<=approved_revision for e in events)):raise ValueError()
        goals={'LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION','LOCAL_INTERNAL_ACCEPTANCE',
            'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT','LOCAL_SYNTHETIC_COORDINATION_RECORDS','LOCAL_CASE_RECORD_RECHECK'}
        if (previous['required_goals']!=current['required_goals'] or previous['goal_coverage']!=current['goal_coverage']
            or len(current['required_goals'])!=6 or set(current['required_goals'])!=goals
            or any([s['adapter_id'] for s in plan['steps']]!=['P1','P2','P3','P4','P5'] for plan in (previous,current))):raise ValueError()
        # This slice supports an originally completed known Case chain only.
        # A fresh plan must not turn missing old business outputs into known
        # compatibility. The predecessor is immutable after the full ADOPT;
        # prove its original VERIFY events, not current readiness of a retired
        # catalog/source or an observation's later invalidation flag.
        qualification=None
        if frontier_profile is None:
            from .case_goal_results import verification
            for step in previous['steps']:
                if (step.get('coordination_state')!='VERIFIED'
                    or type(step.get('verified_sha256')) is not str
                    or re.fullmatch('[a-f0-9]{64}',step['verified_sha256']) is None
                    or type(step.get('verified_sources')) is not dict
                    or step['verified_sha256']!=cp._hash(step['verified_sources'])
                    or verification(parent,previous,step) is None):
                    raise Conflict('original complete verified five-step replacement predecessor required')
        elif frontier_profile=='P3_NEVER_ACCEPTED_CLOSED_V1':
            from .p3_never_accepted_closure import _protocol
            protocol=_protocol(store)
            if not getattr(bridge,'p3_closure_enabled',False) or bridge.p3_closure_frontier is not protocol:raise Denied('explicit enabled P3 closure scope required')
            qualification=protocol.qualify(c,parent,previous,historical=historical,consumption_key=consumption_key)
        else:
            from .business_frontier import KnownNotStartedFrontier
            protocol=getattr(bridge,'known_not_started_frontier',None)
            if (frontier_profile!='KNOWN_NOT_STARTED_V1' or not getattr(bridge,'known_not_started_enabled',False)
                or type(protocol) is not KnownNotStartedFrontier or getattr(store,'_known_not_started_frontier',None) is not protocol):
                raise Denied('explicit issued known-not-started scope required')
            qualification=protocol.qualify(c,parent,previous,historical=historical,consumption_key=consumption_key)
        # Original request and registry remain the same; only original catalog /
        # selected release instance source may have required the full ADOPT.
        for key in ('request_intent','original_goal','service_id','service_version','registry'):
            if previous['binding'][key]!=current['binding'][key]:raise ValueError()
        if not historical and frontier_profile is None:
            # Reuse the original preflight's finite current-known gate against
            # the actual parent/root. Catalog binding changes require recheck;
            # missing authority, expired/cancelled evidence or unknown source
            # graphs cannot be converted into a replacement opportunity.
            from . import source_change_adoption as adoption,typed_source_impact as typed
            issues,sources,_=steps.current_sources(store,c,parent,previous)
            sources={step['adapter_id']:sources[step['adapter_id']] for step in previous['steps']}
            before=adoption.evidence_sources(parent,previous)
            basis,_,_=steps.dependency_impact(store,c,parent,previous)
            graph=typed.build(parent,previous,before,sources,previous.get('dependency_manifest'),basis)
            ids=[step['id'] for step in previous['steps']]
            valid=(type(graph) is dict and type(graph.get('schema')) is int and graph['schema']==1
                and type(graph.get('affected')) is list and type(graph.get('preserved')) is list
                and all(type(value) is str for value in graph['affected']+graph['preserved'])
                and len(graph['affected'])==len(set(graph['affected'])) and len(graph['preserved'])==len(set(graph['preserved']))
                and not set(graph['affected'])&set(graph['preserved']) and set(graph['affected'])|set(graph['preserved'])==set(ids)
                and graph.get('unknown_scope','UNSUPPORTED') is None and type(graph.get('sha256')) is str
                and re.fullmatch('[a-f0-9]{64}',graph['sha256']) is not None)
            if not valid or any(adoption.unavailable_sources().intersection(value) for value in issues.values()):
                raise Conflict('original current known replacement source graph required')
        if not historical and frontier_profile is not None:
            from .source_change_adoption import unavailable_sources
            issues,source_values,_=steps.current_sources(store,c,parent,previous)
            basis,_,unknown=steps.dependency_impact(store,c,parent,previous)
            if (unknown or any(not value['known'] for value in basis['collections'].values())
                or any(unavailable_sources().intersection(issues[adapter]) for adapter in ('P1','P2'))
                or any(type(source_values.get(adapter)) is not dict or not source_values[adapter] for adapter in ('P1','P2'))):
                raise Conflict('known original P1/P2 sources and complete empty tail required')
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
        result=dict(schema=SCHEMA,profile=PROFILE,classification='NEEDS_RECHECK',
            previous_candidate_id=old_record['id'],replacement_candidate_id=new_record['id'],
            previous_candidate_sha256=old_record['candidate_sha256'],replacement_candidate_sha256=new_record['candidate_sha256'],
            frozen_registry_sha256=cp._hash(old_record['frozen_registry']),pairs=reports,
            affected=[s['id'] for s in current['steps']],preserved=[],
            automatic_adoption=False,automatic_approval=False,automatic_release=False)
        if qualification is not None:
            schema,profile=(3,'ORIGINAL_V4_SERVICE_RELEASE_P3_NEVER_ACCEPTED_CLOSED_V1') if frontier_profile=='P3_NEVER_ACCEPTED_CLOSED_V1' else (2,'ORIGINAL_V4_SERVICE_RELEASE_KNOWN_NOT_STARTED_V1')
            result.update(schema=schema,profile=profile,qualification=qualification)
        return result
    except (KeyError,TypeError,ValueError,AttributeError):
        raise Conflict('known nonbreaking original V4 replacement preflight required') from None


def binding(store,c,p,parent,data,anchor,prior,*,historical=False,consumption_key=None):
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
    comparison=compare(store,c,p,parent,previous,current,historical=historical,approved_revision=approved,frontier_profile=data.replacement_frontier_profile,consumption_key=consumption_key)
    return dict(link_id=str(anchor['id']),link_revision=anchor['revision'],snapshot_sha256=cp._hash(anchor['snapshot']),
        previous_delivery_context=prior['context'],previous_approved_plan_revision=prior['approved_plan_revision'],
        approved_plan_revision=approved,previous_plan_id=old_id,replacement_plan_id=current['id'],
        previous_definition_sha256=_definition(previous),replacement_definition_sha256=_definition(current),
        replacement_adoption_event_id=event['id'],replacement_adoption_sha256=cp._hash(event),
        compatibility=comparison,compatibility_sha256=cp._hash(comparison))


def _validate_complete_binding(value,data,context):
    from .service_release_preflight import Reference
    def sha(v):return type(v) is str and re.fullmatch('[a-f0-9]{64}',v) is not None
    def uuid(v):
        if type(v) is not str:return False
        try:return str(UUID(v))==v
        except (ValueError,TypeError,AttributeError):return False
    def ids(v,*,length=None):
        return type(v) is list and all(uuid(x) for x in v) and len(v)==len(set(v)) and (length is None and len(v)<=5 or len(v)==length)
    def exact(v,keys):return type(v) is dict and set(v)==set(keys)
    def require(condition):
        if not condition:raise ValueError('original replacement Approval binding required')
    require(exact(value,KEYS))
    require(type(value['link_revision']) is int and value['link_revision']==data.expected_link_revision
        and value['previous_plan_id']==str(data.expected_previous_plan_id)
        and value['previous_plan_id']!=value['replacement_plan_id'] and value['replacement_plan_id']==context['plan_id']
        and type(value['previous_delivery_context']) is dict
        and value['previous_delivery_context'].get('plan_id')==value['previous_plan_id']
        and value['previous_definition_sha256']==value['previous_delivery_context'].get('plan_definition_sha256')
        and value['replacement_definition_sha256']==context.get('plan_definition_sha256')
        and type(value['approved_plan_revision']) is int and value['approved_plan_revision']==data.expected_plan_revision
        and 1<=value['approved_plan_revision']<=64
        and type(value['previous_approved_plan_revision']) is int and 1<=value['previous_approved_plan_revision']<=64)
    require(all(value['previous_delivery_context'].get(k)==context.get(k) for k in
        ('scope','preparation_id','case_id','run_id','owner_id','park_id','org_id','service_id','service_version')))
    require(all(uuid(value[k]) for k in ('link_id','previous_plan_id','replacement_plan_id','replacement_adoption_event_id')))
    require(all(sha(value[k]) for k in ('snapshot_sha256','previous_definition_sha256','replacement_definition_sha256','replacement_adoption_sha256','compatibility_sha256')))
    report=value['compatibility']
    require(exact(report,('schema','profile','classification','previous_candidate_id','replacement_candidate_id',
        'previous_candidate_sha256','replacement_candidate_sha256','frozen_registry_sha256','pairs','affected','preserved',
        'automatic_adoption','automatic_approval','automatic_release')))
    require(type(report['schema']) is int and report['schema']==SCHEMA and report['profile']==PROFILE
        and report['classification']=='NEEDS_RECHECK' and value['compatibility_sha256']==cp._hash(report)
        and all(report[k] is False for k in ('automatic_adoption','automatic_approval','automatic_release'))
        and uuid(report['previous_candidate_id']) and uuid(report['replacement_candidate_id'])
        and report['previous_candidate_id']!=report['replacement_candidate_id']
        and all(sha(report[k]) for k in ('previous_candidate_sha256','replacement_candidate_sha256','frozen_registry_sha256'))
        and ids(report['affected'],length=5) and type(report['preserved']) is list and report['preserved']==[]
        and type(report['pairs']) is list and len(report['pairs'])==3)
    old_refs=[];new_refs=[]
    for pair in report['pairs']:
        require(exact(pair,('original_ref','target_ref','original_source_sha256','target_source_sha256','comparison')))
        require(sha(pair['original_source_sha256']) and sha(pair['target_source_sha256']))
        for key,seen in (('original_ref',old_refs),('target_ref',new_refs)):
            ref=Reference.model_validate(pair[key]).model_dump()
            require(ref==pair[key] and ref not in seen);seen.append(ref)
        comparison=pair['comparison']
        require(exact(comparison,('classification','differences','affected','blocking_reasons')))
        require(comparison['classification'] in ('COMPATIBLE','NEEDS_RECHECK') and ids(comparison['affected'])
            and type(comparison['blocking_reasons']) is list and comparison['blocking_reasons']==[]
            and type(comparison['differences']) is list and len(comparison['differences'])<=64)
        for difference in comparison['differences']:
            require(exact(difference,('field','category','before_sha256','after_sha256'))
                and type(difference['field']) is str and 1<=len(difference['field'])<=120
                and difference['category'] in ('INFORMATIONAL','SOURCE','CONTRACT','MAPPING')
                and sha(difference['before_sha256']) and sha(difference['after_sha256']))


def verify_history(store,c,parent,link,receipt):
    """Read-only actual receipt/link/plan reconstruction, strictly descending.

    catalog_decision / Approval._view -> this helper -> _ledger,
    _recovery_proofs, _history, binding(historical=True). None calls _view,
    delivery._verify, capacity confirmation or a current target publication.
    """
    from .service_plan_approval import _ledger,verify_receipt,Proposal,REPLACEMENT_PURPOSE,REAPPROVAL_PURPOSE
    from . import case_resources as cr
    if not receipt.get('plan_approval'):return
    _,items=_ledger(parent)
    own=items[receipt['plan_approval']['id']]
    context=own['proposal']['binding']['context']
    # Preserve the existing source-only protocol; additionally prove chains
    # which contain this new replacement profile, including later local ADOPT.
    probe=context;contains_replacement=False
    for _ in range(64):
        if 'plan_replacement' in probe:contains_replacement=True;break
        anchor=probe.get('source_reapproval')
        if not isinstance(anchor,dict):break
        probe=anchor.get('previous_delivery_context',{})
        if not isinstance(probe,dict):break
    if not contains_replacement:return
    if store is None:raise Denied('original replacement history store required')
    steps._recovery_proofs(parent)
    p=c.execute('SELECT * FROM principals WHERE id=%s',(parent['owner_id'],)).fetchone()
    if not p:raise Denied('original replacement owner proof required')
    rows=cr._history(c,p,parent);seen=set()
    for _ in range(64):
        if link['revision'] in seen:raise Conflict('descending original replacement history required')
        seen.add(link['revision'])
        proof=receipt.get('delivery_binding')
        actual=c.execute('SELECT payload,fingerprint,combination_id FROM synthetic_resource_combination_receipts WHERE actor_id=%s AND request_key=%s',
            (p['id'],link['request_key'])).fetchone()
        if (not actual or actual['payload']!=receipt or actual['fingerprint']!=link['fingerprint']
            or actual['combination_id']!=link['combination_id']):raise Conflict('original replacement database receipt changed')
        if (not isinstance(proof,dict) or link['snapshot'].get('delivery_binding')!=proof
            or link['snapshot'].get('plan_approval')!=receipt.get('plan_approval')
            or str(link['combination_id'])!=receipt.get('combination_id')
            or proof.get('request_key')!=link['request_key'] or proof.get('fingerprint')!=link['fingerprint']):
            raise Conflict('exact original replacement receipt link required')
        verify_receipt(parent,receipt,link['snapshot'].get('plan_approval'),link_revision=link['revision'])
        item=items[receipt['plan_approval']['id']]
        data=Proposal.model_validate({k:v for k,v in item['proposal']['request'].items() if k!='action'}).delivery
        context=proof.get('context')
        if context!=item['proposal']['binding']['context'] or proof.get('approved_plan_revision')!=data.expected_plan_revision:
            raise Conflict('original replacement approved context changed')
        if data.expected_link_revision is None:return
        name='plan_replacement' if data.expected_previous_plan_id is not None else 'source_reapproval'
        anchor=context.get(name)
        anchors=[r for r in rows if r['revision']==data.expected_link_revision]
        if not isinstance(anchor,dict) or len(anchors)!=1:raise Conflict('original replacement history anchor required')
        old=anchors[0];prior=old['snapshot'].get('delivery_binding')
        old_receipt=c.execute('SELECT payload,fingerprint FROM synthetic_resource_combination_receipts WHERE actor_id=%s AND request_key=%s',
            (p['id'],old['request_key'])).fetchone()
        if (old['revision']>=link['revision'] or old['revision']+1!=link['revision'] or old['actor_id']!=p['id']
            or anchor.get('link_id')!=str(old['id']) or anchor.get('link_revision')!=old['revision']
            or anchor.get('snapshot_sha256')!=cp._hash(old['snapshot']) or not isinstance(prior,dict)
            or anchor.get('previous_delivery_context')!=prior.get('context')
            or anchor.get('previous_approved_plan_revision')!=prior.get('approved_plan_revision')
            or not old_receipt or old_receipt['fingerprint']!=old['fingerprint']
            or old_receipt['payload'].get('delivery_binding')!=prior
            or old_receipt['payload'].get('plan_approval')!=old['snapshot'].get('plan_approval')):
            raise Conflict('original descending replacement receipt proof changed')
        if name=='plan_replacement':
            if item['proposal']['binding']['purpose']!=REPLACEMENT_PURPOSE:raise Conflict('original replacement purpose required')
            actual=binding(store,c,p,parent,data,old,prior,historical=True,consumption_key=proof['request_key'])
            if actual!=anchor:raise Conflict('original replacement immutable profile changed')
        else:
            if item['proposal']['binding']['purpose']!=REAPPROVAL_PURPOSE:raise Conflict('original source continuation purpose required')
            plans=[*parent['service_case_plan'].get('history',[]),parent['service_case_plan']]
            matches=[plan for plan in plans if plan['id']==context.get('plan_id')==prior['context'].get('plan_id')]
            if len(matches)!=1:raise Conflict('original source continuation plan required')
            plan=matches[0];events=[e for e in plan['events'] if e['action']=='ADOPT' and e['revision']<=data.expected_plan_revision]
            event=events[-1] if events else {};patch=event.get('local_revision') or {};change=patch.get('source_change')
            p2=next((s['id'] for s in plan['steps'] if s['adapter_id']=='P2'),None)
            if (not isinstance(change,dict) or event.get('revision',0)<=prior['approved_plan_revision']
                or p2 not in patch.get('affected',[]) or p2 not in change.get('affected',[])
                or patch.get('request',{}).get('opportunity_proof') is None):raise Conflict('original source continuation adoption required')
            actual=dict(link_id=str(old['id']),link_revision=old['revision'],snapshot_sha256=cp._hash(old['snapshot']),
                previous_delivery_context=prior['context'],previous_approved_plan_revision=prior['approved_plan_revision'],
                approved_plan_revision=data.expected_plan_revision,source_adoption_event_id=event['id'],source_adoption_revision=event['revision'],
                source_adoption_sha256=cp._hash(event),source_change_sha256=change['sha256'])
            if actual!=anchor:raise Conflict('original source continuation immutable profile changed')
        link=old;receipt=old_receipt['payload']
    raise Conflict('bounded original replacement history required')


def validate_binding(value,data,context):
    if data.replacement_frontier_profile is None:return _validate_complete_binding(value,data,context)
    if data.replacement_frontier_profile=='P3_NEVER_ACCEPTED_CLOSED_V1':
        from .p3_never_accepted_closure import validate_qualification
        schema,profile=3,'ORIGINAL_V4_SERVICE_RELEASE_P3_NEVER_ACCEPTED_CLOSED_V1'
    else:
        from .business_frontier import validate_qualification
        schema,profile=2,'ORIGINAL_V4_SERVICE_RELEASE_KNOWN_NOT_STARTED_V1'
    if type(value) is not dict or set(value)!=KEYS:raise ValueError('strict original replacement proof required')
    report=value.get('compatibility')
    original_keys={'schema','profile','classification','previous_candidate_id','replacement_candidate_id','previous_candidate_sha256',
        'replacement_candidate_sha256','frozen_registry_sha256','pairs','affected','preserved','automatic_adoption','automatic_approval','automatic_release'}
    if (type(report) is not dict or set(report)!=original_keys|{'qualification'} or type(report['schema']) is not int or report['schema']!=schema
        or report['profile']!=profile or value['compatibility_sha256']!=cp._hash(report)):
        raise ValueError('strict versioned known-not-started replacement required')
    validate_qualification(report['qualification'],data,context)
    old_report={k:v for k,v in report.items() if k!='qualification'};old_report.update(schema=SCHEMA,profile=PROFILE)
    old_value=dict(value,compatibility=old_report,compatibility_sha256=cp._hash(old_report))
    return _validate_complete_binding(old_value,data,context)
